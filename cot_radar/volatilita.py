# -*- coding: utf-8 -*-
"""
volatilita.py - LA NATURA DI OGNI MERCATO: quanto si muove, giorno per giorno, settimana per settimana,
mese per mese e anno per anno, e in che "regime" e' adesso (calmo, normale, agitato).

Perche' serve: un drawdown del 2% e' tanto su EURUSD (si muove ~0,5% a settimana) e poco sul gas (~5%).
Inoltre il regime di volatilita' nel momento in cui nasce un segnale puo' cambiarne il comportamento:
il backtest divide i segnali in calma / normale / agitata (vedi backtest.py) per scoprirlo.

Dati: archivio permanente dei prezzi (storico.py), quindi decenni di storia senza chiamate in piu'.
LIMITE: FRED da' solo la CHIUSURA giornaliera. La volatilita' qui e' "da chiusura a chiusura";
il range vero della giornata (massimo - minimo, ATR) richiederebbe dati OHLC (a pagamento).

Unita':
  - movimenti giornalieri e settimanali = media del valore assoluto della variazione in %;
  - volatilita' (mesi, anni, regime) = deviazione standard dei rendimenti giornalieri x radice di 252,
    cioe' "volatilita' annua" in %, la misura standard per confrontare periodi e mercati.

DEBUG: python -m unittest tests.test_volatilita -v
"""
import math
from bisect import bisect_left
from datetime import date

from .config import PRICES
from .log import log
from .stagionalita import prezzo_coppia

ANNO = 252                 # sedute in un anno: per "annualizzare" la volatilita'
MOBILE = 20                # finestra del regime attuale: ultime 20 sedute (4 settimane)
CONFRONTO = 1260           # il regime si confronta con gli ultimi 5 anni (1260 sedute)
SOGLIE = (33, 67)          # sotto il 33 percentile = calma, sopra il 67 = agitata
MIN_ANNO = 50              # un anno con meno di 50 prezzi non viene mostrato (dato troppo scarso)
GIORNI = ["lun", "mar", "mer", "gio", "ven"]
SALTA = {k for k, v in PRICES.items() if v[0].startswith("DEX")} | {"DXY", "USD"}   # valute: gia' nelle coppie


def _dev(x):
    """Deviazione standard campionaria (None con meno di 2 valori)."""
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def rendimenti(pts):
    """[(data, rendimento logaritmico dal prezzo precedente)] saltando prezzi nulli o negativi."""
    return [(pts[i][0], math.log(pts[i][1] / pts[i - 1][1])) for i in range(1, len(pts))
            if pts[i][1] > 0 and pts[i - 1][1] > 0]


def vol_mobile(pts, n=MOBILE):
    """Volatilita' annua delle ultime n sedute, per ogni indice di pts (None all'inizio).
    Calcolata con somme scorrevoli: veloce anche su 50 anni di dati."""
    out = [None] * len(pts)
    r = [0.0] + [math.log(pts[i][1] / pts[i - 1][1]) if pts[i][1] > 0 and pts[i - 1][1] > 0 else 0.0
                 for i in range(1, len(pts))]
    s = s2 = 0.0
    for i in range(1, len(pts)):
        s += r[i]
        s2 += r[i] * r[i]
        if i > n:
            s -= r[i - n]
            s2 -= r[i - n] * r[i - n]
        if i >= n:
            var = max(0.0, (s2 - s * s / n) / (n - 1))
            out[i] = math.sqrt(var) * math.sqrt(ANNO) * 100
    return out


def regime(v20, i, finestra=CONFRONTO):
    """Regime di volatilita' all'indice i, confrontato SOLO con il passato (ultimi 5 anni): niente "futuro".
    Restituisce (etichetta, percentile 0..100, volatilita' annua) oppure None se la storia e' troppo corta."""
    if i is None or i >= len(v20) or v20[i] is None:
        return None
    passato = sorted(v for v in v20[max(0, i - finestra):i] if v is not None)
    if len(passato) < 250:
        return None
    pct = round(100 * bisect_left(passato, v20[i]) / len(passato))
    nome = "calma" if pct < SOGLIE[0] else "agitata" if pct > SOGLIE[1] else "normale"
    return nome, pct, round(v20[i], 1)


