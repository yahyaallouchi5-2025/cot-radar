# -*- coding: utf-8 -*-
"""
notizie.py - MOTORE NOTIZIE (fase 1): eventi macro ad alto impatto e il loro effetto sul segnale COT.

Idea (vedi anche la scheda "Metodo"):
  * il COT dice la DIREZIONE per le prossime settimane; una notizia (CPI, NFP, Fed, BCE) muove il prezzo
    per ore o pochi giorni: cambia soprattutto il TEMPISMO e il RISCHIO, raramente la direzione;
  * PRIMA dell'evento: nessun cambio, solo l'avviso "evento oggi/domani" sulle valute coinvolte;
  * DOPO l'evento: misuriamo la SORPRESA dal mercato stesso (fase 1, dati gratuiti): di quanto si e' mosso
    il tasso a 2 anni della valuta nel giorno dell'evento rispetto a una giornata normale (z-score).
    Tassi in forte salita = sorpresa "falco" = valuta piu' forte; in forte discesa = valuta piu' debole.
    Fase 2 (con una fonte a pagamento come FMP): sorpresa = (dato - attese) / deviazione tipica.
  * il correttivo ha un TETTO (una notizia da sola non ribalta un segnale forte) e DECADE:
    si dimezza ogni ~1 giorno per i dati, ~3 giorni per le banche centrali.

Calendario: dalla v6.20 arriva dall'agenda automatica (agenda.py, financecalendar.com). Quello scritto qui
sotto e' la RISERVA, usata solo se l'agenda non e' disponibile (orari locali dell'ente).
"""
import math
from datetime import date, datetime, timedelta

from .calcoli import clip
from .calendario import _last_sunday, et_to_utc, utc_to_it, utcnow
from .config import K_Y2

