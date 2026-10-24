# -*- coding: utf-8 -*-
"""
motore.py - MOTORE UNICO DEI SEGNALI: le stesse regole per il registro live e per il backtest.

Tre parti, tutte "pure" (stesso input -> stesso output, nessun accesso a internet o file):

1) NASCITA E VITA DI UN SEGNALE (transizioni)
   - nasce quando l'etichetta passa da NEUTRO a BUY/SELL oppure si inverte (BUY -> SELL o viceversa);
   - la stessa direzione la settimana dopo NON e' un segnale nuovo: e' una "conferma";
   - il passaggio a STRONG (es. SELL -> STRONG SELL) apre un segnale "figlio" STRONG, legato al padre:
     cosi' si misura anche la fase STRONG senza contare due volte lo stesso movimento nelle statistiche generali;
   - finisce quando l'etichetta torna NEUTRO o si inverte (il figlio STRONG anche quando torna BUY/SELL).

2) MISURA (misura)
   Ingresso = PRIMA chiusura giornaliera DOPO l'orario di generazione (mai un prezzo gia' passato).
   Poi, nel verso del segnale: risultato a 1, 2 e 4 settimane e "fino al cambio di etichetta" (massimo 12
   settimane), con guadagno massimo (MFE) e drawdown massimo (MAE) lungo il percorso.
   Tre modi di entrare, misurati in parallelo:
     A = subito (alla prima chiusura);
     B = ritracciamento: ordine limite a 0,5 volte il movimento settimanale tipico, valido 5 giorni,
         altrimenti "non eseguito";
     C = meta' e meta' (meta' subito, meta' con l'ordine limite).
   ATTENZIONE: i prezzi gratuiti (FRED) sono solo CHIUSURE giornaliere, niente massimi/minimi:
   MFE e MAE sono misurati sulle chiusure (il vero estremo intraday puo' essere un po' piu' ampio).

3) STATISTICHE (statistiche)
   Per gruppo: numero di segnali, percentuale vinti con intervallo di incertezza (Wilson 95%),
   resa media, MFE medio, MAE medio e rapporto MFE/MAE. MFE e MAE NON vengono mediati tra loro.

DEBUG: python -m unittest tests.test_motore -v
"""
import math
from datetime import date, datetime, timedelta, timezone

ORIZZONTI = (("1s", 7), ("2s", 14), ("4s", 28))   # settimane fisse, in giorni di calendario
CAP_GIORNI = 84                                   # "fino al cambio": al massimo 12 settimane
LIMITE_VOLTE = 0.5                                # entrata B: 0,5 x movimento settimanale tipico
LIMITE_GIORNI = 5                                 # entrata B: l'ordine limite resta valido 5 chiusure
BUCHI_MAX = 7                                     # un orizzonte senza prezzo per piu' di 7 giorni = n/d
GIORNI_MAX = 20                                   # percorso giorno per giorno: fino a 20 sedute (4 settimane)

# --------------------------------------------------------------------------- orari di chiusura dei prezzi
# Ogni serie FRED ha UN prezzo al giorno, ma a orari diversi. Serve per decidere qual e' la prima chiusura
# DOPO la generazione del segnale. (fuso, ora, minuti)
ORARI = {
    "fx": ("NY", 12, 0),        # cambi FRED H.10: tassi di mezzogiorno di New York (18:00 in Italia)
    "indici": ("NY", 16, 0),    # S&P 500, Nasdaq, Dow: chiusura di Wall Street
    "energia": ("NY", 14, 30),  # petrolio e gas (EIA): chiusura del NYMEX
    "crypto": ("UTC", 23, 59),  # Coinbase: fine giornata UTC
}
CLASSE_PREZZO = {"SP500": "indici", "NASDAQ": "indici", "DOW": "indici",
                 "WTI": "energia", "BRENT": "energia", "NATGAS": "energia", "BTC": "crypto", "ETH": "crypto"}

