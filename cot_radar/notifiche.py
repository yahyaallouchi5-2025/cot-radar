# -*- coding: utf-8 -*-
"""
notifiche.py - AVVISI DEI SEGNALI: canale Telegram per tutti gli iscritti + copia via e-mail all'admin.

Fonte unica: il registro live dei segnali (storico/segnali/registro.jsonl, vedi registro.py). Si avvisa solo di
cio' che e' gia' scritto nel registro ufficiale e gia' pubblicato sul sito: il workflow "Notifiche" parte
SOLO dopo una pubblicazione riuscita.

CURSORE (storico/segnali/notificati.json): numero dell'ultimo evento gia' avvisato. Serve a:
  - non mandare mai due volte lo stesso avviso (i giri della sera sono tre, quelli del mattino uno);
  - recuperare da solo: se Telegram non risponde il cursore NON avanza e gli eventi partono al giro dopo;
  - primo avvio: il cursore parte dall'ultimo evento esistente, nessun "arretrato" inviato agli iscritti.
Eventi piu' vecchi di MAX_ETA_ORE (es. dopo giorni di sito fermo) non si mandano: un avviso in ritardo e'
peggio di nessun avviso. Il cursore li supera comunque.

RIEPILOGO SETTIMANALE (riepilogo.py): quando la dashboard online mostra un report COT NUOVO (il venerdi' sera,
dopo l'uscita del COT) parte il riepilogo di tutti i segnali attivi divisi per categoria di asset, al posto del
messaggio sugli eventi. Il cursore ricorda la data COT dell'ultimo riepilogo ("riepilogo_cot"): uno a settimana.

Negli altri giri (un solo messaggio per giro, diviso solo se supera il limite di Telegram) si avvisa di:
  - NUOVO SEGNALE (apertura): direzione, punteggio, affidabilita' e motivi;
  - RAFFORZAMENTO a STRONG (apertura "figlio") e INDEBOLIMENTO da STRONG;
  - CHIUSURA (torna neutro / si inverte) con la durata del segnale;
  - CONFERME del nuovo COT: raccolte in una riga sola (sono settimanali e numerose).
Gli eventi "iniziali" del primo avvio del registro non si avvisano mai (non sono nati in quel momento).

Credenziali: SOLO nei GitHub Secrets, mai nel codice o nei log (vedi README, sezione "Notifiche").
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID         -> canale Telegram (obbligatori per gli avvisi)
  SMTP_USER, SMTP_PASSWORD, ADMIN_EMAIL        -> copia e-mail all'admin (facoltativa; SMTP_HOST, default Gmail)
Senza Telegram configurato il cursore avanza comunque (nessun arretrato quando lo si attiva).

USO:  python -m cot_radar.notifiche storico https://utente.github.io/cot-radar/   (giro normale)
      python -m cot_radar.notifiche prova   https://utente.github.io/cot-radar/   (TEST: riepilogo subito)
      python -m cot_radar.notifiche anteprima storico                              (stampa senza inviare)
"""
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape as _escape

from .config import ASSETS
from .log import log
from .registro import leggi, verifica

CURSORE = "notificati.json"
MAX_ETA_ORE = 36                      # oltre: l'avviso e' troppo vecchio per essere utile
LIMITE_TG = 3800                      # Telegram accetta 4096 caratteri: margine per i tag HTML
NOMI = {k: nome for k, _, nome, _ in ASSETS}
def escape(t):
    """Escape HTML per Telegram (gli apostrofi restano leggibili)."""
    return _escape(str(t), quote=False)


AVVERTENZA = "Informazione statistica dal registro pubblico, non consulenza finanziaria."


# ---------- testo dei messaggi ----------

def nome(e):
    """Nome leggibile: EUR/USD per le coppie, nome esteso per gli altri strumenti."""
    if e.get("base") and e.get("quote"):
        return f"{e['base']}/{e['quote']}"
    s = e.get("strumento", "?")
    return NOMI.get(s, s)


def _ora(iso):
    """'2026-10-23T22:59Z' -> datetime UTC (None se illeggibile)."""
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _durata(da, a):
    """Durata leggibile tra due istanti ISO: '12 giorni (1 settimana e 5 giorni)'."""
    t0, t1 = _ora(da), _ora(a)
    if not t0 or not t1:
        return ""
    g = max(0, (t1 - t0).days)
    if g < 1:
        return "meno di 1 giorno"
    testo = f"{g} {'giorno' if g == 1 else 'giorni'}"
    s, r = divmod(g, 7)
    if s:
        sett = f"{s} {'settimana' if s == 1 else 'settimane'}"
        testo += f" ({sett}" + (f" e {r} {'giorno' if r == 1 else 'giorni'})" if r else ")")
    return testo


