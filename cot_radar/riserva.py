"""
riserva.py - FONTI DI RISERVA quando FRED non risponde (manutenzione, chiave errata, rete lenta...).

Idea: FRED non "produce" i dati, li raccoglie da altri enti pubblici. Se FRED e' fermo, chiediamo
gli stessi numeri direttamente a chi li pubblica (tutti gratuiti, senza chiave):

  serie FRED       fonte originale                         note
  ---------------  --------------------------------------  ------------------------------------------
  DGS2, DGS10      Tesoro USA (curva dei rendimenti)       stessi identici valori di FRED
  DFII10           Tesoro USA (curva dei rendimenti reali)
  T10YIE           calcolata: DGS10 - DFII10               inflazione attesa = nominale - reale
  VIXCLS           CBOE (chi calcola il VIX)
  RRPONTSYD        Federal Reserve di New York             reverse repo overnight
  WTREGEN          Tesoro USA (Daily Treasury Statement)   conto del Tesoro (TGA), saldo di fine giornata
  MORTGAGE30US     Freddie Mac (sondaggio PMMS)            stessi valori di FRED
  DEX... (cambi)   BCE (cambi di riferimento in euro)      convertiti in dollari: scarto minimo (orario diverso)
  CBBTCUSD/ETH     Coinbase (chiusura giornaliera)

Restano SENZA riserva (si usa la copia salvata): WALCL (bilancio Fed), indici azionari, petrolio, gas,
dollaro DTWEXBGS, spread high yield.

Regola: un solo giro di richieste per fonte (niente tentativi ripetuti). Se una fonte non risponde la saltiamo.
DEBUG: python main.py --debug -> righe "riserva ...".
"""
import csv
import io
import json
import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger("cot_radar")

TESORO = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
          "{y}/all?type={tipo}&field_tdr_date_value={y}&page&_format=csv")
VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate={a}&endDate={b}"
TGA_URL = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance"
           "?fields=record_date,account_type,open_today_bal&page%5Bsize%5D=10000&filter=")
PMMS_URL = "https://www.freddiemac.com/pmms/docs/PMMS_history.csv"
COINBASE = "https://api.exchange.coinbase.com/products/{p}/candles?granularity=86400&start={a}&end={b}"

# cambi FRED -> (valuta BCE, verso). La BCE da' "unita' di valuta per 1 euro" (es. USD 1.08 = 1 EUR vale 1.08 $).
#   "usd_per": dollari per 1 unita' di valuta (EURUSD, GBPUSD, AUDUSD, NZDUSD)
#   "per_usd": unita' di valuta per 1 dollaro (USDJPY, USDCHF, ...)
CAMBI = {
    "DEXUSEU": ("EUR", "usd_per"), "DEXUSUK": ("GBP", "usd_per"), "DEXUSAL": ("AUD", "usd_per"),
    "DEXUSNZ": ("NZD", "usd_per"), "DEXJPUS": ("JPY", "per_usd"), "DEXSZUS": ("CHF", "per_usd"),
    "DEXCAUS": ("CAD", "per_usd"), "DEXMXUS": ("MXN", "per_usd"), "DEXBZUS": ("BRL", "per_usd"),
    "DEXSFUS": ("ZAR", "per_usd"),
}


def _mdy(s):
    """'10/20/2026' o '4/2/1971' -> '2026-10-20' (None se non e' una data)."""
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _colonna(header, *nomi):
    """Posizione della prima colonna il cui nome (senza maiuscole/spazi) e' tra 'nomi'."""
    h = [c.strip().strip('"').lower() for c in header]
    for n in nomi:
        if n in h:
            return h.index(n)
    raise RuntimeError("colonna %s non trovata (intestazione: %s)" % (nomi, header[:8]))


def tesoro(http, since):
    """Rendimenti nominali (2 e 10 anni) e reali (10 anni) dal Tesoro USA: un file per anno."""
    out = {"DGS2": {}, "DGS10": {}, "DFII10": {}}
    for y in range(int(since[:4]), date.today().year + 1):
        for tipo, col in (("daily_treasury_yield_curve", {"DGS2": "2 yr", "DGS10": "10 yr"}),
                          ("daily_treasury_real_yield_curve", {"DFII10": "10 yr"})):
            try:                                     # un file che manca non deve far perdere gli altri
                rows = list(csv.reader(io.StringIO(http(TESORO.format(y=y, tipo=tipo)))))
            except Exception as e:
                log.debug("riserva Tesoro %s %s: %s", tipo, y, e)
                continue
            if not rows:
                continue
            idx = {sid: _colonna(rows[0], c) for sid, c in col.items()}
            for r in rows[1:]:
                d = _mdy(r[0]) if r else None
                if d and d >= since:
                    for sid, i in idx.items():
                        v = _num(r[i]) if i < len(r) else None
                        if v is not None:
                            out[sid][d] = v
    # inflazione attesa (breakeven) = rendimento nominale - rendimento reale, stesso giorno
    out["T10YIE"] = {d: round(v - out["DFII10"][d], 2) for d, v in out["DGS10"].items() if d in out["DFII10"]}
    if not any(out.values()):
        raise RuntimeError("nessun dato dal Tesoro USA")
    return out


