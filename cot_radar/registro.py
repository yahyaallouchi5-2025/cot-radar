# -*- coding: utf-8 -*-
"""
registro.py - REGISTRO LIVE DEI SEGNALI: ogni segnale con data e ora vere, salvato per sempre e non modificabile.

Dove sta: storico/segnali/registro.jsonl (ramo "storico" del repository, come l'archivio dei prezzi).
Formato: una riga JSON per EVENTO (apertura, conferma, chiusura), solo in aggiunta: gli eventi passati non si
riscrivono mai.

CATENA DI HASH (anti-manomissione): ogni evento contiene l'impronta SHA-256 dell'evento precedente ("prec") e
la propria ("hash", calcolata su tutto il resto della riga). Cambiare anche una sola cifra di un evento vecchio
rompe la catena da li' in poi: il sito lo mostra subito ("catena NON integra") e il registro smette di scrivere
finche' l'admin non controlla. In piu' il ramo git conserva la cronologia di ogni salvataggio.

Quando si scrive:
  - solo con dati COMPLETI (COT e FRED online): con una fonte a meta' il punteggio cambierebbe per un motivo
    tecnico e nascerebbe un segnale finto;
  - solo se l'aggiornamento viene PUBBLICATO (main.py chiama salva() dopo il paracadute);
  - mai in modalita' demo o sul PC (lo scrive solo il sito, cosi' esiste un unico registro ufficiale).
Primo avvio: i segnali gia' attivi vengono registrati come "iniziali" e restano fuori dalle statistiche
(non sono nati in quel momento).

DEBUG: python -c "from cot_radar import registro; print(registro.verifica(registro.leggi())[:3])"
"""
import hashlib
import json
import os
from datetime import timezone

from . import motore, volatilita
from .eventi import Calendario as eventi_cal
from .config import PRICES, ROOT
from .log import log
from .stagionalita import prezzo_coppia

CARTELLA = os.path.join(ROOT, "storico", "segnali")
FILE = "registro.jsonl"
ZERO = "0" * 64
VERSIONE = 1
MAX_CHIUSI = 150                     # segnali chiusi mostrati nella pagina (le statistiche usano tutti)
SALTA_FX = set(k for k, v in PRICES.items() if v[0].startswith("DEX")) | {"DXY", "USD"}   # valute: gia' nelle coppie

_in_attesa = None                    # eventi calcolati in questo giro, scritti solo da salva()


