# -*- coding: utf-8 -*-
"""
vetrina.py - LANDING PAGE del sito (public/index.html). Il terminale sta in public/terminale/.

Prende il modello web/landing.html e ci mette i numeri VERI dell'ultimo aggiornamento (pagina.ULTIMI):
data del report COT, segnali attivi, mercati seguiti, inizio del backtest e un'anteprima dei segnali
per categoria (i nomi sono sfocati nella pagina: si sbloccano con il pass gratuito).
Nessun numero inventato: se un dato manca si scrive "n.d." e la pagina resta comunque valida.

DEBUG: python -c "from cot_radar import vetrina; print(vetrina.html({'data':{'assets':{},'pairs':[]}})[:300])"
"""
import os
from datetime import datetime
from html import escape

from . import pagina, riepilogo
from .config import TELEGRAM_CANALE, WEB_DIR
from .log import log

MAX_CATEGORIE = 4                      # categorie mostrate nell'anteprima
MAX_PER_CATEGORIA = 2                  # righe per categoria


def anteprima(attivi):
    """HTML delle righe dell'anteprima: categoria (con il numero di segnali) e i primi segnali, nome sfocato."""
    out = []
    for cat, lista in list(attivi.items())[:MAX_CATEGORIE]:
        out.append(f'<div class="cat">{escape(cat)}<em>{len(lista)} segnali</em></div>')
        for s in lista[:MAX_PER_CATEGORIA]:
            cls = "b" if "BUY" in s["etichetta"] else "s"
            out.append(f'<div class="riga"><span class="nome">{escape(s["nome"])}</span>'
                       f'<span class="etic {cls}">{escape(s["etichetta"])}</span></div>')
    return "\n".join(out) or '<div class="riga">Nessun segnale attivo questa settimana.</div>'


def html(ultimi):
    """Pagina completa a partire dai dati dell'ultima dashboard (pagina.ULTIMI)."""
    dati = ultimi.get("data") or {}
    attivi, _ = riepilogo.segnali(dati)
    cot = riepilogo.data_cot(dati)
    mercati = [k for k, a in (dati.get("assets") or {}).items() if k != "USD"]   # USD composito: non e' un future
    valori = {
        "{{TELEGRAM}}": TELEGRAM_CANALE,
        "{{COT}}": f"{cot[8:10]}/{cot[5:7]}/{cot[:4]}" if cot else "n.d.",
        "{{N_SEGNALI}}": str(sum(len(v) for v in attivi.values())),
        "{{N_MERCATI}}": str(len(mercati)),
        "{{N_COPPIE}}": str(len(dati.get("pairs") or [])),
        "{{BT_DAL}}": (ultimi.get("bt_dal") or "")[:4] or "n.d.",
        "{{AGGIORNATO}}": datetime.now().strftime("%d/%m/%Y"),
        "{{ANTEPRIMA}}": anteprima(attivi),
    }
    with open(os.path.join(WEB_DIR, "landing.html"), encoding="utf-8") as f:
        pagina_html = f.read()
    for k, v in valori.items():
        pagina_html = pagina_html.replace(k, v)
    return pagina_html


def crea(cartella):
    """Scrive cartella/index.html (la landing). Chiamata da main.py solo in modalita' sito, dopo il terminale."""
    if not pagina.ULTIMI.get("data"):
        log.warning("landing page non aggiornata: mancano i dati della dashboard")
        return None
    f = os.path.join(cartella, "index.html")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(html(pagina.ULTIMI))
    log.info("Landing page creata: %s", f)
    return f