def vix(http, since):
    rows = list(csv.reader(io.StringIO(http(VIX_URL))))
    i = _colonna(rows[0], "close")
    return {"VIXCLS": {d: _num(r[i]) for r in rows[1:] if r and (d := _mdy(r[0])) and d >= since and _num(r[i]) is not None}}


def rrp(http, since):
    """Reverse repo NY Fed: importo accettato in dollari -> miliardi (come FRED RRPONTSYD)."""
    j = json.loads(http(RRP_URL.format(a=since, b=date.today().isoformat())))
    out = {}
    for o in j.get("repo", {}).get("operations", []):
        v = _num(o.get("totalAmtAccepted"))
        if o.get("operationDate") and v is not None:
            out[o["operationDate"]] = out.get(o["operationDate"], 0) + v / 1e9   # piu' operazioni nello stesso giorno: somma
    return {"RRPONTSYD": out}


def tga(http, since):
    """Saldo di fine giornata del conto del Tesoro (milioni $, come FRED WTREGEN)."""
    f = f"record_date:gte:{since},account_type:eq:Treasury General Account (TGA) Closing Balance"
    j = json.loads(http(TGA_URL + urllib.parse.quote(f, safe=":,")))
    return {"WTREGEN": {r["record_date"]: _num(r["open_today_bal"]) for r in j.get("data", [])
                        if _num(r.get("open_today_bal")) is not None}}


def mutuo_usa(http, since):
    rows = list(csv.reader(io.StringIO(http(PMMS_URL))))
    i = _colonna(rows[0], "pmms30")
    return {"MORTGAGE30US": {d: _num(r[i]) for r in rows[1:]
                             if r and (d := _mdy(r[0])) and d >= since and _num(r[i]) is not None}}


def cambi(get_ecb, since):
    """Cambi BCE (valuta per 1 euro) -> cambi in dollari come quelli FRED."""
    valute = "+".join(sorted({"USD"} | {v[0] for v in CAMBI.values() if v[0] != "EUR"}))
    dati = get_ecb("EXR", f"D.{valute}.EUR.SP00.A", since[:7])
    serie = {k.split(".")[2]: dict(v) for k, v in dati.items()}       # "EXR.D.JPY.EUR.SP00.A" -> "JPY"
    usd = serie.get("USD", {})
    out = {}
    for sid, (cur, verso) in CAMBI.items():
        out[sid] = {}
        for d, u in usd.items():
            c = 1.0 if cur == "EUR" else serie.get(cur, {}).get(d)
            if c and u and d >= since:
                out[sid][d] = round(u / c, 6) if verso == "usd_per" else round(c / u, 6)
    return out


def cripto(http, since):
    """Chiusure giornaliere Coinbase (max 300 candele per richiesta -> blocchi da 300 giorni)."""
    out = {}
    for sid, prod in (("CBBTCUSD", "BTC-USD"), ("CBETHUSD", "ETH-USD")):
        out[sid] = {}
        a = date.fromisoformat(since)
        while a < date.today():
            b = min(a + timedelta(days=299), date.today())
            for t, _lo, _hi, _op, close, _vol in json.loads(http(COINBASE.format(p=prod, a=a.isoformat(), b=b.isoformat()))):
                out[sid][datetime.fromtimestamp(t, timezone.utc).date().isoformat()] = close
            a = b + timedelta(days=1)
    return out


def scarica(mancanti, since, http, get_ecb):
    """Scarica dalle fonti di riserva SOLO le serie che servono ('mancanti').
    Restituisce ({serie: [[data, valore], ...]}, {fonte: errore})."""
    fonti = [
        ("Tesoro USA", {"DGS2", "DGS10", "DFII10", "T10YIE"}, lambda: tesoro(http, since)),
        ("CBOE", {"VIXCLS"}, lambda: vix(http, since)),
        ("NY Fed", {"RRPONTSYD"}, lambda: rrp(http, since)),
        ("Tesoro USA (TGA)", {"WTREGEN"}, lambda: tga(http, since)),
        ("Freddie Mac", {"MORTGAGE30US"}, lambda: mutuo_usa(http, since)),
        ("BCE cambi", set(CAMBI), lambda: cambi(get_ecb, since)),
        ("Coinbase", {"CBBTCUSD", "CBETHUSD"}, lambda: cripto(http, since)),
    ]
    da_fare = [(n, s, f) for n, s, f in fonti if s & set(mancanti)]
    dati, errori = {}, {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futuri = [(n, s, ex.submit(f)) for n, s, f in da_fare]
        for nome, serie, fu in futuri:
            try:
                for sid, punti in fu.result().items():
                    if sid in mancanti and punti:
                        dati[sid] = sorted([d, v] for d, v in punti.items())
                log.info("riserva %-16s ok: %s", nome, ", ".join(sorted(s for s in serie if s in dati)) or "nessuna serie")
            except Exception as e:                   # una fonte giu' non ferma le altre
                errori[nome] = str(e) or type(e).__name__
                log.warning("riserva %s non disponibile: %s", nome, errori[nome])
    return dati, errori
