# -*- coding: utf-8 -*-
"""
fondamentali.py - BILANCI DELLE AZIENDE USA (fatturato, utile, anni in perdita, debito netto) dalla SEC

IDEA
  Nella scheda Azionario, aprendo un titolo USA (S&P 500 e Nasdaq-100) si vede la "salute" dell'azienda negli
  ultimi 5 anni fiscali: ricavi, utile netto, anni in perdita, debito, liquidita', debito netto e un giudizio
  semplice (SOLIDA / NELLA MEDIA / INDEBITATA). Fonte gratuita e ufficiale: la SEC (l'ente di vigilanza della borsa
  USA), API "companyfacts" con i dati XBRL dei bilanci depositati (moduli 10-K annuali).

RITARDO (perche' i dati non sono "di oggi")
  Le aziende depositano il bilancio annuale (10-K) 60-90 giorni dopo la fine dell'anno fiscale, le trimestrali
  (10-Q) 40-45 giorni dopo il trimestre. La SEC pubblica i dati pochi minuti dopo il deposito. Qui si usano gli
  ANNUALI, riscaricati una volta a settimana per titolo (giorno fisso per titolo, sparso sui 5 giorni feriali):
  un bilancio nuovo compare al massimo una settimana dopo il deposito.

REGOLE DELLA SEC (rispettate)
  - User-Agent con nome del servizio e un contatto email (obbligatorio): Secret SEC_CONTATTO del workflow;
    senza contatto il modulo NON scarica nulla (lo dice nel registro) e la scheda mostra "non disponibile".
  - Massimo 10 richieste al secondo: qui una ogni 0,15 secondi.

GIUDIZIO (semplice e spiegato nella scheda)
  - SOLIDA: utile positivo in tutti gli anni disponibili (almeno 3) e debito netto <= 3 volte l'utile medio
    (o liquidita' maggiore del debito);
  - INDEBITATA: patrimonio netto negativo, oppure debito netto > 6 volte l'utile medio, oppure utile medio <= 0
    con debito netto positivo;
  - NELLA MEDIA: tutto il resto. Banche e assicurazioni: il debito fa parte del mestiere, il giudizio sul debito
    non si applica (settore "fin") e conta solo la continuita' degli utili.

USCITA (nel ramo "azioni", copiata nel sito): pubblico/bilanci/<T>.json e pubblico/bilanci.json (indice).
DEBUG: python -c "from cot_radar import fondamentali; help(fondamentali.estrai)"
"""
import json
import os
import time
import urllib.request
import zlib
from datetime import date, timedelta

from . import azioni as A
from .log import log

URL_CIK = "https://www.sec.gov/files/company_tickers.json"
URL_FATTI = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ANNI = 5
PAUSA = 0.15
GIORNI_CIK = 7                  # la tabella ticker -> CIK si riscarica una volta a settimana
# concetti XBRL (us-gaap) in ordine di preferenza: il primo con un valore per quell'anno vince
RICAVI = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
          "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense",
          "TotalRevenuesAndOtherIncome", "InterestAndDividendIncomeOperating"]
UTILE = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
DEBITO_TOT = ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"]
DEBITO_LUNGO = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
DEBITO_BREVE = ["LongTermDebtCurrent", "DebtCurrent"]
CASSA = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
         "CashAndDueFromBanks"]
PN = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]


def _ua():
    c = os.environ.get("SEC_CONTATTO", "").strip()
    return f"BoardEdge (analisi di mercato) {c}" if "@" in c else None


def _get(url, ua, timeout=40, tentativi=3):
    for n in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            log.warning("SEC %s: HTTP %s (tentativo %d/%d)", url.rsplit("/", 1)[-1], e.code, n + 1, tentativi)
        except Exception as e:
            log.warning("SEC %s: %s (tentativo %d/%d)", url.rsplit("/", 1)[-1], type(e).__name__, n + 1, tentativi)
        time.sleep(2 * (3 ** n))
    return None


