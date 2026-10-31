# -*- coding: utf-8 -*-
"""
backtest_sconto.py - BACKTEST "SCONTATO O CARO": comprare dopo un drawdown conviene davvero?

DOMANDA: quando un mercato (azione, indice, materia prima, cripto) scende del 10/20/30/40/50% dal suo
massimo, cosa e' successo NEI MESI DOPO? E oggi, ogni mercato quanto e' "scontato" rispetto alla SUA storia?

DATI (tutti gratuiti, gli stessi del sito BoardEdge):
  - azioni: chiusure di FINE MESE (Yahoo, rettificate per frazionamenti) di ~1.000 titoli
    (S&P 500, Nasdaq-100, FTSE MIB, DAX, Euro Stoxx 50, Nikkei, Hang Seng, Cina, India), dal 1962 dove c'e';
  - indice Nasdaq Composite dal 1971, petrolio WTI dal 1986, Brent dal 1987, gas naturale dal 1997,
    Bitcoin dal 2014, Ethereum dal 2016 (FRED; giornalieri ridotti a fine mese).

METODO (scelte dichiarate, per non ingannarsi):
  1. SCONTO = prezzo di fine mese / massimo delle ultime 12 chiusure mensili - 1   (ritracciamento recente,
     il caso "Amazon -20%"). Come contesto si calcola anche lo sconto dal MASSIMO STORICO.
  2. EVENTO = il primo mese in cui lo sconto arriva alla soglia (-10, -20, -30, -40, -50%). La soglia si
     "riarma" solo quando lo sconto torna sopra META' soglia (es. sopra -10% per la soglia -20%):
     cosi' uno stesso drawdown non viene contato 10 volte.
  3b. FILTRO TREND: ogni evento e' diviso in "sopra" (prezzo ancora sopra la media delle ultime 24 chiusure
      mensili: ritracciamento dentro un rialzo) e "sotto" (mercato gia' sotto la media: discesa lunga).
  3. Per ogni evento: rendimento a 3, 6, 12, 24 mesi e DRAWDOWN SUCCESSIVO (quanto e' sceso ancora nei
     12 mesi dopo l'acquisto, sulle chiusure mensili: quello vero intramese e' un po' piu' profondo).
  4. CONFRONTO ONESTO: lo stesso rendimento a 12 mesi calcolato da TUTTI i mesi dello stesso mercato
     ("comprare a caso"). Il vantaggio dello sconto = mediana eventi - mediana di tutti i mesi.
  5. PUNTEGGIO SCONTO di oggi (0-100) per ogni mercato:
       rarita'  = quanti mesi della sua storia hanno avuto uno sconto MENO profondo di oggi (percentile);
       qualita' = quanto comprare a questo livello di sconto e' andato MEGLIO di "comprare a caso" nello stesso
                  mercato (% di 12 mesi positivi dopo gli eventi contro % di tutti i mesi), 50 = uguale.
                  Con pochi eventi la % viene avvicinata a quella normale (PRIOR = 10 eventi "medi"),
                  cosi' 8 eventi su 8 positivi non diventano un 100% di fiducia;
       punteggio = 60% rarita' + 40% qualita'.  Lettura: >=80 molto scontato, 60-79 scontato,
       40-59 neutro, <40 caro (vicino ai massimi).

LIMITI DA NON DIMENTICARE:
  - BIAS DI SOPRAVVIVENZA: i titoli sono quelli quotati OGGI negli indici. Le aziende fallite dopo un -50%
    (Lehman, Enron...) non ci sono: per le SINGOLE AZIONI i risultati sono piu' belli del vero.
    Indici, materie prime e cripto non hanno questo problema (ma le cripto hanno poca storia).
  - Eventi delle azioni concentrati nelle stesse crisi (2000-02, 2008-09, 2020, 2022): non sono indipendenti.
  - Niente dividendi, costi e tasse; chiusure mensili (niente intramese).
  - E' una statistica del passato, non una previsione ne' un consiglio di investimento.

USO:  python backtest_sconto.py dati/   -> scrive risultati.json e stampa il riepilogo.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

SOGLIE = [-10, -20, -30, -40, -50]          # livelli di sconto studiati (%)
ORIZZONTI = [3, 6, 12, 24]                  # mesi dopo l'acquisto
FINESTRA_MAX = 12                           # massimo delle ultime 12 chiusure mensili = "ritracciamento recente"
MESI_MIN = 60                               # almeno 5 anni di storia per entrare nello studio
EVENTI_MIN = 5                              # sotto questa soglia la "qualita'" usa il gruppo (settore)

SETTORI = {"tech": "Tecnologia", "tlc": "Comunicazione", "cdis": "Beni voluttuari", "cstap": "Beni di prima necessita'",
           "fin": "Finanza", "salute": "Salute", "ind": "Industria", "mat": "Materiali", "ener": "Energia",
           "util": "Servizi pubblici", "imm": "Immobiliare"}            # stessi codici di indice.json
PRIOR = 10                                  # "eventi immaginari" alla media del mercato: frena i 100% su 5-8 eventi
ALTRI = {  # serie FRED: nome, gruppo
    "NASDAQCOM": ("Nasdaq Composite (indice)", "Indici"), "DCOILWTICO": ("Petrolio WTI", "Materie prime"),
    "DCOILBRENTEU": ("Petrolio Brent", "Materie prime"), "DHHNGSP": ("Gas naturale Henry Hub", "Materie prime"),
    "CBBTCUSD": ("Bitcoin", "Cripto"), "CBETHUSD": ("Ethereum", "Cripto")}


# --------------------------------------------------------------------------- caricamento dati
def serie_mensili(cartella):
    """{codice: (nome, gruppo, pd.Series di chiusure di fine mese con indice mensile)}"""
    out = {}
    idx = json.load(open(os.path.join(cartella, "indice.json")))
    info = {x["t"]: x for x in idx["titoli"]}
    for f in glob.glob(os.path.join(cartella, "titoli", "*.json")):
        d = json.load(open(f))
        if d.get("t") not in info or not d.get("m"):
            continue
        s = pd.Series([p for _, p in d["m"]], index=pd.PeriodIndex([m for m, _ in d["m"]], freq="M"), dtype=float)
        s = s[s > 0].iloc[:-1]                      # l'ultimo mese e' ancora in corso: fuori dal backtest storico
        x = info[d["t"]]
        out[d["t"]] = (x["n"], SETTORI.get(x.get("s"), "Altro"), s, x)
    for cod, (nome, gruppo) in ALTRI.items():
        f = os.path.join(cartella, cod + ".csv")
        if not os.path.exists(f):
            continue
        g = pd.read_csv(f, parse_dates=["data"]).dropna()
        g = g[g["valore"] > 0].set_index("data")["valore"]
        m = g.resample("ME").last().dropna()
        m.index = m.index.to_period("M")
        out[cod] = (nome, gruppo, m.iloc[:-1], {"t": cod, "n": nome, "p": float(g.iloc[-1])})
    return out


def pulisci(s):
    """Toglie i PICCHI ISOLATI (errori di dato): un mese +50% sui vicini che torna giu' subito (o -33% e torna su).
    Il valore sbagliato viene sostituito dalla media geometrica dei due mesi vicini. Restituisce (serie, n corretti)."""
    v = s.values.copy()
    n = 0
    for i in range(1, len(v) - 1):
        a, b, c = v[i - 1], v[i], v[i + 1]
        if (b / a > 1.5 and c / b < 1 / 1.5) or (b / a < 1 / 1.5 and c / b > 1.5):
            v[i] = (a * c) ** 0.5
            n += 1
    return pd.Series(v, index=s.index), n


# --------------------------------------------------------------------------- calcoli per una serie
def sconto(s, finestra=FINESTRA_MAX):
    """Sconto (%) dal massimo delle ultime `finestra` chiusure (finestra=None: dal massimo storico)."""
    mx = s.cummax() if finestra is None else s.rolling(finestra, min_periods=1).max()
    return (s / mx - 1) * 100


def eventi(s, sc):
    """Lista di eventi: (soglia, posizione del mese) con la regola di riarmo a meta' soglia."""
    ev = []
    v = sc.values
    for k in SOGLIE:
        armato = True
        for i, x in enumerate(v):
            if armato and x <= k:
                ev.append((k, i))
                armato = False
            elif not armato and x > k / 2:
                armato = True
    return ev


