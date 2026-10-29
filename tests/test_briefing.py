# -*- coding: utf-8 -*-
"""Test del briefing del lunedi' e del racconto breve del venerdi' (briefing.py, riepilogo.py, notifiche.py).
Nessuna rete. Lancia: python -m unittest tests.test_briefing -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import briefing, notifiche, registro, riepilogo  # noqa: E402

ENV = {"TELEGRAM_BOT_TOKEN": "finto", "TELEGRAM_CHAT_ID": "@canale"}


def dati():
    """Dati minimi della pagina, con un nome che richiede l'escape HTML (S&P 500)."""
    a = lambda k, g, lab, sc, **x: dict({"key": k, "it": k, "group": g, "label": lab, "score": sc, "idx": 90,
                                         "d_net": 1200, "crowded": False, "date": "2026-10-20"}, **x)
    return {"meta": {"normal": 25}, "assets": {
        "USD": a("USD", "Valute", "NEUTRO", 0, idx=50), "EUR": a("EUR", "Valute", "NEUTRO", -10, idx=8, d_net=0),
        "SP500": a("SP500", "Indici azionari", "BUY", 44.1, it="S&P 500", crowded=True)},
        "pairs": [{"base": "EUR", "quote": "USD", "label": "SELL", "score": -31.0, "new": True}],
        "market": {"drivers": [{"key": "vix", "value": 17.4, "d4": 1.9}, {"key": "hy", "value": 3.07, "d4": -16.0}]},
        "fed": {"regime": "QT (bilancio in riduzione)", "bs13": -2.7},
        "vol": {"EURUSD": {"prezzo": 1.1, "settimane": {"media": 1.0}}},
        "port": {"prossima": "2026-11-02", "rotazione": "2026-10-01", "profili": [
            {"id": "moderato", "nome": "Moderato", "base": [{"k": "US10Y", "nome": "Treasury 10 anni"}],
             "composizione": [{"k": "SP500", "nome": "S&P 500", "peso": 30, "trend": 6.0},
                              {"k": "EAFE", "nome": "Europa", "peso": 10, "trend": 0.8},
                              {"k": "CASH", "nome": "Liquidita", "peso": 60, "trend": None}],
             "esclusi": [{"k": "US10Y", "trend": -4.2, "base": 24}]}]},
        "eventi": [{"quando": "2026-10-28 19:00", "nome": "Fed (FOMC)", "valuta": "USD", "tipo": "banca"}]}


class Briefing(unittest.TestCase):
    def test_sezioni_semaforo_escape_e_limite(self):
        t = briefing.testi(dati(), "https://x.github.io/cot-radar/", datetime(2026, 10, 26, 6, 0))
        testo = "\n".join(t)
        for s in ("COSA MONITORARE", "MESSAGGIO CHIAVE", "FOREX UPDATE", "BANCHE CENTRALI", "ALTRI MERCATI"):
            self.assertIn(s, testo)
        self.assertIn("🟢 S&amp;P 500", testo)             # sopra la media
        self.assertIn("🟡 Europa", testo)                  # vicino alla media
        self.assertIn("🔴 Treasury 10 anni", testo)        # in pausa
        self.assertNotIn("S&P 500 BUY", testo.replace("S&amp;P 500 BUY", ""))     # niente & grezzo
        self.assertIn("non una previsione", testo)         # i livelli sono ampiezze tipiche, mai previsioni
        self.assertTrue(all(len(m) < 4096 for m in t))
        self.assertIn("non consulenza", testo)

    def test_dato_mancante_nessun_crash(self):
        t = briefing.testi({"assets": {}}, "", datetime(2026, 10, 26, 6, 0))
        self.assertTrue(t and "BoardEdge" in t[0])


class Cursore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.inviati = []
        self._orig = notifiche.invia_telegram
        notifiche.invia_telegram = lambda token, chat, testo: (self.inviati.append(testo), True)[1]
        registro._scrivi(self.dir, registro.concatena([], registro.ZERO, 0))

    def tearDown(self):
        notifiche.invia_telegram = self._orig
        shutil.rmtree(self.dir)

    def giro(self, quando):
        return notifiche.esegui(self.dir, "https://x.github.io/cot-radar/", ENV, quando, dati_sito=dati())

    def test_un_solo_briefing_a_settimana(self):
        dom = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)
        self.giro(dom)                                                 # primo avvio: nessun arretrato
        self.assertEqual(self.inviati, [])
        self.giro(datetime(2026, 10, 26, 4, 0, tzinfo=timezone.utc))   # lunedi' presto: troppo presto
        self.assertEqual(self.inviati, [])
        self.giro(datetime(2026, 10, 26, 5, 40, tzinfo=timezone.utc))  # lunedi' mattina: parte
        n = len(self.inviati)
        self.assertGreaterEqual(n, 1)
        self.assertTrue(any("briefing" in t for t in self.inviati))
        self.giro(datetime(2026, 10, 26, 22, 15, tzinfo=timezone.utc))  # stesso lunedi' sera: niente doppioni
        self.assertEqual(len(self.inviati), n)
        self.giro(datetime(2026, 10, 27, 5, 40, tzinfo=timezone.utc))   # martedi' stessa settimana: niente
        self.assertEqual(len(self.inviati), n)
        self.giro(datetime(2026, 11, 2, 5, 40, tzinfo=timezone.utc))    # lunedi' dopo: parte di nuovo
        self.assertGreater(len(self.inviati), n)


class Venerdi(unittest.TestCase):
    def test_racconto_breve_e_andamento(self):
        d = dati()
        d["assets"]["SP500"]["new"] = True
        reg = {"aperti": [{"iniziale": False, "m": {"A": {"fine": {"vinto": True}}}},
                          {"iniziale": False, "m": {"A": {"fine": {"vinto": False}}}}], "chiusi": []}
        t = "\n".join(riepilogo.testi(d, "https://x.github.io/cot-radar/", verifica=reg))
        self.assertIn("In breve", t)
        self.assertIn("1 su 2 in guadagno", t)
        self.assertIn("Prossima rotazione", t)
        self.assertEqual(riepilogo.andamento(None), None)


if __name__ == "__main__":
    unittest.main()


class TolleranzaFed(unittest.TestCase):
    """v6.49: subito dopo le 16:30 di New York del giovedi' il bilancio Fed non ancora su FRED NON e' un ritardo."""
    def _con_ora(self, ora):
        from datetime import datetime
        from cot_radar import calendario as c
        vecchio = c.utcnow
        c.utcnow = lambda: ora
        try:
            return c.weekly_schedule("2026-10-21", 3, 16, 30, 1, tolleranza_ore=18)
        finally:
            c.utcnow = vecchio

    def test_appena_uscito_non_e_ritardo(self):
        from datetime import datetime
        r = self._con_ora(datetime(2026, 10, 29, 21, 0))        # 30 minuti dopo l'uscita
        self.assertFalse(r["late"])
        self.assertEqual(r["expected"], "2026-10-21")

    def test_il_giorno_dopo_e_ritardo(self):
        from datetime import datetime
        r = self._con_ora(datetime(2026, 10, 30, 16, 0))        # oltre 18 ore dopo
        self.assertTrue(r["late"])
        self.assertEqual(r["expected"], "2026-10-28")
