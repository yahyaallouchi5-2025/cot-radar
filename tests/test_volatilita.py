# -*- coding: utf-8 -*-
"""Test della volatilita' per asset (cot_radar/volatilita.py). Lancia: python -m unittest tests.test_volatilita -v"""
import math
import os
import random
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import volatilita  # noqa: E402


def serie(n, sigma_fn, seme=1):
    """Prezzi feriali con volatilita' giornaliera sigma_fn(i)."""
    random.seed(seme)
    out, d, p = [], date(2000, 1, 3), 100.0
    for i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        p *= math.exp(random.gauss(0, sigma_fn(i)))
        out.append((d.isoformat(), p))
        d += timedelta(days=1)
    return out


class Volatilita(unittest.TestCase):
    def test_volatilita_annua_corretta(self):
        pts = serie(3000, lambda i: 0.01)                       # 1% al giorno = ~15,9% annuo
        pr = volatilita.profilo(pts)
        self.assertAlmostEqual(pr["ann_storia"], 15.9, delta=1.0)
        self.assertEqual(len(pr["giorni"]), 5)
        self.assertEqual(len(pr["mesi"]), 12)
        self.assertAlmostEqual(pr["giorni"][0]["storia"], 0.8, delta=0.1)   # E|x| = sigma*radice(2/pi)

    def test_regime_agitato_e_calmo(self):
        agit = volatilita.profilo(serie(2000, lambda i: 0.03 if i > 1980 else 0.01))
        calma = volatilita.profilo(serie(2000, lambda i: 0.003 if i > 1980 else 0.01))
        self.assertEqual(agit["regime"]["nome"], "agitata")
        self.assertEqual(calma["regime"]["nome"], "calma")

    def test_regime_senza_futuro(self):
        """Il regime a una data non cambia se cambiano i prezzi successivi."""
        a = serie(1500, lambda i: 0.01)
        b = a[:1000] + [(d, p * 3) for d, p in a[1000:]]
        ra, rb = volatilita.Regimi(), volatilita.Regimi()
        g = a[900][0] + "T20:00Z"
        self.assertEqual(ra.al_segnale("X", a, g), rb.al_segnale("X", b, g))

    def test_vol_mobile(self):
        pts = serie(100, lambda i: 0.01)
        v = volatilita.vol_mobile(pts)
        r = [math.log(pts[i][1] / pts[i - 1][1]) for i in range(80, 100)]
        m = sum(r) / 20
        atteso = math.sqrt(sum((x - m) ** 2 for x in r) / 19) * math.sqrt(252) * 100
        self.assertAlmostEqual(v[99], atteso, places=6)


if __name__ == "__main__":
    unittest.main()
