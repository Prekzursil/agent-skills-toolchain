"""Versioned checkpoint resume: migrate or refuse; never silently drop fields.

Catalog TST-0165: when the on-disk checkpoint predates CURRENT_SCHEMA,
resume must run a versioned migration or refuse loudly. A partial read that
drops unknown keys is the forbidden outcome.

Production tools/lib/handled-ledger.mjs is absent on this worktree. This
module is the executable SUT the named probes measure. It is not claimed to
be that ledger.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
CURRENT_SCHEMA = 2
UNIT = "TST-0165"

V1_KNOWN = frozenset(
    {
        "schema_version",
        "completed_unit_ids",
        "receipt_hashes",
        "open_nodes",
        "param_bindings",
        "legacy_cursor",
        "legacy_artifact_cache_key",
    }
)
V2_KNOWN = frozenset(
    {
        "schema_version",
        "completed_unit_ids",
        "receipt_hashes",
        "open_nodes",
        "param_bindings",
        "resume_cursor",
        "artifact_cache_key",
        "pinned_sha",
    }
)
V1_TO_V2 = {
    "legacy_cursor": "resume_cursor",
    "legacy_artifact_cache_key": "artifact_cache_key",
}
V2_REQUIRED = (
    "schema_version",
    "completed_unit_ids",
    "receipt_hashes",
    "open_nodes",
    "param_bindings",
    "resume_cursor",
    "artifact_cache_key",
    "pinned_sha",
)
PRODUCTION_LEDGER = "tools/lib/handled-ledger.mjs"
PRODUCTION_PROMPTS = "_USER-PROMPTS.md"


class ResumeRefuse(Exception):
    """Loud refusal. message is operator-facing; exit_code is nonzero."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def digest_file(path: Path) -> tuple[str, int]:
    import hashlib

    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(v, key))
        return out
    if isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            return {prefix: tuple(obj)}
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
        return out
    return {prefix: obj}


def fieldset_diff(before: dict[str, Any], after: dict[str, Any] | None) -> dict[str, Any]:
    """Account every old key: preserved, mapped (equal value), meaning-changed, or silent-drop."""
    fb = flatten(before)
    fa = flatten(after) if isinstance(after, dict) else {}
    rows: list[dict[str, Any]] = []
    silent: list[str] = []
    mapped: list[dict[str, Any]] = []
    preserved: list[str] = []
    meaning_changed: list[str] = []

    def dest_key_for(old_key: str) -> str | None:
        top = old_key.split(".")[0].split("[")[0]
        dest_top = V1_TO_V2.get(top)
        if not dest_top:
            return None
        return dest_top + old_key[len(top) :]

    for key, val in sorted(fb.items()):
        if key in fa:
            if key == "schema_version":
                rows.append(
                    {
                        "path": key,
                        "before": val,
                        "after": fa[key],
                        "account": "version-stamp",
                    }
                )
                preserved.append(key)
                continue
            if fa[key] == val:
                rows.append(
                    {"path": key, "before": val, "after": fa[key], "account": "preserved"}
                )
                preserved.append(key)
            else:
                rows.append(
                    {
                        "path": key,
                        "before": val,
                        "after": fa[key],
                        "account": "meaning-changed",
                    }
                )
                meaning_changed.append(key)
            continue
        dest = dest_key_for(key)
        if dest and dest in fa:
            if fa[dest] == val:
                rows.append(
                    {
                        "path": key,
                        "before": val,
                        "after": fa[dest],
                        "mapped_to": dest,
                        "account": "mapped",
                    }
                )
                mapped.append({"from": key, "to": dest})
            else:
                rows.append(
                    {
                        "path": key,
                        "before": val,
                        "after": fa[dest],
                        "mapped_to": dest,
                        "account": "meaning-changed",
                    }
                )
                meaning_changed.append(key)
            continue
        rows.append(
            {"path": key, "before": val, "after": None, "account": "silent-drop"}
        )
        silent.append(key)

    before_accounted = set(fb)
    mapped_dests = {m["to"] for m in mapped}
    added = sorted(k for k in fa if k not in before_accounted and k not in mapped_dests)
    return {
        "compared": len(rows),
        "silent_drops": silent,
        "mapped": mapped,
        "preserved": preserved,
        "meaning_changed": meaning_changed,
        "added": added,
        "rows": rows,
        "zero_silent_drops": len(silent) == 0 and len(meaning_changed) == 0,
    }


def _unknown(doc: dict[str, Any], known: frozenset[str]) -> list[str]:
    return sorted(k for k in doc.keys() if k not in known)


