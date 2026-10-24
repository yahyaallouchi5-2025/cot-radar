# -*- coding: utf-8 -*-
"""
backtest.py - BACKTEST STORICO (SIMULATO): il motore dei segnali applicato a tutte le settimane dal 1986.

Cosa fa, settimana per settimana, usando SOLO i dati disponibili in quel momento ("point-in-time"):
  1. punteggio COT di ogni strumento con i soli report fino a quel martedi' (stessa formula del sito);
  2. etichette di coppie e strumenti con le stesse regole del sito (soglie, divergenza, dollaro composito);
  3. conferme di allora: Commercials agli estremi e affidabilita' storica (solo esiti gia' noti a quella data);
  4. il segnale "nasce" al momento della pubblicazione del report (venerdi' 15:30 di New York) e viene
     misurato con motore.misura(), esattamente come nel registro live.

Differenze dal sito (dichiarate anche nella pagina):
  - niente parte "Mercato e macro" (30% del punteggio live) e niente notizie: il mercato di allora non si
    ricostruisce in modo affidabile, quindi qui conta solo COT + conferme;
  - stagionalita' non inclusa nel calcolo dell'affidabilita';
  - costi stimati (spread + commissioni) sottratti, swap/rollover esclusi;
  - prezzi solo di chiusura (FRED): MFE e MAE sono sulle chiusure giornaliere.

HOLDOUT: gli ultimi 2 anni sono tenuti separati ("fuori campione"). Se un giorno si cambiano pesi o soglie
guardando il backtest, il giudizio vero lo da' solo il periodo di holdout, che non va usato per tarare.

DEBUG: python -c "from cot_radar import backtest; ..." oppure python -m unittest tests.test_backtest -v
"""
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

from . import motore, volatilita
from .eventi import Calendario
from .config import ASSETS, EXTRA_PAIRS, FX_ORDER, NORMAL, PAIR_NAMES
from .conferme import ORIZZONTE, MIN_SEGNALI, _al, accordo, commercials
from .cot import cot_series, cot_strength, is_divergence, label
from .log import log
from .registro import SALTA_FX
from .stagionalita import prezzo_coppia

FINESTRA = 170                 # settimane passate a cot_strength: bastano (indice a 156, z-score a 52)
SETT_AFFID = 175               # come il sito: l'affidabilita' storica guarda le ultime 175 settimane
HOLDOUT_GIORNI = 730           # ultimi 2 anni = fuori campione
ULTIMI = 12                    # segnali simulati mostrati nella pagina
MAJORS = ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")


def punteggi(ser):
    """{martedi': (punteggio COT, verso Commercials)} con i soli dati fino a ogni settimana."""
    out = {}
    for t in range(29, len(ser)):
        s = ser[max(0, t - FINESTRA):t + 1]
        st = cot_strength(s, len(s) - 1)
        if st:
            c = commercials(s)
            out[ser[t]["date"]] = (st["cot"], c)
    return out


def _esiti_settimanali(sc_per_data, pts):
    """Per l'affidabilita' storica (come conferme.esito): per ogni settimana con segnale, esito a 4 settimane
    dal venerdi' di pubblicazione. Restituisce [(martedi', giorno in cui l'esito e' noto, vinto)]."""
    out = []
    for d, sc in sorted(sc_per_data.items()):
        if sc is None:
            continue
        g0 = (date.fromisoformat(d) + timedelta(days=3)).isoformat()
        g1d = date.fromisoformat(d) + timedelta(days=3 + ORIZZONTE)
        a, b = _al(pts, g0), _al(pts, g1d.isoformat())
        if not a or not b or b[0] > (g1d + timedelta(days=7)).isoformat():
            continue
        out.append((d, b[0], (b[1] / a[1] - 1) * (1 if sc > 0 else -1) > 0))
    return out


class Esiti:
    """Esiti settimanali con somme cumulative: l'affidabilita' a una data si calcola in un istante.
    Sia le date dei segnali sia quelle degli esiti sono in ordine crescente, quindi l'insieme valido e' un tratto."""

    def __init__(self, esiti):
        self.t = [x[0] for x in esiti]
        self.g = [x[1] for x in esiti]
        self.cum = [0]
        for x in esiti:
            self.cum.append(self.cum[-1] + (1 if x[2] else 0))

    def a(self, d):
        """Affidabilita' storica nota al martedi' d: esiti delle 175 settimane prima, gia' conclusi entro il venerdi'."""
        da = (date.fromisoformat(d) - timedelta(weeks=SETT_AFFID)).isoformat()
        noto = (date.fromisoformat(d) + timedelta(days=3)).isoformat()
        lo, hi = bisect_left(self.t, da), min(bisect_left(self.t, d), bisect_right(self.g, noto))
        n = hi - lo
        if n <= 0:
            return None
        return {"n": n, "hit": round(100 * (self.cum[hi] - self.cum[lo]) / n), "pochi": n < MIN_SEGNALI}