def profilo(pts):
    """Profilo completo di uno strumento: giorni della settimana, settimane, mesi, anni e regime attuale."""
    r = rendimenti(pts)
    if len(r) < 300:
        return None
    ultimo_anno = r[-ANNO:]
    # --- giorno per giorno: movimento medio (valore assoluto) per giorno della settimana
    per_g, per_g1 = [[] for _ in range(5)], [[] for _ in range(5)]
    for d, x in r:
        w = date.fromisoformat(d).weekday()
        if w < 5:
            per_g[w].append(abs(x) * 100)
    for d, x in ultimo_anno:
        w = date.fromisoformat(d).weekday()
        if w < 5:
            per_g1[w].append(abs(x) * 100)
    media = lambda v: round(sum(v) / len(v), 3) if v else None
    giorni = [{"g": GIORNI[w], "storia": media(per_g[w]), "anno": media(per_g1[w])} for w in range(5)]
    # --- settimana per settimana: variazione tra l'ultima chiusura di ogni settimana (lunedi'-venerdi')
    fine_sett = {}
    for d, p in pts:
        if p and p > 0:
            y, wk, _ = date.fromisoformat(d).isocalendar()
            fine_sett[(y, wk)] = p                         # resta l'ultimo prezzo della settimana
    ps = [fine_sett[k] for k in sorted(fine_sett)]
    sett = sorted(abs(ps[i] / ps[i - 1] - 1) * 100 for i in range(1, len(ps)))
    sett_anno = sorted(abs(ps[i] / ps[i - 1] - 1) * 100 for i in range(max(1, len(ps) - 52), len(ps)))
    settimane = {"media": round(sum(sett) / len(sett), 2), "brutta": round(sett[int(0.9 * len(sett))], 2),
                 "media_anno": round(sum(sett_anno) / len(sett_anno), 2) if sett_anno else None,
                 "ultima": round(abs(ps[-1] / ps[-2] - 1) * 100, 2) if len(ps) > 1 else None}
    # --- mese per mese (calendario): volatilita' annua media dei giorni di quel mese, su tutta la storia
    per_m = [[] for _ in range(12)]
    for d, x in r:
        per_m[int(d[5:7]) - 1].append(x)
    sd = lambda v: round(_dev(v) * math.sqrt(ANNO) * 100, 1) if len(v) > 20 else None
    mesi = [sd(v) for v in per_m]
    # --- anno per anno
    per_a = {}
    for d, x in r:
        per_a.setdefault(d[:4], []).append(x)
    anni = {a: sd(v) for a, v in sorted(per_a.items()) if len(v) >= MIN_ANNO}
    # --- regime di adesso
    v20 = vol_mobile(pts)
    reg = regime(v20, len(pts) - 1)
    oggi = r[-1]
    w = date.fromisoformat(oggi[0]).weekday()
    return {
        "dal": pts[0][0], "al": pts[-1][0], "prezzo": round(pts[-1][1], 6),   # ultimo prezzo: per i pip/punti
        "giorni": giorni, "settimane": settimane, "mesi": mesi, "anni": anni,
        "ann_storia": sd([x for _, x in r]), "ann_anno": sd([x for _, x in ultimo_anno]),
        "regime": {"nome": reg[0], "pct": reg[1], "vol": reg[2]} if reg else None,
        "oggi": {"data": oggi[0], "mossa": round(abs(oggi[1]) * 100, 3),
                 "media_giorno": giorni[w]["storia"] if w < 5 else None},
    }


def strumenti_con_prezzo(pairs, prezzi):
    """{nome: prezzi} delle coppie e degli strumenti non valutari con un prezzo storico."""
    out = {}
    for p in pairs:
        pts = prezzo_coppia(prezzi, p["base"], p["quote"])
        if pts:
            out[p["pair"]] = pts
    for k, pts in prezzi.items():
        if k not in SALTA and pts:
            out[k] = pts
    return out


def calcola(pairs, prezzi):
    """Profilo di volatilita' di ogni strumento verificabile. Isolato: se uno strumento fallisce, gli altri restano."""
    out = {}
    for nome, pts in strumenti_con_prezzo(pairs, prezzi).items():
        try:
            pr = profilo(pts)
            if pr:
                out[nome] = pr
        except Exception as e:
            log.warning("volatilita' di %s non calcolata: %s", nome, e)
    return out


class Regimi:
    """Regime di volatilita' al momento di ogni segnale, con un calcolo solo per strumento (cache).
    Usa i prezzi fino al giorno PRIMA della generazione: e' quello che si sapeva quando il segnale e' nato."""

    def __init__(self):
        self.cache = {}

    def al_segnale(self, nome, pts, generato):
        if nome not in self.cache:
            self.cache[nome] = ([d for d, _ in pts], vol_mobile(pts))
        date_, v20 = self.cache[nome]
        i = bisect_left(date_, generato[:10]) - 1
        r = regime(v20, i) if i >= 0 else None
        return {"nome": r[0], "pct": r[1], "vol": r[2]} if r else None
