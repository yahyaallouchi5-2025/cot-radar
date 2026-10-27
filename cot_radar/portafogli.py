# -*- coding: utf-8 -*-
"""
portafogli.py - TRE PORTAFOGLI MODELLO A ROTAZIONE MENSILE (solo acquisto, strumenti spot tipo ETF/ETC)

IDEA
  L'investitore sceglie un profilo (conservativo, moderato, aggressivo) e ogni mese riceve la lista di cosa
  tenere e con che peso. Il profilo decide QUALI mercati sono ammessi e QUANTO rischio si accetta
  (volatilita' obiettivo -> drawdown storico atteso). Ogni ~30 giorni (primo giorno di borsa del mese) il
  portafoglio ruota: restano i mercati ancora favorevoli, escono gli altri, entrano i nuovi.

REGOLE, VERSIONE 2 (scelte guardando SOLO lo storico 2006-2015, poi verificate una volta fuori campione)
  1. Ogni profilo ha una BASE fissa di mercati e pesi (indici azionari, Treasury, oro; Nasdaq, emergenti e
     Bitcoin nell'aggressivo), comprabili a pronti con ETF/ETC. Prezzi rettificati (dividendi inclusi) Yahoo.
  2. FILTRO DI TREND a ogni rotazione mensile: se il prezzo di un mercato e' sotto la sua media a 200 giorni,
     il suo peso va "in pausa" in liquidita' (Treasury 1-3 anni) fino a quando torna sopra. Solo acquisti.
  3. Il punteggio COT di ogni mercato e' mostrato accanto come informazione, ma NON decide i pesi: nello
     storico 2006-2015 il filtro COT (da solo, come conferma o come veto) peggiorava il rendimento a parita'
     di rischio, mentre il filtro di trend dimezzava le cadute (vedi README, "Portafogli modello").
  4. Costi: 0,10% sul capitale che cambia a ogni ribilanciamento.
  VERSIONE 1 (ritirata): ingresso solo con COT da BUY + trend e pesi a volatilita' obiettivo. Fuori campione
  rendeva 1-2% l'anno contro l'8% del 60/40, quasi sempre in liquidita'. Le sue rotazioni restano in
  storico/portafogli/rotazioni.json; la versione 2 registra in rotazioni_v2.json.

VERIFICA ONESTA
  - STORICO: dal primo anno con dati sufficienti fino al 31/12/2015;
  - FUORI CAMPIONE (OOS): dal 2016 a oggi, con le STESSE regole (mai ritoccate guardando questo periodo);
  - LIVE: dalla prima rotazione pubblicata sul sito. Ogni rotazione viene salvata nell'archivio
    (storico/portafogli/rotazioni_v2.json) e non viene mai riscritta: la linea live non si puo' "aggiustare".

DATI: storico/yahoo/<TICKER>.csv (copia dei prezzi Yahoo, aggiornata al massimo una volta al giorno).
  Se Yahoo non risponde si usa la copia salvata; senza copia il portafoglio non viene mostrato.
  ATTENZIONE: i termini d'uso di Yahoo riguardano l'uso personale; per un servizio commerciale conviene
  passare a un fornitore con licenza (basta cambiare scarica_yahoo()).

DEBUG: python -c "from cot_radar import portafogli; help(portafogli.calcola)"
"""
import csv
import json
import math
import os
import time
import urllib.parse
import urllib.request
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone

from .backtest import punteggi
from .config import ASSETS, NORMAL, ROOT
from .cot import cot_series
from .log import log

CARTELLA = os.path.join(ROOT, "storico")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?{q}"

