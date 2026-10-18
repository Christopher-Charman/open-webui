"""Regression: malformed receiver requests must carry objective evidence denial."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "delegate-cagent.py"


class MandatoryObjectiveAssessmentOnMalformedInput(unittest.TestCase):
    def test_invalid_requests_fail_with_objective_assessment(self):
        for name, payload in (
            ("malformed-json", b"{invalid-json"),
            ("json-array", b"[]"),
            ("empty", b""),
            ("invalid-utf8", b"\xff"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                env = dict(os.environ, PPC_ACCOUNT=root,
                           CAGENT_ARCHIVE_CONTEXT="0", CAGENT_MNEMOSYNE_CONTEXT="0")
                process = subprocess.run(
                    [sys.executable, str(SCRIPT)], input=payload,
                    capture_output=True, env=env, timeout=20, check=False)
                self.assertEqual(process.returncode, 2, process.stderr)
                receipt = json.loads(process.stdout)
                self.assertEqual(receipt["completion_state"], "FAILED")
                assessment = receipt["owned_objective_assessment"]
                self.assertIs(assessment["can_terminate_as_complete"], False)
                self.assertEqual(assessment["scope"], "objective_not_action")
                self.assertEqual(receipt["actions"], [])
                self.assertEqual(receipt["resource_usage"], {})


if __name__ == "__main__":
    unittest.main()
