# -*- coding: utf-8 -*-
"""
briefing.py - BRIEFING DEL LUNEDI' MATTINA per il canale Telegram (formato lungo, "stile report di banca").

COSA E'
  Un messaggio ragionato, diviso in sezioni con emoji, che ogni lunedi' mattina riassume la situazione:
    📌 COSA MONITORARE NEL PORTAFOGLIO   mercati del portafoglio modello (Moderato) con semaforo 🟢🟡🔴
    🎯 MESSAGGIO CHIAVE                  due o tre frasi che dicono il tono della settimana
    ✍️ FOREX UPDATE                      una scheda per valuta (🇺🇸 🇪🇺 🇬🇧 🇯🇵 🇨🇭 🇨🇦 🇦🇺 🇳🇿)
    🏦 BANCHE CENTRALI E DATI            gli eventi ad alto impatto dei prossimi giorni
    🧭 ALTRI MERCATI                     azioni, oro/petrolio, crypto con un segnale attivo

REGOLA D'ORO: OGNI FRASE NASCE DA UN DATO DELLA DASHBOARD PUBBLICA (la costante "D" dentro index.html), la stessa
che vede chi apre il sito. Niente opinioni di terzi, niente previsioni inventate, niente testi copiati: i
"livelli" sono l'ampiezza TIPICA della settimana calcolata dallo storico del prezzo (non una previsione) e gli
"scenari" sono condizioni misurabili ("il segnale si chiude se il punteggio scende sotto 25").
Se un dato manca, la riga semplicemente non compare (mai un numero di ripiego).

QUANDO PARTE: lo decide notifiche.py (lunedi' dalle 05:30 UTC in poi, una sola volta a settimana; se il giro
del lunedi' salta, riprova il martedi'). In piu' esiste il comando di prova (workflow "Prova notifiche").

DEBUG: python -c "from cot_radar import riepilogo, briefing as b; d=riepilogo.scarica('https://utente.github.io/cot-radar/'); print(b.testi(d,'')[0])"
"""
from datetime import datetime, timedelta, timezone

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
        "novembre", "dicembre"]
# valuta -> (bandiera, nome, coppia di riferimento sul grafico, valuta e' la prima della coppia?)
VALUTE = [("USD", "🇺🇸", "DOLLARO USA", None), ("EUR", "🇪🇺", "EURO", "EURUSD"), ("GBP", "🇬🇧", "STERLINA", "GBPUSD"),
          ("JPY", "🇯🇵", "YEN", "USDJPY"), ("CHF", "🇨🇭", "FRANCO SVIZZERO", "USDCHF"),
          ("CAD", "🇨🇦", "DOLLARO CANADESE", "USDCAD"), ("AUD", "🇦🇺", "DOLLARO AUSTRALIANO", "AUDUSD"),
          ("NZD", "🇳🇿", "DOLLARO NEOZELANDESE", "NZDUSD")]
GRUPPI_ALTRI = [("Indici azionari", "📈", "Azioni"), ("Metalli", "🥇", "Metalli"), ("Energia", "🛢️", "Energia"),
                ("Crypto", "₿", "Crypto")]
AVVERTENZA = ("Analisi di scenario costruita dai dati di BoardEdge (COT CFTC, FRED, BCE, Yahoo Finance), "
              "non consulenza finanziaria.")


def _esc(t):
    from html import escape
    return escape(str(t), quote=False)


def _n(x, dec=1, segno=False):
    """Numero all'italiana: 3,2 / +3,2 / 1.250."""
    if x is None:
        return "n.d."
    s = f"{x:+,.{dec}f}" if segno else f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _data_it(iso):
    """'2026-10-23' -> '23/10'."""
    return f"{iso[8:10]}/{iso[5:7]}" if iso and len(iso) >= 10 else ""


# --------------------------------------------------------------------------- piccoli traduttori dato -> parola
def posizionamento(a):
    """Parole per il posizionamento speculativo (idx = percentile 0-100 della posizione netta)."""
    i = a.get("idx")
    if i is None:
        return None
    if i >= 85:
        t = "molto long, vicino ai massimi storici recenti"
    elif i >= 60:
        t = "orientato al long"
    elif i > 40:
        t = "equilibrato"
    elif i > 15:
        t = "orientato allo short"
    else:
        t = "molto short, vicino ai minimi storici recenti"
    return t + (" (posizione affollata: occhio alle inversioni)" if a.get("crowded") else "")


