# -*- coding: utf-8 -*-
"""
backtest_sconto.py - BACKTEST "SCONTATO O CARO": comprare dopo un drawdown conviene davvero?

DOMANDA: quando un mercato (azione, indice, materia prima, cripto) scende del 10/20/30/40/50% dal suo
massimo, cosa e' successo NEI MESI DOPO? E oggi, ogni mercato quanto e' "scontato" rispetto alla SUA storia?

DATI (tutti gratuiti, gli stessi del sito BoardEdge):
  - azioni: chiusure di FINE MESE (Yahoo, rettificate per frazionamenti) di ~1.000 titoli
    (S&P 500, Nasdaq-100, FTSE MIB, DAX, Euro Stoxx 50, Nikkei, Hang Seng, Cina, India), dal 1962 dove c'e';
  - indice Nasdaq Composite dal 1971, petrolio WTI dal 1986, Brent dal 1987, gas naturale dal 1997,
    Bitcoin dal 2014, Ethereum dal 2016 (FRED; giornalieri ridotti a fine mese).

METODO (scelte dichiarate, per non ingannarsi):
  1. SCONTO = prezzo di fine mese / massimo delle ultime 12 chiusure mensili - 1   (ritracciamento recente,
     il caso "Amazon -20%"). Come contesto si calcola anche lo sconto dal MASSIMO STORICO.
  2. EVENTO = il primo mese in cui lo sconto arriva alla soglia (-10, -20, -30, -40, -50%). La soglia si
     "riarma" solo quando lo sconto torna sopra META' soglia (es. sopra -10% per la soglia -20%):
     cosi' uno stesso drawdown non viene contato 10 volte.
  3b. FILTRO TREND: ogni evento e' diviso in "sopra" (prezzo ancora sopra la media delle ultime 24 chiusure
      mensili: ritracciamento dentro un rialzo) e "sotto" (mercato gia' sotto la media: discesa lunga).
  3. Per ogni evento: rendimento a 3, 6, 12, 24 mesi e DRAWDOWN SUCCESSIVO (quanto e' sceso ancora nei
     12 mesi dopo l'acquisto, sulle chiusure mensili: quello vero intramese e' un po' piu' profondo).
  4. CONFRONTO ONESTO: lo stesso rendimento a 12 mesi calcolato da TUTTI i mesi dello stesso mercato
     ("comprare a caso"). Il vantaggio dello sconto = mediana eventi - mediana di tutti i mesi.
  5. PUNTEGGIO SCONTO di oggi (0-100) per ogni mercato:
       rarita'  = quanti mesi della sua storia hanno avuto uno sconto MENO profondo di oggi (percentile);
       qualita' = quanto comprare a questo livello di sconto e' andato MEGLIO di "comprare a caso" nello stesso
                  mercato (% di 12 mesi positivi dopo gli eventi contro % di tutti i mesi), 50 = uguale.
                  Con pochi eventi la % viene avvicinata a quella normale (PRIOR = 10 eventi "medi"),
                  cosi' 8 eventi su 8 positivi non diventano un 100% di fiducia;
       punteggio = 60% rarita' + 40% qualita'.  Lettura: >=80 molto scontato, 60-79 scontato,
       40-59 neutro, <40 caro (vicino ai massimi).

LIMITI DA NON DIMENTICARE:
  - BIAS DI SOPRAVVIVENZA: i titoli sono quelli quotati OGGI negli indici. Le aziende fallite dopo un -50%
    (Lehman, Enron...) non ci sono: per le SINGOLE AZIONI i risultati sono piu' belli del vero.
    Indici, materie prime e cripto non hanno questo problema (ma le cripto hanno poca storia).
  - Eventi delle azioni concentrati nelle stesse crisi (2000-02, 2008-09, 2020, 2022): non sono indipendenti.
  - Niente dividendi, costi e tasse; chiusure mensili (niente intramese).
  - E' una statistica del passato, non una previsione ne' un consiglio di investimento.

USO:  python backtest_sconto.py dati/   -> scrive risultati.json e stampa il riepilogo.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

SOGLIE = [-10, -20, -30, -40, -50]          # livelli di sconto studiati (%)
ORIZZONTI = [3, 6, 12, 24]                  # mesi dopo l'acquisto
FINESTRA_MAX = 12                           # massimo delle ultime 12 chiusure mensili = "ritracciamento recente"
MESI_MIN = 60                               # almeno 5 anni di storia per entrare nello studio
EVENTI_MIN = 5                              # sotto questa soglia la "qualita'" usa il gruppo (settore)

SETTORI = {"tech": "Tecnologia", "tlc": "Comunicazione", "cdis": "Beni voluttuari", "cstap": "Beni di prima necessita'",
           "fin": "Finanza", "salute": "Salute", "ind": "Industria", "mat": "Materiali", "ener": "Energia",
           "util": "Servizi pubblici", "imm": "Immobiliare"}            # stessi codici di indice.json
PRIOR = 10                                  # "eventi immaginari" alla media del mercato: frena i 100% su 5-8 eventi
ALTRI = {  # serie FRED: nome, gruppo
    "NASDAQCOM": ("Nasdaq Composite (indice)", "Indici"), "DCOILWTICO": ("Petrolio WTI", "Materie prime"),
    "DCOILBRENTEU": ("Petrolio Brent", "Materie prime"), "DHHNGSP": ("Gas naturale Henry Hub", "Materie prime"),
    "CBBTCUSD": ("Bitcoin", "Cripto"), "CBETHUSD": ("Ethereum", "Cripto")}


# --------------------------------------------------------------------------- caricamento dati
def serie_mensili(cartella):
    """{codice: (nome, gruppo, pd.Series di chiusure di fine mese con indice mensile)}"""
    out = {}
    idx = json.load(open(os.path.join(cartella, "indice.json")))
    info = {x["t"]: x for x in idx["titoli"]}
    for f in glob.glob(os.path.join(cartella, "titoli", "*.json")):
        d = json.load(open(f))
        if d.get("t") not in info or not d.get("m"):
            continue
        s = pd.Series([p for _, p in d["m"]], index=pd.PeriodIndex([m for m, _ in d["m"]], freq="M"), dtype=float)
        s = s[s > 0].iloc[:-1]                      # l'ultimo mese e' ancora in corso: fuori dal backtest storico
        x = info[d["t"]]
        out[d["t"]] = (x["n"], SETTORI.get(x.get("s"), "Altro"), s, x)
    for cod, (nome, gruppo) in ALTRI.items():
        f = os.path.join(cartella, cod + ".csv")
        if not os.path.exists(f):
            continue
        g = pd.read_csv(f, parse_dates=["data"]).dropna()
        g = g[g["valore"] > 0].set_index("data")["valore"]
        m = g.resample("ME").last().dropna()
        m.index = m.index.to_period("M")
        out[cod] = (nome, gruppo, m.iloc[:-1], {"t": cod, "n": nome, "p": float(g.iloc[-1])})
    return out


def pulisci(s):
    """Toglie i PICCHI ISOLATI (errori di dato): un mese +50% sui vicini che torna giu' subito (o -33% e torna su).
    Il valore sbagliato viene sostituito dalla media geometrica dei due mesi vicini. Restituisce (serie, n corretti)."""
    v = s.values.copy()
    n = 0
    for i in range(1, len(v) - 1):
        a, b, c = v[i - 1], v[i], v[i + 1]
        if (b / a > 1.5 and c / b < 1 / 1.5) or (b / a < 1 / 1.5 and c / b > 1.5):
            v[i] = (a * c) ** 0.5
            n += 1
    return pd.Series(v, index=s.index), n


# --------------------------------------------------------------------------- calcoli per una serie
def sconto(s, finestra=FINESTRA_MAX):
    """Sconto (%) dal massimo delle ultime `finestra` chiusure (finestra=None: dal massimo storico)."""
    mx = s.cummax() if finestra is None else s.rolling(finestra, min_periods=1).max()
    return (s / mx - 1) * 100


def eventi(s, sc):
    """Lista di eventi: (soglia, posizione del mese) con la regola di riarmo a meta' soglia."""
    ev = []
    v = sc.values
    for k in SOGLIE:
        armato = True
        for i, x in enumerate(v):
            if armato and x <= k:
                ev.append((k, i))
                armato = False
            elif not armato and x > k / 2:
                armato = True
    return ev