def _load(source: Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return copy.deepcopy(source)
    text = Path(source).read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResumeRefuse(
            f"resume: refuse {Path(source).as_posix()}: JSONDecodeError {exc.msg} "
            f"at line {exc.lineno} col {exc.colno} (unreadable checkpoint)."
        ) from exc
    if not isinstance(doc, dict):
        raise ResumeRefuse("resume: refuse checkpoint is not a JSON object.")
    return doc


def _migrate_v1(doc: dict[str, Any]) -> dict[str, Any]:
    unknown = _unknown(doc, V1_KNOWN)
    if unknown:
        raise ResumeRefuse(
            "resume: refuse unknown field "
            + ", ".join(unknown)
            + f" on schema_version=1; no partial read. File keeps {unknown[0]}."
        )
    missing = [k for k in V1_KNOWN if k not in doc]
    if missing:
        raise ResumeRefuse(
            "resume: refuse schema_version=1 missing required "
            + ", ".join(missing)
            + "."
        )
    out: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA,
        "completed_unit_ids": copy.deepcopy(doc["completed_unit_ids"]),
        "receipt_hashes": copy.deepcopy(doc["receipt_hashes"]),
        "open_nodes": copy.deepcopy(doc["open_nodes"]),
        "param_bindings": copy.deepcopy(doc["param_bindings"]),
        "resume_cursor": copy.deepcopy(doc["legacy_cursor"]),
        "artifact_cache_key": copy.deepcopy(doc["legacy_artifact_cache_key"]),
        "pinned_sha": "unpinned-v1-migrated",
    }
    return out


def _accept_v2(doc: dict[str, Any]) -> dict[str, Any]:
    unknown = _unknown(doc, V2_KNOWN)
    if unknown:
        raise ResumeRefuse(
            "resume: refuse unknown field "
            + ", ".join(unknown)
            + f" on schema_version={CURRENT_SCHEMA}; no partial read."
        )
    missing = [k for k in V2_REQUIRED if k not in doc]
    if missing:
        raise ResumeRefuse(
            f"resume: refuse schema_version={CURRENT_SCHEMA} missing required "
            + ", ".join(missing)
            + "."
        )
    if doc.get("schema_version") != CURRENT_SCHEMA:
        raise ResumeRefuse(
            f"resume: refuse schema_version={doc.get('schema_version')!r} "
            f"is not current ({CURRENT_SCHEMA})."
        )
    return copy.deepcopy(doc)


def resume_strict(source: Path | dict[str, Any]) -> dict[str, Any]:
    """Migrate v1 or load current v2. Unknown versions and extra keys refuse."""
    try:
        doc = _load(source)
    except ResumeRefuse as exc:
        return {
            "exit_code": exc.exit_code,
            "message": exc.message,
            "migrated": False,
            "from_version": None,
            "to_version": None,
            "checkpoint": None,
            "refused": True,
        }
    ver = doc.get("schema_version")
    try:
        if ver == 1:
            migrated = _migrate_v1(doc)
            return {
                "exit_code": 0,
                "message": (
                    "resume: migrated schema_version 1 -> 2; "
                    "legacy_cursor->resume_cursor, "
                    "legacy_artifact_cache_key->artifact_cache_key; "
                    "pinned_sha defaulted to unpinned-v1-migrated."
                ),
                "migrated": True,
                "from_version": 1,
                "to_version": CURRENT_SCHEMA,
                "checkpoint": migrated,
                "refused": False,
            }
        if ver == CURRENT_SCHEMA:
            loaded = _accept_v2(doc)
            return {
                "exit_code": 0,
                "message": (
                    f"resume: current schema_version={CURRENT_SCHEMA}; no migration."
                ),
                "migrated": False,
                "from_version": CURRENT_SCHEMA,
                "to_version": CURRENT_SCHEMA,
                "checkpoint": loaded,
                "refused": False,
            }
        raise ResumeRefuse(
            f"resume: refuse schema_version={ver!r}; expected 1 (migrate) or "
            f"{CURRENT_SCHEMA} (current). No partial read."
        )
    except ResumeRefuse as exc:
        return {
            "exit_code": exc.exit_code,
            "message": exc.message,
            "migrated": False,
            "from_version": ver if isinstance(ver, int) else None,
            "to_version": None,
            "checkpoint": None,
            "refused": True,
        }


