# -*- coding: utf-8 -*-
"""
avvisi.py - AVVISI TELEGRAM SULLE NOTIZIE MACRO (in arrivo + esito), a partire dall'agenda della pagina
(D["agenda"], costruita da agenda.py a ogni aggiornamento del sito).

TRE MESSAGGI, OGNUNO UNA SOLA VOLTA (lo stato e' nel cursore delle notifiche, vedi notifiche.py):
  0. SETTIMANA (v6.22): il venerdi' sera, dopo il riepilogo COT, l'agenda della settimana dopo giorno per giorno:
     ora italiana, cos'e' ogni notizia, precedente, come leggerla e a favore di quali segnali COT
     (se il giro del venerdi' salta, parte entro il lunedi' mattina).
  1. IN ARRIVO: eventi che escono entro le prossime ORE_PRIMA ore (la sera prima o la mattina stessa):
     orario italiano, impatto, valuta, segnali COT esposti e cosa succede se la valuta si rafforza o indebolisce.
  2. ESITO: per ogni valuta e giorno, appena c'e' la reazione del mercato (tasso a 2 anni, di solito il giorno
     dopo): dato uscito contro precedente, reazione in punti base e deviazioni standard, verdetto sui segnali.
     CICLO: se la reazione non c'e' ancora l'esito resta in attesa e si riprova al giro dopo; dopo
     ATTESA_MAX giorni parte comunque con quello che c'e' (mai un esito perso, mai inventato).
     Valute senza tasso a 2 anni nei nostri dati (GBP, JPY, CAD, AUD, NZD, CHF): esito con il solo dato uscito
     confrontato con il precedente ("lettura del dato", dichiarata come stima) e verdetto sui segnali.

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


def _testa(titolo, prova):
    """Intestazione del messaggio; con prova=True aggiunge l'etichetta TEST (workflow "Prova notifiche")."""
    return f"<b>BoardEdge · {titolo}</b>" + (" <i>[TEST · esempio]</i>" if prova else "")


