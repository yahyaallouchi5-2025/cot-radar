# -*- coding: utf-8 -*-
"""Test dell'agenda delle notizie (agenda.py) e degli avvisi Telegram (avvisi.py). Nessuna rete.
Lancia: python -m unittest tests.test_agenda -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import agenda, avvisi, notizie  # noqa: E402

# eventi nel formato di financecalendar.com (ridotti dai dati veri del 25/10/2026)
GREZZI = [
    {"id": "us-cpi-report-october-2026", "series_code": "us-cpi", "impact": "high", "date": "2026-10-14",
     "release_at_utc": "2026-10-14T12:30:00+00:00", "status": "released", "prior": "3.4", "actual": "3.7", "unit": "% y/y"},
    {"id": "uk-cpi-inflation-october-2026", "series_code": "gb-cpi", "impact": "high", "date": "2026-10-21",
     "release_at_utc": "2026-10-21T06:00:00+00:00", "status": "released", "prior": "3.1", "actual": "3.5", "unit": "% y/y"},
    {"id": "fomc-rate-decision-october-2026", "series_code": "fomc", "impact": "high", "date": "2026-10-28",
     "release_at_utc": "2026-10-28T18:00:00+00:00", "status": "confirmed", "prior": None, "actual": None,
     "unit": "% target range"},
    {"id": "eurozone-flash-cpi-november-2026", "series_code": "eu-cpi", "impact": "high", "date": "2026-11-04",
     "release_at_utc": None, "status": "confirmed", "prior": None, "actual": None, "unit": "% y/y"},
    {"id": "qualcosa-che-non-seguiamo", "series_code": "us-treasury-bills", "impact": "medium", "date": "2026-10-27",
     "release_at_utc": "2026-10-27T15:30:00+00:00"},
]
PAIRS = [{"pair": "NZDUSD", "base": "NZD", "quote": "USD", "label": "SELL", "score": -35.0},
         {"pair": "USDJPY", "base": "USD", "quote": "JPY", "label": "BUY", "score": 30.0},
         {"pair": "EURGBP", "base": "EUR", "quote": "GBP", "label": "NEUTRO", "score": 5.0}]


def dgs2(salto_giorno="2026-10-14", salto=0.12):
    """Tasso a 2 anni finto: piccole oscillazioni ogni giorno feriale, un salto nel giorno del CPI."""
    out, v, d = [], 3.50, date(2025, 9, 1)
    while d <= date(2026, 10, 20):
        if d.weekday() < 5:
            v += salto if d.isoformat() == salto_giorno else (0.01 if d.toordinal() % 2 else -0.01)
            out.append((d.isoformat(), round(v, 4)))
        d += timedelta(days=1)
    return out


class Agenda(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cache = os.path.join(self.dir, "agenda.json")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def costruisci(self, adesso, fred=None, scarica=lambda: GREZZI):
        return agenda.costruisci(fred or {"DGS2": dgs2()}, {}, PAIRS, adesso=adesso, scarica_fn=scarica, cache=self.cache)

    def test_reazione_e_verdetto_sui_segnali_esposti(self):
        a = self.costruisci(datetime(2026, 10, 20, 8, 0))
        cpi = next(e for e in a["eventi"] if e["codice"] == "us-cpi")
        self.assertTrue(cpi["uscito"])
        self.assertGreater(cpi["z"], 2)                                  # tassi su = sorpresa da falco = USD forte
        v = {x["coppia"]: x["verdetto"] for x in cpi["esposti"]}
        self.assertEqual(v, {"NZD/USD": "conferma", "USD/JPY": "conferma"})   # EURGBP neutro: non esposto
        self.assertNotIn("qualcosa-che-non-seguiamo", [e["id"] for e in a["eventi"]])
        gb = next(e for e in a["eventi"] if e["codice"] == "gb-cpi")
        self.assertIsNone(gb["z"])                                       # GBP: niente tasso a 2 anni nei nostri dati

    def test_fonte_giu_usa_la_copia_poi_il_calendario_interno(self):
        self.costruisci(datetime(2026, 10, 20, 8, 0))                    # salva la copia
        a = self.costruisci(datetime(2026, 10, 20, 8, 0), scarica=lambda: None)
        self.assertIn("copia salvata", a["fonte"])
        os.remove(self.cache)
        a = self.costruisci(datetime(2026, 10, 26, 8, 0), scarica=lambda: None)
        self.assertEqual(a["fonte"], "interno")
        self.assertIn("fomc", [e["codice"] for e in a["eventi"]])

    def test_motore_usa_gli_eventi_principali_dell_agenda(self):
        a = self.costruisci(datetime(2026, 10, 20, 8, 0))
        cal = agenda.calendario_motore(a)
        self.assertEqual([c[4] for c in cal], ["CPI USA", "Fed (FOMC)"])   # solo principali con orario certo
        out = notizie.motore({"DGS2": dgs2()}, {}, adesso=datetime(2026, 10, 15, 8, 0), calendario=cal)
        self.assertGreater(out["valute"]["USD"]["adj"], 0)


class Avvisi(unittest.TestCase):
    def ag(self, adesso, salto_giorno="2026-10-14"):
        return agenda.costruisci({"DGS2": dgs2(salto_giorno)}, {}, PAIRS, adesso=adesso, scarica_fn=lambda: GREZZI,
                                 cache=os.path.join(tempfile.mkdtemp(), "a.json"))

    def test_in_arrivo_una_sola_volta_la_sera_prima(self):
        adesso = datetime(2026, 10, 27, 22, 15)                          # FOMC domani 18:00 UTC = 20 ore
        a = self.ag(adesso)
        arrivo, _, st = avvisi.da_inviare(a, avvisi.stato_iniziale(a, adesso), adesso)
        self.assertEqual([e["codice"] for e in arrivo], ["fomc"])
        t = avvisi.testo_arrivo(arrivo, a["credito"])
        self.assertIn("Fed (FOMC)", t)
        self.assertIn("mer 28/10 ore 19:00", t)                          # ora italiana (solare dal 25/10)
        self.assertIn("USD più forte → a favore di: NZD/USD SELL, USD/JPY BUY", t)
        self.assertIn("financecalendar.com", t)
        arrivo2, _, _ = avvisi.da_inviare(a, st, adesso + timedelta(hours=1))
        self.assertEqual(arrivo2, [])

    def test_esito_aspetta_la_reazione_poi_parte_una_volta(self):
        # FRED non ha ancora il dato del giorno del CPI: esito in attesa
        adesso = datetime(2026, 10, 15, 6, 0)
        a = agenda.costruisci({"DGS2": [x for x in dgs2() if x[0] < "2026-10-14"]}, {}, PAIRS, adesso=adesso,
                              scarica_fn=lambda: GREZZI, cache=os.path.join(tempfile.mkdtemp(), "a.json"))
        _, gruppi, st = avvisi.da_inviare(a, {"arrivo": {}, "esito": {}}, adesso)
        self.assertEqual([g["chiave"] for g in gruppi], [])
        # giro dopo: il dato c'e' -> esito con verdetto
        adesso = datetime(2026, 10, 15, 22, 15)
        a = self.ag(adesso)
        _, gruppi, st = avvisi.da_inviare(a, st, adesso)
        self.assertEqual([g["chiave"] for g in gruppi], ["USD-2026-10-14"])
        t = avvisi.testo_esito(gruppi, a["credito"])
        self.assertIn("CPI USA (inflazione)</b>: 3,7% a/a (precedente 3,4% a/a)", t)
        self.assertIn("USD più forte", t)
        self.assertIn("NZD/USD SELL ✓ conferma", t)
        _, gruppi, _ = avvisi.da_inviare(a, st, adesso + timedelta(hours=8))
        self.assertEqual(gruppi, [])

    def test_valuta_senza_tasso_esito_con_il_solo_dato(self):
        adesso = datetime(2026, 10, 22, 6, 0)
        a = self.ag(adesso)
        _, gruppi, _ = avvisi.da_inviare(a, {"arrivo": {}, "esito": {"USD-2026-10-14": "2026-10-14"}}, adesso)
        self.assertEqual([g["chiave"] for g in gruppi], ["GBP-2026-10-21"])
        self.assertIn("non misurata per GBP", avvisi.testo_esito(gruppi, a["credito"]))

    def test_valori_leggibili(self):
        self.assertEqual(avvisi.valore("3.7", "% y/y"), "3,7% a/a")
        self.assertEqual(avvisi.valore("142000", "jobs"), "+142.000 posti")
        self.assertEqual(avvisi.valore("4.5", "% target range"), "4,5%")
        self.assertIsNone(avvisi.valore(None, "% y/y"))


if __name__ == "__main__":
    unittest.main()
