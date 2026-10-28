# -*- coding: utf-8 -*-
"""
backtest_varianti.py - CONFRONTO TRA VARIANTI DEI PORTAFOGLI (solo studio: non cambia nulla sul sito)

Idea: prima di toccare i profili del sito si misura su dati storici cosa cambierebbe. Si usa lo stesso motore di
cot_radar/portafogli.py (stessi prezzi Yahoo, stesso filtro di trend a 200 giorni, stessi costi) e si cambiano
SOLO i pesi o la frequenza dei ribilanciamenti.

VARIANTI
  A  Attuale             : profili come sul sito (az 10/20/40%), ribilancio ogni mese.
  B  Azioni ridotte      : quota "5 azioni scelte" 5/10/15%; il resto va negli ETF della base (stessi pesi relativi).
  C  B + difesa          : come B, ma meta' dei Treasury 7-10 anni passa in liquidita' e +5 punti di oro
                           (difesa meno legata ai tassi, dopo il 2022).
  D  C + ribilancio lento: come C, ma si scambia solo se cambia l'insieme dei mercati attivi (un segnale di trend
                           scatta) oppure ogni 3 mesi: meno movimenti = meno costi e meno tasse (26% sulle vendite in guadagno).
BENCHMARK PER PROFILO: 30/70, 60/40, 80/20 (S&P 500 / Treasury 10 anni, ribilanciati ogni mese).

LIMITI (da dire chiaro): i prezzi sono ETF USA in dollari, quindi NON si vede l'effetto del cambio euro/dollaro e
della copertura valutaria; le tasse non sono simulate, si mostra il TURNOVER (% di capitale scambiato all'anno)
che e' la misura da cui dipendono. Risultati storici, non garanzia.

USO:  python tools/backtest_varianti.py [cartella_dati] [satellite.json]
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cot_radar import portafogli as P          # noqa: E402

CARTELLA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.ROOT, "storico")
SAT = sys.argv[2] if len(sys.argv) > 2 else None


def _norm(base):
    """Riporta i pesi della base a somma 1."""
    t = sum(base.values())
    return {k: v / t for k, v in base.items()}


def variante(prof, az=None, difesa=False):
    """Copia del profilo con quota azioni scelte e/o difesa cambiate."""
    p = copy.deepcopy(prof)
    if az is not None:
        p["az"] = az
    if difesa and "US10Y" in p["base"]:
        meta = p["base"]["US10Y"] / 2
        p["base"]["US10Y"] -= meta
        p["base"]["CASH"] = p["base"].get("CASH", 0) + meta
        if "GOLD" in p["base"]:
            p["base"]["GOLD"] += 0.05
            p["base"]["CASH"] -= 0.05 if p["base"]["CASH"] >= 0.05 else 0
    p["base"] = _norm(p["base"])
    p["ammessi"] = [k for k in p["base"] if k != "CASH"] + (["AZ"] if p.get("az") else [])
    return p


def simula_con_giri(g, pianificati, dal_i):
    """Come P.simula ma restituisce anche il turnover medio annuo (somma |variazione peso| / 2 per anno)."""
    al_i = len(g.date) - 1
    valore, curva, quote, scambiato = 100.0, [], {}, 0.0
    for i in range(dal_i, al_i + 1):
        if i in pianificati:
            nuovi = pianificati[i]
            tot = sum(quote.values()) or 1.0
            vecchi = {k: v / tot for k, v in quote.items()}
            s = sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi))
            scambiato += s / 2 if quote else 0
            valore *= (1 - P.COSTO * s)
            quote = {k: valore * w for k, w in nuovi.items()}
        elif quote:
            quote = {k: v * (1 + g.rend(P._ticker(k), i)) for k, v in quote.items()}
            valore = sum(quote.values())
        curva.append((g.date[i], valore))
    anni = max(0.5, (len(g.date) - dal_i) / 252)
    return curva, scambiato / anni * 100


def piano(prof, g, giorni, sc, lento=False, fissi=()):
    """{indice: pesi}. lento=True: si ribilancia solo se cambia l'insieme dei mercati attivi o ogni 3 mesi."""
    out, prec_set, ultimo_mese = {}, None, None
    for n, i in enumerate(giorni):
        pesi, _, _ = P.scegli(prof, g, i, sc)
        for k in fissi:                       # mercati SENZA filtro di trend: restano sempre in portafoglio
            w = prof["base"].get(k, 0) * (1 - prof.get("az", 0))
            if w and k not in pesi:
                pesi[k] = w
                pesi["CASH"] = max(0.0, pesi.get("CASH", 0) - w)
        insieme = frozenset(k for k in pesi if k != "CASH")
        if not lento or prec_set is None or insieme != prec_set or n % 3 == 0:
            out[i] = pesi
        prec_set = insieme
    return out


