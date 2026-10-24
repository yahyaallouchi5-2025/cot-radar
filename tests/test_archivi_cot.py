# -*- coding: utf-8 -*-
"""Test degli archivi COT extra (storico.aggiorna_extra) e delle varianti del confronto (confronto.py).
Lancia: python -m unittest tests.test_archivi_cot -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import confronto, storico  # noqa: E402
from cot_radar.config import ARCHIVI_COT  # noqa: E402


def righe_tff(codici, settimane, dal=date(2006, 6, 13)):
    """Righe finte del report TFF: una per mercato e settimana (martedi')."""
    out = []
    for c in codici:
        for i in range(settimane):
            d = (dal + timedelta(weeks=i)).isoformat() + "T00:00:00.000"
            out.append({"cftc_contract_market_code": c, "report_date_as_yyyy_mm_dd": d, "open_interest_all": "1000",
                        "dealer_positions_long_all": "100", "dealer_positions_short_all": "200",
                        "asset_mgr_positions_long": str(300 + i), "asset_mgr_positions_short": "100",
                        "lev_money_positions_long": "50", "lev_money_positions_short": str(150 + i)})
    return out


class ArchivioExtra(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.chiamate = []
        self.min = ARCHIVI_COT["TFF"]["min"]
        ARCHIVI_COT["TFF"]["min"] = 100          # nei test bastano poche righe

    def tearDown(self):
        ARCHIVI_COT["TFF"]["min"] = self.min
        shutil.rmtree(self.dir)

    def scarica(self, righe):
        def f(inizio):
            self.chiamate.append(inizio)
            return [r for r in righe if r["report_date_as_yyyy_mm_dd"][:10] >= inizio]
        return f

    def test_crea_poi_aggiunge_solo_il_nuovo(self):
        tutte = righe_tff(["099741", "096742"], 60)
        primo, rie = storico.aggiorna_extra("TFF", self.scarica(tutte[:50] + tutte[60:110]), self.dir,
                                            oggi=date(2007, 7, 1))
        self.assertEqual(rie["stato"], "creato")
        self.assertEqual(len(primo), 100)
        self.assertEqual(self.chiamate, ["2006-01-01"])
        # settimana nuova: una sola richiesta piccola, dal giorno dopo l'ultima salvata
        ultima = max(r["report_date_as_yyyy_mm_dd"][:10] for r in primo)
        oggi = date.fromisoformat(ultima) + timedelta(days=storico.ATTESA_NUOVO + 7)
        dopo, rie = storico.aggiorna_extra("TFF", self.scarica(tutte), self.dir, oggi=oggi)
        self.assertEqual(self.chiamate[-1], (date.fromisoformat(ultima) + timedelta(days=1)).isoformat())
        self.assertEqual(rie["nuove"], 20)
        self.assertEqual(len(dopo), 120)
        self.assertEqual(dopo, [dict(r, report_date_as_yyyy_mm_dd=r["report_date_as_yyyy_mm_dd"][:10])
                                for r in sorted(tutte, key=lambda r: (r["cftc_contract_market_code"],
                                                                      r["report_date_as_yyyy_mm_dd"]))])

    def test_nessuna_richiesta_se_non_puo_esserci_un_report_nuovo(self):
        tutte = righe_tff(["099741"], 120)
        storico.aggiorna_extra("TFF", self.scarica(tutte), self.dir, oggi=date(2008, 9, 30))
        ultima = date.fromisoformat(max(r["report_date_as_yyyy_mm_dd"][:10] for r in tutte))
        storico.aggiorna_extra("TFF", self.scarica(tutte), self.dir, oggi=ultima + timedelta(days=4))
        self.assertEqual(len(self.chiamate), 1)

    def test_download_sospetto_non_salvato(self):
        _, rie = storico.aggiorna_extra("TFF", self.scarica(righe_tff(["099741"], 10)), self.dir)
        self.assertEqual(rie["stato"], "assente")
        self.assertFalse(os.path.exists(os.path.join(self.dir, ARCHIVI_COT["TFF"]["file"])))

    def test_righe_impossibili_scartate_e_storico_mai_riscritto(self):
        tutte = righe_tff(["099741"], 120)
        tutte[5]["lev_money_positions_long"] = "-3"                  # posizione negativa: impossibile
        tutte[6]["open_interest_all"] = "0"                          # mercato vuoto: scartato
        primo, _ = storico.aggiorna_extra("TFF", self.scarica(tutte), self.dir, oggi=date(2008, 9, 30))
        self.assertEqual(len(primo), 118)
        # la CFTC "corregge" una settimana gia' salvata: l'archivio NON la riscrive
        cambiata = [dict(r) for r in tutte]
        cambiata[10]["asset_mgr_positions_long"] = "999999"
        dopo, _ = storico.aggiorna_extra("TFF", self.scarica(cambiata), self.dir, oggi=date(2009, 9, 30))
        self.assertEqual(dopo[8]["asset_mgr_positions_long"], primo[8]["asset_mgr_positions_long"])

    def test_errore_di_rete_non_rompe_niente(self):
        def guasto(inizio):
            raise OSError("rete giu'")
        righe, rie = storico.aggiorna_extra("TFF", guasto, self.dir)
        self.assertEqual((righe, rie["stato"]), ([], "assente"))


class Varianti(unittest.TestCase):
    def test_leveraged_funds_al_posto_degli_speculatori(self):
        base = [{"cftc_contract_market_code": "099741", "report_date_as_yyyy_mm_dd": "2010-01-05", "open_interest_all": "900",
                 "noncomm_positions_long_all": "1", "noncomm_positions_short_all": "2",
                 "comm_positions_long_all": "7", "comm_positions_short_all": "3"},
                {"cftc_contract_market_code": "067651", "report_date_as_yyyy_mm_dd": "2010-01-05", "open_interest_all": "500",
                 "noncomm_positions_long_all": "40", "noncomm_positions_short_all": "20",
                 "comm_positions_long_all": "5", "comm_positions_short_all": "5"}]
        tff = [{"cftc_contract_market_code": "099741", "report_date_as_yyyy_mm_dd": "2010-01-05", "open_interest_all": "1000",
                "lev_money_positions_long": "50", "lev_money_positions_short": "150",
                "asset_mgr_positions_long": "300", "asset_mgr_positions_short": "100"}]
        v = confronto.variante(base, tff, "lev")
        eur = [r for r in v if r["cftc_contract_market_code"] == "099741"][0]
        wti = [r for r in v if r["cftc_contract_market_code"] == "067651"][0]
        self.assertEqual((eur["noncomm_positions_long_all"], eur["noncomm_positions_short_all"]), (50.0, 150.0))
        self.assertEqual(eur["open_interest_all"], 1000.0)
        self.assertEqual((eur["comm_positions_long_all"], eur["comm_positions_short_all"]), ("7", "3"))  # Commercials: Legacy
        self.assertEqual(wti, base[1])                                    # mercato senza TFF: resta come oggi
        self.assertEqual(confronto.mercati_variante(base, tff), {"099741"})

    def test_differenza_opzioni(self):
        fo = [{"cftc_contract_market_code": "088691", "report_date_as_yyyy_mm_dd": "2010-01-05", "open_interest_all": "100",
               "noncomm_positions_long_all": "60", "noncomm_positions_short_all": "10"}]
        co = [{"cftc_contract_market_code": "088691", "report_date_as_yyyy_mm_dd": "2010-01-05", "open_interest_all": "125",
               "noncomm_positions_long_all": "65", "noncomm_positions_short_all": "30"}]
        d = confronto.diff_opzioni(fo, co)
        self.assertAlmostEqual(d["088691"]["2010-01-05"], 28.0 - 50.0)    # netto %OI con opzioni - senza


if __name__ == "__main__":
    unittest.main()