def simula(cot_righe, prezzi):
    """La simulazione vera e propria, senza statistiche: settimana per settimana con il MOTORE UNICO, poi la misura
    di ogni segnale. Separata da calcola() perche' la usa anche confronto.py (stesso identico motore).
    Restituisce {"misurati": [(segnale, misura, costo%)], "strum", "eventi", "ultima", "limite_h"} oppure None."""
    serie = cot_series(cot_righe)
    per_k = {a[0]: serie[a[1]] for a in ASSETS if a[1] in serie}
    utili = set(MAJORS) | {"DXY"} | {b for b, q in EXTRA_PAIRS} | {q for b, q in EXTRA_PAIRS} | set(FX_ORDER)
    utili |= {k for k in prezzi if k not in SALTA_FX}
    sc = {k: punteggi(s) for k, s in per_k.items() if k in utili}
    if not sc:
        return None

    # dollaro composito: 50% DXY + 50% inverso della media delle altre valute (servono tutte e 7)
    usd = {}
    if all(c in sc for c in MAJORS):
        for d in sc["EUR"]:
            v = [sc[c][d][0] for c in MAJORS if d in sc[c]]
            if len(v) == len(MAJORS):
                inv = -sum(v) / len(v)
                usd[d] = ((0.5 * sc["DXY"][d][0] + 0.5 * inv) if "DXY" in sc and d in sc["DXY"] else inv, None)
        sc["USD"] = usd

    # strumenti misurabili: coppie con entrambi i prezzi + strumenti non valutari con prezzo
    fx = [c for c in FX_ORDER if c in sc]
    combo = [(fx[i], fx[j]) for i in range(len(fx)) for j in range(i + 1, len(fx))] + list(EXTRA_PAIRS)
    strum = {}
    for b, q in combo:
        pts = prezzo_coppia(prezzi, b, q)
        if pts and b in sc and q in sc:
            strum[PAIR_NAMES.get((b, q), b + q)] = {"b": b, "q": q, "pts": pts, "cls": "fx", "costo": motore.costo("", b, q)}
    for k in sc:
        if k in prezzi and k not in SALTA_FX:
            strum[k] = {"pts": prezzi[k], "cls": motore.classe(k), "costo": motore.costo(k)}

    # punteggio ed etichetta di ogni strumento per ogni martedi'
    date_tutte = sorted(set().union(*[set(v) for v in sc.values()]))
    tab = {}
    for nome, s in strum.items():
        riga = {}
        for d in date_tutte:
            if "b" in s:
                xb, xq = sc[s["b"]].get(d), sc[s["q"]].get(d)
                if not xb or not xq:
                    continue
                sb, sq = xb[0], xq[0]
                v = (xb[1]["verso"] if xb[1] else 0) - (xq[1]["verso"] if xq[1] else 0)
                punt = round((sb - sq) / 2, 1)
                lab = label(punt, is_divergence(sb, sq))
                acc = None if v == 0 or lab == "NEUTRO" else ("conferma" if (v > 0) == (punt > 0) else "contrasto")
            else:
                x = sc[nome].get(d)
                if not x:
                    continue
                punt = x[0]
                lab = label(punt, single=True)
                acc = accordo(punt, x[1])
            riga[d] = (punt, lab, acc)
        tab[nome] = riga
        s["esiti"] = Esiti(_esiti_settimanali({d: (p if l != "NEUTRO" else None) for d, (p, l, a) in riga.items()}, s["pts"]))

    # simulazione: settimana per settimana con il MOTORE UNICO (stesse transizioni del registro live)
    aperti, eventi = {}, []
    for d in date_tutte:
        correnti = {}
        for nome, riga in tab.items():
            if d in riga:
                punt, lab, acc = riga[d]
                liv, perche = motore.affidabilita(strum[nome]["esiti"].a(d), acc, None, punt) \
                    if lab != "NEUTRO" else (None, [])
                c = {"etichetta": lab, "punteggio": punt, "affid": liv, "perche": perche}
                if "b" in strum[nome]:
                    c.update(base=strum[nome]["b"], quote=strum[nome]["q"])
                correnti[nome] = c
        if correnti:
            eventi += motore.transizioni(aperti, correnti, motore.utc_iso(motore.pubblicazione_cot(d)), d)
    segnali, _ = motore.applica(eventi)

    # misura e statistiche
    ultima = date_tutte[-1]
    limite_h = (date.fromisoformat(ultima) - timedelta(days=HOLDOUT_GIORNI)).isoformat()
    misurati, reg = [], volatilita.Regimi()
    for sid, s in segnali.items():
        st = strum[s["strumento"]]
        s["vol"] = reg.al_segnale(s["strumento"], st["pts"], s["generato"])   # regime di volatilita' di allora
        m = motore.misura(s, st["pts"], st["cls"])
        if m and m.get("stato") == "ok":
            misurati.append((s, m, st["costo"]))
    # giorni con annunci macro USA nel percorso di ogni trade (per lo studio del drawdown, vedi motore.drawdown)
    motore.prepara_eventi(misurati, Calendario())
    return {"misurati": misurati, "strum": strum, "eventi": eventi, "ultima": ultima, "limite_h": limite_h}


