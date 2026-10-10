"""Never upgrade a signed encrypted publication to invented task completion."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric import ed25519

SCRIPT=Path(__file__).resolve().parents[1]/"reconcile-signed-published-results.py"
spec=importlib.util.spec_from_file_location("owned_signed_result_reconcile_test",SCRIPT)
mod=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)


class PublishedReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.results=self.dir/"results"
        self.mirror=self.dir/"mirror"
        self.results.mkdir();self.mirror.mkdir()
        self.tid="test-claimed-published-orphan1"
        self.received=1790904409
        self.envsha="f"*64
        self.key=ed25519.Ed25519PrivateKey.generate()
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute(
            "CREATE TABLE tasks(task_id TEXT PRIMARY KEY,envelope_sha256 TEXT,"
            "state TEXT,received_at INTEGER,completed_at INTEGER,result_path TEXT)"
        )
        self.db.execute("INSERT INTO tasks(task_id,envelope_sha256,state,received_at)"
                        "VALUES(?,?,?,?)",(self.tid,self.envsha,"claimed",self.received))
        self.db.commit()
        self.publish()

    def publish(self,**changes):
        result={
            "protocol":"powerpc-control-v1","version":1,
            "task_id":self.tid,"target_runtime_id":mod.EXPECTED_RUNTIME,
            "kind":"result","published_at":self.received+1,
            "nonce_b64":"encrypted","ciphertext_b64":"not-plaintext",
        }
        result.update(changes)
        result["signature_b64"]=mod.base64.urlsafe_b64encode(
            self.key.sign(mod.canonical(result))
        ).decode().rstrip("=")
        data=mod.canonical(result)+b"\n"
        (self.results/(self.tid+".json")).write_bytes(data)
        (self.mirror/(self.tid+".json")).write_bytes(data)

    def evidence(self):
        return mod.attest_published_result(
            self.tid,self.received,self.key.public_key(),self.results,self.mirror
        )

    def state(self):
        return self.db.execute(
            "SELECT state,completed_at,result_path FROM tasks WHERE task_id=?",
            (self.tid,),
        ).fetchone()

    def test_signed_envelope_proves_published_only(self):
        item=self.evidence()
        self.assertEqual(item.status,"SIGNED_PUBLISHED")
        self.assertEqual(item.reason,"decrypted_outcome_not_verified")
        self.assertEqual(mod.reconcile_one(self.db,item,self.envsha,False),
                         "ELIGIBLE_NO_MUTATION")
        self.assertEqual(self.state(),("claimed",None,None))

    def test_metadata_only_cas_and_idempotence(self):
        item=self.evidence()
        self.assertEqual(mod.reconcile_one(self.db,item,self.envsha,True),
                         "CLASSIFIED_PUBLISHED_OUTCOME_UNVERIFIED")
        self.assertEqual(self.state(),
                         (mod.UNVERIFIED,None,str(self.results/(self.tid+".json"))))
        self.assertEqual(mod.reconcile_one(self.db,item,self.envsha,True),
                         "ALREADY_CLASSIFIED")
        self.assertIsNone(self.state()[1])

    def test_tampered_ciphertext_without_valid_signature_is_not_classified(self):
        p=self.results/(self.tid+".json")
        value=json.loads(p.read_text())
        value["ciphertext_b64"]="tampered"
        data=mod.canonical(value)+b"\n"
        p.write_bytes(data)
        (self.mirror/(self.tid+".json")).write_bytes(data)
        item=self.evidence()
        self.assertEqual(item.status,"UNRESOLVED")
        self.assertEqual(mod.reconcile_one(self.db,item,self.envsha,True),
                         "UNRESOLVED_RESULT_UNVERIFIED")
        self.assertEqual(self.state(),("claimed",None,None))

    def test_missing_mirror_does_not_promote(self):
        (self.mirror/(self.tid+".json")).unlink()
        self.assertEqual(self.evidence().status,"UNRESOLVED")
        self.assertEqual(self.state(),("claimed",None,None))

    def test_conflicting_envelope_record_denied(self):
        item=self.evidence()
        self.assertEqual(mod.reconcile_one(self.db,item,"0"*64,True),
                         "UNRESOLVED_ENVELOPE_CHANGED")
        self.assertEqual(self.state(),("claimed",None,None))

    def test_completion_not_rewritten(self):
        self.db.execute("UPDATE tasks SET state=?,completed_at=? WHERE task_id=?",
                        ("completed",123,self.tid))
        self.db.commit()
        self.assertEqual(mod.reconcile_one(self.db,self.evidence(),self.envsha,True),
                         "UNRESOLVED_STATE_CHANGED")
        self.assertEqual(self.state(),("completed",123,None))

    def test_wrong_task_result_signature_rejected(self):
        self.publish(task_id="wrong-task")
        self.assertEqual(self.evidence().status,"UNRESOLVED")
        self.assertEqual(self.state(),("claimed",None,None))

    def test_unreasonable_publish_clock_rejected(self):
        self.publish(published_at=self.received-500)
        self.assertEqual(self.evidence().status,"UNRESOLVED")
        self.assertEqual(self.state(),("claimed",None,None))


if __name__=="__main__":
    unittest.main()
