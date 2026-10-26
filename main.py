#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - punto di partenza. Doppio clic oppure da terminale:

    python main.py                 scarica i dati, crea cot_radar.html e lo apre nel browser
    python main.py --demo          stessa cosa con dati FINTI (nessun internet): per provare e fare debug
    python main.py --debug         stampa i dettagli di ogni passaggio (quale serie arriva, quanto ci mette...)
    python main.py --out public    modalita' sito (GitHub Actions): public/index.html = landing page,
                                   public/terminale/index.html = terminale (dashboard), public/stato.json
    python main.py --no-open       non apre il browser
    python main.py --pianifica     Windows: aggiornamento automatico ogni venerdi' alle 21:45

Registro di monitoraggio: dati/registro.log (tutti i messaggi) e dati/stato.json (riepilogo dell'ultima esecuzione).

Solo libreria standard di Python 3.9+: non serve installare nulla.
"""
import json
import os
import sys
import traceback
import webbrowser
from datetime import datetime

# permette di lanciare main.py da qualsiasi cartella (anche con doppio clic)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cot_radar.config import OUT, REGISTRO, STATO, TERMINALE  # noqa: E402
from cot_radar import admin                           # noqa: E402
from cot_radar.log import log, raccoglitore, setup   # noqa: E402
from cot_radar.pagina import build, error_page       # noqa: E402
from cot_radar import paracadute                     # noqa: E402
from cot_radar import registro                       # noqa: E402


def install_task():
    """Crea un'attivita' pianificata di Windows (o suggerisce la riga di crontab su Mac/Linux)."""
    exe, me = sys.executable, os.path.abspath(__file__)
    if os.name != "nt":
        print(f"Aggiungi a crontab (crontab -e):  45 21 * * 5 {exe} {me}")
        return
    import subprocess
    r = subprocess.run(["schtasks", "/Create", "/F", "/SC", "WEEKLY", "/D", "FRI", "/ST", "21:45", "/TN", "COT Radar",
                        "/TR", f'"{exe}" "{me}"'], capture_output=True, text=True)
    print(r.stdout or r.stderr)
    print("Fatto: ogni venerdi' alle 21:45 COT Radar si aggiorna e si apre." if r.returncode == 0
          else "Non riuscito: apri il Prompt dei comandi come amministratore e riprova.")


def scrivi_stato(stato, cartelle, pubblica=None):
    """Salva il riepilogo dell'esecuzione (stato.json).
    cartelle = copie PRIVATE (stato completo, es. dati/ sul PC o nella cache di GitHub);
    pubblica = cartella del sito: li' va solo la versione "vetrina" (esito e fonti, nessun messaggio interno)."""
    copie = [(c, stato) for c in cartelle] + ([(pubblica, admin.pubblico(stato))] if pubblica else [])
    for c, contenuto in copie:
        try:
            os.makedirs(c, exist_ok=True)
            with open(os.path.join(c, "stato.json"), "w", encoding="utf-8") as f:
                json.dump(contenuto, f, ensure_ascii=False, indent=1)
        except Exception as e:
            log.warning("stato.json non salvato in %s: %s", c, e)


def segnala_a_github(stato):
    """Solo su GitHub Actions: riepilogo leggibile nella pagina dell'esecuzione + valori per il job
    "avviso-admin" (che con esito critico/errori fa partire la mail privata di GitHub al proprietario)."""
    riepilogo = os.environ.get("GITHUB_STEP_SUMMARY")
    if riepilogo:
        righe = [f"## COT Radar: esito **{stato['esito'].upper()}**", "",
                 f"- creato: {stato.get('creato')} (durata {stato.get('durata_s')} s)",
                 f"- fonti: {stato.get('fonti')}",
                 f"- errori: {stato.get('errori')}, avvisi: {stato.get('avvisi')}", ""]
        # NB: il repository e' pubblico, quindi anche questa pagina: i messaggi dettagliati (avvisi, critici)
        # NON si scrivono qui ma solo nel registro cifrato del sito (.../#admin) e in dati/registro.log
        righe += [f"- critici: {len(stato.get('critici', []))} (dettaglio nel registro admin)"]
        with open(riepilogo, "a", encoding="utf-8") as f:
            f.write("\n".join(righe) + "\n")
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write(f"esito={stato['esito']}\nerrori={stato.get('errori', 0)}\navvisi={stato.get('avvisi', 0)}\n")
            f.write(f"fred={(stato.get('fonti') or {}).get('fred', '?')}\n")   # usato dal job "segnala"


def main(argv):
    setup(debug="--debug" in argv, file_registro=REGISTRO)
    if "--pianifica" in argv:
        install_task()
        return 0

    site = "--out" in argv
    out = OUT
    if site:
        folder = argv[argv.index("--out") + 1]
        os.makedirs(folder, exist_ok=True)
        # landing page nella radice (scritta da vetrina.py a fine giro), terminale nella sottocartella
        os.makedirs(os.path.join(folder, TERMINALE), exist_ok=True)
        out = os.path.join(folder, TERMINALE, "index.html")
    log.info("===== COT Radar: avvio (%s) =====", "sito" if site else "locale")

    if "--demo" in argv:
        from cot_radar.demo import demo_data
        log.warning("MODALITA' DEMO: dati finti, non usarli per decidere")
        source = demo_data
    else:
        from cot_radar.fonti import load_all
        source = load_all

    try:
        page, stato = build(source, demo="--demo" in argv, sito=site)
    except Exception:
        err = traceback.format_exc()
        log.critical("La dashboard NON e' stata creata:\n%s", err)
        stato = {"esito": "fallito", "errori": 1, "avvisi": 0, "creato": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "voci": raccoglitore.voci[-200:]}
        scrivi_stato(stato, [os.path.dirname(STATO)])
        segnala_a_github(stato)
        if site:
            return 1          # sul sito NON pubblichiamo una pagina di errore: resta online l'ultima versione buona
        page = error_page(err)
    else:
        # PARACADUTE: confronto con l'ultimo aggiornamento buono (vedi cot_radar/paracadute.py)
        pubblica, critici = (True, []) if "--demo" in argv else paracadute.valuta(stato, paracadute.ultimo_buono(STATO))
        if critici:
            stato["critici"] = critici
            stato["esito"] = "critico"
        if not pubblica:
            stato["esito"] = "scartato"
            scrivi_stato(stato, [])                                   # niente sovrascritture: resta il riferimento buono
            with open(os.path.join(os.path.dirname(STATO), "stato_scartato.json"), "w", encoding="utf-8") as f:
                json.dump(stato, f, ensure_ascii=False, indent=1)      # per il debug: cosa e' stato scartato
            segnala_a_github(stato)
            if site:
                return 1      # niente pubblicazione: online resta l'ultima versione buona (e parte la mail all'admin)
            log.critical("Pagina NON aggiornata: tengo quella precedente (%s)", out)
            return 1
        scrivi_stato(stato, [os.path.dirname(STATO)], folder if site else None)   # stato.json nella radice del sito
        # REGISTRO LIVE dei segnali: si salva solo adesso, ad aggiornamento approvato, e mai con esito critico
        # (dati sospetti = possibili segnali finti). Vedi cot_radar/registro.py
        if stato["esito"] != "critico":
            registro.salva()
        else:
            log.warning("registro segnali non aggiornato: esito critico")
        segnala_a_github(stato)
        log.info("Esito: %s (%d errori, %d avvisi)", stato["esito"].upper(), stato["errori"], stato["avvisi"])

    # REGISTRO ADMIN (vedi cot_radar/admin.py): sul sito cifrato con il Secret ADMIN_PASSWORD
    # (senza password: non pubblicato), sul PC in chiaro perche' la pagina resta locale.
    reg = {k: stato.get(k) for k in ("creato", "esito", "errori", "avvisi", "durata_s", "fonti", "strumenti",
                                       "coppie", "critici", "voci")}
    blocco = admin.cifra(reg, os.environ.get("ADMIN_PASSWORD", "")) if site else {"chiaro": reg}
    if site and blocco is None:
        log.info("Registro admin non pubblicato (manca il Secret ADMIN_PASSWORD o la libreria cryptography)")
    page = page.replace('"__ADMIN__"', json.dumps(blocco, ensure_ascii=False).replace("</", "<\\/"), 1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    log.info("Pagina creata: %s  |  registro: %s", out, REGISTRO)
    if site:
        # LANDING PAGE (vetrina.py) con i numeri veri di questo giro. Isolata: se fallisce il terminale e' gia' salvo
        try:
            from cot_radar import vetrina
            vetrina.crea(folder)
        except Exception:
            log.error("landing page non creata:\n%s", traceback.format_exc())
        # SCHEDA AZIONI: dati del ramo "azioni" (workflow azioni.yml) copiati in <sito>/azioni/.
        # Su GitHub dal ramo; sul PC da una cartella indicata in AZIONI_LOCALE (prova). Mai bloccante.
        try:
            from cot_radar import azioni
            if os.environ.get("AZIONI_LOCALE"):
                azioni.copia_nel_sito(folder, cartella_locale=os.environ["AZIONI_LOCALE"])
            elif os.environ.get("GITHUB_ACTIONS"):
                azioni.copia_nel_sito(folder)
                from cot_radar import pattern
                pattern.copia_nel_sito(folder)
        except Exception:
            log.warning("dati azioni non copiati nel sito:\n%s", traceback.format_exc())
    if not site and "--no-open" not in argv:
        webbrowser.open("file:///" + out.replace("\\", "/").lstrip("/"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
