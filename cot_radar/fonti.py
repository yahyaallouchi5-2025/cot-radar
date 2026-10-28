# -*- coding: utf-8 -*-
"""
fonti.py - scarica i dati da CFTC, FRED e BCE e li salva in una copia locale (cache).

Regola d'oro: se un download fallisce il programma NON si ferma. Usa l'ultima copia salvata
e segnala il problema nella dashboard (riquadri di stato in alto).

DEBUG: se una fonte non arriva, lancia  python main.py --debug  e guarda le righe "FRED ..." / "BCE ...":
       vedrai quale serie fallisce e il messaggio di errore esatto.
"""
import csv
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from . import riserva
from .config import (ARCHIVI_COT, ASSETS, CACHE, CFTC_RISORSA, CFTC_URL, ECB_REQ, ECB_URL, FRED_API_URL, FRED_IDS, FRED_URL, HISTORY_WEEKS,
                     TIMEOUT)
from .log import log

DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")   # accetta "2026-10-14" (giorno) e "2026-08" (mese)


def valid_date(s):
    """True solo se s e' una data nel formato atteso. Protegge da righe "sporche" (es. una pagina web
    al posto del CSV): e' la correzione dell'errore 'time data ... does not match format'."""
    return bool(s) and bool(DATE_RE.match(s))


