# -*- coding: utf-8 -*-
"""Test SMART DISCOUNT (cot_radar/sconto.py). Nessuna rete: serie mensili finte.
Lancia: python -m unittest tests.test_sconto -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cot_radar import sconto as S  # noqa: E402


class SmartDiscount(unittest.TestCase):
    def test_picco_isolato_corretto(self):
        self.assertAlmostEqual(S.pulisci([100, 100, 300, 100, 100])[2], 100)

    def test_eventi_con_riarmo(self):
        p = [100] * 3 + [85, 84, 83, 100, 100, 85] + [100] * 20       # due cali a -15% separati da un recupero
        ev = [k for k, _ in S.eventi(p, S.sconti(p))]
        self.assertEqual(ev.count(-10), 2)                           # contati 2 volte, non 5 (un evento per calo)

    def test_punteggio_ai_massimi_e_scontato(self):
        su = [100 * 1.01 ** i for i in range(120)]                   # sempre in rialzo
        giu = su[:-12] + [su[-13] * (1 - 0.04 * i) for i in range(1, 13)]   # ultimo anno -40%
        righe = [{"t": "A", "s": "tech", "p": su[-1]}, {"t": "B", "s": "tech", "p": giu[-1]},
                 {"t": "C", "s": "tech", "p": 1}]                     # C: storia troppo corta
        self.assertEqual(S.calcola({"A": su, "B": giu, "C": [1] * 10}, righe), 2)
        a, b, c = righe
        self.assertLess(a["sd"], 40)                                 # ai massimi = caro
        self.assertGreater(b["sd"], a["sd"])
        self.assertLessEqual(b["sdo"], -30)
        self.assertNotIn("sd", c)


if __name__ == "__main__":
    unittest.main()