# --------------------------------------------------------------------------- estrazione dai "companyfacts"
def _annuali(fatti, concetti, durata=True):
    """{data di fine anno fiscale: valore} dal primo concetto utile. Solo bilanci annuali (10-K, fp=FY).
    durata=True per i flussi (ricavi, utile: periodo di ~1 anno), False per i saldi (debito, cassa: a una data).
    Per la stessa data vince il valore depositato per ULTIMO (le correzioni successive)."""
    usgaap = (fatti or {}).get("facts", {}).get("us-gaap", {})
    out = {}                                               # data di fine -> (valore, depositato il, priorita')
    for prio, c in enumerate(concetti):                    # in ordine di preferenza: un concetto dopo non sovrascrive
        for f in (usgaap.get(c) or {}).get("units", {}).get("USD") or []:
            if not str(f.get("form", "")).startswith("10-K") or f.get("fp") != "FY" or f.get("val") is None:
                continue
            fine = f.get("end")
            if not fine:
                continue
            if durata:
                ini = f.get("start")
                if not ini:
                    continue
                giorni = (date.fromisoformat(fine) - date.fromisoformat(ini)).days
                if not 330 <= giorni <= 400:                # solo periodi di circa un anno (no trimestri, no cumulati)
                    continue
            cur = out.get(fine)
            if cur is None or (cur[2] == prio and f.get("filed", "") >= cur[1]):
                out[fine] = (f["val"], f.get("filed", ""), prio)
    return {k: v[0] for k, v in out.items()}


def estrai(fatti, settore=None):
    """Sintesi degli ultimi ANNI anni fiscali: {anni: [{a, fine, ricavi, utile, debito, cassa, pn, dn}], perdite,
    crescita (% annua dei ricavi), giudizio, motivo}. None se mancano ricavi o utile."""
    ric, ut = _annuali(fatti, RICAVI), _annuali(fatti, UTILE)
    if not ric or not ut:
        return None
    dt, dl, db = _annuali(fatti, DEBITO_TOT, False), _annuali(fatti, DEBITO_LUNGO, False), _annuali(fatti, DEBITO_BREVE, False)
    cs, pn = _annuali(fatti, CASSA, False), _annuali(fatti, PN, False)
    fini = sorted(set(ric) & set(ut))[-ANNI:]
    anni = []
    for f in fini:
        deb = dt.get(f)
        if deb is None and (f in dl or f in db):
            deb = (dl.get(f) or 0) + (db.get(f) or 0)
        cassa = cs.get(f)
        anni.append({"a": int(f[:4]), "fine": f, "ricavi": ric[f], "utile": ut[f], "debito": deb, "cassa": cassa,
                     "pn": pn.get(f), "dn": (deb or 0) - (cassa or 0) if deb is not None or cassa is not None else None})
    if len(anni) < 2:
        return None
    perdite = sum(1 for x in anni if x["utile"] < 0)
    n = len(anni) - 1
    crescita = round(((anni[-1]["ricavi"] / anni[0]["ricavi"]) ** (1 / n) - 1) * 100, 1) \
        if anni[0]["ricavi"] and anni[-1]["ricavi"] and anni[0]["ricavi"] > 0 and anni[-1]["ricavi"] > 0 else None
    giudizio, motivo = _giudizio(anni, perdite, settore)
    return {"anni": anni, "perdite": perdite, "crescita": crescita, "giudizio": giudizio, "motivo": motivo}


def _giudizio(anni, perdite, settore):
    medio = sum(x["utile"] for x in anni) / len(anni)
    ult = anni[-1]
    dn, pn = ult.get("dn"), ult.get("pn")
    finanza = settore == "fin"
    if not finanza and pn is not None and pn < 0:
        return "INDEBITATA", "patrimonio netto negativo (i debiti superano il valore di tutto l'attivo)"
    if not finanza and dn is not None and medio <= 0 and dn > 0:
        return "INDEBITATA", "utile medio negativo e debiti superiori alla liquidita'"
    if not finanza and dn is not None and medio > 0 and dn > 6 * medio:
        return "INDEBITATA", f"debito netto pari a {dn / medio:.1f} anni di utile medio"
    if perdite == 0 and len(anni) >= 3 and (finanza or dn is None or dn <= 3 * medio):
        if finanza:
            return "SOLIDA", "utile in tutti gli anni (banca/assicurazione: il debito fa parte dell'attivita')"
        return "SOLIDA", "utile in tutti gli anni e " + ("piu' liquidita' che debiti" if dn is not None and dn <= 0
                                                          else f"debito netto ripagabile in {max(dn, 0) / medio:.1f} anni di utile")
    return "NELLA MEDIA", ((f"{perdite} anno" if perdite == 1 else f"{perdite} anni") + f" in perdita su {len(anni)}" if perdite else "utile costante ma debito netto superiore a 3 anni di utile")


