# -*- coding: utf-8 -*-
"""
avvisi.py - AVVISI TELEGRAM SULLE NOTIZIE MACRO (in arrivo + esito), a partire dall'agenda della pagina
(D["agenda"], costruita da agenda.py a ogni aggiornamento del sito).

DUE MESSAGGI, OGNUNO UNA SOLA VOLTA (lo stato e' nel cursore delle notifiche, vedi notifiche.py):
  1. IN ARRIVO: eventi che escono entro le prossime ORE_PRIMA ore (la sera prima o la mattina stessa):
     orario italiano, impatto, valuta, segnali COT esposti e cosa succede se la valuta si rafforza o indebolisce.
  2. ESITO: per ogni valuta e giorno, appena c'e' la reazione del mercato (tasso a 2 anni, di solito il giorno
     dopo): dato uscito contro precedente, reazione in punti base e deviazioni standard, verdetto sui segnali.
     CICLO: se la reazione non c'e' ancora l'esito resta in attesa e si riprova al giro dopo; dopo
     ATTESA_MAX giorni parte comunque con quello che c'e' (mai un esito perso, mai inventato).
     Valute senza tasso a 2 anni nei nostri dati (GBP, JPY, CAD, AUD, NZD, CHF): esito con il solo dato uscito.

DEBUG: python -c "from cot_radar import avvisi; help(avvisi.da_inviare)"
"""
from datetime import date, datetime, timedelta
from html import escape as _escape

from .agenda import MISURABILI, Z_MARCATA

ORE_PRIMA = 30                 # finestra dell'avviso "in arrivo"
ATTESA_MAX = 4                 # giorni massimi di attesa della reazione del mercato
TENUTA = 40                    # giorni dopo cui lo stato di un evento viene dimenticato
GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def esc(t):
    return _escape(str(t), quote=False)


def _it(utc):
    """'2026-10-28T18:00Z' -> datetime ora italiana (ora legale fino all'ultima domenica di ottobre)."""
    from .calendario import utc_to_it
    return utc_to_it(datetime.strptime(utc, "%Y-%m-%dT%H:%MZ"))


def quando(e):
    """'mer 28/10 ore 19:00' (ora italiana); solo la data se l'orario non e' noto."""
    if e.get("utc"):
        t = _it(e["utc"])
        return f"{GIORNI[t.weekday()]} {t:%d/%m} ore {t:%H:%M}"
    d = date.fromisoformat(e["data"])
    return f"{GIORNI[d.weekday()]} {d:%d/%m} (orario da confermare)"


UNITA = {"% y/y": "% a/a", "% m/m": "% m/m", "% q/q annualised": "% t/t annualizzato", "index": "",
         "% unemployment rate": "% disoccupazione"}


def valore(x, unita):
    """Dato con l'unita' in forma leggibile: '3.7' + '% y/y' -> '3,7% a/a'; posti di lavoro con le migliaia;
    tassi delle banche centrali ('% target range', '% deposit rate'...) -> '%'."""
    if x in (None, ""):
        return None
    try:
        v = float(str(x).replace(",", ""))
    except ValueError:
        return esc(x)                                   # es. una forchetta "4.25-4.50": la lasciamo com'e'
    if unita == "jobs":
        return f"{v:+,.0f}".replace(",", ".") + " posti"
    u = UNITA.get(unita, "%" if (unita or "").startswith("%") else (unita or ""))
    n = f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{n}{u}" if u.startswith("%") or not u else f"{n} {u}"


def _segnale(x):
    return f"{esc(x['coppia'])} {esc(x['etichetta'])}"


def scenario(e):
    """Cosa favorisce una valuta piu' forte / piu' debole tra i segnali esposti (stessa logica del verdetto)."""
    v, es = e["valuta"], e.get("esposti") or []
    if not es:
        return f"Nessun segnale COT attivo su {v}: notizia da tenere d'occhio solo per la volatilità."
    forte = [x for x in es if x["lato"] == x["verso"]]       # valuta piu' forte = coppia nel verso del segnale
    debole = [x for x in es if x["lato"] != x["verso"]]
    righe = []
    if forte:
        righe.append(f"{v} più forte → a favore di: " + ", ".join(_segnale(x) for x in forte[:6]))
    if debole:
        righe.append(f"{v} più debole → a favore di: " + ", ".join(_segnale(x) for x in debole[:6]))
    return "\n".join(righe)


def testo_arrivo(eventi, credito):
    """Messaggio "notizie in arrivo" (un blocco per evento)."""
    blocchi = []
    for e in eventi:
        imp = "impatto ALTO" if e.get("impatto") == "high" else "impatto medio"
        prec = valore(e.get("precedente"), e.get("unita"))
        b = (f"⚡ <b>{esc(e['nome'])}</b> · {quando(e)} · {imp} · <b>{esc(e['valuta'])}</b>"
             + (f"\nPrecedente: {prec}" if prec else "")
             + f"\n{scenario(e)}")
        blocchi.append(b)
    return ("<b>BoardEdge · notizie in arrivo</b>\n\n" + "\n\n".join(blocchi)
            + "\n\n<i>Attorno all'annuncio la volatilità sale: è rumore di breve. La direzione resta quella del COT; "
              "l'esito arriva appena il mercato ha reagito.</i>"
            + f'\n<a href="{_escape(credito)}">Calendario: financecalendar.com</a>')


