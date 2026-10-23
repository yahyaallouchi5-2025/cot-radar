"""
stagionalita.py - STAGIONALITA' su piu' scale: prossime 4 settimane, mesi, giorni della settimana.

Domanda: "negli anni passati, in questo periodo / in questo mese / in questo giorno della settimana,
lo strumento e' salito o sceso?"  I prezzi arrivano dall'archivio permanente (storico.py).

1) FINESTRA (prossime 4 settimane, stesso orizzonte del backtest "storico"):
   per ogni anno il rendimento da oggi (stessa data) a 28 giorni dopo.
2) MESI: rendimento di ogni mese (fine mese su fine mese) per ogni anno + mappa anni x mesi.
3) GIORNI DELLA SETTIMANA: rendimento giornaliero medio di lunedi', martedi'... su tutta la storia.
   NB: i cambi FRED sono rilevati a mezzogiorno di New York, quindi "mercoledi'" = da martedi'
   12:00 a mercoledi' 12:00 (ora di New York).

FILTRI contro le coincidenze (un effetto vale solo se li supera TUTTI, altrimenti "non affidabile"):
  - abbastanza dati (almeno 10 anni; per i giorni almeno 500 osservazioni);
  - trend tolto: si sottrae il movimento medio dello strumento, cosi' resta solo l'effetto calendario;
  - stabile nel tempo: prima meta' e seconda meta' degli anni devono andare nello stesso verso;
  - stabile nelle date (solo finestra): spostando la finestra di 7 giorni avanti/indietro non cambia verso;
  - abbastanza forte: almeno 65% (o al massimo 35%) degli anni nello stesso verso;
    per i mesi anche un test t >= 2; per i giorni t >= 2,58 (5 giorni confrontati insieme: soglia piu' severa).

PESO nel punteggio: lo decide il BACKTEST (funzione backtest): si confrontano i segnali COT passati
con stagionalita' a favore e contraria (calcolata solo con gli anni PRECEDENTI a ogni segnale, niente
"sbirciate" nel futuro). Se l'accordo non migliora i risultati il peso e' 0: la stagionalita' resta informativa.
"""
import math
from bisect import bisect_left
from datetime import date, timedelta
from statistics import median, pstdev

from .config import NORMAL
from .cot import is_divergence, label
from . import conferme

ANNI_MIN = 10
FINESTRA = 28                 # giorni di calendario (4 settimane)
SPOSTA = 7                    # controllo di stabilita' nelle date
SOGLIA_ANNI = 15              # |% anni - 50| minimo (65% / 35%)
T_GIORNI = 2.58
T_MESI = 2.0                  # mesi: anni in rialzo + test t >= 2 (scarta i mesi "fortunati")
OSS_GIORNI = 500
ANNI_MAPPA = 20
PESO_MAX = 0.15               # al massimo +-15 punti su un punteggio di 100
MIN_BT = 30                   # segnali minimi per lato nel backtest
GIORNI_IT = ["Lunedi'", "Martedi'", "Mercoledi'", "Giovedi'", "Venerdi'"]


def _iso(d):
    return d.isoformat()


class Serie:
    """Prezzi ordinati per data, con ricerca veloce del primo giorno disponibile da una data in poi."""

    def __init__(self, pts):
        self.d = [p[0] for p in pts]
        self.v = [p[1] for p in pts]

    def da(self, giorno_iso, tolleranza=5):
        """Indice del primo prezzo dal giorno indicato (entro 'tolleranza' giorni), altrimenti None."""
        i = bisect_left(self.d, giorno_iso)
        if i >= len(self.d):
            return None
        if self.d[i] > _iso(date.fromisoformat(giorno_iso) + timedelta(days=tolleranza)):
            return None
        return i


def coppia(pb, pq):
    """Prezzo della coppia = base / quotata, solo nei giorni in cui ci sono entrambe."""
    q = dict(pq)
    return [(d, v / q[d]) for d, v in pb if q.get(d)]


