# -*- coding: utf-8 -*-
"""
sconto.py - SMART DISCOUNT (v6.55): quanto e' "scontato" oggi ogni titolo rispetto alla SUA storia, e se in passato
comprare a quel livello di sconto e' andato meglio che comprare a caso. Punteggio 0-100.

Stesso metodo del backtest "scontato o caro" (tools/backtest_sconto.py, risultati su tutta la storia):
  SCONTO   = prezzo di oggi / massimo delle ultime 12 chiusure mensili - 1 (ritracciamento recente).
  EVENTO   = primo mese in cui lo sconto arriva a -10/-20/-30/-40/-50%; si riarma sopra meta' soglia.
  RARITA'  = % dei mesi della storia del titolo con uno sconto MENO profondo di oggi (0-100).
  QUALITA' = % di 12 mesi positivi dopo gli eventi alla soglia di oggi (del titolo, o del settore se ha meno di
             5 eventi) contro la % normale di 12 mesi positivi; frenata verso la normalita' con 10 eventi "medi".
             50 = come comprare a caso; ogni punto % in piu' vale 2 punti.
  PUNTEGGIO= 60% rarita' + 40% qualita'.  >=80 molto scontato, 60-79 scontato, 40-59 neutro, <40 caro.

Note oneste (mostrate anche nel sito): il bias di sopravvivenza (titoli falliti assenti) rende la "qualita'" un po'
ottimista; e' una statistica del passato, non una previsione ne' un consiglio. Solo libreria standard (niente pandas).
"""
SOGLIE = [-10, -20, -30, -40, -50]
FINESTRA = 12            # massimo delle ultime 12 chiusure mensili
MESI_MIN = 60            # almeno 5 anni di storia
EVENTI_MIN = 5
PRIOR = 10


def pulisci(p):
    """Picchi isolati (errori di dato): +50% e ritorno subito (o -33% e ritorno) -> media geometrica dei vicini."""
    v = list(p)
    for i in range(1, len(v) - 1):
        a, b, c = v[i - 1], v[i], v[i + 1]
        if (b / a > 1.5 and c / b < 1 / 1.5) or (b / a < 1 / 1.5 and c / b > 1.5):
            v[i] = (a * c) ** 0.5
    return v


def sconti(p):
    """Sconto % di ogni mese dal massimo delle ultime FINESTRA chiusure."""
    return [(x / max(p[max(0, i - FINESTRA + 1):i + 1]) - 1) * 100 for i, x in enumerate(p)]


def eventi(p, sc):
    """[(soglia, rendimento a 12 mesi o None)] con la regola di riarmo a meta' soglia."""
    out = []
    for k in SOGLIE:
        armato = True
        for i, x in enumerate(sc):
            if armato and x <= k:
                out.append((k, (p[i + 12] / p[i] - 1) * 100 if i + 12 < len(p) else None))
                armato = False
            elif not armato and x > k / 2:
                armato = True
    return out


def calcola(serie, righe):
    """serie = {ticker: [chiusure mensili COMPLETE, dalla piu' vecchia]}; righe = elenco dell'indice (dict con t, s, p).
    Aggiunge a ogni riga con abbastanza storia: sd (punteggio), sdo (sconto di oggi), sdr (rarita'), sdq (qualita'),
    sdn (eventi usati), sdv (% positivi dopo eventi), sdb (% positivi normale), sdx=1 se gli eventi sono del settore. Restituisce quante righe ha valutato."""
    dati, per_sett, base_sett = {}, {}, {}
    for r in righe:
        p = [x for x in (serie.get(r["t"]) or []) if x and x > 0]
        if len(p) < MESI_MIN or not r.get("p"):
            continue
        p = pulisci(p)
        sc = sconti(p)
        ev = eventi(p, sc)
        b12 = [(p[i + 12] / p[i] - 1) * 100 for i in range(len(p) - 12)]
        dati[r["t"]] = (p, sc, ev, b12)
        for k, x in ev:
            if x is not None:
                per_sett.setdefault((r["s"], k), []).append(x)
        base_sett.setdefault(r["s"], []).extend(b12)
    n = 0
    for r in righe:
        if r["t"] not in dati:
            continue
        p, sc, ev, b12 = dati[r["t"]]
        oggi = (r["p"] / max(max(p[-(FINESTRA - 1):]), r["p"]) - 1) * 100
        rarita = sum(1 for x in sc if x > oggi) / len(sc) * 100
        base = sum(1 for x in b12 if x > 0) / len(b12) * 100 if b12 else 60.0
        k = max([s for s in SOGLIE if oggi <= s], default=None)
        settore = False
        if k is None:                                    # sconto sotto -10%: nessun vantaggio ne' svantaggio
            w, usati = base, 0
        else:
            mie = [x for s, x in ev if s == k and x is not None]
            settore = len(mie) < EVENTI_MIN
            if settore:                    # pochi eventi propri: si usa il settore (confronto alla pari)
                mie = per_sett.get((r["s"], k), [])
                bs = base_sett.get(r["s"]) or []
                base = sum(1 for x in bs if x > 0) / len(bs) * 100 if bs else base
            usati = len(mie)
            w = (sum(1 for x in mie if x > 0) + PRIOR * base / 100) / (usati + PRIOR) * 100
        q = max(0.0, min(100.0, 50 + (w - base) * 2))
        r.update({"sd": int(round(0.6 * rarita + 0.4 * q)), "sdo": round(oggi, 1), "sdr": int(round(rarita)),
                  "sdq": int(round(q)), "sdn": usati, "sdv": int(round(w)), "sdb": int(round(base)),
                  **({"sdx": 1} if settore else {})})
        n += 1
    return n

