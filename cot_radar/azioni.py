# -*- coding: utf-8 -*-
"""
azioni.py - SCHEDA AZIONI: ~630 titoli dei listini principali, divisi per settore, con prezzi Yahoo Finance.

LISTINI: S&P 500, Nasdaq-100, FTSE MIB, DAX 40, Euro Stoxx 50 (+ i 5 indici come riferimento).
  L'elenco dei titoli con settore (classificazione GICS, 11 settori) e listini e' in cot_radar/azioni_elenco.csv:
  Yahoo da GitHub Actions non concede il profilo aziendale (settore), quindi l'elenco e' fisso e va aggiornato a
  ogni ribilanciamento trimestrale degli indici. Il NOME del titolo invece arriva da Yahoo a ogni download.

FLUSSO GIORNALIERO (workflow .github/workflows/azioni.yml, dopo la chiusura USA, separato dal sito):
  1. per ogni titolo: ultimi 2 anni giornalieri (prezzi rettificati) -> 1 richiesta;
     una volta a settimana per titolo (giorno scelto dal ticker, cosi' il carico si spalma) anche lo storico
     MENSILE completo per la stagionalita' -> 1 richiesta in piu';
  2. ogni richiesta: fino a 3 tentativi (pausa 2 s, poi 6 s). 5 titoli falliti di fila = Yahoo fermo:
     niente altre richieste in questo giro, restano le copie di ieri;
  3. le copie grezze stanno in <cartella>/grezzi/ (ramo git "azioni", riscritto ogni giorno senza storia:
     non si gonfia mai). Un titolo che non si aggiorna tiene la sua copia: la pagina non salta;
  4. si scrivono i file per il sito in <cartella>/pubblico/: indice.json (tutti i titoli con i numeri della
     tabella, ~200 KB) e titoli/<TICKER>.json (grafico e stagionalita', caricato solo quando si apre il titolo);
  5. ANOMALIA: se Yahoo e' fermo o fallisce oltre il 10% dei titoli -> indice.json riporta {codice, quando}:
     l'utente vede un popup "manutenzione in corso" (una volta per sessione), il workflow fallisce apposta e
     GitHub manda la mail all'admin. I titoli singoli che falliscono (es. appena tolti dal listino) finiscono
     solo nel registro.

USO: python -m cot_radar.azioni <cartella>        (es. dati_azioni; --prova = solo 12 titoli)
"""
import csv
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
import zlib
from datetime import date, datetime, timedelta, timezone

from .log import log

QUI = os.path.dirname(os.path.abspath(__file__))
ELENCO = os.path.join(QUI, "azioni_elenco.csv")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?{q}"
TENTATIVI = 3                  # tentativi per richiesta
DI_FILA = 5                    # fallimenti consecutivi oltre i quali Yahoo e' considerato fermo
SOGLIA_ANOMALIA = 0.10         # quota di titoli falliti oltre la quale scatta l'avviso di manutenzione
PAUSA = 0.35                   # secondi tra una richiesta e l'altra (gentili con Yahoo)
CODICE_ERRORE = "503"
CHIUSURA_UTC = "21:00"         # dopo quest'ora (UTC) i prezzi del giorno sono definitivi anche per Wall Street

SETTORI = [  # id, nome, ETF di riferimento USA (SPDR)
    ("tech", "Tecnologia", "XLK"), ("tlc", "Comunicazione", "XLC"), ("cdis", "Beni voluttuari", "XLY"),
    ("cstap", "Beni di prima necessità", "XLP"), ("salute", "Salute", "XLV"), ("fin", "Finanza", "XLF"),
    ("ind", "Industria", "XLI"), ("mat", "Materiali", "XLB"), ("ener", "Energia", "XLE"),
    ("util", "Servizi pubblici", "XLU"), ("imm", "Immobiliare", "XLRE"),
]
LISTINI = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "mib": "FTSE MIB", "dax": "DAX 40", "sx5e": "Euro Stoxx 50",
           "n225": "Nikkei 225", "hsi": "Hang Seng", "sse50": "SSE 50 Cina", "nifty": "Nifty 50 India"}
INDICI = [("^GSPC", "S&P 500", "sp500"), ("^NDX", "Nasdaq-100", "ndx"), ("FTSEMIB.MI", "FTSE MIB", "mib"),
          ("^GDAXI", "DAX 40", "dax"), ("^STOXX50E", "Euro Stoxx 50", "sx5e"), ("^N225", "Nikkei 225", "n225"),
          ("^HSI", "Hang Seng", "hsi"), ("000001.SS", "Shanghai Composite", "sse50"), ("^NSEI", "Nifty 50", "nifty")]

