"""test_admin.py - il registro cifrato si decifra solo con la password giusta; lo stato pubblico non ha messaggi."""
import base64
import json
import unittest

from cot_radar import admin


class TestAdmin(unittest.TestCase):
    def test_pubblico_senza_messaggi(self):
        s = admin.pubblico({"creato": "x", "esito": "critico", "fonti": {"fred": "online"}, "voci": [1], "critici": ["a"]})
        self.assertNotIn("voci", s)
        self.assertNotIn("critici", s)
        self.assertEqual(s["esito"], "parziale")      # il dettaglio "critico" lo vede solo l'admin

    def test_senza_password_niente_registro(self):
        self.assertIsNone(admin.cifra({"a": 1}, ""))

    def test_cifra_e_decifra(self):
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except ImportError:
            self.skipTest("libreria cryptography non installata")
        blob = admin.cifra({"voci": ["segreto"]}, "pw")
        d = lambda k: base64.b64decode(blob[k])
        chiave = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=d("salt"), iterations=blob["iter"]).derive(b"pw")
        self.assertEqual(json.loads(AESGCM(chiave).decrypt(d("iv"), d("ct"), None)), {"voci": ["segreto"]})
        self.assertNotIn("segreto", json.dumps(blob))   # in chiaro non c'e'


if __name__ == "__main__":
    unittest.main()
