# -*- coding: utf-8 -*-
"""Test della scheda Azioni (cot_radar/azioni.py). Nessuna rete: Yahoo e' sostituito da funzioni finte.
Lancia: python -m unittest tests.test_azioni -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import azioni as A  # noqa: E402


def finto(t, intervallo="1d", periodo="2y"):
    """Serie regolare: +0,1% al giorno (o +1% al mese) dal 2024."""
    meta = {"nome": "Nome " + t, "valuta": "USD", "borsa": "Prova"}
    if intervallo == "1mo":
        return meta, [(f"{a}-{m:02d}", 100 * 1.01 ** ((a - 2000) * 12 + m)) for a in range(2000, 2026) for m in range(1, 13)]
    d, v, out = date(2024, 10, 1), 100.0, []
    while d <= date(2026, 10, 23):
        if d.weekday() < 5:
            v *= 1.001
            out.append((d.isoformat(), round(v, 4)))
        d += timedelta(days=1)
    return meta, out


class Azioni(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_elenco_completo_e_settori_validi(self):
        el = A.elenco()
        self.assertGreater(len(el), 600)
        ids = {s[0] for s in A.SETTORI}
        self.assertTrue(all(x["s"] in ids for x in el))
        self.assertTrue(all(set(x["l"]) <= set(A.LISTINI) for x in el))
        self.assertEqual(len({x["t"] for x in el}), len(el))                     # nessun doppione

    def test_giro_completo_e_file_pubblici(self):
        tit = [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]}, {"t": "BBB.MI", "nome": "B", "s": "fin", "l": ["mib"]}]
        st = A.aggiorna(self.dir, ["AAA", "BBB.MI"], oggi=date(2026, 10, 26), scarica=finto, pausa=0)
        self.assertEqual(st["ok"], 2)
        self.assertIsNone(st["anomalia"])
        ix = A.pubblica(self.dir, st, tit)
        self.assertEqual(len(ix["titoli"]), 2)
        r = ix["titoli"][0]
        self.assertEqual(r["n"], "Nome AAA")                                     # nome da Yahoo
        self.assertGreater(r["v1a"], 0)
        self.assertTrue(0 <= min(r["sp"]) and max(r["sp"]) <= 99)
        det = json.load(open(os.path.join(self.dir, "pubblico", "titoli", "BBB.MI.json")))
        self.assertEqual(len(det["stag"]["mesi"]), 12)
        self.assertAlmostEqual(det["stag"]["mesi"][0]["media"], 1.0, places=1)    # +1% al mese

    def test_punteggio_e_vetrina(self):
        base = {"s": "tech", "l": ["sp500"], "t200": 5, "v3m": 4, "v1a": 20, "st_media": 1.0, "st_pos": 70, "st_n": 20,
                "dmax": -3}
        righe = [dict(base, t="A%d" % i, v1a=i, s="tech" if i % 2 else "fin") for i in range(10)]
        righe.append(dict(base, t="DEBOLE", v1a=-30, t200=-10))
        A.punteggi(righe)
        self.assertEqual(sorted(r["rk"] for r in righe), list(range(1, 12)))
        top = A.vetrina(righe)
        self.assertLessEqual(len(top), A.TOP_N)
        self.assertNotIn("DEBOLE", [r["t"] for r in top])                     # sotto la media a 200 giorni: escluso
        self.assertEqual(len({r["s"] for r in top}), len(top))                 # al massimo un titolo per settore
        self.assertEqual(top[0]["t"], "A9")                                     # il piu' forte del suo settore

    def test_yahoo_fermo_copia_e_anomalia(self):
        A.aggiorna(self.dir, ["AAA"], oggi=date(2026, 10, 23), scarica=finto, pausa=0)
        chiesti = []
        def giu(t, *a, **k):
            chiesti.append(t)
            return None
        titoli = ["AAA"] + [f"X{i}" for i in range(9)]
        st = A.aggiorna(self.dir, titoli, oggi=date(2026, 10, 26), scarica=giu, pausa=0)
        self.assertEqual(len(chiesti), A.DI_FILA)                                 # dopo 5 fallimenti di fila basta
        self.assertTrue(st["fermo"])
        self.assertEqual(st["copia"], ["AAA"])                                    # resta la copia di venerdi'
        self.assertEqual(st["anomalia"]["codice"], A.CODICE_ERRORE)
        self.assertRegex(st["anomalia"]["quando"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")  # giorno e ora dell'anomalia
        ix = A.pubblica(self.dir, st, [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]}])
        self.assertEqual(len(ix["titoli"]), 1)                                    # la scheda resta piena
        self.assertIsNotNone(ix["anomalia"])

    def test_tentativi_e_dati_rotti(self):
        n = []
        def rotto(req, timeout=0):
            n.append(1)
            raise OSError("429")
        with mock.patch.object(A.urllib.request, "urlopen", rotto):
            self.assertIsNone(A.scarica("AAA", attesa=0))
        self.assertEqual(len(n), A.TENTATIVI)
        serie = [((date(2026, 1, 1) + timedelta(days=i)).isoformat(), 10.0) for i in range(30)]
        serie[10] = (serie[10][0], 1.0)                                           # crollo del 90% in un giorno: dato rotto
        self.assertIsNone(A._valida(serie))

    def test_ramo_assente_non_blocca(self):
        with mock.patch("subprocess.run", side_effect=OSError("niente git")):
            self.assertFalse(A.copia_nel_sito(self.dir))


if __name__ == "__main__":
    unittest.main()
