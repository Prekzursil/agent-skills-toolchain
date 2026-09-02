"""Independently-addressable 12-condition completion reducer.

Each condition is a boolean check that does not short-circuit the others.
Absence of the expected file is owned by condition 2: size re-measure and
consumer-open are gated on existence so a missing path can fail C2 alone.
That gating is the answer to TST-0002's coupling question, not a silent skip.

Verdict shape (TST-0001 contract): verdict + failing_condition_id + reason.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

from conditions import (
    COMPLETION_STATES,
    CONDITIONS,
    OPEN,
    P0P1,
    SHA256_RE,
)

HERE = Path(__file__).resolve().parent
ARTIFACT_SCHEMA = HERE / "artifact.schema.json"
CONSUMER_FIELD = ("payload", "score")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _load_schema() -> dict:
    return json.loads(ARTIFACT_SCHEMA.read_text(encoding="utf-8"))


def _primary(receipt: dict) -> dict | None:
    arts = receipt.get("artifacts") or []
    if not isinstance(arts, list) or not arts:
        return None
    for a in arts:
        if isinstance(a, dict) and a.get("role") == "primary":
            return a
    return arts[0] if isinstance(arts[0], dict) else None


def _outcome(n: int, ok: bool, basis: str) -> dict:
    return {
        "n": n,
        "text": CONDITIONS[n - 1],
        "outcome": "SATISFIED" if ok else "UNSATISFIED",
        "basis": basis,
    }


def _c1(receipt: dict) -> dict:
    state = str(receipt.get("state") or "")
    ok = state in COMPLETION_STATES
    if ok:
        return _outcome(1, True, f"state={state} is a completion terminal")
    return _outcome(
        1,
        False,
        f"state={state!r} is not a completion terminal (SUCCESS only)",
    )


def _c2(receipt: dict, repo: Path) -> dict:
    primary = _primary(receipt)
    if primary is None:
        return _outcome(2, False, "no expected artifact listed")
    rel = str(primary.get("path") or "").replace("\\", "/")
    if not rel:
        return _outcome(2, False, "artifact path empty")
    path = repo / rel
    if not path.is_file():
        return _outcome(
            2,
            False,
            f"expected artifact absent on disk: {rel} "
            "(exists-field in the receipt is not proof)",
        )
    return _outcome(2, True, f"expected artifact exists: {rel}")


def _c3(receipt: dict, repo: Path) -> dict:
    primary = _primary(receipt)
    if primary is None:
        return _outcome(
            3, True, "no listed artifact; size/hash owned by C2 when list is empty"
        )
    rel = str(primary.get("path") or "").replace("\\", "/")
    path = repo / rel
    if not rel or not path.is_file():
        return _outcome(
            3,
            True,
            "size/hash not applicable while the expected file is absent (C2 owns absence)",
        )
    live_sha, live_bytes = digest_file(path)
    floor = int(receipt.get("min_bytes_threshold") or 128)
    declared_sha = str(primary.get("sha256") or "")
    declared_bytes = primary.get("bytes")
    if live_bytes < floor:
        return _outcome(
            3,
            False,
            f"live bytes={live_bytes} below min_bytes_threshold={floor}",
        )
    if not re.match(SHA256_RE, declared_sha):
        return _outcome(3, False, "declared sha256 is not 64 hex chars")
    if declared_sha.lower() != live_sha:
        return _outcome(
            3,
            False,
            f"declared sha256 {declared_sha} != live {live_sha} "
            "(a plausible digest is not a receipt)",
        )
    if declared_bytes is not None and int(declared_bytes) != live_bytes:
        return _outcome(
            3,
            False,
            f"declared bytes={declared_bytes} != live {live_bytes}",
        )
    return _outcome(
        3, True, f"live bytes={live_bytes} >= {floor} and sha256 re-measured"
    )


def _c4(receipt: dict, repo: Path) -> dict:
    primary = _primary(receipt)
    if primary is None:
        return _outcome(
            4, True, "no listed artifact; schema parse owned by C2 when list is empty"
        )
    rel = str(primary.get("path") or "").replace("\\", "/")
    path = repo / rel
    if not rel or not path.is_file():
        return _outcome(
            4,
            True,
            "schema parse not applicable while the expected file is absent (C2 owns absence)",
        )
    try:
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _outcome(4, False, f"artifact unparseable: {type(exc).__name__}")
    schema = _load_schema()
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        first = errs[0]
        return _outcome(
            4,
            False,
            f"artifact schema-invalid: {list(first.path)} {first.message}",
        )
    return _outcome(4, True, "artifact parses against artifact.schema.json")


def _c5(receipt: dict, repo: Path) -> dict:
    unit_id = str(receipt.get("unit_id") or "")
    required = f"SUCCESS:{unit_id}" if unit_id else ""
    sentinel = str(receipt.get("sentinel") or "")
    if not required or required not in sentinel:
        return _outcome(
            5,
            False,
            f"receipt sentinel {sentinel!r} does not carry {required!r}",
        )
    primary = _primary(receipt)
    rel = str((primary or {}).get("path") or "").replace("\\", "/")
    path = repo / rel if rel else None
    if path is not None and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        if required not in text:
            return _outcome(
                5,
                False,
                f"artifact {rel} does not carry {required!r}",
            )
    return _outcome(5, True, f"sentinel {required} present on receipt and artifact")


def _c6(receipt: dict) -> dict:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return _outcome(
            6, False, "SUCCESS requires >=2 anchored evidence items"
        )
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            return _outcome(6, False, f"evidence[{i}] is not an object")
        if not str(item.get("anchor") or "").strip():
            return _outcome(6, False, f"evidence[{i}] missing anchor")
        probes = item.get("probes") or []
        if not isinstance(probes, list) or len(probes) < 2:
            return _outcome(
                6, False, f"evidence[{i}] has <2 probes (single-signal)"
            )
        roles = {str(p.get("role") or "") for p in probes if isinstance(p, dict)}
        if not {"source", "verifier"} <= roles:
            return _outcome(
                6,
                False,
                f"evidence[{i}] probes lack distinct source+verifier roles",
            )
    return _outcome(
        6, True, f"{len(evidence)} anchored evidence item(s), source/verifier pairs"
    )


def _c7(receipt: dict) -> dict:
    tests = receipt.get("tests")
    if not isinstance(tests, list) or not tests:
        return _outcome(7, False, "no tests recorded")
    bad = [
        f"{t.get('id')}={t.get('result')}"
        for t in tests
        if isinstance(t, dict) and str(t.get("result") or "") != "PASS"
    ]
    if bad:
        return _outcome(7, False, f"non-PASS results: {bad}")
    return _outcome(7, True, f"{len(tests)} test(s) PASS")


def _c8(receipt: dict) -> dict:
    ctrls = receipt.get("negative_controls")
    if not isinstance(ctrls, list) or not ctrls:
        return _outcome(8, False, "no negative controls recorded")
    inert = []
    for c in ctrls:
        if not isinstance(c, dict):
            inert.append("non-object")
            continue
        if c.get("fired_on_bad_state") is not True:
            inert.append(f"{c.get('id')}:did-not-fire")
        if c.get("silent_on_good_state") is not True:
            inert.append(f"{c.get('id')}:not-silent-on-good")
    if inert:
        return _outcome(8, False, f"inert or one-sided controls: {inert}")
    return _outcome(
        8, True, f"{len(ctrls)} both-states control(s) fired on bad and silent on good"
    )


def _c9(receipt: dict) -> dict:
    rev = receipt.get("reviewer")
    if not isinstance(rev, dict):
        return _outcome(9, False, "reviewer object missing (self-review is not review)")
    verdict = str(rev.get("verdict") or "")
    indep = rev.get("independent") is True
    if verdict != "PASS" or not indep:
        return _outcome(
            9,
            False,
            f"reviewer verdict={verdict!r} independent={rev.get('independent')!r}",
        )
    return _outcome(
        9, True, f"independent reviewer {rev.get('reviewer_id')} PASS"
    )


def _c10(receipt: dict) -> dict:
    defects = receipt.get("defects") or []
    if defects is None:
        defects = []
    if not isinstance(defects, list):
        return _outcome(10, False, "defects is not a list")
    open_p = [
        d
        for d in defects
        if isinstance(d, dict)
        and str(d.get("severity") or "") in P0P1
        and str(d.get("status") or "") in OPEN
    ]
    if open_p:
        ids = [str(d.get("id")) for d in open_p]
        return _outcome(10, False, f"unresolved P0/P1 attached: {ids}")
    return _outcome(
        10, True, f"{len(defects)} defect(s) recorded, none open at P0/P1"
    )


def _c11(receipt: dict, repo: Path) -> dict:
    reg = receipt.get("manifest_registration")
    if not isinstance(reg, dict) or reg.get("registered") is not True:
        return _outcome(
            11, False, "manifest_registration.registered is not true"
        )
    man_rel = str(reg.get("manifest_path") or "").replace("\\", "/")
    man_path = repo / man_rel
    if not man_rel or not man_path.is_file():
        return _outcome(11, False, f"manifest file absent: {man_rel}")
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _outcome(11, False, f"manifest unparseable: {type(exc).__name__}")
    unit_id = str(receipt.get("unit_id") or "")
    primary = _primary(receipt)
    rel = str((primary or {}).get("path") or "").replace("\\", "/")
    path = repo / rel if rel else None
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == unit_id
    ]
    if not rows:
        return _outcome(11, False, f"no manifest row for {unit_id}")
    if path is None or not path.is_file():
        return _outcome(
            11,
            True,
            "registered=true; digest skipped because expected file is absent "
            "(completion_predicate._c11_manifest skips digest on absent files)",
        )
    live_sha, _ = digest_file(path)
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == rel
        and str(a.get("sha256") or "") == live_sha
        and a.get("present") is True
    ]
    if not matching:
        return _outcome(11, False, "manifest row sha256/path mismatch vs live artifact")
    return _outcome(11, True, f"manifest row present for {rel} sha256={live_sha}")


def _consumer_read(path: Path) -> tuple[bool, str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return False, f"consumer parse failed: {type(exc).__name__}"
    cur: Any = doc
    for key in CONSUMER_FIELD:
        if not isinstance(cur, dict) or key not in cur:
            return False, f"consumer missing required field {'.'.join(CONSUMER_FIELD)}"
        cur = cur[key]
    if cur is None or cur == "":
        return False, "consumer required field empty"
    return True, f"consumer read {'.'.join(CONSUMER_FIELD)}={cur!r}"


def _c12(receipt: dict, repo: Path) -> dict:
    consumers = receipt.get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return _outcome(
            12, False, "no downstream consumer probe; condition 12 would be decorative"
        )
    c0 = consumers[0] if isinstance(consumers[0], dict) else None
    if c0 is None:
        return _outcome(12, False, "downstream_consumers[0] is not an object")
    if c0.get("executed") is not True or c0.get("read_ok") is not True:
        return _outcome(
            12,
            False,
            f"consumer executed={c0.get('executed')!r} read_ok={c0.get('read_ok')!r}",
        )
    primary = _primary(receipt)
    rel = str((primary or {}).get("path") or "").replace("\\", "/")
    path = repo / rel if rel else None
    if path is None or not path.is_file():
        return _outcome(
            12,
            True,
            "live consumer-open not applicable while the expected file is absent "
            "(C2 owns absence)",
        )
    ok, basis = _consumer_read(path)
    if not ok:
        return _outcome(12, False, basis)
    return _outcome(12, True, basis)


def evaluate(receipt: dict, repo: Path) -> dict:
    """Return verdict + failing_condition_id + reason plus the 12-vector."""
    checks = [
        _c1(receipt),
        _c2(receipt, repo),
        _c3(receipt, repo),
        _c4(receipt, repo),
        _c5(receipt, repo),
        _c6(receipt),
        _c7(receipt),
        _c8(receipt),
        _c9(receipt),
        _c10(receipt),
        _c11(receipt, repo),
        _c12(receipt, repo),
    ]
    unsatisfied = [c["n"] for c in checks if c["outcome"] == "UNSATISFIED"]
    if not unsatisfied:
        return {
            "verdict": "PASS",
            "failing_condition_id": None,
            "reason": "all 12 conditions SATISFIED",
            "conditions": checks,
            "unsatisfied": [],
        }
    k = unsatisfied[0]
    failed = next(c for c in checks if c["n"] == k)
    return {
        "verdict": "FAILED",
        "failing_condition_id": k,
        "reason": f"C{k} {failed['text']}: {failed['basis']}",
        "conditions": checks,
        "unsatisfied": unsatisfied,
    }


def always_pass(_receipt: dict, _repo: Path) -> dict:
    """Negative-control stub: vacuously PASS. The isolation harness must reject it."""
    return {
        "verdict": "PASS",
        "failing_condition_id": None,
        "reason": "stub always returns PASS",
        "conditions": [
            _outcome(n, True, "stub") for n in range(1, 13)
        ],
        "unsatisfied": [],
    }