# (chiave COT, ticker Yahoo per lo storico, nome, strumento da comprare, classe)
UNIVERSO = [
    ("SP500", "SPY", "S&P 500", "ETF S&P 500", "azioni"),
    ("NASDAQ", "QQQ", "Nasdaq-100", "ETF Nasdaq-100", "azioni"),
    ("DOW", "DIA", "Dow Jones", "ETF Dow Jones", "azioni"),
    ("RUSSELL", "IWM", "Russell 2000", "ETF Russell 2000 (piccole aziende USA)", "azioni"),
    ("EAFE", "EFA", "Azioni Europa e Asia", "ETF MSCI EAFE (Paesi sviluppati esclusi USA)", "azioni"),
    ("EM", "EEM", "Azioni emergenti", "ETF MSCI Emerging Markets", "azioni"),
    ("US10Y", "IEF", "Treasury 10 anni", "ETF Treasury USA 7-10 anni", "obbligazioni"),
    ("USBOND", "TLT", "Treasury 30 anni", "ETF Treasury USA 20+ anni", "obbligazioni"),
    ("GOLD", "GLD", "Oro", "ETC oro fisico", "metalli"),
    ("SILVER", "SLV", "Argento", "ETC argento fisico", "metalli"),
    ("PLATINUM", "PPLT", "Platino", "ETC platino fisico", "metalli"),
    ("COPPER", "CPER", "Rame", "ETC rame", "materie prime"),
    ("WTI", "USO", "Petrolio WTI", "ETC petrolio WTI", "materie prime"),
    ("NATGAS", "UNG", "Gas naturale", "ETC gas naturale", "materie prime"),
    ("CORN", "CORN", "Mais", "ETC mais", "materie prime"),
    ("WHEAT", "WEAT", "Grano", "ETC grano", "materie prime"),
    ("SOY", "SOYB", "Soia", "ETC soia", "materie prime"),
    ("BTC", "BTC-USD", "Bitcoin", "ETP Bitcoin (o Bitcoin a pronti)", "crypto"),
    ("ETH", "ETH-USD", "Ether", "ETP Ether (o Ether a pronti)", "crypto"),
]
LIQUIDITA = ("CASH", "SHY", "Liquidità", "ETF Treasury USA 1-3 anni (parcheggio)", "liquidita")
# Quota "Azioni scelte": 5 titoli dell'Azionario a pari peso, scelti ogni mese da satellite.py (workflow delle azioni).
# Nei calcoli e' un mercato sintetico "SAT": prezzo costruito dai rendimenti mensili dello storico simulato e, dal
# live, dai prezzi giornalieri dei titoli registrati (vedi serie_satellite()).
AZIONI_SCELTE = ("AZ", "SAT", "Azioni scelte", "5 azioni dell'Azionario a pari peso (1 per settore)", "azioni singole")
# Prezzi in piu' che NON entrano nei portafogli: servono alla scheda Correlazioni (correlazioni.py) -> settori USA
# (ETF SPDR) e dollaro (UUP). Scaricati e salvati insieme agli altri, una volta al giorno.
EXTRA = ["XLK", "XLC", "XLY", "XLF", "XLI", "XLE", "XLB", "XLV", "XLP", "XLU", "XLRE", "UUP"]
BENCH = (("SPY", 0.6), ("IEF", 0.4))          # confronto: classico 60% azioni USA + 40% Treasury, ribilanciato
TUTTI = {u[0]: u for u in UNIVERSO + [LIQUIDITA, AZIONI_SCELTE]}
# STRUMENTI DA COMPRARE IN EUROPA: gli ETF USA usati per i calcoli (SPY, QQQ, ...) non si possono comprare da un
# conto europeo (manca il documento KID), quindi per ogni mercato si indica un equivalente UCITS / ETC / ETP con ISIN
# (da cercare nell'app del broker). Verificati il 27/10/2026. Classe di accumulo (Acc) dove esiste.
# chiave -> (nome del prodotto, ISIN, nota facoltativa)
STRUMENTI_UE = {
    "SP500": ("iShares Core S&P 500 UCITS ETF (Acc)", "IE00B5BMR087", None),
    "NASDAQ": ("iShares Nasdaq 100 UCITS ETF (Acc)", "IE00B53SZB19", None),
    "EAFE": ("Xtrackers MSCI World ex USA UCITS ETF 1C", "IE0006WW1TQ4",
             "include anche il Canada: è l'equivalente UCITS più vicino all'MSCI EAFE"),
    "EM": ("iShares Core MSCI EM IMI UCITS ETF (Acc)", "IE00BKM4GZ66", None),
    "US10Y": ("iShares $ Treasury Bond 7-10yr UCITS ETF (Acc)", "IE00B3VWN518", None),
    "GOLD": ("iShares Physical Gold ETC", "IE00B4ND3602", None),
    "BTC": ("iShares Bitcoin ETP", "XS2940466316", None),
    "CASH": ("Xtrackers II EUR Overnight Rate Swap UCITS ETF 1C", "LU0290358497",
             "liquidità in euro al tasso BCE (il modello usa i Treasury USA 1-3 anni in dollari)"),
}

# I tre profili: BASE fissa (chiave -> peso) e drawdown di riferimento. La parte "CASH" e' liquidita' fissa.
# I tre profili: stesso motore, rischio diverso. BASE fissa di ETF (chiave -> peso relativo, somma 1) e quota di
# AZIONI SCELTE ("az"): i pesi reali sono base x (1 - az) + az nelle 5 azioni. dd = caduta di riferimento del profilo.
# Quote decise il 26/10/2026 dopo il test 2006-2026 con filtro di mercato (README, "Azioni scelte"): conservativo 10%,
# moderato 20%, aggressivo 40%. La parte "CASH" della base e' liquidita' fissa.
PROFILI = [
    {"id": "conservativo", "nome": "Conservativo", "rischio": "Basso", "dd": 14, "az": .10,
     "base": {"SP500": .20, "EAFE": .10, "US10Y": .45, "GOLD": .10, "CASH": .15},
     "descr": "Protezione del capitale prima di tutto: Treasury, oro e liquidità come cuscinetto, azioni globali "
              "e una piccola quota di 5 azioni scelte per dare spinta al rendimento."},
    {"id": "moderato", "nome": "Moderato", "rischio": "Medio", "dd": 18, "az": .20,
     "base": {"SP500": .35, "EAFE": .10, "EM": .05, "US10Y": .30, "GOLD": .10, "CASH": .10},
     "descr": "Equilibrio tra crescita e difesa: azioni USA, Europa/Asia ed emergenti bilanciate da Treasury e oro, "
              "più un quinto in 5 azioni scelte ogni mese."},
    {"id": "aggressivo", "nome": "Aggressivo", "rischio": "Alto", "dd": 22, "az": .40,
     "base": {"SP500": .40, "NASDAQ": .15, "EAFE": .10, "EM": .10, "US10Y": .10, "GOLD": .10, "BTC": .05},
     "descr": "Massima crescita: indici azionari con tecnologia, emergenti e una quota di Bitcoin, più il 40% in "
              "5 azioni scelte ogni mese. Cadute più ampie, ripagate da un rendimento nettamente più alto."},
]
for _p in PROFILI:                                   # mercati ammessi = quelli della base (per la pagina)
    _p["ammessi"] = [k for k in _p["base"] if k != "CASH"] + (["AZ"] if _p.get("az") else [])