def flusso(a):
    """Cosa hanno fatto i grandi speculatori nell'ultima settimana (contratti netti)."""
    d = a.get("d_net")
    if not d:
        return "posizione netta invariata nell'ultima settimana"
    return ("acquisti netti" if d > 0 else "vendite nette") + f" per {_n(abs(d), 0)} contratti nell'ultima settimana"


def semaforo(trend):
    """🟢 sopra la media a 200 giorni con margine, 🟡 vicino alla media (rischio di uscita/ingresso), 🔴 sotto."""
    if trend is None:
        return "⚪"
    if trend < 0:
        return "🔴"
    return "🟡" if trend < 1.5 else "🟢"


# --------------------------------------------------------------------------- sezioni
def sezione_portafoglio(dati):
    """📌 Mercati del portafoglio Moderato col semaforo del trend, e quota di liquidita' dei tre profili."""
    prof = [p for p in (dati.get("port") or {}).get("profili") or []]
    mod = next((p for p in prof if p["id"] == "moderato"), prof[0] if prof else None)
    if not mod:
        return None
    righe = ["<b>📌 COSA MONITORARE NEL PORTAFOGLIO</b>",
             f"Profilo {_esc(mod['nome'])}, rotazione del {_data_it(dati['port'].get('rotazione'))}:"]
    for c in mod["composizione"]:
        if c["k"] in ("CASH",):
            continue
        t = c.get("trend")
        righe.append(f"{semaforo(t)} {_esc(c['nome'])} {_n(c['peso'], 0)}%"
                     + (f" · {_n(t, 1, True)}% dalla media a 200 giorni" if t is not None else ""))
    for e in mod.get("esclusi") or []:
        if e["k"] == "AZ":
            nome = "Azioni scelte"
        else:
            nome = next((x["nome"] for x in mod["base"] if x["k"] == e["k"]), e["k"])
        t = e.get("trend")
        righe.append(f"🔴 {_esc(nome)} {_n(e.get('base'), 0)}%: in pausa" +
                     (f" ({_n(t, 1, True)}% dalla media)" if t is not None else ""))
    liq = {p["id"]: next((c["peso"] for c in p["composizione"] if c["k"] == "CASH"), 0) for p in prof}
    righe.append("")
    righe.append("Liquidità oggi: " + " · ".join(f"{_esc(p['nome'])} {_n(liq.get(p['id'], 0), 0)}%" for p in prof))
    pros = (dati.get("port") or {}).get("prossima")
    if pros:
        d = datetime.strptime(pros, "%Y-%m-%d")
        righe.append(f"Prossima rotazione: {GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}. "
                     "🟢 sopra la media · 🟡 vicino alla media (può cambiare alla rotazione) · 🔴 in pausa.")
    return "\n".join(righe)


def _driver(dati, chiave):
    return next((x for x in (dati.get("market") or {}).get("drivers") or [] if x.get("key") == chiave), None)


