# -*- coding: utf-8 -*-
"""
log.py - messaggi a schermo, utili per capire cosa sta facendo il programma.

Normalmente stampa solo i passaggi principali. Con  python main.py --debug  stampa anche
i dettagli (quante righe ha scaricato ogni fonte, quanto tempo ci ha messo, ecc.).
"""
import logging
import sys

log = logging.getLogger("cot_radar")


def setup(debug=False):
    """Da chiamare una volta all'avvio. debug=True mostra anche i messaggi log.debug(...)."""
    if sys.stdout is None:                    # avvio con pythonw (avvia.pyw): non c'e' una console
        log.handlers[:] = [logging.NullHandler()]
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
    log.handlers[:] = [h]
    log.setLevel(logging.DEBUG if debug else logging.INFO)
