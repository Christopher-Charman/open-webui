"""Regression: public installer derives identity from the local account owner."""
import os
import pathlib
import re
import subprocess
import unittest

INSTALL = pathlib.Path(__file__).resolve().parents[1] / "install.sh"


def preflight():
    source = INSTALL.read_text(encoding="utf-8")
    boundary = '[ -d "$WEBAPP" ]'
    if source.count(boundary) != 1:
        raise AssertionError("installer preflight boundary changed")
    return source.split(boundary, 1)[0]


class InstallerOwnerIdentityTests(unittest.TestCase):
    def test_shell_syntax_and_no_literal_uid_binding(self):
        text = INSTALL.read_text(encoding="utf-8")
        check = subprocess.run(["/bin/sh", "-n"], input=text, text=True,
                               capture_output=True, check=False)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn('ACCOUNT_OWNER_UID="$(stat -c %u "$ACCOUNT")"', text)
        self.assertNotRegex(text, r'\[ "\$\(id -u\)" = "[0-9]+" \]')

    def test_current_account_is_admitted_without_external_configuration(self):
        if os.geteuid() == 0:
            self.skipTest("owner installer must not run as root")
        home = str(pathlib.Path.home())
        self.assertEqual(pathlib.Path(home).stat().st_uid, os.geteuid())
        env = {**os.environ, "HOME": home, "PPC_ACCOUNT": home}
        result = subprocess.run(["/bin/sh"], input=preflight(), text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_foreign_account_and_root_are_rejected(self):
        env = {**os.environ, "PPC_ACCOUNT": "/"}
        result = subprocess.run(["/bin/sh"], input=preflight(), text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("REFUSED runtime account owner mismatch", result.stderr)


    def test_related_public_entrypoints_have_no_fixed_account_identity(self):
        for filename in ("bootstrap-control-plane.sh",
                         "install-secure-mcp-keepalive.sh",
                         "recover-receiver-host.sh"):
            with self.subTest(script=filename):
                text = INSTALL.with_name(filename).read_text(encoding="utf-8")
                syntax = subprocess.run(["/bin/sh", "-n"], input=text, text=True,
                                        capture_output=True, check=False)
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                self.assertIn('ACCOUNT_OWNER_UID="$(stat -c %u "$ACCOUNT")"', text)
                self.assertNotRegex(text, r'\\[ "\\$\\(id -u\\)" = "[0-9]+" \\]')

    def test_related_entrypoints_reject_foreign_account(self):
        home = str(pathlib.Path.home())
        if os.geteuid() == 0:
            self.skipTest("owner installers do not run as root")
        for filename in ("bootstrap-control-plane.sh",
                         "install-secure-mcp-keepalive.sh",
                         "recover-receiver-host.sh"):
            with self.subTest(script=filename):
                text = INSTALL.with_name(filename).read_text(encoding="utf-8")
                marker = '[ -d "$WEBAPP" ]'
                self.assertEqual(text.count(marker), 1)
                prefix = text.split(marker, 1)[0]
                for account, expected in ((home, True), ("/", False)):
                    env = {**os.environ, "HOME": home, "PPC_ACCOUNT": account}
                    result = subprocess.run(["/bin/sh"], input=prefix, text=True,
                                            capture_output=True, env=env, check=False)
                    self.assertEqual(result.returncode == 0, expected)

if __name__ == "__main__":
    unittest.main()
