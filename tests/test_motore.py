# -*- coding: utf-8 -*-
"""Test del motore unico dei segnali, del registro live (catena di hash) e del backtest (niente "futuro").
Lancia:  python -m unittest tests.test_motore -v"""
import os
import random
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import backtest, motore, registro  # noqa: E402
from cot_radar.config import ASSETS  # noqa: E402


def giorni(inizio, prezzi):
    """Serie [(data, prezzo)] nei giorni feriali a partire da 'inizio'."""
    out, d = [], date.fromisoformat(inizio)
    for p in prezzi:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append((d.isoformat(), p))
        d += timedelta(days=1)
    return out


class Orari(unittest.TestCase):
    def test_ora_legale_italia_e_new_york(self):
        self.assertEqual(motore.ora_italia("2026-10-23T19:47Z"), "23/10/2026 ore 21:47")    # ora legale
        self.assertEqual(motore.ora_italia("2026-12-04T20:47Z"), "04/12/2026 ore 21:47")    # ora solare
        self.assertEqual(motore.chiusura_utc("2026-10-23", "fx").strftime("%H:%M"), "16:00")  # 12:00 NY (EDT)
        self.assertEqual(motore.chiusura_utc("2026-12-04", "fx").strftime("%H:%M"), "17:00")  # 12:00 NY (EST)

    def test_pubblicazione_cot_venerdi(self):
        t = motore.pubblicazione_cot("2026-10-20")
        self.assertEqual((t.date().isoformat(), t.strftime("%H:%M")), ("2026-10-23", "19:30"))


class Transizioni(unittest.TestCase):
    def passi(self, etichette):
        aperti, ev = {}, []
        for i, lab in enumerate(etichette):
            q = f"2026-01-{i + 1:02d}T20:00Z"
            ev += motore.transizioni(aperti, {"EURUSD": {"etichetta": lab, "punteggio": 0}}, q, f"w{i}")
        return ev

    def test_nascita_conferma_chiusura(self):
        ev = self.passi(["NEUTRO", "BUY", "BUY", "SELL", "NEUTRO"])
        tipi = [(e["tipo"], e.get("etichetta") or e.get("motivo")) for e in ev]
        self.assertEqual(tipi, [("apertura", "BUY"), ("conferma", "BUY"), ("chiusura", "inversione"),
                                ("apertura", "SELL"), ("chiusura", "neutro")])

    def test_strong_figlio(self):
        ev = self.passi(["SELL", "STRONG SELL", "SELL", "NEUTRO"])
        aperture = [e for e in ev if e["tipo"] == "apertura"]
        self.assertEqual(len(aperture), 2)
        self.assertEqual(aperture[1]["padre"], aperture[0]["id"])
        segnali, aperti = motore.applica(ev)
        self.assertEqual(segnali[aperture[1]["id"]]["chiuso"]["motivo"], "indebolito")
        self.assertEqual(segnali[aperture[0]["id"]]["chiuso"]["motivo"], "neutro")
        self.assertEqual(aperti, {})

    def test_applica_ricostruisce_lo_stato(self):
        aperti, ev = {}, []
        for i, lab in enumerate(["BUY", "STRONG BUY", "STRONG BUY"]):
            ev += motore.transizioni(aperti, {"X": {"etichetta": lab, "punteggio": 0}}, f"2026-01-0{i + 1}T20:00Z", f"w{i}")
        _, ricostruiti = motore.applica(ev)
        self.assertEqual(ricostruiti, aperti)


class Misura(unittest.TestCase):
    def test_ingresso_dopo_il_segnale_e_metriche(self):
        pts = giorni("2026-01-05", [100, 101, 99, 102, 103, 104, 98, 105, 106, 107, 108, 109, 110, 111, 112] + [112] * 30)
        # generato lunedi' 5/1 alle 20:00 UTC: la chiusura FX del 5/1 (17:00 UTC) e' gia' passata -> ingresso il 6/1
        s = {"verso": 1, "generato": "2026-01-05T20:00Z", "chiuso": None}
        m = motore.misura(s, pts, "fx")
        self.assertEqual(m["ingresso"]["data"], "2026-01-06")
        self.assertEqual(m["ingresso"]["prezzo"], 101)
        a1 = m["A"]["1s"]
        self.assertEqual(a1["data"], "2026-01-13")
        self.assertAlmostEqual(a1["res"], (98 / 101 - 1) * 100, places=2)     # chiusura del 13/1
        self.assertAlmostEqual(a1["mae"], (98 / 101 - 1) * 100, places=2)
        self.assertAlmostEqual(a1["mfe"], (104 / 101 - 1) * 100, places=2)    # massimo lungo il percorso (12/1)

    def test_vendita_e_chiusura(self):
        pts = giorni("2026-01-05", [100, 100, 98, 97, 99, 95, 96, 94] + [94] * 40)
        s = {"verso": -1, "generato": "2026-01-05T10:00Z", "chiuso": {"quando": "2026-01-09T20:00Z", "motivo": "neutro"}}
        m = motore.misura(s, pts, "fx")
        self.assertEqual(m["ingresso"]["data"], "2026-01-05")
        f = m["A"]["fine"]
        self.assertEqual(f["data"], "2026-01-12")                 # prima chiusura dopo la chiusura del segnale
        self.assertAlmostEqual(f["res"], 5.0, places=2)           # da 100 a 95 in vendita = +5%
        self.assertFalse(f["provvisorio"])

    def test_percorso_giornaliero(self):
        pts = giorni("2026-01-05", [100, 101, 99, 102, 103, 104, 98] + [100] * 30)
        s = {"verso": 1, "generato": "2026-01-05T20:00Z", "chiuso": None}
        m = motore.misura(s, pts, "fx")
        g = m["G"]                                                  # ingresso 101 il 6/1
        self.assertEqual(len(g), motore.GIORNI_MAX)
        self.assertAlmostEqual(g[0][0], (99 / 101 - 1) * 100, places=2)     # giorno 1: 99
        self.assertAlmostEqual(g[3][1], (104 / 101 - 1) * 100, places=2)    # massimo fino al giorno 4
        self.assertAlmostEqual(g[4][2], (98 / 101 - 1) * 100, places=2)     # drawdown fino al giorno 5
        st = motore.giorni_stat([(s, m, 0.0)])
        self.assertEqual(st[0][:2], [1, 0])                         # giorno 1 perso
        self.assertEqual(st[3][:2], [1, 1])                         # giorno 4 vinto

    def test_wilson(self):
        lo, hi = motore.wilson(5, 10)
        self.assertTrue(lo < 50 < hi)
        self.assertEqual(motore.wilson(0, 0), None)