def futuri(s, i):
    """Rendimenti a 3/6/12/24 mesi e drawdown successivo (12 mesi) dal mese i. None se il futuro non c'e' ancora."""
    p = s.values
    r = {h: (p[i + h] / p[i] - 1) * 100 if i + h < len(p) else None for h in ORIZZONTI}
    fin = p[i + 1:i + 13]
    dd = (fin.min() / p[i] - 1) * 100 if len(fin) else None
    return r, (min(dd, 0.0) if dd is not None else None)


def base12(s):
    """Rendimenti a 12 mesi da TUTTI i mesi (il riferimento 'comprare a caso')."""
    p = s.values
    return (p[12:] / p[:-12] - 1) * 100 if len(p) > 12 else np.array([])


# --------------------------------------------------------------------------- statistiche
def riassumi(lista, chiave):
    v = np.array([x[chiave] for x in lista if x[chiave] is not None], dtype=float)
    if not len(v):
        return None
    return {"n": int(len(v)), "media": round(float(v.mean()), 1), "mediana": round(float(np.median(v)), 1),
            "pos": round(float((v > 0).mean() * 100), 0), "p10": round(float(np.percentile(v, 10)), 1)}


def tabella(evs):
    """Per ogni soglia: n eventi, rendimenti 3/6/12/24 mesi, drawdown successivo."""
    out = {}
    for k in SOGLIE:
        e = [x for x in evs if x["k"] == k]
        if not e:
            continue
        out[k] = {"eventi": len(e), **{f"r{h}": riassumi(e, f"r{h}") for h in ORIZZONTI}, "dd": riassumi(e, "dd")}
    return out