def resume_lenient(source: Path | dict[str, Any]) -> dict[str, Any]:
    """Negative-control mutant: strip unknown keys and stamp schema_version=2.

    Does not remap v1 names. Missing v2 fields get empty defaults. Always
    exit_code 0 — that is the bug the field-set detector must catch.
    """
    try:
        doc = _load(source)
    except ResumeRefuse as exc:
        # Even the mutant refuses unreadable JSON; the silent-drop bug is
        # about unknown keys, not about parsing.
        return {
            "exit_code": exc.exit_code,
            "message": exc.message,
            "migrated": False,
            "from_version": None,
            "to_version": None,
            "checkpoint": None,
            "refused": True,
            "lenient": True,
        }
    dropped = [k for k in doc.keys() if k not in V2_KNOWN]
    out: dict[str, Any] = {}
    for k in V2_REQUIRED:
        if k == "schema_version":
            out[k] = CURRENT_SCHEMA
        elif k in doc:
            out[k] = copy.deepcopy(doc[k])
        elif k in ("completed_unit_ids", "open_nodes"):
            out[k] = []
        elif k in ("receipt_hashes", "param_bindings"):
            out[k] = {}
        else:
            out[k] = ""
    return {
        "exit_code": 0,
        "message": (
            f"resume: lenient load schema_version stamped to {CURRENT_SCHEMA}; "
            f"unknown keys ignored: {dropped}."
        ),
        "migrated": False,
        "from_version": doc.get("schema_version"),
        "to_version": CURRENT_SCHEMA,
        "checkpoint": out,
        "refused": False,
        "lenient": True,
        "ignored_keys": dropped,
    }


def fixture_docs() -> dict[str, Any]:
    v2 = {
        "schema_version": 2,
        "completed_unit_ids": ["IMP-0145", "IMP-0146"],
        "receipt_hashes": {
            "IMP-0145": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "IMP-0146": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        },
        "open_nodes": ["human-checkpoint.wait"],
        "param_bindings": {"workflow": "bp-resume", "phase": "7"},
        "resume_cursor": "phase-7-mid",
        "artifact_cache_key": "cache-xyz",
        "pinned_sha": "d4076fb9c3920000000000000000000000000000",
    }
    v1 = {
        "schema_version": 1,
        "completed_unit_ids": ["IMP-0145", "IMP-0146"],
        "receipt_hashes": {
            "IMP-0145": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "IMP-0146": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        },
        "open_nodes": ["human-checkpoint.wait"],
        "param_bindings": {"workflow": "bp-resume", "phase": "7"},
        "legacy_cursor": "phase-7-mid",
        "legacy_artifact_cache_key": "cache-xyz",
    }
    extra = dict(v1)
    extra["secret_operator_note"] = "do-not-drop-me"
    future = {
        "schema_version": 99,
        "completed_unit_ids": ["IMP-0145"],
        "payload": "future-only",
    }
    return {
        "current-v2": v2,
        "old-v1": v1,
        "old-v1-unknown-extra": extra,
        "future-v99": future,
    }


def materialize_fixtures() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for fid, doc in fixture_docs().items():
        p = FIXTURES / f"{fid}.json"
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths[fid] = p
    unreadable = FIXTURES / "unreadable.json"
    unreadable.write_text('{"schema_version": 1, "completed_unit_ids": [', encoding="utf-8")
    paths["unreadable"] = unreadable
    return paths


def production_census() -> dict[str, Any]:
    rows = []
    for rel in (PRODUCTION_LEDGER, PRODUCTION_PROMPTS, "tools/lib"):
        p = REPO / rel
        rows.append(
            {
                "path": rel,
                "exists": p.exists(),
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    present = any(r["exists"] for r in rows)
    return {
        "rows": rows,
        "handled_ledger_present": (REPO / PRODUCTION_LEDGER).is_file(),
        "any_named_input_present": present,
        "sut": "command-center/p2-wave/probes/TST-0165/engine.py:resume_strict",
        "note": (
            "Catalog inputs tools/lib/handled-ledger.mjs and _USER-PROMPTS.md "
            "are absent. Named probes measure resume_strict / resume_lenient "
            "in this probe directory, not a production ledger."
        ),
    }


def evaluate_strict(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or materialize_fixtures()
    out: dict[str, Any] = {}
    for fid, path in paths.items():
        rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
        result = resume_strict(path)
        before = None
        if fid != "unreadable":
            before = json.loads(path.read_text(encoding="utf-8"))
        diff = None
        if before is not None and result["checkpoint"] is not None:
            diff = fieldset_diff(before, result["checkpoint"])
        elif before is not None:
            diff = fieldset_diff(before, None)
        out[fid] = {
            "id": fid,
            "path": rel,
            "resume": result,
            "fieldset": diff,
        }
    return out


def evaluate_lenient(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    paths = paths or materialize_fixtures()
    out: dict[str, Any] = {}
    for fid in ("old-v1", "old-v1-unknown-extra", "current-v2"):
        path = paths[fid]
        before = json.loads(path.read_text(encoding="utf-8"))
        result = resume_lenient(path)
        diff = fieldset_diff(before, result["checkpoint"])
        out[fid] = {
            "id": fid,
            "path": path.relative_to(REPO).as_posix(),
            "resume": result,
            "fieldset": diff,
        }
    return out
