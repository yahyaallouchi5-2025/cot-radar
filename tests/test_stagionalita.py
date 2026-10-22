"""test_stagionalita.py - archivio permanente (mai riscritto, salti anomali scartati) e filtri della stagionalita'."""
import math
import os
import random
import shutil
import tempfile
import unittest
from datetime import date, timedelta

from cot_radar import stagionalita, storico


def serie(anni=25, seed=1, mese_buono=None, venerdi=0.0, sd=0.006):
    """Prezzi giornalieri finti: rumore puro, con eventuale mese in rialzo e venerdi' negativo."""
    rnd, v, pts = random.Random(seed), 100.0, []
    d = date(2025, 1, 1) - timedelta(days=365 * anni)
    while d < date(2025, 1, 1):
        if d.weekday() < 5:
            mu = (0.002 if d.month == mese_buono else 0) + (venerdi if d.weekday() == 4 else 0)
            v *= math.exp(mu + rnd.gauss(0, sd))
            pts.append([d.isoformat(), v])
        d += timedelta(days=1)
    return pts


class TestArchivio(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.base = serie(anni=3)
        self.scarica = lambda sid, inizio: [list(p) for p in self.base]

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_primo_download_e_aggiunta(self):
        arch, rie = storico.aggiorna({}, self.scarica, self.dir)
        n0 = len(arch["DEXUSEU"])
        nuovi = {"DEXUSEU": [["2025-01-02", self.base[-1][1] * 1.001], ["2025-01-03", self.base[-1][1] * 1.002]]}
        arch, rie = storico.aggiorna(nuovi, None, self.dir)        # niente download: solo giorni nuovi
        self.assertEqual(len(arch["DEXUSEU"]), n0 + 2)
        self.assertEqual(storico.leggi(self.dir, "DEXUSEU")[-1][0], "2025-01-03")

    def test_mai_riscritto(self):
        storico.aggiorna({}, self.scarica, self.dir)
        prima = storico.leggi(self.dir, "DEXUSEU")
        vecchio = {"DEXUSEU": [[prima[10][0], 999.0]]}            # dato "nuovo" con una data gia' salvata
        storico.aggiorna(vecchio, None, self.dir)
        self.assertEqual(storico.leggi(self.dir, "DEXUSEU"), prima)

    def test_salto_anomalo_scartato(self):
        storico.aggiorna({}, self.scarica, self.dir)
        u = self.base[-1][1]
        storico.aggiorna({"DEXUSEU": [["2025-01-02", u * 1.5]]}, None, self.dir)   # +50% in un giorno, non confermato
        self.assertEqual(storico.leggi(self.dir, "DEXUSEU")[-1][0], self.base[-1][0])

    def test_salto_vero_confermato(self):
        storico.aggiorna({}, self.scarica, self.dir)
        u = self.base[-1][1] * 1.2                                  # es. franco svizzero 2015: il livello resta
        storico.aggiorna({"DEXUSEU": [["2025-01-02", u], ["2025-01-03", u * 1.001], ["2025-01-06", u * 0.999]]},
                         None, self.dir)
        self.assertEqual(storico.leggi(self.dir, "DEXUSEU")[-1][0], "2025-01-06")

    def test_file_rovinato_non_toccato(self):
        storico.aggiorna({}, self.scarica, self.dir)
        f = os.path.join(self.dir, "DEXUSEU.csv")
        with open(f, "a") as fh:
            fh.write("riga,rotta,xx\n")
        arch, rie = storico.aggiorna({"DEXUSEU": [["2026-01-01", 1.0]]}, None, self.dir)
        self.assertNotIn("DEXUSEU", arch)
        self.assertIn("DEXUSEU", rie["problemi"])
        with open(f) as fh:
            self.assertIn("riga,rotta", fh.read())                 # nessuna sovrascrittura

    def test_download_sospetto_non_salvato(self):
        arch, rie = storico.aggiorna({}, lambda sid, i: self.base[:50], self.dir)
        self.assertIsNone(storico.leggi(self.dir, "DEXUSEU"))


class TestStagionalita(unittest.TestCase):
    def test_rumore_non_e_stagionale(self):
        """Su serie di puro rumore i filtri devono quasi sempre dire 'non affidabile'."""
        falsi = 0
        for seed in range(20):
            r = stagionalita.analizza(serie(seed=seed), oggi=date(2025, 3, 1))
            falsi += r["finestra"] is not None and r["finestra"]["robusto"]
            falsi += sum(g["robusto"] for g in r["giorni"])
        self.assertLessEqual(falsi, 3)                              # 20 serie x 6 test: al massimo qualche caso

    def test_mese_vero_trovato(self):
        r = stagionalita.analizza(serie(mese_buono=11), oggi=date(2025, 11, 1))
        self.assertTrue(r["mesi"][10]["robusto"])
        self.assertGreater(r["finestra"]["score"], 0)

    def test_venerdi_vero_trovato(self):
        r = stagionalita.analizza(serie(venerdi=-0.0015), oggi=date(2025, 3, 1))
        self.assertTrue(r["giorni"][4]["robusto"])
        self.assertLess(r["giorni"][4]["t"], 0)


if __name__ == "__main__":
    unittest.main()