def impronta(evento, prec):
    """SHA-256 dell'evento (senza il campo hash) concatenato all'impronta precedente."""
    corpo = {k: v for k, v in evento.items() if k != "hash"}
    corpo["prec"] = prec
    testo = json.dumps(corpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def leggi(cartella=CARTELLA):
    """Eventi in ordine. File assente = registro vuoto. Riga illeggibile = errore (non si scrive sopra)."""
    f = os.path.join(cartella, FILE)
    if not os.path.exists(f):
        return []
    with open(f, encoding="utf-8") as fh:
        return [json.loads(r) for r in fh if r.strip()]


def verifica(eventi):
    """Controlla la catena. Restituisce (integra, ultimo_hash, indice del primo evento sbagliato o None)."""
    prec = ZERO
    for i, e in enumerate(eventi):
        if e.get("prec") != prec or e.get("hash") != impronta(e, prec):
            return False, prec, i
        prec = e["hash"]
    return True, prec, None


def concatena(eventi, prec, primo_n):
    """Aggiunge numero progressivo, versione, prec e hash ai nuovi eventi."""
    out = []
    for k, e in enumerate(eventi):
        e = dict(e, n=primo_n + k, v=VERSIONE)
        e["prec"] = prec
        e["hash"] = impronta(e, prec)
        prec = e["hash"]
        out.append(e)
    return out


def _scrivi(cartella, eventi):
    """Scrittura atomica dell'intero file (file temporaneo + sostituzione)."""
    os.makedirs(cartella, exist_ok=True)
    f = os.path.join(cartella, FILE)
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        for e in eventi:
            fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    os.replace(tmp, f)


def strumenti(pairs, assets, prezzi):
    """{nome: dati} degli strumenti VERIFICABILI (con un prezzo storico): coppie e strumenti non valutari.
    Oro e argento restano fuori finche' non c'e' una fonte di prezzo gratuita affidabile."""
    out = {}
    for p in pairs:
        pts = prezzo_coppia(prezzi, p["base"], p["quote"])
        if pts:
            liv, perche = motore.affidabilita(p.get("affid"), p.get("comm_acc"), p.get("stag"), p["score"])
            out[p["pair"]] = {"etichetta": p["label"], "punteggio": p["score"], "affid": liv, "perche": perche,
                              "base": p["base"], "quote": p["quote"], "_pts": pts, "_cls": "fx"}
    for k, a in assets.items():
        if k in SALTA_FX or k not in prezzi:
            continue
        liv, perche = motore.affidabilita(a.get("affid"), a.get("comm_acc"), a.get("stag"), a["score"])
        out[k] = {"etichetta": a["label"], "punteggio": a["score"], "affid": liv, "perche": perche,
                  "_pts": prezzi[k], "_cls": motore.classe(k)}
    return out


def aggiorna(pairs, assets, prezzi, fonti, adesso, cot_data, cartella=CARTELLA, scrivi=True):
    """Calcola gli eventi nuovi (li tiene in attesa: li scrive salva()) e prepara la vista per la pagina.
    adesso = datetime UTC dell'aggiornamento; fonti = stato delle fonti; scrivi=False: solo lettura."""
    global _in_attesa
    _in_attesa = None
    eventi = leggi(cartella)
    integra, ultimo, rotto = verifica(eventi)
    if not integra:
        log.critical("registro segnali: catena di hash NON integra dall'evento %d: non scrivo nulla finche' "
                     "non viene controllato", rotto)
    strum = strumenti(pairs, assets, prezzi)
    completi = (fonti or {}).get("cot") == "online" and (fonti or {}).get("fred") == "online"
    nuovi = []
    if scrivi and integra and completi:
        _, aperti = motore.applica(eventi)
        correnti = {s: {k: v for k, v in d.items() if not k.startswith("_")} for s, d in strum.items()}
        quando = motore.utc_iso(adesso.astimezone(timezone.utc))
        nuovi = motore.transizioni(aperti, correnti, quando, cot_data, iniziale=not eventi)
        if nuovi:
            nuovi = concatena(nuovi, ultimo, len(eventi))
            _in_attesa = (cartella, eventi + nuovi)
            log.info("registro segnali: %d eventi nuovi (in attesa di pubblicazione)", len(nuovi))
    elif scrivi and integra:
        log.info("registro segnali: non aggiornato in questo giro (dati incompleti: %s)", fonti)
    return vista(eventi + nuovi, strum, integra, completi)


def salva():
    """Scrive gli eventi in attesa. Da chiamare SOLO dopo che l'aggiornamento e' stato approvato e pubblicato."""
    global _in_attesa
    if not _in_attesa:
        return 0
    cartella, eventi = _in_attesa
    try:
        _scrivi(cartella, eventi)
    except OSError as e:
        log.critical("registro segnali NON salvato (%s): gli eventi di questo giro andranno ricalcolati", e)
        return 0
    _in_attesa = None
    log.info("registro segnali salvato: %d eventi in totale", len(eventi))
    return len(eventi)


def vista(eventi, strum, integra, completi):
    """Dati per la pagina: segnali misurati (aperti + ultimi chiusi), statistiche e stato della catena."""
    segnali, _ = motore.applica(eventi)
    righe, misurati = [], []
    reg = volatilita.Regimi()
    for sid, s in segnali.items():
        d = strum.get(s["strumento"])
        s["vol"] = reg.al_segnale(s["strumento"], d["_pts"], s["generato"]) if d else None
        m = motore.misura(s, d["_pts"], d["_cls"]) if d else None
        cst = motore.costo(s["strumento"], s.get("base"), s.get("quote"))
        if not s.get("iniziale"):
            misurati.append((s, m, cst))
        righe.append({"id": sid, "strumento": s["strumento"], "etichetta": s["etichetta"], "verso": s["verso"],
                      "punteggio": s["punteggio"], "affid": s.get("affid"), "perche": s.get("perche"),
                      "generato": s["generato"], "generato_it": motore.ora_italia(s["generato"]),
                      "padre": s.get("padre"), "iniziale": s.get("iniziale", False), "conferme": s["conferme"],
                      "chiuso": dict(s["chiuso"], quando_it=motore.ora_italia(s["chiuso"]["quando"])) if s["chiuso"] else None,
                      "cls": d["_cls"] if d else None, "m": m, "vol": s.get("vol")})
    aperti = [r for r in righe if not r["chiuso"]]
    chiusi = sorted([r for r in righe if r["chiuso"]], key=lambda r: r["chiuso"]["quando"], reverse=True)
    padri = [x for x in misurati if not x[0].get("padre")]
    motore.prepara_eventi(misurati, eventi_cal())
    per_s = {}
    for x in padri:
        per_s.setdefault(x[0]["strumento"], []).append(x)
    unita = {k: motore.unita(k, d.get("base"), d.get("quote")) for k, d in strum.items()}

    def gruppi(lista, fn):
        g = {}
        for x in lista:
            g.setdefault(fn(x[0]), []).append(x)
        return {k: motore.riassunto(v) for k, v in sorted(g.items())}

    # stessa forma di un "periodo" del backtest (vedi backtest.py): la pagina li disegna con lo stesso codice
    stat = {"dd": {"tutti": motore.drawdown(padri),
                   "strumento": {k: motore.drawdown(v, unita.get(k)) for k, v in sorted(per_s.items())}},
            "riass": motore.riassunto(padri, varianti=True),
            "etichetta": gruppi(misurati, lambda s: s["etichetta"]),
            "affid": gruppi(padri, lambda s: s.get("affid") or "n/d"),
            "strumento": gruppi(padri, lambda s: s["strumento"]),
            "vol": gruppi(padri, lambda s: (s.get("vol") or {}).get("nome") or "n/d")}
    for r in righe:
        r["m"] = motore.snello(r["m"])
    return {"aperti": sorted(aperti, key=lambda r: r["generato"], reverse=True), "chiusi": chiusi[:MAX_CHIUSI],
            "n_chiusi": len(chiusi), "stat": stat, "dd_campi": motore.DD_CAMPI,
            "unita": {k: v[0] for k, v in unita.items()},
            "profilo": {k: motore.profilo(d["_pts"]) for k, d in strum.items()}, "eventi": len(eventi), "integra": integra,
            "ultimo_hash": eventi[-1]["hash"] if eventi else None, "completi": completi,
            "dal": motore.ora_italia(eventi[0]["generato"]) if eventi and eventi[0].get("generato") else None}
