"""No-network regression tests for owner-bound objective context admission."""

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from open_webui.utils.owned_objective_admission import (
    append_owned_objective_context,
    bind_owned_objective_readback,
)


class OwnedObjectiveAdmissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = type('User', (), {'role': 'admin'})()
        self.objective_id = 'owned-architecture-repairs-20261004-through-20261011'
        self.metadata = {'owned_objective_id': self.objective_id}
        self.env = {'OWNED_OBJECTIVE_INGRESS_PATH': '/synthetic/owner-ingress'}

    def result(self, payload=None, returncode=3):
        payload = (
            {
                'objective_id': self.objective_id,
                'state': 'CONTINUATION_REQUIRED',
                'next_action': 'EXECUTE_NEXT_AUTHORIZED_REQUIREMENT',
                'decision': {'next_requirement_id': 'openwebui-pre-model-admission'},
                'execution_attempted': False,
                'objective_complete': False,
            }
            if payload is None
            else payload
        )
        return type('Result', (), {'stdout': json.dumps(payload), 'returncode': returncode})()

    async def test_admin_readback_is_bounded_and_non_authoritative(self):
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch('open_webui.utils.owned_objective_admission.os.path.isfile', return_value=True),
            patch('open_webui.utils.owned_objective_admission.os.access', return_value=True),
            patch(
                'open_webui.utils.owned_objective_admission.subprocess.run',
                return_value=self.result(),
            ) as run,
        ):
            await bind_owned_objective_readback(self.metadata, self.user)

        run.assert_called_once()
        self.assertEqual(json.loads(run.call_args.kwargs['input']), {'objective_id': self.objective_id})
        self.assertEqual(self.metadata['owned_objective_admission']['state'], 'CONTINUATION_REQUIRED')
        self.assertFalse(self.metadata['owned_objective_admission']['mutation_authority'])
        self.assertFalse(self.metadata['owned_objective_admission']['execution_attempted'])

    async def test_non_admin_invalid_id_and_missing_ingress_fail_closed(self):
        with patch.dict(os.environ, self.env, clear=True):
            with self.assertRaises(HTTPException) as non_admin:
                await bind_owned_objective_readback(self.metadata, type('User', (), {'role': 'user'})())
            self.assertEqual(non_admin.exception.status_code, 403)

            self.metadata['owned_objective_id'] = '../invalid'
            with self.assertRaises(HTTPException) as invalid:
                await bind_owned_objective_readback(self.metadata, self.user)
            self.assertEqual(invalid.exception.status_code, 400)

        with patch.dict(os.environ, {}, clear=True):
            self.metadata['owned_objective_id'] = self.objective_id
            with self.assertRaises(HTTPException) as missing:
                await bind_owned_objective_readback(self.metadata, self.user)
            self.assertEqual(missing.exception.status_code, 503)

    async def test_invalid_readback_shape_and_identity_fail_closed(self):
        for payload in ([], {'objective_id': 'different-id', 'state': 'CONTINUATION_REQUIRED'}):
            with (
                self.subTest(payload=payload),
                patch.dict(os.environ, self.env, clear=True),
                patch('open_webui.utils.owned_objective_admission.os.path.isfile', return_value=True),
                patch('open_webui.utils.owned_objective_admission.os.access', return_value=True),
                patch(
                    'open_webui.utils.owned_objective_admission.subprocess.run',
                    return_value=self.result(payload),
                ),
            ):
                with self.assertRaises(HTTPException) as invalid:
                    await bind_owned_objective_readback(self.metadata, self.user)
                self.assertEqual(invalid.exception.status_code, 503)

    def test_context_contains_only_status_and_untagged_request_is_unchanged(self):
        form_data = {'messages': [{'role': 'user', 'content': 'status'}]}
        original_messages = list(form_data['messages'])
        self.assertIs(append_owned_objective_context(form_data, {}), form_data)
        self.assertEqual(form_data['messages'], original_messages)

        context = {
            'objective_id': self.objective_id,
            'state': 'CONTINUATION_REQUIRED',
            'mutation_authority': True,
            'secret_extra_field': 'must not be forwarded',
        }
        with patch(
            'open_webui.utils.owned_objective_admission.add_or_update_system_message',
            side_effect=lambda content, messages, append: [*messages, {'role': 'system', 'content': content}],
        ):
            append_owned_objective_context(form_data, {'owned_objective_admission': context})

        injected = form_data['messages'][-1]['content']
        self.assertIn('NOT EXECUTION AUTHORITY', injected)
        self.assertIn('CONTINUATION_REQUIRED', injected)
        self.assertNotIn('secret_extra_field', injected)
        self.assertNotIn('must not be forwarded', injected)
        self.assertIn('does not prove execution or completion', injected)


if __name__ == '__main__':
    unittest.main()
