# -*- coding: utf-8 -*-
"""
conferme.py - tre letture che dicono QUANTO fidarsi di un segnale COT (per lo swing).

1) COMMERCIALS (hedger: produttori, banche, utilizzatori).
   Stanno quasi sempre dalla parte opposta degli speculatori. Il loro COT Index (0..100 su 3 anni) agli
   estremi e' un classico segnale "smart money": molto long (>=80) di solito vicino ai minimi del prezzo,
   molto short (<=20) vicino ai massimi. Se va nella stessa direzione del segnale = CONFERMA, se no = CONTRASTO.

2) OPEN INTEREST (contratti aperti) nelle ultime 4 settimane, letto insieme al flusso dei Non Commercial:
     speculatori comprano + OI sale   -> nuovi long: trend sano
     speculatori comprano + OI scende -> chiusura di short (short covering): spinta piu' debole
     speculatori vendono  + OI sale   -> nuovi short: trend ribassista sano
     speculatori vendono  + OI scende -> liquidazione di long: spinta piu' debole

3) AFFIDABILITA' STORICA (backtest semplice).
   Per ogni settimana passata ricalcoliamo il punteggio COT con i SOLI dati di allora; se era BUY/SELL
   guardiamo il prezzo 4 settimane dopo (partendo dal venerdi' di pubblicazione). "Hit" = il prezzo si e'
   mosso nel verso del segnale. Serve un prezzo storico: c'e' per cambi, indici, petrolio, gas e cripto.
   ATTENZIONE: e' solo la parte COT (il modello di mercato di allora non lo ricostruiamo) e non include costi.

DEBUG: python -c "from cot_radar.demo import demo_data; ..." oppure guarda la sezione Strumenti.
"""
from datetime import date, timedelta

from .calcoli import cot_index
from .config import NORMAL, PRICES
from .cot import cot_strength, is_divergence, label

ORIZZONTE = 28          # giorni dopo la pubblicazione per misurare l'esito (4 settimane)
MIN_SEGNALI = 8         # sotto questo numero il risultato non e' statisticamente utile: lo segnaliamo


# --------------------------------------------------------------------------- 1) Commercials
def commercials(ser):
    """Posizione dei Commercials: netto in % OI, COT Index e lettura. None se il report non li contiene."""
    v = [(x["comm"] / x["oi"] * 100) for x in ser if x.get("comm") is not None and x["oi"]]
    if len(v) < 30:
        return None
    idx = round(cot_index(v))
    if idx >= 80:
        txt, verso = "molto long (spesso vicino ai minimi del prezzo)", 1
    elif idx <= 20:
        txt, verso = "molto short (spesso vicino ai massimi del prezzo)", -1
    else:
        txt, verso = "nella norma", 0
    return {"pct": round(v[-1], 1), "idx": idx, "txt": txt, "verso": verso}


def accordo(score, comm):
    """Il segnale (score) e i Commercials agli estremi vanno d'accordo?"""
    if not comm or comm["verso"] == 0 or abs(score) < NORMAL:
        return None
    return "conferma" if (score > 0) == (comm["verso"] > 0) else "contrasto"


# --------------------------------------------------------------------------- 2) Open interest
def open_interest(ser, settimane=4):
    """Variazione % dell'open interest in 4 settimane + lettura insieme al flusso dei Non Commercial."""
    if len(ser) <= settimane:
        return None
    oi0, oi1 = ser[-1 - settimane]["oi"], ser[-1]["oi"]
    d_oi = (oi1 / oi0 - 1) * 100 if oi0 else 0
    d_net = ser[-1]["net"] - ser[-1 - settimane]["net"]
    if abs(d_oi) < 2 or d_net == 0:                     # sotto il 2% l'OI e' praticamente fermo
        txt, forza = "open interest stabile: nessuna conferma", 0
    elif d_net > 0:
        txt, forza = ("nuovi long: trend sano", 1) if d_oi > 0 else ("chiusura di short: spinta piu' debole", 0)
    else:
        txt, forza = ("nuovi short: trend ribassista sano", -1) if d_oi > 0 else ("liquidazione di long: spinta piu' debole", 0)
    return {"d_oi": round(d_oi, 1), "txt": txt, "forza": forza}


