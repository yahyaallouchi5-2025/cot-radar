# -*- coding: utf-8 -*-
"""
pattern.py - PATTERN DETECTOR: inversione a 3 candele con assorbimento (forex e materie prime, H4 e Daily).

IL PATTERN (come nelle immagini dell'admin)
  BUY  : candela 1 ribassista (SELL), candele 2 e 3 rialziste (BUY) e la CHIUSURA della candela 3 sopra
         l'APERTURA della candela 1 -> le due candele BUY hanno "assorbito" tutta la candela SELL.
  SELL : candela 1 rialzista (BUY), candele 2 e 3 ribassiste (SELL) e la chiusura della candela 3 sotto
         l'apertura della candela 1.
  Ingresso indicativo = chiusura della candela 3. Livello del pattern = apertura della candela 1.
  Estremo del pattern = minimo (BUY) o massimo (SELL) delle 3 candele (utile come riferimento per lo stop).
  Somiglia al "Three Outside Up/Down", ma l'assorbimento qui avviene in due candele invece che in una.

DATI: Yahoo Finance, candele orarie (ultimi 60 giorni) aggregate in H4 e candele giornaliere (2 anni).
  - H4 allineate alle ore UTC 00-04-08-12-16-20: possono differire di qualche ora dalle H4 del proprio broker
    (MT4/MT5 usano l'ora del server, di solito UTC+2/+3);
  - si usano SOLO candele chiuse: la candela in corso non genera segnali;
  - oro e argento: spot se Yahoo lo fornisce (XAUUSD=X), altrimenti il future (GC=F) come approssimazione.

AGGIORNAMENTO: workflow .github/workflows/pattern.yml ogni 4 ore pochi minuti dopo la chiusura della candela H4
  (e la sera dopo la chiusura daily). Il risultato va nel ramo git "pattern" (un solo commit, sovrascritto) e la
  pagina lo legge direttamente da raw.githubusercontent.com: niente ripubblicazione del sito ogni 4 ore.
  Ritardo tipico 10-20 minuti dalla chiusura della candela (GitHub puo' ritardare i workflow programmati).

STATISTICA ONESTA: per ogni strumento e timeframe si contano i pattern passati e cosa e' successo dopo 5 candele
  (quante volte il prezzo era nella direzione del segnale e lo spostamento medio). Campioni piccoli: indicativi.

USO: python -m cot_radar.pattern <cartella>
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .log import log

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?{q}"
TENTATIVI = 3
DI_FILA = 5
DOPO = 5                     # candele dopo il segnale per la statistica
MOSTRA = 60                  # candele per il grafico della pagina
CODICE_ERRORE = "503"

VALUTE = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]          # ordine di quotazione standard
FOREX = [(a + b, a + "/" + b) for i, a in enumerate(VALUTE) for b in VALUTE[i + 1:]]
# (id, nome, gruppo, ticker Yahoo in ordine di preferenza, cifre decimali)
STRUMENTI = [(c, n, "forex", [c + "=X"], 3 if "JPY" in c else 5) for c, n in FOREX] + [
    ("XAUUSD", "Oro (XAU/USD)", "materie", ["XAUUSD=X", "GC=F"], 2),
    ("XAGUSD", "Argento (XAG/USD)", "materie", ["XAGUSD=X", "SI=F"], 3),
    ("WTI", "Petrolio WTI", "materie", ["CL=F"], 2),
    ("BRENT", "Petrolio Brent", "materie", ["BZ=F"], 2),
    ("NATGAS", "Gas naturale", "materie", ["NG=F"], 3),
    ("COPPER", "Rame", "materie", ["HG=F"], 4),
    ("PLATINUM", "Platino", "materie", ["PL=F"], 2),
]


def ora_italia():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- download
def scarica(ticker, intervallo, periodo, timeout=20, tentativi=TENTATIVI, attesa=2):
    """[(epoch_utc, open, high, low, close)] da Yahoo (candele senza buchi), None dopo `tentativi` prove."""
    q = urllib.parse.urlencode({"range": periodo, "interval": intervallo})
    for n in range(tentativi):
        try:
            req = urllib.request.Request(YAHOO.format(t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/pattern"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                res = json.load(r)["chart"]["result"][0]
            qd = res["indicators"]["quote"][0]
            out = [(ts, o, h, l, c) for ts, o, h, l, c in zip(res.get("timestamp") or [], qd["open"], qd["high"],
                                                                  qd["low"], qd["close"])
                   if None not in (o, h, l, c) and min(o, h, l, c) > 0]
            if len(out) >= 30:
                return out
            log.warning("Yahoo %s %s: troppo pochi dati (tentativo %d/%d)", ticker, intervallo, n + 1, tentativi)
        except Exception as e:
            log.warning("Yahoo %s %s: %s (tentativo %d/%d)", ticker, intervallo, getattr(e, "code", type(e).__name__),
                        n + 1, tentativi)
        if n + 1 < tentativi and attesa:
            time.sleep(attesa * (3 ** n))
    return None


def h4(orarie, adesso=None):
    """Aggrega candele orarie in H4 allineate a UTC 00/04/08/12/16/20. Scarta la H4 non ancora chiusa."""
    adesso = adesso or time.time()
    gruppi = {}
    for ts, o, h, l, c in orarie:
        b = ts - ts % (4 * 3600)
        g = gruppi.get(b)
        gruppi[b] = (b, o, h, l, c) if g is None else (b, g[1], max(g[2], h), min(g[3], l), c)
    return [g for b, g in sorted(gruppi.items()) if b + 4 * 3600 <= adesso]


def giornaliere(dati, adesso=None):
    """Candele daily chiuse: si scarta quella del giorno in corso (UTC)."""
    adesso = adesso or time.time()
    oggi = int(adesso) - int(adesso) % 86400
    return [x for x in dati if x[0] < oggi - 3600]


# --------------------------------------------------------------------------- pattern
def trova(c):
    """Indici i (candela 3 = c[i]) dove si completa il pattern. Ritorna [(i, 'BUY'|'SELL')]."""
    out = []
    for i in range(2, len(c)):
        a, b, d = c[i - 2], c[i - 1], c[i]          # candela 1, 2, 3
        su = lambda x: x[4] > x[1]
        giu = lambda x: x[4] < x[1]
        if giu(a) and su(b) and su(d) and d[4] > a[1]:
            out.append((i, "BUY"))
        elif su(a) and giu(b) and giu(d) and d[4] < a[1]:
            out.append((i, "SELL"))
    return out


def analizza(c, cifre):
    """Segnali, ultimo segnale e statistica su una serie di candele chiuse."""
    segnali = trova(c)
    lista, esiti = [], []
    for i, lato in segnali:
        a = c[i - 2]
        estremo = min(x[3] for x in c[i - 2:i + 1]) if lato == "BUY" else max(x[2] for x in c[i - 2:i + 1])
        s = {"t": c[i][0], "lato": lato, "ingresso": round(c[i][4], cifre), "livello": round(a[1], cifre),
             "estremo": round(estremo, cifre), "fa": len(c) - 1 - i}
        if i + DOPO < len(c):
            mossa = (c[i + DOPO][4] / c[i][4] - 1) * 100 * (1 if lato == "BUY" else -1)
            s["esito"] = round(mossa, 2)
            esiti.append(mossa)
        lista.append(s)
    stat = {"n": len(esiti), "vinti": round(100 * sum(e > 0 for e in esiti) / len(esiti)) if esiti else None,
            "media": round(sum(esiti) / len(esiti), 2) if esiti else None, "dopo": DOPO}
    ult = lista[-1] if lista else None
    if ult:
        ult["ora"] = round(c[-1][4], cifre)
        ult["mossa"] = round((c[-1][4] / ult["ingresso"] - 1) * 100 * (1 if ult["lato"] == "BUY" else -1), 2)
    return {"ultimo": ult, "segnali": lista[-12:], "stat": stat,
            "candele": [[x[0], round(x[1], cifre), round(x[2], cifre), round(x[3], cifre), round(x[4], cifre)]
                        for x in c[-MOSTRA:]],
            "ultima_chiusa": c[-1][0] if c else None}


# --------------------------------------------------------------------------- giro completo
def esegui(cartella, scarica=scarica, adesso=None, pausa=0.3):
    adesso = adesso or time.time()
    risultati, falliti, di_fila = [], [], 0
    for sid, nome, gruppo, tickers, cifre in STRUMENTI:
        rec = None
        if di_fila < DI_FILA:
            for t in tickers:                          # spot se c'e', altrimenti il future
                o = scarica(t, "60m", "60d")
                d = scarica(t, "1d", "2y") if o else None
                if pausa:
                    time.sleep(pausa)
                if o and d:
                    rec = {"id": sid, "n": nome, "g": gruppo, "fonte": t,
                           "h4": analizza(h4(o, adesso), cifre), "d1": analizza(giornaliere(d, adesso), cifre)}
                    break
        if rec:
            di_fila = 0
            risultati.append(rec)
        else:
            di_fila += 1
            falliti.append(sid)
    # copia del giro precedente per gli strumenti falliti: la scheda non perde righe
    vecchio = {}
    try:
        with open(os.path.join(cartella, "pattern.json"), encoding="utf-8") as f:
            vecchio = {x["id"]: x for x in json.load(f).get("strumenti", [])}
    except (OSError, ValueError):
        pass
    for sid in falliti:
        if sid in vecchio:
            risultati.append(dict(vecchio[sid], copia=True))
    ordine = {s[0]: i for i, s in enumerate(STRUMENTI)}
    risultati.sort(key=lambda x: ordine.get(x["id"], 999))
    quando = ora_italia().strftime("%Y-%m-%d %H:%M")
    anomalia = None
    if di_fila >= DI_FILA or len(falliti) > 0.2 * len(STRUMENTI):
        anomalia = {"codice": CODICE_ERRORE, "quando": quando}
        log.error("pattern: aggiornamento non riuscito (%s), strumenti falliti: %s", quando, ", ".join(falliti))
    elif falliti:
        log.warning("pattern: strumenti non aggiornati: %s", ", ".join(falliti))
    out = {"generato": quando, "generato_utc": int(adesso), "anomalia": anomalia, "dopo": DOPO,
           "strumenti": risultati}
    os.makedirs(cartella, exist_ok=True)
    with open(os.path.join(cartella, "pattern.json.tmp"), "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    os.replace(os.path.join(cartella, "pattern.json.tmp"), os.path.join(cartella, "pattern.json"))
    log.info("pattern: %d strumenti, %d falliti", len(risultati), len(falliti))
    return out


def main(argv):
    cartella = argv[1] if len(argv) > 1 else "dati_pattern"
    out = esegui(cartella)
    print(json.dumps({"strumenti": len(out["strumenti"]), "anomalia": out["anomalia"]}))
    return 1 if out["anomalia"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


def copia_nel_sito(out, ramo="pattern"):
    """Copia di riserva di pattern.json dentro <out>/pattern/ (la pagina legge prima raw.githubusercontent.com)."""
    import subprocess
    try:
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", ramo], check=True, timeout=60, capture_output=True)
        dati = subprocess.run(["git", "show", "FETCH_HEAD:pattern.json"], check=True, timeout=60,
                              capture_output=True).stdout
        os.makedirs(os.path.join(out, "pattern"), exist_ok=True)
        with open(os.path.join(out, "pattern", "pattern.json"), "wb") as f:
            f.write(dati)
        return True
    except Exception as e:
        log.warning("pattern: ramo '%s' non disponibile (%s)", ramo, type(e).__name__)
        return False
