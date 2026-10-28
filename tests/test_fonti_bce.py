# -*- coding: utf-8 -*-
"""Test del nuovo tentativo verso la BCE (fonti.get_ecb) e dell'avviso "grave" (calendario.sources_status).
Nessuna rete: http() e' sostituito. Lancia: python -m unittest tests.test_fonti_bce -v"""
import io
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import fonti  # noqa: E402

CSV = "KEY,TIME_PERIOD,OBS_VALUE\nYC.X,2026-10-27,2.1\n"


def errore(codice):
    return urllib.error.HTTPError("https://bce", codice, "Gateway Time-out", {}, io.BytesIO(b""))


class Riprova(unittest.TestCase):
    def setUp(self):
        self.orig, self.chiamate = fonti.http, []
        fonti.ECB_RIPROVA = 0                         # niente attese nei test

    def tearDown(self):
        fonti.http = self.orig

    def finto(self, risposte):
        def http(url):
            self.chiamate.append(url)
            r = risposte.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        fonti.http = http

    def test_504_poi_ok_un_solo_nuovo_tentativo(self):
        self.finto([errore(504), CSV])
        self.assertEqual(fonti.get_ecb("YC", "X", "2026-01-01"), {"YC.X": [["2026-10-27", 2.1]]})
        self.assertEqual(len(self.chiamate), 2)

    def test_due_504_si_rinuncia_dopo_il_secondo(self):
        self.finto([errore(504), errore(504), CSV])
        with self.assertRaises(urllib.error.HTTPError):
            fonti.get_ecb("YC", "X", "2026-01-01")
        self.assertEqual(len(self.chiamate), 2)

    def test_404_non_si_riprova(self):
        self.finto([errore(404), CSV])
        with self.assertRaises(urllib.error.HTTPError):
            fonti.get_ecb("YC", "X", "2026-01-01")
        self.assertEqual(len(self.chiamate), 1)


if __name__ == "__main__":
    unittest.main()
