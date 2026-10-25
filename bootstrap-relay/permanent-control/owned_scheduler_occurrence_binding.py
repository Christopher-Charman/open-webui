"""Bound occurrence dispatcher for the existing scheduler's due-task callback.

The scheduler supplies its own deterministic occurrence identity and existing
authenticated dispatch callback. This adapter does not mint owner authority,
register schedules, or invent a second clock.
"""
from collections.abc import Callable
from time import time
from owned_occurrence_ledger import OccurrenceLedger


def dispatch_due_occurrence(*, ledger: OccurrenceLedger, occurrence_id: str,
                            task_id: str, due_at: int, owner_id: str, now: int,
                            dispatch: Callable, verify_destination: Callable,
                            lease_seconds: int = 300, clock: Callable = time) -> dict:
    if not isinstance(ledger, OccurrenceLedger):
        raise TypeError("OWNED_OCCURRENCE_LEDGER_REQUIRED")
    if not callable(dispatch) or not callable(verify_destination) or not callable(clock):
        raise ValueError("BOUND_DISPATCH_AND_READBACK_REQUIRED")
    ledger.register(occurrence_id, task_id, due_at)
    claim = ledger.claim(occurrence_id, owner_id, now, lease_seconds)
    if claim.get("state") != "CLAIMED" or claim.get("claimed") is not True:
        return {**claim, "execution_attempted": False, "occurrence_id": occurrence_id}
    packet = {"occurrence_id": occurrence_id, "task_id": task_id,
              "owner_id": owner_id, "generation": claim["generation"]}
    try:
        receipt = dispatch(dict(packet))
    except Exception:
        # The remote effect may already have committed. Leave the claim
        # unresolved; expiry transitions to UNKNOWN for owner reconciliation.
        return {"state": "OUTCOME_UNKNOWN", "execution_attempted": True,
                "occurrence_id": occurrence_id}
    if not isinstance(receipt, dict) or not isinstance(receipt.get("receipt_ref"), str):
        return {"state": "OUTCOME_UNKNOWN", "execution_attempted": True,
                "occurrence_id": occurrence_id}
    receipt_ref = receipt["receipt_ref"]
    if not receipt_ref:
        return {"state": "OUTCOME_UNKNOWN", "execution_attempted": True,
                "occurrence_id": occurrence_id}
    try:
        verified = verify_destination(dict(packet), receipt_ref)
    except Exception:
        verified = False
    if verified is not True:
        return {"state": "AWAITING_READBACK", "execution_attempted": True,
                "occurrence_id": occurrence_id}
    completed = ledger.complete(occurrence_id, owner_id, claim["generation"],
                               receipt_ref, int(clock()))
    return {**completed, "execution_attempted": True,
            "destination_readback_verified": completed["completed"],
            "occurrence_id": occurrence_id}
