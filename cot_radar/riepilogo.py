# -*- coding: utf-8 -*-
"""
riepilogo.py - RIEPILOGO SETTIMANALE DEI SEGNALI per il canale Telegram, diviso per categoria di asset.

Quando parte: ogni settimana, appena la dashboard ONLINE mostra un report COT nuovo (di solito il venerdi'
sera, dopo l'uscita del COT alle 15:30 di New York; se la CFTC slitta per una festivita', parte quando esce).
Lo decide notifiche.py confrontando la data COT della pagina con quella dell'ultimo riepilogo inviato.

Fonte: i dati della pagina pubblicata (la costante "D" dentro index.html), cioe' ESATTAMENTE quello che vede
chi apre la dashboard. Niente ricalcoli: il messaggio non puo' mai dire una cosa diversa dal sito.

Contenuto:
  - segnali attivi (BUY / SELL / STRONG) raggruppati per categoria: Forex (coppie) e poi i settori del COT;
    le singole valute non compaiono (si negoziano tramite le coppie del Forex);
  - per ogni segnale: direzione, punteggio, affidabilita' (stessa regola del badge del sito) e "nuovo"
    se e' nato con questo report;
  - segnali chiusi con questo report (tornati NEUTRO).

DEBUG: python -c "from cot_radar import riepilogo as r; d=r.scarica('https://utente.github.io/cot-radar/'); print(r.testi(d, '')[0])"
"""
import json
import time
import urllib.request

from . import motore
from .config import SECTORS
from .log import log

ORDINE = ["Forex"] + [s for s in SECTORS if s != "Valute"]
SALTA = {"Valute"}                    # forza delle singole valute: gia' rappresentata dalle coppie del Forex


def scarica(sito, timeout=30):
    """Dati della pagina pubblicata (dizionario D) oppure None. Il parametro r evita copie vecchie in cache."""
    if not sito:
        return None
    try:
        with urllib.request.urlopen(f"{sito.rstrip('/')}/?r={int(time.time())}", timeout=timeout) as r:
            html = r.read().decode("utf-8")
        inizio = html.index("const D=") + len("const D=")
        dati, _ = json.JSONDecoder().raw_decode(html, inizio)
        return dati
    except (OSError, ValueError) as e:
        log.warning("dati della dashboard non letti (%s): riepilogo rimandato", type(e).__name__)
        return None


def data_cot(dati):
    """Data (martedi') del report COT mostrato dalla dashboard."""
    return max((a.get("date") or "" for a in (dati or {}).get("assets", {}).values()), default="") or None


def _affid(x):
    liv, _ = motore.affidabilita(x.get("affid") if isinstance(x.get("affid"), dict) else None,
                                 x.get("comm_acc"), x.get("stag"), x.get("score") or 0)
    return liv


def segnali(dati):
    """{categoria: [segnale]} dei segnali attivi + lista dei chiusi. Ogni segnale: nome, etichetta, punteggio,
    affid, nuovo. Ordine: categorie come ORDINE, dentro ogni categoria dal punteggio piu' forte."""
    attivi, chiusi = {}, []
    assets = dati.get("assets") or {}
    valute = {k for k, a in assets.items() if a.get("group") == "Valute"} | {"USD"}
    # Forex = solo coppie di VALUTE: le coppie dei metalli (es. SILVER/USD) sono gia' nella categoria Metalli
    voci = [("Forex", f"{p['base']}/{p['quote']}", p, p.get("prev")) for p in dati.get("pairs") or []
            if p.get("base") in valute and p.get("quote") in valute]
    voci += [(a.get("group") or "Altro", a.get("it") or a.get("name") or k, a, a.get("prev_label"))
             for k, a in assets.items()]
    for cat, nome, x, prima in voci:
        if cat in SALTA:
            continue
        lab = x.get("label") or "NEUTRO"
        if lab == "NEUTRO":
            if prima and prima != "NEUTRO":
                chiusi.append({"nome": nome, "prima": prima, "cat": cat})
            continue
        attivi.setdefault(cat, []).append({"nome": nome, "etichetta": lab, "punteggio": x.get("score"),
                                           "affid": _affid(x), "nuovo": bool(x.get("new"))})
    for v in attivi.values():
        v.sort(key=lambda s: -abs(s["punteggio"] or 0))
    ordinate = sorted(attivi, key=lambda c: (ORDINE.index(c) if c in ORDINE else len(ORDINE), c))
    return {c: attivi[c] for c in ordinate}, chiusi


def testi(dati, sito, test=False):
    """Messaggi HTML pronti per Telegram (lista: divisa solo se supera il limite)."""
    from .notifiche import _escape, _freccia, _punti, escape, impagina   # evita l'import circolare
    attivi, chiusi = segnali(dati)
    cot = data_cot(dati)
    n = sum(len(v) for v in attivi.values())
    testa = (("[TEST] " if test else "") + "<b>Edge Board · segnali della settimana</b>\n<i>" +
             (f"COT del {cot[8:10]}/{cot[5:7]}/{cot[:4]} · " if cot else "") +
             f"{n} segnali attivi</i>\n▲ acquisto · ▼ vendita · ★ nuovo con questo report\n\n")
    blocchi = []
    for cat, lista in attivi.items():
        righe = [f"<b>{escape(cat.upper())}</b>"]
        for s in lista:
            righe.append(f"{_freccia(s['etichetta'])} {escape(s['nome'])}: <b>{escape(s['etichetta'])}</b> "
                         f"{_punti(s['punteggio'])} · affid. {escape(s['affid'])}" + (" ★" if s["nuovo"] else ""))
        blocchi.append("\n".join(righe))
    if chiusi:
        blocchi.append("<b>CHIUSI CON QUESTO REPORT</b>\n" +
                       "\n".join(f"■ {escape(c['nome'])}: era {escape(c['prima'])}, ora NEUTRO" for c in chiusi))
    if not blocchi:
        blocchi.append("Nessun segnale attivo questa settimana.")
    piede = "\n\n" + (f'<a href="{_escape(sito.rstrip("/"))}/">Apri la dashboard</a>\n' if sito else "") + \
        "<i>Informazione statistica dalla dashboard pubblica, non consulenza finanziaria.</i>"
    return impagina(testa, blocchi, piede)