INIZIO = "2006-01-01"          # primo ribilanciamento (prima i dati degli ETF sono troppo pochi)
OOS_DAL = "2016-01-01"         # da qui in poi: fuori campione
COSTO = 0.001                  # 0,10% del capitale scambiato
SMA = 200                      # media mobile del filtro di trend (giorni di borsa)
VOL_GIORNI = 63                # finestra della volatilita' (circa 3 mesi)
MIN_STORIA = 260               # giorni di prezzo minimi perche' un mercato sia ammesso


# --------------------------------------------------------------------------- dati Yahoo (con copia locale)
TENTATIVI = 3                  # tentativi di download per ogni ticker, con pausa crescente (2 s, 6 s)
VECCHI_GIORNI = 4              # oltre questi giorni di calendario senza prezzi nuovi la scheda avvisa l'utente
CODICE_ERRORE = "503"          # codice generico mostrato all'utente (i dettagli restano nel registro admin)
ESITO = {}                     # ultimo giro di prezzi(): {"falliti": [ticker], "copia": [ticker]} (per l'avviso)


def _valida(pts):
    """Controllo di qualita' di una serie scaricata: almeno 30 prezzi, date crescenti e senza buchi assurdi
    (salto giornaliero oltre +/-70%: dato rotto). Restituisce la serie o None."""
    if not pts or len(pts) < 30:
        return None
    for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
        if d1 <= d0 or not (0.3 < v1 / v0 < 1.7):
            return None
    return pts


def scarica_yahoo(ticker, timeout=20, tentativi=TENTATIVI, attesa=2):
    """Prezzi giornalieri RETTIFICATI (dividendi e frazionamenti inclusi): [(data, prezzo)], None se fallisce.
    Riprova fino a `tentativi` volte (pausa 2 s, poi 6 s): Yahoo a volte risponde 429/5xx per pochi secondi.
    Una risposta incompleta o con prezzi assurdi conta come fallita: in quel caso resta la copia salvata."""
    q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": "1d",
                                "events": "div,split", "includeAdjustedClose": "true"})
    for n in range(tentativi):
        try:
            req = urllib.request.Request(YAHOO.format(t=urllib.parse.quote(ticker), q=q),
                                         headers={"User-Agent": "cot-radar/portafogli"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                js = json.load(r)
            res = js["chart"]["result"][0]
            off = res["meta"].get("gmtoffset", 0)
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            out = {}
            for ts, v in zip(res["timestamp"], adj):
                if v is not None and v > 0:
                    out[datetime.fromtimestamp(ts + off, tz=timezone.utc).date().isoformat()] = round(float(v), 6)
            pts = _valida(sorted(out.items()))
            if pts:
                return pts
            log.warning("Yahoo %s: risposta incompleta o anomala (tentativo %d/%d)", ticker, n + 1, tentativi)
        except Exception as e:                   # rete, limite di richieste, formato cambiato...
            log.warning("Yahoo %s non disponibile: %s (tentativo %d/%d)", ticker, type(e).__name__, n + 1, tentativi)
        if n + 1 < tentativi and attesa:
            time.sleep(attesa * (3 ** n))
    return None


def _file(cartella, ticker):
    return os.path.join(cartella, "yahoo", ticker.replace("^", "_") + ".csv")


def _leggi(cartella, ticker):
    try:
        with open(_file(cartella, ticker), encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            return [(r[0], float(r[1])) for r in rd if len(r) == 2]
    except (OSError, ValueError):
        return []


def _scrivi(cartella, ticker, pts):
    f = _file(cartella, ticker)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["data", "valore"])
        w.writerows(pts)
    os.replace(f + ".tmp", f)


def prezzi(scarica=scarica_yahoo, cartella=CARTELLA, oggi=None, pausa=0.8):
    """{ticker: [(data, prezzo)]} per tutto l'universo + liquidita'. Scarica al massimo una volta al giorno;
    un download nuovo sostituisce la copia solo se e' completo (non piu' corto e non piu' vecchio).
    I prezzi rettificati di Yahoo cambiano all'indietro a ogni dividendo: per questo la copia si sostituisce
    intera invece di aggiungere solo i giorni nuovi."""
    oggi = (oggi or date.today()).isoformat()
    meta_f = os.path.join(cartella, "yahoo", "_meta.json")
    try:
        with open(meta_f, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError):
        meta = {}
    out, cambiato = {}, False
    ESITO.clear()
    ESITO.update({"falliti": [], "copia": []})
    di_fila = 0                                        # fallimenti consecutivi: a 3 Yahoo e' giu', si smette
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]] + EXTRA:
        vecchi = _leggi(cartella, t)
        if meta.get(t) != oggi and scarica:
            # Yahoo fermo: niente altri tentativi in questo giro (il workflow non resta appeso per mezz'ora),
            # si usano le copie e si riprova al giro successivo
            nuovi = scarica(t) if di_fila < 3 else None
            di_fila = 0 if nuovi else di_fila + 1
            if pausa:
                time.sleep(pausa)
            if nuovi and len(nuovi) >= 0.95 * len(vecchi) and (not vecchi or nuovi[-1][0] >= vecchi[-1][0]):
                _scrivi(cartella, t, nuovi)
                vecchi, meta[t], cambiato = nuovi, oggi, True
            else:                                      # download fallito o peggiore della copia: si tiene la copia
                ESITO["falliti"].append(t)
                if vecchi:
                    ESITO["copia"].append(t)
        if vecchi:
            out[t] = vecchi
    if cambiato:
        os.makedirs(os.path.dirname(meta_f), exist_ok=True)
        with open(meta_f, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1, sort_keys=True)
    return out


