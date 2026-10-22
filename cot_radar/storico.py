"""
storico.py - ARCHIVIO PERMANENTE dei prezzi giornalieri (decenni di dati) per la stagionalita'.

Dove sta:
  - sul PC: cartella  storico/  (un file CSV per serie FRED, es. storico/DEXUSEU.csv)
  - su GitHub: ramo separato "storico" del repository (vedi sito.yml): resta salvato per sempre,
    con la cronologia di ogni modifica, e non si mescola con il codice.

Regole di sicurezza (il sito non deve MAI rompersi per colpa dei dati):
  1. Lo storico gia' salvato NON viene mai riscritto: si aggiungono solo i giorni nuovi.
  2. I giorni nuovi arrivano dalla normale copia FRED della dashboard: nessuna chiamata in piu' ai server.
     Solo la PRIMA volta (archivio vuoto) si scarica tutta la storia della serie.
  3. Ogni dato nuovo viene controllato: valori <= 0 o salti impossibili NON vengono salvati
     (riga CRITICAL nel registro admin + mail). Un salto vero (es. franco svizzero 2015) viene
     accettato solo se i giorni successivi lo confermano.
  4. Se un file e' illeggibile o il download fallisce si tiene quello che c'e' e lo si segnala:
     la stagionalita' usa l'ultimo archivio buono.
DEBUG: python -c "from cot_radar import storico; print({k: len(v) for k, v in storico.leggi_tutto().items()})"
"""
import csv
import json
import math
import os
from datetime import date

from .config import PRICES, ROOT
from .log import log

CARTELLA = os.path.join(ROOT, "storico")
META = "_meta.json"                  # quali serie sono gia' state scaricate per intero
INIZIO = "1960-01-01"               # "tutta la storia": FRED parte da dove ha i dati
MIN_PUNTI = 500                     # un download completo con meno punti e' sospetto
SALTO_MIN = 0.04                    # salto giornaliero minimo (4%) per essere "sospetto"...
SALTO_VOLTE = 12                    # ...e comunque almeno 12 volte il movimento tipico della serie


def serie_prezzi():
    """Codici FRED delle serie di prezzo da archiviare (uno per strumento, senza doppioni)."""
    return sorted({sid for sid, _ in PRICES.values()})


def _file(cartella, sid):
    return os.path.join(cartella, sid + ".csv")


def leggi(cartella, sid):
    """[[data, valore], ...] dal CSV; None se il file non c'e'. Solleva errore se e' rovinato."""
    f = _file(cartella, sid)
    if not os.path.exists(f):
        return None
    out = []
    with open(f, encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if r and r[0] != "data":
                out.append([r[0], float(r[1])])
    if any(out[i][0] >= out[i + 1][0] for i in range(len(out) - 1)):
        raise ValueError("date non in ordine")
    return out


def _scrivi(cartella, sid, pts):
    """Scrittura 'atomica': prima un file temporaneo, poi lo sostituisce (mai un CSV scritto a meta')."""
    os.makedirs(cartella, exist_ok=True)
    tmp = _file(cartella, sid) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["data", "valore"])
        w.writerows([d, repr(v)] for d, v in pts)
    os.replace(tmp, _file(cartella, sid))