def _punti(p):
    return f"{p:+.1f}" if isinstance(p, (int, float)) else "n.d."


def _freccia(etichetta):
    return "▲" if "BUY" in etichetta else "▼" if "SELL" in etichetta else "■"


def righe_eventi(nuovi, aperture):
    """Testo HTML (Telegram) per gli eventi nuovi. aperture = {id: evento di apertura} di tutto il registro."""
    blocchi, conferme = [], []
    ordine = {"apertura": 0, "chiusura": 1, "conferma": 2}
    for e in sorted(nuovi, key=lambda e: ordine.get(e["tipo"], 3)):
        a = aperture.get(e.get("id"), {})
        if e["tipo"] == "apertura":
            if e.get("iniziale"):
                continue
            lab = e["etichetta"]
            motivi = ", ".join(e.get("perche") or []).replace("stagionalita'", "stagionalità")
            titolo = (f"rafforzato a <b>{lab}</b>" if e.get("padre") else f"nuovo segnale <b>{lab}</b>")
            riga = (f"{_freccia(lab)} <b>{escape(nome(e))}</b>: {titolo}\n"
                    f"    Punteggio {_punti(e.get('punteggio'))} · affidabilità {escape(e.get('affid') or 'n.d.')}")
            if motivi:
                riga += f" ({escape(motivi)})"
            blocchi.append(riga)
        elif e["tipo"] == "chiusura":
            if a.get("padre") and e.get("motivo") != "indebolito":
                continue                              # il figlio si chiude col padre: basta la riga del padre
            if a.get("padre"):
                blocchi.append(f"{_freccia(e.get('nuova', ''))} <b>{escape(nome(a))}</b>: da {escape(a['etichetta'])} "
                               f"torna <b>{escape(e.get('nuova', ''))}</b> (punteggio {_punti(e.get('punteggio'))})")
                continue
            motivo = "si inverte" if e.get("motivo") == "inversione" else "torna neutro"
            durata = _durata(a.get("generato"), e.get("quando"))
            blocchi.append(f"■ <b>{escape(nome(a) if a else e.get('id', '?'))}</b>: chiuso il segnale "
                           f"{escape(a.get('etichetta', ''))}, {motivo} (punteggio {_punti(e.get('punteggio'))})"
                           + (f"\n    Durata del segnale: {durata}" if durata else ""))
        elif e["tipo"] == "conferma" and a:
            conferme.append(f"{escape(nome(a))} {escape(e.get('etichetta', ''))}")
    if conferme:
        blocchi.append("✓ Confermati dal nuovo COT: " + ", ".join(conferme))
    return blocchi


def componi(blocchi, nuovi, sito):
    """Messaggi completi (lista: si divide solo se supera il limite di Telegram)."""
    if not blocchi:
        return []
    cot = next((e.get("cot_data") for e in reversed(nuovi) if e.get("cot_data")), None)
    quando = next((e.get("quando") or e.get("generato") for e in reversed(nuovi)), "")
    t = _ora(quando)
    testa = "<b>Edge Board · aggiornamento segnali</b>\n<i>" + \
            (t.strftime("%d/%m/%Y %H:%M UTC") if t else "") + \
            (f" · COT del {cot[8:10]}/{cot[5:7]}/{cot[:4]}" if cot else "") + "</i>\n\n"
    piede = "\n\n" + (f'<a href="{_escape(sito.rstrip("/"))}/#registro">Registro completo e statistiche</a>\n'
                      if sito else "") + f"<i>{AVVERTENZA}</i>"
    return impagina(testa, blocchi, piede)


def impagina(testa, blocchi, piede):
    """Unisce intestazione, blocchi e piede; se si supera il limite di Telegram divide tra un blocco e l'altro
    (mai a meta' di un blocco) e ripete intestazione e piede in ogni messaggio."""
    out, corpo = [], ""
    for b in blocchi:
        if corpo and len(testa) + len(corpo) + len(b) + len(piede) > LIMITE_TG:
            out.append(testa + corpo.rstrip() + piede)
            corpo = ""
        corpo += b + "\n\n"
    out.append(testa + corpo.rstrip() + piede)
    return out