def prezzi_demo(inizio="2000-01-03", fine=None):
    """Prezzi FINTI (passeggiata casuale, sempre uguale) per la modalita' --demo: servono solo a vedere la scheda."""
    import random
    rnd = random.Random(7)
    fine = fine or date.today().isoformat()
    giorni, d = [], date.fromisoformat(inizio)
    while d.isoformat() <= fine:
        if d.weekday() < 5:
            giorni.append(d.isoformat())
        d += timedelta(days=1)
    out = {}
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]] + EXTRA:
        v, pts = 100.0, []
        mu, sg = (0.0001, 0.001) if t == LIQUIDITA[1] else (0.0003, 0.011)
        for g in giorni:
            v *= math.exp(rnd.gauss(mu, sg))
            pts.append((g, round(v, 4)))
        out[t] = pts
    return out


# --------------------------------------------------------------------------- strumenti di calcolo
class Griglia:
    """Prezzi di tutti i mercati sulle stesse date (calendario di borsa USA, quello dello SPY).
    I giorni mancanti di un mercato ripetono l'ultimo prezzo noto; prima del primo prezzo: None."""

    def __init__(self, px, base="SPY"):
        self.date = [d for d, _ in px[base]]
        self.pos = {d: i for i, d in enumerate(self.date)}
        self.p = {}
        for t, pts in px.items():
            dd = dict(pts)
            col, ultimo, n = [], None, 0
            for d in self.date:
                if d in dd:
                    ultimo, n = dd[d], n + 1
                col.append(ultimo)
            self.p[t] = col
        self.n = {t: [0] * len(self.date) for t in px}            # quanti giorni di storia ha ogni mercato
        for t, col in self.p.items():
            c = 0
            for i, v in enumerate(col):
                c += v is not None
                self.n[t][i] = c

    def rend(self, t, i):
        """Rendimento del giorno i (prezzo i / prezzo i-1 - 1); 0 se manca."""
        c = self.p.get(t)
        if not c or i == 0 or c[i] is None or c[i - 1] is None:
            return 0.0
        return c[i] / c[i - 1] - 1


def _std(x):
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1))


def segnali_cot(righe_cot):
    """{chiave: [(martedi', punteggio)]} point-in-time per i mercati dell'universo (stessa formula del sito)."""
    serie = cot_series(righe_cot)
    codici = {a[0]: a[1] for a in ASSETS}
    out = {}
    for k, *_ in UNIVERSO:
        s = serie.get(codici.get(k))
        if s:
            out[k] = sorted((d, v[0]) for d, v in punteggi(s).items())
    return out


def cot_al(sc, giorno):
    """Ultimo punteggio COT GIA' PUBBLICATO al giorno dato (report del martedi', pubblico il venerdi')."""
    if not sc:
        return None
    limite = (date.fromisoformat(giorno) - timedelta(days=4)).isoformat()   # martedi' + 3 = venerdi' < giorno
    i = bisect_left(sc, (limite, float("inf"))) - 1
    return sc[i] if i >= 0 else None


def date_ribilancio(g, dal=INIZIO):
    """Primo giorno di borsa di ogni mese, da 'dal' in poi."""
    out, mese = [], None
    for i, d in enumerate(g.date):
        if d >= dal and d[:7] != mese:
            out.append(i)
            mese = d[:7]
    return out


def regola_base(score, trend_ok):
    """Regola della versione 2: conta solo il trend (prezzo sopra la media a 200 giorni). score e' ignorato."""
    return trend_ok


