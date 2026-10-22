# -*- coding: utf-8 -*-
"""
demo.py - dati FINTI ma realistici, per provare e fare debug SENZA internet.

    python main.py --demo

Genera serie casuali con la stessa forma di quelle vere (CFTC, FRED, BCE) e con alcune relazioni
volute (es. EUR scende quando sale il differenziale tassi USA-Europa), cosi' il modello ha qualcosa da trovare.
Il seme casuale e' fisso: ogni volta escono gli stessi numeri, utile per confrontare prima/dopo una modifica.
I numeri NON sono reali: non usarli per decidere nulla.
"""
import math
import random
from datetime import date, timedelta

from .calcoli import add_month, month_avg
from .config import ASSETS, FRED_IDS, K_DFR, K_ESTR, K_EURIBOR, K_MIR, K_Y2, K_Y10, PRICES


def demo_data(seed=7):
    rnd = random.Random(seed)
    today = date.today()

    # ---- COT: un "random walk" del netto per ogni mercato, ogni martedi'
    last_fri = today - timedelta(days=(today.weekday() - 4) % 7)      # ultimo venerdi' (giorno di uscita)
    last_tue = last_fri - timedelta(days=3)                            # i dati si riferiscono al martedi' prima
    rows = []
    for k, code, _, _ in ASSETS:
        oi = rnd.randint(50000, 900000)
        net = rnd.uniform(-.2, .2) * oi
        for w in range(175, -1, -1):
            d = last_tue - timedelta(weeks=w)
            net += rnd.gauss(0, .025) * oi
            if w < 5 and k in ("EUR", "CORN", "NATGAS"):
                net -= 0.04 * oi                 # speculatori in vendita nelle ultime settimane
            if w < 5 and k in ("DXY", "GOLD", "COFFEE", "SP500"):
                net += 0.04 * oi                 # speculatori in acquisto
            net = max(-.5 * oi, min(.5 * oi, net))
            lo = oi * .35 + max(net, 0) + 5000
            oiw = int(oi * (1 + 0.08 * math.sin(w / 7)))             # open interest che sale e scende nel tempo
            comm = -0.85 * net + rnd.gauss(0, .02) * oi              # i Commercials stanno di solito dall'altra parte
            cl = oi * .4 + max(comm, 0)
            rows.append({"report_date_as_yyyy_mm_dd": d.isoformat() + "T00:00:00.000", "cftc_contract_market_code": code,
                         "open_interest_all": str(oiw), "noncomm_positions_long_all": str(int(lo)),
                         "noncomm_positions_short_all": str(int(lo - net)),
                         "comm_positions_long_all": str(int(cl)), "comm_positions_short_all": str(int(cl - comm))})

    # ---- giorni lavorativi degli ultimi ~4 anni
    days, d = [], today - timedelta(days=1400)
    while d < today:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)

    lv = {"DGS2": 4.3, "DGS10": 4.0, "DFII10": 1.8, "T10YIE": 2.3, "VIXCLS": 17, "BAMLH0A0HYM2": 3.4, "EU2": 2.6, "EU10": 2.6}
    fred = {k: [] for k in FRED_IDS}
    eu2, eu10, estr = [], [], []
    px = {k: 100.0 for k in PRICES}
    # relazioni volute: (driver, sensibilita') -> il modello di mercato dovrebbe ritrovarle
    sens = {"EUR": {"diff": -0.02}, "GBP": {"diff": -0.015}, "AUD": {"VIXCLS": -0.25}, "SP500": {"VIXCLS": -0.6},
            "NASDAQ": {"VIXCLS": -0.8, "DFII10": -0.04}, "BTC": {"DFII10": -0.08}, "WTI": {"T10YIE": 0.1}}
    dfr = 4.0
    for i, d in enumerate(days):
        ch = {k: rnd.gauss(0, 0.045) for k in ("DGS2", "DGS10", "DFII10", "T10YIE", "EU2", "EU10")}
        for k, v in ch.items():
            lv[k] += v
        ch["VIXCLS"] = rnd.gauss(0, 0.9)
        lv["VIXCLS"] = max(10, lv["VIXCLS"] + ch["VIXCLS"] - 0.05 * (lv["VIXCLS"] - 17))
        ch["BAMLH0A0HYM2"] = rnd.gauss(0, 0.03)
        lv["BAMLH0A0HYM2"] += ch["BAMLH0A0HYM2"]
        if d.day == 15 and dfr > 2.0 and i < len(days) - 300:
            dfr -= 0.25                                       # la BCE taglia i tassi nella prima parte dello storico
        ds = d.isoformat()
        for k in ("DGS2", "DGS10", "DFII10", "T10YIE", "VIXCLS", "BAMLH0A0HYM2"):
            fred[k].append([ds, round(lv[k], 3)])
        eu2.append([ds, round(lv["EU2"], 3)]); eu10.append([ds, round(lv["EU10"], 3)])
        estr.append([ds, round(dfr - 0.08 + rnd.gauss(0, 0.01), 3)])
        diffch = (ch["DGS2"] - ch["EU2"]) * 100
        for k, (sid, sign) in PRICES.items():
            r = rnd.gauss(0, 0.005)
            for drv, b in sens.get(k, {}).items():
                x = diffch if drv == "diff" else ch[drv] * (1 if drv == "VIXCLS" else 100)
                r += b * x / 100
            px[k] *= (1 + r)
            fred[sid].append([ds, round(px[k] if sign > 0 else 1 / px[k], 6)])
        if d.weekday() == 2:
            fred["WALCL"].append([ds, 7e6 * (1 - 0.0003 * i)]); fred["WTREGEN"].append([ds, 750000 + rnd.gauss(0, 30000)])
        if d.weekday() == 3:
            fred["MORTGAGE30US"].append([ds, round(lv["DGS10"] + 2.4, 2)])
        fred["RRPONTSYD"].append([ds, max(0, 400 - i * 0.4) * 1000])
    fred = {k: v for k, v in fred.items() if v}

    # ---- BCE: tassi mutui che inseguono (con ritardo) i tassi di mercato
    ecb = {}
    y10m, estm = month_avg(eu10), month_avg(estr)
    last_month = add_month(today.strftime("%Y-%m"), -2)        # come nella realta': ~2 mesi di ritardo
    for cc, base in (("IT", 0), ("U2", -.1), ("DE", -.15), ("FR", -.25), ("ES", -.05)):
        for mt in "AFP":
            pts, val = [], None
            for m in sorted(y10m):
                pm = add_month(m, -1)
                if m > last_month or pm not in y10m:
                    continue
                tgt = {"P": y10m[pm] + 1.2, "F": estm[pm], "A": (y10m[pm] + 1.2 + estm[pm]) / 2}[mt] + base
                val = tgt if val is None else val + 0.5 * (tgt - val) + rnd.gauss(0, 0.03)
                pts.append([m, round(val, 2)])
            ecb[K_MIR.format(c=cc, m=mt)] = pts
    ecb[K_EURIBOR] = [[m, round(v + 0.15, 3)] for m, v in sorted(estm.items()) if m <= add_month(last_month, 1)]
    ecb[K_ESTR], ecb[K_Y2], ecb[K_Y10] = estr, eu2, eu10
    ecb[K_DFR] = [[d.isoformat(), 2.0] for d in days[-300:]]

    now = today.isoformat() + "T00:00"
    cache = {"cot": {"saved": now, "data": rows}, "fred": {"saved": now, "data": fred}, "ecb": {"saved": now, "data": ecb}}
    return cache, {"cot": "online", "fred": "online", "ecb": "online"}, {}
