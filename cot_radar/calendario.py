# -*- coding: utf-8 -*-
"""
calendario.py - quando escono i dati e se sono in ritardo.

Le uscite USA sono fissate in ora di New York. Per convertirle in ora italiana serve sapere
l'ora legale di ENTRAMBI i paesi, che cambiano in date diverse: per circa una settimana a marzo e
una a fine ottobre/novembre il COT esce alle 20:30 italiane invece che alle 21:30.
Calcoliamo tutto a mano (niente librerie di fusi orari, che su Windows spesso mancano).
"""
import re
from datetime import date, datetime, timedelta, timezone

from .calcoli import add_month
from .config import K_Y10

GG = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


def _nth_sunday(y, mo, n):
    """n-esima domenica del mese (USA: ora legale dalla 2a domenica di marzo alla 1a di novembre)."""
    d = date(y, mo, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_sunday(y, mo):
    """Ultima domenica del mese (UE: ora legale dall'ultima di marzo all'ultima di ottobre)."""
    d = date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def et_to_utc(d, hh, mm):
    """Ora di New York del giorno d -> data/ora UTC."""
    dst = _nth_sunday(d.year, 3, 2) <= d < _nth_sunday(d.year, 11, 1)
    return datetime(d.year, d.month, d.day, hh, mm) + timedelta(hours=4 if dst else 5)


def utc_to_it(dt):
    """UTC -> ora italiana."""
    d = dt.date()
    return dt + timedelta(hours=2 if _last_sunday(d.year, 3) <= d < _last_sunday(d.year, 10) else 1)


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def weekly_schedule(last_date, weekday, hh, mm, offset):
    """Per un dato settimanale pubblicato il giorno `weekday` (0=lunedi') alle hh:mm di New York,
    riferito a `offset` giorni prima della pubblicazione (COT: venerdi', dati del martedi' -> offset 3).

    Restituisce: data attesa dell'ultimo dato, se siamo in ritardo, ultima e prossima uscita (ora italiana)."""
    now = utcnow()
    d = now.date()
    while d.weekday() != weekday or et_to_utc(d, hh, mm) > now:   # torna indietro fino all'ultima uscita passata
        d -= timedelta(days=1)
    exp = (d - timedelta(days=offset)).isoformat()
    nxt = d + timedelta(days=7)
    ms = int((et_to_utc(nxt, hh, mm) - datetime(1970, 1, 1)).total_seconds() * 1000)   # per il JavaScript
    return {"expected": exp, "late": (last_date or "") < exp, "last_pub": utc_to_it(et_to_utc(d, hh, mm)),
            "next": utc_to_it(et_to_utc(nxt, hh, mm)), "next_ms": ms}


def fd(s):
    """Data in italiano: "2026-10-13" -> "mar 13/10/2026", "2026-08" -> "ago 2026". Mai un errore: al peggio "n/d"."""
    try:
        if len(s) == 7:
            return f"{MESI[int(s[5:7]) - 1]} {s[:4]}"
        d = datetime.strptime(s[:10], "%Y-%m-%d").date()
        return f"{GG[d.weekday()]} {d.strftime('%d/%m/%Y')}"
    except Exception:
        return "n/d"


def fdt(dt):
    return f"{GG[dt.weekday()]} {dt.strftime('%d/%m')} ore {dt.strftime('%H:%M')}"


def sources_status(cache, status, errors, assets, mort, fred):
    """Un riquadro per ogni fonte: ultimo dato, prossima uscita, stato.
    st = "ok" (verde), "cache" (giallo: dati salvati), "late" (rosso: dato atteso non uscito), "err" (download fallito)."""
    out = []
    today = date.today()

    last_cot = max(a["date"] for a in assets.values() if a.get("date"))
    c = weekly_schedule(last_cot, 4, 15, 30, 3)                        # venerdi' 15:30 NY, dati del martedi'
    out.append({"name": "COT (CFTC)", "last": fd(last_cot), "next": fdt(c["next"]), "next_ms": c["next_ms"],
                "st": "late" if c["late"] else ("ok" if status["cot"] == "online" else "cache"),
                "msg": (f"Il report con i dati al {fd(c['expected'])} doveva uscire {fdt(c['last_pub'])} ma la CFTC "
                        f"non l'ha ancora pubblicato (festivita' USA, shutdown o ritardo)." if c["late"] else "")})

    if "WALCL" in fred:
        lf = fred["WALCL"][-1][0]
        f = weekly_schedule(lf, 3, 16, 30, 1)                          # giovedi' 16:30 NY, dati del mercoledi'
        out.append({"name": "Bilancio Fed", "last": fd(lf), "next": fdt(f["next"]), "next_ms": f["next_ms"],
                    "st": "late" if f["late"] else ("ok" if status["fred"] == "online" else "cache"),
                    "msg": f"Il bilancio Fed del {fd(f['expected'])} non e' ancora su FRED." if f["late"] else ""})

    # serie giornaliere/settimanali: "in ritardo" se l'ultimo dato e' piu' vecchio di `tol` giorni
    for name, s, tol, nxt in (("Mercati USA (FRED)", fred.get("DGS2"), 5, "giornaliero"),):
        if s:
            late = s[-1][0] < (today - timedelta(days=tol)).isoformat()
            out.append({"name": name, "last": fd(s[-1][0]), "next": nxt,
                        "st": "late" if late else ("ok" if status["fred"] in ("online", "parziale") else "cache"),
                        "msg": f"Ultimo dato {fd(s[-1][0])}: nessun aggiornamento da piu' di {tol} giorni." if late else ""})

    ecb = cache.get("ecb", {}).get("data", {})
    if K_Y10 in ecb:
        l = ecb[K_Y10][-1][0]
        late = l < (today - timedelta(days=5)).isoformat()
        out.append({"name": "Tassi mercato BCE", "last": fd(l), "next": "giornaliero",
                    "st": "late" if late else ("ok" if status["ecb"] in ("online", "parziale") else "cache"),
                    "msg": f"Curva BCE ferma al {fd(l)}." if late else ""})
    if mort:
        # dato mensile pubblicato ~5 settimane dopo la fine del mese: atteso = mese di (oggi - 40 giorni) - 1
        exp = add_month((today - timedelta(days=40)).strftime("%Y-%m"), -1)
        late = mort["last"] < exp
        out.append({"name": "Tassi mutui (BCE)", "last": fd(mort["last"]), "next": "mensile (~5 settimane dopo)",
                    "st": "late" if late else ("ok" if status["ecb"] in ("online", "parziale") else "cache"),
                    "msg": f"Il dato di {fd(exp)} sui mutui doveva gia' essere pubblicato." if late else ""})

    # errori di download, riassunti in una riga per fonte
    for grp, nm in (("cot", "CFTC"), ("fred", "FRED"), ("ecb", "BCE")):
        if status.get(grp) == "manutenzione":
            out.append({"name": f"Download {nm}", "last": "", "next": "", "st": "cache",
                        "msg": "in manutenzione. "         # testo pubblico: breve e professionale
                               + ("Serie principali da fonti ufficiali alternative, le altre dagli ultimi dati disponibili."
                                  if status.get("fred_riserva") else "In uso gli ultimi dati disponibili.")
                               + " Aggiornamento automatico al ripristino."})
            continue
        if status.get(grp) in ("cache", "assente", "parziale") and errors.get(grp):
            e = errors[grp]
            lst = [e] if isinstance(e, str) else e
            why = (lst[0].split(": ", 1)[-1] if not isinstance(e, str) else e).replace("<urlopen error ", "").rstrip(">")[:140]
            n = f" per {len(lst)} serie" if not isinstance(e, str) else ""
            saved = "uso i dati salvati" if status[grp] != "assente" else "nessun dato salvato"
            # GRAVE = l'intera fonte non ha risposto (nessun dato nuovo): solo allora la pagina mostra il popup di
            # manutenzione con il codice d'errore. Una sola serie mancante (stato "parziale") resta silenziosa per gli
            # utenti: il dettaglio tecnico rimane in "msg" (registro admin, log del workflow).
            cod = re.search(r"\b([45]\d\d)\b", why)
            out.append({"name": f"Download {nm}", "last": "", "next": "", "st": "err",
                        "msg": f"non riuscito{n} ({saved}). Motivo: {why}",
                        "grave": status[grp] in ("cache", "assente"),
                        "codice": cod.group(1) if cod else "503"})
    return out