def scegli(profilo, g, i, sc, regola=None):
    """Composizione del profilo al giorno i: ({chiave: peso}, dettagli dei mercati tenuti, mercati in pausa).
    Ogni mercato della base tiene il suo peso se regola(score COT, trend) e' vera, altrimenti il peso va in
    liquidita'. I mercati non ancora quotati abbastanza a lungo (es. Bitcoin prima del 2015) sono liquidita'."""
    regola = regola or regola_base
    giorno = g.date[i]
    pesi, info, esclusi = {}, {}, []
    az = profilo.get("az", 0)
    if az:
        # QUOTA AZIONI SCELTE: accesa solo se l'S&P 500 e' sopra la sua media a 200 giorni (filtro di MERCATO:
        # nel 2008 senza filtro la quota perdeva il 55%), altrimenti va in liquidita' come gli ETF in pausa.
        spy = g.p.get("SPY") or []
        fin = [v for v in spy[max(0, i - SMA):i] if v is not None]
        sma = sum(fin) / len(fin) if len(fin) >= SMA * 0.9 else None
        trend = round((spy[i - 1] / sma - 1) * 100, 1) if sma and spy[i - 1] else None
        if "SAT" not in g.p or g.p["SAT"][i - 1 if i else 0] is None:
            pesi["CASH"] = az                                   # dati delle azioni assenti: quota in liquidita'
            esclusi.append({"k": "AZ", "score": None, "trend": None, "base": round(az * 100, 1),
                            "motivo": "dati dell'Azionario non disponibili in questo aggiornamento: quota in liquidità"})
        elif sma and spy[i - 1] > sma:
            vol = _std([g.rend("SAT", j) for j in range(max(1, i - VOL_GIORNI), i)])
            pesi["AZ"] = az
            info["AZ"] = {"k": "AZ", "vol": (vol or 0) * math.sqrt(252), "score": None, "trend": trend, "base": az}
        else:
            pesi["CASH"] = az
            esclusi.append({"k": "AZ", "score": None, "trend": trend, "base": round(az * 100, 1),
                            "motivo": "S&P 500 sotto la media a 200 giorni: le 5 azioni scelte sono in pausa nella liquidità"})
    for k, w in profilo["base"].items():
        w = w * (1 - az)                                        # la base occupa cio' che resta dopo la quota azioni
        if k == "CASH":
            pesi["CASH"] = pesi.get("CASH", 0) + w
            continue
        t = TUTTI[k][1]
        if t not in g.p or g.n[t][i - 1 if i else 0] < MIN_STORIA:
            pesi["CASH"] = pesi.get("CASH", 0) + w            # mercato non ancora disponibile
            continue
        col = g.p[t]
        finestra = [v for v in col[max(0, i - SMA):i] if v is not None]
        sma = sum(finestra) / len(finestra) if len(finestra) >= SMA * 0.9 else None
        x = cot_al(sc.get(k), giorno)
        score = x[1] if x else None
        trend = round((col[i - 1] / sma - 1) * 100, 1) if sma else None
        if sma and regola(score if score is not None else 0, col[i - 1] > sma):
            vol = _std([g.rend(t, j) for j in range(max(1, i - VOL_GIORNI), i)])
            pesi[k] = pesi.get(k, 0) + w
            info[k] = {"k": k, "vol": (vol or 0) * math.sqrt(252), "score": score, "trend": trend, "base": w}
        else:
            pesi["CASH"] = pesi.get("CASH", 0) + w
            esclusi.append({"k": k, "score": score, "trend": trend, "base": round(w * 100, 1),
                            "motivo": "prezzo sotto la media a 200 giorni: peso in pausa nella liquidità"})
    pesi = {k: round(v, 4) for k, v in pesi.items() if v >= 0.005}
    return pesi, info, esclusi


def _ticker(k):
    """Chiave del portafoglio -> ticker dei prezzi (le chiavi del benchmark sono gia' ticker)."""
    return TUTTI[k][1] if k in TUTTI else k


def simula(g, pianificati, dal_i, al_i=None):
    """Valore del portafoglio giorno per giorno. pianificati = {indice giorno: {chiave: peso}}.
    I pesi derivano liberamente tra un ribilanciamento e l'altro (come in un conto reale)."""
    al_i = len(g.date) - 1 if al_i is None else al_i
    valore, curva, quote = 100.0, [], {}
    for i in range(dal_i, al_i + 1):
        if i in pianificati:
            nuovi = pianificati[i]
            tot = sum(quote.values()) or 1.0
            vecchi = {k: v / tot for k, v in quote.items()}
            scambio = sum(abs(nuovi.get(k, 0) - vecchi.get(k, 0)) for k in set(nuovi) | set(vecchi))
            valore *= (1 - COSTO * scambio)
            quote = {k: valore * w for k, w in nuovi.items()}
        elif quote:
            quote = {k: v * (1 + g.rend(_ticker(k), i)) for k, v in quote.items()}
            valore = sum(quote.values())
        curva.append((g.date[i], valore))
    return curva


def statistiche(curva):
    """CAGR, volatilita', drawdown massimo, peggior mese, % di mesi positivi (niente statistiche per anno solare:
    il portafoglio ruota ogni mese, il rischio si legge mese per mese)."""
    if len(curva) < 40:
        return None
    v = [x[1] for x in curva]
    anni = (date.fromisoformat(curva[-1][0]) - date.fromisoformat(curva[0][0])).days / 365.25
    r = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    picco, dd, dd_data = v[0], 0.0, curva[0][0]
    for d, x in curva:
        picco = max(picco, x)
        if x / picco - 1 < dd:
            dd, dd_data = x / picco - 1, d
    fine_mese = {}
    for d, x in curva:
        fine_mese[d[:7]] = x
    mesi = list(fine_mese.items())
    rm = [(mesi[i][0], mesi[i][1] / mesi[i - 1][1] - 1) for i in range(1, len(mesi))]
    pm = min(rm, key=lambda x: x[1]) if rm else None
    return {
        "dal": curva[0][0], "al": curva[-1][0],
        "cagr": round(((v[-1] / v[0]) ** (1 / anni) - 1) * 100, 1) if anni > 0.5 else None,
        "totale": round((v[-1] / v[0] - 1) * 100, 1),
        "vol": round((_std(r) or 0) * math.sqrt(252) * 100, 1),
        "maxdd": round(dd * 100, 1), "maxdd_data": dd_data,
        "peggior_mese": [pm[0], round(pm[1] * 100, 1)] if pm else None,
        "mesi_pos": round(100 * sum(1 for _, x in rm if x > 0) / len(rm)) if rm else None,
    }