def prezzo_coppia(prezzi, b, q):
    """Prezzi della coppia b/q. Il dollaro non ha una serie sua (1 dollaro = 1 dollaro):
    EURUSD = prezzo dell'euro in dollari, USDJPY = 1 / prezzo dello yen in dollari. None se manca un prezzo."""
    if q == "USD":
        return prezzi.get(b)
    if b == "USD":
        return [(d, 1 / v) for d, v in prezzi[q]] if q in prezzi else None
    if b in prezzi and q in prezzi:
        return coppia(prezzi[b], prezzi[q])
    return None


# --------------------------------------------------------------------------- 1) finestra delle prossime 4 settimane
def _rend(s, inizio_iso, giorni=FINESTRA):
    i = s.da(inizio_iso)
    if i is None:
        return None
    j = s.da(_iso(date.fromisoformat(s.d[i]) + timedelta(days=giorni)))
    return math.log(s.v[j] / s.v[i]) if j is not None and j > i else None


def _deriva(s, fino_anno=None):
    """Movimento medio dello strumento in 28 giorni (il "trend" da togliere), con i dati fino a fino_anno escluso."""
    j = len(s.d) - 1 if fino_anno is None else bisect_left(s.d, f"{fino_anno}-01-01") - 1
    if j <= 0:
        return 0.0
    giorni = (date.fromisoformat(s.d[j]) - date.fromisoformat(s.d[0])).days
    return math.log(s.v[j] / s.v[0]) / giorni * FINESTRA if giorni > 0 else 0.0


def _anni(s, mese, giorno, sposta=0, prima_di=None):
    """{anno: rendimento} della finestra che parte da mese/giorno (+sposta giorni) di ogni anno."""
    out = {}
    a0, a1 = int(s.d[0][:4]), int(s.d[-1][:4])
    for y in range(a0, a1 + 1):
        if prima_di is not None and y >= prima_di:
            break
        inizio = date(y, mese, min(giorno, 28)) + timedelta(days=sposta)
        r = _rend(s, _iso(inizio))
        if r is not None:
            out[y] = r
    return out


def _verso(x):
    return (x > 0) - (x < 0)


