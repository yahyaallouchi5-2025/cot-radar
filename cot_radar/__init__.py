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
  conferme.py    Commercials, open interest e affidabilita' storica dei segnali
  notizie.py     motore notizie: calendario CPI/NFP/Fed/BCE e sorpresa misurata dal mercato
  paracadute.py  il sito non peggiora mai: confronto con l'ultimo aggiornamento buono + esito CRITICO
  riserva.py     fonti di riserva se FRED e' fermo (Tesoro USA, NY Fed, CBOE, Freddie Mac, BCE, Coinbase)
  demo.py        dati finti per provare senza internet
  log.py         registro: schermo + dati/registro.log + riepilogo per la scheda "Registro"
  storico.py     archivio permanente dei prezzi (ramo git "storico"), mai riscritto, dati controllati
  stagionalita.py stagionalita': prossime 4 settimane, mesi, giorni della settimana + backtest del peso
  admin.py       registro riservato: sul sito cifrato con la password admin (Secret ADMIN_PASSWORD)
"""
__version__ = "6.0"
