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
        r = notifiche.esegui(self.dir, "https://x.github.io/cot-radar/", ENV, ADESSO, dati_sito={})
        self.assertEqual((r["esito"], self.inviati), ("primo_avvio", []))
        self.aggiungi([apertura("WTI", "2026-10-24T22:15Z", "STRONG SELL")])
        r = notifiche.esegui(self.dir, "https://x.github.io/cot-radar/", ENV, ADESSO, dati_sito={})
        self.assertEqual(r["esito"], "inviato")
        self.assertEqual(len(self.inviati), 1)
        self.assertIn("Petrolio WTI", self.inviati[0])
        self.assertIn("STRONG SELL", self.inviati[0])
        self.assertNotIn("GBP/USD", self.inviati[0])
        self.assertIn("/cot-radar/#registro", self.inviati[0])
        self.assertNotIn("affid", self.inviati[0].lower())                    # mai l'affidabilita' su Telegram
        # stesso giro ripetuto (tentativo 2 della sera): niente doppioni
        r = notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
        self.assertEqual((r["esito"], len(self.inviati)), ("niente_di_nuovo", 1))

    def test_telegram_giu_il_cursore_non_avanza(self):
        self.scrivi([apertura("GBPUSD", "2026-10-23T22:59Z")])
        notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
        self.aggiungi([apertura("SP500", "2026-10-24T22:15Z", "SELL")])
        self.ok = False
        self.assertEqual(notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})["esito"], "telegram_errore")
        self.ok = True
        r = notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
        self.assertEqual(r["esito"], "inviato")
        self.assertIn("S&amp;P 500", self.inviati[-1])

    def test_eventi_troppo_vecchi_non_inviati(self):
        self.scrivi([apertura("GBPUSD", "2026-10-01T22:59Z")])
        notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
        self.aggiungi([apertura("DOW", "2026-10-20T22:15Z")])
        r = notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
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
        notifiche.esegui(self.dir, "", {}, ADESSO, dati_sito={})
        self.aggiungi([apertura("DOW", "2026-10-24T22:15Z")])
        r = notifiche.esegui(self.dir, "", {}, ADESSO, dati_sito={})
        self.assertEqual((r["esito"], self.inviati), ("non_configurato", []))
        self.assertEqual(notifiche.leggi_cursore(self.dir)["ultimo_n"], 1)


def dashboard(cot, **segnali):
    """Dati finti della pagina: coppie EUR/USD e GBP/USD + gli strumenti indicati {chiave: (etichetta, prima)}."""
    assets = {"EUR": {"group": "Valute", "label": "NEUTRO", "date": cot},
              "GBP": {"group": "Valute", "label": "SELL", "date": cot},
              "GOLD": {"group": "Metalli", "label": "NEUTRO", "date": cot, "it": "Oro"}}
    for k, (lab, prima) in segnali.items():
        assets[k] = {"group": "Energia", "label": lab, "prev_label": prima, "score": -40.0 if "SELL" in lab else 40.0,
                     "new": lab != prima, "date": cot, "it": k.title()}
    pairs = [{"base": "EUR", "quote": "USD", "label": "BUY", "score": 31.0, "new": True, "prev": "NEUTRO"},
             {"base": "GBP", "quote": "USD", "label": "NEUTRO", "score": 3.0, "new": True, "prev": "SELL"},
             {"base": "GOLD", "quote": "USD", "label": "SELL", "score": -30.0, "prev": "SELL"}]
    return {"assets": assets, "pairs": pairs}


class Settimanale(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.inviati = []
        self._orig = notifiche.invia_telegram
        notifiche.invia_telegram = lambda token, chat, testo: (self.inviati.append(testo), True)[1]
        registro._scrivi(self.dir, registro.concatena([apertura("WTI", "2026-10-16T21:05Z", "SELL")], registro.ZERO, 0))

    def tearDown(self):
        notifiche.invia_telegram = self._orig
        shutil.rmtree(self.dir)

    def test_riepilogo_solo_con_un_cot_nuovo(self):
        d13 = dashboard("2026-10-13", WTI=("SELL", "SELL"))
        notifiche.esegui(self.dir, "https://x/", ENV, ADESSO, dati_sito=d13)          # primo avvio
        self.assertEqual(notifiche.leggi_cursore(self.dir)["riepilogo_cot"], "2026-10-13")
        r = notifiche.esegui(self.dir, "https://x/", ENV, ADESSO, dati_sito=d13)      # stesso COT: niente
        self.assertEqual((r["esito"], self.inviati), ("niente_di_nuovo", []))
        d20 = dashboard("2026-10-20", WTI=("STRONG SELL", "SELL"), NATGAS=("NEUTRO", "SELL"))
        r = notifiche.esegui(self.dir, "https://x/", ENV, ADESSO, dati_sito=d20)      # venerdi': COT nuovo
        self.assertEqual((r["esito"], r["tipo"]), ("inviato", "settimanale"))
        t = self.inviati[0]
        self.assertIn("segnali della settimana", t)
        self.assertIn("COT del 20/10/2026", t)
        self.assertNotIn("affid", t.lower())
        self.assertLess(t.index("<b>FOREX</b>"), t.index("<b>ENERGIA</b>"))           # Forex per primo
        self.assertIn("EUR/USD: <b>BUY</b> +31.0", t)
        self.assertIn("Wti: <b>STRONG SELL</b>", t)
        self.assertNotIn("GOLD/USD", t)                                               # metalli fuori dal Forex
        self.assertIn("■ GBP/USD: era SELL, ora NEUTRO", t)
        self.assertIn("■ Natgas: era SELL, ora NEUTRO", t)
        self.assertEqual(notifiche.leggi_cursore(self.dir)["riepilogo_cot"], "2026-10-20")
        notifiche.esegui(self.dir, "https://x/", ENV, ADESSO, dati_sito=d20)          # giro dopo: niente doppioni
        self.assertEqual(len(self.inviati), 1)

    def test_sito_non_raggiungibile_riepilogo_rimandato(self):
        notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito=dashboard("2026-10-13"))
        r = notifiche.esegui(self.dir, "", ENV, ADESSO, dati_sito={})
        self.assertEqual(r["tipo"], "eventi")
        self.assertEqual(notifiche.leggi_cursore(self.dir)["riepilogo_cot"], "2026-10-13")

    def test_prova_manda_il_riepilogo_marcato_test_senza_toccare_il_cursore(self):
        r = notifiche.prova("https://x/", ENV, dati_sito=dashboard("2026-10-20", WTI=("SELL", "SELL")))
        self.assertTrue(r["telegram"])
        self.assertTrue(self.inviati[0].startswith("[TEST] <b>Edge Board · segnali della settimana"))
        self.assertIsNone(notifiche.leggi_cursore(self.dir))


if __name__ == "__main__":
    unittest.main()
