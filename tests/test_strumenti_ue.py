# -*- coding: utf-8 -*-
"""Strumenti da comprare in Europa (portafogli.STRUMENTI_UE) e anteprima delle 5 azioni (satellite.py).
Lancia: python -m unittest tests.test_strumenti_ue -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import portafogli as PF  # noqa: E402


class StrumentiUE(unittest.TestCase):
    def test_ogni_mercato_dei_profili_ha_un_isin_valido(self):
        # ogni mercato della base di ogni profilo (CASH compreso) deve avere un prodotto acquistabile in Europa
        for p in PF.PROFILI:
            for k in p["base"]:
                self.assertIn(k, PF.STRUMENTI_UE, f"{p['id']}: manca lo strumento UE per {k}")
        for nome, isin, _ in PF.STRUMENTI_UE.values():
            self.assertTrue(nome)
            self.assertRegex(isin, r"^[A-Z]{2}[A-Z0-9]{9}\d$")   # formato ISIN: paese + 9 caratteri + controllo

    def test_cifra_di_controllo_isin(self):
        # algoritmo di Luhn sulle cifre (lettere -> numeri): un ISIN copiato male viene scoperto qui
        for _, isin, _ in PF.STRUMENTI_UE.values():
            cifre = "".join(str(int(c, 36)) for c in isin[:-1])
            tot = 0
            for i, ch in enumerate(reversed(cifre)):
                n = int(ch) * (2 if i % 2 == 0 else 1)
                tot += n // 10 + n % 10
            self.assertEqual((10 - tot % 10) % 10, int(isin[-1]), isin)


if __name__ == "__main__":
    unittest.main()
