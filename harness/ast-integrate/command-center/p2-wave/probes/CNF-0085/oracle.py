#!/usr/bin/env python3
"""Reference oracle: 12 independently-addressable booleans, then first-fail.

Written as a full condition vector so agreement with the runner is per-condition,
not an aggregate boolean. Same spec labels as spec.py. Evaluation is local to
this module (the production reducer is not imported). Receipts are the
production envelope: artifacts[], sentinel, manifest_registration, etc.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from spec import CONDITION_IDS

PASS = "PASS"
FAIL = "FAIL"

_SUCCESS_TERMINAL = frozenset({"SUCCESS", "COMPLETED"})
_SENTINEL_ID = re.compile(
    r"^(?:SUCCESS|FAILED|SENTINEL):(?P<uid>[A-Z][A-Z0-9]*-[0-9]{4})\b"
)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_ANCHOR_FILE_LINE = re.compile(
    r"^(?P<path>[^\s:]+(?::[^\s:\\/]*)?):(?P<line>\d+)(?:-(?P<end>\d+))?$"
)
_BLOCK_SEV = frozenset({"P0", "P1"})
_RESOLVED = frozenset(
    {
        "resolved",
        "waived-by-owner",
        "superseded",
        "closed",
        "externally-blocked-proven",
    }
)


def _result(vector: list[bool], reasons: dict[str, str]) -> dict[str, Any]:
    failing = None
    reason = "all 12 conditions held"
    for i, held in enumerate(vector):
        if not held:
            failing = CONDITION_IDS[i]
            reason = reasons.get(failing, f"{failing} false")
            break
    return {
        "verdict": PASS if failing is None else FAIL,
        "failing_condition_id": failing,
        "reason": reason,
        "evaluator": "reference-oracle",
        "condition_vector": {CONDITION_IDS[i]: vector[i] for i in range(12)},
    }


def _primaries(receipt: dict) -> list[dict[str, Any]]:
    raw = receipt.get("artifacts")
    arts = [a for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []
    primary = [a for a in arts if a.get("role") == "primary"]
    return primary or arts


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return root / raw.replace("\\", "/")


def _seq(value: Any) -> list[Any]:
    return [x for x in value] if isinstance(value, (list, tuple)) else []


def _c1(receipt: Any, reasons: dict[str, str]) -> bool:
    if not isinstance(receipt, dict):
        reasons["C1"] = "receipt is not an object"
        return False
    state = receipt.get("state")
    sentinel = receipt.get("sentinel")
    if not isinstance(state, str) or state not in _SUCCESS_TERMINAL:
        reasons["C1"] = f"state {state!r} is not success-class"
        return False
    if isinstance(sentinel, str) and sentinel.startswith("FAILED:"):
        reasons["C1"] = "success-class state with FAILED sentinel"
        return False
    if not isinstance(sentinel, str) or not sentinel:
        reasons["C1"] = "success-class state with no sentinel"
        return False
    return True


def _c2(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    prims = _primaries(receipt)
    if not prims:
        reasons["C2"] = "receipt declares no artifacts (digest is not a receipt)"
        return False
    for art in prims:
        raw = art.get("path")
        if not isinstance(raw, str) or not raw:
            reasons["C2"] = "artifact entry carries no path"
            return False
        path = _resolve(repo, raw)
        if not path.is_file():
            reasons["C2"] = (
                f"stat says absent: {raw}; exit={receipt.get('process_exit_code')!r} "
                "is not success"
            )
            return False
        real = path.stat().st_size
        declared = art.get("bytes")
        if isinstance(declared, int) and declared != real:
            reasons["C2"] = f"declared bytes {declared} != {real} on disk"
            return False
        sha = art.get("sha256")
        if isinstance(sha, str) and _SHA256_HEX.match(sha):
            worktree = hashlib.sha256(path.read_bytes()).hexdigest()
            lf = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if sha not in {worktree, lf}:
                reasons["C2"] = "re-hash mismatch; a plausible digest is not a receipt"
                return False
    return True


def _c3(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    prims = _primaries(receipt)
    floor = receipt.get("min_bytes_threshold")
    if not prims:
        reasons["C3"] = "no artifacts to size"
        return False
    missing = [
        a.get("path")
        for a in prims
        if not _resolve(repo, str(a.get("path") or "")).is_file()
    ]
    if missing:
        reasons["C3"] = "artifact absent; size not measurable (C2 owns this)"
        return False
    if type(floor) is not int or floor < 1:
        reasons["C3"] = f"floor {floor!r} is not a positive int"
        return False
    for art in prims:
        path = _resolve(repo, str(art.get("path")))
        size = path.stat().st_size
        if size < 1:
            reasons["C3"] = "empty file"
            return False
        if size < floor:
            reasons["C3"] = f"{size}B < floor {floor}"
            return False
    return True


class _ParseFail:
    """Sentinel distinct from None (absent) and from a parsed value."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _ParseFail()


