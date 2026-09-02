#!/usr/bin/env python3
"""Sentinel-versus-completeness auditor for CNF-0168.

Two error directions, never a combined 'sentinel mismatch' count:

  Direction A (dangerous): the artifact carries an exact completion sentinel
  but fails completeness-minus-sentinel. That manufactures a pass.

  Direction B (spec 11313 / question half-2): the artifact satisfies
  completeness-minus-sentinel but does not carry its exact sentinel.

Completeness-minus-sentinel (P) is the mechanical subset that can be
evaluated on this worktree without the missing shipped reducer,
COMPLETION-GATES.json, or CNF-0162 receipt:

  C2  artifact exists
  C3  size >= MIN_BYTES
  C4  JSON parses (utf-8)
  C1  if a state field is present, it is not a self-declared failure

C5 (sentinel) is evaluated separately with an exact bounded token, so a
near-miss string cannot satisfy it. C6-C12 are NOT-CHECKED on the live
corpus and are named as such in the receipt.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SELF_UID = "CNF-0168"

# Declared constant. Rationale: ready_units.py text-body floor (~two sentences);
# CNF-0162 requires a meaningful size floor; 0-byte is the MSYS truncation
# signature and 1-byte is the forged-touch signature. 200 bytes is the smallest
# value that still rejects a sentinel-only file for typical SUCCESS:<id> tokens.
MIN_BYTES = 200
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
SUCCESS_FORM = "SUCCESS:{uid}"

# Fixture unit used only inside temp trees. Not a catalog id.
FIX_UID = "FIX-0001"
FIX_SENTINEL = "SUCCESS:FIX-0001"


def token_present(text: str, token: str) -> bool:
    """True iff `token` appears as an exact bounded token.

    A near-miss (extra suffix, missing letter, wrong id, case fold, space
    instead of colon) does not count. Alphanumeric / '_' / '-' / ':' on either
    side extends the token; quotes and whitespace do not.
    """
    token = (token or "").strip()
    if not token:
        return False
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_:-]){re.escape(token)}(?![A-Za-z0-9_:-])"
    )
    return bool(pattern.search(text))


def success_sentinel(unit_id: str) -> str:
    return SUCCESS_FORM.format(uid=unit_id)


def carries_sentinel(text: str, *, unit_id: str, declared: str | None) -> bool:
    """C5: exact declared sentinel if provided, else exact SUCCESS:<unit-id>."""
    declared = (declared or "").strip()
    if declared:
        return token_present(text, declared)
    if UID_RE.match(unit_id or ""):
        return token_present(text, success_sentinel(unit_id))
    return False


def completeness_minus_sentinel(path: Path) -> tuple[bool, str]:
    """P: C2, C3, C4-parse, C1-terminal-state. Does not look at the sentinel."""
    if not path.is_file():
        return False, "absent"
    try:
        size = path.stat().st_size
    except OSError as exc:
        return False, f"unreadable:{type(exc).__name__}"
    if size <= 0:
        return False, "empty"
    if size < MIN_BYTES:
        return False, f"below-min-bytes:{size}<{MIN_BYTES}"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "not-utf8"
    except OSError as exc:
        return False, f"read-error:{type(exc).__name__}"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return False, "unparseable"
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st.upper() in NOT_DELIVERING:
            return False, f"self-declared:{st.upper()}"
    return True, "complete-minus-sentinel"


def classify_path(
    path: Path, *, unit_id: str, declared: str | None
) -> dict[str, Any]:
    p_ok, p_why = completeness_minus_sentinel(path)
    text = ""
    if path.is_file():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    c5 = carries_sentinel(text, unit_id=unit_id, declared=declared)
    if c5 and not p_ok:
        direction = "A"
    elif p_ok and not c5:
        direction = "B"
    elif p_ok and c5:
        direction = "healthy"
    else:
        direction = "neither"
    return {
        "id": unit_id,
        "path": str(path),
        "direction": direction,
        "completeness_minus_sentinel": p_ok,
        "completeness_reason": p_why,
        "sentinel_present": c5,
        "declared_sentinel": declared,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def healthy_doc(uid: str = FIX_UID, sentinel: str | None = None) -> dict[str, Any]:
    token = sentinel or success_sentinel(uid)
    return {
        "unit_id": uid,
        "state": "SUCCESS",
        "sentinel": token,
        "title": "Healthy completeness-and-sentinel pair for CNF-0168.",
        "body": (
            "This control artifact clears the 200-byte floor, parses as JSON, "
            "declares a valid terminal state, and carries the exact sentinel "
            f"{token} as a bounded token. Padding ensures truncation still "
            "leaves the sentinel while breaking parse. " + ("pad " * 40)
        ),
    }


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def make_truncated(healthy_bytes: bytes, sentinel: str) -> bytes:
    """Leave the sentinel in place; drop the tail so JSON no longer parses.

    Size stays >= MIN_BYTES so Direction A is a truncated-but-still-plausible
    file, not a below-floor stub. Catalog: 'truncate an artifact while leaving
    its sentinel'.
    """
    text = healthy_bytes.decode("utf-8")
    if sentinel not in text:
        raise ValueError("healthy fixture lost its sentinel before truncation")
    truncated = text[:-40]
    if sentinel not in truncated:
        raise ValueError("truncation dropped the sentinel")
    if len(truncated.encode("utf-8")) < MIN_BYTES:
        raise ValueError("truncated fixture fell below MIN_BYTES")
    return truncated.encode("utf-8")


def near_misses(uid: str) -> list[tuple[str, str]]:
    """(label, impostor-string) that must NOT satisfy C5 for uid."""
    exact = success_sentinel(uid)
    return [
        ("suffix", exact + "X"),
        ("wrong-id", exact[:-1] + "2" if exact[-1] != "2" else exact[:-1] + "3"),
        ("missing-letter", exact.replace("SUCCESS", "SUCCES", 1)),
        ("space-not-colon", exact.replace(":", " ", 1)),
        ("case-fold", exact.lower()),
    ]


def run_controls(root: Path | None = None) -> dict[str, Any]:
    """Plant both-states, two known-broken, and sentinel-format near-misses."""
    cleanup = False
    if root is None:
        tmp = tempfile.TemporaryDirectory(prefix="cnf0168-")
        root = Path(tmp.name)
        cleanup = True
    try:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        healthy_path = root / "healthy.json"
        write_json(healthy_path, healthy_doc())
        healthy = classify_path(
            healthy_path, unit_id=FIX_UID, declared=FIX_SENTINEL
        )

        truncated_path = root / "truncated-with-sentinel.json"
        truncated_path.write_bytes(
            make_truncated(healthy_path.read_bytes(), FIX_SENTINEL)
        )
        direction_a = classify_path(
            truncated_path, unit_id=FIX_UID, declared=FIX_SENTINEL
        )

        missing_path = root / "complete-without-sentinel.json"
        missing_doc = healthy_doc()
        missing_doc["sentinel"] = "ABSENT"
        missing_doc["body"] = missing_doc["body"].replace(FIX_SENTINEL, "NO-TOKEN")
        write_json(missing_path, missing_doc)
        if FIX_SENTINEL in missing_path.read_text(encoding="utf-8"):
            raise RuntimeError("complete-without-sentinel fixture still has token")
        direction_b = classify_path(
            missing_path, unit_id=FIX_UID, declared=FIX_SENTINEL
        )

        near = []
        for label, impostor in near_misses(FIX_UID):
            doc = healthy_doc()
            doc["sentinel"] = impostor
            doc["body"] = doc["body"].replace(FIX_SENTINEL, impostor)
            path = root / f"near-miss-{label}.json"
            write_json(path, doc)
            text = path.read_text(encoding="utf-8")
            fired = token_present(text, FIX_SENTINEL)
            row = classify_path(path, unit_id=FIX_UID, declared=FIX_SENTINEL)
            near.append(
                {
                    "label": label,
                    "impostor": impostor,
                    "exact_token_fired": fired,
                    "direction": row["direction"],
                    "sentinel_present": row["sentinel_present"],
                }
            )

        healthy_silent = healthy["direction"] == "healthy"
        a_fires = direction_a["direction"] == "A" and direction_a["sentinel_present"]
        b_fires = direction_b["direction"] == "B" and not direction_b["sentinel_present"]
        near_ok = all(
            (not n["exact_token_fired"]) and (not n["sentinel_present"]) for n in near
        )
        return {
            "pass": bool(healthy_silent and a_fires and b_fires and near_ok),
            "healthy_silent": healthy_silent,
            "direction_a_fires_on_truncate": a_fires,
            "direction_b_fires_on_complete_without_sentinel": b_fires,
            "near_miss_does_not_count": near_ok,
            "healthy": healthy,
            "direction_a": direction_a,
            "direction_b": direction_b,
            "near_misses": near,
            "min_bytes": MIN_BYTES,
        }
    finally:
        if cleanup:
            tmp.cleanup()


def load_catalog_units() -> list[dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    return [u for u in units if isinstance(u, dict) and u.get("id")]


def live_census(
    repo: Path | None = None, *, skip_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Classify every catalog output_path that exists. Skip `skip_ids`."""
    repo = repo or REPO
    skip = set(skip_ids or ()) | {SELF_UID}
    direction_a: list[dict[str, Any]] = []
    direction_b: list[dict[str, Any]] = []
    healthy: list[str] = []
    neither: list[dict[str, Any]] = []
    absent = 0
    present = 0
    for unit in load_catalog_units():
        uid = str(unit.get("id") or "")
        if uid in skip:
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel:
            continue
        path = repo / rel
        if not path.is_file():
            absent += 1
            continue
        present += 1
        declared = unit.get("completion_sentinel")
        declared_s = declared.strip() if isinstance(declared, str) else None
        row = classify_path(path, unit_id=uid, declared=declared_s)
        slim = {
            "id": uid,
            "path": rel,
            "reason": row["completeness_reason"],
            "declared_sentinel": declared_s,
        }
        if row["direction"] == "A":
            direction_a.append(slim)
        elif row["direction"] == "B":
            direction_b.append(slim)
        elif row["direction"] == "healthy":
            healthy.append(uid)
        else:
            neither.append(slim)
    return {
        "min_bytes": MIN_BYTES,
        "present_artifacts": present,
        "absent_output_paths": absent,
        "skipped_ids": sorted(skip),
        "direction_a_sentinel_on_incomplete": {
            "count": len(direction_a),
            "ids": [r["id"] for r in direction_a],
            "rows": direction_a,
        },
        "direction_b_complete_without_sentinel": {
            "count": len(direction_b),
            "ids": [r["id"] for r in direction_b],
            "rows": direction_b,
        },
        "healthy_count": len(healthy),
        "healthy_ids": healthy,
        "neither_count": len(neither),
        "neither_ids": [r["id"] for r in neither],
        "neither_rows": neither,
        "combined_mismatch_forbidden": True,
    }


def reviewer_plants(root: Path | None = None) -> dict[str, Any]:
    """Independent reviewer: plant one fault in each direction and detect both."""
    return run_controls(root)


def directions_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Read the two-direction block from a receipt_core or legacy top-level shape."""
    top = doc.get("directions")
    if isinstance(top, dict) and "sentinel_on_incomplete" in top:
        return top
    report = doc.get("report")
    if isinstance(report, dict):
        nested = report.get("directions")
        if isinstance(nested, dict) and "sentinel_on_incomplete" in nested:
            return nested
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        nested = ext.get("directions")
        if isinstance(nested, dict) and "sentinel_on_incomplete" in nested:
            return nested
    return {}


def plants_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Reviewer plants live in report/extensions; reviewer{} forbids extra keys."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("plants"), dict):
        return report["plants"]
    ext = doc.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("plants"), dict):
        return ext["plants"]
    rev = doc.get("reviewer")
    if isinstance(rev, dict) and isinstance(rev.get("plants"), dict):
        return rev["plants"]
    return {}
