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
  - per ogni segnale: direzione, punteggio e "nuovo" se e' nato con questo report
    (l'affidabilita' NON compare su Telegram: scelta del proprietario);
  - segnali chiusi con questo report (tornati NEUTRO).

DEBUG: python -c "from cot_radar import riepilogo as r; d=r.scarica('https://utente.github.io/cot-radar/'); print(r.testi(d, '')[0])"
"""
import html
import json
import time
import urllib.request

from .config import SECTORS
from .log import log

ORDINE = ["Forex"] + [s for s in SECTORS if s != "Valute"]
SALTA = {"Valute"}                    # forza delle singole valute: gia' rappresentata dalle coppie del Forex


def scarica(sito, timeout=30):
    """Dati della pagina pubblicata (dizionario D) oppure None. Il parametro r evita copie vecchie in cache."""
    if not sito:
        return None
    try:
        # il terminale sta in /terminale/ (v6.17); la radice e' la landing page
        with urllib.request.urlopen(f"{sito.rstrip('/')}/terminale/?r={int(time.time())}", timeout=timeout) as r:
            html = r.read().decode("utf-8")
        inizio = html.index("const D=") + len("const D=")
        dati, _ = json.JSONDecoder().raw_decode(html, inizio)
        return dati
    except (OSError, ValueError) as e:
        log.warning("dati della dashboard non letti (%s): riepilogo rimandato", type(e).__name__)
        return None


def scarica_verifica(sito, dati, timeout=30):
    """Registro dei segnali misurati (verifica.json, caricato dalla pagina solo quando serve) oppure None.
    Serve al riepilogo del venerdi' per dire "come stanno andando i segnali"; se non si legge, quel blocco manca."""
    try:
        nome = (dati or {}).get("verifica") or "verifica.json"
        with urllib.request.urlopen(f"{sito.rstrip('/')}/terminale/{nome}", timeout=timeout) as r:
            return (json.load(r) or {}).get("reg")
    except (OSError, ValueError, AttributeError) as e:
        log.warning("verifica.json non letto (%s): il riepilogo esce senza il blocco 'come vanno i segnali'", type(e).__name__)
        return None


def _vinto(m):
    """True/False se il segnale e' in guadagno/perdita secondo l'ultima misura disponibile, None se non misurato."""
    a = (m or {}).get("A") or {}
    x = a.get("fine") or (list(a.values())[-1] if a else None)
    return x.get("vinto") if isinstance(x, dict) else None


def andamento(reg, adesso=None):
    """Blocco "come stanno andando i segnali" dal registro pubblico: segnali aperti ora (non iniziali) in guadagno,
    e segnali chiusi negli ultimi 7 giorni con esito positivo. Restituisce None se non ci sono dati."""
    from datetime import datetime, timedelta, timezone
    if not reg:
        return None
    adesso = adesso or datetime.now(timezone.utc).replace(tzinfo=None)
    aperti = [_vinto(r.get("m")) for r in reg.get("aperti") or [] if not r.get("iniziale")]
    aperti = [v for v in aperti if v is not None]
    recenti = []
    for r in reg.get("chiusi") or []:
        try:
            q = datetime.strptime(r["chiuso"]["quando"], "%Y-%m-%dT%H:%MZ")
        except (KeyError, TypeError, ValueError):
            continue
        if adesso - q <= timedelta(days=7) and not r.get("iniziale"):
            v = _vinto(r.get("m"))
            if v is not None:
                recenti.append(v)
    righe = []
    if aperti:
        righe.append(f"Segnali aperti: {sum(aperti)} su {len(aperti)} in guadagno al momento.")
    if recenti:
        righe.append(f"Chiusi negli ultimi 7 giorni: {sum(recenti)} su {len(recenti)} in guadagno.")
    return ("\n".join(righe) + "\nLe statistiche complete e il registro verificabile sono nel terminale.") if righe else None


