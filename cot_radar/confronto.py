# -*- coding: utf-8 -*-
"""
confronto.py - IL BACKTEST DECIDE: le nuove letture COT migliorano davvero i segnali?

Domanda: oggi il punteggio usa il report Legacy "solo futures" (speculatori = Non-Commercial).
La CFTC pubblica anche:
  - Legacy COMBINED: stessi gruppi, ma con le OPZIONI convertite in futures equivalenti (delta);
  - TFF: per valute, indici, tassi e crypto separa Leveraged Funds (fondi veloci) e Asset Manager (fondi lenti);
  - DISAGGREGATED: per le materie prime separa i Managed Money (i veri speculatori).
Qui si rifa' il backtest con lo STESSO motore del sito (backtest.simula) cambiando solo chi conta come
"speculatore", e si confrontano i risultati sullo stesso periodo, con gli stessi costi. Niente pesi nuovi:
se una lettura non migliora sia lo sviluppo sia l'holdout, non entra nel sito.

Varianti (il resto non cambia: soglie, pesi, divergenza, Commercials dal Legacy):
  base = come oggi (Legacy solo futures)
  comb = Legacy futures + opzioni (anche i Commercials sono quelli "combined")
  lev  = TFF Leveraged Funds al posto dei Non-Commercial (solo dove esiste il TFF)
  am   = TFF Asset Manager al posto dei Non-Commercial
  mm   = Disaggregated Managed Money al posto dei Non-Commercial (materie prime)
Piu' un FILTRO: sui segnali di oggi, le opzioni degli speculatori (combined - solo futures) vanno a favore
o contro il segnale? Se "a favore" funziona meglio di "contro", le opzioni portano informazione.

Periodi:
  - "dal 2009": stesso periodo per tutte le varianti (TFF e Disaggregated partono a giugno 2006 e il COT Index
    usa 3 anni: prima di meta' 2009 l'indice non sarebbe completo);
  - "dal 1998": solo base, comb e filtro opzioni (il combined parte nel 1995).
  Ogni periodo e' diviso in sviluppo e HOLDOUT (ultimi 2 anni), come nella pagina.

LIMITE IMPORTANTE: si misura solo dove c'e' un prezzo storico (FRED): cambi, indici USA, petrolio, gas, crypto.
Oro, cereali e bestiame (dove le opzioni pesano di piu') non hanno un prezzo giornaliero gratuito: li' il
confronto non si puo' fare.

USO: python -m cot_radar.confronto [cartella archivio]   (di solito la cartella storico/, ramo "storico")
"""
import json
import os
import sys

from . import backtest, motore, storico
from .config import ASSETS, PRICES

DAL_COMUNE = "2009-07-01"       # tutte le varianti con COT Index completo (3 anni dopo l'inizio del TFF)
DAL_LUNGO = "1998-07-01"        # solo Legacy: combined dal 1995 + 3 anni di indice
SOGLIA_OPZ = 1.0                # differenza minima (punti % dell'open interest) per dire "a favore" o "contro"
SEDUTE = 5                      # uscita "in settimana" (5 sedute), come richiesto per chi chiude in settimana
CODICE = {a[0]: a[1] for a in ASSETS}
MAJORS = ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")

# colonne (long, short) della categoria usata come "speculatori" in ogni variante
CATEGORIA = {
    "comb": ("noncomm_positions_long_all", "noncomm_positions_short_all"),
    "lev": ("lev_money_positions_long", "lev_money_positions_short"),
    "am": ("asset_mgr_positions_long", "asset_mgr_positions_short"),
    "mm": ("m_money_positions_long_all", "m_money_positions_short_all"),
}
ARCHIVIO = {"comb": "COMB", "lev": "TFF", "am": "TFF", "mm": "DIS"}
NOMI = {"base": "Legacy solo futures (come oggi)", "comb": "Legacy futures + opzioni",
        "lev": "TFF Leveraged Funds (fondi veloci)", "am": "TFF Asset Manager (fondi lenti)",
        "mm": "Disaggregated Managed Money"}