# --------------------------------------------------------------------------- 3) Affidabilita' storica
def _prezzi(fred):
    """{chiave strumento: [(data, prezzo in dollari)]} dalle serie FRED (con il verso giusto)."""
    out = {}
    for k, (sid, verso) in PRICES.items():
        pts = [(d, (v if verso > 0 else (1 / v if v else None))) for d, v in (fred.get(sid) or [])]
        pts = [(d, v) for d, v in pts if v]
        if len(pts) > 100:
            out[k] = pts
    return out


def _al(pts, giorno):
    """Primo prezzo disponibile da 'giorno' in poi (i dati sono ordinati per data)."""
    lo, hi = 0, len(pts)
    while lo < hi:                                     # ricerca binaria: veloce anche con migliaia di giorni
        m = (lo + hi) // 2
        if pts[m][0] < giorno:
            lo = m + 1
        else:
            hi = m
    return pts[lo] if lo < len(pts) else None


def punteggi_storici(ser):
    """{data martedi': punteggio COT calcolato con i soli dati fino a quella settimana}."""
    out = {}
    for t in range(29, len(ser)):
        s = cot_strength(ser, t)
        if s:
            out[ser[t]["date"]] = s["cot"]
    return out


def esito(storico, pts, coppia=False, storico_q=None):
    """Statistiche del backtest. storico = {data: punteggio}; pts = prezzi (per una coppia: base/quotata).
    Per le coppie (coppia=True) il punteggio e' (base - quotata)/2 come nella dashboard."""
    n = hit = 0
    resa = []
    for d, sc in sorted(storico.items()):
        if coppia:
            if d not in storico_q:
                continue
            sb, sq = sc, storico_q[d]
            sc = (sb - sq) / 2
            if label(sc, is_divergence(sb, sq)) == "NEUTRO":
                continue
        elif abs(sc) < NORMAL:
            continue
        g0 = (date.fromisoformat(d) + timedelta(days=3)).isoformat()            # venerdi' di pubblicazione
        g1 = (date.fromisoformat(d) + timedelta(days=3 + ORIZZONTE)).isoformat()
        a, b = _al(pts, g0), _al(pts, g1)
        if not a or not b or b[0] > (date.fromisoformat(g1) + timedelta(days=7)).isoformat():
            continue                                    # manca il prezzo (o il futuro non c'e' ancora)
        r = (b[1] / a[1] - 1) * 100 * (1 if sc > 0 else -1)   # resa nel verso del segnale
        n += 1
        hit += r > 0
        resa.append(r)
    if not n:
        return None
    return {"n": n, "hit": round(100 * hit / n), "resa": round(sum(resa) / n, 2), "pochi": n < MIN_SEGNALI}


def affidabilita(series_per_chiave, fred, pairs):
    """Calcola l'affidabilita' storica per strumenti (con prezzo) e coppie.
    series_per_chiave = {chiave: serie COT}; pairs = lista delle coppie della dashboard.
    Restituisce ({chiave: esito}, {nome_coppia: esito})."""
    prezzi = _prezzi(fred)
    storici = {k: punteggi_storici(s) for k, s in series_per_chiave.items()}
    # dollaro composito, come nella dashboard: 50% DXY + 50% inverso della media delle altre valute
    majors = [c for c in ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD") if c in storici]
    if majors:
        usd = {}
        for d in storici[majors[0]]:
            v = [storici[c][d] for c in majors if d in storici[c]]
            if len(v) == len(majors):
                inv = -sum(v) / len(v)
                usd[d] = 0.5 * storici["DXY"][d] + 0.5 * inv if "DXY" in storici and d in storici["DXY"] else inv
        storici["USD"] = usd
        prezzi["USD"] = [(d, 1.0) for d in sorted({d for p in prezzi.values() for d, _ in p})]   # 1 dollaro = 1 dollaro
    per_asset = {k: esito(storici[k], prezzi[k]) for k in storici if k in prezzi and k != "USD"}
    per_coppia = {}
    for p in pairs:
        b, q = p.get("base"), p.get("quote")
        if b in prezzi and q in prezzi and b in storici and q in storici:
            pq = dict(prezzi[q])
            pts = [(d, v / pq[d]) for d, v in prezzi[b] if pq.get(d)]          # prezzo della coppia = base/quotata
            per_coppia[p["pair"]] = esito(storici[b], pts, coppia=True, storico_q=storici[q])
    return {k: v for k, v in per_asset.items() if v}, {k: v for k, v in per_coppia.items() if v}
