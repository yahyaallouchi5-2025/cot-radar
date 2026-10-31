# -*- coding: utf-8 -*-
"""Test dei bilanci SEC (cot_radar/fondamentali.py). Nessuna rete: "companyfacts" finti nel formato della SEC.
Lancia: python -m unittest tests.test_fondamentali -v"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cot_radar import fondamentali as F  # noqa: E402


def fatto(anno, val, durata=True, filed=None, fp="FY", form="10-K"):
    f = {"end": f"{anno}-12-31", "val": val, "fp": fp, "form": form, "filed": filed or f"{anno + 1}-02-15"}
    if durata:
        f["start"] = f"{anno}-01-01"
    return f


def azienda(utili, debito=100, cassa=50, pn=500):
    anni = range(2020, 2020 + len(utili))
    return {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [fatto(a, 1000 + 100 * i) for i, a in enumerate(anni)]
                               + [fatto(2023, 999, fp="Q3", form="10-Q")]}},        # trimestrale: va ignorata
        "NetIncomeLoss": {"units": {"USD": [fatto(a, u) for a, u in zip(anni, utili)]}},
        "LongTermDebt": {"units": {"USD": [fatto(a, debito, False) for a in anni]}},
        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [fatto(a, cassa, False) for a in anni]}},
        "StockholdersEquity": {"units": {"USD": [fatto(a, pn, False) for a in anni]}},
    }}}


class Bilanci(unittest.TestCase):
    def test_solida(self):
        s = F.estrai(azienda([50, 60, 70, 80, 90]))
        self.assertEqual(len(s["anni"]), 5)
        self.assertEqual(s["perdite"], 0)
        self.assertEqual(s["giudizio"], "SOLIDA")
        self.assertEqual(s["anni"][-1]["dn"], 50)
        self.assertAlmostEqual(s["crescita"], 8.8, places=1)

    def test_solida_senza_debito_dichiarato(self):
        # bug del primo giro live: debito e cassa assenti (dn = None) facevano crollare tutto il giro dei bilanci
        a = azienda([50, 60, 70, 80, 90])
        for k in ("LongTermDebt", "CashAndCashEquivalentsAtCarryingValue"):
            del a["facts"]["us-gaap"][k]
        s = F.estrai(a)
        self.assertEqual(s["giudizio"], "SOLIDA")
        self.assertIn("non indicato", s["motivo"])

    def test_perdite_e_indebitata(self):
        s = F.estrai(azienda([50, -20, 10, -5, 5], debito=2000, cassa=10))
        self.assertEqual(s["perdite"], 2)
        self.assertEqual(s["giudizio"], "INDEBITATA")
        s = F.estrai(azienda([50, 60, 70, 80, 90], pn=-10))
        self.assertEqual(s["giudizio"], "INDEBITATA")

    def test_correzione_vince_il_deposito_piu_recente(self):
        a = azienda([50, 60, 70, 80, 90])
        a["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"].append(fatto(2024, 95, filed="2026-03-01"))
        self.assertEqual(F.estrai(a)["anni"][-1]["utile"], 95)

    def test_giro_senza_contatto_non_scarica(self):
        os.environ.pop("SEC_CONTATTO", None)
        d = tempfile.mkdtemp()
        try:
            self.assertTrue(F.aggiorna(d, el=[])["saltato"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_giro_completo_con_download_finto(self):
        d = tempfile.mkdtemp()
        try:
            el = [{"t": "AAA", "nome": "A", "s": "tech", "l": ["sp500"]}, {"t": "BBB.MI", "nome": "B", "s": "fin", "l": ["mib"]}]
            finto = lambda url: {"AAA": 1} if url == "CIK" else azienda([50, 60, 70, 80, 90])
            r = F.aggiorna(d, oggi=date(2026, 10, 27), el=el, scarica=finto, pausa=0)
            self.assertEqual(r["ok"], 1)                         # il titolo italiano non e' USA: escluso
            self.assertTrue(os.path.exists(os.path.join(d, "pubblico", "bilanci", "AAA.json")))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


# --------------------------------------------------------------------------- v6.54: trimestrali e date dei conti
def periodo(ini, fine, val, form="10-Q", filed="2026-01-01"):
    return {"start": ini, "end": fine, "val": val, "form": form, "filed": filed, "fp": "Q"}


class Trimestrali(unittest.TestCase):
    def fatti(self):
        q = [periodo("2025-01-01", "2025-03-31", 100), periodo("2025-04-01", "2025-06-30", 110),
             periodo("2025-07-01", "2025-09-30", 120), periodo("2025-01-01", "2025-12-31", 460, "10-K"),
             periodo("2025-01-01", "2025-06-30", 210),                       # cumulato semestrale: va ignorato
             periodo("2026-01-01", "2026-03-31", 130)]
        u = [dict(x, val=x["val"] / 10) for x in q]
        e = [dict(x, val=x["val"] / 100) for x in q]
        return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": q}}, "NetIncomeLoss": {"units": {"USD": u}},
                                      "EarningsPerShareDiluted": {"units": {"USD/shares": e}}}}}

    def test_quarto_trimestre_ricavato(self):
        t = F.trimestri(self.fatti())
        self.assertEqual([x["fine"] for x in t], ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"])
        q4 = t[3]
        self.assertEqual(q4["ricavi"], 130)                 # 460 - 100 - 110 - 120
        self.assertEqual(q4["ini"], "2025-10-01")
        self.assertTrue(q4["r4"])
        self.assertFalse(t[0]["r4"])
        self.assertEqual(t[0]["eps"], 1.0)

    def test_date_dei_conti(self):
        dep = {"filings": {"recent": {"form": ["8-K", "8-K", "10-Q", "8-K", "8-K"],
                                      "filingDate": ["2026-10-30", "2026-07-31", "2026-08-01", "2025-10-30", "2026-05-02"],
                                      "items": ["2.02,9.01", "2.02", "", "2.02", "5.07"]}}}
        c = F.conti(dep, date(2026, 10, 31))
        self.assertEqual(c["ultimo"], "2026-10-30")
        self.assertEqual(c["prossimo"], "2027-01-29")       # niente 8-K 2.02 di gennaio: ultimo + 91 giorni
        self.assertIsNone(F.conti({}, date(2026, 10, 31)))