def _settimanale(curva):
    """Un punto per settimana (l'ultimo giorno di ogni settimana): basta per il grafico e pesa poco."""
    out, sett = [], None
    for d, x in curva:
        s = date.fromisoformat(d).isocalendar()[:2]
        if s != sett:
            out.append([d, round(x, 2)])
            sett = s
        else:
            out[-1] = [d, round(x, 2)]
    return out


def _tagli(curva, dal=None, al=None):
    """Parte della curva tra due date, ribasata a 100."""
    c = [(d, x) for d, x in curva if (dal is None or d >= dal) and (al is None or d <= al)]
    return [(d, x * 100 / c[0][1]) for d, x in c] if c else []


MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]


def rischio_mese(g, pesi, mese, fino_a):
    """IL MESE DI CALENDARIO della rotazione (es. ottobre) in TUTTI gli anni dello storico, tenendo la composizione
    di oggi: per ogni anno rendimento del mese (dal primo giorno di borsa al primo del mese dopo) e caduta massima
    DENTRO il mese (dal punto piu' alto al piu' basso). Un mercato non ancora quotato quell'anno conta come
    liquidita' (o 0 se manca anche quella). fino_a = 'AAAA-MM' della rotazione attuale (esclusa: non e' finita).
    Restituisce {mese, anni: [{a, r, dd}], peggiore, media, positivi, n, dd_max, mercati: [{k, media, pos, n}]}."""
    inizi = {}
    for i, d in enumerate(g.date):
        inizi.setdefault(d[:7], i)
    chiavi = sorted(inizi)
    anni = []
    for j, ym in enumerate(chiavi[:-1]):
        if ym[5:] != mese or ym >= fino_a:
            continue
        i0, i1 = inizi[ym], inizi[chiavi[j + 1]]
        quote = []                                           # (peso, colonna prezzi) con prezzo noto al via
        for k, w in pesi.items():
            col = g.p.get(_ticker(k))
            if not col or col[i0] is None:
                col = g.p.get(LIQUIDITA[1])
            quote.append((w, col if col and col[i0] is not None else None))
        picco, dd, v = 1.0, 0.0, 1.0
        for i in range(i0, i1 + 1):
            v = sum(w * (c[i] / c[i0] if c else 1.0) for w, c in quote) / (sum(pesi.values()) or 1)
            picco = max(picco, v)
            dd = min(dd, v / picco - 1)
        anni.append({"a": int(ym[:4]), "r": round((v - 1) * 100, 1), "dd": round(dd * 100, 1)})
    if not anni:
        return None
    # stagionalita' di ogni mercato tenuto nello stesso mese (informativa)
    mercati = []
    for k in pesi:
        if k == "CASH":
            continue
        col = g.p.get(_ticker(k))
        rr = [col[inizi[chiavi[j + 1]]] / col[inizi[ym]] - 1 for j, ym in enumerate(chiavi[:-1])
              if ym[5:] == mese and ym < fino_a and col and col[inizi[ym]] is not None and g.n[_ticker(k)][inizi[ym]] > 20]
        if len(rr) >= 3:
            mercati.append({"k": k, "media": round(sum(rr) / len(rr) * 100, 1),
                            "pos": round(100 * sum(x > 0 for x in rr) / len(rr)), "n": len(rr)})
    r = [x["r"] for x in anni]
    peg = min(anni, key=lambda x: x["r"])
    return {"mese": MESI[int(mese) - 1], "anni": anni, "n": len(anni),
            "peggiore": [peg["a"], peg["r"]], "media": round(sum(r) / len(r), 1),
            "positivi": sum(x > 0 for x in r), "dd_max": min(x["dd"] for x in anni), "mercati": mercati}


# --------------------------------------------------------------------------- registro delle rotazioni live
def _registro(cartella):
    return os.path.join(cartella, "portafogli", "rotazioni_v2.json")


