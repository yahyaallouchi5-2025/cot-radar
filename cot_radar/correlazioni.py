# -*- coding: utf-8 -*-
"""
correlazioni.py - CHI SI MUOVE INSIEME E CHI AL CONTRARIO (prezzi giornalieri, aggiornati a ogni giro del sito)

IDEA
  La scheda "Correlazioni" aveva solo i flussi COT (settimanali). Qui si misura come si muovono i PREZZI:
  indici azionari, settori USA, obbligazioni, metalli, energia, agricole, cripto e dollaro.
  Correlazione dei rendimenti giornalieri: +1 = salgono e scendono insieme, -1 = quando uno sale l'altro scende,
  0 = nessun legame. Due finestre: ultimi 3 mesi (63 giorni di borsa, "adesso") e ultimo anno (252, "di solito").
  La differenza tra le due dice quali legami stanno CAMBIANDO (es. il Bitcoin che si stacca dal Nasdaq).

DATI
  Gli stessi prezzi Yahoo dei portafogli (portafogli.prezzi, copia locale aggiornata una volta al giorno) piu' gli
  ETF dei settori USA e del dollaro (portafogli.EXTRA). Calendario di borsa USA (SPY): cripto e mercati chiusi in
  un giorno USA ripetono l'ultimo prezzo, cosi' le serie sono allineate.

USCITA (per la pagina, D.corr_px)
  {"aggiornato", "asset": [{k, nome, g}], "gruppi": [...], "m63", "m252" (matrici), "insieme", "opposti",
   "cambiati" (coppie piu' forti / che cambiano di piu'), "spx": [{k, c63, c252, serie}] legame con l'S&P 500,
   "gm63", "gm252" (matrici medie tra gruppi)}

DEBUG: python -c "from cot_radar import correlazioni; help(correlazioni.calcola)"
"""
import math

# (ticker Yahoo, nome, gruppo). L'ordine e' quello delle righe della mappa di calore.
ASSET = [
    ("SPY", "S&P 500", "Indici"), ("QQQ", "Nasdaq-100", "Indici"), ("IWM", "Russell 2000", "Indici"),
    ("EFA", "Europa e Asia", "Indici"), ("EEM", "Emergenti", "Indici"),
    ("XLK", "Tecnologia", "Settori USA"), ("XLC", "Comunicazione", "Settori USA"), ("XLY", "Consumi ciclici", "Settori USA"),
    ("XLF", "Finanza", "Settori USA"), ("XLI", "Industria", "Settori USA"), ("XLE", "Energia (azioni)", "Settori USA"),
    ("XLB", "Materiali", "Settori USA"), ("XLV", "Salute", "Settori USA"), ("XLP", "Beni di prima necessità", "Settori USA"),
    ("XLU", "Utility", "Settori USA"), ("XLRE", "Immobiliare", "Settori USA"),
    ("IEF", "Treasury 10 anni", "Obbligazioni"), ("TLT", "Treasury 30 anni", "Obbligazioni"),
    ("GLD", "Oro", "Metalli"), ("SLV", "Argento", "Metalli"), ("PPLT", "Platino", "Metalli"), ("CPER", "Rame", "Metalli"),
    ("USO", "Petrolio WTI", "Energia"), ("UNG", "Gas naturale", "Energia"),
    ("CORN", "Mais", "Agricole"), ("WEAT", "Grano", "Agricole"), ("SOYB", "Soia", "Agricole"),
    ("BTC-USD", "Bitcoin", "Cripto"), ("ETH-USD", "Ether", "Cripto"),
    ("UUP", "Dollaro USA", "Dollaro"),
]
GRUPPI = ["Indici", "Settori USA", "Obbligazioni", "Metalli", "Energia", "Agricole", "Cripto", "Dollaro"]
FAMIGLIA = {"Indici": "azioni", "Settori USA": "azioni"}   # gruppi dello stesso mondo, esclusi dalle liste di coppie
BREVE, LUNGA = 63, 252          # giorni di borsa: ~3 mesi e ~1 anno
SERIE_SETT = 156                # punti settimanali della correlazione mobile con l'S&P 500 (~3 anni)
TOP = 8                         # coppie mostrate in "insieme", "opposti", "cambiati"