def _c4(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    prims = _primaries(receipt)
    if not prims:
        reasons["C4"] = "no artifacts to parse"
        return False
    paths = [_resolve(repo, str(a.get("path"))) for a in prims]
    if any(not p.is_file() for p in paths):
        reasons["C4"] = "artifact absent, cannot parse (C2 owns this)"
        return False
    schema_rel = receipt.get("schema_path")
    if not isinstance(schema_rel, str) or not schema_rel.strip():
        reasons["C4"] = "no schema_path"
        return False
    sp = _resolve(repo, schema_rel)
    if not sp.is_file():
        reasons["C4"] = "schema file missing"
        return False
    schema = _load_json(sp)
    if isinstance(schema, _ParseFail) or not isinstance(schema, dict):
        reasons["C4"] = "schema unreadable"
        return False
    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        reasons["C4"] = "jsonschema not installed"
        return False
    for art, path in zip(prims, paths):
        body = _load_json(path)
        if isinstance(body, _ParseFail):
            reasons["C4"] = "JSON parse failed"
            return False
        try:
            jsonschema.validate(body, schema)
        except jsonschema.ValidationError as exc:
            reasons["C4"] = f"schema validation failed: {exc.message}"
            return False
        except jsonschema.SchemaError as exc:
            reasons["C4"] = f"schema is invalid: {exc.message}"
            return False
    return True


def _c5(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    sentinel = receipt.get("sentinel")
    unit_id = receipt.get("unit_id")
    if not isinstance(sentinel, str) or not sentinel:
        reasons["C5"] = "no sentinel declared"
        return False
    m = _SENTINEL_ID.match(sentinel)
    if not m:
        reasons["C5"] = "sentinel matches no known family"
        return False
    if isinstance(unit_id, str) and m.group("uid") != unit_id:
        reasons["C5"] = f"sentinel uid {m.group('uid')} != {unit_id}"
        return False
    prims = _primaries(receipt)
    if not prims:
        reasons["C5"] = "no artifact to carry the sentinel"
        return False
    checked = 0
    for art in prims:
        path = _resolve(repo, str(art.get("path")))
        if not path.is_file():
            reasons["C5"] = "artifact absent; sentinel not measurable"
            return False
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            reasons["C5"] = "artifact not UTF-8 text"
            return False
        checked += 1
        if sentinel not in text:
            reasons["C5"] = "artifact does not carry the sentinel verbatim"
            return False
    return checked > 0


def _anchor_ok(anchor: str, repo: Path) -> bool:
    m = _ANCHOR_FILE_LINE.match(anchor.strip())
    if not m:
        return False
    path = _resolve(repo, m.group("path"))
    if not path.is_file():
        return False
    line = int(m.group("line"))
    n = len(path.read_bytes().split(b"\n"))
    return line <= n


def _c6(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    items = [x for x in _seq(receipt.get("evidence")) if isinstance(x, dict)]
    if len(items) < 2:
        reasons["C6"] = "fewer than two evidence anchors"
        return False
    fps: set[str] = set()
    for idx, row in enumerate(items):
        if not str(row.get("claim") or "").strip():
            reasons["C6"] = "evidence claim empty"
            return False
        anchor = row.get("anchor")
        if not isinstance(anchor, str) or not anchor.strip():
            reasons["C6"] = f"evidence[{idx}] has no anchor"
            return False
        probes = [p for p in _seq(row.get("probes")) if isinstance(p, dict)]
        if not probes:
            reasons["C6"] = "evidence has no probes"
            return False
        sources = [p for p in probes if p.get("role") == "source"]
        verifiers = [p for p in probes if p.get("role") == "verifier"]
        if not sources or not str(sources[0].get("command") or "").strip():
            reasons["C6"] = "no non-empty SOURCE probe"
            return False
        if row.get("verdict") in {"CONFIRMED", "REFUTED"}:
            if not verifiers:
                reasons["C6"] = "CONFIRMED/REFUTED without VERIFIER"
                return False
            s_fp = str(sources[0].get("fingerprint") or "")
            v_fp = str(verifiers[0].get("fingerprint") or "")
            if not s_fp or not v_fp or s_fp == v_fp:
                reasons["C6"] = "same-probe-rerun or empty fingerprint"
                return False
            if str(sources[0].get("method")) == str(verifiers[0].get("method")):
                reasons["C6"] = "source and verifier share method"
                return False
            fps.add(s_fp)
            fps.add(v_fp)
        else:
            for probe in probes:
                fp = probe.get("fingerprint")
                if not isinstance(fp, str) or not fp.strip():
                    reasons["C6"] = "fingerprint missing"
                    return False
                fps.add(fp)
        if not _anchor_ok(anchor, repo):
            raw_out = "".join(str(pr.get("raw_output") or "") for pr in probes)
            if not raw_out.strip():
                reasons["C6"] = "anchor does not resolve and no raw_output"
                return False
    if len(fps) < 2:
        reasons["C6"] = "only one distinct probe fingerprint"
        return False
    return True


def _c7(receipt: dict, reasons: dict[str, str]) -> bool:
    if "tests" not in receipt:
        reasons["C7"] = "no tests key"
        return False
    tests = [t for t in _seq(receipt.get("tests")) if isinstance(t, dict)]
    if not tests:
        reasons["C7"] = "tests list empty"
        return False
    for row in tests:
        if row.get("result") != "PASS" or not str(row.get("command") or "").strip():
            reasons["C7"] = "a test is not a verifiable PASS"
            return False
    return True


def _c8(receipt: dict, reasons: dict[str, str]) -> bool:
    if "negative_controls" not in receipt:
        reasons["C8"] = "no negative_controls key"
        return False
    controls = [c for c in _seq(receipt.get("negative_controls")) if isinstance(c, dict)]
    if not controls:
        reasons["C8"] = "no negative controls"
        return False
    for row in controls:
        if row.get("fired_on_bad_state") is not True or row.get("silent_on_good_state") is not True:
            reasons["C8"] = "control failed the both-states rule"
            return False
    return True


def _c9(receipt: dict, reasons: dict[str, str]) -> bool:
    reviewer = receipt.get("reviewer")
    if not isinstance(reviewer, dict):
        reasons["C9"] = "no reviewer object"
        return False
    rid = reviewer.get("reviewer_id")
    if not isinstance(rid, str) or rid.strip() == "":
        reasons["C9"] = "reviewer_id empty"
        return False
    if reviewer.get("verdict") != "PASS":
        reasons["C9"] = "reviewer verdict is not PASS"
        return False
    if reviewer.get("independent") is not True:
        reasons["C9"] = "reviewer not independent"
        return False
    return True


def _c10(receipt: dict, reasons: dict[str, str]) -> bool:
    defects = [d for d in _seq(receipt.get("defects")) if isinstance(d, dict)]
    if not defects:
        return True
    for row in defects:
        sev = row.get("severity")
        if sev in (None, ""):
            reasons["C10"] = "defect without severity is not computable"
            return False
        if sev in _BLOCK_SEV and row.get("status") not in _RESOLVED:
            reasons["C10"] = f"unresolved {sev} {row.get('id')}"
            return False
    return True


def _c11(receipt: dict, repo: Path, reasons: dict[str, str]) -> bool:
    reg = receipt.get("manifest_registration")
    if not isinstance(reg, dict):
        reasons["C11"] = "no manifest_registration record"
        return False
    man_rel = reg.get("manifest_path")
    if not isinstance(man_rel, str) or not man_rel.strip():
        reasons["C11"] = "manifest_path missing"
        return False
    mp = _resolve(repo, man_rel)
    if not mp.is_file():
        reasons["C11"] = "manifest not a file"
        return False
    try:
        doc = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        reasons["C11"] = "manifest JSON failed"
        return False
    items = doc.get("artifacts") if isinstance(doc, dict) else None
    if not isinstance(items, list):
        reasons["C11"] = "artifacts list missing"
        return False
    index = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            index[item["path"].replace("\\", "/")] = item
    for art in _primaries(receipt):
        raw = str(art.get("path") or "").replace("\\", "/")
        if raw not in index:
            reasons["C11"] = f"{raw} not present in manifest"
            return False
    if reg.get("registered") is not True:
        reasons["C11"] = "receipt records registered=false"
        return False
    return True


def _c12(receipt: dict, reasons: dict[str, str]) -> bool:
    consumers = [c for c in _seq(receipt.get("downstream_consumers")) if isinstance(c, dict)]
    if not consumers:
        reasons["C12"] = "no downstream consumers"
        return False
    if any(c.get("executed") is not True for c in consumers):
        reasons["C12"] = "a declared consumer was never executed"
        return False
    for row in consumers:
        probe = row.get("probe") if isinstance(row.get("probe"), dict) else {}
        if row.get("read_ok") is not True:
            reasons["C12"] = "read_ok is not true"
            return False
        exit_code = row.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            reasons["C12"] = f"consumer exit_code={exit_code}"
            return False
        if not str(probe.get("raw_output") or "").strip():
            reasons["C12"] = "consumer probe carries no verbatim output"
            return False
    return True


def evaluate_receipt(receipt: Any, repo: Path) -> dict[str, Any]:
    """Oracle: evaluate every condition, then take the lowest-numbered failure."""
    reasons: dict[str, str] = {}
    if not isinstance(receipt, dict):
        vector = [False] * 12
        reasons["C1"] = "receipt is not an object"
        return _result(vector, reasons)
    vector = [
        _c1(receipt, reasons),
        _c2(receipt, repo, reasons),
        _c3(receipt, repo, reasons),
        _c4(receipt, repo, reasons),
        _c5(receipt, repo, reasons),
        _c6(receipt, repo, reasons),
        _c7(receipt, reasons),
        _c8(receipt, reasons),
        _c9(receipt, reasons),
        _c10(receipt, reasons),
        _c11(receipt, repo, reasons),
        _c12(receipt, reasons),
    ]
    return _result(vector, reasons)
