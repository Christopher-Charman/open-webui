"""Optional owner-only Mnemosyne context contract and replay tests."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from test_delegate_cagent_typed_intent import delegate, typed_envelope

def response(req, records=None):
    return {"schema":"owned-mnemosyne-context-v1","request_id":req["request_id"],
            "state":"READ_ONLY_CONTEXT","runtime_id":"fasthost.powerpc_darwin_org",
            "domain":"shared-architecture","derived_memory_authority":"DERIVED_CONTEXT_ONLY",
            "current_project_authority_verified":False,"automatic_agent_injection":False,
            "memory_ingestion":False,"sync_enabled":False,
            "mnemosyne":[] if records is None else records}

def record():
    return {"kind":"VERIFIED_DERIVED_MEMORY","authority":"DERIVED_CONTEXT_ONLY",
            "record_id":"architecture.test.v1","text":"Synthetic architectural test.",
            "text_truncated":False,"source_ref":"git:Owner/Repo/architecture.md",
            "source_version":"a"*40}

class MnemoContextTests(unittest.TestCase):
    def setUp(self):
        self.env=typed_envelope()
    def fake(self, function):
        def call(argv,**kwargs):
            self.assertEqual(argv,[str(delegate.MNEMO_PYTHON),str(delegate.MNEMO_READER)])
            self.assertLessEqual(kwargs["timeout"],10)
            r=json.loads(kwargs["input"])
            self.assertEqual(r["query"],self.env["objective"][:256])
            kwargs["stdout"].write(delegate.canon(function(r)))
            return type("Done",(),{"returncode":0})()
        return call

    def test_empty_bank_read_and_tight_source_contract(self):
        with patch.object(delegate.subprocess,"run",side_effect=self.fake(response)):
            p=delegate.read_owned_mnemosyne_context(self.env,8)
        self.assertEqual(p["count"],0)
        self.assertFalse(p["verified_current_project_authority"])

    def test_source_verified_record_stays_derived(self):
        with patch.object(delegate.subprocess,"run",side_effect=self.fake(
             lambda r:response(r,[record()]))):
            p=delegate.read_owned_mnemosyne_context(self.env,8)
        self.assertEqual(p["records"][0]["authority"],"DERIVED_CONTEXT_ONLY")

    def test_denies_renamed_authority_secrets_and_unpinned_git(self):
        for key,value in [("authority","RUNTIME_OWNER"),("source_ref","runtime:untrusted"),
                          ("source_version","main"),("text","password=credential-value-123")]:
            item=record();item[key]=value
            with self.subTest(key=key),patch.object(delegate.subprocess,"run",
                 side_effect=self.fake(lambda r:response(r,[item]))):
                with self.assertRaises(delegate.Reject):
                    delegate.read_owned_mnemosyne_context(self.env,8)

    def test_denies_wrong_receipt_binding(self):
        for key,value in [("request_id","wrong"),("memory_ingestion",True),
                          ("current_project_authority_verified",True),
                          ("runtime_id","fasthost.evenio"),
                          ("automatic_agent_injection",True)]:
            def altered(req):
                d=response(req);d[key]=value;return d
            with self.subTest(key=key),patch.object(delegate.subprocess,"run",
                 side_effect=self.fake(altered)):
                with self.assertRaises(delegate.Reject):
                    delegate.read_owned_mnemosyne_context(self.env,8)

    def test_optional_real_receiver_replay_no_duplicate_fetch(self):
        events=[]
        def read(env,t):events.append("mnemo");return {
            "schema":"owned-cagent-architecture-memory-v1",
            "authority":"DERIVED_CONTEXT_ONLY",
            "verified_current_project_authority":False,
            "count":0,"records":[]}
        def frontier(*a,**kw):events.append("frontier");return {}, "f"*64
        def mcp(*a,**kw):events.append("mcp");return {"isError":False},1
        with tempfile.TemporaryDirectory() as td:
            with (patch.object(delegate,"STATE",Path(td)),
                  patch.object(delegate,"CONTEXT_ENABLED",False),
                  patch.object(delegate,"MNEMO_ENABLED",True),
                  patch.object(delegate.time,"time",return_value=2_000_000_000),
                  patch.object(delegate,"open_ledger_session",return_value=("session:test","now")),
                  patch.object(delegate,"read_ledger_frontier",side_effect=frontier),
                  patch.object(delegate,"read_owned_mnemosyne_context",side_effect=read) as reader,
                  patch.object(delegate,"resolve_claim_model") as claim_model,
                  patch.object(delegate,"call_local_mcp",side_effect=mcp)):
                first=delegate.run(self.env)
                second=delegate.run(self.env)
        self.assertEqual(first,second)
        self.assertEqual(first["completion_state"],"COMPLETED")
        self.assertEqual(events,["frontier","mnemo","mcp"])
        self.assertEqual(first["owned_memory_context_status"],"DERIVED_CONTEXT_ONLY")
        claim_model.assert_not_called()
        reader.assert_called_once()

    def test_off_baseline_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            with (patch.object(delegate,"STATE",Path(td)),
                  patch.object(delegate,"CONTEXT_ENABLED",False),
                  patch.object(delegate,"MNEMO_ENABLED",False),
                  patch.object(delegate.time,"time",return_value=2_000_000_000),
                  patch.object(delegate,"open_ledger_session",return_value=("session:test","now")),
                  patch.object(delegate,"read_ledger_frontier",return_value=({}, "f"*64)),
                  patch.object(delegate,"read_owned_mnemosyne_context") as reader,
                  patch.object(delegate,"call_local_mcp",return_value=({"isError":False},1))):
                receipt=delegate.run(self.env)
        self.assertEqual(receipt["completion_state"],"COMPLETED")
        self.assertNotIn("owned_memory_context",receipt)
        reader.assert_not_called()

if __name__=="__main__":unittest.main()
