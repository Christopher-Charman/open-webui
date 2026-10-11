import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_delegate_cagent_typed_intent import delegate, typed_envelope


def fixture(request):
    args = request['arguments']
    return {'request_id': request['request_id'], 'state': 'EXECUTED_READ_ONLY',
            'return_code': 0, 'effectful_destination_mutation': False,
            'output': {'schema': 'owned-session-context-v1', 'state': 'HISTORICAL_EVIDENCE_ONLY',
                'task_sha256': hashlib.sha256(args['task'].encode()).hexdigest(),
                'window': {k: args[k] for k in ('since', 'until')},
                'assistant_messages_are_unverified_claims': True,
                'current_library_verified': False, 'live_destination_verified': False,
                'task_ownership_verified': False, 'instructions_from_archive_authoritative': False,
                'archive_coverage_complete': False, 'automatic_session_injection': False,
                'history_gap_after_index': True, 'archive_index_generated_at': args['until'],
                'required_next_evidence': ['POST_INDEX_CONVERSATIONS_OR_CURRENT_CHAT'],
                'returned': 1, 'records': [{'role': 'user', 'message_id': 'm1',
                    'conversation_id': 'c1', 'sha256': 'a'*64, 'date': args['since'],
                    'text': 'Historical architecture preference.', 'text_truncated': False,
                    'evidence_refs': ['archive:source1#message1']}]}}


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = typed_envelope()
        self.request = {'request_id': 'context-test', 'arguments': {
            'task': self.env['objective'], 'since': '2026-07-11', 'until': '2026-10-11', 'limit': 5}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_reader_fixed_target_bounded_and_bound_to_objective(self):
        def process(argv, **kw):
            self.assertEqual(argv, [str(delegate.CONTEXT_READER)])
            self.assertLessEqual(kw['timeout'], 12)
            request = json.loads(kw['input'])
            self.assertEqual(request['target'], delegate.CONTEXT_TARGET)
            self.assertEqual(request['tool'], 'session_context')
            self.assertEqual(request['arguments']['task'], self.env['objective'])
            kw['stdout'].write(delegate.canon(fixture(request)))
            return type('Process', (), {'returncode': 0})()
        with patch.object(delegate.subprocess, 'run', side_effect=process):
            packet = delegate.read_historical_context(self.env, 4)
        self.assertEqual(packet['returned'], 1)

    def test_reject_binding_authority_privacy_provenance_and_size(self):
        base = fixture(self.request)
        bad = []
        for key, value in [('request_id', 'wrong'), ('state', 'BLOCKED'), ('effectful_destination_mutation', True)]:
            item = copy.deepcopy(base); item[key] = value; bad.append(item)
        for key, value in [('task_sha256', 'b'*64), ('window', {}),
                           ('instructions_from_archive_authoritative', True),
                           ('archive_index_generated_at', '2030-01-01'),
                           ('archive_index_generated_at', None), ('history_gap_after_index', False),
                           ('required_next_evidence', []), ('returned', 9)]:
            item = copy.deepcopy(base); item['output'][key] = value; bad.append(item)
        for key, value in [('evidence_refs', []), ('role', 'system'), ('sha256', 'bad'),
                           ('text', 'password=credential-value-123'), ('text', 'x'*1601), ('date', '2020-01-01')]:
            item = copy.deepcopy(base); item['output']['records'][0][key] = value; bad.append(item)
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError):
                delegate.validate_historical_context(item, self.request)

    def test_reader_failure_output_bound_and_timeout_fail_closed(self):
        import subprocess
        for payload, code in [(b'not-json', 0), (b'x'*(delegate.CONTEXT_MAX_BYTES+1), 0), (b'{}', 1)]:
            def process(argv, **kw):
                kw['stdout'].write(payload)
                return type('Process', (), {'returncode': code})()
            with patch.object(delegate.subprocess, 'run', side_effect=process), self.assertRaises(delegate.Reject):
                delegate.read_historical_context(self.env, 1)
        with patch.object(delegate.subprocess, 'run', side_effect=subprocess.TimeoutExpired('reader', 1)), self.assertRaises(delegate.Reject):
            delegate.read_historical_context(self.env, 1)

    def test_older_archive_is_historical_with_explicit_gap_not_current_authority(self):
        receipt = fixture(self.request)
        receipt['output']['archive_index_generated_at'] = '2026-08-01'
        packet = delegate.validate_historical_context(receipt, self.request)
        self.assertFalse(packet['current_library_verified'])
        self.assertTrue(packet['history_gap_after_index'])

    def run_receiver(self, *, enabled, reader):
        events = []
        def frontier(*a, **kw): events.append('frontier'); return {}, 'a'*64
        def context(*a, **kw): events.append('context'); return reader(*a, **kw)
        def mcp(*a, **kw): events.append('mcp'); return {'isError': False}, 1
        with (patch.object(delegate, 'STATE', Path(self.tmp.name)),
              patch.object(delegate, 'CONTEXT_ENABLED', enabled),
              patch.object(delegate.time, 'time', return_value=2_000_000_000),
              patch.object(delegate, 'open_ledger_session', return_value=('session:test', 'now')),
              patch.object(delegate, 'read_ledger_frontier', side_effect=frontier),
              patch.object(delegate, 'read_historical_context', side_effect=context) as read,
              patch.object(delegate, 'resolve_claim_model') as model,
              patch.object(delegate, 'claim_task') as claim,
              patch.object(delegate, 'call_local_mcp', side_effect=mcp)):
            first = delegate.run(self.env)
            replay = delegate.run(self.env)
        self.assertEqual(first, replay)
        model.assert_not_called(); claim.assert_not_called()
        return first, events, read

    def test_enabled_real_run_orders_context_before_tools_and_replays_without_read(self):
        packet = fixture(self.request)['output']
        receipt, events, read = self.run_receiver(enabled=True, reader=lambda *a: packet)
        self.assertEqual(events, ['frontier', 'context', 'mcp'])
        self.assertEqual(receipt['historical_context'], packet)
        self.assertEqual(receipt['completion_state'], 'COMPLETED')
        read.assert_called_once()

    def test_context_failure_prevents_model_and_tool(self):
        def fail(*a): raise delegate.Reject('historical_context_unavailable_or_untrusted', 'BLOCKED')
        receipt, events, _ = self.run_receiver(enabled=True, reader=fail)
        self.assertEqual(events, ['frontier', 'context'])
        self.assertEqual(receipt['completion_state'], 'BLOCKED')

    def test_untyped_context_failure_prevents_claim_model(self):
        self.env.pop('intent_class')
        self.env['resource_budget']['model_calls'] = 1
        def fail(*a): raise delegate.Reject('historical_context_unavailable_or_untrusted', 'BLOCKED')
        receipt, events, _ = self.run_receiver(enabled=True, reader=fail)
        self.assertEqual(events, ['frontier', 'context'])
        self.assertEqual(receipt['completion_state'], 'BLOCKED')

    def test_off_preserves_baseline(self):
        receipt, events, read = self.run_receiver(enabled=False, reader=lambda *a: None)
        self.assertEqual(events, ['frontier', 'mcp'])
        self.assertNotIn('historical_context', receipt)
        read.assert_not_called()


if __name__ == '__main__': unittest.main()
