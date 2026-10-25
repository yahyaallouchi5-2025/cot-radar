# -*- coding: utf-8 -*-
"""Test delle statistiche anonime (web/statistiche.js inserito da pagina.statistiche()). Nessuna rete.
Lancia: python -m unittest tests.test_statistiche -v"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import pagina, vetrina  # noqa: E402


class Statistiche(unittest.TestCase):
    def test_id_vuoto_statistiche_spente(self):
        with mock.patch.object(pagina, "STATISTICHE_ID", ""):
            js = pagina.statistiche()
        self.assertIn('var ID="";', js)                    # nessun ID: lo script di Umami non si carica
        self.assertNotIn("__STAT_ID__", js)

    def test_id_inserito_e_ripulito(self):
        with mock.patch.object(pagina, "STATISTICHE_ID", "1a2b-3c4d\";alert(1)//"):
            js = pagina.statistiche()
        self.assertIn('var ID="1a2b-3c4dalert1";', js)     # solo lettere, cifre e trattini: niente codice iniettato

    def test_presenti_in_terminale_e_landing(self):
        self.assertIn("window.ebStat", pagina.template())
        html = vetrina.html({"data": {"assets": {}, "pairs": []}})
        self.assertIn("window.ebStat", html)
        self.assertNotIn("{{", html)                       # nessun segnaposto rimasto
        self.assertIn('data-ev-vista="vantaggio"', html)


if __name__ == "__main__":
    unittest.main()
