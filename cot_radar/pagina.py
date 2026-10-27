# -*- coding: utf-8 -*-
"""
pagina.py - trasforma i risultati in UNA pagina HTML autonoma (si apre anche senza internet).

La grafica sta nella cartella web/:
  web/index.html  struttura della pagina (con i segnaposto {{CSS}} e {{JS}})
  web/stile.css   aspetto (colori, spazi, versione telefono, tema scuro)
  web/js/*.js     disegnano tabelle, schede e grafici a partire dai dati (un file per scheda)
Qui li uniamo in un solo file e ci inseriamo i dati in formato JSON (variabile D nel JavaScript).

DEBUG: nel browser premi F12 -> scheda "Console" e scrivi  D  per vedere tutti i dati della pagina.
"""
import json
import math
import os
import traceback
from datetime import datetime, timezone

from .analisi import analyse
from .calendario import sources_status
from . import __version__
from .config import (ARCHIVI_COT, ASSETS, DIVERGENCE_MIN, MACRO_WEIGHT, NORMAL, REG_WEEKS, SECTORS, STRONG,
                     FEEDBACK_CHIAVE, STATISTICHE_ID, TELEGRAM_CANALE, TV_PAIRS, TV_SYMBOLS, WEB_DIR, WEIGHTS)
from .controlli import controlla
from .cot import cot_series
from .fonti import get_cftc_tutto, get_fred, load_all, scarica_archivio
from .log import log, raccoglitore
from .mercato import fed_liquidity
from . import agenda, backtest, correlazioni, notizie, portafogli, registro, stagionalita, storico, volatilita
from .admin import pubblico


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
    # CODICE DELLA PAGINA: un file per scheda in web/js/, uniti in ordine di nome (01_base.js per primo: aiuti comuni,
    # protezione anti-crollo; poi una scheda per file). Lo script finale e' uno solo, come prima: le variabili
    # globali definite in 01_base.js valgono per tutti. Per aggiungere una scheda: nuovo file con il numero giusto.
    js = "".join(read(os.path.join("js", f)) for f in sorted(os.listdir(os.path.join(WEB_DIR, "js"))) if f.endswith(".js"))
    return read("index.html").replace("{{CSS}}", read("stile.css")).replace("{{JS}}", js) \
        .replace("{{TELEGRAM}}", TELEGRAM_CANALE).replace("{{STATISTICHE}}", statistiche()) \
        .replace("__FEEDBACK_KEY__", "".join(c for c in (os.environ.get("WEB3FORMS_KEY") or FEEDBACK_CHIAVE)
                                             if c.isalnum() or c == "-"))


def statistiche():
    """Codice delle statistiche anonime (web/statistiche.js) con il Website ID di config.STATISTICHE_ID.
    Usato dal terminale (qui sopra) e dalla landing page (vetrina.py). ID vuoto = statistiche spente."""
    with open(os.path.join(WEB_DIR, "statistiche.js"), encoding="utf-8") as f:
        js = f.read()
    sid = "".join(c for c in STATISTICHE_ID if c.isalnum() or c == "-")     # solo caratteri validi di un ID
    return js.replace("__STAT_ID__", sid)


# Dati dell'ultima dashboard creata, per la landing page (vetrina.py): segnali e numeri VERI, mai inventati.
ULTIMI = {}


