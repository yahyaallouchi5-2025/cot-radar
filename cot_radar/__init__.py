# -*- coding: utf-8 -*-
"""
COT Radar - pacchetto Python.

Mappa dei moduli (in ordine di "viaggio" dei dati):
  config.py      impostazioni, strumenti, indirizzi delle fonti
  fonti.py       download da CFTC / FRED / BCE + copia locale (cache)
  calcoli.py     matematica di base (z-score, COT Index, regressione)
  cot.py         punteggio COT di ogni strumento
  mercato.py     punteggio "Mercato": cosa e' gia' scontato nei prezzi + liquidita' Fed
  mutui.py       tassi mutui BCE e stima dei mesi non ancora pubblicati
  analisi.py     unisce tutto: strumenti, coppie, correlazioni
  calendario.py  orari di uscita, ritardi, stato delle fonti
  pagina.py      costruisce la pagina HTML (usa i file in web/)
  controlli.py   controlli di qualita' dei dati (dati vecchi, valori impossibili, mercati spariti)
  demo.py        dati finti per provare senza internet
  log.py         registro: schermo + dati/registro.log + riepilogo per la scheda "Registro"
"""
__version__ = "4.2"