def http(url):
    """Scarica un indirizzo e restituisce il testo. Solleva un'eccezione se non risponde entro TIMEOUT."""
    req = urllib.request.Request(url, headers={"User-Agent": "cot-radar/4"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "ignore")


def get_cftc():
    """Report COT: una sola richiesta per tutti i mercati e tutte le settimane dello storico."""
    since = (date.today() - timedelta(weeks=HISTORY_WEEKS)).isoformat()
    codes = ",".join(f"'{a[1]}'" for a in ASSETS)
    q = {
        # chiediamo solo le colonne che ci servono: il download e' molto piu' leggero
        "$select": "report_date_as_yyyy_mm_dd,cftc_contract_market_code,open_interest_all,"
                   "noncomm_positions_long_all,noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all",
        "$where": f"cftc_contract_market_code in({codes}) AND report_date_as_yyyy_mm_dd >= '{since}'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": "50000",
    }
    rows = json.loads(http(CFTC_URL + "?" + urllib.parse.urlencode(q)))
    if not rows:
        raise RuntimeError("risposta CFTC vuota")
    return rows


def get_cftc_archivio(url, campi, inizio, pagina=50000):
    """Righe di un report CFTC (qualsiasi: Legacy, Combined, TFF, Disaggregated) per i NOSTRI mercati,
    dalla data 'inizio' in poi, scaricate a pagine da 50.000 (limite dell'API). Solo le colonne 'campi'."""
    codes = ",".join(f"'{a[1]}'" for a in ASSETS)
    righe, offset = [], 0
    while True:
        q = {
            "$select": ",".join(campi),
            "$where": f"cftc_contract_market_code in({codes}) AND report_date_as_yyyy_mm_dd >= '{inizio}'",
            "$order": "cftc_contract_market_code,report_date_as_yyyy_mm_dd", "$limit": str(pagina), "$offset": str(offset),
        }
        blocco = json.loads(http(url + "?" + urllib.parse.urlencode(q)))
        righe += blocco
        if len(blocco) < pagina:
            return righe
        offset += pagina


def get_cftc_tutto(inizio="1986-01-01", pagina=50000):
    """TUTTO lo storico COT Legacy (futures only) dei nostri mercati (dal 1986): serve UNA volta sola per creare
    l'archivio del backtest (vedi storico.aggiorna_cot). Circa 75.000 righe."""
    campi = ["report_date_as_yyyy_mm_dd", "cftc_contract_market_code", "open_interest_all",
             "noncomm_positions_long_all", "noncomm_positions_short_all", "comm_positions_long_all",
             "comm_positions_short_all"]
    return get_cftc_archivio(CFTC_URL, campi, inizio, pagina)


def scarica_archivio(nome):
    """Funzione di download per storico.aggiorna_extra: scarica(inizio) -> righe del report 'nome' di ARCHIVI_COT."""
    a = ARCHIVI_COT[nome]
    return lambda inizio: get_cftc_archivio(CFTC_RISORSA.format(id=a["id"]), a["campi"], inizio)


def get_fred(sid, since):
    """Una serie FRED -> lista ordinata [[data, valore], ...].

    Due modi:
      1) con la chiave API gratuita (variabile d'ambiente FRED_API_KEY): API ufficiale, affidabile
         anche dai server di GitHub. Su GitHub la chiave sta in Settings -> Secrets -> FRED_API_KEY.
      2) senza chiave: file CSV pubblico (va bene dal PC di casa, ma dai server cloud spesso va in timeout).
    I giorni festivi hanno "." come valore: li saltiamo."""
    key = os.environ.get("FRED_API_KEY", "").strip().strip('"').strip("'")
    if key.upper().startswith("FRED_API_KEY="):      # chiave incollata insieme al suo nome: la ripuliamo
        key = key.split("=", 1)[1].strip()
    out = []
    if key:
        q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json", "observation_start": since})
        text = http(FRED_API_URL + "?" + q)
        if "Site Maintenance" in text[:600]:
            raise RuntimeError("FRED e' in manutenzione (pagina 'Site Maintenance'): riprovare piu' tardi")
        try:
            data = json.loads(text)
        except ValueError:
            raise RuntimeError("l'API FRED non ha risposto con dati JSON (inizio risposta: %r)" % text[:80])
        for o in data.get("observations", []):
            if valid_date(o.get("date", "")):
                try:
                    out.append([o["date"], float(o["value"]) * FRED_IDS[sid]])
                except (ValueError, KeyError):
                    pass
    else:
        text = http(FRED_URL.format(sid=sid, since=since))
        for line in text.splitlines():
            p = [x.strip().strip('"') for x in line.split(",")]
            if len(p) >= 2 and len(p[0]) == 10 and valid_date(p[0]):   # scarta intestazione e righe non valide
                try:
                    out.append([p[0], float(p[1]) * FRED_IDS[sid]])
                except ValueError:
                    pass
        if not out and "Site Maintenance" in text[:600]:
            raise RuntimeError("FRED e' in manutenzione (pagina 'Site Maintenance'): riprovare piu' tardi")
        if not out and "<" in text[:300]:
            raise RuntimeError("FRED ha risposto con una pagina web invece dei dati")
    if not out:
        raise RuntimeError("FRED non ha restituito dati")
    return sorted(out)


ECB_RIPROVA = 4                 # secondi di attesa prima dell'UNICO nuovo tentativo verso la BCE


def _temporaneo(e):
    """True se l'errore e' passeggero: risposta 5xx del server (es. 504 Gateway Time-out) o tempo scaduto.
    Errori 4xx (serie sbagliata, richiesta rifiutata) NON si riprovano: ripetere non servirebbe."""
    import socket
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        return 500 <= e.code < 600
    if isinstance(e, urllib.error.URLError):
        return isinstance(e.reason, (socket.timeout, TimeoutError)) or "timed out" in str(e.reason)
    return isinstance(e, (socket.timeout, TimeoutError))


def get_ecb(flow, key, since):
    """Una richiesta BCE -> {chiave_serie: [[periodo, valore], ...]} (una richiesta puo' contenere piu' serie).
    Il servizio dati della BCE ogni tanto risponde "504 Gateway Time-out" quando e' carico: in quel caso (e solo per
    errori temporanei) si riprova UNA volta dopo ECB_RIPROVA secondi, poi si rinuncia e si usano i dati salvati."""
    url = ECB_URL.format(flow=flow, key=key, since=since)
    try:
        text = http(url)
    except Exception as e:                           # noqa: BLE001 - si decide qui se vale la pena riprovare
        if not _temporaneo(e):
            raise
        log.info("BCE %s.%s: errore temporaneo (%s), riprovo una volta tra %d s", flow, key, e, ECB_RIPROVA)
        time.sleep(ECB_RIPROVA)
        text = http(url)
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        try:
            v = float(r["OBS_VALUE"])
        except (KeyError, ValueError, TypeError):
            continue
        if not valid_date((r.get("TIME_PERIOD") or "").strip()):
            continue
        k = r.get("KEY") or f"{flow}.{key}"
        out.setdefault(k, []).append([r["TIME_PERIOD"], v])
    if not out:
        raise RuntimeError("nessun dato")
    for v in out.values():
        v.sort()
    return out


def _read_cache():
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:                       # cache rovinata: si riparte da zero
            log.warning("cache illeggibile (%s), la ricreo", e)
    return {}


def load_all():
    """Scarica tutto IN PARALLELO (10 download alla volta) e aggiorna la cache.

    Restituisce (cache, status, errors):
      cache  = {"cot": {...}, "fred": {"saved": ..., "data": {serie: punti}}, "ecb": {...}}
      status = per gruppo: "online" (tutto ok), "parziale", "cache" (uso la copia salvata), "assente",
               "manutenzione" (solo FRED: sito fermo per lavori, nessun altro tentativo)
      errors = messaggi di errore per gruppo, mostrati nella dashboard
    """
    t0 = time.time()
    cache = _read_cache()
    since = (date.today() - timedelta(weeks=HISTORY_WEEKS + 10)).isoformat()
    since_ecb = (date.today() - timedelta(days=365 * 7)).isoformat()[:7]
    now = datetime.now().isoformat(timespec="minutes")
    status, errors = {}, {}

    with ThreadPoolExecutor(max_workers=10) as ex:
        # 1) lancio tutti i download insieme ...
        f_cot = ex.submit(get_cftc)
        # FRED: al massimo 4 richieste alla volta (pool separato), per non farsi rallentare dal server
        f_ecb = [(fl, k, ex.submit(get_ecb, fl, k, since_ecb)) for fl, k in ECB_REQ]
        fred_pool = ThreadPoolExecutor(max_workers=4)
        # "Sonda": scarico PRIMA una sola serie. Se FRED e' in manutenzione non insistiamo con le altre
        # (sarebbero solo richieste inutili): usiamo la copia salvata e il controllo orario su GitHub
        # (job "sonda" in sito.yml) rilancera' l'aggiornamento da solo appena FRED torna online.
        ids = list(FRED_IDS)
        f_fred = {ids[0]: fred_pool.submit(get_fred, ids[0], since)}
        fred_manut = False
        try:
            f_fred[ids[0]].result()
        except Exception as e:
            fred_manut = "manutenzione" in str(e)
        if fred_manut:
            log.warning("FRED in manutenzione: %d serie rinviate, uso fonti alternative e ultimi dati disponibili",
                        len(ids) - 1)
        else:
            f_fred.update({sid: fred_pool.submit(get_fred, sid, since) for sid in ids[1:]})

        # 2) ... poi raccolgo i risultati uno per uno. .result() "rilancia" l'eventuale errore del download.
        try:
            cache["cot"] = {"saved": now, "data": f_cot.result()}
            status["cot"] = "online"
            log.debug("CFTC: %d righe", len(cache["cot"]["data"]))
        except Exception as e:
            errors["cot"] = str(e) or type(e).__name__
            status["cot"] = "cache" if "cot" in cache else "assente"
            log.warning("CFTC non scaricato: %s", errors["cot"])

        fred = cache.get("fred", {"saved": None, "data": {}})
        ok = bad = 0
        for sid, fu in f_fred.items():
            try:
                fred["data"][sid] = fu.result()
                ok += 1
                log.debug("FRED %-14s %5d punti, ultimo %s", sid, len(fred["data"][sid]), fred["data"][sid][-1][0])
            except Exception as e:
                bad += 1
                errors.setdefault("fred", []).append(f"{sid}: {e}")
                if not fred_manut:                    # in manutenzione il messaggio e' gia' stato scritto sopra
                    log.warning("FRED %s non scaricato: %s", sid, e)
        fred_pool.shutdown()
        # Serie FRED non arrivate -> le chiediamo alle FONTI DI RISERVA (Tesoro USA, NY Fed, BCE...: vedi riserva.py).
        # Si aggiungono alla copia salvata solo i giorni NUOVI: dove abbiamo gia' il dato FRED, teniamo quello.
        mancanti = [sid for sid in FRED_IDS if sid not in f_fred or f_fred[sid].exception() is not None]
        if mancanti:
            dati_r, err_r = riserva.scarica(mancanti, since, http, get_ecb)
            for sid, punti in dati_r.items():
                vecchi = fred["data"].get(sid) or []
                ultimo = vecchi[-1][0] if vecchi else ""
                nuovi = [[d, v * FRED_IDS[sid]] for d, v in punti if d > ultimo]
                fred["data"][sid] = vecchi + nuovi
            status["fred_riserva"] = len(dati_r)
            if err_r:
                errors["riserva"] = [f"{k}: {v}" for k, v in err_r.items()]
            log.info("FRED: %d serie mancanti, %d recuperate dalle fonti di riserva", len(mancanti), len(dati_r))
        if ok:
            fred["saved"] = now
        cache["fred"] = fred
        if fred_manut:
            status["fred"] = "manutenzione"
        else:
            status["fred"] = "online" if bad == 0 else ("parziale" if ok else ("cache" if fred["data"] else "assente"))

        ecb = cache.get("ecb", {"saved": None, "data": {}})
        ok = bad = 0
        for fl, k, fu in f_ecb:
            try:
                res = fu.result()
                ecb["data"].update(res)
                ok += 1
                log.debug("BCE %s/%s: %d serie", fl, k, len(res))
            except Exception as e:
                bad += 1
                errors.setdefault("ecb", []).append(f"{fl}/{k}: {e}")
                log.warning("BCE %s/%s non scaricato: %s", fl, k, e)
        if ok:
            ecb["saved"] = now
        cache["ecb"] = ecb
        status["ecb"] = "online" if bad == 0 else ("parziale" if ok else ("cache" if ecb["data"] else "assente"))

    # pulizia: elimina righe non valide eventualmente salvate da versioni precedenti del programma
    for grp in ("fred", "ecb"):
        dat = cache.get(grp, {}).get("data", {})
        for k in list(dat):
            dat[k] = sorted(p for p in dat[k] if isinstance(p, list) and len(p) == 2 and valid_date(str(p[0])))
            if not dat[k]:
                del dat[k]

    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception as e:
        log.warning("impossibile salvare la cache: %s", e)

    log.info("Download completati in %.1f s (CFTC %s, FRED %s, BCE %s)", time.time() - t0,
             status["cot"], status["fred"], status["ecb"])
    if "cot" not in cache:
        raise RuntimeError("Nessun dato COT disponibile (ne' online ne' salvato): " + errors.get("cot", ""))
    return cache, status, errors
