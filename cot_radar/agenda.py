# -*- coding: utf-8 -*-
"""
agenda.py - AGENDA DELLE NOTIZIE MACRO (calendario + esito misurato dal mercato), usata da:
  - il motore notizie (notizie.py): date e orari degli eventi PRINCIPALI (NFP, CPI, Fed, BCE);
  - gli avvisi Telegram (avvisi.py): "notizia in arrivo" e "esito della notizia" con i segnali COT esposti.

FLUSSO (una sola strada, ogni dato ha un solo compito):
  1. CALENDARIO = financecalendar.com (gratuito, uso commerciale con link di attribuzione): data, ora, impatto,
     dato uscito e precedente. Se non risponde: ultima copia salvata (dati/agenda.json); se manca anche quella,
     il calendario interno di notizie.py (solo NFP, CPI, Fed, BCE). Mai un buco, mai dati inventati.
  2. ESITO = reazione del MERCATO, da FRED/BCE: di quanto si e' mosso il tasso a 2 anni della valuta nel giorno
     dell'annuncio rispetto a una giornata normale (z-score, vedi notizie.sorpresa_mercato). Misura la vera
     sorpresa (rispetto a quanto era gia' prezzato) senza bisogno del consensus. Disponibile per USD ed EUR;
     arriva quando FRED/BCE pubblicano il tasso (di solito il giorno dopo): finche' manca, l'esito resta
     "in attesa" e gli avvisi riprovano al giro successivo.
  3. SEGNALI ESPOSTI = coppie Forex con un segnale COT attivo che contengono la valuta della notizia.
     Verdetto: CONFERMA (la reazione spinge la coppia nel verso del segnale), CONTRASTO (verso opposto),
     NEUTRO (reazione nella norma, |z| < 1).

DEBUG: python -c "from cot_radar import agenda; print(agenda.scarica()[:2])"
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from .config import ROOT
from .log import log

FONTE = "https://www.financecalendar.com/wp-json/fc/v1/calendar"
CREDITO = "https://www.financecalendar.com"          # link di attribuzione richiesto dalla licenza
CACHE = os.path.join(ROOT, "dati", "agenda.json")
# codice financecalendar -> (nome italiano, valuta, tipo, principale)
#   tipo "dato" = statistica (effetto breve), "banca" = decisione di banca centrale (effetto piu' lungo)
#   principale = entra anche nel correttivo del punteggio (stessi eventi usati finora dal motore notizie)
SERIE = {
    "fomc": ("Fed (FOMC)", "USD", "banca", True), "ecb": ("BCE", "EUR", "banca", True),
    "us-nfp": ("NFP USA (occupazione)", "USD", "dato", True), "us-cpi": ("CPI USA (inflazione)", "USD", "dato", True),
    "us-pce": ("PCE USA (inflazione)", "USD", "dato", False), "us-ppi": ("PPI USA (prezzi alla produzione)", "USD", "dato", False),
    "us-gdp": ("PIL USA", "USD", "dato", False), "us-retail-sales": ("Vendite al dettaglio USA", "USD", "dato", False),
    "us-ism-manufacturing": ("ISM manifatturiero USA", "USD", "dato", False),
    "us-ism-services": ("ISM servizi USA", "USD", "dato", False),
    "eu-cpi": ("CPI Eurozona (stima flash)", "EUR", "dato", False),
    "boe": ("Bank of England", "GBP", "banca", False), "gb-cpi": ("CPI Regno Unito", "GBP", "dato", False),
    "boj": ("Bank of Japan", "JPY", "banca", False), "boc": ("Bank of Canada", "CAD", "banca", False),
    "ca-cpi": ("CPI Canada", "CAD", "dato", False), "rba": ("RBA (Australia)", "AUD", "banca", False),
    "au-cpi": ("CPI Australia", "AUD", "dato", False), "rbnz": ("RBNZ (Nuova Zelanda)", "NZD", "banca", False),
    "snb": ("SNB (Svizzera)", "CHF", "banca", False),
}
MISURABILI = {"USD", "EUR"}                          # valute con il tasso a 2 anni nei nostri dati
Z_MARCATA = 1.0                                      # |z| sotto questa soglia = reazione nella norma
PRIMA, DOPO = 10, 8                                  # giorni di agenda: prossimi 10, ultimi 8


def scarica(da=None, a=None, timeout=25):
    """Eventi del calendario (lista di dizionari) tra le date da e a. None se la fonte non risponde."""
    oggi = date.today()
    da, a = da or oggi - timedelta(days=DOPO), a or oggi + timedelta(days=PRIMA)
    q = urllib.parse.urlencode({"series": ",".join(SERIE), "from": da.isoformat(), "to": a.isoformat(), "limit": 200})
    try:
        req = urllib.request.Request(f"{FONTE}?{q}", headers={"User-Agent": "cot-radar/agenda"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dati = json.load(r)
        eventi = dati.get("events")
        if not isinstance(eventi, list):
            raise ValueError("risposta senza 'events'")
        return eventi
    except (OSError, ValueError) as e:
        log.warning("calendario financecalendar non raggiungibile (%s): uso l'ultima copia", type(e).__name__)
        return None


def _numero(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def normalizza(e):
    """Evento della fonte -> formato interno (None se la serie non ci interessa o i dati sono incompleti)."""
    s = SERIE.get(e.get("series_code"))
    if not s or not e.get("date"):
        return None
    utc = None
    if e.get("release_at_utc"):
        try:
            utc = datetime.fromisoformat(e["release_at_utc"].replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%MZ")
        except ValueError:
            utc = None
    return {"id": e.get("id") or f"{e['series_code']}-{e['date']}", "codice": e["series_code"], "nome": s[0],
            "valuta": s[1], "tipo": s[2], "principale": s[3], "impatto": e.get("impact") or "high",
            "data": e["date"][:10], "utc": utc, "stato": e.get("status"), "unita": e.get("unit") or "",
            "precedente": e.get("prior"), "attuale": e.get("actual"), "fonte": e.get("source_url")}


def interno():
    """Calendario di riserva: gli eventi principali scritti a mano in notizie.CALENDARIO."""
    from .notizie import CALENDARIO, _utc
    codici = {"Fed (FOMC)": "fomc", "BCE": "ecb", "NFP USA": "us-nfp", "CPI USA": "us-cpi"}
    out = []
    for ev in CALENDARIO:
        c = codici.get(ev[4])
        if c:
            s = SERIE[c]
            out.append({"id": f"{c}-{ev[0]}", "codice": c, "nome": s[0], "valuta": s[1], "tipo": s[2], "principale": True,
                        "impatto": "high", "data": ev[0], "utc": _utc(ev).strftime("%Y-%m-%dT%H:%MZ"), "stato": None,
                        "unita": "", "precedente": None, "attuale": None, "fonte": None})
    return out


def carica(adesso=None, scarica_fn=scarica, cache=CACHE):
    """(eventi normalizzati, fonte): financecalendar -> ultima copia salvata -> calendario interno."""
    grezzi = scarica_fn()
    if grezzi is not None:
        eventi = [x for x in (normalizza(e) for e in grezzi) if x]
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(eventi, f, ensure_ascii=False)
        except OSError as e:
            log.warning("copia dell'agenda non salvata (%s)", e)
        return eventi, "financecalendar"
    try:
        with open(cache, encoding="utf-8") as f:
            return json.load(f), "financecalendar (copia salvata)"
    except (OSError, ValueError):
        log.warning("agenda: nessuna copia salvata, uso il calendario interno (solo NFP, CPI, Fed, BCE)")
        return interno(), "interno"


def esposti(valuta, pairs):
    """Coppie Forex con segnale COT attivo che contengono la valuta. lato = +1 se e' la valuta base
    (valuta piu' forte = coppia sale), -1 se e' la quotata (valuta piu' forte = coppia scende)."""
    out = []
    for p in pairs:
        if p.get("label", "NEUTRO") == "NEUTRO" or valuta not in (p.get("base"), p.get("quote")):
            continue
        out.append({"coppia": f"{p['base']}/{p['quote']}", "etichetta": p["label"],
                    "verso": 1 if "BUY" in p["label"] else -1, "lato": 1 if p["base"] == valuta else -1,
                    "punteggio": p.get("score")})
    return sorted(out, key=lambda x: -abs(x["punteggio"] or 0))


def verdetto(z, segnale):
    """Effetto della reazione del mercato su un segnale esposto: conferma / contrasto / neutro."""
    if z is None:
        return None
    if abs(z) < Z_MARCATA:
        return "neutro"
    return "conferma" if (1 if z > 0 else -1) * segnale["lato"] == segnale["verso"] else "contrasto"


def costruisci(fred, ecb, pairs, adesso=None, scarica_fn=scarica, cache=CACHE):
    """Agenda completa per la pagina e per gli avvisi: {"fonte", "credito", "eventi": [...]}.
    Per ogni evento gia' uscito di USD/EUR aggiunge la reazione del mercato (z, pb) e il verdetto sui segnali."""
    from .notizie import _serie_tasso, sorpresa_mercato
    adesso = adesso or datetime.utcnow()
    eventi, fonte = carica(adesso, scarica_fn, cache)
    oggi = adesso.date()
    out = []
    for e in eventi:
        d = date.fromisoformat(e["data"])
        if not (oggi - timedelta(days=DOPO) <= d <= oggi + timedelta(days=PRIMA)):
            continue
        e = dict(e, esposti=esposti(e["valuta"], pairs))
        uscito = (datetime.strptime(e["utc"], "%Y-%m-%dT%H:%MZ") <= adesso) if e["utc"] else d < oggi
        e["uscito"] = uscito
        e["z"] = e["pb"] = None
        if uscito and e["valuta"] in MISURABILI:
            s = sorpresa_mercato(e["data"], _serie_tasso(e["valuta"], fred, ecb))
            if s:
                e["z"], e["pb"] = s
        for x in e["esposti"]:
            x["verdetto"] = verdetto(e["z"], x)
        out.append(e)
    out.sort(key=lambda x: (x["data"], x["utc"] or "99"))
    return {"fonte": fonte, "credito": CREDITO, "aggiornato": adesso.strftime("%Y-%m-%dT%H:%MZ"), "eventi": out}


def calendario_motore(agenda):
    """Eventi PRINCIPALI nel formato di notizie.CALENDARIO (per il correttivo del punteggio):
    (data, ora, minuti, "UTC", nome breve, valuta, tipo). Solo quelli con un orario certo."""
    nomi = {"fomc": "Fed (FOMC)", "ecb": "BCE", "us-nfp": "NFP USA", "us-cpi": "CPI USA"}
    out = []
    for e in (agenda or {}).get("eventi", []):
        if e.get("principale") and e.get("utc"):
            t = datetime.strptime(e["utc"], "%Y-%m-%dT%H:%MZ")
            out.append((t.strftime("%Y-%m-%d"), t.hour, t.minute, "UTC", nomi[e["codice"]], e["valuta"], e["tipo"]))
    return out
