# -*- coding: utf-8 -*-
"""
pagina.py - trasforma i risultati in UNA pagina HTML autonoma (si apre anche senza internet).

La grafica sta nella cartella web/:
  web/index.html  struttura della pagina (con i segnaposto {{CSS}} e {{JS}})
  web/stile.css   aspetto (colori, spazi, versione telefono, tema scuro)
  web/app.js      disegna tabelle, schede e grafici a partire dai dati
Qui li uniamo in un solo file e ci inseriamo i dati in formato JSON (variabile D nel JavaScript).

DEBUG: nel browser premi F12 -> scheda "Console" e scrivi  D  per vedere tutti i dati della pagina.
"""
import json
import math
import os
import traceback
from datetime import datetime

from .analisi import analyse
from .calendario import sources_status
from .config import (ASSETS, DIVERGENCE_MIN, MACRO_WEIGHT, NORMAL, REG_WEEKS, SECTORS, STRONG, TV_PAIRS, TV_SYMBOLS,
                     WEB_DIR, WEIGHTS)
from .controlli import controlla
from .fonti import load_all
from .log import log, raccoglitore
from .mercato import fed_liquidity
from .mutui import mortgages
from . import notizie


def clean(o):
    """JSON non accetta NaN/Infinito: li trasformiamo in null, altrimenti il JavaScript si rompe."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def template():
    """Legge i tre file di web/ e li unisce."""
    def read(name):
        with open(os.path.join(WEB_DIR, name), encoding="utf-8") as f:
            return f.read()
    return read("index.html").replace("{{CSS}}", read("stile.css")).replace("{{JS}}", read("app.js"))


def build(data_source=load_all, demo=False):
    """Scarica (o riceve) i dati, calcola tutto e restituisce (html, stato).
    data_source si puo' sostituire: la modalita' --demo passa dati finti invece di scaricarli.
    stato = riepilogo dell'esecuzione (fonti, avvisi, errori): finisce nella scheda "Registro" e in stato.json."""
    t0 = datetime.now()
    cache, status, errors = data_source()
    fred = cache.get("fred", {}).get("data", {}) or {}
    ecb = cache.get("ecb", {}).get("data", {}) or {}
    assets, pairs, corr, market = analyse(cache["cot"]["data"], fred, ecb)
    if not assets:
        raise RuntimeError("nessun dato COT utilizzabile")
    # mutui e liquidita' Fed sono "extra": se falliscono la dashboard si crea lo stesso
    try:
        mort = mortgages(ecb, fred)
    except Exception:
        log.warning("mutui non calcolati:\n%s", traceback.format_exc())
        mort = None
    try:
        fed = fed_liquidity(fred)
    except Exception:
        log.warning("liquidita' Fed non calcolata:\n%s", traceback.format_exc())
        fed = None
    try:                              # motore notizie (vedi notizie.py): se fallisce mancano solo le righe "Notizie"
        news = notizie.motore(fred, ecb)
        notizie.applica(pairs, assets, news)
    except Exception:
        log.warning("motore notizie non calcolato:\n%s", traceback.format_exc())
        news = {"prossimi": [], "valute": {}}
    try:
        sources = sources_status(cache, status, errors, assets, mort, fred)
    except Exception:
        log.exception("stato delle fonti non calcolato")
        sources = []
    controlli = controlla(assets, pairs, fred, ecb, mort)        # qualita' dei dati (errori "invisibili")
    log.info("Calcolo fatto: %d strumenti, %d coppie, mercato %s, mutui %s",
             len(assets), len(pairs), "si" if market else "no", "si" if mort else "no")

    n_err = raccoglitore.conta("ERROR") + raccoglitore.conta("CRITICAL")
    n_warn = raccoglitore.conta("WARNING")
    stato = {
        "creato": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "durata_s": round((datetime.now() - t0).total_seconds(), 1),
        "esito": "errori" if n_err else ("avvisi" if n_warn else "ok"),
        "errori": n_err, "avvisi": n_warn, "fonti": status,
        "strumenti": len(assets), "coppie": len(pairs), "mercato": bool(market), "mutui": bool(mort),
        "voci": raccoglitore.voci[-200:],             # ultimi avvisi/errori di questa esecuzione
        "controlli": controlli, "demo": demo,
    }
    meta = {"now": datetime.now().strftime("%d/%m/%Y %H:%M"), "w": WEIGHTS, "strong": STRONG, "normal": NORMAL,
            "divmin": DIVERGENCE_MIN, "mw": MACRO_WEIGHT, "regw": REG_WEEKS, "demo": demo}
    data = {"meta": meta, "sources": sources,
            "assets": assets, "pairs": pairs, "corr": corr, "market": market, "fed": fed, "mortgage": mort,
            "order": [a[0] for a in ASSETS] + ["USD"], "sectors": SECTORS, "stato": stato, "eventi": news["prossimi"],
            "tv": {k: {"s": v[0], "inv": v[1]} for k, v in TV_SYMBOLS.items()}, "tvp": TV_PAIRS}
    payload = json.dumps(clean(data), ensure_ascii=False)
    # "</" dentro <script> chiuderebbe il tag per errore: lo "spezziamo" in "<\/"
    return template().replace("{{DATA}}", payload.replace("</", "<\\/")), clean(stato)


def error_page(msg):
    """Pagina mostrata quando qualcosa va storto: contiene il testo dell'errore per il debug."""
    return ("<!doctype html><meta charset='utf-8'><title>COT Radar</title>"
            "<body style='font-family:system-ui;padding:48px;max-width:760px;margin:auto;line-height:1.5'>"
            "<h1>COT Radar: non riesco a creare la dashboard</h1><p>Controlla la connessione a internet e riapri il programma. "
            "Se il problema resta, copia il testo qui sotto: indica il file e la riga dell'errore.</p>"
            f"<pre style='background:#f3f3f3;padding:16px;border-radius:8px;white-space:pre-wrap'>{msg}</pre></body>")
