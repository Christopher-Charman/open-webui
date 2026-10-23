"""Owner-bound, read-only objective status for OpenWebUI chat context."""

import asyncio
import json
import os
import re
import subprocess

from fastapi import HTTPException

from open_webui.utils.misc import add_or_update_system_message


async def bind_owned_objective_readback(metadata, user):
    """Attach a validated read-only owner status to request metadata."""
    if metadata.get('owned_objective_id') is None:
        return

    objective_id = metadata['owned_objective_id']
    ingress = os.environ.get('OWNED_OBJECTIVE_INGRESS_PATH', '')
    if getattr(user, 'role', None) != 'admin':
        raise HTTPException(status_code=403, detail='OWNED_OBJECTIVE_ADMIN_REQUIRED')
    if not isinstance(objective_id, str) or re.fullmatch(r'[a-z0-9][a-z0-9-]{2,127}', objective_id) is None:
        raise HTTPException(status_code=400, detail='OWNED_OBJECTIVE_ID_INVALID')
    if not ingress or not os.path.isfile(ingress) or not os.access(ingress, os.X_OK):
        raise HTTPException(status_code=503, detail='OWNED_OBJECTIVE_INGRESS_NOT_BOUND')

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [ingress],
            input=json.dumps({'objective_id': objective_id}),
            text=True,
            capture_output=True,
            check=False,
            timeout=3,
        )
        readback = json.loads(result.stdout[:16384])
        if not isinstance(readback, dict):
            raise ValueError('OWNER_OBJECTIVE_READBACK_INVALID')
        decision = readback.get('decision') or {}
        if not isinstance(decision, dict):
            raise ValueError('OWNER_OBJECTIVE_READBACK_INVALID')
        if (
            result.returncode not in (0, 3)
            or readback.get('objective_id') != objective_id
            or readback.get('state') not in {'OBJECTIVE_COMPLETE', 'CONTINUATION_REQUIRED'}
        ):
            raise ValueError('OWNER_OBJECTIVE_READBACK_INVALID')
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=503, detail='OWNED_OBJECTIVE_READBACK_UNAVAILABLE')

    metadata['owned_objective_admission'] = {
        'objective_id': objective_id,
        'state': readback['state'],
        'next_action': readback.get('next_action'),
        'next_requirement_id': decision.get('next_requirement_id'),
        'handoff_status': readback.get('handoff_status', 'NOT_DISPATCHED'),
        'execution_attempted': readback.get('execution_attempted') is True,
        'objective_complete': readback.get('objective_complete') is True,
        'mutation_authority': False,
    }


def append_owned_objective_context(form_data, metadata):
    """Append an explicit non-authoritative status note before model dispatch."""
    context = metadata.get('owned_objective_admission')
    if not isinstance(context, dict):
        return form_data

    owner_status = {
        key: context.get(key)
        for key in (
            'objective_id',
            'state',
            'next_action',
            'next_requirement_id',
            'handoff_status',
            'execution_attempted',
            'objective_complete',
        )
    }
    form_data['messages'] = add_or_update_system_message(
        '[OWNED OBJECTIVE STATUS READBACK; NOT EXECUTION AUTHORITY]\n'
        + json.dumps(owner_status, sort_keys=True)
        + '\nThis does not prove execution or completion. Continue only through independently admitted owner tools and readback.',
        form_data.get('messages', []),
        append=True,
    )
    return form_data
