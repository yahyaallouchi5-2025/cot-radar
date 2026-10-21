# -*- coding: utf-8 -*-
"""
mercato.py - il "Mercato" a breve termine: cosa e' gia' scontato nei prezzi.

IDEA
  Il mercato anticipa le notizie. Invece dei dati macro (che escono in ritardo) usiamo indicatori
  prezzati ogni giorno: tasso USA 2a, rendimento reale, inflazione attesa, VIX, spread high yield,
  differenziale tassi USA-Europa.

COME
  1. Per ogni strumento con un prezzo pubblico costruiamo dati SETTIMANALI (rendimento % e variazioni dei driver).
  2. Regressione: rendimento = somma(beta_i * variazione driver_i). Stimata su 2 anni ESCLUDENDO
     le ultime 4 settimane (cosi' il test sulle ultime 4 e' "fuori campione", piu' onesto).
  3. Ultime 4 settimane: mossa IMPLICITA (quella che i driver "chiedevano") vs mossa REALE del prezzo.
       differenza ~ 0            -> gia' scontato
       implicita > reale         -> prezzo in ritardo, spazio al rialzo
       implicita < reale         -> spazio al ribasso
  4. Punteggio = differenza / errore tipico, ridotto se il modello spiega poco (R2 basso).
"""
from datetime import datetime, timedelta

from .calcoli import Series, clip, ols, zlast
from .config import DRIVERS, HISTORY_WEEKS, K_Y2, PRICES, REG_WEEKS


def market_model(fred, ecb):
    """Restituisce (stato_driver, {chiave_strumento: risultato_modello}). (None, {}) se mancano dati."""
    S = {k: Series(v) for k, v in fred.items()}
    eu2 = Series(ecb[K_Y2]) if K_Y2 in ecb else None
    # teniamo solo i driver di cui abbiamo davvero i dati
    drv = [d for d in DRIVERS if (d[2] in S) or (d[0] == "diff" and eu2 and "DGS2" in S)]
    if len(drv) < 3:
        return None, {}

    def dval(d, day):
        """Valore del driver d nel giorno day (il differenziale e' calcolato al volo)."""
        if d[0] == "diff":
            a, b = S["DGS2"].at(day), eu2.at(day)
            return None if a is None or b is None else a - b
        return S[d[2]].at(day)

    # "ancora" = l'ultimo giorno in cui TUTTI i driver hanno un dato: da li' contiamo le settimane all'indietro
    anchor = min((S[d[2]].last[0] if d[2] else min(S["DGS2"].last[0], eu2.last[0])) for d in drv)
    a = datetime.strptime(anchor, "%Y-%m-%d").date()
    weeks = [(a - timedelta(weeks=i)).isoformat() for i in range(HISTORY_WEEKS)][::-1]
    X = {d[0]: [dval(d, w) for w in weeks] for d in drv}
    mult = {d[0]: (100 if d[3] == "pb" else 1) for d in drv}   # tassi in % -> punti base (x100)

    def chg(vals, i, h=1):
        """Variazione su h settimane (None se manca un dato)."""
        return None if vals[i] is None or vals[i - h] is None else vals[i] - vals[i - h]

    # ---- stato attuale di ogni driver (per le schede della dashboard)
    drivers = []
    for d in drv:
        v = X[d[0]]
        dv = [x * mult[d[0]] for x in (chg(v, i) for i in range(1, len(v))) if x is not None]
        c1, c4 = chg(v, len(v) - 1), chg(v, len(v) - 1, 4)
        drivers.append({
            "key": d[0], "name": d[1], "unit": d[3], "value": v[-1],
            "d1": round(c1 * mult[d[0]], 1) if c1 is not None else None,
            "d4": round(c4 * mult[d[0]], 1) if c4 is not None else None,
            # quanto e' insolita la mossa di 4 settimane rispetto agli ultimi 2 anni
            "z4": round(zlast([sum(dv[i - 3:i + 1]) for i in range(3, len(dv))], REG_WEEKS), 2),
            "spark": [round(x, 3) if x is not None else None for x in v[-104:]],
        })

    # ---- modello per ogni strumento con prezzo
    out = {}
    for key, (sid, sign) in PRICES.items():
        if sid not in S:
            continue
        p = [S[sid].at(w) for w in weeks]
        p = [(x if sign > 0 else (1 / x if x else None)) if x is not None else None for x in p]
        rows_x, rows_y = [], []
        for i in range(1, len(weeks)):
            if p[i] is None or p[i - 1] is None:
                continue
            xs = [chg(X[d[0]], i) for d in drv]
            if None in xs:
                continue
            rows_x.append([x * mult[d[0]] for x, d in zip(xs, drv)])
            rows_y.append((p[i] / p[i - 1] - 1) * 100)                 # rendimento settimanale in %
        if len(rows_y) < 60:
            continue
        # stima su (al massimo) REG_WEEKS settimane, escluse le ultime 4
        if len(rows_x) > REG_WEEKS + 4:
            fx, fy = rows_x[-REG_WEEKS - 4:-4], rows_y[-REG_WEEKS - 4:-4]
        else:
            fx, fy = rows_x[:-4], rows_y[:-4]
        m = ols(fx, fy, ridge=3.0)
        if not m:
            continue
        # contributo di ogni driver alla mossa delle ultime 4 settimane
        contrib = [0.0] * len(drv)
        for r in rows_x[-4:]:
            for j in range(len(drv)):
                contrib[j] += (r[j] - m["mu"][j]) / m["sd"][j] * m["beta"][j]
        impl = sum(contrib)                                    # mossa implicita (%)
        act = sum(y - m["my"] for y in rows_y[-4:])            # mossa reale (%), tolta la deriva media
        gap = impl - act
        s4 = m["sigma"] * 2                                     # errore tipico su 4 settimane = sigma*radice(4)
        rel = min(1.0, m["r2"] / 0.15)                          # fiducia: piena se R2 >= 0.15
        gz = gap / s4 if s4 else 0
        score = round(100 * clip(gz / 2) * rel, 1)
        if m["r2"] < 0.05:
            status = "Il macro spiega poco questo strumento"
        elif abs(gz) < 0.5:
            status = "GIA' SCONTATO: il prezzo ha gia' fatto la mossa dei driver"
        elif gz > 0:
            status = "IN RITARDO: i driver spingono piu' in alto di dove e' il prezzo"
        else:
            status = "IN RITARDO: i driver spingono piu' in basso di dove e' il prezzo"
        top = sorted(range(len(drv)), key=lambda j: -abs(contrib[j]))[:2]
        out[key] = {
            "r2": round(m["r2"], 2), "impl": round(impl, 2), "act": round(act, 2), "gap": round(gap, 2),
            "gz": round(gz, 2), "score": score, "status": status, "sigma4": round(s4, 2),
            "top": [{"name": drv[j][1], "c": round(contrib[j], 2)} for j in top],
            "price": round(p[-1], 6) if p[-1] else None,
        }

    # clima di rischio: VIX, spread e rendimenti reali in salita = negativo per gli asset rischiosi
    zz = {d["key"]: d["z4"] for d in drivers}
    risk = -(zz.get("vix", 0) + zz.get("hy", 0)) / 2 - zz.get("real", 0) / 2
    return {"drivers": drivers, "anchor": anchor, "risk": round(100 * clip(risk / 2)), "weeks": weeks[-104:]}, out