# ---------- cursore ----------

def leggi_cursore(cartella):
    f = os.path.join(cartella, CURSORE)
    if not os.path.exists(f):
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def scrivi_cursore(cartella, ultimo_n, ultimo_hash, adesso, riepilogo_cot=None):
    """ultimo_n = ultimo evento avvisato; riepilogo_cot = data COT dell'ultimo riepilogo settimanale inviato."""
    f = os.path.join(cartella, CURSORE)
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"ultimo_n": ultimo_n, "hash": ultimo_hash, "riepilogo_cot": riepilogo_cot,
                   "aggiornato": adesso.strftime("%Y-%m-%dT%H:%MZ")}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, f)


def da_avvisare(eventi, cursore, adesso):
    """(eventi nuovi da avvisare, eventi saltati perche' troppo vecchi). cursore None = primo avvio: niente."""
    if cursore is None:
        return [], []
    nuovi = [e for e in eventi if e.get("n", -1) > cursore.get("ultimo_n", -1)]
    limite = adesso - timedelta(hours=MAX_ETA_ORE)
    freschi = [e for e in nuovi if (_ora(e.get("quando") or e.get("generato")) or adesso) >= limite]
    vecchi = [e for e in nuovi if e not in freschi]
    return freschi, vecchi


# ---------- invio ----------

