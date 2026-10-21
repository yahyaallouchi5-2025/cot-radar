# -*- coding: utf-8 -*-
"""
mutui.py - tassi sui mutui casa (statistica ufficiale BCE "MIR", per l'Italia fonte Banca d'Italia).

Il dato ufficiale esce circa 5 settimane dopo la fine del mese. I tassi di mercato che lo guidano
(rendimento a 10 anni per il fisso, ESTR per il variabile) escono invece ogni giorno:
li usiamo per STIMARE i mesi non ancora pubblicati.
"""
import math
from datetime import date

from .calcoli import add_month, month_avg, ols
from .config import COUNTRIES, K_DFR, K_ESTR, K_EURIBOR, K_MIR, K_Y2, K_Y10


def mortgage_projection(m_series, drv_month, months_back=72):
    """Stima del tasso mutuo nei mesi successivi all'ultimo dato pubblicato.

    Modello (sulle VARIAZIONI mensili, piu' stabili dei livelli):
        variazione mutuo(t) = a + b1 * variazione driver(t) + b2 * variazione driver(t-1)
    Il termine (t-1) cattura il ritardo con cui le banche aggiornano i listini.
    Restituisce i punti stimati con un errore che cresce con la distanza (sigma * radice(mesi))."""
    ms = sorted(m_series)
    rows_x, rows_y = [], []
    for t in ms[-months_back:]:
        p, p1 = add_month(t, -1), add_month(t, -2)
        if p in m_series and all(k in drv_month for k in (t, p, p1)):
            rows_x.append([drv_month[t] - drv_month[p], drv_month[p] - drv_month[p1]])
            rows_y.append(m_series[t] - m_series[p])
    if len(rows_y) < 24:                      # meno di 2 anni di storia: stima non affidabile
        return None
    m = ols(rows_x, rows_y)
    if not m:
        return None
    last = ms[-1]
    cur = date.today().strftime("%Y-%m")
    val, out, h = m_series[last], [], 0
    k = add_month(last, 1)
    # avanti un mese alla volta finche' abbiamo i dati di mercato (anche il mese in corso, parziale)
    while k <= cur and k in drv_month and add_month(k, -1) in drv_month and add_month(k, -2) in drv_month:
        x = [drv_month[k] - drv_month[add_month(k, -1)], drv_month[add_month(k, -1)] - drv_month[add_month(k, -2)]]
        val = val + m["my"] + sum((x[j] - m["mu"][j]) / m["sd"][j] * m["beta"][j] for j in range(2))
        h += 1
        out.append({"month": k, "value": round(val, 2), "err": round(m["sigma"] * math.sqrt(h), 2)})
        k = add_month(k, 1)
    return {"r2": round(m["r2"], 2), "points": out}


def mortgages(ecb, fred):
    """Prepara tutto cio' che serve alla scheda "Mutui". None se mancano i dati BCE."""
    if not ecb:
        return None

    def mir(c, mt):
        """Serie mensile di un paese c e tipo mt (A=media, F=variabile, P=fisso >10 anni) -> {"AAAA-MM": tasso}"""
        return dict((d[:7], v) for d, v in ecb.get(K_MIR.format(c=c, m=mt), []))

    it_tot, it_var, it_fix = mir("IT", "A"), mir("IT", "F"), mir("IT", "P")
    if not it_tot:
        return None
    y10, estr = month_avg(ecb.get(K_Y10, [])), month_avg(ecb.get(K_ESTR, []))
    eur = dict((d[:7], v) for d, v in ecb.get(K_EURIBOR, []))

    # tabella di confronto tra paesi, con la variazione su 12 mesi
    table = []
    for c, name in COUNTRIES:
        row = {"code": c, "name": name}
        for mt, lab in (("A", "tot"), ("F", "var"), ("P", "fix")):
            s = mir(c, mt)
            if s:
                ks = sorted(s)
                row[lab] = round(s[ks[-1]], 2)
                row[lab + "_d12"] = round(s[ks[-1]] - s[ks[-13]], 2) if len(ks) > 12 else None
                row["month"] = ks[-1]
        table.append(row)

    months = sorted(it_tot)[-60:]      # ultimi 5 anni per il grafico
    hist = {"months": months, "fix": [it_fix.get(m) for m in months], "var": [it_var.get(m) for m in months],
            "tot": [it_tot.get(m) for m in months],
            "y10": [round(y10[m], 2) if m in y10 else None for m in months],
            "estr": [round(estr[m], 2) if m in estr else None for m in months]}
    last = sorted(it_tot)[-1]

    def lastpt(key):
        s = ecb.get(key) or [[None, None]]
        return {"date": s[-1][0], "v": s[-1][1]}

    us = fred.get("MORTGAGE30US")
    return {
        "last": last, "tot": it_tot[last], "var": it_var.get(last), "fix": it_fix.get(last),
        "tot_d3": round(it_tot[last] - it_tot.get(add_month(last, -3), it_tot[last]), 2),
        "tot_d12": round(it_tot[last] - it_tot.get(add_month(last, -12), it_tot[last]), 2),
        # margine della banca sul fisso = tasso fisso - rendimento 10 anni
        "fix_spread": round(it_fix[last] - y10[last], 2) if last in y10 and last in it_fix else None,
        "proj_fix": mortgage_projection(it_fix, y10) if it_fix and y10 else None,
        "proj_var": mortgage_projection(it_var, estr) if it_var and estr else None,
        "table": table, "hist": hist,
        "y10": lastpt(K_Y10), "y2": lastpt(K_Y2), "estr": lastpt(K_ESTR), "dfr": lastpt(K_DFR),
        "euribor": {"month": sorted(eur)[-1], "v": eur[sorted(eur)[-1]]} if eur else None,
        "us30": {"date": us[-1][0], "v": us[-1][1], "d4": round(us[-1][1] - us[-5][1], 2) if len(us) > 5 else None,
                 "spark": [x[1] for x in us[-104:]]} if us else None,
    }
