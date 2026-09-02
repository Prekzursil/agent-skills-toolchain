"""Independent ARTIFACT-MANIFEST vs DISK gate for CNF-0192.

Reads the filesystem (worktree bytes) rather than the manifest's own present
claims. A manifest row is never evidence for another row. Trap keys
``claimed_present`` / ``present`` / ``exists`` are ignored.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from consumer import CONSUMER_ID, consume  # noqa: E402

# Floor is 16 bytes so a 0-byte and a 1-byte planted file both fail. A JSON
# object with the consumer's required keys cannot fit in 15 bytes, so the
# default is not decorative. Hashing is worktree bytes (CRLF normalized).
MIN_BYTES = 16
TRAP_KEYS = frozenset({"claimed_present", "present", "exists"})
FORBIDDEN_EVIDENCE_SOURCES = frozenset(
    {
        "manifest-claim",
        "manifest-present",
        "claimed_present",
        "peer-manifest-entry",
        "manifest-as-own-evidence",
    }
)
EXCEPTION_STATES = frozenset(
    {
        "MISSING",
        "EMPTY",
        "BELOW-MIN-SIZE",
        "UNREADABLE-BY-CONSUMER",
        "HASH-MISMATCH",
        "CIRCULAR-EVIDENCE",
    }
)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def list_disk(root: Path) -> list[dict[str, Any]]:
    """CNF-0192-DISK-LISTING: independent pathlib walk, not a manifest rewrite."""
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        sha, nbytes = digest_bytes(raw)
        rows.append(
            {
                "path": rel,
                "bytes": nbytes,
                "sha256": sha,
                "listing_source": "pathlib.Path.rglob+read_bytes",
            }
        )
    return rows


def list_disk_os_walk(root: Path) -> list[str]:
    """Second listing instrument (os.walk) for the independent reviewer relist."""
    import os

    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abs_p = Path(dirpath) / name
            found.append(abs_p.relative_to(root).as_posix())
    return sorted(found)


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify(manifest_path: Path) -> dict[str, Any]:
    """Verify every manifested path against disk + consumer. Root = manifest parent."""
    manifest_path = manifest_path.resolve()
    root = manifest_path.parent
    listing = list_disk(root)
    listing_by_path = {row["path"]: row for row in listing}
    doc = _load_manifest(manifest_path)
    items = doc.get("artifacts") or []
    entries: list[dict[str, Any]] = []
    counts = {
        "verified": 0,
        "missing": 0,
        "empty": 0,
        "unreadable_by_consumer": 0,
        "below_min_size": 0,
        "hash_mismatch": 0,
        "circular_evidence": 0,
        "total": len(items),
    }

    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError(f"malformed manifest row in {manifest_path}")
        eid = str(item.get("id") or item["path"])
        rel = item["path"].replace("\\", "/")
        claimed_sha = str(item.get("sha256") or "")
        trap_used = [k for k in TRAP_KEYS if k in item]
        entry = _verify_one(
            root=root,
            eid=eid,
            rel=rel,
            claimed_sha=claimed_sha,
            listing_by_path=listing_by_path,
            trap_keys_present=trap_used,
        )
        entries.append(entry)
        _tally(counts, entry["terminal_state"])

    circularity = _circularity(entries, manifest_path.name)
    if not circularity["ok"]:
        counts["circular_evidence"] = len(circularity["violations"])

    terminal_lines = [
        _terminal_line(e) for e in entries
    ]
    exceptions = sum(counts[k] for k in (
        "missing",
        "empty",
        "unreadable_by_consumer",
        "below_min_size",
        "hash_mismatch",
        "circular_evidence",
    ))
    bucket = "SUCCESS" if exceptions == 0 and counts["verified"] == counts["total"] and counts["total"] > 0 else "REFUTED"
    terminal_lines.append(
        f"TERMINAL-BUCKET {bucket} verified={counts['verified']} missing={counts['missing']} "
        f"empty={counts['empty']} unreadable-by-consumer={counts['unreadable_by_consumer']} "
        f"below-min-size={counts['below_min_size']} hash-mismatch={counts['hash_mismatch']} "
        f"total={counts['total']}"
    )
    return {
        "bucket_terminal_state": bucket,
        "min_bytes": MIN_BYTES,
        "min_bytes_rationale": (
            "16 bytes is below any valid consumer JSON object and above 0-byte/1-byte plants"
        ),
        "bytes_hashed": "worktree",
        "hash_normalization": "CRLF-to-LF",
        "manifest_path": str(manifest_path),
        "artifact_root": str(root),
        "entries": entries,
        "counts": counts,
        "disk_listing": listing,
        "circularity": circularity,
        "terminal_lines": terminal_lines,
        "walker": {
            "module": "command-center/p2-wave/probes/CNF-0192/gate.py",
            "function": "list_disk",
            "marker": "CNF-0192-DISK-LISTING",
            "independent_of_manifest_writer": True,
        },
        "consumer_id": CONSUMER_ID,
        "exceptions": exceptions,
    }


def _verify_one(
    *,
    root: Path,
    eid: str,
    rel: str,
    claimed_sha: str,
    listing_by_path: dict[str, dict[str, Any]],
    trap_keys_present: list[str],
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    disk_row = listing_by_path.get(rel)
    target = root / rel
    if disk_row is None and not target.is_file():
        return {
            "id": eid,
            "path": rel,
            "terminal_state": "MISSING",
            "bytes": 0,
            "sha256": None,
            "stat_only": False,
            "opened": False,
            "trap_keys_ignored": trap_keys_present,
            "consumer": None,
            "evidence": [
                {
                    "source": "disk-listing-this-run",
                    "path": rel,
                    "present_in_listing": False,
                    "note": "path absent from independent listing and Path.is_file is false",
                }
            ],
        }

    if disk_row is None and target.is_file():
        raw = target.read_bytes()
        sha, nbytes = digest_bytes(raw)
        disk_row = {"path": rel, "bytes": nbytes, "sha256": sha}

    evidence.append(
        {
            "source": "disk-listing-this-run",
            "path": rel,
            "bytes": disk_row["bytes"],
            "sha256": disk_row["sha256"],
            "present_in_listing": rel in listing_by_path,
        }
    )
    raw = target.read_bytes()
    sha, nbytes = digest_bytes(raw)
    evidence.append(
        {
            "source": "file-open-this-run",
            "path": rel,
            "bytes_read": len(raw),
            "sha256": sha,
        }
    )

    if nbytes == 0:
        return {
            "id": eid,
            "path": rel,
            "terminal_state": "EMPTY",
            "bytes": 0,
            "sha256": sha,
            "stat_only": False,
            "opened": True,
            "trap_keys_ignored": trap_keys_present,
            "consumer": consume(target),
            "evidence": evidence,
        }
    if nbytes < MIN_BYTES:
        return {
            "id": eid,
            "path": rel,
            "terminal_state": "BELOW-MIN-SIZE",
            "bytes": nbytes,
            "sha256": sha,
            "stat_only": False,
            "opened": True,
            "trap_keys_ignored": trap_keys_present,
            "consumer": None,
            "evidence": evidence,
            "min_bytes": MIN_BYTES,
        }

    consumed = consume(target)
    evidence.append(
        {
            "source": "consumer-open-parse-extract",
            "path": rel,
            "consumer_id": consumed.get("consumer_id"),
            "ok": consumed.get("ok"),
            "first_key": consumed.get("first_key"),
            "bytes_read": consumed.get("bytes_read"),
            "class": consumed.get("class"),
        }
    )
    if not consumed.get("ok"):
        return {
            "id": eid,
            "path": rel,
            "terminal_state": "UNREADABLE-BY-CONSUMER",
            "bytes": nbytes,
            "sha256": sha,
            "stat_only": False,
            "opened": True,
            "trap_keys_ignored": trap_keys_present,
            "consumer": consumed,
            "evidence": evidence,
        }
    if claimed_sha and claimed_sha != sha:
        return {
            "id": eid,
            "path": rel,
            "terminal_state": "HASH-MISMATCH",
            "bytes": nbytes,
            "sha256": sha,
            "claimed_sha256": claimed_sha,
            "stat_only": False,
            "opened": True,
            "trap_keys_ignored": trap_keys_present,
            "consumer": consumed,
            "evidence": evidence,
        }
    return {
        "id": eid,
        "path": rel,
        "terminal_state": "VERIFIED",
        "bytes": nbytes,
        "sha256": sha,
        "stat_only": False,
        "opened": True,
        "trap_keys_ignored": trap_keys_present,
        "consumer": consumed,
        "evidence": evidence,
    }


def _tally(counts: dict[str, int], state: str) -> None:
    mapping = {
        "VERIFIED": "verified",
        "MISSING": "missing",
        "EMPTY": "empty",
        "UNREADABLE-BY-CONSUMER": "unreadable_by_consumer",
        "BELOW-MIN-SIZE": "below_min_size",
        "HASH-MISMATCH": "hash_mismatch",
        "CIRCULAR-EVIDENCE": "circular_evidence",
    }
    key = mapping.get(state)
    if key:
        counts[key] += 1


def _circularity(entries: list[dict[str, Any]], manifest_name: str) -> dict[str, Any]:
    violations: list[str] = []
    for entry in entries:
        for ev in entry.get("evidence") or []:
            src = str(ev.get("source") or "")
            if src in FORBIDDEN_EVIDENCE_SOURCES:
                violations.append(f"{entry['id']}: forbidden source {src}")
            cited = str(ev.get("path") or "").replace("\\", "/")
            if cited.endswith("/" + manifest_name) or cited == manifest_name:
                if entry["path"] != cited:
                    violations.append(
                        f"{entry['id']}: cited {manifest_name} as evidence of {entry['path']}"
                    )
            if src == "peer-manifest-entry":
                violations.append(f"{entry['id']}: peer entry used as evidence")
    return {
        "ok": len(violations) == 0,
        "rule": "disk listing + file open + consumer; never the manifest's own claims",
        "violations": violations,
        "trap_keys_are_not_evidence": True,
    }


def _terminal_line(entry: dict[str, Any]) -> str:
    cons = entry.get("consumer") or {}
    first = cons.get("first_key") or "-"
    sha = entry.get("sha256") or "-"
    return (
        f"TERMINAL {entry['id']} {entry['terminal_state']} path={entry['path']} "
        f"bytes={entry.get('bytes')} sha256={sha} consumer={CONSUMER_ID} "
        f"first_key={first} opened={entry.get('opened')} stat_only={entry.get('stat_only')}"
    )


def uses_trap_keys_for_verdict(source: str) -> bool:
    """True when source reads claimed_present/present/exists off a manifest item."""
    import ast

    tree = ast.parse(source)
    trap = TRAP_KEYS
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "get" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and arg0.value in trap:
                    return True
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and sl.value in trap:
                return True
    return False