# costi stimati andata+ritorno in % (spread + commissioni, senza swap/rollover): usati solo nelle STATISTICHE
COSTI = {"major": 0.02, "cross": 0.04, "em": 0.15, "indici": 0.05, "energia": 0.08, "NATGAS": 0.20, "crypto": 0.20}
MAJOR = {"EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
EM = {"MXN", "BRL", "ZAR"}


def classe(strumento, base=None, quote=None):
    """Classe di prezzo: 'fx' per le coppie, altrimenti indici/energia/crypto."""
    return "fx" if base else CLASSE_PREZZO.get(strumento, "indici")


def costo(strumento, base=None, quote=None):
    """Costo stimato andata+ritorno in % per lo strumento."""
    if base:
        if base in EM or quote in EM:
            return COSTI["em"]
        return COSTI["major"] if "USD" in (base, quote) else COSTI["cross"]
    if strumento == "NATGAS":
        return COSTI["NATGAS"]
    return COSTI.get(CLASSE_PREZZO.get(strumento, "indici"), 0.05)


def _domenica(anno, mese, n):
    """n-esima domenica del mese (n=-1: ultima)."""
    if n > 0:
        d = date(anno, mese, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    d = date(anno, mese + 1, 1) - timedelta(days=1) if mese < 12 else date(anno, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def scarto_ny(g):
    """Ore di differenza New York - UTC in quel giorno (-4 ora legale, -5 ora solare). Regole USA dal 2007;
    prima del 2007 (prima domenica di aprile - ultima di ottobre) bastano per il backtest."""
    if g.year >= 2007:
        ini, fin = _domenica(g.year, 3, 2), _domenica(g.year, 11, 1)
    else:
        ini, fin = _domenica(g.year, 4, 1), _domenica(g.year, 10, -1)
    return -4 if ini <= g < fin else -5


def scarto_roma(t):
    """Ore di differenza Italia - UTC nell'istante t (UTC): +2 ora legale (ultima domenica di marzo - ultima di
    ottobre, cambio all'01:00 UTC), +1 ora solare. Scritto a mano: niente dipendenze (tzdata) su Windows."""
    ini = datetime.combine(_domenica(t.year, 3, -1), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    fin = datetime.combine(_domenica(t.year, 10, -1), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return 2 if ini <= t < fin else 1


def chiusura_utc(giorno_iso, cls):
    """Istante UTC della chiusura del giorno 'giorno_iso' per quella classe di prezzo."""
    g = date.fromisoformat(giorno_iso)
    fuso, h, m = ORARI[cls]
    t = datetime(g.year, g.month, g.day, h, m, tzinfo=timezone.utc)
    return t - timedelta(hours=scarto_ny(g)) if fuso == "NY" else t


def utc_iso(t):
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def da_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def ora_italia(s):
    """'2026-10-23T19:47Z' -> '23/10/2026 ore 21:47' (ora italiana)."""
    t = da_iso(s)
    t = t + timedelta(hours=scarto_roma(t))
    return t.strftime("%d/%m/%Y ore %H:%M")


def pubblicazione_cot(martedi_iso):
    """Il report del martedi' esce il venerdi' alle 15:30 di New York: istante UTC (per il backtest)."""
    v = date.fromisoformat(martedi_iso) + timedelta(days=3)
    return datetime(v.year, v.month, v.day, 15, 30, tzinfo=timezone.utc) - timedelta(hours=scarto_ny(v))


# --------------------------------------------------------------------------- 1) nascita e vita dei segnali
def verso(etichetta):
    """+1 acquisto, -1 vendita, 0 neutro."""
    return 1 if "BUY" in etichetta else -1 if "SELL" in etichetta else 0


def affidabilita(storico, comm_acc, stag, score):
    """Stessa regola del badge AFFIDABILITA' del sito (app.js, affidabilitaSegnale):
    storico >= 60% +1 / < 50% -1; Commercials a favore +1 / contrari -1; stagionalita' robusta a favore +1 /
    contraria -1. Totale >= 2 ALTA, <= -1 BASSA, altrimenti MEDIA. Restituisce (livello, motivi)."""
    v, perche = 0, []
    if storico and not storico.get("pochi"):
        if storico["hit"] >= 60:
            v += 1
            perche.append(f"storico {storico['hit']}%")
        elif storico["hit"] < 50:
            v -= 1
            perche.append(f"storico solo {storico['hit']}%")
    if comm_acc == "conferma":
        v += 1
        perche.append("Commercials a favore")
    elif comm_acc == "contrasto":
        v -= 1
        perche.append("Commercials contrari")
    if stag and stag.get("robusto"):
        if (stag["score"] > 0) == (score > 0):
            v += 1
            perche.append("stagionalita' a favore")
        else:
            v -= 1
            perche.append("stagionalita' contraria")
    return ("ALTA" if v >= 2 else "BASSA" if v <= -1 else "MEDIA"), perche


def transizioni(aperti, correnti, quando, cot_data, iniziale=False):
    """Confronta i segnali aperti con le etichette di adesso e restituisce gli EVENTI nuovi.
    aperti   = {strumento: stato} (modificato sul posto); lo stato si ricostruisce dagli eventi con applica()
    correnti = {strumento: {"etichetta", "punteggio", "affid", "perche", ...}} (strumenti senza dati: assenti,
               e restano come sono)
    quando   = istante UTC in formato "AAAA-MM-GGTHH:MMZ"; cot_data = martedi' del report COT in uso.
    iniziale = True solo al primo avvio del registro: i segnali gia' attivi vengono marcati "iniziale"
               (non sono nati adesso, quindi restano fuori dalle statistiche)."""
    eventi = []
    stamp = quando[:10].replace("-", "") + "-" + quando[11:16].replace(":", "")
    for s in sorted(correnti):
        c = correnti[s]
        lab = c["etichetta"]
        v, forte = verso(lab), lab.startswith("STRONG")
        a = aperti.get(s)
        if a and a["verso"] != v:                                   # torna NEUTRO o si inverte: fine
            motivo = "neutro" if v == 0 else "inversione"
            if a.get("figlio"):
                eventi.append({"tipo": "chiusura", "id": a["figlio"], "quando": quando, "motivo": motivo,
                               "nuova": lab, "punteggio": c["punteggio"]})
            eventi.append({"tipo": "chiusura", "id": a["id"], "quando": quando, "motivo": motivo,
                           "nuova": lab, "punteggio": c["punteggio"]})
            del aperti[s]
            a = None
        if a:                                                       # stessa direzione
            if forte and not a["forte"]:                            # sale a STRONG: segnale figlio
                fid = f"{s}-{stamp}-F"
                eventi.append(_apertura(fid, s, c, quando, cot_data, padre=a["id"]))
                a.update(forte=True, figlio=fid)
            elif not forte and a["forte"]:                          # scende da STRONG a BUY/SELL
                if a.get("figlio"):
                    eventi.append({"tipo": "chiusura", "id": a["figlio"], "quando": quando, "motivo": "indebolito",
                                   "nuova": lab, "punteggio": c["punteggio"]})
                a.update(forte=False, figlio=None)
            if cot_data and cot_data != a["cot_data"]:              # nuova settimana COT nella stessa direzione
                eventi.append({"tipo": "conferma", "id": a["id"], "quando": quando, "cot_data": cot_data,
                               "etichetta": lab, "punteggio": c["punteggio"]})
                a["cot_data"] = cot_data
        elif v != 0:                                                # nasce un segnale
            sid = f"{s}-{stamp}"
            eventi.append(_apertura(sid, s, c, quando, cot_data, iniziale=iniziale))
            aperti[s] = {"id": sid, "verso": v, "forte": forte, "figlio": None, "cot_data": cot_data}
    return eventi


def _apertura(sid, s, c, quando, cot_data, padre=None, iniziale=False):
    e = {"tipo": "apertura", "id": sid, "strumento": s, "etichetta": c["etichetta"], "verso": verso(c["etichetta"]),
         "punteggio": c["punteggio"], "affid": c.get("affid"), "perche": c.get("perche") or [],
         "generato": quando, "cot_data": cot_data}
    for k in ("base", "quote"):
        if c.get(k):
            e[k] = c[k]
    if padre:
        e["padre"] = padre
    if iniziale:
        e["iniziale"] = True
    return e


def applica(eventi):
    """Dagli eventi (in ordine) ricostruisce: segnali {id: segnale} e aperti {strumento: stato}."""
    segnali, aperti = {}, {}
    for e in eventi:
        t = e["tipo"]
        if t == "apertura":
            segnali[e["id"]] = dict(e, conferme=0, chiuso=None)
            if e.get("padre"):
                if e["strumento"] in aperti:
                    aperti[e["strumento"]].update(forte=True, figlio=e["id"])
            else:
                aperti[e["strumento"]] = {"id": e["id"], "verso": e["verso"], "forte": e["etichetta"].startswith("STRONG"),
                                          "figlio": None, "cot_data": e.get("cot_data")}
        elif e["id"] in segnali:
            sg = segnali[e["id"]]
            if t == "conferma":
                sg["conferme"] += 1
                if sg["strumento"] in aperti:
                    aperti[sg["strumento"]]["cot_data"] = e.get("cot_data")
            elif t == "chiusura":
                sg["chiuso"] = {"quando": e["quando"], "motivo": e["motivo"], "nuova": e.get("nuova")}
                a = aperti.get(sg["strumento"])
                if a and a["id"] == e["id"]:
                    del aperti[sg["strumento"]]
                elif a and a.get("figlio") == e["id"]:
                    a.update(forte=False, figlio=None)
    return segnali, aperti


# --------------------------------------------------------------------------- 2) misura
def _primo_dopo(pts, istante, cls, da=0):
    """Indice della prima chiusura avvenuta DOPO 'istante' (UTC)."""
    for i in range(da, len(pts)):
        if chiusura_utc(pts[i][0], cls) > istante:
            return i
    return None


def _primo_dal(pts, giorno, da=0):
    """Indice del primo prezzo con data >= giorno (ricerca binaria)."""
    lo, hi = da, len(pts)
    while lo < hi:
        m = (lo + hi) // 2
        if pts[m][0] < giorno:
            lo = m + 1
        else:
            hi = m
    return lo if lo < len(pts) else None


def _tratto(pts, i0, i1, prezzo0, v):
    """Risultato, MFE e MAE in % nel verso v, dall'ingresso (indice i0, prezzo0) fino all'indice i1 incluso."""
    r = [v * (pts[i][1] / prezzo0 - 1) * 100 for i in range(i0 + 1, i1 + 1)]
    fine = r[-1] if r else 0.0
    return {"res": round(fine, 3), "mfe": round(max([0.0] + r), 3), "mae": round(min([0.0] + r), 3),
            "data": pts[i1][0], "prezzo": pts[i1][1], "vinto": fine > 0}


def tipico_settimanale(pts, i):
    """Movimento settimanale tipico (mediana di |variazione a 5 chiusure|, log) nell'anno prima dell'indice i."""
    r = sorted(abs(math.log(pts[k][1] / pts[k - 5][1])) for k in range(max(5, i - 250), i + 1)
               if pts[k][1] > 0 and pts[k - 5][1] > 0)
    return r[len(r) // 2] if len(r) >= 20 else None


def misura(segnale, pts, cls, oggi=None):
    """Misura un segnale sui prezzi pts = [(data, prezzo)] (gia' nel verso della coppia/strumento).
    Restituisce un dizionario con ingresso, varianti A/B/C e orizzonti; None se i prezzi mancano del tutto."""
    if not pts:
        return None
    v = segnale["verso"]
    gen = da_iso(segnale["generato"])
    ie = _primo_dopo(pts, gen, cls, da=_primo_dal(pts, (gen - timedelta(days=3)).date().isoformat()) or 0)
    if ie is None:
        return {"stato": "in attesa del primo prezzo"}
    pe, de = pts[ie][1], pts[ie][0]
    d_e = date.fromisoformat(de)
    out = {"stato": "ok", "ingresso": {"data": de, "prezzo": pe, "utc": utc_iso(chiusura_utc(de, cls))}, "A": {}, "B": {}, "C": {}}

    # indici di uscita: orizzonti fissi + "fino al cambio" (massimo 12 settimane)
    uscite = {}
    for nome, g in ORIZZONTI:
        j = _primo_dal(pts, (d_e + timedelta(days=g)).isoformat(), ie)
        if j is not None and pts[j][0] <= (d_e + timedelta(days=g + BUCHI_MAX)).isoformat():
            uscite[nome] = (j, False)
    cap = (d_e + timedelta(days=CAP_GIORNI)).isoformat()
    ch = segnale.get("chiuso")
    jx, in_corso, motivo = None, False, None
    if ch:
        jx = _primo_dopo(pts, da_iso(ch["quando"]), cls, da=ie)
        motivo = ch["motivo"]
        if jx is None:                                   # chiuso, ma la chiusura d'uscita non c'e' ancora
            jx, in_corso = len(pts) - 1, True
    else:
        jx, in_corso = len(pts) - 1, True                # ancora aperto: misura fino a oggi (provvisoria)
    jcap = _primo_dal(pts, cap, ie)
    if jcap is not None and pts[jcap][0] > cap:
        jcap -= 1
    if (jcap is not None and jx > jcap) or (jcap is None and pts[jx][0] > cap):
        jx, in_corso, motivo = (jcap if jcap is not None else jx), False, "12 settimane"
    if jx > ie or not in_corso:
        uscite["fine"] = (max(jx, ie), in_corso)
    out["fine"] = {"motivo": motivo, "in_corso": in_corso}

    # PERCORSO GIORNO PER GIORNO (uscita a tempo fisso, scelta da chi guarda: 1..20 sedute dopo l'ingresso).
    # Per ogni seduta k: [risultato a k, guadagno massimo fino a k, drawdown massimo fino a k] in %, nel verso
    # del segnale. Non dipende dal cambio di etichetta: risponde a "se chiudo dopo k giorni, cosa succede?".
    g, gd, mx, mn = [], [], 0.0, 0.0
    for k in range(1, GIORNI_MAX + 1):
        if ie + k >= len(pts):
            break
        r = v * (pts[ie + k][1] / pe - 1) * 100
        mx, mn = max(mx, r), min(mn, r)
        g.append([round(r, 3), round(mx, 3), round(mn, 3)])
        gd.append(pts[ie + k][0])
    out["G"], out["Gd"], out["cls"] = g, gd, cls

    # A: ingresso immediato
    for nome, (j, prov) in uscite.items():
        t = _tratto(pts, ie, j, pe, v)
        t["provvisorio"] = prov
        out["A"][nome] = t

    # B: ordine limite di ritracciamento, valido 5 chiusure
    tip = tipico_settimanale(pts, ie)
    # movimento settimanale tipico all'ingresso, in %: l'unita' di misura del drawdown "in volatilita'"
    # (calcolato con i soli prezzi fino all'ingresso: niente dati dal futuro)
    out["tip"] = round((math.exp(tip) - 1) * 100, 4) if tip else None
    if tip is None:
        out["B"] = {"esito": "n/d"}
    else:
        lim = pe * math.exp(-v * LIMITE_VOLTE * tip)
        fi = None
        for k in range(ie + 1, min(len(pts), ie + 1 + LIMITE_GIORNI)):
            if (v > 0 and pts[k][1] <= lim) or (v < 0 and pts[k][1] >= lim):
                fi = k
                break
        if fi is None:
            scaduto = len(pts) - 1 >= ie + LIMITE_GIORNI
            out["B"] = {"esito": "non eseguito" if scaduto else "in attesa", "limite": lim}
        else:
            out["B"] = {"esito": "eseguito", "limite": lim, "data": pts[fi][0]}
            for nome, (j, prov) in uscite.items():
                if j >= fi:
                    t = _tratto(pts, fi, j, lim, v)
                    t["provvisorio"] = prov
                    out["B"][nome] = t

    # C: meta' subito e meta' con il limite (se il limite non scatta, meta' capitale resta ferma = 0)
    for nome in uscite:
        a = out["A"][nome]["res"]
        b = out["B"].get(nome, {}).get("res") if out["B"].get("esito") == "eseguito" else None
        if out["B"].get("esito") in ("eseguito", "non eseguito"):
            out["C"][nome] = {"res": round(0.5 * a + 0.5 * (b or 0.0), 3)}
    return out


# --------------------------------------------------------------------------- 3) statistiche
def wilson(k, n, z=1.96):
    """Intervallo di confidenza al 95% della percentuale di vinti (metodo di Wilson): (minimo, massimo) in %."""
    if not n:
        return None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(100 * max(0.0, c - m)), round(100 * min(1.0, c + m))


def statistiche(misurati, orizzonti=("1s", "2s", "4s", "fine")):
    """misurati = [(segnale, misura, costo%)]. Solo tratti chiusi (non provvisori), al netto dei costi stimati.
    Per ogni orizzonte: A (n, vinti, intervallo, resa, mfe, mae, rapporto), B (eseguiti, valore per segnale),
    C (valore per segnale)."""
    out = {}
    for h in orizzonti:
        a, b_tot, b_ok, c = [], 0, [], []
        for s, m, cst in misurati:
            if not m or m.get("stato") != "ok":
                continue
            t = m["A"].get(h)
            if not t or t.get("provvisorio"):
                continue
            a.append((t["res"] - cst, t["mfe"], t["mae"]))
            eb = m["B"].get("esito")
            if eb in ("eseguito", "non eseguito"):
                b_tot += 1
                tb = m["B"].get(h)
                if eb == "eseguito" and tb and not tb.get("provvisorio"):
                    b_ok.append(tb["res"] - cst)
                tc = m["C"].get(h)
                if tc:
                    c.append(tc["res"] - (cst if eb == "eseguito" else cst / 2))
        n = len(a)
        if not n:
            continue
        vinti = sum(1 for x in a if x[0] > 0)
        mfe, mae = sum(x[1] for x in a) / n, sum(x[2] for x in a) / n
        out[h] = {
            "n": n, "vinti": vinti, "hit": round(100 * vinti / n), "ic": wilson(vinti, n),
            "resa": round(sum(x[0] for x in a) / n, 3), "mfe": round(mfe, 3), "mae": round(mae, 3),
            "rapporto": round(mfe / abs(mae), 2) if mae < 0 else None,
            "B": {"n": b_tot, "eseguiti": len(b_ok), "fill": round(100 * len(b_ok) / b_tot) if b_tot else None,
                  "resa_eseguiti": round(sum(b_ok) / len(b_ok), 3) if b_ok else None,
                  "valore": round(sum(b_ok) / b_tot, 3) if b_tot else None},
            "C": {"n": len(c), "valore": round(sum(c) / len(c), 3) if c else None},
        }
    return out


def giorni_stat(misurati):
    """Percorso medio giorno per giorno: per ogni seduta k (1..20) la lista compatta
    [segnali, vinti, somma risultati, somma guadagni massimi, somma drawdown massimi], al netto dei costi.
    Compatta di proposito: medie, percentuali e intervallo di Wilson le calcola la pagina (app.js)."""
    acc = [[0, 0, 0.0, 0.0, 0.0] for _ in range(GIORNI_MAX)]
    for s, m, cst in misurati:
        if not m or m.get("stato") != "ok":
            continue
        for k, (r, mx, mn) in enumerate(m.get("G") or []):
            a = acc[k]
            a[0] += 1
            a[1] += 1 if r - cst > 0 else 0
            a[2] += r - cst
            a[3] += mx
            a[4] += mn
    return [[a[0], a[1], round(a[2], 2), round(a[3], 2), round(a[4], 2)] for a in acc if a[0]]


def riassunto(misurati, varianti=False):
    """Tutto cio' che serve alla pagina per un gruppo di segnali:
    g = percorso giorno per giorno (uscita dopo 1..20 sedute), fine = statistiche "fino al cambio di etichetta",
    var = confronto dei tre ingressi A/B/C a 1, 2 e 4 settimane (solo per i gruppi principali)."""
    st = statistiche(misurati, ("1s", "2s", "4s", "fine") if varianti else ("fine",))
    out = {"g": giorni_stat(misurati), "fine": st.get("fine")}
    if varianti:
        out["var"] = {h: {"resa": x["resa"], "n": x["n"], "B": x["B"], "C": x["C"]} for h, x in st.items() if h != "fine"}
    return out


def snello(m):
    """Misura senza il percorso giornaliero (per le schede della pagina: piu' leggera)."""
    return {k: v for k, v in m.items() if k not in ("G", "Gd", "E", "_dd")} if m else m


def profilo(pts, giorni=250):
    """NATURA DEL MERCATO di uno strumento nell'ultimo anno (circa 250 sedute), per leggere i drawdown nel contesto:
      ann  = volatilita' annua in % (deviazione standard dei rendimenti giornalieri x radice di 252);
      sett = movimento settimanale tipico in % (mediana delle variazioni a 5 sedute, in valore assoluto).
    Un drawdown medio del 2% e' tanto su EURUSD (si muove ~1% a settimana) e poco sul gas (~8%)."""
    p = [v for _, v in pts[-(giorni + 6):] if v and v > 0]
    if len(p) < 60:
        return None
    r = [math.log(p[i] / p[i - 1]) for i in range(1, len(p))]
    m = sum(r) / len(r)
    ann = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252) * 100
    w = sorted(abs(p[i] / p[i - 5] - 1) * 100 for i in range(5, len(p)))
    return {"ann": round(ann, 1), "sett": round(w[len(w) // 2], 2)}


# --------------------------------------------------------------------------- DRAWDOWN (studio del rischio)
# Obiettivo: capire QUANTO un segnale va contro prima di andare (o non andare) dove deve, rispetto a quanto si
# muove di solito quel mercato e a quanto guadagna. Per ogni durata del trade (1..20 sedute e "al cambio segnale")
# si calcola una riga compatta con i campi di DD_CAMPI (la pagina la legge per nome, vedi app.js "DD"):
#   n            segnali misurati
#   mae50/mae90  drawdown massimo tipico (mediana) e "brutto" (1 trade su 10 va peggio), in % (negativi)
#   mfe50/res50  guadagno massimo tipico e risultato tipico (mediane), in %
#   v50/v90      drawdown in VOLATILITA': drawdown / movimento settimanale tipico di quel mercato all'ingresso
#   fv50/rv50    guadagno massimo e risultato tipici nella stessa unita' (per il grafico "in volatilita'")
#   h1..h4       % di trade con drawdown <0,5 / 0,5-1 / 1-2 / oltre 2 settimane tipiche
#   gmin         seduta tipica in cui si tocca il punto peggiore (solo trade andati in negativo)
#   prima        % di trade in cui il guadagno massimo arriva PRIMA del drawdown massimo
#   hit/resa     % vinti e resa media al netto dei costi (in piccolo nella pagina: il quadro resta completo)
#   p50/p90      drawdown tipico e brutto in PUNTI (pip, punti indice, $): solo per un singolo strumento
#   ev_*/no_*    drawdown (n, tipico) dei trade con almeno un annuncio macro USA nella finestra / senza
#   pg/pa        % di trade il cui giorno peggiore cade su un annuncio, e % attesa per puro caso
# Per "al cambio segnale" non c'e' il percorso giornaliero: tempi ed eventi restano vuoti (None).
DD_CAMPI = ["n", "mae50", "mae90", "mfe50", "res50", "v50", "v90", "fv50", "rv50", "h1", "h2", "h3", "h4",
            "gmin", "prima", "hit", "resa", "p50", "p90", "ev_n", "ev50", "no_n", "no50", "pg", "pa"]
SOGLIE_VOL = (0.5, 1.0, 2.0)          # confini delle fasce di drawdown in "settimane tipiche"


def quantile(v, q):
    """Quantile con interpolazione lineare (v gia' ordinata). q=0,5 = mediana."""
    if not v:
        return None
    x = (len(v) - 1) * q
    i = int(x)
    return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (x - i)


def unita(strumento, base=None, quote=None):
    """Unita' dei PUNTI di uno strumento: (nome, dimensione di un punto nel prezzo).
    Cambi: pip = 0,0001 (0,01 se la quotata e' lo yen); indici: punti; petrolio, gas e crypto: dollari."""
    if base:
        return ("pip", 0.01 if quote == "JPY" else 0.0001)
    cls = CLASSE_PREZZO.get(strumento, "indici")
    return ("punti", 1.0) if cls == "indici" else ("$", 1.0)


def prepara_eventi(misurati, cal):
    """Per ogni trade, quali sedute del percorso contengono un annuncio macro (m["E"]). Una volta sola."""
    if not cal:
        return
    for s, m, c in misurati:
        if m and m.get("stato") == "ok" and "E" not in m and m.get("Gd"):
            m["E"] = cal.giorni(m["ingresso"]["data"], m["Gd"], m.get("cls") or "fx")


def _riga_dd(righe, u):
    """righe = [(mae, mfe, res netto, tip, prezzo, gmin, prima, ev, peggiore_su_evento, quota_eventi)]."""
    n = len(righe)
    if not n:
        return None
    q = lambda v, p: round(quantile(sorted(v), p), 2) if v else None
    pc = lambda k: round(100 * k / n)
    mae = [r[0] for r in righe]
    vol = [(abs(r[0]) / r[3], r[1] / r[3], r[2] / r[3]) for r in righe if r[3]]
    nv = len(vol)
    fasce = [0, 0, 0, 0]
    for a, _, _ in vol:
        fasce[sum(1 for t in SOGLIE_VOL if a >= t)] += 1
    gmin = [r[5] for r in righe if r[5]]
    con_t = [r for r in righe if r[6] is not None]
    pts = [abs(r[0]) / 100 * r[4] / u[1] for r in righe if u and r[4]] if u else []
    ev = [r[0] for r in righe if r[7] is True]
    no = [r[0] for r in righe if r[7] is False]
    pg = [r for r in righe if r[8] is not None]
    riga = {
        "n": n, "mae50": q(mae, .5), "mae90": q(mae, .1), "mfe50": q([r[1] for r in righe], .5),
        "res50": q([r[2] for r in righe], .5),
        "v50": q([x[0] for x in vol], .5), "v90": q([x[0] for x in vol], .9),
        "fv50": q([x[1] for x in vol], .5), "rv50": q([x[2] for x in vol], .5),
        "h1": round(100 * fasce[0] / nv) if nv else None, "h2": round(100 * fasce[1] / nv) if nv else None,
        "h3": round(100 * fasce[2] / nv) if nv else None, "h4": round(100 * fasce[3] / nv) if nv else None,
        "gmin": q(gmin, .5), "prima": round(100 * sum(1 for r in con_t if r[6]) / len(con_t)) if con_t else None,
        "hit": pc(sum(1 for r in righe if r[2] > 0)), "resa": round(sum(r[2] for r in righe) / n, 3),
        "p50": q(pts, .5), "p90": q(pts, .9),
        "ev_n": len(ev), "ev50": q(ev, .5), "no_n": len(no), "no50": q(no, .5),
        "pg": round(100 * sum(1 for r in pg if r[8]) / len(pg)) if pg else None,
        "pa": round(100 * sum(r[9] for r in pg) / len(pg)) if pg else None,
    }
    return [riga[k] for k in DD_CAMPI]


def _righe_trade(m, cst):
    """Le righe di UN trade per ogni durata (1..20 sedute) e per "al cambio segnale". Calcolate una volta sola e
    tenute in m["_dd"]: lo stesso trade entra in piu' gruppi (tutti, strumento, periodo) senza ricalcoli."""
    if "_dd" in m:
        return m["_dd"]
    tip, prezzo, G, E = m.get("tip"), m["ingresso"]["prezzo"], m.get("G") or [], m.get("E")
    delta = [G[0][0]] + [G[j][0] - G[j - 1][0] for j in range(1, len(G))] if G else []
    righe, jmin, jmax = [], None, None
    for k in range(1, len(G) + 1):
        res, mfe, mae = G[k - 1]
        # seduta in cui si tocca per la prima volta il punto peggiore / migliore (si aggiornano solo se migliorano)
        if mae < 0 and (k == 1 or mae < G[k - 2][2]):
            jmin = k
        if mfe > 0 and (k == 1 or mfe > G[k - 2][1]):
            jmax = k
        prima = None if (mae == 0 and mfe == 0) else (True if mae == 0 else False if mfe == 0 else jmax < jmin)
        ev = pegg = quota = None
        if E is not None and len(E) >= k:
            ev = any(E[:k])
            dmin = min(delta[:k])
            if dmin < 0:
                pegg, quota = E[delta[:k].index(dmin)], sum(E[:k]) / k
        righe.append((mae, mfe, res - cst, tip, prezzo, jmin if mae < 0 else None, prima, ev, pegg, quota))
    f = (m.get("A") or {}).get("fine")
    fine = (f["mae"], f["mfe"], f["res"] - cst, tip, prezzo, None, None, None, None, None) \
        if f and not f.get("provvisorio") else None
    m["_dd"] = (righe, fine)
    return m["_dd"]


def drawdown(misurati, u=None):
    """Studio del drawdown per ogni durata: lista di 21 righe compatte (sedute 1..20, poi "al cambio segnale").
    misurati = [(segnale, misura, costo%)]; u = unita' dei punti (solo per un singolo strumento)."""
    per_k, fine = [[] for _ in range(GIORNI_MAX)], []
    for s, m, cst in misurati:
        if not m or m.get("stato") != "ok":
            continue
        righe, f = _righe_trade(m, cst)
        for k, r in enumerate(righe):
            per_k[k].append(r)
        if f:
            fine.append(f)
    return [_riga_dd(r, u) for r in per_k] + [_riga_dd(fine, u)]