def messaggio_chiave(dati, oggi):
    """🎯 Tono della settimana in due-tre frasi: mercato (VIX, spread), segnali COT, eventi."""
    frasi = []
    vix, hy = _driver(dati, "vix"), _driver(dati, "hy")
    if vix:
        tono = "in rialzo" if (vix.get("d4") or 0) > 1 else "in calo" if (vix.get("d4") or 0) < -1 else "stabile"
        frasi.append(f"La paura sui mercati (VIX {_n(vix['value'], 1)}) è {tono} rispetto a quattro settimane fa "
                     f"({_n(vix.get('d4'), 1, True)} punti)"
                     + (f"; lo spread sulle obbligazioni ad alto rischio è a {_n(hy['value'] * 100, 0)} punti base"
                        f" ({_n(hy.get('d4'), 0, True)} pb in 4 settimane)." if hy else "."))
    assets, pairs = dati.get("assets") or {}, dati.get("pairs") or []
    attivi = [p for p in pairs if p.get("label") not in (None, "NEUTRO")]
    nuovi = [p for p in attivi if p.get("new")]
    ass_att = [a for a in assets.values() if a.get("label") not in (None, "NEUTRO") and a.get("group") != "Valute"]
    fx = "nessuna coppia Forex" if not attivi else "1 coppia Forex" if len(attivi) == 1 else f"{len(attivi)} coppie Forex"
    altri = "nessun altro mercato" if not ass_att else "1 altro mercato" if len(ass_att) == 1 else f"{len(ass_att)} altri mercati"
    frasi.append(f"Il COT segnala {fx} e {altri} con un segnale attivo"
                 + ((f", di cui {len(nuovi)} " + ("nato" if len(nuovi) == 1 else "nati") + " con l'ultimo report.") if nuovi else "."))
    aff = sorted([(k, a) for k, a in assets.items() if a.get("crowded") and a.get("group") == "Valute" and k != "USD"],
                 key=lambda x: -abs((x[1].get("idx") or 50) - 50))
    if aff:
        nomi = ", ".join(f"{a.get('it') or k}" for k, a in aff[:3])
        frasi.append(f"Posizioni speculative molto affollate su: {_esc(nomi)}. Quando tutti sono dalla stessa parte "
                     "basta poco per un'inversione.")
    ev = eventi_settimana(dati, oggi)
    if ev:
        frasi.append("In agenda: " + ", ".join(f"{_esc(e['nome'])} ({GIORNI[e['d'].weekday()][:3]} {e['d'].day})"
                                               for e in ev[:3]) + ".")
    return "<b>🎯 MESSAGGIO CHIAVE</b>\n" + " ".join(frasi)


def _area_settimana(dati, coppia):
    """Area TIPICA di oscillazione della settimana: ultimo prezzo +/- movimento medio settimanale storico.
    NON e' una previsione: e' l'ampiezza che il prezzo ha di solito in una settimana."""
    v = (dati.get("vol") or {}).get(coppia)
    if not v or not v.get("prezzo") or not (v.get("settimane") or {}).get("media"):
        return None
    p, m = v["prezzo"], v["settimane"]["media"] / 100
    dec = 2 if p > 20 else 4
    return f"{_n(p * (1 - m), dec)} – {_n(p * (1 + m), dec)}", _n(m * 100, 1), _n(p, dec)


def sezione_forex(dati):
    """✍️ Una scheda per valuta, solo con dati veri del COT e dei driver."""
    assets, pairs = dati.get("assets") or {}, dati.get("pairs") or []
    righe = ["<b>✍️ FOREX UPDATE</b>"]
    us2y, diff = _driver(dati, "us2y"), _driver(dati, "diff")
    fed = dati.get("fed") or {}
    for cod, bandiera, nome, coppia in VALUTE:
        a = assets.get(cod) or (assets.get("DXY") if cod == "USD" else None)
        if not a:
            continue
        blocco = [f"\n<b>{bandiera} {nome}</b>"]
        pos = posizionamento(a)
        if pos:
            blocco.append(f"Speculatori: {pos}; {flusso(a)}.")
        if cod == "USD" and us2y:
            blocco.append(f"Tasso USA a 2 anni al {_n(us2y['value'], 2)}% ({_n(us2y.get('d4'), 1, True)} pb in 4 settimane)"
                          + (f"; differenziale con l'Europa {_n(diff['value'] * 100 if diff['value'] < 10 else diff['value'], 0)} pb."
                             if diff else "."))
            if fed.get("regime"):
                blocco.append(f"Bilancio della Fed: {_esc(fed['regime'])} ({_n(fed.get('bs13'), 1, True)}% in 13 settimane).")
        m = (a.get("mkt") or {}).get("status")
        if m and cod != "USD":
            testa_m, _, resto = m.partition(":")                  # "IN RITARDO: i driver..." -> "In ritardo: i driver..."
            blocco.append("Driver di mercato: " + _esc(testa_m.capitalize() + (":" + resto if resto else "")) + ".")
        segn = [p for p in pairs if cod in (p.get("base"), p.get("quote")) and p.get("label") not in (None, "NEUTRO")]
        for p in sorted(segn, key=lambda p: -abs(p.get("score") or 0))[:2]:
            blocco.append(f"{'▲' if 'BUY' in p['label'] else '▼'} {p['base']}/{p['quote']}: <b>{p['label']}</b> "
                          f"({_n(p['score'], 1, True)}); si chiude se il punteggio scende sotto "
                          f"{_n((dati.get('meta') or {}).get('normal', 25), 0)}.")
        ar = _area_settimana(dati, coppia) if coppia else None
        if ar:
            blocco.append(f"Ampiezza tipica della settimana per {coppia[:3]}/{coppia[3:]}: {ar[0]} "
                          f"(±{ar[1]}% sull'ultimo prezzo {ar[2]}, media storica, non una previsione).")
        if len(blocco) > 1:
            righe.append("\n".join(blocco))
    return "\n".join(righe) if len(righe) > 1 else None


