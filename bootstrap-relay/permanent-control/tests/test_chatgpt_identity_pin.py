import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519


CONTROL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("origin_client", CONTROL / "origin-client.py")
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


def signed_identity():
    signing = ed25519.Ed25519PrivateKey.generate()
    encryption = x25519.X25519PrivateKey.generate()
    def der(key):
        return key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    xder, eder = der(encryption), der(signing)
    fingerprint = "SHA256:" + base64.b64encode(
        hashlib.sha256(xder + eder).digest()).decode().rstrip("=")
    identity = {
        "protocol": CLIENT.PROTOCOL, "version": CLIENT.VERSION,
        "runtime_id": CLIENT.RUNTIME_ID,
        "x25519_spki_b64": CLIENT.b64e(xder),
        "ed25519_spki_b64": CLIENT.b64e(eder),
        "identity_fingerprint": fingerprint,
    }
    identity["signature_b64"] = CLIENT.b64e(signing.sign(CLIENT.canon(identity)))
    return identity, fingerprint


class ChatGPTIdentityPinTests(unittest.TestCase):
    def test_matching_pin_accepts_signed_identity(self):
        identity, fingerprint = signed_identity()
        self.assertEqual(CLIENT.validate_identity(identity, fingerprint)[2], fingerprint)

    def test_replacement_self_signed_identity_rejected_before_queue_access(self):
        identity, _ = signed_identity()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control = root / "bootstrap-relay/permanent-control"
            control.mkdir(parents=True)
            for name in ("chatgpt-owned-control-run.sh", "origin-client.py"):
                shutil.copyfile(CONTROL / name, control / name)
            (control / "chatgpt-request.json").write_text(json.dumps({
                "schema": "chatgpt-owned-control-request-v1",
                "request_id": "test-identity-pin",
                "target_runtime_id": "fasthost.powerpc_darwin_org",
                "tool": "runtime_health", "arguments": {},
            }))
            fixture = root / "identity.json"
            fixture.write_text(json.dumps(identity))
            queue_access = root / "queue-access"
            binaries = root / "bin"
            binaries.mkdir()
            # Transport stubs prevent all network and Git effects. Run the real
            # adapter and crypto client, stopping if it ever reaches queue fetch.
            (binaries / "git").write_text(
                '#!/bin/sh\n[ "$1" = config ] && exit 0\n'
                'printf "%s\\n" "$*" >> "$TEST_QUEUE_ACCESS"\nexit 77\n')
            (binaries / "curl").write_text(
                '#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
                'if [ "$1" = -o ]; then cp "$TEST_IDENTITY" "$2"; exit 0; fi\n'
                'shift\ndone\nexit 78\n')
            for binary in binaries.iterdir():
                binary.chmod(0o700)
            env = dict(os.environ, GITHUB_WORKSPACE=str(root),
                       PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                       TEST_IDENTITY=str(fixture), TEST_QUEUE_ACCESS=str(queue_access))
            result = subprocess.run(
                ["bash", str(control / "chatgpt-owned-control-run.sh")],
                cwd=root, env=env, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity fingerprint pin mismatch", result.stderr)
            self.assertFalse(queue_access.exists(), result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
