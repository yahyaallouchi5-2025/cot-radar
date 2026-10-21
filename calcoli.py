# -*- coding: utf-8 -*-
"""
calcoli.py - strumenti matematici di base, senza librerie esterne (niente numpy/pandas).

Sono funzioni "pure": stesso input -> stesso output, nessun accesso a internet o file.
Per questo sono le piu' facili da testare: vedi tests/test_calcoli.py.
"""
import math
from bisect import bisect_right


def clip(x, a=-1.0, b=1.0):
    """Limita x all'intervallo [a, b]. Esempio: clip(1.7) -> 1.0, clip(-3, -2, 2) -> -2."""
    return max(a, min(b, x))


def zlast(values, window=52):
    """Z-score dell'ULTIMO valore rispetto agli ultimi `window` valori.
    Dice "quanto e' insolito" il dato di oggi: 0 = nella media, +2 = molto sopra il solito, -2 = molto sotto.
    Con meno di 12 valori restituisce 0 (troppo pochi per una statistica affidabile)."""
    w = values[-window:]
    if len(w) < 12:
        return 0.0
    m = sum(w) / len(w)                                               # media
    sd = math.sqrt(sum((x - m) ** 2 for x in w) / (len(w) - 1))       # deviazione standard campionaria
    return 0.0 if sd == 0 else (w[-1] - m) / sd


def cot_index(values, window=156):
    """COT Index di Larry Williams: dove si trova l'ultimo valore tra il minimo (0) e il massimo (100)
    degli ultimi `window` valori (156 settimane = 3 anni)."""
    w = values[-window:]
    lo, hi = min(w), max(w)
    return 50.0 if hi == lo else 100 * (w[-1] - lo) / (hi - lo)


def pearson(a, b):
    """Correlazione di Pearson tra due liste della stessa lunghezza (-1..+1). None se non calcolabile."""
    n = len(a)
    if n < 10:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:          # una delle due serie e' costante: correlazione indefinita
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def solve(A, b):
    """Risolve il sistema lineare A*x = b con l'eliminazione di Gauss (pivot parziale).
    Va bene per sistemi piccoli (qui al massimo 6x6). Restituisce None se il sistema e' singolare."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]        # matrice "aumentata" [A | b]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))     # riga con il valore piu' grande: piu' stabile
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] for i in range(n)]


def ols(X, y, ridge=0.0):
    """Regressione lineare y = a + b1*x1 + b2*x2 + ...

    X: lista di righe, ogni riga una lista di variabili; y: lista dei valori da spiegare.
    Le variabili vengono standardizzate (media 0, deviazione 1) cosi' i coefficienti sono confrontabili.
    ridge > 0 aggiunge una piccola penalita' (regressione "ridge") che evita coefficienti esagerati
    quando le variabili si somigliano tra loro (es. VIX e spread high yield).

    Restituisce un dizionario con:
      beta  = coefficienti (sulle variabili standardizzate)
      mu/sd = media e deviazione di ogni variabile (servono per standardizzare dati nuovi)
      my    = media di y (l'intercetta)
      r2    = quota della variabilita' di y spiegata dal modello (0..1)
      sigma = errore tipico del modello (stesse unita' di y)
    """
    n, k = len(X), len(X[0])
    mu = [sum(r[j] for r in X) / n for j in range(k)]
    sd = [math.sqrt(sum((r[j] - mu[j]) ** 2 for r in X) / max(1, n - 1)) or 1.0 for j in range(k)]
    Z = [[(r[j] - mu[j]) / sd[j] for j in range(k)] for r in X]
    my = sum(y) / n
    # equazioni normali: (Z'Z + ridge*I) beta = Z'(y - media)
    A = [[sum(Z[i][a] * Z[i][b] for i in range(n)) + (ridge if a == b else 0) for b in range(k)] for a in range(k)]
    bb = [sum(Z[i][a] * (y[i] - my) for i in range(n)) for a in range(k)]
    beta = solve(A, bb)
    if beta is None:
        return None
    fit = [my + sum(Z[i][j] * beta[j] for j in range(k)) for i in range(n)]
    ssr = sum((y[i] - fit[i]) ** 2 for i in range(n))      # errore residuo
    sst = sum((v - my) ** 2 for v in y) or 1e-9             # variabilita' totale
    return {"beta": beta, "mu": mu, "sd": sd, "my": my, "r2": max(0.0, 1 - ssr / sst),
            "sigma": math.sqrt(ssr / max(1, n - k - 1))}


class Series:
    """Serie temporale [[data, valore], ...] con una funzione comoda:
    .at(data) = ultimo valore disponibile a quella data (se quel giorno era festivo prende il precedente)."""

    def __init__(self, pts):
        pts = sorted(pts)
        self.d = [p[0] for p in pts]      # date come stringhe "AAAA-MM-GG": l'ordine alfabetico e' anche cronologico
        self.v = [p[1] for p in pts]

    def at(self, d):
        i = bisect_right(self.d, d) - 1   # ricerca binaria: veloce anche su migliaia di valori
        return self.v[i] if i >= 0 else None

    @property
    def last(self):
        return (self.d[-1], self.v[-1]) if self.d else (None, None)


def month_avg(pts):
    """Da serie giornaliera a media mensile: {"2026-08": 3.12, ...}"""
    acc = {}
    for d, v in pts:
        acc.setdefault(d[:7], []).append(v)
    return {m: sum(v) / len(v) for m, v in acc.items()}


def add_month(m, k):
    """Somma k mesi a "AAAA-MM". add_month("2026-11", 3) -> "2027-02"."""
    y, mo = int(m[:4]), int(m[5:7]) + k
    while mo > 12:
        y, mo = y + 1, mo - 12
    while mo < 1:
        y, mo = y - 1, mo + 12
    return f"{y:04d}-{mo:02d}"
