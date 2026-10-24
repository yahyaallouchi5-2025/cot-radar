# -*- coding: utf-8 -*-
"""
eventi.py - CALENDARIO STORICO degli eventi macro USA (occupazione NFP, inflazione CPI, decisioni Fed),
usato dal backtest per capire QUANTO del drawdown arriva nei giorni di notizie (i driver di breve termine).

Dati: cot_radar/eventi_usa.csv (date ufficiali dal 1985, Fed dal 1994; vedi l'intestazione del file) piu' le date
future del calendario delle notizie (notizie.CALENDARIO). Le date passate non cambiano: il file non va aggiornato,
basta aggiornare ogni anno notizie.CALENDARIO come gia' previsto.

"Giorno con evento": ogni seduta del percorso di un trade copre l'intervallo tra la chiusura precedente e la sua
chiusura. Se un annuncio cade in quell'intervallo, quella seduta e' un "giorno con evento". Conta l'ORA:
  - i cambi FRED chiudono alle 12:00 di New York: il dato delle 8:30 entra nella chiusura dello stesso giorno,
    la Fed delle 14:00 entra in quella del giorno DOPO;
  - gli indici chiudono alle 16:00, il petrolio alle 14:30, le crypto a fine giornata UTC (circa 19-20 di NY).
LIMITE: con le sole chiusure giornaliere non si vede il picco dentro la giornata, solo il suo effetto alla chiusura.

DEBUG: python -c "from cot_radar import eventi; c=eventi.Calendario(); print(len(c.lista), c.lista[:3])"
"""
import csv
import os
from bisect import bisect_right

from .log import log

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eventi_usa.csv")
# ora di chiusura (New York) dei prezzi usati per ogni classe di strumento (vedi motore.ORARI)
CHIUSURA_ET = {"fx": 12.0, "indici": 16.0, "energia": 14.5, "crypto": 19.5}
NOMI = {"NFP USA": "NFP", "CPI USA": "CPI", "Fed (FOMC)": "FOMC"}


def carica(file=FILE):
    """[(data ISO, ora ET, nome)] ordinata: file storico + date future di notizie.CALENDARIO (solo USA)."""
    out = set()
    try:
        with open(file, encoding="utf-8") as fh:
            righe = [r for r in fh if not r.startswith("#")]
        for r in csv.DictReader(righe):
            out.add((r["data"], float(r["ora_et"]), r["evento"]))
    except (OSError, KeyError, ValueError) as e:
        log.warning("calendario eventi storico non leggibile (%s): analisi delle notizie nel backtest assente", e)
    try:
        from .notizie import CALENDARIO
        for d, hh, mm, fuso, nome, valuta, tipo in CALENDARIO:
            if fuso == "ET" and nome in NOMI:
                out.add((d, hh + mm / 60, NOMI[nome]))
    except Exception as e:                       # il calendario futuro e' un extra: mai bloccante
        log.warning("date future degli eventi non lette (%s)", e)
    return sorted(out)


class Calendario:
    """Ricerca veloce: c'e' almeno un evento tra due chiusure? (ricerca binaria su (data, ora))."""

    def __init__(self, lista=None):
        self.lista = carica() if lista is None else sorted(lista)
        self.chiavi = [(d, h) for d, h, _ in self.lista]

    def conta(self, da, a):
        """Numero di eventi con da < (data, ora) <= a; da e a sono tuple (data ISO, ora ET)."""
        return bisect_right(self.chiavi, a) - bisect_right(self.chiavi, da)

    def giorni(self, ingresso, date_percorso, cls):
        """[True/False per ogni seduta del percorso]: True se quella seduta contiene un annuncio.
        ingresso = data della chiusura d'ingresso; date_percorso = date delle chiusure successive."""
        h = CHIUSURA_ET.get(cls, 16.0)
        out, prima = [], ingresso
        for d in date_percorso:
            out.append(self.conta((prima, h), (d, h)) > 0)
            prima = d
        return out
