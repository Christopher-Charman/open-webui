"""Signed public bootstrap must not expose process identity."""
import importlib.util
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519

spec = importlib.util.spec_from_file_location("owned_daemon", Path(__file__).resolve().parents[1] / "daemon.py")
daemon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon)

class TestPublicIdentityPrivacy(unittest.TestCase):
    def setUp(self):
        self.x = x25519.X25519PrivateKey.generate()
        self.s = ed25519.Ed25519PrivateKey.generate()
        self.data = daemon._identity_payload(self.x, self.s, 100, 200)
    def test_no_os_identity(self):
        for field in ("user", "uid", "hostname"):
            self.assertNotIn(field, self.data)
    def test_crypto_discovery_and_signature(self):
        self.assertEqual(self.data["runtime_id"], daemon.RUNTIME_ID)
        self.assertEqual(self.data["protocol"], daemon.PROTOCOL)
        self.assertEqual(self.data["heartbeat_at"], 200)
        self.assertTrue(self.data["identity_fingerprint"].startswith("SHA256:"))
        self.assertTrue(self.data["x25519_spki_b64"])
        self.assertTrue(self.data["ed25519_spki_b64"])
        message = daemon._canon(self.data)
        self.s.public_key().verify(self.s.sign(message), message)
    def test_tool_and_state_contract(self):
        self.assertEqual(self.data["state"], "ready")
        self.assertEqual(set(self.data["tool_contract"]), daemon.ALLOWED_TOOLS)

if __name__ == "__main__":
    unittest.main()