def finestra(s, giorno, prima_di=None, dettagli=True):
    """Statistiche della finestra di 4 settimane che parte da 'giorno' (date), con i filtri anti-coincidenza.
    prima_di = usa solo gli anni precedenti (backtest)."""
    anni = _anni(s, giorno.month, giorno.day, prima_di=prima_di)
    n = len(anni)
    if n < ANNI_MIN:
        return None
    der = _deriva(s, prima_di)
    rd = {y: r - der for y, r in anni.items()}            # senza trend
    vals = list(rd.values())
    hit = 100 * sum(x > 0 for x in vals) / n
    med = median(vals)
    sd = pstdev(list(anni.values())) or 1e-9
    ys = sorted(rd)
    meta1, meta2 = [rd[y] for y in ys[:n // 2]], [rd[y] for y in ys[n // 2:]]
    verso = _verso(med)
    ok_mezzi = _verso(median(meta1)) == verso == _verso(median(meta2))
    spost = [median([r - der for r in _anni(s, giorno.month, giorno.day, k, prima_di).values()] or [0]) for k in (-SPOSTA, SPOSTA)]
    ok_date = all(_verso(x) == verso for x in spost)
    ok_forza = abs(hit - 50) >= SOGLIA_ANNI and _verso(hit - 50) == verso
    # anche sui prezzi "veri" (con il trend) la maggioranza degli anni deve andare nello stesso verso,
    # altrimenti la card direbbe "ribasso" con la maggior parte degli anni in rialzo
    su = sum(r > 0 for r in anni.values())
    ok_grezzo = _verso(su - n / 2) == verso == _verso(median(anni.values()))
    robusto = bool(verso) and ok_mezzi and ok_date and ok_forza and ok_grezzo
    # punteggio -100..+100: quanto sono concordi gli anni, ridotto se il movimento e' piccolo rispetto al rumore
    forza = min(100.0, abs(hit - 50) * 2) * min(1.0, abs(med) / (0.25 * sd))
    out = {"score": round(verso * forza) if robusto else 0, "robusto": robusto, "n": n,
           "su": sum(r > 0 for r in anni.values()), "hit": round(hit), "med": round(median(anni.values()) * 100, 2),
           "med_d": round(med * 100, 2), "da": ys[0]}
    if not robusto:
        out["perche"] = ("anni divisi" if not (ok_forza and ok_grezzo) else "cambia nel tempo" if not ok_mezzi
                         else "dipende dalle date")
    if dettagli:                                           # percorso medio delle prossime 8 settimane (per il grafico)
        perc = []
        for k in range(0, 57, 7):
            rr = []
            for y in anni:
                i = s.da(_iso(date(y, giorno.month, min(giorno.day, 28))))
                j = s.da(_iso(date(y, giorno.month, min(giorno.day, 28)) + timedelta(days=k))) if i is not None else None
                if i is not None and j is not None:
                    rr.append(math.log(s.v[j] / s.v[i]))
            perc.append(round(median(rr) * 100, 2) if rr else None)
        out["percorso"] = perc
    return out


# --------------------------------------------------------------------------- 2) mesi
def mesi(s):
    """Per ogni mese: anni, % in rialzo, mediana, robustezza + mappa degli ultimi 20 anni."""
    fine = {}
    for d, v in zip(s.d, s.v):                            # ultimo prezzo di ogni mese
        fine[(int(d[:4]), int(d[5:7]))] = v
    rend = {}
    for (y, m), v in fine.items():
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        if (py, pm) in fine:
            rend[(y, m)] = math.log(v / fine[(py, pm)])
    if not rend:
        return None, None
    ultimo = max(fine)
    rend.pop(ultimo, None)                                # il mese in corso non e' ancora finito
    der = sum(rend.values()) / len(rend)
    out = []
    for m in range(1, 13):
        anni = {y: r for (y, mm), r in rend.items() if mm == m}
        n = len(anni)
        if n < ANNI_MIN:
            out.append({"n": n})
            continue
        ys = sorted(anni)
        rd = [anni[y] - der for y in ys]
        hit = 100 * sum(x > 0 for x in rd) / n
        med = median(rd)
        verso = _verso(med)
        t = (sum(rd) / n) / ((pstdev(rd) or 1e-9) / math.sqrt(n))   # test t: il movimento medio e' "vero"?
        su = sum(anni[y] > 0 for y in ys)
        ok_grezzo = _verso(su - n / 2) == verso == _verso(median(anni.values()))   # coerente anche con il trend
        ok = ok_grezzo and (abs(hit - 50) >= SOGLIA_ANNI and _verso(hit - 50) == verso and abs(t) >= T_MESI and _verso(t) == verso
              and _verso(median(rd[:n // 2])) == verso == _verso(median(rd[n // 2:])))
        out.append({"n": n, "su": su, "med": round(median(anni.values()) * 100, 2),
                    "med_d": round(med * 100, 2), "robusto": bool(verso) and ok})
    anni_m = sorted({y for y, _ in rend})[-ANNI_MAPPA:]
    mappa = {"anni": anni_m, "v": [[round(rend[(y, m)] * 100, 1) if (y, m) in rend else None for m in range(1, 13)]
                                   for y in anni_m]}
    return out, mappa


# --------------------------------------------------------------------------- 3) giorni della settimana
def giorni(s):
    """Lunedi'..venerdi': % giorni in rialzo, media, movimento tipico, ultimi 10 anni, robustezza (test t)."""
    per = {w: [] for w in range(5)}
    for i in range(1, len(s.d)):
        d0, d1 = date.fromisoformat(s.d[i - 1]), date.fromisoformat(s.d[i])
        w = d1.weekday()
        if w > 4 or (d1 - d0).days > 4:                    # salta weekend strani e buchi lunghi nei dati
            continue
        per[w].append((s.d[i], math.log(s.v[i] / s.v[i - 1]) * 100))
    tutti = [r for v in per.values() for _, r in v]
    if len(tutti) < OSS_GIORNI * 5:
        return None
    mu = sum(tutti) / len(tutti)
    dieci = _iso(date.fromisoformat(s.d[-1]) - timedelta(days=3653))
    out = []
    for w in range(5):
        rr = [r for _, r in per[w]]
        n = len(rr)
        media = sum(rr) / n
        sd = pstdev(rr) or 1e-9
        t = (media - mu) / (sd / math.sqrt(n))
        meta = n // 2
        m1 = sum(rr[:meta]) / meta - mu
        m2 = sum(rr[meta:]) / (n - meta) - mu
        rec = [r for d, r in per[w] if d >= dieci]
        out.append({"giorno": GIORNI_IT[w], "n": n, "su": round(100 * sum(r > 0 for r in rr) / n),
                    "media": round(media, 3), "vol": round(sum(abs(r) for r in rr) / n, 3), "t": round(t, 1),
                    "rec": round(sum(rec) / len(rec), 3) if rec else None,
                    "robusto": abs(t) >= T_GIORNI and _verso(m1) == _verso(m2) == _verso(t)})
    return out


# --------------------------------------------------------------------------- 3b) prossima settimana da oggi
def settimana(s, giorno, giorni=7):
    """STAGIONALITA' DELLA PROSSIMA SETTIMANA: per ogni anno dello storico, come si e' mosso lo strumento
    da questa stessa data del calendario ai 7 giorni successivi. Lettura semplice per il pannello del grafico.
    Restituisce {n anni, su (anni in rialzo), hit %, med (variazione mediana %), media %, dal (primo anno),
    robusto}: "robusto" solo se almeno 10 anni, almeno 70% (o al massimo 30%) nella stessa direzione e
    mediana e media dello stesso segno. Altrimenti e' rumore e lo diciamo."""
    anni = {}
    a0, a1 = int(s.d[0][:4]), int(s.d[-1][:4])
    for y in range(a0, a1 + 1):
        inizio = date(y, giorno.month, min(giorno.day, 28))
        if inizio >= giorno:                        # solo anni passati: niente futuro
            break
        r = _rend(s, _iso(inizio), giorni)
        if r is not None:
            anni[y] = (math.exp(r) - 1) * 100
    n = len(anni)
    if n < 5:
        return None
    v = list(anni.values())
    su = sum(x > 0 for x in v)
    hit = round(100 * su / n)
    med, media = median(v), sum(v) / n
    return {"n": n, "su": su, "hit": hit, "med": round(med, 2), "media": round(media, 2), "dal": min(anni),
            "robusto": n >= 10 and abs(hit - 50) >= 20 and _verso(med) == _verso(media) != 0}


# --------------------------------------------------------------------------- 4) tutto insieme per uno strumento
def analizza(pts, oggi=None):
    """Tutte le statistiche per una serie di prezzi [(data, prezzo)]. None se lo storico e' troppo corto."""
    if len(pts) < 250 * ANNI_MIN:
        return None
    s = Serie(pts)
    oggi = oggi or date.today()
    m, mappa = mesi(s)
    return {"finestra": finestra(s, oggi), "mesi": m, "mappa": mappa, "giorni": giorni(s),
            "sett": settimana(s, oggi), "da": s.d[0][:4], "al": s.d[-1]}


# --------------------------------------------------------------------------- 5) backtest: decide il peso
def backtest(hist, prezzi, pairs):
    """Segnali COT passati divisi in: stagionalita' a favore / contraria / neutra (calcolata con i soli anni
    precedenti al segnale). Restituisce le % di successo in 4 settimane e il PESO da usare."""
    storici = {k: conferme.punteggi_storici(s) for k, s in hist.items()}
    # dollaro composito, come nella dashboard (vedi conferme.affidabilita): 50% DXY + 50% inverso delle altre valute
    majors = [c for c in ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD") if c in storici]
    if majors:
        usd = {}
        for d in storici[majors[0]]:
            v = [storici[c][d] for c in majors if d in storici[c]]
            if len(v) == len(majors):
                inv = -sum(v) / len(v)
                usd[d] = 0.5 * storici["DXY"][d] + 0.5 * inv if d in storici.get("DXY", {}) else inv
        storici["USD"] = usd
    casi = []                                              # (prezzi, {data: punteggio del segnale})
    for k, st in storici.items():
        if k in prezzi and k != "USD":
            casi.append((prezzi[k], {d: sc for d, sc in st.items() if abs(sc) >= NORMAL}))
    for p in pairs:
        b, q = p.get("base"), p.get("quote")
        pts = prezzo_coppia(prezzi, b, q)
        if pts and b in storici and q in storici:
            sig = {}
            for d, sb in storici[b].items():
                if d in storici[q]:
                    sq = storici[q][d]
                    sc = (sb - sq) / 2
                    if label(sc, is_divergence(sb, sq)) != "NEUTRO":
                        sig[d] = sc
            casi.append((pts, sig))
    conta = {"accordo": [0, 0], "contrasto": [0, 0]}       # [segnali, successi]
    for pts, sig in casi:
        if len(pts) < 250 * ANNI_MIN:
            continue
        s = Serie(pts)
        for d, sc in sig.items():
            g0 = date.fromisoformat(d) + timedelta(days=3)    # venerdi' di pubblicazione
            st = finestra(s, g0, prima_di=g0.year, dettagli=False)
            if not st or not st["score"]:
                continue
            r = _rend(s, _iso(g0))
            if r is None:
                continue
            lato = "accordo" if _verso(st["score"]) == _verso(sc) else "contrasto"
            conta[lato][0] += 1
            conta[lato][1] += (r * _verso(sc)) > 0
    res = {k: {"n": n, "hit": round(100 * h / n) if n else None} for k, (n, h) in conta.items()}
    a, c = res["accordo"], res["contrasto"]
    peso = 0.0
    if a["n"] >= MIN_BT and c["n"] >= MIN_BT:
        peso = max(0.0, min(PESO_MAX, (a["hit"] - c["hit"]) / 100))
    res["peso"] = round(peso, 3)
    return res


def calcola(hist, prezzi, pairs, assets, oggi=None):
    """Calcola la stagionalita' di strumenti e coppie, il peso dal backtest e aggiunge a coppie/strumenti
    la sintesi "stag" (score, correzione, testo). Restituisce (dati per la scheda Stagionalita', meta)."""
    oggi = oggi or date.today()
    tab = {}
    for k in assets:
        if k in prezzi:
            r = analizza(prezzi[k], oggi)
            if r:
                tab[k] = r
    for p in pairs:
        pts = prezzo_coppia(prezzi, p["base"], p["quote"])
        if pts:
            r = analizza(pts, oggi)
            if r:
                tab[p["pair"]] = r
    meta = backtest(hist, prezzi, pairs)
    for chiave, obj in [(p["pair"], p) for p in pairs] + list(assets.items()):
        obj["stag1s"] = (tab.get(chiave) or {}).get("sett")       # prossima settimana da oggi (pannello grafico)
        f = (tab.get(chiave) or {}).get("finestra")
        if not f:
            continue
        adj = round(f["score"] * meta["peso"], 1)
        obj["stag"] = {k: f[k] for k in ("score", "robusto", "n", "su", "hit", "med", "med_d") if k in f}
        obj["stag"]["adj"] = adj
    return tab, meta