class Registro(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def giro(self, label, quando, fonti=None):
        pairs = [{"pair": "EURUSD", "base": "EUR", "quote": "USD", "score": 30 if "BUY" in label else 0, "label": label}]
        prezzi = {"EUR": giorni("2025-01-01", [1.0 + i * 0.001 for i in range(400)])}
        v = registro.aggiorna(pairs, {}, prezzi, fonti or {"cot": "online", "fred": "online"}, quando, "2026-01-06",
                              cartella=self.dir)
        registro.salva()
        return v

    def test_catena_e_iniziale(self):
        t = datetime(2026, 1, 9, 22, 15, tzinfo=timezone.utc)
        v = self.giro("BUY", t)
        self.assertTrue(v["integra"])
        self.assertTrue(v["aperti"][0]["iniziale"])                # gia' attivo al primo avvio
        self.giro("NEUTRO", t + timedelta(days=3))
        self.giro("SELL", t + timedelta(days=4))
        ev = registro.leggi(self.dir)
        self.assertEqual(len(ev), 3)
        self.assertTrue(registro.verifica(ev)[0])
        self.assertNotIn("iniziale", ev[2])                       # nato davvero: entra nelle statistiche

    def test_manomissione_rilevata(self):
        t = datetime(2026, 1, 9, 22, 15, tzinfo=timezone.utc)
        self.giro("BUY", t)
        self.giro("NEUTRO", t + timedelta(days=1))
        f = os.path.join(self.dir, registro.FILE)
        testo = open(f, encoding="utf-8").read().replace('"BUY"', '"SELL"', 1)
        open(f, "w", encoding="utf-8").write(testo)
        v = self.giro("BUY", t + timedelta(days=2))
        self.assertFalse(v["integra"])
        self.assertEqual(len(registro.leggi(self.dir)), 2)         # con catena rotta non si scrive piu'

    def test_dati_incompleti_non_scrivono(self):
        t = datetime(2026, 1, 9, 22, 15, tzinfo=timezone.utc)
        v = self.giro("BUY", t, fonti={"cot": "online", "fred": "parziale"})
        self.assertFalse(v["completi"])
        self.assertEqual(registro.leggi(self.dir), [])


class Backtest(unittest.TestCase):
    def righe(self, settimane, seme=3, cambia_dopo=None):
        random.seed(seme)
        out, d0 = [], date(2015, 1, 6)
        for k, code, _, _ in ASSETS:
            if k not in ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "DXY", "SP500"):
                continue
            net = 0.0
            for w in range(settimane):
                net = 0.97 * net + random.gauss(0, 3000)
                d = d0 + timedelta(weeks=w)
                if cambia_dopo and d.isoformat() > cambia_dopo:
                    net += 20000                                   # "futuro" diverso
                out.append({"cftc_contract_market_code": code, "report_date_as_yyyy_mm_dd": d.isoformat(),
                            "open_interest_all": "100000", "noncomm_positions_long_all": str(50000 + net / 2),
                            "noncomm_positions_short_all": str(50000 - net / 2),
                            "comm_positions_long_all": str(40000 - net / 2), "comm_positions_short_all": str(40000 + net / 2)})
        return out

    def prezzi(self):
        random.seed(9)
        out = {}
        for k in ("EUR", "GBP", "AUD", "NZD", "SP500"):
            p, v = 1.0, []
            for _ in range(3500):
                p *= 1 + random.gauss(0, 0.005)
                v.append(p)
            out[k] = giorni("2014-01-01", v)
        for k in ("JPY", "CHF", "CAD"):
            out[k] = [(d, 1 / v) for d, v in out["EUR"]]
        return out

    def test_niente_futuro(self):
        """I segnali nati prima di una data non devono cambiare se cambiano i dati DOPO quella data."""
        pr = self.prezzi()
        a = backtest.calcola(self.righe(400), pr, con_eventi=True)
        b = backtest.calcola(self.righe(400, cambia_dopo="2020-01-01"), pr, con_eventi=True)
        prima = lambda r: [(e["tipo"], e["id"]) for e in r["_eventi"] if (e.get("quando") or e["generato"]) < "2020-01-01"]
        self.assertTrue(len(prima(a)) > 50)
        self.assertEqual(prima(a), prima(b))
        self.assertTrue(a["n"] > 0 and "holdout" in a["periodi"])
        self.assertEqual(len(a["periodi"]["tutti"]["riass"]["g"]), 20)        # percorso 1..20 sedute


if __name__ == "__main__":
    unittest.main()