def testo_arrivo(eventi, credito, prova=False):
    """Messaggio "notizie in arrivo" (un blocco per evento)."""
    blocchi = []
    for e in eventi:
        imp = "impatto ALTO" if e.get("impatto") == "high" else "impatto medio"
        prec = valore(e.get("precedente"), e.get("unita"))
        b = (f"⚡ <b>{esc(e['nome'])}</b> · {quando(e)} · {imp} · <b>{esc(e['valuta'])}</b>"
             + (f"\nPrecedente: {prec}" if prec else "")
             + f"\n{scenario(e)}")
        blocchi.append(b)
    return (_testa("notizie in arrivo", prova) + "\n\n" + "\n\n".join(blocchi)
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


def direzione(e):
    """Dato uscito contro il precedente: (verso, frase). verso +1 = spinta alla valuta (dato piu' alto o rialzo
    dei tassi), -1 = il contrario, 0 = invariato. None se mancano i numeri."""
    try:
        att, prec = float(str(e.get("attuale")).replace(",", "")), float(str(e.get("precedente")).replace(",", ""))
    except (TypeError, ValueError):
        return None
    diff = round(att - prec, 4)
    if e.get("tipo") == "banca":
        return (1, "tassi alzati") if diff > 0 else (-1, "tassi tagliati") if diff < 0 else (0, "tassi invariati")
    if diff == 0:
        return 0, "uguale al precedente"
    return (1 if diff > 0 else -1), f"{'sopra' if diff > 0 else 'sotto'} il precedente"


def testo_esito(gruppi, credito, prova=False):
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
            # valute senza tasso a 2 anni: lettura del SOLO dato rispetto al precedente (stima, dichiarata come tale)
            d = next((x for x in (direzione(e) for e in g["eventi"]) if x), None)
            if d:
                verso, frase = d
                righe.append(f"Lettura del dato: {frase}" + (f" → {esc(e0['valuta'])} tendenzialmente più "
                             f"{'forte' if verso > 0 else 'debole'}" if verso else "") +
                             " <i>(stima: reazione del mercato non misurata per questa valuta)</i>")
                es = e0.get("esposti") or []
                if es and verso:
                    righe.append("Segnali COT: " + " · ".join(
                        f"{_segnale(x)} " + ("✓ conferma" if verso * x["lato"] == x["verso"] else "✗ contrasto")
                        for x in es[:8]))
            else:
                righe.append(f"Reazione: non misurata per {esc(e0['valuta'])} (manca il tasso a 2 anni nei nostri dati).")
        blocchi.append("\n".join(righe))
    return (_testa("esito delle notizie", prova) + "\n\n" + "\n\n".join(blocchi)
            + "\n\n<i>Reazione = movimento del tasso a 2 anni nel giorno dell'annuncio rispetto a una giornata normale "
              "(σ). ✓ conferma il segnale COT, ✗ va contro, · nessun effetto.</i>"
            + f'\n<a href="{_escape(credito)}">Calendario: financecalendar.com</a>')


def da_inviare(agenda, stato, adesso):
    """Decide cosa mandare. stato = {"arrivo": {id: data}, "esito": {chiave: data}} dal cursore.
    Restituisce (eventi_in_arrivo, gruppi_esito, nuovo_stato). Lo stato si salva SOLO dopo l'invio riuscito."""
    settimana = (stato or {}).get("settimana")          # lunedi' dell'ultima agenda settimanale inviata
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
    if settimana:
        nuovo["settimana"] = settimana
    return arrivo, sorted(pronti, key=lambda g: g["chiave"]), nuovo


def stato_iniziale(agenda, adesso):
    """Primo avvio: gli esiti gia' passati si considerano gia' inviati (niente arretrati sul canale)."""
    st = {"arrivo": {}, "esito": {}}
    for e in (agenda or {}).get("eventi") or []:
        if e.get("uscito"):
            st["esito"][f"{e['valuta']}-{e['data']}"] = e["data"]
            st["arrivo"][e["id"]] = e["data"]
    return st


# ---------- AGENDA DELLA SETTIMANA (un messaggio il venerdi' sera, dopo il riepilogo COT) ----------
GIORNI_LUNGHI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
# cosa e' ogni notizia, in poche parole (codici di agenda.SERIE)
COSA = {
    "fomc": "decisione sui tassi della Fed + conferenza stampa", "ecb": "decisione sui tassi della BCE + conferenza stampa",
    "boe": "decisione sui tassi", "boj": "decisione sui tassi", "boc": "decisione sui tassi", "rba": "decisione sui tassi",
    "rbnz": "decisione sui tassi", "snb": "decisione sui tassi",
    "us-nfp": "nuovi posti di lavoro e disoccupazione", "us-cpi": "inflazione dei prezzi al consumo",
    "us-pce": "l'inflazione che guarda la Fed", "us-ppi": "prezzi alla produzione (anticipano l'inflazione)",
    "us-gdp": "crescita dell'economia nel trimestre", "us-retail-sales": "spesa delle famiglie",
    "us-ism-manufacturing": "fiducia delle fabbriche (sopra 50 = crescita)",
    "us-ism-services": "fiducia dei servizi (sopra 50 = crescita)",
    "eu-cpi": "inflazione, prima stima", "gb-cpi": "inflazione", "ca-cpi": "inflazione", "au-cpi": "inflazione",
}
GIORNO_INVIO = 4                     # venerdi' (dopo l'uscita del COT)
ORA_INVIO = 18                       # dalle 18 UTC del venerdi'...
LUNEDI_FINO = 12                     # ...fino al lunedi' alle 12 UTC (se il venerdi' il giro non e' andato)


def lettura(e):
    """Come leggere la notizia: verso della valuta. Il mercato reagisce alla SORPRESA rispetto alle attese."""
    v = esc(e["valuta"])
    if e["tipo"] == "banca":
        return f"rialzo o toni duri → {v} più forte · taglio o toni morbidi → {v} più debole"
    if e["codice"].startswith("us-ism"):
        return f"più alto del previsto → {v} più forte"
    return f"più alto del previsto → {v} più forte · più basso → {v} più debole"


def settimana_da_inviare(stato, adesso):
    """Lunedi' (data) della settimana la cui agenda va inviata ora, oppure None.
    Finestra: dal venerdi' 18 UTC al lunedi' 12 UTC; una sola volta per settimana (stato["settimana"])."""
    g, ora = adesso.weekday(), adesso.hour
    if g == GIORNO_INVIO and ora >= ORA_INVIO or g in (5, 6):
        lunedi = adesso.date() + timedelta(days=7 - g)
    elif g == 0 and ora < LUNEDI_FINO:
        lunedi = adesso.date()
    else:
        return None
    return None if (stato or {}).get("settimana") == lunedi.isoformat() else lunedi


def testo_settimana(agenda, lunedi, prova=False):
    """Messaggio "notizie della settimana": per giorno, ora italiana, cosa sono, precedente, come leggerle
    e quanti segnali COT sono esposti. None se la settimana non ha notizie in agenda."""
    fine = lunedi + timedelta(days=6)
    eventi = [e for e in (agenda or {}).get("eventi") or []
              if lunedi <= date.fromisoformat(e["data"]) <= fine]
    if not eventi:
        return None
    eventi.sort(key=lambda e: (e["data"], e.get("utc") or ""))     # senza orario: in testa al giorno
    blocchi, giorno = [], None
    for e in eventi:
        d = date.fromisoformat(e["data"])
        if d != giorno:
            giorno = d
            blocchi.append(f"\n<b>{GIORNI_LUNGHI[d.weekday()]} {d:%d/%m}</b>")
        ora = f"{_it(e['utc']):%H:%M}" if e.get("utc") else "orario da confermare"
        imp = "🔴" if e.get("impatto") == "high" else "🟠"
        prec = valore(e.get("precedente"), e.get("unita"))
        es = e.get("esposti") or []
        riga = (f"{imp} {ora} · <b>{esc(e['nome'])}</b> — {esc(COSA.get(e['codice'], ''))}"
                + (f"\n     precedente {prec}" if prec else "")
                + f"\n     {lettura(e)}"
                + "".join(f"\n     {r}" for r in (scenario(e).split("\n") if es else [])))
        blocchi.append(riga)
    return (_testa(f"notizie della settimana {lunedi:%d/%m} – {fine:%d/%m}", prova) + "\n"
            + "\n".join(blocchi)
            + "\n\n<i>🔴 impatto alto · 🟠 medio · orari italiani. Il mercato reagisce alla sorpresa rispetto alle "
              "attese degli analisti (non incluse nel calendario gratuito): il precedente è il riferimento. "
              "La sera prima arriva il pre-avviso, dopo l'uscita l'esito con la reazione del mercato.</i>"
            + f'\n<a href="{_escape((agenda or {}).get("credito") or "")}">Calendario: financecalendar.com</a>')
