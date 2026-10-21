# -*- coding: utf-8 -*-
"""
analisi.py - mette insieme COT + Mercato e costruisce strumenti, coppie e correlazioni.

Flusso:
  righe CFTC -> serie per mercato -> punteggio COT
                                   + punteggio Mercato (se lo strumento ha un prezzo)
                                   = punteggio FINALE -> etichetta (BUY/SELL/...)
  finali delle valute -> coppie (EURUSD, ...) -> etichette con regola della divergenza
  flussi settimanali  -> matrice delle correlazioni
"""
from .calcoli import clip, pearson
from .config import ASSETS, EXTRA_PAIRS, FX_ORDER, MACRO_WEIGHT, PAIR_NAMES
from .cot import cot_series, cot_strength, is_divergence, label
from .log import log
from .mercato import market_model


def analyse(cot_rows, fred, ecb):
    """Restituisce (assets, pairs, corr, market)."""
    series = cot_series(cot_rows)
    by_code = {a[1]: a for a in ASSETS}

    # ---- 1. punteggio COT di ogni strumento (oggi e settimana scorsa)
    assets, hist = {}, {}
    for code, ser in series.items():
        if code not in by_code or len(ser) < 30:
            continue
        k, _, name, group = by_code[code]
        now, prev = cot_strength(ser, len(ser) - 1), cot_strength(ser, len(ser) - 2)
        if not now:
            continue
        now.update(key=k, name=name, group=group, cot_prev=prev["cot"] if prev else None, mkt=None)
        assets[k] = now
        hist[k] = ser
    missing = [a[0] for a in ASSETS if a[0] not in assets]
    if missing:
        log.debug("strumenti senza dati COT sufficienti: %s", ", ".join(missing))

    # ---- 2. punteggio Mercato e punteggio finale
    # isolato: se il modello di mercato ha un problema, i segnali COT restano validi (solo senza la parte "Mercato")
    try:
        market, mk = market_model(fred, ecb) if fred else (None, {})
    except Exception:
        log.exception("modello di mercato non calcolato: i segnali usano solo il COT")
        market, mk = None, {}
    for k, a in assets.items():
        m = mk.get(k)
        a["mkt"] = m
        a["macro"] = m["score"] if m else None
        a["score"] = (round(clip((1 - MACRO_WEIGHT) * a["cot"] + MACRO_WEIGHT * a["macro"], -100, 100), 1)
                      if a["macro"] is not None else a["cot"])
        a["prev"] = a["cot_prev"]          # settimana scorsa: solo COT (il mercato di allora non lo ricalcoliamo)
        a["label"] = label(a["score"], single=True)
        a["prev_label"] = label(a["prev"], single=True) if a["prev"] is not None else None
        a["new"] = a["prev_label"] is not None and a["prev_label"] != a["label"]

    # ---- 3. dollaro "composito": i futures CME sulle valute sono quotati CONTRO il dollaro,
    #         quindi comprare EUR, GBP, JPY... equivale a vendere USD. USD = 50% indice DXY + 50% inverso delle altre.
    majors = [c for c in ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD") if c in assets]
    if majors:
        dxy = assets.get("DXY")
        inv = -sum(assets[c]["score"] for c in majors) / len(majors)
        inv_c = -sum(assets[c]["cot"] for c in majors) / len(majors)
        inv_p = -sum(assets[c]["prev"] or 0 for c in majors) / len(majors)
        u = dict(dxy) if dxy else {"idx": None, "crowded": False, "net": None, "d_net": None}
        u.update(key="USD", name="Dollaro USA (composito)", group="Valute", composite=True, crowded=False,
                 score=round(0.5 * dxy["score"] + 0.5 * inv, 1) if dxy else round(inv, 1),
                 cot=round(0.5 * dxy["cot"] + 0.5 * inv_c, 1) if dxy else round(inv_c, 1),
                 prev=round(0.5 * (dxy["prev"] or 0) + 0.5 * inv_p, 1) if dxy else round(inv_p, 1),
                 macro=dxy.get("macro") if dxy else None, new=False)
        u["label"] = label(u["score"], single=True)
        assets["USD"] = u

    # ---- 4. coppie: punteggio = (base - quotata) / 2, cosi' resta tra -100 e +100
    pairs = []
    fx = [c for c in FX_ORDER if c in assets]
    combos = [(fx[i], fx[j]) for i in range(len(fx)) for j in range(i + 1, len(fx))] + EXTRA_PAIRS
    for b, q in combos:
        if b not in assets or q not in assets:
            continue
        sb, sq = assets[b]["score"], assets[q]["score"]
        sc = round((sb - sq) / 2, 1)
        div = is_divergence(sb, sq)
        pb, pq = assets[b].get("prev"), assets[q].get("prev")
        prev_lab = label((pb - pq) / 2, is_divergence(pb, pq)) if pb is not None and pq is not None else None
        lab = label(sc, div)
        mb, mq = assets[b].get("macro"), assets[q].get("macro")
        pairs.append({"pair": PAIR_NAMES.get((b, q), b + q), "base": b, "quote": q, "score": sc, "label": lab,
                      "div": div, "prev": prev_lab, "new": prev_lab is not None and prev_lab != lab,
                      "cot": round((assets[b]["cot"] - assets[q]["cot"]) / 2, 1),
                      "macro": round((mb - mq) / 2, 1) if mb is not None and mq is not None else None})

    # ---- 5. correlazioni tra i FLUSSI settimanali degli speculatori (ultime 52 settimane)
    flows = {}
    for k, ser in hist.items():
        n = {x["date"]: x["net"] / x["oi"] * 100 for x in ser}
        ds = sorted(n)
        flows[k] = {ds[i]: n[ds[i]] - n[ds[i - 1]] for i in range(1, len(ds))}
    keys = [a[0] for a in ASSETS if a[0] in flows]
    dates = sorted(set().union(*[set(f) for f in flows.values()]))[-52:] if flows else []

    def corr_of(fa, fb):
        common = [d for d in dates if d in fa and d in fb]        # solo le settimane presenti in entrambi
        c = pearson([fa[d] for d in common], [fb[d] for d in common])
        return round(c, 2) if c is not None else None

    matrix = [[None if i == j else corr_of(flows[a], flows[b]) for j, b in enumerate(keys)] for i, a in enumerate(keys)]
    fl = dict(flows)
    fl["USD"] = flows.get("DXY", {})
    for p in pairs:
        p["corr"] = corr_of(fl[p["base"]], fl[p["quote"]]) if fl.get(p["base"]) and fl.get(p["quote"]) else None
        p["rank"] = abs(p["score"]) + (25 if p["div"] else 0)     # le divergenze salgono in classifica
    pairs.sort(key=lambda p: -p["rank"])
    return assets, pairs, {"keys": keys, "m": matrix}, market
