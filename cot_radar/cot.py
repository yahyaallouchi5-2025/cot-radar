# -*- coding: utf-8 -*-
"""
cot.py - dal report CFTC al punteggio COT di ogni strumento (da -100 a +100).

Glossario:
  Non-Commercial = grandi speculatori (fondi, CTA, banche d'affari)
  netto          = contratti long - contratti short
  open interest  = contratti aperti in totale; dividendo il netto per l'OI i mercati diventano confrontabili
"""
from .calcoli import clip, cot_index, zlast
from .config import CROWD_DAMPING, CROWD_HI, CROWD_LO, DIVERGENCE_MIN, NORMAL, STRONG, WEIGHTS


def cot_series(rows):
    """Righe grezze CFTC -> {codice_mercato: [settimana1, settimana2, ...]} in ordine di data.
    Ogni settimana e' un dizionario {date, oi, long, short, net}."""
    by = {}
    for r in rows:
        try:
            code = r["cftc_contract_market_code"].strip()
            d = r["report_date_as_yyyy_mm_dd"][:10]
            oi = float(r["open_interest_all"])
            nl, ns = float(r["noncomm_positions_long_all"]), float(r["noncomm_positions_short_all"])
        except (KeyError, ValueError, TypeError, AttributeError):
            continue                      # riga incompleta: la saltiamo invece di bloccare tutto
        try:                              # Commercials (hedger: produttori, banche, utilizzatori): facoltativi
            cn = float(r["comm_positions_long_all"]) - float(r["comm_positions_short_all"])
        except (KeyError, ValueError, TypeError):
            cn = None
        if oi > 0:
            # se la stessa data arriva due volte vince l'ultima (dizionario per data)
            by.setdefault(code, {})[d] = {"date": d, "oi": oi, "long": nl, "short": ns, "net": nl - ns, "comm": cn}
    return {c: [v[d] for d in sorted(v)] for c, v in by.items()}


def cot_strength(ser, t):
    """Punteggio COT usando SOLO i dati fino alla settimana t (inclusa).
    Usare t = ultima settimana da' il valore attuale, t = penultima quello della settimana scorsa
    (cosi' la dashboard puo' dire "Nuovo segnale")."""
    s = ser[: t + 1]
    if len(s) < 30:
        return None                                       # storico troppo corto
    n = [x["net"] / x["oi"] * 100 for x in s]             # netto in % dell'open interest
    d1 = [n[i] - n[i - 1] for i in range(1, len(n))]      # variazioni settimanali
    d4 = [n[i] - n[i - 4] for i in range(4, len(n))]      # variazioni a 4 settimane
    idx = cot_index(n)                                     # 0..100 sugli ultimi 3 anni
    p = (idx - 50) / 50                                    # posizione riportata a -1..+1
    f1 = clip(zlast(d1) / 2.5)                             # z-score diviso 2.5: uno z di 2.5 vale gia' il massimo
    f4 = clip(zlast(d4) / 2.5)
    score = 100 * (WEIGHTS["posizione"] * p + WEIGHTS["flusso_1w"] * f1 + WEIGHTS["flusso_4w"] * f4)
    # Se sono gia' tutti dalla stessa parte (affollato) e il punteggio spinge ancora in quella direzione,
    # lo riduciamo: chi doveva comprare ha gia' comprato, cresce il rischio di inversione.
    crowded = (idx >= CROWD_HI and score > 0) or (idx <= CROWD_LO and score < 0)
    if crowded:
        score *= CROWD_DAMPING
    return {
        "cot": round(clip(score, -100, 100), 1), "idx": round(idx), "crowded": crowded,
        "net": int(s[-1]["net"]), "d_net": int(s[-1]["net"] - s[-2]["net"]),
        "d_net4": int(s[-1]["net"] - s[max(0, len(s) - 5)]["net"]),
        "d_long": int(s[-1]["long"] - s[-2]["long"]), "d_short": int(s[-1]["short"] - s[-2]["short"]),
        "pct_oi": round(n[-1], 1), "date": s[-1]["date"],
    }


def label(score, divergence=True, single=False):
    """Punteggio -> etichetta. Per le coppie, STRONG richiede la divergenza;
    per gli strumenti singoli (single=True) basta la soglia."""
    a = abs(score)
    if a >= STRONG and (divergence or single):
        return "STRONG BUY" if score > 0 else "STRONG SELL"
    if a >= NORMAL:
        return "BUY" if score > 0 else "SELL"
    return "NEUTRO"


def is_divergence(sb, sq):
    """True se su una valuta comprano (>= +20) e sull'altra vendono (<= -20)."""
    return (sb >= DIVERGENCE_MIN and sq <= -DIVERGENCE_MIN) or (sb <= -DIVERGENCE_MIN and sq >= DIVERGENCE_MIN)