def main(cartella):
    dati = serie_mensili(cartella)
    tutti_ev, base_per_gruppo, righe, corretti = [], {}, [], 0
    for cod, (nome, gruppo, s, info) in dati.items():
        if len(s) < MESI_MIN:
            continue
        s, nc = pulisci(s)
        corretti += nc
        sc, sc_ath = sconto(s), sconto(s, None)
        b = base12(s)
        base_per_gruppo.setdefault(gruppo, []).extend(b.tolist())
        evs = []
        media24 = s.rolling(24, min_periods=24).mean()                # trend lungo: media delle ultime 24 chiusure
        for k, i in eventi(s, sc):
            r, dd = futuri(s, i)
            trend = None if pd.isna(media24.iloc[i]) else bool(s.iloc[i] > media24.iloc[i])
            evs.append({"cod": cod, "gruppo": gruppo, "k": k, "mese": str(s.index[i]), "sconto": round(sc.iloc[i], 1),
                        **{f"r{h}": r[h] for h in ORIZZONTI}, "dd": dd, "trend": trend})
        tutti_ev.extend(evs)
        # ---- situazione di OGGI: ultimo prezzo disponibile contro il massimo delle ultime 12 chiusure
        ultimo = float(info.get("p") or s.iloc[-1])
        oggi = (ultimo / max(s.iloc[-11:].max(), ultimo) - 1) * 100   # stessa definizione del backtest (fine mese)
        oggi_ath = (ultimo / max(s.max(), ultimo) - 1) * 100
        rarita = float((sc.values > oggi).mean() * 100)   # % di mesi con sconto MENO profondo di oggi
        livello = max([k for k in SOGLIE if oggi <= k], default=None)  # soglia raggiunta oggi (es. -20)
        righe.append({"cod": cod, "nome": nome, "gruppo": gruppo, "mesi": len(s), "dal": str(s.index[0]),
                      "oggi": round(oggi, 1), "oggi_ath": round(oggi_ath, 1), "rarita": round(rarita, 0),
                      "tipico": round(float(np.median(sc.values)), 1), "p10": round(float(np.percentile(sc.values, 10)), 1),
                      "livello": livello, "evs": evs,
                      "base12": round(float(np.median(b)), 1) if len(b) else None,
                      "base_pos": round(float((b > 0).mean() * 100), 0) if len(b) else None})

    # ---- qualita': % positivi a 12 mesi dopo eventi alla soglia di oggi (proprio storico o del gruppo)
    per_gruppo = {}
    for e in tutti_ev:
        if e["r12"] is not None:
            per_gruppo.setdefault((e["gruppo"], e["k"]), []).append(e["r12"])
    for r in righe:
        k, base = r["livello"], (r["base_pos"] or 60)
        if k is None:                                   # sconto sotto -10%: nessun vantaggio ne' svantaggio
            w, fonte = base, "nessuno sconto rilevante"
        else:
            mie = [e["r12"] for e in r["evs"] if e["k"] == k and e["r12"] is not None]
            if len(mie) >= EVENTI_MIN:
                pos, n, fonte = float((np.array(mie) > 0).sum()), len(mie), f"{len(mie)} eventi propri"
            else:
                g = per_gruppo.get((r["gruppo"], k), [])
                pos, n, fonte = float((np.array(g) > 0).sum()), len(g), f"settore ({len(g)} eventi)"
                bg = np.array(base_per_gruppo.get(r["gruppo"], []))      # confronto alla pari: settore con settore
                base = float((bg > 0).mean() * 100) if len(bg) else base
            w = (pos + PRIOR * base / 100) / (n + PRIOR) * 100   # % positivi "frenata" verso quella normale
        q = max(0.0, min(100.0, 50 + (w - base) * 2))           # +25 punti % sopra il normale = 100
        r["qualita"], r["vinte"], r["fonte_q"] = round(q, 0), round(w, 0), fonte
        r["punteggio"] = int(round(0.6 * r["rarita"] + 0.4 * q))
        r["giudizio"] = ("Molto scontato" if r["punteggio"] >= 80 else "Scontato" if r["punteggio"] >= 60
                         else "Neutro" if r["punteggio"] >= 40 else "Caro")
        r["n_ev"] = len(r.pop("evs"))

    # ---- tabelle riassuntive per gruppo + confronto con "comprare a caso"
    gruppi = sorted({e["gruppo"] for e in tutti_ev} | {"Azioni (tutte)"})
    risultati = {}
    for g in gruppi:
        evs = tutti_ev if g == "Azioni (tutte)" else [e for e in tutti_ev if e["gruppo"] == g]
        if g == "Azioni (tutte)":
            evs = [e for e in evs if e["gruppo"] in SETTORI.values()]
            base = [x for k, v in base_per_gruppo.items() if k in SETTORI.values() for x in v]
        else:
            base = base_per_gruppo.get(g, [])
        bb = np.array(base)
        # FILTRO TREND: lo stesso sconto, ma con il prezzo ancora SOPRA (ritracciamento in un rialzo) o SOTTO
        # (mercato gia' in discesa da tempo) la media delle ultime 24 chiusure mensili
        filtro = {lab: {k: riassumi([e for e in evs if e["k"] == k and e["trend"] is v], "r12") for k in SOGLIE}
                  for lab, v in (("sopra", True), ("sotto", False))}
        risultati[g] = {"tabella": tabella(evs), "trend": filtro, "base12": {"mediana": round(float(np.median(bb)), 1),
                        "pos": round(float((bb > 0).mean() * 100), 0), "n": int(len(bb))} if len(bb) else None}
    # ---- crisi: quanti eventi per anno (per vedere la concentrazione)
    anni = pd.Series([e["mese"][:4] for e in tutti_ev if e["k"] == -20]).value_counts().sort_index()
    out = {"generato": pd.Timestamp.now().strftime("%Y-%m-%d"), "mercati": len(righe), "eventi": len(tutti_ev),
           "picchi_corretti": corretti,
           "gruppi": risultati, "oggi": sorted(righe, key=lambda r: -r["punteggio"]),
           "anni_eventi20": {k: int(v) for k, v in anni.items()},
           "esempi": {c: [e for e in tutti_ev if e["cod"] == c and e["k"] == -20] for c in ("AMZN", "NASDAQCOM", "DCOILWTICO")}}
    json.dump(out, open("risultati.json", "w"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    r = main(sys.argv[1] if len(sys.argv) > 1 else "dati")
    print("mercati:", r["mercati"], "eventi:", r["eventi"])
    for g, v in r["gruppi"].items():
        print("\n==", g, "| comprare a caso 12m: mediana", v["base12"] and v["base12"]["mediana"], "% positivi", v["base12"] and v["base12"]["pos"])
        for k, t in v["tabella"].items():
            r12 = t["r12"] or {}
            print(f"  soglia {k:>4}%: {t['eventi']:>5} eventi | 12m mediana {r12.get('mediana')}% pos {r12.get('pos')}% "
                  f"p10 {r12.get('p10')} | 24m med {(t['r24'] or {}).get('mediana')} | dd successivo med {(t['dd'] or {}).get('mediana')}")
