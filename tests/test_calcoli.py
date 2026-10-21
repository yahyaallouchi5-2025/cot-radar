# -*- coding: utf-8 -*-
"""
Test automatici. Si lanciano con:

    python -m unittest discover -s tests -v

Ogni test controlla un pezzo piccolo e indipendente. Se dopo una modifica un test diventa rosso (FAIL/ERROR),
sai esattamente QUALE funzione si e' rotta, senza dover cercare nella dashboard.
Su GitHub girano da soli a ogni modifica (workflow .github/workflows/test.yml).
"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar.calcoli import add_month, clip, cot_index, ols, pearson, zlast   # noqa: E402
from cot_radar.calendario import et_to_utc, fd, utc_to_it                        # noqa: E402
from cot_radar.cot import is_divergence, label                                   # noqa: E402
from cot_radar.fonti import valid_date                                           # noqa: E402


class TestCalcoli(unittest.TestCase):
    def test_clip(self):
        self.assertEqual(clip(1.7), 1.0)
        self.assertEqual(clip(-3, -2, 2), -2)
        self.assertEqual(clip(0.3), 0.3)

    def test_zlast(self):
        self.assertEqual(zlast([1, 2, 3]), 0.0)                    # troppo pochi valori
        vals = [0.0] * 20 + [1.0] * 20 + [10.0]                    # ultimo valore molto sopra la media
        self.assertGreater(zlast(vals), 2)

    def test_cot_index(self):
        self.assertEqual(cot_index([0, 5, 10]), 100)               # ultimo = massimo
        self.assertEqual(cot_index([10, 5, 0]), 0)                 # ultimo = minimo
        self.assertEqual(cot_index([3, 3, 3]), 50)                 # serie piatta

    def test_pearson(self):
        a = list(range(20))
        self.assertAlmostEqual(pearson(a, [2 * x for x in a]), 1.0)
        self.assertAlmostEqual(pearson(a, [-x for x in a]), -1.0)
        self.assertIsNone(pearson(a, [1] * 20))                    # serie costante

    def test_ols_ritrova_i_coefficienti(self):
        # y = 2 + 3*x1 - 1*x2 senza rumore: il modello deve spiegare tutto (R2 = 1)
        X = [[i % 7, (i * 3) % 5] for i in range(40)]
        y = [2 + 3 * a - b for a, b in X]
        m = ols(X, y)
        self.assertAlmostEqual(m["r2"], 1.0, places=6)
        self.assertAlmostEqual(m["beta"][0] / m["sd"][0], 3, places=6)    # coefficiente "vero" di x1
        self.assertAlmostEqual(m["beta"][1] / m["sd"][1], -1, places=6)

    def test_add_month(self):
        self.assertEqual(add_month("2026-11", 3), "2027-02")
        self.assertEqual(add_month("2026-01", -1), "2025-12")


class TestSegnali(unittest.TestCase):
    def test_label(self):
        self.assertEqual(label(60, divergence=True), "STRONG BUY")
        self.assertEqual(label(60, divergence=False), "BUY")         # niente divergenza -> niente STRONG
        self.assertEqual(label(-30), "SELL")
        self.assertEqual(label(10), "NEUTRO")

    def test_divergenza(self):
        self.assertTrue(is_divergence(-40, 30))                      # vendono EUR, comprano USD
        self.assertFalse(is_divergence(-40, -30))                    # vendono entrambi


class TestDateOrari(unittest.TestCase):
    def test_valid_date(self):
        self.assertTrue(valid_date("2026-10-14"))
        self.assertTrue(valid_date("2026-08"))
        self.assertFalse(valid_date("          "))                  # il bug corretto nella versione 4.1
        self.assertFalse(valid_date("<html>"))

    def test_fd(self):
        self.assertEqual(fd("2026-10-13"), "mar 13/10/2026")
        self.assertEqual(fd("2026-08"), "ago 2026")
        self.assertEqual(fd("spazzatura"), "n/d")                    # mai un errore

    def test_orario_cot(self):
        # venerdi' 16/10/2026 15:30 New York = 21:30 in Italia (entrambi con ora legale)
        self.assertEqual(utc_to_it(et_to_utc(date(2026, 10, 16), 15, 30)).strftime("%H:%M"), "21:30")
        # venerdi' 30/10/2026: l'Italia e' gia' all'ora solare, gli USA no -> 20:30
        self.assertEqual(utc_to_it(et_to_utc(date(2026, 10, 30), 15, 30)).strftime("%H:%M"), "20:30")


class TestPagina(unittest.TestCase):
    def test_dashboard_demo(self):
        """Prova completa: dati finti -> calcoli -> HTML. Se passa, tutta la catena funziona."""
        from cot_radar.demo import demo_data
        from cot_radar.pagina import build
        html, stato = build(demo_data, demo=True)
        self.assertIn("const D=", html)
        self.assertIn(stato["esito"], ("ok", "avvisi", "errori"))
        self.assertNotIn("{{", html)                                 # nessun segnaposto rimasto


if __name__ == "__main__":
    unittest.main()