def _num(x):
    """Testo CFTC -> numero, None se manca o non e' un numero."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mercati_variante(base, extra):
    """Codici dei mercati presenti sia nel Legacy sia nel report alternativo: solo questi cambiano."""
    return {r["cftc_contract_market_code"] for r in base} & {r["cftc_contract_market_code"] for r in extra}


def variante(base, extra, tipo):
    """Righe in formato Legacy (quelle che legge cot.cot_series) con la categoria 'tipo' come speculatori.
    I mercati senza report alternativo restano IDENTICI a oggi. Per i mercati che cambiano si usano SOLO le
    settimane del report alternativo (niente serie "cucite" a meta': il COT Index mescolerebbe due scale)."""
    lk, sk = CATEGORIA[tipo]
    tocca = mercati_variante(base, extra)
    comm = {(r["cftc_contract_market_code"], r["report_date_as_yyyy_mm_dd"][:10]):
            (r.get("comm_positions_long_all"), r.get("comm_positions_short_all")) for r in base}
    out = [r for r in base if r["cftc_contract_market_code"] not in tocca]
    for r in extra:
        c, d = r["cftc_contract_market_code"], r["report_date_as_yyyy_mm_dd"][:10]
        oi, lo, sh = _num(r.get("open_interest_all")), _num(r.get(lk)), _num(r.get(sk))
        if c not in tocca or not oi or lo is None or sh is None:
            continue
        # Commercials: dal Legacy della stessa settimana (nel combined, quelli "combined")
        cl, cs = (r.get("comm_positions_long_all"), r.get("comm_positions_short_all")) if tipo == "comb" \
            else comm.get((c, d), (None, None))
        out.append({"cftc_contract_market_code": c, "report_date_as_yyyy_mm_dd": d, "open_interest_all": oi,
                    "noncomm_positions_long_all": lo, "noncomm_positions_short_all": sh,
                    "comm_positions_long_all": cl, "comm_positions_short_all": cs})
    return out


def diff_opzioni(fo, co):
    """{codice: {martedi': punti %OI}} = netto degli speculatori in % OI CON le opzioni meno SENZA.
    Positivo = con le opzioni gli speculatori sono piu' long (o meno short) che con i soli futures."""
    def netti(righe):
        out = {}
        for r in righe:
            oi = _num(r.get("open_interest_all"))
            lo, sh = _num(r.get("noncomm_positions_long_all")), _num(r.get("noncomm_positions_short_all"))
            if oi and lo is not None and sh is not None:
                out[(r["cftc_contract_market_code"], r["report_date_as_yyyy_mm_dd"][:10])] = (lo - sh) / oi * 100
        return out
    a, b = netti(fo), netti(co)
    out = {}
    for k in a.keys() & b.keys():
        out.setdefault(k[0], {})[k[1]] = b[k] - a[k]
    return out


def gambe(s):
    """Codici CFTC che formano lo strumento. Il dollaro composito dipende da tutte le majors e dal DXY."""
    if s.get("base"):
        g = set()
        for v in (s["base"], s["quote"]):
            g |= {CODICE[m] for m in MAJORS} | {CODICE["DXY"]} if v == "USD" else {CODICE[v]}
        return g
    return {CODICE[s["strumento"]]}


def classe(s):
    """Gruppo di confronto: valute, indici, energia, crypto."""
    return "valute" if s.get("base") else {"indici": "indici", "energia": "energia", "crypto": "crypto"}.get(
        motore.classe(s["strumento"]), "altro")


def misure(lista):
    """Numeri del confronto per un gruppo di segnali, al netto dei costi:
    n, hit e resa media a 4 settimane, drawdown medio a 4 settimane, hit e resa uscendo dopo 5 sedute."""
    if not lista:
        return None
    st = motore.statistiche(lista, ("4s",)).get("4s")
    g = motore.giorni_stat(lista)
    g5 = g[SEDUTE - 1] if len(g) >= SEDUTE else None
    return {"n": len(lista),
            "hit4": st and st["hit"], "resa4": st and st["resa"], "mae4": st and st["mae"], "ic4": st and st["ic"],
            "hit5g": g5 and round(100 * g5[1] / g5[0]), "resa5g": g5 and round(g5[2] / g5[0], 3)}


def _tabella(misurati, limite_h, dal, filtro=None):
    """{periodo: {gruppo: misure}} per i segnali "padre" nati dal giorno 'dal' (sviluppo, holdout, tutti)."""
    padri = [x for x in misurati if not x[0].get("padre") and x[0]["generato"][:10] >= dal
             and (filtro is None or filtro(x[0]))]
    per = {"sviluppo": [x for x in padri if x[0]["generato"][:10] < limite_h],
           "holdout": [x for x in padri if x[0]["generato"][:10] >= limite_h]}
    per["tutti"] = per["sviluppo"] + per["holdout"]
    out = {}
    for p, lista in per.items():
        g = {"tutti": misure(lista)}
        for k in ("valute", "indici", "energia", "crypto"):
            g[k] = misure([x for x in lista if classe(x[0]) == k])
        out[p] = g
    return out


def lato_opzioni(s, diff):
    """Le opzioni degli speculatori vanno 'a favore', 'contro' o sono 'neutre' rispetto al segnale?
    Coppie: differenza della valuta base meno quella della quotata (il dollaro composito conta zero:
    sul DXY le opzioni sono circa 0%). None se manca il dato di quella settimana."""
    d, v = s.get("cot_data"), motore.verso(s["etichetta"])
    parti = [(s["base"], 1), (s["quote"], -1)] if s.get("base") else [(s["strumento"], 1)]
    tot, visto = 0.0, False
    for k, segno in parti:
        if k == "USD":
            continue
        x = diff.get(CODICE[k], {}).get(d)
        if x is None:
            return None
        tot, visto = tot + segno * x, True
    if not visto:
        return None
    return "a favore" if tot * v > SOGLIA_OPZ else "contro" if tot * v < -SOGLIA_OPZ else "neutre"


def esegui(cartella=storico.CARTELLA, log_print=print):
    """Tutto il confronto. Restituisce un dizionario (salvato anche in confronto.json nella cartella)."""
    archivio = {sid: storico.leggi(cartella, sid) for sid in sorted({v[0] for v in PRICES.values()})}
    prezzi = storico.prezzi_usd({k: v for k, v in archivio.items() if v})
    base = storico.leggi_cot(cartella)
    extra = {n: storico.leggi_extra(n, cartella) for n in ("COMB", "TFF", "DIS")}
    log_print(f"archivi: Legacy {len(base)} righe, " + ", ".join(f"{n} {len(v)}" for n, v in extra.items()))
    if not base or not prezzi:
        raise SystemExit("mancano l'archivio COT o i prezzi")

    sims = {"base": backtest.simula(base, prezzi)}
    for t in ("comb", "lev", "am", "mm"):
        righe = extra[ARCHIVIO[t]]
        if righe:
            log_print(f"simulazione {t} ...")
            sims[t] = backtest.simula(variante(base, righe, t), prezzi)
    limite_h = sims["base"]["limite_h"]

    out = {"holdout_dal": limite_h, "al": sims["base"]["ultima"], "nomi": NOMI, "periodi": {}}
    for nome_p, dal, varianti in (("dal 2009", DAL_COMUNE, sims), ("dal 1998", DAL_LUNGO,
                                                                   {k: sims[k] for k in ("base", "comb") if k in sims})):
        tab = {}
        for t, sim in varianti.items():
            # per ogni variante si guardano solo gli strumenti che cambiano davvero (gli altri sono identici a base)
            tocca = mercati_variante(base, extra[ARCHIVIO[t]]) if t != "base" else None
            filtro = (lambda s, tc=tocca: bool(gambe(s) & tc)) if tocca else None
            tab[t] = _tabella(sim["misurati"], limite_h, dal, filtro)
            if t != "base":   # base RISTRETTA agli stessi strumenti: il confronto giusto e' questo
                tab[t + "_base"] = _tabella(sims["base"]["misurati"], limite_h, dal, filtro)
        out["periodi"][nome_p] = tab

    # filtro opzioni sui segnali di oggi (base)
    if extra["COMB"]:
        diff = diff_opzioni(base, extra["COMB"])
        out["opzioni"] = {}
        for lato in ("a favore", "neutre", "contro"):
            out["opzioni"][lato] = _tabella(sims["base"]["misurati"], limite_h, DAL_LUNGO,
                                            lambda s, l=lato: lato_opzioni(s, diff) == l)
    with open(os.path.join(cartella, "confronto.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    return out


def stampa(out, log_print=print):
    """Tabella leggibile nel terminale: ogni variante accanto a "base" sugli STESSI strumenti."""
    def riga(nome, m):
        if not m:
            return f"  {nome:<26} {'-':>5}"
        return (f"  {nome:<26} {m['n']:>5}  hit4 {m['hit4']!s:>3}%  resa4 {m['resa4']!s:>7}%  dd4 {m['mae4']!s:>7}%"
                f"  | 5 sedute: hit {m['hit5g']!s:>3}%  resa {m['resa5g']!s:>7}%")
    log_print(f"holdout dal {out['holdout_dal']} al {out['al']} (rese al netto dei costi)")
    for nome_p, tab in out["periodi"].items():
        for per in ("sviluppo", "holdout"):
            log_print(f"\n=== {nome_p} - {per} ===")
            log_print(riga("base tutti", tab["base"][per]["tutti"]))
            for t in ("comb", "lev", "am", "mm"):
                if t not in tab:
                    continue
                for g in ("valute", "indici", "energia", "crypto"):
                    if tab[t][per][g]:
                        log_print(riga(f"{t} {g}", tab[t][per][g]))
                        log_print(riga(f"  base {g}", tab[t + "_base"][per][g]))
    if "opzioni" in out:
        for per in ("sviluppo", "holdout"):
            log_print(f"\n=== filtro opzioni (segnali di oggi, dal 1998) - {per} ===")
            for lato, tab in out["opzioni"].items():
                for g in ("tutti", "valute", "indici", "energia", "crypto"):
                    log_print(riga(f"{lato} {g}", tab[per][g]))


if __name__ == "__main__":
    stampa(esegui(sys.argv[1] if len(sys.argv) > 1 else storico.CARTELLA))