def reazione(z, pb, valuta):
    """Frase e colore della reazione del mercato."""
    if z is None:
        return f"reazione del mercato non disponibile per {esc(valuta)}"
    forza = "forte" if abs(z) >= 2 else "marcata" if abs(z) >= Z_MARCATA else "nella norma"
    segno = "+" if pb >= 0 else "−"
    base = f"tasso a 2 anni {esc(valuta)} {segno}{abs(pb):.1f} pb ({'+' if z >= 0 else '−'}{abs(z):.1f}σ)".replace(".", ",")
    if abs(z) < Z_MARCATA:
        return f"{base} → reazione {forza}, nessuna sorpresa rilevante"
    return f"{base} → sorpresa {forza}: <b>{esc(valuta)} più {'forte' if z > 0 else 'debole'}</b>"


def testo_esito(gruppi, credito):
    """Messaggio "esito delle notizie": un blocco per valuta e giorno (la reazione e' quella della giornata)."""
    simbolo = {"conferma": "✓", "contrasto": "✗", "neutro": "·"}
    blocchi = []
    for g in gruppi:
        e0 = g["eventi"][0]
        dati = []
        for e in g["eventi"]:
            att, prec = valore(e.get("attuale"), e.get("unita")), valore(e.get("precedente"), e.get("unita"))
            dati.append(f"<b>{esc(e['nome'])}</b>: " + (f"{att}" + (f" (precedente {prec})" if prec else "")
                                                        if att else "dato non ancora registrato"))
        righe = ["📊 " + " · ".join(dati) + f" — {date.fromisoformat(g['data']):%d/%m}"]
        if e0["valuta"] in MISURABILI:
            righe.append("Reazione: " + reazione(e0.get("z"), e0.get("pb"), e0["valuta"]))
            es = [x for x in e0.get("esposti") or [] if x.get("verdetto")]
            if es:
                righe.append("Segnali COT: " + " · ".join(f"{_segnale(x)} {simbolo[x['verdetto']]} {x['verdetto']}"
                                                          for x in es[:8]))
        else:
            righe.append(f"Reazione: non misurata per {esc(e0['valuta'])} (manca il tasso a 2 anni nei nostri dati).")
        blocchi.append("\n".join(righe))
    return ("<b>BoardEdge · esito delle notizie</b>\n\n" + "\n\n".join(blocchi)
            + "\n\n<i>Reazione = movimento del tasso a 2 anni nel giorno dell'annuncio rispetto a una giornata normale "
              "(σ). ✓ conferma il segnale COT, ✗ va contro, · nessun effetto.</i>"
            + f'\n<a href="{_escape(credito)}">Calendario: financecalendar.com</a>')


def da_inviare(agenda, stato, adesso):
    """Decide cosa mandare. stato = {"arrivo": {id: data}, "esito": {chiave: data}} dal cursore.
    Restituisce (eventi_in_arrivo, gruppi_esito, nuovo_stato). Lo stato si salva SOLO dopo l'invio riuscito."""
    stato = {"arrivo": dict((stato or {}).get("arrivo") or {}), "esito": dict((stato or {}).get("esito") or {})}
    eventi = (agenda or {}).get("eventi") or []
    oggi = adesso.date()
    arrivo, gruppi = [], {}
    for e in eventi:
        t = datetime.strptime(e["utc"], "%Y-%m-%dT%H:%MZ") if e.get("utc") else \
            datetime.combine(date.fromisoformat(e["data"]), datetime.min.time()) + timedelta(hours=10)
        ore = (t - adesso).total_seconds() / 3600
        if 0 < ore <= ORE_PRIMA and e["id"] not in stato["arrivo"]:
            arrivo.append(e)
        if e.get("uscito"):
            chiave = f"{e['valuta']}-{e['data']}"
            if chiave not in stato["esito"]:
                gruppi.setdefault(chiave, {"chiave": chiave, "data": e["data"], "eventi": []})["eventi"].append(e)
    pronti = []
    for g in gruppi.values():
        e0, eta = g["eventi"][0], (oggi - date.fromisoformat(g["data"])).days
        misura_ok = e0["valuta"] not in MISURABILI or e0.get("z") is not None
        dati_ok = all(e.get("attuale") not in (None, "") for e in g["eventi"])
        # pronto: reazione misurata e dati registrati (o almeno 2 giorni di attesa per i dati);
        # dopo ATTESA_MAX giorni parte comunque con quello che c'e'
        if (misura_ok and (dati_ok or eta >= 2)) or eta >= ATTESA_MAX:
            pronti.append(g)
    nuovo = {"arrivo": dict(stato["arrivo"]), "esito": dict(stato["esito"])}
    for e in arrivo:
        nuovo["arrivo"][e["id"]] = e["data"]
    for g in pronti:
        nuovo["esito"][g["chiave"]] = g["data"]
    limite = (oggi - timedelta(days=TENUTA)).isoformat()
    for k in ("arrivo", "esito"):
        nuovo[k] = {i: d for i, d in nuovo[k].items() if d >= limite}
    return arrivo, sorted(pronti, key=lambda g: g["chiave"]), nuovo


def stato_iniziale(agenda, adesso):
    """Primo avvio: gli esiti gia' passati si considerano gia' inviati (niente arretrati sul canale)."""
    st = {"arrivo": {}, "esito": {}}
    for e in (agenda or {}).get("eventi") or []:
        if e.get("uscito"):
            st["esito"][f"{e['valuta']}-{e['data']}"] = e["data"]
            st["arrivo"][e["id"]] = e["data"]
    return st
