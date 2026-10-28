"""
paracadute.py - il sito non deve MAI peggiorare.

Dopo ogni aggiornamento confrontiamo il risultato nuovo con l'ultimo risultato BUONO (dati/stato.json):

  * se mancano pezzi rispetto all'ultima volta (strumenti o coppie spariti, sezione mercati vuota)
    -> NON pubblichiamo: resta online l'ultima versione buona  (livello CRITICAL nel registro)
  * se una fonte non e' online (server giu', manutenzione...) la pagina si pubblica lo stesso con gli
    ultimi dati salvati, ma l'esito diventa "critico"  (livello CRITICAL nel registro)

Con esito "critico" il job "avviso-admin" di sito.yml fallisce apposta: GitHub manda una MAIL PRIVATA
al proprietario del repository (solo a te). Nessuna segnalazione pubblica.
DEBUG: python main.py --debug -> righe "PARACADUTE ...".
"""
import json
import os

from .log import log

TOLLERANZA = 0.9      # accettiamo fino al 10% di strumenti in meno (es. un mercato chiuso dalla CFTC), non di piu'


def ultimo_buono(percorso):
    """Riepilogo dell'ultimo aggiornamento pubblicato (None se non esiste o e' illeggibile)."""
    try:
        with open(percorso, encoding="utf-8") as f:
            s = json.load(f)
        return s if s.get("esito") not in ("fallito", "scartato") else None
    except Exception:
        return None


def valuta(nuovo, vecchio):
    """Restituisce (pubblica, critici): pubblica=False se il nuovo risultato e' peggiore dell'ultimo buono."""
    critici, pubblica = [], True

    # 1) fonti non online: si pubblica con i dati salvati, ma e' CRITICO.
    #    Eccezione (v6.42): "parziale" = la fonte ha risposto ma e' mancata QUALCHE serie (es. un 504 della BCE su una
    #    sola serie, gia' riprovata una volta): si usano i dati salvati di quella serie, NON e' critico (niente mail,
    #    registro segnali e notifiche Telegram continuano). Resta un WARNING nel registro admin.
    for fonte, st in (nuovo.get("fonti") or {}).items():
        if fonte == "fred_riserva":
            continue
        if st == "parziale":
            log.warning("PARACADUTE: fonte %s parziale (qualche serie dai dati salvati): non critico", fonte.upper())
            continue
        if st != "online":
            critici.append(f"fonte {fonte.upper()} non disponibile ({st}): pubblicati gli ultimi dati validi")

    # 2) il nuovo risultato ha meno contenuto dell'ultimo buono: NON si pubblica
    if vecchio:
        for chiave, nome in (("strumenti", "strumenti"), ("coppie", "coppie di valute")):
            n, v = nuovo.get(chiave) or 0, vecchio.get(chiave) or 0
            if v and n < v * TOLLERANZA:
                pubblica = False
                critici.append(f"{nome}: {n} invece di {v} -> pagina NON pubblicata, resta la versione precedente")
        for chiave, nome in (("mercato", "modello di mercato"),):          # mutui tolti in v6.35
            if vecchio.get(chiave) and not nuovo.get(chiave):
                pubblica = False
                critici.append(f"{nome}: assente (prima c'era) -> pagina NON pubblicata, resta la versione precedente")

    for c in critici:
        log.critical("PARACADUTE: %s", c)
    return pubblica, critici
