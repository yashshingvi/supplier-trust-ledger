"""Hash-chained, append-only ledger helpers.

Each event stores prev_hash, payload_hash, chain_hash. A reader can recompute
chain_hash for every row in order; a mismatch = tamper detected.
"""
import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from .models import LedgerEvent


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def append_event(
    db: Session,
    supplier_id: str,
    event_type: str,
    payload: dict[str, Any],
    actor: str = "system",
) -> LedgerEvent:
    last = (
        db.query(LedgerEvent)
        .filter(LedgerEvent.supplier_id == supplier_id)
        .order_by(LedgerEvent.id.desc())
        .first()
    )
    prev_hash = last.chain_hash if last else None

    occurred_at = datetime.utcnow()
    payload_hash = _sha256_hex(_canonical_json(payload))
    chain_input = f"{prev_hash or ''}|{payload_hash}|{occurred_at.isoformat()}"
    chain_hash = _sha256_hex(chain_input)

    event = LedgerEvent(
        supplier_id=supplier_id,
        event_type=event_type,
        actor=actor,
        occurred_at=occurred_at,
        payload=payload,
        prev_hash=prev_hash,
        payload_hash=payload_hash,
        chain_hash=chain_hash,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def verify_chain(db: Session, supplier_id: str) -> dict[str, Any]:
    events = (
        db.query(LedgerEvent)
        .filter(LedgerEvent.supplier_id == supplier_id)
        .order_by(LedgerEvent.id.asc())
        .all()
    )

    prev_hash: str | None = None
    for ev in events:
        expected_payload_hash = _sha256_hex(_canonical_json(ev.payload))
        if expected_payload_hash != ev.payload_hash:
            return {
                "valid": False,
                "broken_at_event_id": ev.id,
                "reason": "payload_hash mismatch (payload was modified)",
            }
        chain_input = f"{prev_hash or ''}|{ev.payload_hash}|{ev.occurred_at.isoformat()}"
        expected_chain_hash = _sha256_hex(chain_input)
        if expected_chain_hash != ev.chain_hash:
            return {
                "valid": False,
                "broken_at_event_id": ev.id,
                "reason": "chain_hash mismatch (event reordered or hash tampered)",
            }
        if ev.prev_hash != prev_hash:
            return {
                "valid": False,
                "broken_at_event_id": ev.id,
                "reason": "prev_hash mismatch (link to prior event broken)",
            }
        prev_hash = ev.chain_hash

    return {"valid": True, "events_verified": len(events)}