def calcola(cot_righe, prezzi, con_eventi=False):
    """cot_righe = righe CFTC (archivio completo o ultimi anni); prezzi = {chiave: [(data, prezzo $)]}.
    Restituisce il riepilogo per la pagina (statistiche e ultimi segnali simulati), None senza dati.
    con_eventi=True: aggiunge "_eventi" (tutti gli eventi simulati), usato dalla modalita' demo."""
    sim = simula(cot_righe, prezzi)
    if not sim:
        return None
    misurati, strum, eventi = sim["misurati"], sim["strum"], sim["eventi"]
    ultima, limite_h = sim["ultima"], sim["limite_h"]
    padri = [x for x in misurati if not x[0].get("padre")]
    svil = [x for x in padri if x[0]["generato"][:10] < limite_h]
    hold = [x for x in padri if x[0]["generato"][:10] >= limite_h]

    def gruppi(lista, fn):
        g = {}
        for x in lista:
            g.setdefault(fn(x[0]), []).append(x)
        return {k: motore.riassunto(v) for k, v in sorted(g.items())}

    def periodo(padri_p, tutti_p):
        """Un periodo (tutto / sviluppo / holdout): riassunto generale e tabelle per etichetta, affidabilita',
        strumento. Le fasi STRONG ("figli") contano solo nella tabella per etichetta."""
        per_s = {}
        for x in padri_p:
            per_s.setdefault(x[0]["strumento"], []).append(x)
        return {"dd": {"tutti": motore.drawdown(padri_p),
                       "strumento": {k: motore.drawdown(v, unita[k]) for k, v in sorted(per_s.items())}},
                "riass": motore.riassunto(padri_p, varianti=True),
                "etichetta": gruppi(tutti_p, lambda s: s["etichetta"]),
                "affid": gruppi(padri_p, lambda s: s.get("affid") or "n/d"),
                "strumento": gruppi(padri_p, lambda s: s["strumento"]),
                "vol": gruppi(padri_p, lambda s: (s.get("vol") or {}).get("nome") or "n/d")}

    # unita' dei PUNTI di ogni strumento (pip, punti indice, $): vedi motore.unita
    unita = {k: motore.unita(k, v.get("b"), v.get("q")) for k, v in strum.items()}
    in_hold = lambda x: x[0]["generato"][:10] >= limite_h
    anni = {}
    for x in padri:
        anni.setdefault(x[0]["generato"][:4], []).append(x)
    conclusi = [x for x in padri if x[1]["A"].get("fine") and not x[1]["A"]["fine"].get("provvisorio")]
    ultimi = sorted(conclusi, key=lambda x: x[0]["generato"], reverse=True)[:ULTIMI]
    log.info("backtest: %d segnali simulati (%d nel holdout) dal %s al %s", len(padri), len(hold),
             padri and min(x[0]["generato"][:10] for x in padri), ultima)
    out = {
        "dal": min((x[0]["generato"][:10] for x in padri), default=None), "al": ultima, "holdout_dal": limite_h,
        "n": len(padri), "n_strong": len(misurati) - len(padri), "n_svil": len(svil), "n_hold": len(hold),
        "periodi": {"tutti": periodo(padri, misurati),
                    "sviluppo": periodo(svil, [x for x in misurati if not in_hold(x)]),
                    "holdout": periodo(hold, [x for x in misurati if in_hold(x)])},
        "anni": {a: motore.riassunto(v) for a, v in sorted(anni.items())},
        "ultimi": [{"id": s["id"], "strumento": s["strumento"], "etichetta": s["etichetta"], "affid": s.get("affid"),
                    "generato_it": motore.ora_italia(s["generato"]), "punteggio": s["punteggio"], "vol": s.get("vol"),
                    "chiuso": dict(s["chiuso"], quando_it=motore.ora_italia(s["chiuso"]["quando"])) if s["chiuso"] else None,
                    "m": motore.snello(m)} for s, m, c in ultimi],
        "costi": {k: v for k, v in motore.COSTI.items()},
        "dd_campi": motore.DD_CAMPI, "unita": {k: v[0] for k, v in unita.items()},
        "profilo": {k: motore.profilo(v["pts"]) for k, v in strum.items()},   # volatilita' dell'ultimo anno
    }
    if con_eventi:
        out["_eventi"] = eventi
    return out
