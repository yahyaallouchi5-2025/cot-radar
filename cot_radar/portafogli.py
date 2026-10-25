# -*- coding: utf-8 -*-
"""
portafogli.py - TRE PORTAFOGLI MODELLO A ROTAZIONE MENSILE (solo acquisto, strumenti spot tipo ETF/ETC)

IDEA
  L'investitore sceglie un profilo (conservativo, moderato, aggressivo) e ogni mese riceve la lista di cosa
  tenere e con che peso. Il profilo decide QUALI mercati sono ammessi e QUANTO rischio si accetta
  (volatilita' obiettivo -> drawdown storico atteso). Ogni ~30 giorni (primo giorno di borsa del mese) il
  portafoglio ruota: restano i mercati ancora favorevoli, escono gli altri, entrano i nuovi.

REGOLE (fissate PRIMA di guardare i risultati, uguali per tutti i periodi: niente ottimizzazione sul passato)
  1. Universo = mercati del report COT che si possono comprare a pronti con un ETF/ETC (indici, Treasury,
     metalli, energia, cereali, crypto). Prezzi giornalieri rettificati (dividendi inclusi) da Yahoo Finance.
  2. Un mercato entra solo se, alla data del ribilanciamento:
       - il punteggio COT (stesso calcolo del sito, solo report gia' pubblicati) e' da BUY (>= NORMAL), e
       - il prezzo e' sopra la sua media a 200 giorni (trend a favore).
     Solo acquisti: un segnale SELL significa "fuori", il peso va in liquidita' (Treasury 1-3 anni).
  3. Pesi: inversamente proporzionali alla volatilita' degli ultimi 3 mesi (chi oscilla meno pesa di piu'),
     con un tetto per singolo mercato; poi tutto il portafoglio viene ridotto fino alla volatilita'
     obiettivo del profilo. Il resto resta in liquidita'. Nessuna leva.
  4. Costi: 0,10% sul capitale che cambia a ogni ribilanciamento.

VERIFICA ONESTA
  - STORICO: dal primo anno con dati sufficienti fino al 31/12/2015;
  - FUORI CAMPIONE (OOS): dal 2016 a oggi, con le STESSE regole (mai ritoccate guardando questo periodo);
  - LIVE: dalla prima rotazione pubblicata sul sito. Ogni rotazione viene salvata nell'archivio
    (storico/portafogli/rotazioni.json) e non viene mai riscritta: la linea live non si puo' "aggiustare".

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
BENCH = (("SPY", 0.6), ("IEF", 0.4))          # confronto: classico 60% azioni USA + 40% Treasury, ribilanciato
TUTTI = {u[0]: u for u in UNIVERSO + [LIQUIDITA]}

# I tre profili: mercati ammessi, volatilita' obiettivo (annua), tetto per mercato, drawdown di riferimento
_BASE = ["SP500", "DOW", "EAFE", "US10Y", "USBOND", "GOLD"]
_MEDIO = _BASE + ["NASDAQ", "RUSSELL", "EM", "SILVER", "COPPER", "WTI"]
PROFILI = [
    {"id": "conservativo", "nome": "Conservativo", "vol": 0.05, "tetto": 0.30, "dd": 10, "ammessi": _BASE,
     "descr": "Azioni dei grandi indici, Treasury e oro. Oscillazioni contenute: si accetta di guadagnare meno "
              "in cambio di cadute più piccole."},
    {"id": "moderato", "nome": "Moderato", "vol": 0.09, "tetto": 0.25, "dd": 18, "ammessi": _MEDIO,
     "descr": "Aggiunge tecnologia, piccole aziende, mercati emergenti, argento, rame e petrolio. Equilibrio tra "
              "crescita e cadute."},
    {"id": "aggressivo", "nome": "Aggressivo", "vol": 0.15, "tetto": 0.25, "dd": 25,
     "ammessi": [u[0] for u in UNIVERSO], "tetti": {"BTC": 0.10, "ETH": 0.07, "NATGAS": 0.10},
     "descr": "Tutto l'universo, crypto comprese. Punta alla crescita accettando cadute ampie e mesi negativi "
              "più frequenti."},
]
INIZIO = "2006-01-01"          # primo ribilanciamento (prima i dati degli ETF sono troppo pochi)
OOS_DAL = "2016-01-01"         # da qui in poi: fuori campione
COSTO = 0.001                  # 0,10% del capitale scambiato
SMA = 200                      # media mobile del filtro di trend (giorni di borsa)
VOL_GIORNI = 63                # finestra della volatilita' (circa 3 mesi)
MIN_STORIA = 260               # giorni di prezzo minimi perche' un mercato sia ammesso


# --------------------------------------------------------------------------- dati Yahoo (con copia locale)
def scarica_yahoo(ticker, timeout=30):
    """Prezzi giornalieri RETTIFICATI (dividendi e frazionamenti inclusi): [(data, prezzo)], None se fallisce."""
    q = urllib.parse.urlencode({"period1": 0, "period2": int(time.time()), "interval": "1d",
                                "events": "div,split", "includeAdjustedClose": "true"})
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
        return sorted(out.items()) or None
    except Exception as e:                       # rete, formato cambiato, limite di richieste...
        log.warning("Yahoo %s non disponibile (%s)", ticker, type(e).__name__)
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
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]]:
        vecchi = _leggi(cartella, t)
        if meta.get(t) != oggi and scarica:
            nuovi = scarica(t)
            if pausa:
                time.sleep(pausa)
            if nuovi and len(nuovi) >= 0.95 * len(vecchi) and (not vecchi or nuovi[-1][0] >= vecchi[-1][0]):
                _scrivi(cartella, t, nuovi)
                vecchi, meta[t], cambiato = nuovi, oggi, True
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
    for t in [u[1] for u in UNIVERSO] + [LIQUIDITA[1]]:
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


def scegli(profilo, g, i, sc):
    """Composizione del profilo al giorno i: [(chiave, peso)] (liquidita' compresa) + dettagli per la pagina."""
    giorno = g.date[i]
    scelti, esclusi = [], []
    for k in profilo["ammessi"]:
        t = TUTTI[k][1]
        if t not in g.p or g.n[t][i - 1 if i else 0] < MIN_STORIA:
            continue                                       # mercato non ancora quotato abbastanza a lungo
        col = g.p[t]
        x = cot_al(sc.get(k), giorno)
        finestra = [v for v in col[max(0, i - SMA):i] if v is not None]
        sma = sum(finestra) / len(finestra) if len(finestra) >= SMA * 0.9 else None
        ultimo = col[i - 1]
        trend = round((ultimo / sma - 1) * 100, 1) if sma else None
        if x is None or sma is None:
            continue
        if x[1] >= NORMAL and ultimo > sma:
            vol = _std([g.rend(t, j) for j in range(max(1, i - VOL_GIORNI), i)])
            if vol:
                scelti.append({"k": k, "vol": vol * math.sqrt(252), "score": x[1], "trend": trend, "cot_data": x[0]})
        else:
            motivo = ("posizionamento COT non da acquisto" if x[1] < NORMAL else "prezzo sotto la media a 200 giorni")
            esclusi.append({"k": k, "score": x[1], "trend": trend, "motivo": motivo})
    pesi = {}
    if scelti:
        inv = {s["k"]: 1 / s["vol"] for s in scelti}
        tot = sum(inv.values())
        tetti = profilo.get("tetti", {})
        pesi = {k: v / tot for k, v in inv.items()}
        for _ in range(10):                              # tetti per mercato: l'eccesso va agli altri sotto il tetto
            sopra = {k: w for k, w in pesi.items() if w > tetti.get(k, profilo["tetto"]) + 1e-9}
            if not sopra:
                break
            liberi = {k: w for k, w in pesi.items() if k not in sopra}
            eccesso = sum(w - tetti.get(k, profilo["tetto"]) for k, w in sopra.items())
            for k in sopra:
                pesi[k] = tetti.get(k, profilo["tetto"])
            if not liberi:
                break                                     # tutti al tetto: l'eccesso andra' in liquidita'
            tl = sum(liberi.values())
            for k, w in liberi.items():
                pesi[k] = w + eccesso * w / tl
        # volatilita' del portafoglio (covarianze degli ultimi 3 mesi) -> riduzione alla volatilita' obiettivo
        ks = list(pesi)
        R = {k: [g.rend(TUTTI[k][1], j) for j in range(max(1, i - VOL_GIORNI), i)] for k in ks}
        m = {k: sum(v) / len(v) for k, v in R.items()}
        n = min(len(v) for v in R.values())
        var = 0.0
        for a in ks:
            for b in ks:
                cov = sum((R[a][j] - m[a]) * (R[b][j] - m[b]) for j in range(n)) / max(1, n - 1)
                var += pesi[a] * pesi[b] * cov
        vol_p = math.sqrt(max(var, 0) * 252)
        scala = min(1.0, profilo["vol"] / vol_p) if vol_p > 0 else 1.0
        pesi = {k: w * scala for k, w in pesi.items()}
    pesi = {k: round(w, 4) for k, w in pesi.items() if w >= 0.005}
    resto = round(max(0.0, 1 - sum(pesi.values())), 4)
    if resto >= 0.005:
        pesi["CASH"] = resto                              # liquidita' solo se c'e' davvero
    info = {s["k"]: s for s in scelti}
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
    """CAGR, volatilita', drawdown massimo, peggior mese e anno, % di mesi positivi."""
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
    fine_anno = {}
    for d, x in curva:
        fine_anno[d[:4]] = x
    an = list(fine_anno.items())
    ra = [(an[i][0], an[i][1] / an[i - 1][1] - 1) for i in range(1, len(an))]
    pm = min(rm, key=lambda x: x[1]) if rm else None
    pa = min(ra, key=lambda x: x[1]) if ra else None
    return {
        "dal": curva[0][0], "al": curva[-1][0],
        "cagr": round(((v[-1] / v[0]) ** (1 / anni) - 1) * 100, 1) if anni > 0.5 else None,
        "totale": round((v[-1] / v[0] - 1) * 100, 1),
        "vol": round((_std(r) or 0) * math.sqrt(252) * 100, 1),
        "maxdd": round(dd * 100, 1), "maxdd_data": dd_data,
        "peggior_mese": [pm[0], round(pm[1] * 100, 1)] if pm else None,
        "peggior_anno": [pa[0], round(pa[1] * 100, 1)] if pa else None,
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


# --------------------------------------------------------------------------- registro delle rotazioni live
def _registro(cartella):
    return os.path.join(cartella, "portafogli", "rotazioni.json")


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


# --------------------------------------------------------------------------- calcolo completo per la pagina
def calcola(righe_cot, px, cartella=CARTELLA, scrivi=True, oggi=None):
    """righe_cot = archivio COT; px = prezzi() (ticker -> punti). Restituisce i dati della scheda "Portafogli"
    oppure None se mancano i prezzi di base (SPY e liquidita')."""
    if "SPY" not in px or LIQUIDITA[1] not in px:
        return None
    g = Griglia(px)
    sc = segnali_cot(righe_cot)
    giorni = date_ribilancio(g)
    if not giorni:
        return None
    ultimo_rib = giorni[-1]
    oggi = oggi or date.today()
    prossima = (date(oggi.year + (oggi.month == 12), oggi.month % 12 + 1, 1)).isoformat()

    # benchmark 60/40 ribilanciato ogni mese
    bench = simula(g, {i: dict(BENCH) for i in giorni}, giorni[0]) if "IEF" in px else None

    rotazioni = leggi_rotazioni(cartella)
    out_prof, composizioni = [], {}
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
        cambi = []
        for (d0, p0), (d1, p1) in zip(storia[-13:-1], storia[-12:]):
            a = set(k for k in p1 if k != "CASH")
            b = set(k for k in p0 if k != "CASH")
            cambi.append({"data": d1, "entrati": sorted(a - b), "usciti": sorted(b - a), "tenuti": sorted(a & b),
                          "liquidita": round(p1.get("CASH", 0) * 100)})
        out_prof.append({
            "id": prof["id"], "nome": prof["nome"], "descr": prof["descr"], "dd_rif": prof["dd"],
            "vol_obiettivo": round(prof["vol"] * 100), "ammessi": [{"k": k, "nome": TUTTI[k][2]} for k in prof["ammessi"]],
            "composizione": comp, "esclusi": esclusi,
            "stat": {"storico": statistiche(_tagli(curva, al=OOS_DAL)),
                     "oos": statistiche(_tagli(curva, dal=OOS_DAL)),
                     "totale": statistiche(curva),
                     "live": statistiche(live) if live else None},
            "curva": _settimanale(curva), "live_dal": live[0][0] if live else None,
            "rotazioni": list(reversed(cambi)),
        })
    registra(rotazioni, g.date[ultimo_rib], composizioni, cartella, scrivi=scrivi)
    return {
        "aggiornato": g.date[-1], "rotazione": g.date[ultimo_rib], "prossima": prossima,
        "dal": g.date[giorni[0]], "oos_dal": OOS_DAL, "fonte": "Yahoo Finance (prezzi rettificati)",
        "profili": out_prof,
        "bench": {"nome": "60/40 (S&P 500 + Treasury 10 anni)", "curva": _settimanale(bench),
                  "stat": {"storico": statistiche(_tagli(bench, al=OOS_DAL)),
                           "oos": statistiche(_tagli(bench, dal=OOS_DAL)), "totale": statistiche(bench)}} if bench else None,
    }
