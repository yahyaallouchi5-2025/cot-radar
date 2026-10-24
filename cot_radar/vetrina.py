# -*- coding: utf-8 -*-
"""
vetrina.py - LANDING PAGE del sito (public/index.html). Il terminale sta in public/terminale/.

Prende il modello web/landing.html e ci mette i numeri VERI dell'ultimo aggiornamento (pagina.ULTIMI):
data del report COT, segnali attivi, mercati seguiti, inizio del backtest e un'anteprima dei segnali
per categoria (i nomi sono sfocati nella pagina: si sbloccano con il pass gratuito).
Nessun numero inventato: se un dato manca si scrive "n.d." e la pagina resta comunque valida.

DEBUG: python -c "from cot_radar import vetrina; print(vetrina.html({'data':{'assets':{},'pairs':[]}})[:300])"
"""
import json
import os
from datetime import datetime
from html import escape

from . import pagina, riepilogo
from .config import TELEGRAM_CANALE, WEB_DIR
from .log import log

MAX_CATEGORIE = 8                      # categorie nell'anteprima (il terminale di prova le fa scorrere)
MAX_PER_CATEGORIA = 3                  # righe per categoria
# favicon: barra luminosa + BO/ED (logo v3 "BOARD EDGE" in miniatura)
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' "
           "rx='14' fill='%230a1628'/%3E%3Crect x='10' y='12' width='6' height='40' rx='3' fill='%232ec4b6'/%3E%3Ctext x='22' "
           "y='31' font-family='Arial,Helvetica,sans-serif' font-weight='900' font-size='19' fill='%23eef5ff'%3EBO%3C/text%3E"
           "%3Ctext x='22' y='51' font-family='Arial,Helvetica,sans-serif' font-weight='900' font-size='19' fill='%235b9bff'%3EED"
           "%3C/text%3E%3C/svg%3E")


def anteprima(attivi):
    """Dati dell'anteprima per il JavaScript della landing: [{cat, n, righe:[{nome, etichetta, buy, nuovo}]}].
    I testi sono gia' "escapati" perche' la pagina li inserisce come HTML."""
    out = []
    for cat, lista in list(attivi.items())[:MAX_CATEGORIE]:
        out.append({"cat": escape(cat), "n": len(lista),
                    "righe": [{"nome": escape(s["nome"]), "etichetta": escape(s["etichetta"]),
                               "buy": "BUY" in s["etichetta"], "nuovo": s["nuovo"]} for s in lista[:MAX_PER_CATEGORIA]]})
    return out


def nastro(dati):
    """Nomi dei mercati coperti per il nastro che scorre (solo nomi, nessun segnale)."""
    nomi = [a.get("it") or k for k, a in (dati.get("assets") or {}).items() if a.get("group") != "Valute"]
    nomi = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD"] + nomi
    return "".join(f"<span>{escape(n)}</span>" for n in nomi)


def html(ultimi):
    """Pagina completa a partire dai dati dell'ultima dashboard (pagina.ULTIMI)."""
    dati = ultimi.get("data") or {}
    attivi, _ = riepilogo.segnali(dati)
    mercati = [k for k, a in (dati.get("assets") or {}).items() if k != "USD"]   # USD composito: non e' un future
    dal = (ultimi.get("bt_dal") or "")[:4]
    valori = {
        "{{TELEGRAM}}": TELEGRAM_CANALE,
        "{{FAVICON}}": FAVICON,
        "{{N_SEGNALI}}": str(sum(len(v) for v in attivi.values())),
        "{{N_MERCATI}}": str(len(mercati)),
        "{{N_COPPIE}}": str(len(dati.get("pairs") or [])),
        "{{BT_DAL}}": dal or "n.d.",
        "{{ANNI_BT}}": str(datetime.now().year - int(dal)) if dal.isdigit() else "0",
        "{{AGGIORNATO}}": datetime.now().strftime("%d/%m/%Y"),
        "{{NASTRO}}": nastro(dati),
        # "</" spezzato: dentro <script> chiuderebbe il tag
        "{{ANTEPRIMA_JSON}}": json.dumps(anteprima(attivi), ensure_ascii=False).replace("</", "<\\/"),
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
