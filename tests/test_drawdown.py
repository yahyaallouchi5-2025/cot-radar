# -*- coding: utf-8 -*-
"""Test dello studio del drawdown (motore.drawdown) e del calendario degli annunci (eventi.py).
Lancia: python -m unittest tests.test_drawdown -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import eventi, motore  # noqa: E402


def trade(percorso, tip=1.0, prezzo=1.2, date=None, E=None):
    """Misura finta: percorso = risultati giornalieri in % (nel verso del segnale)."""
    G, mx, mn = [], 0.0, 0.0
    for r in percorso:
        mx, mn = max(mx, r), min(mn, r)
        G.append([r, mx, mn])
    m = {"stato": "ok", "ingresso": {"data": "2024-01-01", "prezzo": prezzo}, "tip": tip, "G": G,
         "Gd": date or [f"2024-01-{d + 2:02d}" for d in range(len(G))], "cls": "fx",
         "A": {"fine": {"mae": mn, "mfe": mx, "res": percorso[-1]}}}
    if E is not None:
        m["E"] = E
    return ({"strumento": "EURUSD"}, m, 0.0)


class Drawdown(unittest.TestCase):
    def riga(self, misurati, k, u=None):
        return dict(zip(motore.DD_CAMPI, motore.drawdown(misurati, u)[k - 1]))

    def test_mediana_brutto_e_volatilita(self):
        # 10 trade: il drawdown massimo dopo 3 giorni va da -0,5% a -5%
        m = [trade([-0.5 * i, 0.0, 0.0], tip=2.0) for i in range(1, 11)]
        r = self.riga(m, 3)
        self.assertEqual(r["n"], 10)
        self.assertAlmostEqual(r["mae50"], -2.75)            # mediana di -0,5..-5
        self.assertAlmostEqual(r["mae90"], -4.55)            # 1 su 10 va peggio
        self.assertAlmostEqual(r["v50"], 1.38, places=2)     # 2,75% / 2% di settimana tipica
        self.assertEqual(r["h1"] + r["h2"] + r["h3"] + r["h4"], 100)
        self.assertEqual(r["gmin"], 1)                        # il punto peggiore e' sempre il primo giorno

    def test_punti_pip(self):
        r = self.riga([trade([-1.0], prezzo=1.2)], 1, ("pip", 0.0001))
        self.assertAlmostEqual(r["p50"], 120.0)               # 1% di 1,2000 = 0,0120 = 120 pip

    def test_guadagno_prima_del_drawdown(self):
        prima = trade([1.0, -2.0])          # sale il primo giorno, poi scende: guadagno prima
        dopo = trade([-1.0, 2.0])           # scende e poi sale: drawdown prima
        self.assertEqual(self.riga([prima], 2)["prima"], 100)
        self.assertEqual(self.riga([dopo], 2)["prima"], 0)

    def test_giorno_peggiore_su_annuncio(self):
        # giorno peggiore = il secondo (da +0,5 a -1,5); il secondo giorno ha un annuncio
        m = trade([0.5, -1.5, -1.0], E=[False, True, False])
        r = self.riga([m], 3)
        self.assertEqual(r["pg"], 100)
        self.assertEqual(r["pa"], 33)                         # 1 giorno su 3 con annuncio: atteso per caso
        self.assertEqual((r["ev_n"], r["no_n"]), (1, 0))

    def test_al_cambio_segnale_senza_percorso(self):
        r = dict(zip(motore.DD_CAMPI, motore.drawdown([trade([-1.0, 1.0])])[20]))
        self.assertEqual(r["n"], 1)
        self.assertIsNone(r["gmin"])


class Calendario(unittest.TestCase):
    def test_ora_di_chiusura(self):
        """La Fed (14:00 NY) arriva DOPO la chiusura dei cambi (12:00): conta il giorno dopo; per gli indici
        (chiusura 16:00) conta lo stesso giorno. NFP alle 8:30: stesso giorno per tutti."""
        c = eventi.Calendario([("2024-01-03", 14.0, "FOMC"), ("2024-01-05", 8.5, "NFP")])
        giorni = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        self.assertEqual(c.giorni("2024-01-01", giorni, "fx"), [False, False, True, True])
        self.assertEqual(c.giorni("2024-01-01", giorni, "indici"), [False, True, False, True])

    def test_file_storico(self):
        c = eventi.Calendario()
        nomi = {n for _, _, n in c.lista}
        self.assertEqual(nomi, {"NFP", "CPI", "FOMC"})
        self.assertLess(c.lista[0][0], "1986-01-01")
        self.assertGreater(len(c.lista), 1200)


if __name__ == "__main__":
    unittest.main()