def _meta(cartella):
    try:
        with open(os.path.join(cartella, META), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _salva_meta(cartella, meta):
    os.makedirs(cartella, exist_ok=True)
    with open(os.path.join(cartella, META), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, sort_keys=True)


def _movimento_tipico(pts):
    """Mediana dei movimenti giornalieri (log) degli ultimi 250 giorni: misura "quanto si muove di solito"."""
    r = sorted(abs(math.log(pts[i][1] / pts[i - 1][1])) for i in range(max(1, len(pts) - 250), len(pts))
               if pts[i][1] > 0 and pts[i - 1][1] > 0)
    return r[len(r) // 2] if r else 0.01


def nuovi_validi(vecchi, nuovi, sid):
    """Dei punti nuovi (gia' filtrati: solo date dopo l'ultima salvata) tiene quelli plausibili.
    Al primo punto non valido si ferma: meglio un giorno in meno che un dato sbagliato per sempre."""
    tipico = _movimento_tipico(vecchi)
    soglia = max(SALTO_MIN, SALTO_VOLTE * tipico)
    buoni, prec = [], vecchi[-1][1]
    for i, (d, v) in enumerate(nuovi):
        if not v or v <= 0 or math.isnan(v):
            log.critical("storico %s: valore impossibile il %s (%r): NON salvato, tengo l'archivio com'era", sid, d, v)
            break
        salto = abs(math.log(v / prec))
        if salto > soglia:
            dopo = nuovi[i + 1:i + 3]               # un salto vero resta: i 2 giorni dopo devono stare vicini
            if len(dopo) == 2 and all(x[1] > 0 and abs(math.log(x[1] / v)) < salto / 2 for x in dopo):
                log.warning("storico %s: salto del %.1f%% il %s confermato dai giorni successivi: salvato",
                            sid, salto * 100, d)
            else:
                log.critical("storico %s: salto anomalo del %.1f%% il %s: NON salvato (in attesa di conferma)",
                             sid, salto * 100, d)
                break
        buoni.append([d, v])
        prec = v
    return buoni


def aggiorna(fred, scarica=None, cartella=CARTELLA, fred_giu=False):
    """Aggiunge all'archivio i giorni nuovi presenti in 'fred' (copia della dashboard).
    scarica(sid, inizio) = funzione per il download COMPLETO (solo per le serie mai scaricate).
    fred_giu=True: FRED e' in manutenzione, niente download completi (si riprova al prossimo giro).
    Restituisce (archivio {sid: punti}, riepilogo {"ok": n, "nuovi": n, "problemi": [...]})."""
    meta = _meta(cartella)
    archivio, rie = {}, {"ok": 0, "nuovi": 0, "problemi": []}
    rete_ko = False                                  # al primo download fallito non insisto con gli altri
    for sid in serie_prezzi():
        try:
            vecchi = leggi(cartella, sid)
        except Exception as e:
            log.critical("storico %s illeggibile (%s): non lo tocco, la stagionalita' di questa serie e' sospesa", sid, e)
            rie["problemi"].append(sid)
            continue
        if not vecchi or sid not in meta:           # mai scaricata per intero: download completo (una volta sola)
            if fred_giu or scarica is None or rete_ko:
                if vecchi:
                    archivio[sid] = vecchi
                continue
            try:
                tutto = scarica(sid, INIZIO)
            except Exception as e:
                log.warning("storico %s: download completo non riuscito (%s): non insisto con le altre serie, "
                            "riprovo al prossimo aggiornamento", sid, e)
                rete_ko = True
                if vecchi:
                    archivio[sid] = vecchi
                rie["problemi"].append(sid)
                continue
            if len(tutto) < MIN_PUNTI or (vecchi and len(tutto) < 0.98 * len(vecchi)):
                log.critical("storico %s: download completo sospetto (%d punti): NON salvato", sid, len(tutto))
                if vecchi:
                    archivio[sid] = vecchi
                rie["problemi"].append(sid)
                continue
            _scrivi(cartella, sid, tutto)
            meta[sid] = date.today().isoformat()
            log.info("storico %s: archivio creato, %d giorni dal %s", sid, len(tutto), tutto[0][0])
            vecchi = tutto
        nuovi = [p for p in (fred.get(sid) or []) if p[0] > vecchi[-1][0]]
        if nuovi:
            buoni = nuovi_validi(vecchi, nuovi, sid)
            if len(buoni) < len(nuovi):
                rie["problemi"].append(sid)
            if buoni:
                vecchi = vecchi + buoni
                _scrivi(cartella, sid, vecchi)
                rie["nuovi"] += len(buoni)
        archivio[sid] = vecchi
        rie["ok"] += 1
    try:
        _salva_meta(cartella, meta)
    except OSError as e:
        log.warning("storico: indice non salvato (%s)", e)
    log.info("storico: %d serie pronte, %d giorni aggiunti%s", rie["ok"], rie["nuovi"],
             f", problemi: {', '.join(rie['problemi'])}" if rie["problemi"] else "")
    return archivio, rie


def prezzi_usd(archivio):
    """{chiave strumento: [(data, prezzo in dollari)]} con il verso giusto (es. JPY: 1/x)."""
    out = {}
    for k, (sid, verso) in PRICES.items():
        pts = archivio.get(sid) or []
        out[k] = [(d, v if verso > 0 else 1 / v) for d, v in pts if v and v > 0]
    return {k: v for k, v in out.items() if v}
