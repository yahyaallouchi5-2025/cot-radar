# -*- coding: utf-8 -*-
"""Test degli avvisi Telegram/e-mail (cot_radar/notifiche.py). Nessuna rete: l'invio e' sostituito.
Lancia: python -m unittest tests.test_notifiche -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import motore, notifiche, registro  # noqa: E402

ENV = {"TELEGRAM_BOT_TOKEN": "finto", "TELEGRAM_CHAT_ID": "@canale"}
ADESSO = datetime(2026, 10, 24, 23, 0, tzinfo=timezone.utc)


def apertura(s, quando, lab="BUY", **k):
    return dict({"tipo": "apertura", "id": f"{s}-{quando}", "strumento": s, "etichetta": lab,
                 "verso": motore.verso(lab), "punteggio": 30.0, "affid": "MEDIA", "perche": ["storico 61%"],
                 "generato": quando, "cot_data": "2026-10-20"}, **k)


class Avvisi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.inviati = []
        self.ok = True
        self._orig = notifiche.invia_telegram
        notifiche.invia_telegram = lambda token, chat, testo: (self.inviati.append(testo), self.ok)[1]

    def tearDown(self):
        notifiche.invia_telegram = self._orig
        shutil.rmtree(self.dir)

    def scrivi(self, eventi):
        registro._scrivi(self.dir, registro.concatena(eventi, registro.ZERO, 0))

    def aggiungi(self, nuovi):
        vecchi = registro.leggi(self.dir)
        _, ultimo, _ = registro.verifica(vecchi)
        registro._scrivi(self.dir, vecchi + registro.concatena(nuovi, ultimo, len(vecchi)))

    def test_primo_avvio_nessun_arretrato_poi_solo_il_nuovo(self):
        self.scrivi([apertura("GBPUSD", "2026-10-23T22:59Z", base="GBP", quote="USD")])
        r = notifiche.esegui(self.dir, "https://x.github.io/cot-radar/", ENV, ADESSO)
        self.assertEqual((r["esito"], self.inviati), ("primo_avvio", []))
        self.aggiungi([apertura("WTI", "2026-10-24T22:15Z", "STRONG SELL")])
        r = notifiche.esegui(self.dir, "https://x.github.io/cot-radar/", ENV, ADESSO)
        self.assertEqual(r["esito"], "inviato")
        self.assertEqual(len(self.inviati), 1)
        self.assertIn("Petrolio WTI", self.inviati[0])
        self.assertIn("STRONG SELL", self.inviati[0])
        self.assertNotIn("GBP/USD", self.inviati[0])
        self.assertIn("/cot-radar/#registro", self.inviati[0])
        # stesso giro ripetuto (tentativo 2 della sera): niente doppioni
        r = notifiche.esegui(self.dir, "", ENV, ADESSO)
        self.assertEqual((r["esito"], len(self.inviati)), ("niente_di_nuovo", 1))

    def test_telegram_giu_il_cursore_non_avanza(self):
        self.scrivi([apertura("GBPUSD", "2026-10-23T22:59Z")])
        notifiche.esegui(self.dir, "", ENV, ADESSO)
        self.aggiungi([apertura("SP500", "2026-10-24T22:15Z", "SELL")])
        self.ok = False
        self.assertEqual(notifiche.esegui(self.dir, "", ENV, ADESSO)["esito"], "telegram_errore")
        self.ok = True
        r = notifiche.esegui(self.dir, "", ENV, ADESSO)
        self.assertEqual(r["esito"], "inviato")
        self.assertIn("S&amp;P 500", self.inviati[-1])

    def test_eventi_troppo_vecchi_non_inviati(self):
        self.scrivi([apertura("GBPUSD", "2026-10-01T22:59Z")])
        notifiche.esegui(self.dir, "", ENV, ADESSO)
        self.aggiungi([apertura("DOW", "2026-10-20T22:15Z")])
        r = notifiche.esegui(self.dir, "", ENV, ADESSO)
        self.assertEqual((r["esito"], self.inviati), ("niente_di_nuovo", []))
        self.assertEqual(notifiche.leggi_cursore(self.dir)["ultimo_n"], 1)

    def test_testo_chiusura_figlio_e_conferme(self):
        padre = apertura("EURUSD", "2026-10-10T22:15Z", base="EUR", quote="USD")
        figlio = apertura("EURUSD", "2026-10-14T22:15Z", "STRONG BUY", base="EUR", quote="USD", padre=padre["id"])
        figlio["id"] += "-F"
        altro = apertura("GBPUSD", "2026-10-10T22:15Z", base="GBP", quote="USD")
        aperture = {e["id"]: e for e in (padre, figlio, altro)}
        q = "2026-10-24T22:15Z"
        nuovi = [{"tipo": "chiusura", "id": figlio["id"], "quando": q, "motivo": "inversione", "nuova": "SELL",
                  "punteggio": -25.0},
                 {"tipo": "chiusura", "id": padre["id"], "quando": q, "motivo": "inversione", "nuova": "SELL",
                  "punteggio": -25.0},
                 {"tipo": "conferma", "id": altro["id"], "quando": q, "cot_data": "2026-10-20", "etichetta": "BUY",
                  "punteggio": 31.0}]
        righe = notifiche.righe_eventi(nuovi, aperture)
        self.assertEqual(len(righe), 2)                                  # il figlio si chiude col padre
        self.assertIn("EUR/USD", righe[0])
        self.assertIn("si inverte", righe[0])
        self.assertIn("14 giorni (2 settimane)", righe[0])
        self.assertEqual(righe[1], "✓ Confermati dal nuovo COT: GBP/USD BUY")

    def test_messaggi_lunghi_divisi(self):
        blocchi = [f"▲ <b>X{i}</b>: " + "a" * 300 for i in range(30)]
        testi = notifiche.componi(blocchi, [{"quando": "2026-10-24T22:15Z"}], "https://x/")
        self.assertGreater(len(testi), 1)
        self.assertTrue(all(len(t) <= notifiche.LIMITE_TG for t in testi))
        self.assertEqual(sum(t.count("<b>X") for t in testi), 30)

    def test_senza_telegram_configurato_il_cursore_avanza(self):
        self.scrivi([apertura("GBPUSD", "2026-10-23T22:59Z")])
        notifiche.esegui(self.dir, "", {}, ADESSO)
        self.aggiungi([apertura("DOW", "2026-10-24T22:15Z")])
        r = notifiche.esegui(self.dir, "", {}, ADESSO)
        self.assertEqual((r["esito"], self.inviati), ("non_configurato", []))
        self.assertEqual(notifiche.leggi_cursore(self.dir)["ultimo_n"], 1)


if __name__ == "__main__":
    unittest.main()
