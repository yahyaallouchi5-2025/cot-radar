# -*- coding: utf-8 -*-
"""Test del Pattern Detector (cot_radar/pattern.py). Nessuna rete.
Lancia: python -m unittest tests.test_pattern -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import pattern as P  # noqa: E402


def cand(ts, o, c):
    return (ts, o, max(o, c) + 0.5, min(o, c) - 0.5, c)


class Pattern(unittest.TestCase):
    def test_buy_con_assorbimento(self):
        # candela 1 SELL 110->100, candele 2 e 3 BUY, la 3 chiude a 112 > apertura della 1 (110)
        c = [cand(0, 110, 100), cand(1, 100, 105), cand(2, 105, 112)]
        self.assertEqual(P.trova(c), [(2, "BUY")])
        # se la candela 3 non supera l'apertura della 1: nessun segnale
        c[2] = cand(2, 105, 109)
        self.assertEqual(P.trova(c), [])

    def test_sell_simmetrico(self):
        c = [cand(0, 100, 110), cand(1, 110, 104), cand(2, 104, 97)]
        self.assertEqual(P.trova(c), [(2, "SELL")])
        c[1] = cand(1, 110, 112)                       # candela 2 rialzista: non e' il pattern
        self.assertEqual(P.trova(c), [])

    def test_h4_scarta_la_candela_aperta(self):
        ore = [(h * 3600, 1, 2, 0.5, 1.5) for h in range(10)]   # 10 ore: H4 00-04, 04-08 chiuse, 08-12 aperta
        x = P.h4(ore, adesso=10 * 3600)
        self.assertEqual([g[0] for g in x], [0, 4 * 3600])

    def test_statistica_e_giro(self):
        c = [cand(0, 110, 100), cand(1, 100, 105), cand(2, 105, 112)] + [cand(3 + i, 112 + i, 113 + i) for i in range(6)]
        a = P.analizza(c, 2)
        self.assertEqual(a["stat"]["n"], 1)
        self.assertEqual(a["stat"]["vinti"], 100)
        self.assertEqual(a["ultimo"]["lato"], "BUY")
        self.assertEqual(a["ultimo"]["livello"], 110)
        d = tempfile.mkdtemp()
        try:
            serie = [(i * 3600, 1.0 + i * 0.001, 1.01 + i * 0.001, 0.99 + i * 0.001, 1.0 + i * 0.001) for i in range(800)]
            out = P.esegui(d, scarica=lambda t, i, p: serie if not t.startswith("XAU") else None,
                           adesso=800 * 3600 + 86400, pausa=0)
            self.assertIsNone(out["anomalia"])
            ids = [x["id"] for x in out["strumenti"]]
            self.assertIn("XAUUSD", ids)                                 # spot assente: si usa il future
            self.assertEqual([x for x in out["strumenti"] if x["id"] == "XAUUSD"][0]["fonte"], "GC=F")
            # Yahoo giu': restano le copie del giro prima e scatta l'anomalia
            out2 = P.esegui(d, scarica=lambda *a: None, pausa=0)
            self.assertIsNotNone(out2["anomalia"])
            self.assertEqual(len(out2["strumenti"]), len(out["strumenti"]))
            self.assertTrue(json.load(open(os.path.join(d, "pattern.json")))["anomalia"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
