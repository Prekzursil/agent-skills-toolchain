"""Moderation cases, disputes, and the revocations a case authorises.

THE ONE PROPERTY THAT MAKES THIS A PROCESS AND NOT A DELETE BUTTON
    An upheld appeal must be able to REVERSE a revocation. :func:`uphold_appeal` removes the
    revocation entry the case created and re-signs the list. A moderation system with no
    reversal path is a deletion system with a form attached, and the spec asks for a dispute
    process, not a takedown queue.

ROLE SEPARATION IS ENFORCED, NOT DOCUMENTED
    :func:`revoke` refuses unless the authority's publisher record carries a role in
    ``{registry-maintainer, moderator, security-response}``. A publisher cannot revoke a
    competitor, and -- more importantly -- cannot un-revoke itself.

HONEST SCOPE
    marketplace-first section 7.2 REFUTED moderation as operational dead weight for a
    one-user estate, and this build adopts that finding as a scope statement rather than as
    a reason to skip a required deliverable: the state machine, the role checks and the
    reversal path are executable and tested; no human moderation body exists.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import registry as reg
from . import schemas
from .canon import ensure_within, iso_now, read_json, write_json
from .crypto import sign_document

AUTHORITY_ROLES = frozenset({"registry-maintainer", "moderator", "security-response"})

#: Legal transitions. A transition not listed here is refused, so the log cannot record a
#: state change the process does not permit.
TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"under-review", "dismissed"}),
    "under-review": frozenset({"action-taken", "dismissed"}),
    "action-taken": frozenset({"appealed"}),
    "appealed": frozenset({"appeal-upheld", "appeal-rejected"}),
    "dismissed": frozenset(),
    "appeal-upheld": frozenset(),
    "appeal-rejected": frozenset(),
}


class ModerationError(RuntimeError):
    """An illegal transition, a missing case, or an authority without the role."""


def case_dir(registry_root: str | Path) -> Path:
    return Path(registry_root) / "moderation"


def open_case(
    registry_root: str | Path,
    *,
    case_id: str,
    name: str,
    version: str | None,
    publisher: str | None,
    reason_category: str,
    opened_by: str,
    note: str,
    evidence: list[str] | None = None,
    sla_days: int = 14,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or iso_now()
    subject: dict[str, Any] = {"name": name}
    if version:
        subject["version"] = version
    if publisher:
        subject["publisher"] = publisher
    case = {
        "case_id": case_id,
        "subject": subject,
        "opened_at": timestamp,
        "opened_by": opened_by,
        "reason_category": reason_category,
        "state": "open",
        "sla_days": sla_days,
        "events": [
            {
                "at": timestamp,
                "actor": opened_by,
                "transition": "none->open",
                "note": note,
                **({"evidence": evidence} if evidence else {}),
            }
        ],
    }
    schemas.validate("moderation-case", case)
    write_json(case_dir(registry_root) / f"{case_id.replace(':', '-')}.json", case)
    return case


def load_case(registry_root: str | Path, case_id: str) -> dict[str, Any]:
    path = case_dir(registry_root) / f"{case_id.replace(':', '-')}.json"
    if not path.is_file():
        raise ModerationError(f"no such moderation case: {case_id}")
    doc = read_json(path)
    schemas.validate("moderation-case", doc)
    return doc


def transition(
    registry_root: str | Path,
    case_id: str,
    *,
    to_state: str,
    actor: str,
    note: str,
    evidence: list[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    case = load_case(registry_root, case_id)
    current = case["state"]
    allowed = TRANSITIONS.get(current, frozenset())
    if to_state not in allowed:
        raise ModerationError(
            f"illegal transition {current} -> {to_state} for {case_id}; legal: {sorted(allowed) or 'none (terminal)'}"
        )
    event = {
        "at": now or iso_now(),
        "actor": actor,
        "transition": f"{current}->{to_state}",
        "note": note,
    }
    if evidence:
        event["evidence"] = evidence
    case["events"].append(event)
    case["state"] = to_state
    schemas.validate("moderation-case", case)
    write_json(case_dir(registry_root) / f"{case_id.replace(':', '-')}.json", case)
    return case


# --------------------------------------------------------------------------- #
# revocation list maintenance
# --------------------------------------------------------------------------- #


def load_or_init_revocation(
    registry_root: str | Path, index: dict[str, Any], *, now: str | None = None
) -> dict[str, Any]:
    doc = reg.load_revocation(registry_root, index)
    if doc is not None:
        return doc
    return {
        "schema_version": "1.0.0",
        "registry_id": index["registry_id"],
        "updated_at": now or iso_now(),
        "revocations": [],
    }


def revoke(
    registry_root: str | Path,
    *,
    scope: dict[str, Any],
    reason: str,
    severity: str,
    authority: str,
    maintainer_secret_hex: str,
    revocation_id: str | None = None,
    moderation_case: str | None = None,
    advisory_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Append a revocation and re-sign the list. Refuses an authority without the role."""
    timestamp = now or iso_now()
    index = reg.load_index(registry_root)
    record = reg.publisher_record(index, authority)
    if record is None or record.get("role") not in AUTHORITY_ROLES:
        raise ModerationError(
            f"authority {authority!r} has role {(record or {}).get('role')!r}; revocation requires one of "
            f"{sorted(AUTHORITY_ROLES)} -- a publisher must not be able to revoke, or un-revoke, on its own authority"
        )
    doc = load_or_init_revocation(registry_root, index, now=timestamp)
    rid = (
        revocation_id
        or "rev-"
        + hashlib.sha256(f"{scope}|{reason}|{timestamp}".encode("utf-8")).hexdigest()[
            :12
        ]
    )
    if not rid.startswith("rev:"):
        rid = "rev:" + rid.removeprefix("rev-")
    entry: dict[str, Any] = {
        "revocation_id": rid,
        "scope": scope,
        "reason": reason,
        "severity": severity,
        "revoked_at": timestamp,
        "authority": authority,
    }
    if moderation_case:
        entry["moderation_case"] = moderation_case
    if advisory_id:
        entry["advisory_id"] = advisory_id
    doc["revocations"] = [
        r for r in doc["revocations"] if r["revocation_id"] != rid
    ] + [entry]
    _write_revocation(registry_root, index, doc, maintainer_secret_hex, timestamp)
    return doc