# PUNTEGGIO di ogni titolo (0-100), ricalcolato ogni sera: media pesata dei PERCENTILI tra tutti i titoli
# (cosi' valute e mercati diversi sono confrontabili). Forza = momento + trend + stagionalita' del mese in corso.
PESI = {"v1a": 0.30, "v3m": 0.20, "t200": 0.15, "st_media": 0.20, "st_pos": 0.15}
MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
           "novembre", "dicembre"]
TOP_N = 5                      # titoli nella vetrina della Dashboard (al massimo 1 per settore)
MIN_ANNI_STAG = 8              # anni minimi di storico mensile perche' la stagionalita' conti


def ora_italia():
    """Data e ora italiane (per il messaggio d'anomalia), con ripiego su UTC."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now(timezone.utc)


def elenco(percorso=ELENCO):
    """[{t, nome, s (settore), l [listini]}] dal CSV (le righe che iniziano con # sono commenti)."""
    with open(percorso, encoding="utf-8") as f:
        righe = [r for r in f if r.strip() and not r.startswith("#")]
    return [{"t": r["ticker"], "nome": r["nome"], "s": r["settore"], "l": r["listini"].split(",")}
            for r in csv.DictReader(righe, delimiter=";")]


# --------------------------------------------------------------------------- download
def _valida(pts, min_punti=20):
    """Serie plausibile: abbastanza punti, date crescenti, nessun salto fra -75% e +300% (= dato rotto)."""
    if not pts or len(pts) < min_punti:
        return None
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d1 <= d0 or not (0.25 < v1 / v0 < 4):
            return None
    return pts


def scarica(ticker, intervallo="1d", periodo="2y", timeout=20, tentativi=TENTATIVI, attesa=2):
    """({meta}, [(data, prezzo rettificato)]) da Yahoo, oppure None dopo `tentativi` prove fallite.
    meta = nome, valuta, borsa (dal grafico: nessun cookie o crumb richiesto)."""
    # ATTENZIONE: con range=max Yahoo "comprime" gli storici lunghi (es. Apple dal 1980) in barre TRIMESTRALI anche se
    # si chiede interval=1mo. Con l'intervallo esplicito period1/period2 rispetta invece la granularita' mensile.
    if periodo == "max":
        q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": intervallo,
                                    "includeAdjustedClose": "true", "events": "div,split"})
    else:
        q = urllib.parse.urlencode({"range": periodo, "interval": intervallo, "includeAdjustedClose": "true",
                                    "events": "div,split"})
    for n in range(tentativi):
        try:
            req = urllib.request.Request(YAHOO.format(t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/azioni"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)["chart"]["result"][0]
            m = res["meta"]
            off = m.get("gmtoffset", 0)
            ind = res["indicators"]
            valori = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
            out = {}
            for ts, v in zip(res.get("timestamp") or [], valori):
                if v is not None and v > 0:
                    d = datetime.fromtimestamp(ts + off, tz=timezone.utc).date().isoformat()
                    out[d[:7] if intervallo == "1mo" else d] = round(float(v), 4)
            pts = _valida(sorted(out.items()), 12 if intervallo == "1mo" else 20)
            if pts and intervallo == "1mo" and not mensile_ok(pts):
                log.warning("Yahoo %s: storico mensile non mensile (granularita' %s)", ticker, m.get("dataGranularity"))
                pts = None
            if pts:
                return {"nome": m.get("longName") or m.get("shortName"), "valuta": m.get("currency"),
                        "borsa": m.get("fullExchangeName") or m.get("exchangeName")}, pts
            # Risposta arrivata ma inutilizzabile: per lo storico MENSILE e' sempre la stessa (titolo quotato da poco o con
            # buchi), quindi riprovare e' solo tempo perso -> ci si ferma subito e aggiorna() usa i prezzi giornalieri.
            if intervallo == "1mo":
                log.info("Yahoo %s: storico mensile non utilizzabile, uso i prezzi giornalieri", ticker)
                return None
            log.warning("Yahoo %s (%s): risposta incompleta o anomala (tentativo %d/%d)", ticker, intervallo, n + 1, tentativi)
        except Exception as e:
            log.warning("Yahoo %s (%s): %s (tentativo %d/%d)", ticker, intervallo, getattr(e, "code", type(e).__name__),
                        n + 1, tentativi)
        if n + 1 < tentativi and attesa:
            time.sleep(attesa * (3 ** n))
    return None


def _mesi(x):
    """'AAAA-MM' -> numero progressivo del mese (per misurare la distanza tra due barre)."""
    return int(x[:4]) * 12 + int(x[5:7])


def mensile_da_giornaliero(d):
    """[(AAAA-MM-GG, prezzo)] -> [(AAAA-MM, ultimo prezzo del mese)]: storico mensile di riserva (copre solo gli anni
    dei prezzi giornalieri, ma basta per i titoli quotati da poco, che uno storico lungo non ce l'hanno comunque)."""
    m = {}
    for g, v in d or []:
        m[g[:7]] = v
    return sorted(m.items())


def mensile_ok(m):
    """True se lo storico [(AAAA-MM, prezzo)] e' davvero MENSILE: almeno il 90% delle barre consecutive dista 1 mese
    (le copie vecchie scaricate con range=max possono essere trimestrali: vanno riscaricate)."""
    if not m or len(m) < 3:
        return False
    salti = [_mesi(b[0]) - _mesi(a[0]) for a, b in zip(m, m[1:])]
    return sum(s == 1 for s in salti) >= 0.9 * len(salti)


def _nome_file(t):
    return t.replace("^", "_").replace("/", "_")


def _leggi(f):
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _scrivi(f, dati):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(dati, fh, separators=(",", ":"), ensure_ascii=False)
    os.replace(f + ".tmp", f)


def giorno_mensile(t):
    """Giorno della settimana (0-4) in cui il titolo riscarica lo storico mensile: sparso sui 5 giorni."""
    return zlib.crc32(t.encode()) % 5


def aggiorna(cartella, titoli=None, oggi=None, scarica=scarica, pausa=PAUSA):
    """Aggiorna le copie grezze (cartella/grezzi/<T>.json). Restituisce lo stato del giro:
    {quando, ok, copia [titoli rimasti alla copia], falliti [senza nessun dato], fermo (Yahoo giu'), anomalia}."""
    oggi = oggi or date.today()
    titoli = titoli if titoli is not None else [x["t"] for x in elenco()] + [i[0] for i in INDICI]
    stato = {"quando": ora_italia().strftime("%Y-%m-%d %H:%M"), "ok": 0, "copia": [], "falliti": [], "fermo": False}
    di_fila = 0
    for t in titoli:
        f = os.path.join(cartella, "grezzi", _nome_file(t) + ".json")
        vecchio = _leggi(f) or {}
        # gia' aggiornato DOPO la chiusura USA di oggi (giro ripetuto): niente nuove richieste.
        # Un aggiornamento fatto durante la seduta (prezzi provvisori) invece si ripete la sera.
        if vecchio.get("agg") == oggi.isoformat() and vecchio.get("agg_ora", "") >= CHIUSURA_UTC:
            stato["ok"] += 1
            continue
        nuovo = None
        if di_fila < DI_FILA:
            nuovo = scarica(t)
            if pausa:
                time.sleep(pausa)
        if nuovo:
            di_fila = 0
            meta, d = nuovo
            rec = dict(vecchio, t=t, agg=oggi.isoformat(), agg_ora=datetime.now(timezone.utc).strftime("%H:%M"), d=d,
                       **{k: v for k, v in meta.items() if v})
            # storico mensile: nel giorno del titolo (al massimo una volta a settimana) o se e' vecchio di oltre 10 giorni.
            # Se Yahoo non da' uno storico mensile valido, si ricava dai prezzi giornalieri (ultimo prezzo di ogni mese)
            # e si segna la data lo stesso: cosi' NON si richiede di nuovo ogni sera (prima ~3 tentativi a vuoto al giorno).
            vecchio_m = vecchio.get("agg_m", "")
            if (oggi.weekday() == giorno_mensile(t) and vecchio_m < (oggi - timedelta(days=3)).isoformat()) \
                    or vecchio_m < (oggi - timedelta(days=10)).isoformat():
                mm = scarica(t, "1mo", "max")
                if pausa:
                    time.sleep(pausa)
                if mm:
                    rec["m"], rec["agg_m"] = mm[1], oggi.isoformat()
                else:
                    if not mensile_ok(vecchio.get("m")):
                        rec["m"] = mensile_da_giornaliero(d)
                    rec["agg_m"] = oggi.isoformat()
            _scrivi(f, rec)
            stato["ok"] += 1
        else:
            di_fila += 1
            (stato["copia"] if vecchio.get("d") else stato["falliti"]).append(t)
    stato["fermo"] = di_fila >= DI_FILA
    mancati = len(stato["copia"]) + len(stato["falliti"])
    stato["anomalia"] = None
    if stato["fermo"] or (titoli and mancati / len(titoli) > SOGLIA_ANOMALIA):
        stato["anomalia"] = {"codice": CODICE_ERRORE, "quando": stato["quando"]}
        log.error("azioni: aggiornamento non riuscito (%s): %d titoli non aggiornati su %d%s",
                  stato["quando"], mancati, len(titoli), ", Yahoo fermo" if stato["fermo"] else "")
    elif mancati:
        log.warning("azioni: %d titoli non aggiornati (restano le copie): %s", mancati,
                    ", ".join((stato["copia"] + stato["falliti"])[:30]))
    return stato


# --------------------------------------------------------------------------- calcoli per il sito
def _var(d, giorni):
    """Variazione % dall'ultimo prezzo a quello di `giorni` di calendario prima (o il primo disponibile dopo)."""
    if len(d) < 2:
        return None
    lim = (date.fromisoformat(d[-1][0]) - timedelta(days=giorni)).isoformat()
    base = next((v for x, v in reversed(d) if x <= lim), None)
    return round((d[-1][1] / base - 1) * 100, 1) if base else None


def riassunto(rec):
    """Numeri della tabella per un titolo: prezzo, variazioni, distanza dal massimo a 52 settimane, trend rispetto
    alla media a 200 giorni e mini grafico (1 punto a settimana, scala 0-99)."""
    d = rec.get("d") or []
    if len(d) < 2:
        return None
    ult = d[-1][0]
    inizio_anno = next((v for x, v in reversed(d) if x < ult[:4] + "-01-01"), None)
    anno = [v for x, v in d if x >= (date.fromisoformat(ult) - timedelta(days=365)).isoformat()]
    sma = sum(v for _, v in d[-200:]) / len(d[-200:]) if len(d) >= 200 else None
    sett, ultima = [], None
    for x, v in d:
        if x >= (date.fromisoformat(ult) - timedelta(days=365)).isoformat():
            k = date.fromisoformat(x).isocalendar()[:2]
            if k != ultima:
                sett.append(v)
                ultima = k
            else:
                sett[-1] = v
    lo, hi = min(sett), max(sett)
    return {"p": d[-1][1], "data": ult, "v1g": round((d[-1][1] / d[-2][1] - 1) * 100, 2),
            "v1s": _var(d, 7), "v1m": _var(d, 30), "v3m": _var(d, 91),
            "vytd": round((d[-1][1] / inizio_anno - 1) * 100, 1) if inizio_anno else None, "v1a": _var(d, 365),
            "dmax": round((d[-1][1] / max(anno) - 1) * 100, 1) if anno else None,
            "t200": round((d[-1][1] / sma - 1) * 100, 1) if sma else None,
            "sp": [round((v - lo) / (hi - lo) * 99) if hi > lo else 50 for v in sett]}


def stagionalita(m):
    """Stagionalita' mensile dallo storico mensile [(AAAA-MM, prezzo)]: per ogni mese di calendario rendimento
    medio, mediano, % di anni positivi e numero di anni. Il mese in corso (incompleto) e' escluso."""
    if not m or len(m) < 13:
        return None
    corrente = ora_italia().strftime("%Y-%m")
    r = {}
    # le barre mensili di Yahoo portano la chiusura di FINE mese: rendimento del mese b = chiusura b / chiusura a
    for (a, va), (b, vb) in zip(m, m[1:]):
        if b >= corrente:            # mese in corso: non ancora chiuso
            break
        if _mesi(b) - _mesi(a) != 1:  # buco o barra trimestrale: non e' il rendimento di UN mese, si salta
            continue
        r.setdefault(int(b[5:]), []).append(vb / va - 1)
    out = []
    for mese in range(1, 13):
        x = sorted(r.get(mese, []))
        if not x:
            out.append(None)
            continue
        med = x[len(x) // 2] if len(x) % 2 else (x[len(x) // 2 - 1] + x[len(x) // 2]) / 2
        out.append({"media": round(sum(x) / len(x) * 100, 2), "mediana": round(med * 100, 2),
                    "pos": round(100 * sum(v > 0 for v in x) / len(x)), "n": len(x)})
    return {"dal": m[0][0][:4], "mesi": out}


def pubblica(cartella, stato=None, titoli=None):
    """Scrive cartella/pubblico/: indice.json (tutti i titoli + indici + settori) e titoli/<T>.json.
    Usa SOLO le copie grezze: se oggi Yahoo non ha risposto, la scheda mostra gli ultimi dati con l'avviso."""
    el = titoli if titoli is not None else elenco()
    righe, dettagli, mensili = [], 0, {}
    for x in el:
        rec = _leggi(os.path.join(cartella, "grezzi", _nome_file(x["t"]) + ".json"))
        r = riassunto(rec) if rec else None
        if not r:
            continue
        stag = stagionalita(rec.get("m"))
        mese = (stag or {}).get("mesi", [None] * 12)[ora_italia().month - 1] if stag else None
        righe.append(dict({"t": x["t"], "n": rec.get("nome") or x["nome"], "s": x["s"], "l": x["l"],
                           "val": rec.get("valuta"), "st_media": mese and mese["media"], "st_pos": mese and mese["pos"],
                           "st_n": mese and mese["n"]}, **r))
        det = {"t": x["t"], "n": rec.get("nome") or x["nome"], "s": x["s"], "l": x["l"], "val": rec.get("valuta"),
               "borsa": rec.get("borsa"), "d": rec["d"], "m": rec.get("m") or [], "stag": stag}
        _scrivi(os.path.join(cartella, "pubblico", "titoli", _nome_file(x["t"]) + ".json"), det)
        mensili[x["t"]] = [v for _, v in (rec.get("m") or [])[:-1]]   # SMART DISCOUNT: solo mesi chiusi
        dettagli += 1
    indici = []
    for t, nome, l in INDICI:
        rec = _leggi(os.path.join(cartella, "grezzi", _nome_file(t) + ".json"))
        r = riassunto(rec) if rec else None
        if r:
            indici.append(dict({"t": t, "n": nome, "l": l, "val": rec.get("valuta")}, **r))
    punteggi(righe)
    try:                                       # v6.55 SMART DISCOUNT (sconto.py): mai bloccante per la scheda
        from . import sconto
        log.warning("smart discount: %d titoli valutati", sconto.calcola(mensili, righe))
    except Exception as e:
        log.warning("smart discount non calcolato (%s: %s)", type(e).__name__, e)
    top = vetrina(righe)
    ultimo = max((r["data"] for r in righe), default=None)
    indice = {"aggiornato": ultimo, "generato": ora_italia().strftime("%Y-%m-%d %H:%M"),
              "anomalia": (stato or {}).get("anomalia"),
              "settori": [{"id": i, "nome": n, "etf": e} for i, n, e in SETTORI],
              "listini": [{"id": k, "nome": v} for k, v in LISTINI.items()],
              "indici": indici, "titoli": righe, "top": [r["t"] for r in top]}
    _scrivi(os.path.join(cartella, "pubblico", "indice.json"), indice)
    # file piccolo per la vetrina della Dashboard (si carica all'apertura del terminale, ~3 KB)
    _scrivi(os.path.join(cartella, "pubblico", "top.json"),
            {"aggiornato": ultimo, "mese": ora_italia().month, "anomalia": indice["anomalia"],
             "settori": {i: n for i, n, _ in SETTORI}, "listini": LISTINI, "titoli": top})
    _scrivi(os.path.join(cartella, "stato.json"), dict(stato or {}, pubblicati=len(righe)))
    log.info("azioni: %d titoli pubblicati (%d schede dettaglio), dati al %s", len(righe), dettagli, ultimo)
    return indice


def punteggi(righe):
    """Aggiunge a ogni riga 'pt' (0-100) e 'rk' (posizione). Un dato mancante vale il percentile mediano (50)."""
    n = len(righe)
    if not n:
        return righe
    perc = {}
    for k in PESI:
        val = sorted((r[k], i) for i, r in enumerate(righe) if r.get(k) is not None)
        for pos, (_, i) in enumerate(val):
            perc.setdefault(i, {})[k] = 100 * pos / max(1, len(val) - 1)
    for i, r in enumerate(righe):
        p = perc.get(i, {})
        r["pt"] = round(sum(w * p.get(k, 50) for k, w in PESI.items()))
    for pos, r in enumerate(sorted(righe, key=lambda x: -x["pt"])):
        r["rk"] = pos + 1
    return righe


def vetrina(righe, n=TOP_N):
    """I titoli piu' forti di oggi per la Dashboard: punteggio alto E condizioni tutte favorevoli
    (sopra la media a 200 giorni, 3 e 12 mesi positivi, mese in corso storicamente positivo in almeno il 60% degli
    anni con almeno 8 anni di storia, non piu' del 15% sotto il massimo a 52 settimane). Al massimo 1 per settore."""
    ok = [r for r in righe if (r.get("t200") or -1) > 0 and (r.get("v3m") or -1) > 0 and (r.get("v1a") or -1) > 0
          and (r.get("st_media") or -1) > 0 and (r.get("st_pos") or 0) >= 60 and (r.get("st_n") or 0) >= MIN_ANNI_STAG
          and (r.get("dmax") or -100) > -15]
    out, settori = [], set()
    for r in sorted(ok, key=lambda x: -x["pt"]):
        if r["s"] in settori:
            continue
        settori.add(r["s"])
        out.append({k: r.get(k) for k in ("t", "n", "s", "l", "val", "p", "v1g", "v1m", "v3m", "v1a", "t200", "dmax",
                                          "st_media", "st_pos", "st_n", "pt", "rk", "sp")})
        if len(out) == n:
            break
    return out


# --------------------------------------------------------------------------- copia nel sito
def copia_nel_sito(out, ramo="azioni", cartella_locale=None):
    """Copia pubblico/ del ramo git "azioni" dentro <out>/azioni/ (lo fa il workflow del sito).
    Se il ramo non c'e' (primo giorno, PC senza git) non fa niente: la scheda mostra il suo stato vuoto."""
    import shutil
    import subprocess
    import tarfile
    import io
    dest = os.path.join(out, "azioni")
    if cartella_locale:                                   # prova sul PC: copia da una cartella gia' pronta
        src = os.path.join(cartella_locale, "pubblico")
        if os.path.isdir(src):
            shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(src, dest)
            return True
        return False
    try:
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", ramo], check=True, timeout=120,
                       capture_output=True)
        tar = subprocess.run(["git", "archive", "FETCH_HEAD", "pubblico"], check=True, timeout=120,
                             capture_output=True).stdout
        shutil.rmtree(dest, ignore_errors=True)
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name.startswith("pubblico/") and ".." not in m.name:
                    p = os.path.join(dest, m.name[len("pubblico/"):])
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "wb") as fh:
                        fh.write(tf.extractfile(m).read())
        log.info("azioni: dati copiati nel sito (%s)", dest)
        return True
    except Exception as e:
        log.warning("azioni: ramo '%s' non disponibile (%s): la scheda Azioni mostra l'ultimo stato pubblicato",
                    ramo, type(e).__name__)
        return False


def main(argv):
    cartella = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else "dati_azioni"
    titoli = None
    if "--prova" in argv:
        titoli = elenco()[:12]
    stato = aggiorna(cartella, [x["t"] for x in titoli] + [i[0] for i in INDICI] if titoli else None)
    pubblica(cartella, stato, titoli)
    # quota "Azioni scelte" dei portafogli modello (satellite.py): mai bloccante per la scheda Azionario
    try:
        from . import satellite
        satellite.calcola(cartella, titoli=titoli, anomalia=bool(stato.get("anomalia")))
    except Exception:
        import traceback
        log.error("satellite non calcolato:\n%s", traceback.format_exc())
    # bilanci delle aziende USA dalla SEC (fondamentali.py): una volta a settimana per titolo, mai bloccante
    try:
        from . import fondamentali
        fondamentali.aggiorna(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("bilanci SEC non aggiornati:\n%s", traceback.format_exc())
    # profilo delle aziende da Wikidata/Wikipedia (profili.py): ognuno al massimo una volta al mese, mai bloccante
    try:
        from . import profili
        profili.aggiorna(cartella, el=titoli)
    except Exception:
        import traceback
        log.error("profili aziende non aggiornati:\n%s", traceback.format_exc())
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in stato.items()}, ensure_ascii=False))
    return 1 if stato.get("anomalia") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