# (data, ora, minuti, fuso "ET" New York / "CET" Francoforte, nome breve, valuta, tipo)
#   tipo "dato" = dato macro (effetto breve), "banca" = decisione di banca centrale (effetto piu' lungo)
CALENDARIO = [
    # --- USA: inflazione CPI (BLS, 08:30 New York)
    ("2026-11-10", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2026-12-10", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-01-13", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-02-11", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-03-10", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-04-13", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-05-12", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-06-10", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-07-14", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-08-11", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-09-14", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-10-14", 8, 30, "ET", "CPI USA", "USD", "dato"),
    ("2027-11-10", 8, 30, "ET", "CPI USA", "USD", "dato"), ("2027-12-10", 8, 30, "ET", "CPI USA", "USD", "dato"),
    # --- USA: occupazione NFP (BLS, 08:30 New York)
    ("2026-11-06", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2026-12-04", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-01-08", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-02-05", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-03-05", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-04-02", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-05-07", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-06-04", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-07-02", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-08-06", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-09-03", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-10-08", 8, 30, "ET", "NFP USA", "USD", "dato"),
    ("2027-11-05", 8, 30, "ET", "NFP USA", "USD", "dato"), ("2027-12-03", 8, 30, "ET", "NFP USA", "USD", "dato"),
    # --- USA: decisione Fed (FOMC, 14:00 New York; il 2027 e' provvisorio)
    ("2026-10-28", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"), ("2026-12-09", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"),
    ("2027-01-27", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"), ("2027-03-17", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"),
    ("2027-04-28", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"), ("2027-06-09", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"),
    ("2027-07-28", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"), ("2027-09-15", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"),
    ("2027-10-27", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"), ("2027-12-08", 14, 0, "ET", "Fed (FOMC)", "USD", "banca"),
    # --- Eurozona: decisione BCE (14:15 Francoforte, conferenza stampa 14:45)
    ("2026-10-29", 14, 15, "CET", "BCE", "EUR", "banca"), ("2026-12-17", 14, 15, "CET", "BCE", "EUR", "banca"),
    ("2027-02-04", 14, 15, "CET", "BCE", "EUR", "banca"), ("2027-03-18", 14, 15, "CET", "BCE", "EUR", "banca"),
    ("2027-04-29", 14, 15, "CET", "BCE", "EUR", "banca"), ("2027-06-10", 14, 15, "CET", "BCE", "EUR", "banca"),
    ("2027-07-22", 14, 15, "CET", "BCE", "EUR", "banca"), ("2027-09-09", 14, 15, "CET", "BCE", "EUR", "banca"),
    ("2027-10-28", 14, 15, "CET", "BCE", "EUR", "banca"), ("2027-12-16", 14, 15, "CET", "BCE", "EUR", "banca"),
]
DIMEZZAMENTO = {"dato": 1.0, "banca": 3.0}    # giorni in cui l'effetto della sorpresa si dimezza
TETTO = 30                                    # massimo correttivo (punti) per valuta
PUNTI_PER_Z = 10                              # 1 deviazione standard di sorpresa = 10 punti
DURATA = 7                                    # dopo 7 giorni l'evento non conta piu'


def _utc(ev):
    """Evento -> data/ora UTC."""
    d = date.fromisoformat(ev[0])
    if ev[3] == "UTC":                                   # eventi dall'agenda (agenda.py): orario gia' in UTC
        return datetime(d.year, d.month, d.day, ev[1], ev[2])
    if ev[3] == "ET":
        return et_to_utc(d, ev[1], ev[2])
    estate = _last_sunday(d.year, 3) <= d < _last_sunday(d.year, 10)          # Francoforte: CET/CEST
    return datetime(d.year, d.month, d.day, ev[1], ev[2]) - timedelta(hours=2 if estate else 1)


def _serie_tasso(valuta, fred, ecb):
    """Tasso a 2 anni giornaliero della valuta: USA = DGS2 (FRED o Tesoro), Eurozona = curva BCE."""
    if valuta == "USD":
        return fred.get("DGS2") or []
    if valuta == "EUR":
        return ecb.get(K_Y2) or []
    return []


def sorpresa_mercato(giorno, serie):
    """z-score della variazione del tasso a 2 anni nel giorno 'giorno' rispetto agli ultimi ~250 giorni.
    None se il dato del giorno non c'e' ancora (es. FRED fermo e riserva non aggiornata)."""
    d = {x[0]: x[1] for x in serie}
    date_ord = sorted(d)
    if giorno not in d:
        return None
    i = date_ord.index(giorno)
    if i < 30:
        return None
    var = [d[date_ord[j]] - d[date_ord[j - 1]] for j in range(max(1, i - 250), i)]   # variazioni PRIMA dell'evento
    sd = math.sqrt(sum(v * v for v in var) / len(var)) if var else 0
    if not sd:
        return None
    oggi = d[giorno] - d[date_ord[i - 1]]
    return round(oggi / sd, 2), round(oggi * 100, 1)                   # (z, variazione in punti base)


def motore(fred, ecb, adesso=None, calendario=None):
    """Restituisce {"prossimi": [...eventi entro 7 giorni...], "valute": {valuta: {adj, oggi, eventi}}}.
    adj = correttivo in punti per la VALUTA (positivo = valuta piu' forte), gia' decaduto nel tempo.
    calendario = eventi principali dall'agenda (agenda.calendario_motore); None o vuoto = CALENDARIO qui sopra."""
    adesso = adesso or utcnow()
    prossimi, valute = [], {}
    for ev in (calendario or CALENDARIO):
        t = _utc(ev)
        giorni = (adesso - t).total_seconds() / 86400            # >0 = gia' uscito
        v = valute.setdefault(ev[5], {"adj": 0.0, "oggi": [], "eventi": []})
        ora_it = utc_to_it(t)
        etichetta = f"{ev[4]} {ora_it:%d/%m %H:%M}"
        if -7 <= giorni < 0:                                     # nei prossimi 7 giorni
            prossimi.append({"quando": ora_it.strftime("%Y-%m-%d %H:%M"), "nome": ev[4], "valuta": ev[5], "tipo": ev[6]})
            if giorni > -1.5:                                    # oggi o domani: avviso di rischio
                v["oggi"].append(etichetta)
        elif 0 <= giorni <= DURATA:                              # uscito da poco: misuriamo la sorpresa
            s = sorpresa_mercato(ev[0], _serie_tasso(ev[5], fred, ecb))
            if s is None:
                v["eventi"].append({"nome": etichetta, "z": None, "pb": None, "peso": None})
                continue
            z, pb = s
            peso = 0.5 ** (giorni / DIMEZZAMENTO[ev[6]])         # decadimento: meta' effetto ogni N giorni
            v["adj"] += z * PUNTI_PER_Z * peso
            v["eventi"].append({"nome": etichetta, "z": z, "pb": pb, "peso": round(peso, 2)})
    for v in valute.values():
        v["adj"] = round(clip(v["adj"], -TETTO, TETTO), 1)
    return {"prossimi": sorted(prossimi, key=lambda x: x["quando"]), "valute": valute}


def applica(pairs, assets, motore_out):
    """Aggiunge a ogni coppia la riga "Notizie": correttivo = (valuta base - valuta quotata) / 2,
    stesso schema del punteggio della coppia. Il segnale COT NON viene cambiato: mostriamo il punteggio
    corretto accanto, cosi' si vede sempre da dove arriva."""
    val = motore_out["valute"]
    for p in pairs:
        vb, vq = val.get(p["base"], {}), val.get(p["quote"], {})
        adj = round(((vb.get("adj") or 0) - (vq.get("adj") or 0)) / 2, 1)
        oggi = (vb.get("oggi") or []) + (vq.get("oggi") or [])
        eventi = (vb.get("eventi") or []) + (vq.get("eventi") or [])
        if not adj and not oggi and not eventi:
            p["news"] = None
            continue
        effetto = "neutro" if abs(adj) < 3 else ("rafforza" if (adj > 0) == (p["score"] > 0) else "penalizza")
        p["news"] = {"adj": adj, "score": round(clip(p["score"] + adj, -100, 100), 1), "effetto": effetto,
                     "oggi": oggi, "eventi": eventi}
    for k in ("USD", "EUR"):
        if k in assets and k in val:
            assets[k]["news"] = val[k]