def in_breve(dati, attivi, chiusi, verifica=None):
    """Racconto breve in testa al riepilogo del venerdi': 3-4 frasi tutte ricavate dai dati (numeri, segnali piu'
    forti, andamento, prossima rotazione del portafoglio)."""
    n = sum(len(v) for v in attivi.values())
    nuovi = sum(1 for v in attivi.values() for s in v if s["nuovo"])
    frasi = [f"{n} segnali attivi" + (f", {nuovi} nati con questo report" if nuovi else "") +
             (f", {len(chiusi)} chiusi" if chiusi else "") + "."]
    top = sorted((s for v in attivi.values() for s in v), key=lambda s: -abs(s["punteggio"] or 0))[:2]
    if top:
        frasi.append("I più forti: " + ", ".join(f"{html.escape(s['nome'], quote=False)} {s['etichetta']} ({_punti_it(s['punteggio'])})" for s in top) + ".")
    a = andamento(verifica)
    if a:
        frasi.append(a.split("\n")[0])
    pros = (dati.get("port") or {}).get("prossima")
    if pros:
        frasi.append(f"Prossima rotazione dei portafogli: {pros[8:10]}/{pros[5:7]}.")
    return "<b>🎯 In breve</b>\n" + " ".join(frasi)


def _punti_it(p):
    return f"{p:+.1f}".replace(".", ",") if isinstance(p, (int, float)) else "n.d."


def data_cot(dati):
    """Data (martedi') del report COT mostrato dalla dashboard."""
    return max((a.get("date") or "" for a in (dati or {}).get("assets", {}).values()), default="") or None


def segnali(dati):
    """{categoria: [segnale]} dei segnali attivi + lista dei chiusi. Ogni segnale: nome, etichetta, punteggio,
    nuovo. Ordine: categorie come ORDINE, dentro ogni categoria dal punteggio piu' forte."""
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
                                           "nuovo": bool(x.get("new"))})
    for v in attivi.values():
        v.sort(key=lambda s: -abs(s["punteggio"] or 0))
    ordinate = sorted(attivi, key=lambda c: (ORDINE.index(c) if c in ORDINE else len(ORDINE), c))
    return {c: attivi[c] for c in ordinate}, chiusi


def testi(dati, sito, test=False, verifica=None):
    """Messaggi HTML pronti per Telegram (lista: divisa solo se supera il limite)."""
    from .notifiche import _escape, _freccia, _punti, escape, impagina   # evita l'import circolare
    attivi, chiusi = segnali(dati)
    cot = data_cot(dati)
    n = sum(len(v) for v in attivi.values())
    testa = (("[TEST] " if test else "") + "<b>BoardEdge · segnali della settimana</b>\n<i>" +
             (f"COT del {cot[8:10]}/{cot[5:7]}/{cot[:4]} · " if cot else "") +
             f"{n} segnali attivi</i>\n▲ acquisto · ▼ vendita · ★ nuovo con questo report\n\n")
    blocchi = [in_breve(dati, attivi, chiusi, verifica)]
    for cat, lista in attivi.items():
        righe = [f"<b>{escape(cat.upper())}</b>"]
        for s in lista:
            righe.append(f"{_freccia(s['etichetta'])} {escape(s['nome'])}: <b>{escape(s['etichetta'])}</b> "
                         f"{_punti(s['punteggio'])}" + (" ★" if s["nuovo"] else ""))
        blocchi.append("\n".join(righe))
    if chiusi:
        blocchi.append("<b>CHIUSI CON QUESTO REPORT</b>\n" +
                       "\n".join(f"■ {escape(c['nome'])}: era {escape(c['prima'])}, ora NEUTRO" for c in chiusi))
    if len(blocchi) == 1:
        blocchi.append("Nessun segnale attivo questa settimana.")
    piede = "\n\n" + (f'<a href="{_escape(sito.rstrip("/"))}/">Apri il terminale BoardEdge</a>\n' if sito else "") + \
        "<i>Informazione statistica dalla dashboard pubblica, non consulenza finanziaria.</i>"
    return impagina(testa, blocchi, piede)