def _rendimenti(px, base="SPY"):
    """{ticker: [rendimento giornaliero o None]} sulle date dello SPY (ultimo prezzo noto ripetuto)."""
    date = [d for d, _ in px[base]]
    out = {}
    for t, *_ in ASSET:
        if t not in px:
            continue
        dd, col, ult = dict(px[t]), [], None
        for d in date:
            ult = dd.get(d, ult)
            col.append(ult)
        out[t] = [None] + [(col[i] / col[i - 1] - 1) if col[i] and col[i - 1] else None for i in range(1, len(col))]
    return date, out


def corr(a, b):
    """Correlazione di Pearson tra due liste (solo i giorni in cui ci sono entrambi). None con meno di 20 coppie."""
    xy = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(xy)
    if n < 20:
        return None
    mx, my = sum(x for x, _ in xy) / n, sum(y for _, y in xy) / n
    sxy = sum((x - mx) * (y - my) for x, y in xy)
    sx = math.sqrt(sum((x - mx) ** 2 for x, _ in xy))
    sy = math.sqrt(sum((y - my) ** 2 for _, y in xy))
    return round(sxy / (sx * sy), 2) if sx and sy else None


def calcola(px):
    """Dati della parte "Prezzi" della scheda Correlazioni, oppure None se mancano i prezzi dello SPY."""
    if not px or "SPY" not in px:
        return None
    date, r = _rendimenti(px)
    asset = [{"k": t, "nome": n, "g": g} for t, n, g in ASSET if t in r]
    ks = [a["k"] for a in asset]
    m = {}
    for nome, giorni in (("m63", BREVE), ("m252", LUNGA)):
        fin = {k: r[k][-giorni:] for k in ks}
        m[nome] = [[1.0 if i == j else corr(fin[a], fin[b]) for j, b in enumerate(ks)] for i, a in enumerate(ks)]
    # coppie per le tre liste (insieme, al contrario, stanno cambiando)
    coppie = []
    for i, a in enumerate(asset):
        for j in range(i + 1, len(asset)):
            b = asset[j]
            c, l = m["m63"][i][j], m["m252"][i][j]
            # niente coppie dello stesso "mondo" (es. S&P 500 e Tecnologia: ovvio che vadano insieme)
            if c is None or FAMIGLIA.get(a["g"], a["g"]) == FAMIGLIA.get(b["g"], b["g"]):
                continue
            coppie.append({"a": a["k"], "b": b["k"], "c63": c, "c252": l, "delta": round(c - l, 2) if l is not None else None})
    insieme = sorted(coppie, key=lambda x: -x["c63"])[:TOP]
    opposti = sorted(coppie, key=lambda x: x["c63"])[:TOP]
    cambiati = sorted([x for x in coppie if x["delta"] is not None], key=lambda x: -abs(x["delta"]))[:TOP]
    # legame con l'S&P 500 + correlazione mobile a 3 mesi, un punto a settimana (per la mini linea)
    spx = []
    i0 = ks.index("SPY") if "SPY" in ks else None
    for i, k in enumerate(ks):
        if k == "SPY" or i0 is None:
            continue
        # un punto ogni 5 giorni di borsa, a ritroso dall'ultimo giorno (cosi' l'ultimo punto e' sempre "oggi")
        punti = [t for t in range(len(date) - 1, BREVE - 1, -5)][:SERIE_SETT][::-1]
        serie = [corr(r[k][t - BREVE + 1:t + 1], r["SPY"][t - BREVE + 1:t + 1]) for t in punti]
        spx.append({"k": k, "c63": m["m63"][i][i0], "c252": m["m252"][i][i0], "serie": serie})
    spx.sort(key=lambda x: -(x["c63"] if x["c63"] is not None else -2))
    # matrici medie tra GRUPPI (vista "per settore")
    gr = [g for g in GRUPPI if any(a["g"] == g for a in asset)]
    gm = {}
    for nome in ("m63", "m252"):
        righe = []
        for ga in gr:
            riga = []
            for gb in gr:
                v = [m[nome][i][j] for i, a in enumerate(asset) for j, b in enumerate(asset)
                     if a["g"] == ga and b["g"] == gb and i != j and m[nome][i][j] is not None]
                riga.append(round(sum(v) / len(v), 2) if v else None)
            righe.append(riga)
        gm["g" + nome] = righe
    return {"aggiornato": date[-1], "asset": asset, "gruppi": gr, **m, **gm,
            "insieme": insieme, "opposti": opposti, "cambiati": cambiati, "spx": spx}
