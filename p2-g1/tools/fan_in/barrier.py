"""Fan-in barrier: a plausible digest is not a receipt.

Cited by BLD-0055 (`tools/fan_in/barrier.py:admit`) and TST-0005.

EXISTENCE-BEFORE-PARSE is the load-bearing rule. Fan-in Test-Path-checks every
contracted output BEFORE parsing any digest. A well-formed prose sha256 whose
artifact is absent is REJECTED with digest_parsed=false. Parsing a digest
whose file does not exist is the measured Codex failure mode this module
closes.

The leaf existence predicate is Test-Path (``test_path_leaf``): the contracted
path must be a file on disk, not a directory and not a string that merely
appears in the digest. ``admit`` keeps ``admitted`` as the BLD-0055 boolean
so a digest-match against a live file still reduces.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

SHA256_TOKEN = re.compile(r"(?i)\bsha256:\s*([0-9a-f]{64})\b")
PHASE_EXIST = "existence_check"
PHASE_PARSE = "digest_parse"
REASON_ABSENT = "absent-artifact"
REASON_MISMATCH = "digest-mismatch"
REASON_MALFORMED = "digest-malformed"
REASON_OK = "ok"


def _join(root: Path | str, rel: str) -> Path:
    """Resolve a contracted relative path against the fan-in root."""
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    return Path(root) / rel


def test_path_leaf(root: Path | str, rel: str) -> bool:
    """PowerShell Test-Path equivalent: the contracted leaf must be a file."""
    return _join(root, rel).is_file()


def check_outputs_exist(root: Path | str, contracted: Iterable[str]) -> list[str]:
    """Return every contracted path that fails Test-Path. Never parses a digest."""
    absent: list[str] = []
    for rel in contracted:
        if not test_path_leaf(root, rel):
            absent.append(str(rel))
    return absent


def digest_well_formed(digest_text: str) -> bool:
    """True iff the prose independently contains a sha256 token. Not a receipt."""
    return SHA256_TOKEN.search(digest_text or "") is not None


def _parse_digest(digest_text: str, phases: list[str]) -> dict[str, Any]:
    """Extract sha256 from prose. Refuses unless existence_check already ran.

    Calling this before Test-Path is the defect TST-0005 injects. The gate is
    in this function body, not only in admit(), so a helper cannot skip it.
    """
    if PHASE_EXIST not in phases:
        raise RuntimeError("digest parse refused: existence check has not run")
    match = SHA256_TOKEN.search(digest_text or "")
    if match is None:
        return {
            "well_formed": False,
            "digest_sha256": None,
        }
    return {
        "well_formed": True,
        "digest_sha256": match.group(1).lower(),
    }


def _verdict(
    *,
    admitted: bool,
    status: str,
    reason_id: str,
    digest_parsed: bool,
    phases: list[str],
    message: str,
    absent_paths: list[str],
    digest_sha256: str | None = None,
    live_sha256: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Stable admit() payload. ``admitted`` remains the BLD-0055 boolean."""
    reason = "absent" if reason_id == REASON_ABSENT else reason_id
    out: dict[str, Any] = {
        "admitted": admitted,
        "status": status,
        "reason_id": reason_id,
        "reason": reason,
        "digest_parsed": digest_parsed,
        "digest_sha256": digest_sha256,
        "live_sha256": live_sha256,
        "phases": list(phases),
        "absent_paths": list(absent_paths),
        "message": message,
        "path": path,
    }
    return out


def admit(
    root: Path | str,
    rels: Iterable[str],
    digest_text: str,
) -> dict[str, Any]:
    """Admit contracted outputs only after Test-Path, then digest parse.

    Order is structural: check_outputs_exist is called before _parse_digest.
    An absent contracted path returns immediately; the digest is not parsed.
    """
    contracted = [str(rel) for rel in rels]
    phases: list[str] = []
    text = str(digest_text or "")

    # EXISTENCE-BEFORE-PARSE: Test-Path every contracted output first.
    absent = check_outputs_exist(root, contracted)
    phases.append(PHASE_EXIST)
    if absent:
        named = absent[0]
        return _verdict(
            admitted=False,
            status="REJECT",
            reason_id=REASON_ABSENT,
            digest_parsed=False,
            phases=phases,
            message=f"fan-in rejected: contracted output absent: {named}",
            absent_paths=absent,
            path=named,
        )

    parsed = _parse_digest(text, phases)
    phases.append(PHASE_PARSE)
    digest_sha = parsed.get("digest_sha256")
    live_by_rel: dict[str, str] = {}
    for rel in contracted:
        live_by_rel[rel] = hashlib.sha256(_join(root, rel).read_bytes()).hexdigest()

    if not parsed.get("well_formed") or not isinstance(digest_sha, str):
        first = contracted[0] if contracted else ""
        return _verdict(
            admitted=False,
            status="REJECT",
            reason_id=REASON_MALFORMED,
            digest_parsed=True,
            phases=phases,
            message=f"fan-in rejected: digest missing sha256 token: {first}",
            absent_paths=[],
            live_sha256=live_by_rel.get(first),
            path=first or None,
        )

    for rel, live_sha in live_by_rel.items():
        if digest_sha != live_sha:
            return _verdict(
                admitted=False,
                status="REJECT",
                reason_id=REASON_MISMATCH,
                digest_parsed=True,
                phases=phases,
                message=f"fan-in rejected: digest mismatch: {rel}",
                absent_paths=[],
                digest_sha256=digest_sha,
                live_sha256=live_sha,
                path=rel,
            )

    first = contracted[0] if contracted else ""
    return _verdict(
        admitted=True,
        status="ACCEPT",
        reason_id=REASON_OK,
        digest_parsed=True,
        phases=phases,
        message="fan-in admitted",
        absent_paths=[],
        digest_sha256=digest_sha,
        live_sha256=live_by_rel.get(first),
        path=first or None,
    )


def as_mapping(verdict: Mapping[str, Any]) -> Mapping[str, Any]:
    """Identity helper for callers that want a Mapping, not a mutation API."""
    return verdict