def leggi_rotazioni(cartella=CARTELLA):
    try:
        with open(_registro(cartella), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def registra(rotazioni, data, composizioni, cartella=CARTELLA, scrivi=True):
    """Aggiunge la rotazione del mese se non c'e' ancora. Le rotazioni gia' salvate non si toccano mai."""
    if any(r["data"] == data for r in rotazioni):
        return rotazioni
    rot = rotazioni + [{"data": data, "profili": {p: sorted(c.items()) for p, c in composizioni.items()}}]
    if scrivi:
        f = _registro(cartella)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(rot, fh, indent=1)
        os.replace(f + ".tmp", f)
    return rot


# --------------------------------------------------------------------------- controllo di freschezza + ultima copia buona
def usati():
    """Ticker che servono davvero alla scheda: mercati delle basi, liquidita' e benchmark."""
    return sorted({TUTTI[k][1] for p in PROFILI for k in p["base"]} | {t for t, _ in BENCH})


def controlla_prezzi(px, oggi=None):
    """Avviso per l'utente se i prezzi non sono aggiornati: None se tutto ok, altrimenti
    {"codice", "dal": ultimo giorno aggiornato, "mercati": ticker in ritardo o mancanti}.
    In ritardo = ultimo prezzo piu' vecchio di VECCHI_GIORNI giorni di calendario (copre weekend e festivi USA)."""
    oggi = oggi or date.today()
    limite = (oggi - timedelta(days=VECCHI_GIORNI)).isoformat()
    vecchi = [t for t in usati() if not px.get(t) or px[t][-1][0] < limite]
    if not vecchi:
        return None
    ultimi = [px[t][-1][0] for t in vecchi if px.get(t)]
    return {"codice": CODICE_ERRORE, "dal": min(ultimi) if ultimi else None, "mercati": vecchi, "quando": _adesso()}


def _adesso():
    """Data e ora italiane dell'anomalia ('AAAA-MM-GG HH:MM'), mostrate all'utente nel popup."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _ultimo_file(cartella):
    return os.path.join(cartella, "portafogli", "ultimo.json")


def salva_ultimo(dati, cartella=CARTELLA):
    """Copia dell'ultima scheda calcolata: se un giro successivo fallisce si mostra questa (con l'avviso)."""
    f = _ultimo_file(cartella)
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(dati, fh, separators=(",", ":"))
    os.replace(f + ".tmp", f)


def leggi_ultimo(cartella=CARTELLA):
    try:
        with open(_ultimo_file(cartella), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def di_riserva(cartella=CARTELLA, oggi=None):
    """Se il calcolo di oggi non e' riuscito: l'ultima scheda buona con l'avviso di manutenzione (o None)."""
    d = leggi_ultimo(cartella)
    if d:
        d["avviso"] = {"codice": CODICE_ERRORE, "dal": d.get("aggiornato"), "mercati": [], "quando": _adesso()}
    return d


# --------------------------------------------------------------------------- calcolo completo per la pagina
def serie_satellite(sat, date_borsa):
    """Prezzo giornaliero sintetico della quota "Azioni scelte" (ticker SAT) sulle date di borsa dello SPY.
    - storico simulato (rendimenti MENSILI di satellite.py): dentro ogni mese il rendimento e' distribuito in modo
      geometrico sui giorni di borsa (le oscillazioni dentro il mese di questa parte non si vedono: limite noto);
    - live: indice GIORNALIERO dei titoli registrati, attaccato all'ultimo valore dello storico.
    Restituisce [(data, prezzo)] o [] se i dati mancano."""
    if not sat or not sat.get("storico"):
        return []
    per_mese = {}
    for d in date_borsa:
        per_mese.setdefault(d[:7], []).append(d)
    rend = {m: r for m, r, *_ in sat["storico"]}
    mesi = sorted(rend)
    prima = [d for d in date_borsa if d[:7] < mesi[0]]
    if not prima:
        return []
    out, v = [(prima[-1], 100.0)], 100.0                    # base 100 all'ultimo giorno del mese prima
    for m in mesi:
        giorni = per_mese.get(m, [])
        for k, d in enumerate(giorni, 1):
            out.append((d, round(v * (1 + rend[m]) ** (k / len(giorni)), 5)))
        v *= 1 + rend[m]
    lv = sat.get("live") or []
    if lv:
        base, v0 = out[-1][1], lv[0][1] or 1.0
        out += [(d, round(base * x / v0, 5)) for d, x in lv if d > out[-1][0]]
    return out