# --------------------------------------------------------------------------- giro settimanale
def _cik(cartella, ua, oggi):
    f = os.path.join(cartella, "sec_cik.json")
    c = A._leggi(f) or {}
    if c.get("agg", "") < (oggi - timedelta(days=GIORNI_CIK)).isoformat() or not c.get("mappa"):
        dati = _get(URL_CIK, ua)
        if dati:
            c = {"agg": oggi.isoformat(), "mappa": {v["ticker"].upper(): int(v["cik_str"]) for v in dati.values()}}
            A._scrivi(f, c)
    return c.get("mappa") or {}


def titoli_usa(el=None):
    """Titoli USA dell'elenco (S&P 500 e Nasdaq-100: niente suffisso di borsa estera)."""
    return [x for x in (el if el is not None else A.elenco()) if ("sp500" in x["l"] or "ndx" in x["l"]) and "." not in x["t"]]


def aggiorna(cartella, oggi=None, el=None, scarica=None, pausa=PAUSA):
    """Riscarica (al massimo una volta a settimana per titolo) e scrive pubblico/bilanci/<T>.json + bilanci.json.
    Restituisce {ok, aggiornati, falliti, saltato}. Mai bloccante per il resto del workflow."""
    oggi = oggi or date.today()
    ua = _ua()
    if not ua and scarica is None:
        log.warning("bilanci SEC: manca il Secret SEC_CONTATTO (email richiesta dalla SEC): nessun download")
        return {"ok": 0, "aggiornati": 0, "falliti": [], "saltato": True}
    get = scarica or (lambda url: _get(url, ua))
    mappa = _cik(cartella, ua, oggi) if scarica is None else (scarica("CIK") or {})
    usa = titoli_usa(el)
    indice, aggiornati, falliti = {}, 0, []
    for x in usa:
        t = x["t"]
        f = os.path.join(cartella, "pubblico", "bilanci", A._nome_file(t) + ".json")
        vecchio = A._leggi(f) or {}
        giorno = zlib.crc32(("sec" + t).encode()) % 5                     # ogni titolo il suo giorno della settimana
        scaduto = vecchio.get("agg", "") < (oggi - timedelta(days=8)).isoformat()
        if not vecchio or (oggi.weekday() == giorno and vecchio.get("agg") != oggi.isoformat()) or scaduto:
            cik = mappa.get(t.upper()) or mappa.get(t.upper().replace("-", "."))
            fatti = get(URL_FATTI.format(cik=cik)) if cik else None
            if pausa and cik:
                time.sleep(pausa)
            sintesi = estrai(fatti, x.get("s")) if fatti else None
            if sintesi:
                vecchio = dict(sintesi, t=t, agg=oggi.isoformat(), fonte="SEC EDGAR (10-K)")
                A._scrivi(f, vecchio)
                aggiornati += 1
            else:
                falliti.append(t)
        if vecchio.get("anni"):
            u = vecchio["anni"][-1]
            indice[t] = {"g": vecchio["giudizio"], "p": vecchio["perdite"], "c": vecchio.get("crescita"), "a": u["a"]}
    A._scrivi(os.path.join(cartella, "pubblico", "bilanci.json"), {"aggiornato": oggi.isoformat(), "titoli": indice})
    if falliti:
        log.warning("bilanci SEC: %d titoli senza dati (%s%s)", len(falliti), ", ".join(falliti[:15]), "..." if len(falliti) > 15 else "")
    log.info("bilanci SEC: %d titoli con bilancio, %d aggiornati oggi", len(indice), aggiornati)
    return {"ok": len(indice), "aggiornati": aggiornati, "falliti": falliti, "saltato": False}
