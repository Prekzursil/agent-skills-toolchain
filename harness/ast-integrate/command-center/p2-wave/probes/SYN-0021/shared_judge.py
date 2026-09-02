"""Single import surface for the 12-condition completion predicate.

Census code must call evaluate() here. It must not copy the 12 checks.
evaluate() prefers CC-0003's production reducer
(platform/lib/completion_predicate.py). TST-0002.reducer and evaluate_spec
remain fallbacks when that module is absent.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TST0002 = REPO / "command-center/p2-wave/probes/TST-0002"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMPLETION_STATES = frozenset({"SUCCESS"})
OPEN = frozenset({"open", "OPEN", "unresolved", "UNRESOLVED"})
P0P1 = frozenset({"P0", "P1", "p0", "p1"})

CONDITIONS: tuple[str, ...] = (
    "process/task reached a valid terminal state",
    "expected artifact exists",
    "artifact is non-empty and exceeds a meaningful minimum size",
    "artifact parses against its schema",
    "required sentinel is present",
    "required evidence anchors exist",
    "required tests ran and passed",
    "negative controls or mutations fail as expected",
    "independent reviewer status is PASS",
    "no unresolved P0/P1 defect is attached",
    "output was registered in the artifact manifest",
    "downstream consumers can read it",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _outcome(n: int, ok: bool, basis: str) -> dict[str, Any]:
    return {
        "n": n,
        "text": CONDITIONS[n - 1],
        "outcome": "SATISFIED" if ok else "UNSATISFIED",
        "basis": basis,
    }


def _pack(checks: list[dict[str, Any]], source: str) -> dict[str, Any]:
    unsat = [c["n"] for c in checks if c["outcome"] == "UNSATISFIED"]
    if not unsat:
        return {
            "verdict": "PASS",
            "ok": True,
            "failing_condition_id": None,
            "reason": "all 12 conditions SATISFIED",
            "conditions": checks,
            "source": source,
        }
    k = unsat[0]
    failed = next(c for c in checks if c["n"] == k)
    return {
        "verdict": "FAILED",
        "ok": False,
        "failing_condition_id": k,
        "reason": f"C{k} {failed['text']}: {failed['basis']}",
        "conditions": checks,
        "source": source,
    }


def _primary(receipt: dict[str, Any]) -> dict[str, Any] | None:
    arts = receipt.get("artifacts") or []
    if not isinstance(arts, list) or not arts:
        return None
    for a in arts:
        if isinstance(a, dict) and a.get("role") == "primary":
            return a
    return arts[0] if isinstance(arts[0], dict) else None


def load_tst0002_evaluate() -> tuple[Callable[..., dict[str, Any]] | None, str]:
    path = TST0002 / "reducer.py"
    if not path.is_file():
        return None, "tst0002-reducer-absent"
    sys.path.insert(0, str(TST0002))
    try:
        import reducer as R  # type: ignore

        fn = getattr(R, "evaluate", None)
        if not callable(fn):
            return None, "tst0002-evaluate-missing"
        return fn, str(path.relative_to(REPO)).replace("\\", "/")
    except Exception as exc:  # pragma: no cover - import surface
        return None, f"tst0002-import-failed:{type(exc).__name__}"


def normalize_tst0002(raw: dict[str, Any], source: str) -> dict[str, Any]:
    verdict = str(raw.get("verdict") or "").upper()
    ok = verdict == "PASS"
    fid = raw.get("failing_condition_id")
    if fid is not None:
        try:
            fid = int(fid)
        except (TypeError, ValueError):
            fid = None
    return {
        "verdict": "PASS" if ok else "FAILED",
        "ok": ok,
        "failing_condition_id": None if ok else fid,
        "reason": str(raw.get("reason") or ""),
        "conditions": raw.get("conditions") or [],
        "source": source,
    }


def is_native_receipt(doc: Any) -> bool:
    return (
        isinstance(doc, dict)
        and "min_bytes_threshold" in doc
        and isinstance(doc.get("artifacts"), list)
        and isinstance(doc.get("unit_id"), str)
    )


def _c1(receipt: dict[str, Any]) -> dict[str, Any]:
    state = str(receipt.get("state") or "")
    ok = state in COMPLETION_STATES
    if ok:
        return _outcome(1, True, f"state={state} is a completion terminal")
    return _outcome(1, False, f"state={state!r} is not a completion terminal")


def _c2(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
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


def _c3(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
    primary = _primary(receipt)
    if primary is None:
        return _outcome(3, True, "no listed artifact; size owned by C2")
    rel = str(primary.get("path") or "").replace("\\", "/")
    path = repo / rel
    if not rel or not path.is_file():
        return _outcome(3, True, "size not applicable while file is absent (C2 owns absence)")
    live_sha, live_bytes = digest_file(path)
    floor = int(receipt.get("min_bytes_threshold") or 128)
    declared_sha = str(primary.get("sha256") or "")
    declared_bytes = primary.get("bytes")
    if live_bytes < floor:
        return _outcome(3, False, f"live bytes={live_bytes} below min_bytes_threshold={floor}")
    if declared_sha and not SHA256_RE.match(declared_sha):
        return _outcome(3, False, "declared sha256 is not 64 hex chars")
    if declared_sha and declared_sha.lower() != live_sha:
        return _outcome(
            3,
            False,
            f"declared sha256 {declared_sha} != live {live_sha} "
            "(a plausible digest is not a receipt)",
        )
    if declared_bytes is not None and int(declared_bytes) != live_bytes:
        return _outcome(3, False, f"declared bytes={declared_bytes} != live {live_bytes}")
    return _outcome(3, True, f"live bytes={live_bytes} >= {floor}")


def _c4(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
    primary = _primary(receipt)
    if primary is None:
        return _outcome(4, True, "no listed artifact; schema parse owned by C2")
    rel = str(primary.get("path") or "").replace("\\", "/")
    path = repo / rel
    if not rel or not path.is_file():
        return _outcome(4, True, "schema parse not applicable while file is absent (C2 owns absence)")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _outcome(4, False, f"artifact unparseable: {type(exc).__name__}")
    schema_rel = str(receipt.get("output_schema") or receipt.get("schema_path") or "").replace(
        "\\", "/"
    )
    if not schema_rel:
        return _outcome(4, True, "no declared schema; JSON parsed")
    schema_path = repo / schema_rel
    if not schema_path.is_file():
        return _outcome(4, False, f"declared schema absent: {schema_rel}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errs = sorted(
            jsonschema.Draft7Validator(schema).iter_errors(doc),
            key=lambda e: list(e.path),
        )
    except Exception as exc:
        return _outcome(4, False, f"schema validation error: {type(exc).__name__}")
    if errs:
        first = errs[0]
        return _outcome(4, False, f"artifact schema-invalid: {list(first.path)} {first.message}")
    return _outcome(4, True, f"artifact parses against {schema_rel}")


def _c5(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
    unit_id = str(receipt.get("unit_id") or "")
    required = f"SUCCESS:{unit_id}" if unit_id else ""
    sentinel = str(receipt.get("sentinel") or "")
    if not required or required not in sentinel:
        return _outcome(5, False, f"receipt sentinel {sentinel!r} does not carry {required!r}")
    primary = _primary(receipt)
    rel = str((primary or {}).get("path") or "").replace("\\", "/")
    path = repo / rel if rel else None
    if path is not None and path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        if required not in text:
            return _outcome(5, False, f"artifact {rel} does not carry {required!r}")
    return _outcome(5, True, f"sentinel {required} present")


def _c6(receipt: dict[str, Any]) -> dict[str, Any]:
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return _outcome(6, False, "SUCCESS requires >=2 anchored evidence items")
    for i, item in enumerate(evidence):
        if not isinstance(item, dict):
            return _outcome(6, False, f"evidence[{i}] is not an object")
        if not str(item.get("anchor") or "").strip():
            return _outcome(6, False, f"evidence[{i}] missing anchor")
        probes = item.get("probes") or []
        if not isinstance(probes, list) or len(probes) < 2:
            return _outcome(6, False, f"evidence[{i}] has <2 probes (single-signal)")
        roles = {str(p.get("role") or "") for p in probes if isinstance(p, dict)}
        if not {"source", "verifier"} <= roles:
            return _outcome(6, False, f"evidence[{i}] probes lack distinct source+verifier roles")
    return _outcome(6, True, f"{len(evidence)} anchored evidence item(s)")


def _c7(receipt: dict[str, Any]) -> dict[str, Any]:
    tests = receipt.get("tests")
    if not isinstance(tests, list) or not tests:
        return _outcome(7, False, "no tests recorded")
    bad = []
    for t in tests:
        if not isinstance(t, dict):
            bad.append("non-object")
            continue
        result = str(t.get("result") or t.get("result") or "")
        if result != "PASS":
            bad.append(f"{t.get('id')}={result}")
    if bad:
        return _outcome(7, False, f"non-PASS results: {bad}")
    return _outcome(7, True, f"{len(tests)} test(s) PASS")


def _c8(receipt: dict[str, Any]) -> dict[str, Any]:
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
    return _outcome(8, True, f"{len(ctrls)} both-states control(s)")


def _c9(receipt: dict[str, Any]) -> dict[str, Any]:
    rev = receipt.get("reviewer")
    if not isinstance(rev, dict):
        return _outcome(9, False, "reviewer object missing (self-review is not review)")
    verdict = str(rev.get("verdict") or "")
    indep = rev.get("independent") is True
    if verdict != "PASS" or not indep:
        return _outcome(
            9, False, f"reviewer verdict={verdict!r} independent={rev.get('independent')!r}"
        )
    return _outcome(9, True, f"independent reviewer {rev.get('reviewer_id')} PASS")


def _c10(receipt: dict[str, Any]) -> dict[str, Any]:
    defects = receipt.get("defects") or []
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
    return _outcome(10, True, f"{len(defects)} defect(s) recorded, none open at P0/P1")


def _c11(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
    reg = receipt.get("manifest_registration")
    if not isinstance(reg, dict) or reg.get("registered") is not True:
        return _outcome(11, False, "manifest_registration.registered is not true")
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
            "registered=true; digest skipped because expected file is absent (C2 owns absence)",
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
    return _outcome(11, True, f"manifest row present for {rel}")


def _c12(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
    consumers = receipt.get("downstream_consumers")
    primary = _primary(receipt)
    rel = str((primary or {}).get("path") or "").replace("\\", "/")
    path = repo / rel if rel else None
    if path is None or not path.is_file():
        return _outcome(12, True, "consumer-open not applicable while file is absent (C2 owns)")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _outcome(12, False, f"consumer parse failed: {type(exc).__name__}")
    if isinstance(consumers, list) and consumers:
        c0 = consumers[0] if isinstance(consumers[0], dict) else None
        if c0 is None:
            return _outcome(12, False, "downstream_consumers[0] is not an object")
        if c0.get("executed") is not True or c0.get("read_ok") is not True:
            return _outcome(
                12,
                False,
                f"consumer executed={c0.get('executed')!r} read_ok={c0.get('read_ok')!r}",
            )
    return _outcome(12, True, f"consumer json.loads succeeded for {rel}")


def evaluate_spec(receipt: dict[str, Any], repo: Path) -> dict[str, Any]:
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
    return _pack(checks, "spec-adapter-cc0003-absent")


def load_cc0003():
    lib = REPO / "platform" / "lib"
    path = lib / "completion_predicate.py"
    if not path.is_file():
        return None, "cc0003-absent"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        import completion_predicate as CP  # type: ignore

        return CP, str(path.relative_to(REPO)).replace("\\", "/")
    except Exception as exc:  # pragma: no cover - import surface
        return None, f"cc0003-import-failed:{type(exc).__name__}"


def pack_cc0003(result: Any, source: str) -> dict[str, Any]:
    checks = [c.to_dict() if hasattr(c, "to_dict") else c for c in (result.conditions or ())]
    if getattr(result, "is_complete", False):
        return {
            "verdict": "PASS",
            "ok": True,
            "failing_condition_id": None,
            "reason": "all 12 conditions SATISFIED",
            "conditions": checks,
            "source": source,
        }
    conditions = list(result.conditions or ())
    unsat = [c for c in conditions if str(getattr(c.outcome, "value", c.outcome)) == "UNSATISFIED"]
    ncheck = [c for c in conditions if str(getattr(c.outcome, "value", c.outcome)) == "NOT-CHECKED"]
    hit = (unsat or ncheck or conditions)[0]
    n = int(hit.n)
    return {
        "verdict": "FAILED",
        "ok": False,
        "failing_condition_id": n,
        "reason": f"C{n} {hit.text}: {hit.basis}",
        "conditions": checks,
        "source": source,
    }


def evaluate(receipt: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    """Join a receipt to the shared 12-condition predicate.

    Prefer CC-0003's production reducer (platform/lib/completion_predicate.py).
    Fall back to TST-0002.reducer for native receipts, then evaluate_spec,
    when that module is absent.
    """
    root = repo or REPO
    CP, src = load_cc0003()
    if CP is not None:
        schema = str(receipt.get("output_schema") or receipt.get("schema_path") or "").replace(
            "\\", "/"
        )
        opts = CP.PredicateOptions(
            repo_root=root,
            output_schema=schema or None,
        )
        try:
            return pack_cc0003(CP.evaluate(receipt, opts), src)
        except Exception:
            pass
    if is_native_receipt(receipt):
        fn, src = load_tst0002_evaluate()
        if fn is not None:
            try:
                raw = fn(receipt, root)
            except TypeError:
                raw = fn(receipt)
            if isinstance(raw, dict):
                return normalize_tst0002(raw, src)
    return evaluate_spec(receipt, root)