def eventi_settimana(dati, oggi):
    """Eventi ad alto impatto dei prossimi 7 giorni: [{nome, valuta, d, ora, tipo}]."""
    out = []
    for e in dati.get("eventi") or []:
        try:
            t = datetime.strptime(e["quando"], "%Y-%m-%d %H:%M")
        except (KeyError, ValueError):
            continue
        if oggi.date() <= t.date() <= oggi.date() + timedelta(days=7):
            out.append({"nome": e["nome"], "valuta": e.get("valuta", ""), "d": t, "tipo": e.get("tipo")})
    return sorted(out, key=lambda e: e["d"])


def sezione_eventi(dati, oggi):
    ev = eventi_settimana(dati, oggi)
    if not ev:
        return None
    righe = ["<b>🏦 BANCHE CENTRALI E DATI DELLA SETTIMANA</b>"]
    for e in ev:
        righe.append(f"{'🏦' if e['tipo'] == 'banca' else '📊'} {GIORNI[e['d'].weekday()][:3]} {e['d']:%d/%m} "
                     f"ore {e['d']:%H:%M} · <b>{_esc(e['nome'])}</b> ({_esc(e['valuta'])})")
    righe.append("Il giorno del dato la volatilità sale: per un ingresso swing conviene aspettare l'uscita. "
                 "Il calendario dettagliato con orari italiani arriva il venerdì sera.")
    return "\n".join(righe)


def sezione_altri(dati):
    """🧭 Azioni, metalli, energia, crypto: solo i mercati con un segnale attivo, in una riga ciascuno."""
    assets = dati.get("assets") or {}
    righe = ["<b>🧭 ALTRI MERCATI</b>"]
    for gruppo, icona, nome in GRUPPI_ALTRI:
        voci = [a for a in assets.values() if a.get("group") == gruppo and a.get("label") not in (None, "NEUTRO")
                and a.get("key") != "VIX"]
        voci.sort(key=lambda a: -abs(a.get("score") or 0))
        if voci:
            righe.append(f"{icona} <b>{nome}</b>: " + " · ".join(
                f"{'▲' if 'BUY' in a['label'] else '▼'} {_esc(a.get('it') or a['key'])} {a['label']} "
                f"({_n(a['score'], 1, True)})" + (" ⚠️ affollato" if a.get("crowded") else "")
                for a in voci[:4]))
    return "\n".join(righe) if len(righe) > 1 else None


# --------------------------------------------------------------------------- messaggio completo
def testi(dati, sito, oggi=None, test=False):
    """Lista di messaggi HTML per Telegram (divisi tra una sezione e l'altra se superano il limite)."""
    from .notifiche import _escape, impagina
    oggi = oggi or datetime.now(timezone.utc).replace(tzinfo=None)
    testa = (("[TEST] " if test else "") + f"<b>BoardEdge · briefing del {GIORNI[oggi.weekday()]} "
             f"{oggi.day} {MESI[oggi.month - 1]}</b>\n<i>Cosa guardare questa settimana, dai dati del terminale</i>\n\n")
    sezioni = [s for s in (sezione_portafoglio(dati), messaggio_chiave(dati, oggi), sezione_forex(dati),
                           sezione_eventi(dati, oggi), sezione_altri(dati)) if s]
    piede = "\n\n" + (f'<a href="{_escape(sito.rstrip("/"))}/terminale/">Apri il terminale BoardEdge</a>\n' if sito else "") + \
        f"<i>{AVVERTENZA}</i>"
    return impagina(testa, sezioni, piede)
