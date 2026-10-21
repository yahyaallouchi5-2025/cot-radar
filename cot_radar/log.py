# -*- coding: utf-8 -*-
"""
log.py - REGISTRO di monitoraggio: messaggi a schermo + file + riepilogo per la dashboard.

Livelli (dal meno al piu' grave):
  DEBUG     dettagli tecnici (solo con --debug a schermo, sempre nel file)
  INFO      passaggi normali ("download completati", "pagina creata")
  WARNING   qualcosa non va ma il programma continua (una serie non arriva, dati vecchi)
  ERROR     una parte non funziona (es. modello di mercato non calcolato) ma la dashboard si crea
  CRITICAL  la dashboard NON si puo' creare

Dove finiscono i messaggi:
  1. a schermo (console o log di GitHub Actions)
  2. nel file  dati/registro.log  (a rotazione: max 1 MB x 3 file, i piu' vecchi si cancellano da soli)
  3. in memoria (Raccoglitore): avvisi ed errori di QUESTA esecuzione finiscono nella scheda "Registro"
     della dashboard e nel file stato.json

SICUREZZA: un filtro sostituisce con *** qualsiasi chiave API (es. FRED_API_KEY) prima di scriverla ovunque.
"""
import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

log = logging.getLogger("cot_radar")
FORMATO = "%(asctime)s  %(levelname)-8s %(module)-10s %(message)s"


class Oscura(logging.Filter):
    """Toglie dai messaggi le chiavi segrete: 'api_key=abc123' -> 'api_key=***' e il valore di FRED_API_KEY."""
    PATTERN = re.compile(r"(api_key=)[^&\s'\"]+", re.I)

    def filter(self, record):
        msg = record.getMessage()
        msg = self.PATTERN.sub(r"\1***", msg)
        key = os.environ.get("FRED_API_KEY", "").strip()
        if len(key) >= 8:
            msg = msg.replace(key, "***")
        record.msg, record.args = msg, ()          # il messaggio "pulito" sostituisce l'originale
        return True


class Raccoglitore(logging.Handler):
    """Tiene in memoria gli avvisi/errori di questa esecuzione per mostrarli nella dashboard."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.voci = []

    def emit(self, record):
        self.voci.append({"ora": self.formatTime(record, "%H:%M:%S") if hasattr(self, "formatTime") else "",
                          "livello": record.levelname, "modulo": record.module, "messaggio": record.getMessage()})

    def formatTime(self, record, fmt):
        return logging.Formatter().formatTime(record, fmt)

    def conta(self, livello):
        return sum(1 for v in self.voci if v["livello"] == livello)


raccoglitore = Raccoglitore()


def setup(debug=False, file_registro=None):
    """Da chiamare una volta all'avvio.
    debug=True: a schermo anche i DEBUG. file_registro: percorso del file (None = nessun file)."""
    log.handlers[:] = []
    log.filters[:] = [Oscura()]
    log.setLevel(logging.DEBUG)                     # il logger lascia passare tutto, filtrano i "gestori"
    raccoglitore.voci = []
    log.addHandler(raccoglitore)

    if sys.stdout is not None:                      # con pythonw (avvia.pyw) non c'e' una console
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s %(message)s", "%H:%M:%S"))
        h.setLevel(logging.DEBUG if debug else logging.INFO)
        log.addHandler(h)

    if file_registro:
        try:
            os.makedirs(os.path.dirname(file_registro), exist_ok=True)
            f = RotatingFileHandler(file_registro, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
            f.setFormatter(logging.Formatter(FORMATO, "%Y-%m-%d %H:%M:%S"))
            f.setLevel(logging.DEBUG)               # nel file finisce tutto, anche il dettaglio
            log.addHandler(f)
        except Exception as e:                      # il registro non deve MAI bloccare il programma
            print("Impossibile aprire il file di registro:", e)