def fed_liquidity(fred):
    """Contesto lento (non entra nel punteggio): bilancio Fed e liquidita' netta.
    Liquidita' netta = bilancio Fed - conto del Tesoro (TGA) - reverse repo (RRP)."""
    need = ("WALCL", "WTREGEN", "RRPONTSYD")
    if not all(k in fred for k in need):
        return None
    S = {k: Series(fred[k]) for k in need}
    last = S["WALCL"].last[0]
    a = datetime.strptime(last, "%Y-%m-%d").date()
    weeks = [(a - timedelta(weeks=i)).isoformat() for i in range(157)][::-1]
    bs = [S["WALCL"].at(w) for w in weeks]
    nl = [None if None in (S[k].at(w) for k in need) else S["WALCL"].at(w) - S["WTREGEN"].at(w) - S["RRPONTSYD"].at(w)
          for w in weeks]
    if None in bs[-14:] or None in nl[-5:]:
        return None
    bs13 = (bs[-1] / bs[-14] - 1) * 100            # variazione del bilancio in 13 settimane (~3 mesi)
    nl4 = (nl[-1] / nl[-5] - 1) * 100              # variazione della liquidita' in 4 settimane
    regime = ("QT (bilancio in riduzione)" if bs13 <= -0.75 else
              "Espansione (QE o acquisti di riserve)" if bs13 >= 0.75 else "Stabile")
    return {"date": last, "bs": bs[-1], "nl": nl[-1], "bs13": round(bs13, 2), "nl4": round(nl4, 2), "regime": regime,
            "spark_bs": [round(x / 1e6, 3) for x in bs if x], "spark_nl": [round(x / 1e6, 3) for x in nl if x]}
