"""Operational data branch cannot be inferred from protected source main."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/"daemon.py"
with tempfile.TemporaryDirectory() as d:
    old_account=os.environ.get("PPC_CONTROL_ACCOUNT")
    os.environ["PPC_CONTROL_ACCOUNT"]=d
    spec=importlib.util.spec_from_file_location("owned_queue_branch_receiver",SCRIPT)
    recv=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recv)
    if old_account is None:
        os.environ.pop("PPC_CONTROL_ACCOUNT",None)
    else:
        os.environ["PPC_CONTROL_ACCOUNT"]=old_account


class FakeResponse:
    def __init__(self,data):
        self.data=data
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def read(self,n):
        return self.data[:n]


class QueueBranchTests(unittest.TestCase):
    def test_queue_ref_is_dedicated_not_default_source_branch(self):
        self.assertEqual(recv.QUEUE_BRANCH,"runtime-queue-powerpc-darwin-org-v1")
        self.assertIn("/"+recv.QUEUE_BRANCH+"/",recv.QUEUE_URL)
        self.assertIn("?ref="+recv.QUEUE_BRANCH,recv.QUEUE_API_URL)
        self.assertNotIn("?ref=main",recv.QUEUE_API_URL)

    def test_git_ref_resolution_ignores_source_main(self):
        main=("a"*40).encode()
        ops=("b"*40).encode()
        advertisement=(
            b"003d"+main+b" refs/heads/main\n"
            +b"006a"+ops+b" refs/heads/runtime-queue-powerpc-darwin-org-v1\n"
        )
        with patch.object(recv.urllib.request,"urlopen",
                          return_value=FakeResponse(advertisement)) as f:
            self.assertEqual(recv._resolve_queue_branch_sha(),"b"*40)
        self.assertTrue(f.called)

    def test_ambiguous_refs_fail_closed(self):
        data=(
            b"00ff"+b"a"*40+b" refs/heads/runtime-queue-powerpc-darwin-org-v1\n"
            +b"00ff"+b"b"*40+b" refs/heads/runtime-queue-powerpc-darwin-org-v1\n"
        )
        with patch.object(recv.urllib.request,"urlopen",
                          return_value=FakeResponse(data)), \
             patch.object(recv,"_log") as log:
            self.assertIsNone(recv._resolve_queue_branch_sha())
            self.assertTrue(log.called)

    def test_reject_unregistered_or_path_like_branches_at_import(self):
        code="""
import importlib.util
spec=importlib.util.spec_from_file_location('bad_route',r'%s')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
""" % str(SCRIPT)
        for bad in ("../main","refs/heads/main","evil/other",""):
            with self.subTest(ref=bad), tempfile.TemporaryDirectory() as tmp:
                env=dict(os.environ,
                         PPC_CONTROL_QUEUE_BRANCH=bad or "evil/other",
                         PPC_CONTROL_ACCOUNT=tmp)
                r=subprocess.run([sys.executable,"-c",code],env=env,
                                 text=True,capture_output=True,timeout=15)
                self.assertNotEqual(r.returncode,0)
                self.assertIn("unregistered_owned_queue_branch",r.stderr)

    def test_existing_source_main_explicit_compatibility_is_constrained(self):
        code="""
import importlib.util
spec=importlib.util.spec_from_file_location('legacy_route',r'%s')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.QUEUE_BRANCH,module.QUEUE_URL,module.QUEUE_API_URL)
""" % str(SCRIPT)
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,PPC_CONTROL_QUEUE_BRANCH="main",
                     PPC_CONTROL_ACCOUNT=tmp)
            r=subprocess.run([sys.executable,"-c",code],env=env,
                             text=True,capture_output=True,timeout=15)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("/main/",r.stdout)
            self.assertIn("?ref=main",r.stdout)


if __name__=="__main__":
    unittest.main()
