# -*- coding: utf-8 -*-
"""Test della quota "Azioni scelte" dei portafogli (cot_radar/satellite.py + la parte in portafogli.py).
Nessuna rete: titoli finti scritti in una cartella temporanea. Lancia: python -m unittest tests.test_satellite -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import azioni as A, portafogli as P, satellite as S  # noqa: E402

SETTORI = ["tech", "salute", "fin", "ener", "ind", "tlc", "cdisc"]


def _mesi(dal, al):
    out, a, m = [], int(dal[:4]), int(dal[5:])
    while "%d-%02d" % (a, m) <= al:
        out.append("%d-%02d" % (a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def scrivi_titolo(cartella, t, crescita, ottobre=0.0, fino="2026-10"):
    """Titolo finto: crescita mensile costante + un extra a ottobre (stagionalita'); giornaliero = ultimi 40 giorni."""
    m, v = [], 100.0
    for ym in _mesi("2000-01", fino):
        v *= 1 + crescita + (ottobre if ym.endswith("-11") else 0)
        m.append([ym, round(v, 4)])
    d, g = [], date(2026, 9, 20)
    for i in range(40):
        g += timedelta(days=1)
        if g.weekday() < 5:
            d.append([g.isoformat(), round(v * (1 + 0.001 * i), 4)])
    A._scrivi(os.path.join(cartella, "grezzi", t + ".json"), {"t": t, "nome": "Nome " + t, "m": m, "d": d})


class Satellite(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # 7 titoli in 7 settori: i primi 5 salgono (ottobre->novembre molto positivo), gli ultimi 2 scendono
        self.el = []
        for i, s in enumerate(SETTORI):
            t = "T%d" % i
            scrivi_titolo(self.dir, t, 0.01 + i * 0.001 if i < 5 else -0.01, ottobre=0.03 if i < 5 else 0)
            self.el.append({"t": t, "nome": t, "s": s, "l": ["sp500"]})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_scelta_regole_e_un_titolo_per_settore(self):
        tt = S.carica(self.dir, self.el)
        sc = S.scelta(tt, S._n("2025-10"))
        self.assertEqual(sorted(x["t"] for x in sc), ["T0", "T1", "T2", "T3", "T4"])   # i titoli in calo esclusi
        self.assertEqual(len({x["s"] for x in sc}), len(sc))

    def test_registro_ultimo_giorno_e_mai_riscritto(self):
        tt = S.carica(self.dir, self.el)
        reg = S.registra(self.dir, tt, date(2026, 10, 30))      # venerdi' 30 ottobre: ultimo giorno feriale
        self.assertIn("2026-11", reg)
        prima = json.dumps(reg["2026-11"], sort_keys=True)
        scrivi_titolo(self.dir, "T0", -0.05)                      # i dati cambiano dopo...
        reg2 = S.registra(self.dir, S.carica(self.dir, self.el), date(2026, 11, 2))
        self.assertEqual(json.dumps(reg2["2026-11"], sort_keys=True), prima)   # ...ma la scelta registrata no
        self.assertFalse(S._ultimo_giorno_mese(date(2026, 10, 29)))

    def test_prima_del_live_niente_registro(self):
        reg = S.registra(self.dir, S.carica(self.dir, self.el), date(2026, 10, 20))
        self.assertEqual(reg, {})

    def test_calcola_scrive_json(self):
        d = S.calcola(self.dir, oggi=date(2026, 10, 30), titoli=self.el)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "pubblico", "satellite.json")))
        self.assertTrue(d["storico"])
        self.assertTrue(all(len(x) == 3 for x in d["storico"]))
        self.assertEqual(d["live"][0][1], 1.0 - S.COSTO)          # primo ingresso: costo dei 5 acquisti


class PortafogliConAzioni(unittest.TestCase):
    def test_serie_satellite_e_filtro_di_mercato(self):
        px = P.prezzi_demo("2003-01-01", "2010-12-31")
        sat = {"n": 5, "storico": [[ym, 0.01, ["X"]] for ym in _mesi("2005-02", "2010-12")], "live": [], "registro": {}}
        ss = P.serie_satellite(sat, [d for d, _ in px["SPY"]])
        self.assertAlmostEqual(ss[-1][1] / ss[0][1], 1.01 ** len(sat["storico"]), places=3)
        px["SAT"] = ss
        g = P.Griglia(px)
        prof = [p for p in P.PROFILI if p["id"] == "aggressivo"][0]
        i = P.date_ribilancio(g, "2008-01-01")[0]
        # SPY sotto la media: forziamo prezzi in calo per vedere la quota in liquidita'
        g.p["SPY"] = [100.0 * (0.999 ** k) for k in range(len(g.date))]
        pesi, info, esclusi = P.scegli(prof, g, i, {})
        self.assertNotIn("AZ", pesi)
        self.assertTrue(any(x["k"] == "AZ" for x in esclusi))
        g.p["SPY"] = [100.0 * (1.001 ** k) for k in range(len(g.date))]
        pesi, info, esclusi = P.scegli(prof, g, i, {})
        self.assertAlmostEqual(pesi["AZ"], prof["az"])
        self.assertAlmostEqual(sum(pesi.values()), 1.0, places=2)

    def test_senza_dati_azioni_quota_in_liquidita(self):
        px = P.prezzi_demo("2003-01-01", "2008-12-31")
        g = P.Griglia(px)
        prof = [p for p in P.PROFILI if p["id"] == "moderato"][0]
        pesi, _, esclusi = P.scegli(prof, g, P.date_ribilancio(g, "2007-01-01")[0], {})
        self.assertNotIn("AZ", pesi)
        self.assertGreaterEqual(pesi.get("CASH", 0), prof["az"])


if __name__ == "__main__":
    unittest.main()