def uphold_appeal(
    registry_root: str | Path,
    case_id: str,
    *,
    actor: str,
    note: str,
    maintainer_secret_hex: str,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Uphold an appeal: move the case AND REMOVE the revocation the case created.

    The reversal is the whole point. Returns ``(case, revocation_list)``.
    """
    timestamp = now or iso_now()
    case = load_case(registry_root, case_id)
    rid = case.get("resulting_revocation")
    case = transition(
        registry_root,
        case_id,
        to_state="appeal-upheld",
        actor=actor,
        note=note,
        now=timestamp,
    )
    index = reg.load_index(registry_root)
    doc = load_or_init_revocation(registry_root, index, now=timestamp)
    if rid:
        before = len(doc["revocations"])
        doc["revocations"] = [
            r for r in doc["revocations"] if r["revocation_id"] != rid
        ]
        if len(doc["revocations"]) == before:
            raise ModerationError(
                f"appeal upheld for {case_id} but revocation {rid} was not present to remove -- refusing to "
                "report a reversal that did not happen"
            )
    _write_revocation(registry_root, index, doc, maintainer_secret_hex, timestamp)
    return case, doc


def link_revocation(
    registry_root: str | Path, case_id: str, revocation_id: str
) -> dict[str, Any]:
    case = load_case(registry_root, case_id)
    case["resulting_revocation"] = revocation_id
    schemas.validate("moderation-case", case)
    write_json(case_dir(registry_root) / f"{case_id.replace(':', '-')}.json", case)
    return case


def _write_revocation(
    registry_root: str | Path,
    index: dict[str, Any],
    doc: dict[str, Any],
    maintainer_secret_hex: str,
    timestamp: str,
) -> Path:
    doc["updated_at"] = timestamp
    doc.pop("signature", None)
    doc["signature"] = sign_document(
        doc, "mkt.revocation.v1", maintainer_secret_hex, signed_at=timestamp
    )
    schemas.validate("revocation", doc)
    rel = index.get("revocation_path") or "revocation.json"
    return write_json(ensure_within(registry_root, rel), doc)


# --------------------------------------------------------------------------- #
# advisories
# --------------------------------------------------------------------------- #


def publish_advisory(
    registry_root: str | Path,
    *,
    advisory: dict[str, Any],
    authority: str,
    maintainer_secret_hex: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Add or replace an advisory and re-sign the list. Requires the security-response role."""
    timestamp = now or iso_now()
    index = reg.load_index(registry_root)
    record = reg.publisher_record(index, authority)
    if record is None or record.get("role") not in {
        "security-response",
        "registry-maintainer",
    }:
        raise ModerationError(
            f"authority {authority!r} may not publish advisories (role {(record or {}).get('role')!r})"
        )
    doc = reg.load_advisories(registry_root, index) or {
        "schema_version": "1.0.0",
        "registry_id": index["registry_id"],
        "updated_at": timestamp,
        "advisories": [],
    }
    doc["advisories"] = [
        a for a in doc["advisories"] if a["advisory_id"] != advisory["advisory_id"]
    ] + [advisory]
    doc["updated_at"] = timestamp
    doc.pop("signature", None)
    doc["signature"] = sign_document(
        doc, "mkt.advisory.v1", maintainer_secret_hex, signed_at=timestamp
    )
    schemas.validate("advisory", doc)
    rel = index.get("advisory_path") or "advisories.json"
    write_json(ensure_within(registry_root, rel), doc)
    return doc