def calcola(righe_cot, px, cartella=CARTELLA, scrivi=True, oggi=None, sat=None):
    """righe_cot = archivio COT; px = prezzi() (ticker -> punti); sat = satellite.json delle azioni scelte (o None:
    la quota va in liquidita'). Restituisce i dati della scheda "Portafogli" oppure None se mancano i prezzi di base
    (SPY e liquidita')."""
    if "SPY" not in px or LIQUIDITA[1] not in px:
        return None
    px_tutti = dict(px)
    ss = serie_satellite(sat, [d for d, _ in px["SPY"]])
    if ss:
        px_tutti["SAT"] = ss
    g = Griglia(px_tutti)
    sc = segnali_cot(righe_cot)
    giorni = date_ribilancio(g)
    if not giorni:
        return None
    ultimo_rib = giorni[-1]
    oggi = oggi or date.today()
    prossima = date(oggi.year + (oggi.month == 12), oggi.month % 12 + 1, 1)
    while prossima.weekday() >= 5:                 # primo giorno FERIALE del mese dopo (es. lunedi' 2 novembre)
        prossima += timedelta(days=1)
    prossima = prossima.isoformat()

    # benchmark 60/40 ribilanciato ogni mese
    bench = simula(g, {i: dict(BENCH) for i in giorni}, giorni[0]) if "IEF" in px else None

    rotazioni = leggi_rotazioni(cartella)
    out_prof, composizioni = [], {}
    # i 5 titoli del mese della rotazione (registrati dal vivo da satellite.py; prima del live: ultima scelta simulata)
    mese_rot = g.date[ultimo_rib][:7]
    satellite_n = (sat or {}).get("n") or 5
    reg = ((sat or {}).get("registro") or {}).get(mese_rot)
    ante = (sat or {}).get("anteprima") or None       # anteprima dei titoli del mese prossimo (provvisoria)
    if reg:
        titoli_az = [{"t": x["t"], "n": x["n"], "s": x["s"]} for x in reg["titoli"]]
    else:
        ult = [x for x in (sat or {}).get("storico") or [] if x[0] == mese_rot]
        titoli_az = [{"t": t, "n": t, "s": None} for t in (ult[0][2] if ult and len(ult[0]) > 2 else [])]
    for prof in PROFILI:
        piani, storia = {}, []
        for i in giorni:
            pesi, info, esclusi = scegli(prof, g, i, sc)
            piani[i] = pesi
            storia.append((g.date[i], pesi))
        curva = simula(g, piani, giorni[0])
        pesi, info, esclusi = scegli(prof, g, ultimo_rib, sc)
        composizioni[prof["id"]] = pesi
        # linea LIVE: pesi delle rotazioni salvate (mai ricalcolati)
        live = None
        if rotazioni:
            pl = {g.pos[r["data"]]: dict(r["profili"].get(prof["id"], [])) for r in rotazioni if r["data"] in g.pos}
            if pl:
                live = simula(g, pl, min(pl))
        comp = [{"k": k, "nome": TUTTI[k][2], "strumento": TUTTI[k][3], "classe": TUTTI[k][4],
                 "peso": round(w * 100, 1), "score": info.get(k, {}).get("score"),
                 "trend": info.get(k, {}).get("trend"), "vol": round(info[k]["vol"] * 100, 1) if k in info else None}
                for k, w in sorted(pesi.items(), key=lambda x: (x[0] == "CASH", -x[1]))]
        for c in comp:
            u = STRUMENTI_UE.get(c["k"])
            if u:
                c["ue"] = {"nome": u[0], "isin": u[1], "nota": u[2]}
            if c["k"] == "AZ":
                c["titoli"] = titoli_az
                c["peso_titolo"] = round(c["peso"] / satellite_n, 1)
                if ante and ante.get("titoli"):
                    c["anteprima"] = ante
        cambi = []
        for (d0, p0), (d1, p1) in zip(storia[-13:-1], storia[-12:]):
            a = set(k for k in p1 if k != "CASH")
            b = set(k for k in p0 if k != "CASH")
            cambi.append({"data": d1, "entrati": sorted(a - b), "usciti": sorted(b - a), "tenuti": sorted(a & b),
                          "liquidita": round(p1.get("CASH", 0) * 100)})
        out_prof.append({
            "id": prof["id"], "nome": prof["nome"], "descr": prof["descr"], "dd_rif": prof["dd"],
            "rischio": prof.get("rischio"), "az": round(prof.get("az", 0) * 100),
            "base": [{"k": k, "nome": TUTTI[k][2], "peso": round(w * (1 - prof.get("az", 0)) * 100)}
                     for k, w in prof["base"].items()] + ([{"k": "AZ", "nome": TUTTI["AZ"][2], "peso": round(prof["az"] * 100)}]
                                                          if prof.get("az") else []),
            "ammessi": [{"k": k, "nome": TUTTI[k][2]} for k in prof["ammessi"]],
            "composizione": comp, "esclusi": esclusi,
            "mese": rischio_mese(g, pesi, g.date[ultimo_rib][5:7], g.date[ultimo_rib][:7]),
            "stat": {"storico": statistiche(_tagli(curva, al=OOS_DAL)),
                     "oos": statistiche(_tagli(curva, dal=OOS_DAL)),
                     "totale": statistiche(curva),
                     "live": statistiche(live) if live else None},
            "curva": _settimanale(curva), "live_dal": live[0][0] if live else None,
            "rotazioni": list(reversed(cambi)),
        })
    registra(rotazioni, g.date[ultimo_rib], composizioni, cartella, scrivi=scrivi)
    avviso = controlla_prezzi(px, oggi)
    if avviso:          # ERRORE nel registro: l'admin riceve la mail (job "avviso-admin"), l'utente vede l'avviso
        log.error("portafogli: prezzi Yahoo non aggiornati dal %s (%s); falliti in questo giro: %s",
                  avviso["dal"], ", ".join(avviso["mercati"]), ", ".join(ESITO.get("falliti", [])) or "nessuno")
    out = {
        "aggiornato": g.date[-1], "rotazione": g.date[ultimo_rib], "prossima": prossima,
        "dal": g.date[giorni[0]], "oos_dal": OOS_DAL, "fonte": "Yahoo Finance (prezzi rettificati)",
        "profili": out_prof,
        "bench": {"nome": "60/40 (S&P 500 + Treasury 10 anni)", "curva": _settimanale(bench),
                  "stat": {"storico": statistiche(_tagli(bench, al=OOS_DAL)),
                           "oos": statistiche(_tagli(bench, dal=OOS_DAL)), "totale": statistiche(bench)}} if bench else None,
        "avviso": avviso,
        "azioni": {"live_dal": (sat or {}).get("live_dal"), "nota": (sat or {}).get("nota"),
                   "disponibili": bool(ss)},
    }
    if scrivi:
        salva_ultimo(out, cartella)
    return out