def build(data_source=load_all, demo=False, sito=False):
    """Scarica (o riceve) i dati, calcola tutto e restituisce (html, stato).
    data_source si puo' sostituire: la modalita' --demo passa dati finti invece di scaricarli.
    stato = riepilogo dell'esecuzione (fonti, avvisi, errori): finisce nella scheda "Registro" e in stato.json.
    sito=True: e' l'aggiornamento ufficiale del sito, l'unico che scrive il registro live dei segnali."""
    t0 = datetime.now()
    t0_utc = datetime.now(timezone.utc)
    cache, status, errors = data_source()
    fred = cache.get("fred", {}).get("data", {}) or {}
    ecb = cache.get("ecb", {}).get("data", {}) or {}
    assets, pairs, corr, market = analyse(cache["cot"]["data"], fred, ecb)
    if not assets:
        raise RuntimeError("nessun dato COT utilizzabile")
    # la liquidita' Fed e' un "extra": se fallisce la dashboard si crea lo stesso (scheda Mutui tolta in v6.35)
    mort = None
    try:
        fed = fed_liquidity(fred)
    except Exception:
        log.warning("liquidita' Fed non calcolata:\n%s", traceback.format_exc())
        fed = None
    # AGENDA delle notizie (agenda.py): calendario automatico + reazione del mercato + segnali esposti.
    # Isolata: se fallisce il motore notizie usa il suo calendario di riserva e mancano solo gli avvisi Telegram.
    agenda_out = None
    if not demo:
        try:
            agenda_out = agenda.costruisci(fred, ecb, pairs)
            log.info("agenda notizie: %d eventi (fonte %s)", len(agenda_out["eventi"]), agenda_out["fonte"])
        except Exception:
            log.warning("agenda notizie non costruita:\n%s", traceback.format_exc())
    try:                              # motore notizie (vedi notizie.py): se fallisce mancano solo le righe "Notizie"
        news = notizie.motore(fred, ecb, calendario=agenda.calendario_motore(agenda_out))
        notizie.applica(pairs, assets, news)
    except Exception:
        log.warning("motore notizie non calcolato:\n%s", traceback.format_exc())
        news = {"prossimi": [], "valute": {}}
    # STAGIONALITA' (vedi storico.py e stagionalita.py). Isolata: se qualcosa va storto mancano solo
    # i riquadri "Stagionalita'", il resto della dashboard non cambia.
    rie_storico, stag, stag_meta, archivio = None, {}, None, {}
    try:
        if demo:
            from .demo import storico_demo
            archivio = storico_demo()
        else:
            archivio, rie_storico = storico.aggiorna(fred, scarica=get_fred,
                                                     fred_giu=status.get("fred") == "manutenzione")
        serie = cot_series(cache["cot"]["data"])
        hist = {a[0]: serie[a[1]] for a in ASSETS if a[1] in serie and a[0] in assets}
        # partenza = venerdi' di uscita del COT in uso: la stagionalita' segue il ciclo settimanale del segnale
        stag, stag_meta = stagionalita.calcola(hist, storico.prezzi_usd(archivio), pairs, assets,
                                               oggi=stagionalita.ancora_cot(assets))
        log.info("stagionalita': %d strumenti/coppie, peso dal backtest %s", len(stag), stag_meta.get("peso"))
    except Exception:
        log.warning("stagionalita' non calcolata:\n%s", traceback.format_exc())
    # VERIFICA DEI SEGNALI (vedi motore.py): registro live (registro.py) e backtest simulato (backtest.py).
    # Isolati come il resto: se falliscono manca solo la scheda "Backtest storico", la dashboard non cambia.
    prezzi = storico.prezzi_usd(archivio) if archivio else {}
    reg = bt = rie_cot = None
    righe_cot = None
    try:
        cot_data = max((a.get("date") or "" for a in assets.values()), default="") or None
        reg = registro.aggiorna(pairs, assets, prezzi, status, t0_utc, cot_data,
                                scrivi=sito and not demo)
    except Exception:
        log.error("registro segnali non calcolato:\n%s", traceback.format_exc())
    try:
        righe_cot, rie_cot = (cache["cot"]["data"], {"stato": "demo"}) if demo else \
            storico.aggiorna_cot(cache["cot"]["data"], scarica=get_cftc_tutto)
        bt = backtest.calcola(righe_cot, prezzi, con_eventi=demo) if prezzi else None
        if demo and bt:
            from datetime import date, timedelta
            bt["inizio_demo"] = (date.fromisoformat(bt["al"]) - timedelta(days=90)).isoformat()
        if demo and bt:              # DEMO: registro finto con gli ultimi 3 mesi simulati, per vedere la scheda
            ev = [e for e in bt.pop("_eventi") if (e.get("quando") or e["generato"]) >= bt["inizio_demo"]]
            reg = registro.vista(registro.concatena(ev, registro.ZERO, 0),
                                 registro.strumenti(pairs, assets, prezzi), True, True)
    except Exception:
        log.warning("backtest non calcolato:\n%s", traceback.format_exc())
    # ARCHIVI COT EXTRA (combined, TFF, Disaggregated): solo per il confronto nel backtest (confronto.py),
    # non cambiano nulla nella pagina. Ognuno isolato: se uno non arriva, gli altri e il sito vanno avanti.
    rie_extra = {}
    if not demo:
        for nome in ARCHIVI_COT:
            try:
                rie_extra[nome] = storico.aggiorna_extra(nome, scarica_archivio(nome))[1]
            except Exception:
                log.warning("archivio %s non aggiornato:\n%s", nome, traceback.format_exc())
                rie_extra[nome] = {"stato": "errore"}
    # VOLATILITA' di ogni strumento (giorni, settimane, mesi, anni, regime attuale): vedi volatilita.py
    vol = {}
    try:
        vol = volatilita.calcola(pairs, prezzi) if prezzi else {}
    except Exception:
        log.warning("volatilita' non calcolata:\n%s", traceback.format_exc())
    # PORTAFOGLI MODELLO a rotazione mensile (portafogli.py): conservativo, moderato, aggressivo.
    # Isolati come il resto: se Yahoo o il calcolo falliscono manca solo la scheda "Portafogli".
    port, px = None, None
    try:
        righe = righe_cot or cache["cot"]["data"]
        px = portafogli.prezzi_demo() if demo else portafogli.prezzi()
        # quota "Azioni scelte": satellite.json dal ramo "azioni" (GitHub) o da AZIONI_LOCALE (prova sul PC)
        sat = None
        try:
            from . import satellite
            if os.environ.get("AZIONI_LOCALE"):
                sat = satellite.leggi(os.environ["AZIONI_LOCALE"])
            elif os.environ.get("GITHUB_ACTIONS"):
                sat = satellite.leggi()
        except Exception:
            log.warning("satellite non letto:\n%s", traceback.format_exc())
        if sat is None:
            log.warning("portafogli: dati delle azioni scelte assenti, la loro quota resta in liquidita'")
        port = portafogli.calcola(righe, px, scrivi=sito and not demo, sat=sat)
        if port:
            log.info("portafogli: rotazione del %s, prossima il %s", port["rotazione"], port["prossima"])
    except Exception:
        log.error("portafogli non calcolati:\n%s", traceback.format_exc())
    if port is None and not demo:
        # calcolo fallito o prezzi assenti: resta online l'ultima scheda buona, con l'avviso di manutenzione
        port = portafogli.di_riserva()
        if port:
            log.error("portafogli: mostrata l'ultima scheda salvata (%s) con avviso di manutenzione", port.get("aggiornato"))
    # CORRELAZIONI DEI PREZZI (correlazioni.py): stessi prezzi dei portafogli + settori USA e dollaro. Isolate.
    corr_px = None
    try:
        corr_px = correlazioni.calcola(px)
    except Exception:
        log.warning("correlazioni dei prezzi non calcolate:\n%s", traceback.format_exc())
    # punteggio corretto = COT/mercato + notizie + stagionalita' (il punteggio originale resta quello mostrato nell'anello)
    for p in pairs:
        extra = ((p.get("news") or {}).get("adj") or 0) + ((p.get("stag") or {}).get("adj") or 0)
        p["corretto"] = round(p["score"] + extra, 1) if extra else None
    try:
        sources = sources_status(cache, status, errors, assets, mort, fred)
    except Exception:
        log.exception("stato delle fonti non calcolato")
        sources = []
    controlli = controlla(assets, pairs, fred, ecb, mort)        # qualita' dei dati (errori "invisibili")
    log.info("Calcolo fatto: %d strumenti, %d coppie, mercato %s", len(assets), len(pairs), "si" if market else "no")

    n_err = raccoglitore.conta("ERROR") + raccoglitore.conta("CRITICAL")
    n_warn = raccoglitore.conta("WARNING")
    stato = {
        "creato": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "durata_s": round((datetime.now() - t0).total_seconds(), 1),
        "esito": "errori" if n_err else ("avvisi" if n_warn else "ok"),
        "errori": n_err, "avvisi": n_warn, "fonti": status,
        "strumenti": len(assets), "coppie": len(pairs), "mercato": bool(market),
        "voci": raccoglitore.voci[-200:],             # ultimi avvisi/errori di questa esecuzione
        "controlli": controlli, "demo": demo, "storico": rie_storico, "archivio_cot": rie_cot, "archivi_extra": rie_extra,
    }
    meta = {"now": datetime.now().strftime("%d/%m/%Y %H:%M"), "w": WEIGHTS, "strong": STRONG, "normal": NORMAL,
            "divmin": DIVERGENCE_MIN, "mw": MACRO_WEIGHT, "regw": REG_WEEKS, "demo": demo,
            "version": __version__}
    data = {"meta": meta, "sources": sources,
            "assets": assets, "pairs": pairs, "corr": corr, "corr_px": corr_px, "market": market, "fed": fed,
            "order": [a[0] for a in ASSETS] + ["USD"], "sectors": SECTORS, "stato": pubblico(stato), "admin": "__ADMIN__", "eventi": news["prossimi"], "agenda": agenda_out,
            "stag": stag, "stag_meta": stag_meta, "reg": reg, "bt": bt, "vol": vol, "port": port,
            "tv": {k: {"s": v[0], "inv": v[1]} for k, v in TV_SYMBOLS.items()}, "tvp": TV_PAIRS}
    # "stato" pubblico = solo esito e fonti; "admin" = segnaposto che main.py sostituisce con il registro
    # completo (cifrato sul sito, in chiaro sul PC). Vedi cot_radar/admin.py
    # JSON compatto (senza spazi dopo virgole e due punti): stessa informazione, pagina piu' leggera
    # SUL SITO registro live + backtest (oltre meta' della pagina) vanno in un file a parte, letto dalla scheda
    # "Backtest storico" solo quando la si apre (web/js/13_verifica.js). main.py lo scrive accanto alla pagina.
    verifica = None
    if sito:
        verifica = clean({"reg": data.pop("reg"), "bt": data.pop("bt")})
        data["verifica"] = "verifica.json?v=" + datetime.now().strftime("%Y%m%d%H%M")
    payload = json.dumps(clean(data), ensure_ascii=False, separators=(",", ":"))
    ULTIMI.clear()
    ULTIMI.update(data=clean({"assets": assets, "pairs": pairs}), bt_dal=(bt or {}).get("dal"), bt_n=(bt or {}).get("n"),
                  demo=demo, verifica=verifica)
    # "</" dentro <script> chiuderebbe il tag per errore: lo "spezziamo" in "<\/"
    return template().replace("{{DATA}}", payload.replace("</", "<\\/")), clean(stato)


def error_page(msg):
    """Pagina mostrata quando qualcosa va storto: contiene il testo dell'errore per il debug."""
    return ("<!doctype html><meta charset='utf-8'><title>COT Radar</title>"
            "<body style='font-family:system-ui;padding:48px;max-width:760px;margin:auto;line-height:1.5'>"
            "<h1>COT Radar: non riesco a creare la dashboard</h1><p>Controlla la connessione a internet e riapri il programma. "
            "Se il problema resta, copia il testo qui sotto: indica il file e la riga dell'errore.</p>"
            f"<pre style='background:#f3f3f3;padding:16px;border-radius:8px;white-space:pre-wrap'>{msg}</pre></body>")
