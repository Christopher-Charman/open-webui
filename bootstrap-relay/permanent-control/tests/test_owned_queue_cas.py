"""CAS queue transport remains separate from protected source and Actions."""
from __future__ import annotations
import importlib.util
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/"owned-queue-cas.py"
spec=importlib.util.spec_from_file_location("owned_queue_cas_test",SOURCE)
cas=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cas)


def task(suffix="001"):
    now=int(time.time())
    return {
        "protocol":cas.PROTOCOL,"version":1,
        "task_id":"ops-queue-safe-"+suffix,
        "target_runtime_id":cas.EXPECTED_TARGET,
        "created_at":now,"expires_at":now+300,
        "origin_ephemeral_x25519_spki_b64":"encrypted-public-der",
        "nonce_b64":"encrypted-nonce",
        "ciphertext_b64":"encrypted-payload",
    }


class QueueCASContractTests(unittest.TestCase):
    def setUp(self):
        self.empty={"protocol":cas.PROTOCOL,"version":1,"tasks":[]}

    def test_branch_is_distinct_owned_runtime_data_not_source(self):
        self.assertEqual(cas.BRANCH,"runtime-queue-powerpc-darwin-org-v1")
        self.assertNotEqual(cas.BRANCH,"main")
        self.assertTrue(cas.API.endswith("bootstrap-relay/permanent-control/queue.json"))

    def test_exact_encrypted_append_and_idempotent_replay(self):
        sample=task()
        updated,changed=cas.next_queue(self.empty,sample)
        self.assertTrue(changed)
        self.assertEqual(updated["tasks"],[sample])
        repeated,changed=cas.next_queue(updated,sample)
        self.assertFalse(changed)
        self.assertEqual(repeated,updated)

    def test_same_id_changed_ciphertext_conflicts(self):
        sample=task()
        updated,_=cas.next_queue(self.empty,sample)
        with self.assertRaisesRegex(cas.QueueError,"task_id_conflict"):
            cas.next_queue(updated,{**sample,"ciphertext_b64":"modified"})

    def test_reject_unbound_expired_and_forged_envelopes(self):
        sample=task()
        for invalid in (
            {**sample,"target_runtime_id":"fasthost.evenio"},
            {**sample,"target_runtime_id":"openai:chatgpt"},
            {**sample,"ciphertext_b64":""},
            {**sample,"expires_at":int(time.time())-1},
            {**sample,"created_at":int(time.time())+3600},
            {**sample,"created_at":True},
            {**sample,"version":2},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(cas.QueueError):
                    cas.validate_encrypted_envelope(invalid)

    def test_retirement_is_exact_and_replay_safe(self):
        sample=task("delete")
        q,_=cas.next_queue(self.empty,sample)
        cleaned,changed=cas.retired_queue(q,sample["task_id"])
        self.assertTrue(changed)
        self.assertEqual(cleaned["tasks"],[])
        replay,changed=cas.retired_queue(cleaned,sample["task_id"])
        self.assertFalse(changed)

    def test_read_queue_requires_exact_blob_metadata(self):
        body=base64.b64encode(cas.canonical(self.empty)).decode("ascii")
        response={"path":cas.PATH,"sha":"a"*40,"encoding":"base64","content":body}
        with patch.object(cas,"_gh",return_value=response) as fetch:
            sha,queue=cas.read_queue()
            self.assertEqual(sha,"a"*40)
            self.assertEqual(queue,self.empty)
            self.assertIn("ref="+cas.BRANCH,fetch.call_args.args[0][0])
        with patch.object(cas,"_gh",return_value={**response,"path":"wrong"}):
            with self.assertRaises(cas.QueueError):
                cas.read_queue()

    def test_cas_write_never_claims_executor_success(self):
        sample=task()
        updated,_=cas.next_queue(self.empty,sample)
        with patch.object(cas,"_gh",return_value={"commit":{"sha":"b"*40}}) as gh:
            observed=cas.cas_write("a"*40,updated,sample["task_id"],"append")
            self.assertEqual(observed,"WRITE_RESPONSE_OBSERVED")
            arg=gh.call_args
            self.assertEqual(arg.args[0][:3],["-X","PUT",cas.API])
            payload=json.loads(arg.args[1])
            self.assertEqual(payload["branch"],cas.BRANCH)
            self.assertEqual(payload["sha"],"a"*40)
            self.assertNotIn("terminal_exec",json.dumps(payload))
        with patch.object(cas,"_gh",side_effect=cas.QueueError("github_delivery_unknown")):
            self.assertEqual(cas.cas_write("a"*40,updated,sample["task_id"],"append"),
                             "OUTCOME_UNKNOWN")

    def test_no_implicit_action_execution_in_queue_tool(self):
        source=SOURCE.read_text()
        self.assertNotIn("shell=True",source)
        self.assertNotIn("subprocess.Popen",source)
        self.assertNotIn("origin-client.py prepare",source)


if __name__=="__main__":
    unittest.main()
