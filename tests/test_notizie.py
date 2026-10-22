# -*- coding: utf-8 -*-
"""Test del motore notizie: sorpresa misurata dal mercato, decadimento, tetto e applicazione alle coppie.
Lancia con:  python -m unittest discover -s tests"""
import unittest
from datetime import date, datetime, timedelta

from cot_radar import notizie


def serie_con_salto(giorno_salto, salto=0.20, giorni=300):
    """Tasso a 2 anni finto: oscilla di +-0.02 ogni giorno e nel 'giorno_salto' sale di 'salto' punti %."""
    out, v, d = [], 4.0, date.fromisoformat(giorno_salto) - timedelta(days=giorni)
    i = 0
    while d <= date.fromisoformat(giorno_salto) + timedelta(days=5):
        if d.weekday() < 5:
            v += salto if d.isoformat() == giorno_salto else (0.02 if i % 2 else -0.02)
            out.append([d.isoformat(), round(v, 4)])
            i += 1
        d += timedelta(days=1)
    return out


class TestNotizie(unittest.TestCase):
    def test_sorpresa_falco(self):
        z, pb = notizie.sorpresa_mercato("2026-11-06", serie_con_salto("2026-11-06"))
        self.assertGreater(z, 5)              # 20 pb contro movimenti normali di 2 pb: sorpresa enorme
        self.assertAlmostEqual(pb, 20.0, places=0)

    def test_tetto_e_decadimento(self):
        fred = {"DGS2": serie_con_salto("2026-11-06")}
        subito = notizie.motore(fred, {}, datetime(2026, 11, 6, 20))["valute"]["USD"]["adj"]
        dopo = notizie.motore(fred, {}, datetime(2026, 11, 9, 20))["valute"]["USD"]["adj"]
        self.assertEqual(subito, notizie.TETTO)            # correttivo limitato al tetto
        self.assertLess(dopo, subito)                      # 3 giorni dopo pesa meno

    def test_coppia_penalizzata(self):
        fred = {"DGS2": serie_con_salto("2026-11-06")}
        news = notizie.motore(fred, {}, datetime(2026, 11, 6, 20))
        pairs = [{"pair": "EURUSD", "base": "EUR", "quote": "USD", "score": 70}]
        notizie.applica(pairs, {}, news)
        self.assertEqual(pairs[0]["news"]["effetto"], "penalizza")   # dollaro piu' forte = EURUSD giu'
        self.assertLess(pairs[0]["news"]["score"], 70)


if __name__ == "__main__":
    unittest.main()
