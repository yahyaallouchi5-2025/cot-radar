# -*- coding: utf-8 -*-
"""Test dei portafogli modello (cot_radar/portafogli.py). Nessuna rete: prezzi finti e COT finto.
Lancia: python -m unittest tests.test_portafogli -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import portafogli as P  # noqa: E402
from cot_radar.config import ASSETS  # noqa: E402

CODICI = {a[0]: a[1] for a in ASSETS}


def cot_finto(chiavi, compra):
    """Righe COT settimanali dal 2003: per le chiavi in 'compra' gli speculatori accumulano sempre piu' long."""
    righe, d = [], date(2003, 1, 7)
    t = 0
    while d < date(2026, 10, 20):
        for k in chiavi:
            netto = (1000 + t * 40) if k in compra else (1000 - (t % 7) * 10)
            righe.append({"cftc_contract_market_code": CODICI[k], "report_date_as_yyyy_mm_dd": d.isoformat(),
                          "open_interest_all": "100000", "noncomm_positions_long_all": str(20000 + netto),
                          "noncomm_positions_short_all": "20000", "comm_positions_long_all": "30000",
                          "comm_positions_short_all": "30000"})
        d += timedelta(days=7)
        t += 1
    return righe


class Portafogli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.px = P.prezzi_demo("2003-01-02", "2026-10-23")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_pesi_validi_e_tetti(self):
        g = P.Griglia(self.px)
        sc = P.segnali_cot(cot_finto([u[0] for u in P.UNIVERSO], {u[0] for u in P.UNIVERSO}))
        for prof in P.PROFILI:
            for i in P.date_ribilancio(g)[-24:]:
                pesi, _, _ = P.scegli(prof, g, i, sc)
                self.assertLessEqual(sum(pesi.values()), 1.001)                  # niente leva (arrotondamenti a parte)
                for k, w in pesi.items():
                    if k != "CASH":
                        self.assertIn(k, prof["ammessi"])                         # solo mercati del profilo
                        self.assertLessEqual(w, prof.get("tetti", {}).get(k, prof["tetto"]) + 1e-6)

    def test_niente_segnali_tutto_in_liquidita(self):
        g = P.Griglia(self.px)
        sc = P.segnali_cot(cot_finto(["SP500", "GOLD"], set()))
        pesi, _, esclusi = P.scegli(P.PROFILI[0], g, P.date_ribilancio(g)[-1], sc)
        self.assertEqual(pesi, {"CASH": 1.0})
        self.assertTrue(all("COT" in e["motivo"] or "media" in e["motivo"] for e in esclusi))

    def test_calcolo_completo_e_registro_mai_riscritto(self):
        righe = cot_finto([u[0] for u in P.UNIVERSO], {"SP500", "GOLD", "US10Y", "NASDAQ"})
        r = P.calcola(righe, self.px, cartella=self.dir, scrivi=True, oggi=date(2026, 10, 25))
        self.assertEqual([p["id"] for p in r["profili"]], ["conservativo", "moderato", "aggressivo"])
        self.assertEqual(r["prossima"], "2026-11-01")
        for p in r["profili"]:
            self.assertIsNotNone(p["stat"]["oos"])
            self.assertAlmostEqual(sum(c["peso"] for c in p["composizione"]), 100, delta=0.6)
        rot = P.leggi_rotazioni(self.dir)
        self.assertEqual(len(rot), 1)
        # stessa data con pesi diversi: la rotazione salvata NON cambia
        P.registra(rot, rot[0]["data"], {"conservativo": {"CASH": 1.0}}, self.dir)
        self.assertEqual(P.leggi_rotazioni(self.dir), rot)
        # al giro dopo c'e' la linea live
        r2 = P.calcola(righe, self.px, cartella=self.dir, scrivi=True, oggi=date(2026, 10, 25))
        self.assertEqual(r2["profili"][0]["live_dal"], rot[0]["data"])

    def test_statistiche(self):
        curva = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 100 + i * 0.1 - (20 if 100 < i < 150 else 0))
                 for i in range(400)]
        s = P.statistiche(curva)
        self.assertLess(s["maxdd"], -15)
        self.assertIsNotNone(s["peggior_mese"])

    def test_copia_yahoo_sostituita_solo_se_completa(self):
        lunga = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0 + i) for i in range(100)]
        P._scrivi(self.dir, "SPY", lunga)
        out = P.prezzi(scarica=lambda t: lunga[:50], cartella=self.dir, oggi=date(2026, 1, 2), pausa=0)
        self.assertEqual(len(out["SPY"]), 100)                                    # download corto: si tiene la copia


if __name__ == "__main__":
    unittest.main()
