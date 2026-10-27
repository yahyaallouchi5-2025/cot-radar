"""
admin.py - REGISTRO RISERVATO all'amministratore.

Il sito e' pubblico (GitHub Pages): tutto quello che sta nella pagina lo puo' leggere chiunque.
Per questo il registro completo (avvisi, errori, allarmi critici) NON viene pubblicato in chiaro:
  - sul sito viene CIFRATO con una password (AES-GCM 256 bit, chiave ricavata con PBKDF2-SHA256);
  - la password sta solo nel Secret di GitHub  ADMIN_PASSWORD  (mai nel codice, mai nei log);
  - nel browser, aprendo  .../cot-radar/#admin  e scrivendo la password, la pagina lo decifra
    (Web Crypto API, stessi parametri: vedi web/js, sezione "registro").
Sul PC (pagina locale, non pubblicata) il registro resta in chiaro: lo vede solo chi usa il PC.

Senza password o senza la libreria "cryptography" il registro semplicemente NON viene pubblicato:
l'amministratore riceve comunque la mail privata di GitHub quando l'esito e' critico.
DEBUG: python -c "from cot_radar.admin import cifra; print(cifra({'a':1}, 'prova'))"
"""
import base64
import json
import os

ITERAZIONI = 250_000          # PBKDF2: piu' alto = piu' lento indovinare la password (il browser ci mette ~0,2 s)

# campi di stato.json che restano PUBBLICI (servono al sito e ai controlli automatici, nessun dettaglio interno)
CAMPI_PUBBLICI = ("creato", "esito", "fonti", "strumenti", "coppie", "mercato", "demo")


def pubblico(stato):
    """Versione 'da vetrina' dello stato: esito e fonti si', messaggi di avviso/errore no.
    L'esito interno (avvisi/errori/critico) diventa un generico 'ok' o 'parziale'."""
    s = {k: stato[k] for k in CAMPI_PUBBLICI if k in stato}
    if s.get("esito") not in ("ok", "scartato", "fallito"):
        s["esito"] = "parziale"         # il dettaglio (critico, errori...) lo vede solo l'admin
    return s


def _b64(b):
    return base64.b64encode(b).decode("ascii")


def cifra(dati, password):
    """Cifra un dizionario con la password. Ritorna {"salt","iv","ct","iter"} (testo base64) oppure None
    se manca la password o la libreria (in quel caso il registro non si pubblica)."""
    if not password:
        return None
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        return None
    sale, iv = os.urandom(16), os.urandom(12)                 # casuali a ogni aggiornamento
    chiave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sale, iterations=ITERAZIONI).derive(password.encode("utf-8"))
    testo = json.dumps(dati, ensure_ascii=False).encode("utf-8")
    ct = AESGCM(chiave).encrypt(iv, testo, None)              # AES-GCM: cifra e "sigilla" (modifiche = errore)
    return {"salt": _b64(sale), "iv": _b64(iv), "ct": _b64(ct), "iter": ITERAZIONI}
