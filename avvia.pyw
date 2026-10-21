# -*- coding: utf-8 -*-
# avvia.pyw - doppio clic su Windows: aggiorna e apre la dashboard SENZA la finestra nera.
# (i file .pyw vengono aperti da "pythonw", che non mostra la console)
# Se qualcosa va storto, la pagina che si apre contiene il messaggio d'errore.
import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.argv = [os.path.join(here, "main.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
