"""Silent-in-both-states scanner for TST-0018.

Runs every census-listed detector against a known-GOOD and known-BROKEN
fixture. Identical canonical output is INERT and is named; it is never
folded into an 'all clean' claim. Detectors without an adapter are
NOT-CHECKED, not VALID.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
PLUGIN = TOOLS / "plugin"
CC = TOOLS / "command-center"

for extra in (str(PLUGIN), str(CC), str(TOOLS)):
    if extra not in sys.path:
        sys.path.insert(0, extra)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_two = _load(TOOLS / "detectors" / "two_state.py", "tst0018_two_state")
_census = _load(TOOLS / "detectors" / "census.py", "tst0018_census")

run_two_state = _two.run_two_state
canonicalize = _two.canonicalize
MEASURES_NOTHING = _two.MEASURES_NOTHING
VERDICT_DIFFERS = _two.VERDICT_DIFFERS
VERDICT_SILENT_BOTH = _two.VERDICT_SILENT_BOTH
VERDICT_IDENTICAL = _two.VERDICT_IDENTICAL
VERDICT_NOT_CHECKED = _two.VERDICT_NOT_CHECKED
two_state_valid = getattr(_two, "two_state_valid", None) or getattr(_two, "two_state_valid")
inert_stub = getattr(_two, "inert_stub", None) or getattr(_two, "inert_stub")
census_detector_ids = getattr(_census, "census_detector_ids", None) or getattr(
    _census, "census_detector_ids"
)
enumerator_control = getattr(_census, "enumerator_control", None) or getattr(
    _census, "enumerator_control"
)
CENSUS_KNOWN_PRESENT = getattr(_census, "KNOWN_PRESENT_DETECTOR", None) or getattr(
    _census, "KNOWN_PRESENT_DETECTOR"
)

# AST census emits the on-disk path. The census constant may still use an
# older spelling; both are accepted as "known present".
DISK_KNOWN_PRESENT = "plugin/static_audit.py:audit_snippet"

GOOD_PY = "def ok():\n    return 1\n"
BAD_NET = (
    "import urllib.request\n\n"
    "def phone():\n"
    "    urllib.request.urlopen('http://203.0.113.9/')\n"
)
BAD_KEY = "def generate_key():\n    return 1\n"
GOOD_BOUNDARY = (
    "def consume(art):\n"
    "    facts = extract_facts(art)\n"
    "    return apply_policy(facts)\n"
)
BAD_BOUNDARY = "def consume(payload):\n    apply_policy(payload)\n"


def jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(x) for x in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return jsonable(obj.to_dict())
    if hasattr(obj, "__dict__"):
        return jsonable(vars(obj))
    return str(obj)


def _canonical_text(obj: Any) -> str:
    """two_state.canonicalize may return a dict or a JSON string; hash needs bytes."""
    if obj is None or obj == "":
        return ""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha(text: Any) -> str:
    return hashlib.sha256(_canonical_text(text).encode("utf-8")).hexdigest()


def _findings(fn: Callable[[], Any]) -> dict[str, Any]:
    payload = jsonable(fn())
    return {"fired": bool(payload), "payload": payload}


@dataclass(frozen=True)
class Adapter:
    detector_id: str
    kind: str
    check: Callable[[str], Any] | None


def _static():
    return _load(PLUGIN / "static_audit.py", "tst0018_static_audit")


def _market():
    return _load(TOOLS / "marketplace" / "audit.py", "tst0018_market_audit")


def _boundary():
    return _load(TOOLS / "artifact_boundary" / "ast_guard.py", "tst0018_ast_guard")


def _hook():
    return _load(PLUGIN / "hook_fire_probe.py", "tst0018_hook_fire_probe")


def _scenario():
    return _load(PLUGIN / "scenario.py", "tst0018_hook_scenario")


def _validate():
    return _load(CC / "validate.py", "tst0018_cc_validate")


def check_snippet(state: str) -> dict[str, Any]:
    sa = _static()
    src = BAD_NET if state == "broken" else GOOD_PY
    return _findings(lambda: sa.audit_snippet(src, rel=f"{state}.py"))


def check_audit_source(state: str) -> dict[str, Any]:
    sa = _static()
    src = BAD_NET if state == "broken" else GOOD_PY
    return _findings(lambda: sa.audit_source(src, f"{state}.py", ".py"))


def check_audit_tree(state: str) -> dict[str, Any]:
    sa = _static()
    src = BAD_NET if state == "broken" else GOOD_PY
    with tempfile.TemporaryDirectory(prefix="tst0018-tree-") as tmp:
        root = Path(tmp)
        (root / "prod.py").write_text(src, encoding="utf-8")
        return _findings(lambda: sa.audit_tree([root]))


def check_scan_source(state: str) -> dict[str, Any]:
    m = _market()
    src = BAD_KEY if state == "broken" else GOOD_PY
    return _findings(lambda: m.scan_source(src, f"{state}.py"))


def check_detect_plant(state: str) -> dict[str, Any]:
    m = _market()
    src = BAD_KEY if state == "broken" else GOOD_PY
    return _findings(lambda: m.detect_plant(src))


def check_scan_tree(state: str) -> dict[str, Any]:
    m = _market()
    src = BAD_KEY if state == "broken" else GOOD_PY
    with tempfile.TemporaryDirectory(prefix="tst0018-mkt-") as tmp:
        root = Path(tmp)
        (root / "mod.py").write_text(src, encoding="utf-8")
        return _findings(lambda: m.scan_tree(root))


def check_boundary_source(state: str) -> dict[str, Any]:
    b = _boundary()
    src = BAD_BOUNDARY if state == "broken" else GOOD_BOUNDARY
    return _findings(lambda: b.audit_source(src, label=state))


def check_consume_module(state: str) -> dict[str, Any]:
    b = _boundary()
    src = BAD_BOUNDARY if state == "broken" else GOOD_BOUNDARY
    with tempfile.TemporaryDirectory(prefix="tst0018-consume-") as tmp:
        path = Path(tmp) / f"{state}.py"
        path.write_text(src, encoding="utf-8")
        report = b.audit_consume_module(path)
        findings = report.get("findings") or []
        return {"fired": bool(findings), "payload": jsonable(report)}


def check_run_probe(state: str) -> dict[str, Any]:
    hook = _hook()
    scen = _scenario()
    with tempfile.TemporaryDirectory(prefix="tst0018-hook-") as tmp:
        root = Path(tmp)
        if state == "broken":
            scen.write_broken(root)
        else:
            scen.write_healthy(root)
        report = hook.run_probe(root)
        payload = jsonable(report)
        fired = payload.get("verdict") != "FIRED"
        return {"fired": bool(fired), "payload": payload}


def check_fs_only(state: str) -> dict[str, Any]:
    hook = _hook()
    scen = _scenario()
    with tempfile.TemporaryDirectory(prefix="tst0018-fs-") as tmp:
        root = Path(tmp)
        if state == "broken":
            scen.write_broken(root)
        else:
            scen.write_healthy(root)
        verdict = hook.filesystem_only_verdict(root)
        return {"fired": verdict == "FIRED", "payload": verdict}


def _mini_catalog(tmp: Path, *, broken: bool) -> dict[str, Any]:
    register = tmp / "REGISTER.md"
    text = (
        "# Register\n\n"
        "## 1. OUTSTANDING\n\n"
        "### 1A. Program A - toolchain / Prompt Two (1)\n\n"
        "| ID | Title |\n"
        "| --- | --- |\n"
        "| R-1 | sample item |\n"
    )
    register.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    item = {
        "id": "R-1",
        "title": "sample item",
        "next_smallest_action": "implement the sample",
        "dependencies": ["R-999"] if broken else [],
        "owner_gate": [],
    }
    return {
        "schema_version": 1,
        "items": [item],
        "owner_questions": [],
        "defaults": {},
        "provenance": {
            "register": str(register),
            "register_sha256": digest,
        },
    }


def check_validate(state: str) -> dict[str, Any]:
    val = _validate()
    with tempfile.TemporaryDirectory(prefix="tst0018-val-") as tmp:
        root = Path(tmp)
        catalog = _mini_catalog(root, broken=(state == "broken"))
        register = Path(catalog["provenance"]["register"])
        violations, stats = val.validate(
            catalog,
            register_path=register,
            graph=None,
            require_complete=False,
        )
        payload = {"violations": jsonable(violations), "stats": jsonable(stats)}
        return {"fired": bool(violations), "payload": payload}


def _alias(fn: Callable[[str], Any], *ids: str) -> dict[str, Callable[[str], Any]]:
    return {i: fn for i in ids}


ADAPTERS: dict[str, Callable[[str], Any]] = {}
ADAPTERS.update(
    _alias(
        check_snippet,
        "plugin/static_audit.py:audit_snippet",
        "plugin/static_audit.py:audit_snippet",
    )
)
ADAPTERS.update(
    _alias(
        check_audit_source,
        "plugin/static_audit.py:audit_source",
        "plugin/static_audit.py:audit_source",
    )
)
ADAPTERS.update(
    _alias(
        check_audit_tree,
        "plugin/static_audit.py:audit_tree",
        "plugin/static_audit.py:audit_tree",
    )
)
ADAPTERS.update(
    _alias(
        check_scan_source,
        "marketplace/audit.py:scan_source",
        "marketplace/audit.py:scan_source",
    )
)
ADAPTERS.update(
    _alias(
        check_detect_plant,
        "marketplace/audit.py:detect_plant",
        "marketplace/audit.py:detect_plant",
    )
)
ADAPTERS.update(
    _alias(
        check_scan_tree,
        "marketplace/audit.py:scan_tree",
        "marketplace/audit.py:scan_tree",
    )
)
ADAPTERS.update(
    _alias(
        check_boundary_source,
        "artifact_boundary/ast_guard.py:audit_source",
        "artifact_boundary/ast_guard.py:audit_source",
    )
)
ADAPTERS.update(
    _alias(
        check_consume_module,
        "artifact_boundary/ast_guard.py:audit_consume_module",
        "artifact_boundary/ast_guard.py:audit_consume_module",
    )
)
ADAPTERS.update(
    _alias(
        check_run_probe,
        "plugin/hook_fire_probe.py:run_probe",
        "plugin/hook_fire_probe.py:run_probe",
    )
)
ADAPTERS.update(
    _alias(
        check_fs_only,
        "plugin/hook_fire_probe.py:filesystem_only_verdict",
        "plugin/hook_fire_probe.py:filesystem_only_verdict",
    )
)
ADAPTERS.update(
    _alias(
        check_validate,
        "command-center/validate.py:validate",
        "command-center/validate.py:validate",
    )
)


def row_from_record(rec: Any, *, kind: str, checked: bool) -> dict[str, Any]:
    d = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec)
    good = d.get("good_output", d.get("good_output"))
    broken = d.get("broken_output", d.get("broken_output"))
    good_c = _canonical_text(canonicalize(good) if good is not None else "")
    broken_c = _canonical_text(canonicalize(broken) if broken is not None else "")
    identical = (
        bool(checked) and good is not None and broken is not None and good_c == broken_c
    )
    verdict = d["verdict"]
    nothing = MEASURES_NOTHING
    if isinstance(nothing, str):
        nothing = {nothing, VERDICT_SILENT_BOTH, VERDICT_IDENTICAL}
    inert = verdict in {VERDICT_SILENT_BOTH, VERDICT_IDENTICAL} or identical
    return {
        "detector_id": d["detector_id"],
        "kind": kind,
        "verdict": verdict,
        "reason": d["reason"],
        "differs": d["differs"],
        "silent_in_both": d.get("silent_in_both", d.get("silent_in_both")),
        "good_output": good,
        "broken_output": broken,
        "good_canonical": good_c,
        "broken_canonical": broken_c,
        "good_sha256": _sha(good_c) if good_c else None,
        "broken_sha256": _sha(broken_c) if broken_c else None,
        "byte_diff": (not identical) if checked else None,
        "inert": inert,
        "measures_nothing": inert or verdict in nothing,
        "checked": checked,
    }


def not_checked_row(detector_id: str) -> dict[str, Any]:
    return {
        "detector_id": detector_id,
        "kind": "shipped",
        "verdict": VERDICT_NOT_CHECKED,
        "reason": "no-both-states-adapter",
        "differs": False,
        "silent_in_both": False,
        "good_output": None,
        "broken_output": None,
        "good_canonical": "",
        "broken_canonical": "",
        "good_sha256": None,
        "broken_sha256": None,
        "byte_diff": None,
        "inert": False,
        "measures_nothing": False,
        "checked": False,
    }


def scan(extra: Iterable[Adapter] | None = None) -> dict[str, Any]:
    enum = enumerator_control()
    ids = list(enum.get("ids") or enum.get("ids") or census_detector_ids())
    found_disk = DISK_KNOWN_PRESENT in ids
    found_const = CENSUS_KNOWN_PRESENT in ids
    rows: list[dict[str, Any]] = []
    for detector_id in ids:
        fn = ADAPTERS.get(detector_id)
        if fn is None:
            rows.append(not_checked_row(detector_id))
            continue
        try:
            rec = run_two_state(fn, detector_id=detector_id)
        except (ImportError, ModuleNotFoundError, FileNotFoundError):
            row = not_checked_row(detector_id)
            row["reason"] = "adapter-module-absent"
            rows.append(row)
            continue
        rows.append(row_from_record(rec, kind="shipped", checked=True))

    extra_rows: list[dict[str, Any]] = []
    for adapter in extra or []:
        if adapter.check is None:
            extra_rows.append(not_checked_row(adapter.detector_id))
            continue
        rec = run_two_state(adapter.check, detector_id=adapter.detector_id)
        extra_rows.append(row_from_record(rec, kind=adapter.kind, checked=True))

    checked = [r for r in rows if r["checked"]]
    inert = [r["detector_id"] for r in checked if r["inert"]]
    measures_nothing = [r["detector_id"] for r in checked if r["measures_nothing"]]
    valid = [r["detector_id"] for r in checked if r["verdict"] == VERDICT_DIFFERS]
    not_checked = [r["detector_id"] for r in rows if not r["checked"]]

    if measures_nothing:
        summary = (
            f"{len(measures_nothing)} detector(s) measure nothing (INERT named): "
            + ", ".join(measures_nothing)
        )
    else:
        summary = (
            f"0 inert among {len(checked)} exercised shipped detectors; "
            f"{len(not_checked)} NOT-CHECKED (no adapter)"
        )

    return {
        "enumerator": {
            **enum,
            "disk_known_present": DISK_KNOWN_PRESENT,
            "found_disk_known_present": found_disk,
            "found_census_constant": found_const,
            "enumerator_live": found_disk or found_const,
        },
        "rows": rows,
        "extra_rows": extra_rows,
        "counts": {
            "inventory": len(rows),
            "checked": len(checked),
            "not_checked": len(not_checked),
            "inert": len(inert),
            "measures_nothing": len(measures_nothing),
            "valid": len(valid),
        },
        "inert": inert,
        "measures_nothing": measures_nothing,
        "valid": valid,
        "not_checked": not_checked,
        "summary": summary,
        "all_clean_claim": False,
        "identical_outputs_reported_as_inert": True,
    }


def planted_inert_check(state: str) -> dict[str, Any]:
    """Identical silent payload in both states (byte-identical INERT plant)."""
    return {"fired": False, "payload": {"stub": "inert"}}


def planted_inert_adapter() -> Adapter:
    return Adapter(
        detector_id="planted.inert-stub",
        kind="planted",
        check=planted_inert_check,
    )


def known_good_adapter() -> Adapter:
    return Adapter(
        detector_id="control.two-state-valid",
        kind="control",
        check=two_state_valid,
    )
