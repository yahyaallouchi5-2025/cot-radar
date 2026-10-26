# -*- coding: utf-8 -*-
"""Test dei portafogli modello (cot_radar/portafogli.py). Nessuna rete: prezzi finti e COT finto.
Lancia: python -m unittest tests.test_portafogli -v"""
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
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
                        self.assertLessEqual(w, prof["base"][k] + 1e-6)          # mai oltre il peso della base

    def test_trend_negativo_peso_in_liquidita(self):
        px = dict(self.px)
        giu = [(d, 100.0 * 0.999 ** n) for n, (d, _) in enumerate(px["IEF"])]      # Treasury sempre in discesa
        px["IEF"] = giu
        g = P.Griglia(px)
        sc = P.segnali_cot(cot_finto(["US10Y"], {"US10Y"}))                       # COT da acquisto: non conta
        pesi, _, esclusi = P.scegli(P.PROFILI[0], g, P.date_ribilancio(g)[-1], sc)
        self.assertNotIn("US10Y", pesi)
        self.assertGreaterEqual(pesi["CASH"], 0.45 + 0.15 - 1e-6)
        self.assertEqual([e["k"] for e in esclusi if e["k"] == "US10Y"], ["US10Y"])

    def test_calcolo_completo_e_registro_mai_riscritto(self):
        righe = cot_finto([u[0] for u in P.UNIVERSO], {"SP500", "GOLD", "US10Y", "NASDAQ"})
        r = P.calcola(righe, self.px, cartella=self.dir, scrivi=True, oggi=date(2026, 10, 25))
        self.assertEqual([p["id"] for p in r["profili"]], ["conservativo", "moderato", "aggressivo"])
        self.assertEqual(r["prossima"], "2026-11-02")   # 1 novembre 2026 e' domenica: primo giorno feriale
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

    def test_rischio_del_mese(self):
        # due mercati sintetici: SPY scende del 10% ogni ottobre e risale a novembre, SHY piatto
        giorni, d = [], date(2015, 1, 1)
        while d < date(2020, 12, 31):
            if d.weekday() < 5:
                giorni.append(d.isoformat())
            d += timedelta(days=1)
        spy, v = [], 100.0
        for gg in giorni:
            if gg[5:7] == "10":
                v *= 0.995
            spy.append((gg, v))
        g = P.Griglia({"SPY": spy, "SHY": [(x, 100.0) for x in giorni]})
        m = P.rischio_mese(g, {"SP500": 0.5, "CASH": 0.5}, "10", "2020-10")
        self.assertEqual(m["mese"], "ottobre")
        self.assertEqual([x["a"] for x in m["anni"]], [2015, 2016, 2017, 2018, 2019])   # ottobre 2020 escluso
        self.assertTrue(all(x["r"] < 0 and x["dd"] <= x["r"] for x in m["anni"]))
        self.assertEqual(m["positivi"], 0)
        self.assertEqual(m["mercati"][0]["k"], "SP500")

    def test_download_ritentato_e_validato(self):
        chiamate = []
        def finto(req, timeout=0):
            chiamate.append(1)
            raise OSError("503")
        with mock.patch.object(P.urllib.request, "urlopen", finto):
            self.assertIsNone(P.scarica_yahoo("SPY", attesa=0))
        self.assertEqual(len(chiamate), P.TENTATIVI)                             # riprova prima di arrendersi
        rotta = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0) for i in range(40)]
        rotta[20] = (rotta[20][0], 100.0)                                        # salto assurdo: serie scartata
        self.assertIsNone(P._valida(rotta))

    def test_yahoo_giu_si_smette_e_si_usa_la_copia(self):
        lunga = [((date(2020, 1, 1) + timedelta(days=i)).isoformat(), 10.0 + i) for i in range(100)]
        P._scrivi(self.dir, "SPY", lunga)
        chiesti = []
        out = P.prezzi(scarica=lambda t: chiesti.append(t), cartella=self.dir, oggi=date(2026, 1, 2), pausa=0)
        self.assertEqual(len(chiesti), 3)                                         # dopo 3 fallimenti di fila basta
        self.assertEqual(len(out["SPY"]), 100)                                    # la copia resta
        self.assertIn("SPY", P.ESITO["copia"])

    def test_avviso_prezzi_vecchi_e_scheda_di_riserva(self):
        px = {t: [("2026-10-20", 1.0)] for t in P.usati()}
        self.assertIsNone(P.controlla_prezzi(px, date(2026, 10, 23)))
        av = P.controlla_prezzi(px, date(2026, 10, 30))
        self.assertEqual(av["codice"], P.CODICE_ERRORE)
        self.assertEqual(av["dal"], "2026-10-20")
        self.assertIsNone(P.di_riserva(self.dir))                                 # nessuna copia: niente scheda
        P.salva_ultimo({"aggiornato": "2026-10-20", "profili": []}, self.dir)
        self.assertEqual(P.di_riserva(self.dir)["avviso"]["dal"], "2026-10-20")

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