def riga(nome, curva, giri=None):
    o = P.statistiche(P._tagli(curva, dal=P.OOS_DAL))
    t = P.statistiche(curva)
    return (nome, t, o, giri)


def main():
    px = P.prezzi(scarica=None, cartella=CARTELLA)
    sat = json.load(open(SAT, encoding="utf-8")) if SAT else None
    ss = P.serie_satellite(sat, [d for d, _ in px["SPY"]])
    if ss:
        px["SAT"] = ss
    g = P.Griglia(px)
    sc = {}                                                # il COT non decide i pesi (regola v2): non serve qui
    giorni = P.date_ribilancio(g)
    print(f"Periodo {g.date[giorni[0]]} - {g.date[-1]}, {len(giorni)} ribilanciamenti, azioni scelte: {'si' if ss else 'NO (quota in liquidita)'}")
    bench = {"conservativo": .3, "moderato": .6, "aggressivo": .8}
    righe = []
    for prof in P.PROFILI:
        print(f"\n=== {prof['nome']} ===")
        az_rid = {"conservativo": .05, "moderato": .10, "aggressivo": .15}[prof["id"]]
        vs = [("A attuale", prof, False), ("B azioni ridotte", variante(prof, az=az_rid), False),
              ("C B + difesa", variante(prof, az=az_rid, difesa=True), False),
              ("D C + ribilancio lento", variante(prof, az=az_rid, difesa=True), True),
              ("E D + difesa sempre accesa", variante(prof, az=az_rid, difesa=True), True)]
        r = []
        for nome, p, lento in vs:
            fissi = ("US10Y", "GOLD") if nome.startswith("E") else ()
            c, giri = simula_con_giri(g, piano(p, g, giorni, sc, lento, fissi), giorni[0])
            r.append(riga(nome, c, giri))
        w = bench[prof["id"]]
        cb = P.simula(g, {i: {"SPY": w, "IEF": 1 - w} for i in giorni}, giorni[0])
        r.append(riga(f"Benchmark {round(w*100)}/{round((1-w)*100)}", cb))
        print(f"{'':26}{'--- tutto il periodo ---':^38}|{'--- dal 2016 (fuori campione) ---':^38}| turnover/anno")
        print(f"{'':26}{'CAGR':>7}{'Vol':>7}{'MaxDD':>8}{'CAGR/Vol':>10}   |{'CAGR':>7}{'Vol':>7}{'MaxDD':>8}{'CAGR/Vol':>10}  |")
        for nome, t, o, giri in r:
            f = lambda s: f"{s['cagr']:7.1f}{s['vol']:7.1f}{s['maxdd']:8.1f}{(s['cagr']/s['vol'] if s['vol'] else 0):10.2f}"
            print(f"{nome:26}{f(t)}   |{f(o)}  | {'' if giri is None else f'{giri:5.0f}%'}")
        righe.append((prof["id"], r))
    return righe


if __name__ == "__main__":
    main()
