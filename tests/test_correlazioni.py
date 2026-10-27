# -*- coding: utf-8 -*-
"""Test delle correlazioni dei prezzi (cot_radar/correlazioni.py). Prezzi finti costruiti apposta.
Lancia: python -m unittest tests.test_correlazioni -v"""
import math
import os
import random
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import correlazioni as C  # noqa: E402


def prezzi():
    """SPY casuale; QQQ = SPY + poco rumore (insieme); USO = -SPY (al contrario); GLD indipendente;
    BTC legato allo SPY solo negli ultimi 63 giorni (legame che CAMBIA)."""
    rnd = random.Random(3)
    giorni, d = [], date(2024, 1, 1)
    while len(giorni) < 400:
        if d.weekday() < 5:
            giorni.append(d.isoformat())
        d += timedelta(days=1)
    out = {k: [] for k in ("SPY", "QQQ", "USO", "GLD", "BTC-USD")}
    v = {k: 100.0 for k in out}
    for i, g in enumerate(giorni):
        r = rnd.gauss(0, 0.01)
        mosse = {"SPY": r, "QQQ": r + rnd.gauss(0, 0.002), "USO": -r + rnd.gauss(0, 0.002), "GLD": rnd.gauss(0, 0.01),
                 "BTC-USD": (r if i >= len(giorni) - 63 else -r) + rnd.gauss(0, 0.004)}
        for k in out:
            v[k] *= 1 + mosse[k]
            out[k].append((g, round(v[k], 4)))
    return out


class Correlazioni(unittest.TestCase):
    def test_segni_e_liste(self):
        d = C.calcola(prezzi())
        ks = [a["k"] for a in d["asset"]]
        m = d["m63"]
        self.assertGreater(m[ks.index("SPY")][ks.index("QQQ")], 0.9)
        self.assertLess(m[ks.index("SPY")][ks.index("USO")], -0.9)
        self.assertLess(abs(m[ks.index("SPY")][ks.index("GLD")]), 0.3)
        # SPY-QQQ sono dello stesso "mondo" (azioni): non compaiono nelle liste
        self.assertFalse(any({x["a"], x["b"]} == {"SPY", "QQQ"} for x in d["insieme"]))
        self.assertEqual({d["opposti"][0]["a"], d["opposti"][0]["b"]}, {"SPY", "USO"})
        # il Bitcoin ha cambiato verso con lo SPY: e' in cima a "stanno cambiando"
        self.assertIn("BTC-USD", (d["cambiati"][0]["a"], d["cambiati"][0]["b"]))

    def test_senza_spy(self):
        self.assertIsNone(C.calcola({}))
        self.assertIsNone(C.calcola({"QQQ": [("2024-01-01", 1)]}))

    def test_serie_mobile(self):
        d = C.calcola(prezzi())
        btc = next(x for x in d["spx"] if x["k"] == "BTC-USD")
        self.assertGreater(btc["serie"][-1], 0.5)            # oggi insieme...
        self.assertLess(btc["serie"][0], -0.5)               # ...prima al contrario


if __name__ == "__main__":
    unittest.main()
