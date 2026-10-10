"""The Actions transport is public-safe and must never accept operator effects."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

CONTROL = Path(__file__).resolve().parents[1]
SOURCE = CONTROL / "public_safe_request.py"
SPEC = importlib.util.spec_from_file_location("public_safe_request_test", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def request(**overrides):
    obj = {
        "schema": "chatgpt-owned-control-request-v1",
        "request_id": "public-safe-test-001",
        "target_runtime_id": "fasthost.powerpc_darwin_org",
        "tool": "runtime_health", "arguments": {},
        "authority_ceiling": "read_only",
        "ttl": 300, "result_visibility": "summary",
    }
    obj.update(overrides)
    return obj


class PublicSafeRequestTests(unittest.TestCase):
    def test_valid_read_only_runtime_tools(self):
        for tool in ("runtime_health", "read_text", "list_dir"):
            with self.subTest(tool=tool):
                d = module.validate_public_safe_request(request(tool=tool))
                self.assertEqual(d["tool"], tool)
                self.assertEqual(d["authority_ceiling"], "read_only")

    def test_operator_and_terminal_execution_never_allowed(self):
        cases = [
            request(tool="terminal_exec", authority_ceiling="bounded_operator",
                    arguments={"command": "true"}),
            request(tool="terminal_exec"),
            request(authority_ceiling="bounded_operator"),
            request(tool="open_terminal_control"),
            request(tool="delegation_execute"),
        ]
        for obj in cases:
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                module.validate_public_safe_request(obj)

    def test_public_plaintext_never_allowed(self):
        with self.assertRaisesRegex(ValueError, "summary"):
            module.validate_public_safe_request(
                request(result_visibility="public_plaintext")
            )

    def test_target_schema_and_unknown_fields_denied(self):
        cases = [
            request(target_runtime_id="openai:chatgpt-internal"),
            request(target_runtime_id="fasthost.evenio"),
            request(schema="other"),
            request(user_asserts_owner=True),
            request(arguments=[]),
            request(ttl=True),
            request(ttl=601),
            request(request_id="x"),
        ]
        for obj in cases:
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                module.validate_public_safe_request(obj)

    def test_real_runner_denies_operator_before_identity_or_queue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control = root / "bootstrap-relay/permanent-control"
            control.mkdir(parents=True)
            for name in ("chatgpt-owned-control-run.sh", "public_safe_request.py"):
                shutil.copyfile(CONTROL / name, control / name)
            (control / "chatgpt-request.json").write_text(json.dumps(
                request(tool="terminal_exec", authority_ceiling="bounded_operator",
                        arguments={"command": "true"})
            ))
            binaries = root / "bin"
            binaries.mkdir()
            audit = root / "provider-contacted"
            (binaries / "git").write_text(
                '#!/bin/sh\n'
                'if [ "$1" = "config" ]; then exit 0; fi\n'
                'printf "%s\\n" "$*" >> "$ADAPTER_CONTACT_AUDIT"\n'
                'exit 77\n'
            )
            (binaries / "curl").write_text(
                '#!/bin/sh\necho curl >> "$ADAPTER_CONTACT_AUDIT"\nexit 77\n'
            )
            for p in binaries.iterdir():
                p.chmod(0o700)
            env = dict(os.environ, GITHUB_WORKSPACE=str(root),
                       PATH=str(binaries)+os.pathsep+os.environ["PATH"],
                       ADAPTER_CONTACT_AUDIT=str(audit))
            p = subprocess.run(["bash", str(control / "chatgpt-owned-control-run.sh")],
                               cwd=root,env=env,text=True,capture_output=True,timeout=15)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("public_safe_tool_not_permitted",p.stderr)
            self.assertFalse(audit.exists())
            self.assertFalse((control / "queue.json").exists())


if __name__ == "__main__":
    unittest.main()
