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
  motore.py      motore unico dei segnali (nascita, conferme, chiusura, misura, statistiche)
  registro.py    registro LIVE dei segnali: immutabile, con catena di hash
  backtest.py    backtest storico (simulato) con lo stesso motore, dal 1986, con holdout
  volatilita.py  natura di ogni mercato: volatilita' per giorno, settimana, mese, anno e regime attuale
  confronto.py   backtest delle letture COT alternative (opzioni, TFF, Disaggregated): NON entra nel sito
  eventi.py      calendario storico degli annunci macro USA (NFP, CPI, Fed) per lo studio del drawdown
  notifiche.py   avvisi dei segnali: canale Telegram per gli iscritti + copia e-mail all'admin (cursore anti-doppioni)
  agenda.py      agenda notizie: calendario automatico (financecalendar.com) + reazione del mercato + segnali esposti
  avvisi.py      avvisi Telegram sulle notizie: "in arrivo" (sera prima) ed "esito" (appena il mercato ha reagito)
  web/statistiche.js  statistiche di visita anonime senza cookie (Umami): visite e click, spente se manca l'ID
  vetrina.py     landing page del sito (radice) con i numeri veri; il terminale sta in /terminale/
  riepilogo.py   riepilogo settimanale dei segnali per categoria di asset (Telegram), dai dati della pagina online
"""
__version__ = "6.22"
