"""Evidence-capture — pure append-to-store logic (WU-2F + WU-2L).

A verified :class:`~wearables.datum.Datum` is serialized to a structured JSONL
record and appended to the project evidence store (a path passed in). This is
the PURE function the deferred ``PostToolUse`` capture hook will call; the hook
wrapper itself is live-deploy.

Invariants enforced here:
  * **Provenance required** (WU-2L): a Datum missing complete provenance is
    REFUSED (:class:`~wearables.provenance.ProvenanceError`) before any write.
  * **Egress-scrub runs BEFORE write, fail-CLOSED** (WU-2F): the serialized
    bytes are passed through :func:`~wearables.security.egress.scrub_secrets`
    so no secret lands in persisted bytes. If scrubbing raises, the write is
    refused (the scrub call is fail-closed) rather than writing raw bytes.
  * **Idempotency**: a Datum already present (by content fingerprint) is NOT
    appended again; the store stays deduped across repeated captures.

``source_class`` is stamped on every record (carried verbatim from the Datum).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .datum import Datum
from .provenance import provenance_fields, require_provenance
from .security.egress import scrub_secrets


def _record(datum: Datum) -> dict:
    """Build the structured, JSON-serializable evidence record."""
    rec = {
        "compound_id": datum.compound_id,
        "target_id": datum.target_id,
        "target_context": datum.target_context,
        "metric": datum.metric,
        "value": datum.value,
        "value_as_reported": datum.value_as_reported,
        "unit": datum.unit,
        "unit_as_reported": datum.unit_as_reported,
        "n": datum.n,
        "confidence": datum.confidence,
        "source": datum.source,
        "source_class": datum.source_class,
        "flags": list(datum.flags),
        "provenance": provenance_fields(datum),
    }
    rec["fingerprint"] = _fingerprint(rec)
    return rec


def _fingerprint(record: dict) -> str:
    """Stable content hash over the identity-bearing fields (idempotency key)."""
    payload = {k: v for k, v in record.items() if k != "fingerprint"}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _scrub_line(record: dict) -> str:
    """Serialize + secret-scrub a record to a single JSONL line (fail-CLOSED).

    The scrub call itself is fail-closed: any failure propagates so the caller
    refuses to write rather than persisting un-scrubbed bytes.
    """
    raw = json.dumps(record, sort_keys=True, ensure_ascii=True, default=str)
    scrubbed = scrub_secrets(raw)
    return scrubbed


def _existing_fingerprints(path: Path) -> set[str]:
    """Read the fingerprints already present in the store (empty if absent)."""
    if not path.exists():
        return set()
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        fp = rec.get("fingerprint")
        if fp:
            seen.add(fp)
    return seen


def append_datum(datum: Datum, store_path) -> bool:
    """Append a verified Datum to the JSONL evidence store at ``store_path``.

    Returns ``True`` if a new record was written, ``False`` if the Datum was
    already present (idempotent no-op). Refuses (raises) when provenance is
    incomplete or the secret-scrub fails.
    """
    require_provenance(datum)  # WU-2L: fail-closed before any write
    path = Path(store_path)
    record = _record(datum)
    line = _scrub_line(record)  # WU-2F: scrub BEFORE write, fail-closed

    seen = _existing_fingerprints(path)
    if record["fingerprint"] in seen:
        return False  # idempotent: already captured

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return True


def capture(datum: Datum) -> Datum:
    """Pipeline ``capture`` stage: validate provenance, echo the Datum.

    Replaces the Phase-1 ``capture_stub``. Persistence is driven by the deferred
    PostToolUse hook (via :func:`append_datum`); the in-pipeline stage only
    enforces the provenance contract and passes the Datum through.
    """
    require_provenance(datum)
    return datum
