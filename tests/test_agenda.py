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

from cot_radar import agenda, avvisi, notizie, notifiche, registro  # noqa: E402
from datetime import timezone  # noqa: E402

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
        t = avvisi.testo_esito(gruppi, a["credito"])
        self.assertIn("Lettura del dato: sopra il precedente → GBP tendenzialmente più forte", t)
        self.assertIn("non misurata per questa valuta", t)

    def test_direzione_del_dato(self):
        self.assertEqual(avvisi.direzione({"attuale": "3.5", "precedente": "3.1"}), (1, "sopra il precedente"))
        self.assertEqual(avvisi.direzione({"tipo": "banca", "attuale": "4.25", "precedente": "4.5"}),
                         (-1, "tassi tagliati"))
        self.assertIsNone(avvisi.direzione({"attuale": None, "precedente": "3.1"}))

    def test_valori_leggibili(self):
        self.assertEqual(avvisi.valore("3.7", "% y/y"), "3,7% a/a")
        self.assertEqual(avvisi.valore("142000", "jobs"), "+142.000 posti")
        self.assertEqual(avvisi.valore("4.5", "% target range"), "4,5%")
        self.assertIsNone(avvisi.valore(None, "% y/y"))


class Settimana(unittest.TestCase):
    def ag(self, adesso):
        return agenda.costruisci({"DGS2": dgs2()}, {}, PAIRS, adesso=adesso, scarica_fn=lambda: GREZZI,
                                 cache=os.path.join(tempfile.mkdtemp(), "a.json"))

    def test_finestra_di_invio(self):
        ven = datetime(2026, 10, 23, 20, 30)                             # venerdi' sera
        self.assertEqual(avvisi.settimana_da_inviare({}, ven), date(2026, 10, 26))
        self.assertIsNone(avvisi.settimana_da_inviare({}, datetime(2026, 10, 23, 10, 0)))   # venerdi' mattina
        self.assertEqual(avvisi.settimana_da_inviare({}, datetime(2026, 10, 26, 5, 30)), date(2026, 10, 26))
        self.assertIsNone(avvisi.settimana_da_inviare({}, datetime(2026, 10, 27, 5, 30)))   # martedi': no
        self.assertIsNone(avvisi.settimana_da_inviare({"settimana": "2026-10-26"}, ven))    # gia' inviata

    def test_testo_per_giorno(self):
        a = self.ag(datetime(2026, 10, 23, 20, 30))
        t = avvisi.testo_settimana(a, date(2026, 10, 26))
        self.assertIn("notizie della settimana 26/10 – 01/11", t)
        self.assertIn("<b>Mercoledì 28/10</b>", t)
        self.assertIn("19:00 · <b>Fed (FOMC)</b> — decisione sui tassi della Fed", t)
        self.assertIn("rialzo o toni duri → USD più forte", t)
        self.assertIn("USD più forte → a favore di: NZD/USD SELL, USD/JPY BUY", t)
        self.assertNotIn("CPI USA", t)                                   # fuori settimana
        self.assertIsNone(avvisi.testo_settimana(a, date(2026, 12, 7)))   # settimana vuota

    def test_stato_settimana_conservato(self):
        a = self.ag(datetime(2026, 10, 27, 22, 15))
        _, _, st = avvisi.da_inviare(a, {"arrivo": {}, "esito": {}, "settimana": "2026-10-26"},
                                     datetime(2026, 10, 27, 22, 15))
        self.assertEqual(st["settimana"], "2026-10-26")


class FlussoVenerdi(unittest.TestCase):
    """Giro completo di notifiche.esegui: venerdi' sera riepilogo COT + agenda della settimana, una volta sola."""
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.inviati = []
        self._orig = notifiche.invia_telegram
        notifiche.invia_telegram = lambda token, chat, testo: (self.inviati.append(testo), True)[1]
        registro._scrivi(self.dir, registro.concatena([], registro.ZERO, 0))

    def tearDown(self):
        notifiche.invia_telegram = self._orig
        shutil.rmtree(self.dir)

    def test_agenda_settimanale_una_volta(self):
        env = {"TELEGRAM_BOT_TOKEN": "finto", "TELEGRAM_CHAT_ID": "@canale"}
        gio = datetime(2026, 10, 22, 22, 15)
        dati = {"agenda": agenda.costruisci({"DGS2": dgs2()}, {}, PAIRS, adesso=gio, scarica_fn=lambda: GREZZI,
                                            cache=os.path.join(self.dir, "a.json"))}
        notifiche.esegui(self.dir, "", env, gio.replace(tzinfo=timezone.utc), dati_sito=dati)     # primo avvio
        ven = datetime(2026, 10, 23, 20, 30, tzinfo=timezone.utc)
        notifiche.esegui(self.dir, "", env, ven, dati_sito=dati)
        self.assertEqual(len([t for t in self.inviati if "notizie della settimana 26/10" in t]), 1)
        self.assertEqual(notifiche.leggi_cursore(self.dir)["agenda"]["settimana"], "2026-10-26")
        notifiche.esegui(self.dir, "", env, ven.replace(hour=21), dati_sito=dati)                  # giro dopo
        notifiche.esegui(self.dir, "", env, datetime(2026, 10, 26, 5, 30, tzinfo=timezone.utc), dati_sito=dati)
        self.assertEqual(len([t for t in self.inviati if "notizie della settimana" in t]), 1)

    def test_prova_notizie_tre_esempi(self):
        a = agenda.costruisci({"DGS2": dgs2()}, {}, PAIRS, adesso=datetime(2026, 10, 25, 15, 0),
                              scarica_fn=lambda: GREZZI, cache=os.path.join(self.dir, "a.json"))
        r = notifiche.prova_notizie("", {"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "y"}, {"agenda": a},
                                    adesso=datetime(2026, 10, 25, 15, 0))
        self.assertEqual(r["messaggi"], 3)
        self.assertTrue(all("[TEST · esempio]" in t for t in self.inviati))
        self.assertIn("notizie della settimana 26/10", self.inviati[0])
        self.assertIn("notizie in arrivo", self.inviati[1])
        self.assertIn("esito delle notizie", self.inviati[2])


if __name__ == "__main__":
    unittest.main()