def invia_telegram(token, chat, testo):
    """True se Telegram ha accettato il messaggio. Il token non compare mai nei log."""
    dati = urllib.parse.urlencode({"chat_id": chat, "text": testo, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", dati, timeout=30) as r:
            return json.load(r).get("ok") is True
    except urllib.error.HTTPError as e:
        try:
            motivo = json.load(e).get("description", "")
        except Exception:
            motivo = ""
        log.error("Telegram ha rifiutato il messaggio (HTTP %s: %s)", e.code, motivo)
    except (urllib.error.URLError, OSError, ValueError) as e:
        log.error("Telegram non raggiungibile (%s)", type(e).__name__)
    return False


def invia_email(testi, env):
    """Copia all'admin (facoltativa). Testo semplice ricavato dall'HTML. Errori: solo un avviso nel log."""
    utente, password, dest = env.get("SMTP_USER"), env.get("SMTP_PASSWORD"), env.get("ADMIN_EMAIL")
    if not (utente and password and dest):
        return None
    import re
    corpo = "\n\n".join(re.sub(r"<[^>]+>", "", t) for t in testi).replace("&amp;", "&").replace("&lt;", "<") \
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#x27;", "'")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "Edge Board: aggiornamento segnali", utente, dest
    msg.set_content(corpo)
    try:
        with smtplib.SMTP_SSL(env.get("SMTP_HOST", "smtp.gmail.com"), int(env.get("SMTP_PORT", "465")),
                              context=ssl.create_default_context(), timeout=30) as s:
            s.login(utente, password)
            s.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        log.warning("e-mail all'admin non inviata (%s)", type(e).__name__)
        return False


# ---------- giro completo ----------

def esegui(cartella, sito, env=None, adesso=None, invia=True, dati_sito=None):
    """Un giro: legge registro e cursore, invia gli avvisi nuovi, avanza il cursore.
    SETTIMANALE: se la dashboard online mostra un report COT nuovo, parte il riepilogo per categoria
    (riepilogo.py) AL POSTO del messaggio sugli eventi: le novita' della settimana sono gia' dentro
    (segnali "nuovi" e chiusi), cosi' gli iscritti ricevono un solo messaggio.
    dati_sito = dati della pagina gia' letti (per i test); None = si scaricano dal sito.
    Restituisce un dizionario con l'esito (per il log del workflow e per i test)."""
    from . import riepilogo
    env = os.environ if env is None else env
    adesso = adesso or datetime.now(timezone.utc)
    eventi = leggi(cartella)
    integra, ultimo_hash, rotto = verifica(eventi)
    if not integra:
        log.error("registro NON integro dall'evento %s: nessun avviso finche' l'admin non controlla", rotto)
        return {"esito": "registro_non_integro", "inviati": 0}
    ultimo_n = eventi[-1]["n"] if eventi else -1
    dati = dati_sito if dati_sito is not None else riepilogo.scarica(sito)
    cot_sito = riepilogo.data_cot(dati)
    cursore = leggi_cursore(cartella)
    if cursore is None:
        if invia:
            scrivi_cursore(cartella, ultimo_n, ultimo_hash, adesso, cot_sito)
        log.info("notifiche: primo avvio, cursore all'evento %d e al COT %s (nessun arretrato inviato)",
                 ultimo_n, cot_sito)
        return {"esito": "primo_avvio", "inviati": 0, "ultimo_n": ultimo_n}
    gia_cot = cursore.get("riepilogo_cot")
    settimanale = bool(cot_sito and gia_cot and cot_sito > gia_cot)
    if cot_sito and not gia_cot:
        gia_cot = cot_sito             # cursore di una versione precedente: il primo riepilogo sara' il prossimo
    if settimanale:
        testi = riepilogo.testi(dati, sito)
        log.info("notifiche: nuovo report COT online (%s): riepilogo settimanale", cot_sito)
    else:
        nuovi, vecchi = da_avvisare(eventi, cursore, adesso)
        if vecchi:
            log.warning("notifiche: %d eventi troppo vecchi (> %d ore) non inviati", len(vecchi), MAX_ETA_ORE)
        aperture = {e["id"]: e for e in eventi if e["tipo"] == "apertura"}
        testi = componi(righe_eventi(nuovi, aperture), nuovi, sito)
    esito = {"esito": "niente_di_nuovo", "inviati": 0, "ultimo_n": ultimo_n, "testi": testi,
             "tipo": "settimanale" if settimanale else "eventi"}
    if not invia:
        return dict(esito, esito="anteprima")
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if testi and token and chat:
        for i, t in enumerate(testi):
            if not invia_telegram(token, chat, t):
                # il cursore resta fermo: al prossimo giro si riprova (i messaggi gia' partiti si ripetono:
                # meglio un doppione raro che un segnale perso)
                return dict(esito, esito="telegram_errore", inviati=i)
        esito.update(esito="inviato", inviati=len(testi))
        esito["email"] = invia_email(testi, env)
    elif testi:
        log.info("notifiche: Telegram non configurato (Secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        esito["esito"] = "non_configurato"
    nuovo_cot = cot_sito if settimanale else gia_cot
    if ultimo_n != cursore.get("ultimo_n") or nuovo_cot != cursore.get("riepilogo_cot"):
        scrivi_cursore(cartella, ultimo_n, ultimo_hash, adesso, nuovo_cot)
    return esito


def prova(sito, env=None, dati_sito=None):
    """TEST dal workflow 'Prova notifiche': manda SUBITO il riepilogo settimanale della dashboard attuale,
    marcato [TEST] (non tocca il cursore: il riepilogo vero partira' comunque col prossimo COT).
    Se i dati del sito non si leggono, manda un semplice messaggio di prova del collegamento."""
    from . import riepilogo
    env = os.environ if env is None else env
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    dati = dati_sito if dati_sito is not None else riepilogo.scarica(sito)
    if dati and dati.get("assets"):
        testi = riepilogo.testi(dati, sito, test=True)
    else:
        testi = ["<b>Edge Board · messaggio di prova</b>\n\nIl canale è collegato: qui arriveranno il riepilogo "
                 "settimanale dei segnali e gli aggiornamenti." +
                 (f'\n\n<a href="{_escape(sito.rstrip("/"))}/">Apri la dashboard</a>' if sito else "")]
    if not (token and chat):
        log.error("mancano i Secrets TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID")
        return {"telegram": None, "email": invia_email(testi, env), "messaggi": len(testi)}
    ok = all(invia_telegram(token, chat, t) for t in testi)
    return {"telegram": ok, "email": invia_email(testi, env), "messaggi": len(testi)}


def main(argv):
    if len(argv) >= 2 and argv[0] == "anteprima":
        r = esegui(os.path.join(argv[1], "segnali"), argv[2] if len(argv) > 2 else "", invia=False)
        print(json.dumps({k: v for k, v in r.items() if k != "testi"}, ensure_ascii=False))
        for t in r.get("testi") or []:
            print("-" * 40 + "\n" + t)
        return 0
    if len(argv) >= 1 and argv[0] == "prova":
        r = prova(argv[1] if len(argv) > 1 else "")
        print("esito prova:", r)
        return 0 if r["telegram"] else 1
    if len(argv) < 1:
        print(__doc__)
        return 2
    r = esegui(os.path.join(argv[0], "segnali"), argv[1] if len(argv) > 1 else "")
    print("esito notifiche:", {k: v for k, v in r.items() if k != "testi"})
    return 1 if r["esito"] in ("telegram_errore", "registro_non_integro") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
