#!/usr/bin/env python3
"""Live inventory of size/count gates plus small-vs-padded evaluation.

Probe 1 reads the rule (AST of Python sources), not the docs.
Probe 2 runs empty / small-falsification / padded bytes through those rules.
This directory is excluded from the scan so the evaluator is not scored as a gate.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0089"

SKIP_PARTS = {
    "__pycache__",
    ".git",
    "node_modules",
    "ADV-0089",
    "pwsh",
}
IO_NAMES = {
    "chunk_size",
    "CHUNK",
    "BLOB_SIZE",
    "chunk",
    "block_size",
    "BUF",
}
SIZE_ATTRS = {"st_size", "size", "nbytes", "n_bytes", "length"}
SIZE_NAMES = {"size", "nbytes", "n_bytes", "length", "solid"}
THRESHOLD_NAMES = {
    "min_bytes_threshold",
    "MIN_BYTES",
    "_TEXT_MIN_BODY_CHARS",
    "_TEXT_MIN_DISTINCT_CHARS",
    "_TEXT_MAX_SINGLE_CHAR_RUN",
}
ABSENT_SOURCES = (
    (
        "command-center/p2-wave/r2e_loop.py",
        "r2e-runner-tail-complete",
        "Harvest named r2e_loop.tail_complete with a 1024-byte floor; source is absent here.",
    ),
    (
        "platform/lib/receipt_schema_gate.py",
        "receipt-schema-gate-c3",
        "Harvest named Gate-A C3 effective-min / whole-file sha compare; source is absent here.",
    ),
    (
        "tools/measure-guard/unitgate.py",
        "unitgate-count-floors",
        "P2-INTEGRATE cited count floors (1500 units / 40 artifacts); source is absent here.",
    ),
    (
        "rules/common/fan-out-contract.md",
        "fan-out-contract-B7",
        "Catalog input B7 (never score agents on output volume) is absent on this worktree.",
    ),
)

CATALOG_SENTINEL = (
    "SUCCESS:ADV-0089 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0089 <reason>."
)

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0089/probe1_enumerate_gates.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0089/probe2_compare_outputs.py"
)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _num(node: ast.AST | None) -> int | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        try:
            if node.value != node.value:  # NaN
                return None
            if node.value in {float("inf"), float("-inf")}:
                return None
            return int(node.value)
        except (OverflowError, ValueError):
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _num(node.operand)
        return None if v is None else -v
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        a, b = _num(node.left), _num(node.right)
        if a is not None and b is not None:
            return a * b
    return None


def _name_of(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _mentions_size(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Name) and node.id in SIZE_NAMES | THRESHOLD_NAMES:
        return True
    if isinstance(node, ast.Attribute) and node.attr in SIZE_ATTRS:
        return True
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "len":
            return True
        if isinstance(fn, ast.Attribute) and fn.attr in {"stat", "st_size"}:
            return True
        return _mentions_size(fn) or any(_mentions_size(a) for a in node.args)
    if isinstance(node, ast.Attribute):
        return _mentions_size(node.value)
    if isinstance(node, ast.Subscript):
        return _mentions_size(node.value) or _mentions_size(node.slice)
    return False


def _looks_io(name: str | None) -> bool:
    return bool(name) and name in IO_NAMES


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.hits: list[dict[str, Any]] = []
        self.constants: dict[str, int] = {}

    def _add(
        self,
        kind: str,
        line: int,
        threshold: int,
        snippet: str,
        *,
        name: str = "",
    ) -> None:
        if _looks_io(name):
            return
        self.hits.append(
            {
                "path": self.rel,
                "line": line,
                "kind": kind,
                "name": name,
                "threshold": threshold,
                "volume_sensitive": threshold > 1,
                "empty_only": threshold <= 1,
                "snippet": snippet[:180],
            }
        )

    def visit_Assign(self, node: ast.Assign) -> None:
        val = _num(node.value)
        for t in node.targets:
            name = _name_of(t)
            if val is not None and name:
                self.constants[name] = val
            if val is not None and name in THRESHOLD_NAMES:
                src = ast.get_source_segment(self._src, node) or name
                self._add("constant", node.lineno, val, src, name=name)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        val = _num(node.value)
        name = _name_of(node.target)
        if val is not None and name:
            self.constants[name] = val
            if name in THRESHOLD_NAMES:
                src = ast.get_source_segment(self._src, node) or name
                self._add("constant", node.lineno, val, src, name=name)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        left = node.left
        size_left = _mentions_size(left)
        for op, comp in zip(node.ops, node.comparators):
            if not isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.NotEq)):
                continue
            n = _num(comp)
            name = _name_of(comp)
            if n is None and name and name in self.constants:
                n = self.constants[name]
            if n is None:
                continue
            size_right = _mentions_size(comp)
            if not (size_left or size_right):
                continue
            src = ast.get_source_segment(self._src, node) or f"compare:{n}"
            kind = "size-compare"
            self._add(kind, node.lineno, n, src, name=name or _name_of(left) or "")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == "min_bytes_threshold":
                n = _num(v)
                if n is not None:
                    src = ast.get_source_segment(self._src, node) or "min_bytes_threshold"
                    self._add(
                        "dict-min-bytes",
                        node.lineno,
                        n,
                        src[:180],
                        name="min_bytes_threshold",
                    )
        self.generic_visit(node)


def _scan_file(path: Path) -> list[dict[str, Any]]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    vis = _Visitor(_rel(path))
    vis._src = src  # type: ignore[attr-defined]
    vis.visit(tree)
    return vis.hits


def _scan_roots() -> list[Path]:
    roots = [
        REPO / "command-center" / "ready_units.py",
        REPO / "command-center" / "p2-wave",
        REPO / "tools" / "command-center",
        REPO / "tools" / "council",
        REPO / "tools" / "release",
        REPO / "tools" / "measure-guard",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if _skip(p):
                continue
            files.append(p)
    files.sort()
    return files


def enumerate_gates() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for path in _scan_roots():
        hits.extend(_scan_file(path))
    volume = [h for h in hits if h["volume_sensitive"]]
    empty_only = [h for h in hits if h["empty_only"]]
    by_kind: dict[str, int] = {}
    for h in volume:
        by_kind[h["kind"]] = by_kind.get(h["kind"], 0) + 1
    floor_200 = [
        h
        for h in volume
        if h["threshold"] == 200 and h["kind"] == "size-compare"
    ]
    min_bytes = [
        h
        for h in volume
        if h["name"] in {"min_bytes_threshold", "MIN_BYTES"}
        or h["kind"] == "dict-min-bytes"
    ]
    text_floor = [
        h
        for h in volume
        if h["name"] in {"_TEXT_MIN_BODY_CHARS", "_TEXT_MIN_DISTINCT_CHARS"}
        or (h["path"].endswith("ready_units.py") and h["threshold"] in {12, 200})
    ]
    absent = []
    for rel, tid, note in ABSENT_SOURCES:
        p = REPO / rel
        absent.append(
            {
                "path": rel,
                "target_id": tid,
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
                "note": note,
            }
        )
    p2lib = REPO / "command-center" / "p2-wave" / "_p2lib.py"
    p2lib_src = p2lib.read_text(encoding="utf-8") if p2lib.is_file() else ""
    p2lib_has_floor = "if size < floor" in p2lib_src or "if size < floor:" in p2lib_src
    ru = REPO / "command-center" / "ready_units.py"
    ru_src = ru.read_text(encoding="utf-8") if ru.is_file() else ""
    json_empty_only = "if size <= 0:" in ru_src and "artifact_delivered" in ru_src
    schema_rel = "command-center/schema/benchmark-integrity.schema.json"
    schema_path = REPO / schema_rel
    token_mod = REPO / "tools" / "council" / "antifail" / "participation.py"
    return {
        "unit_id": UNIT,
        "files_scanned": len(_scan_roots()),
        "hit_count": len(hits),
        "volume_sensitive_count": len(volume),
        "empty_only_count": len(empty_only),
        "volume_by_kind": by_kind,
        "named_probe_size_floor_200_count": len(floor_200),
        "named_probe_size_floor_200_sample": [
            f"{h['path']}:{h['line']}" for h in floor_200[:20]
        ],
        "min_bytes_threshold_count": len(min_bytes),
        "min_bytes_threshold_sample": [
            f"{h['path']}:{h['line']}:{h['threshold']}" for h in min_bytes[:20]
        ],
        "text_body_floor_hits": [
            f"{h['path']}:{h['line']}:{h['name']}:{h['threshold']}" for h in text_floor[:12]
        ],
        "p2lib_write_if_valid_size_lt_floor": p2lib_has_floor,
        "ready_units_json_empty_only": json_empty_only,
        "token_count_module_present": token_mod.is_file(),
        "declared_schema_present": schema_path.is_file(),
        "declared_schema_path": schema_rel,
        "absent_sources": absent,
        "volume_hits_sample": [
            {
                "path": h["path"],
                "line": h["line"],
                "threshold": h["threshold"],
                "kind": h["kind"],
                "name": h["name"],
                "snippet": h["snippet"],
            }
            for h in volume[:40]
        ],
    }


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def named_probe_size_floor(path: Path, threshold: int = 200) -> tuple[bool, str]:
    """The live named-probe convention: reject artifacts below 200 bytes."""
    if not path.is_file():
        return False, "absent"
    n = path.stat().st_size
    if n <= 0:
        return False, "empty"
    if n < threshold:
        return False, f"below-{threshold}"
    return True, "pass"


def p2lib_min_bytes_floor(path: Path, floor: int) -> tuple[bool, str]:
    """Same comparison as command-center/p2-wave/_p2lib.py write_if_valid."""
    if not path.is_file():
        return False, "absent"
    n = path.stat().st_size
    if n < floor:
        return False, f"below-{floor}"
    return True, "pass"


def naive_exempt_small(path: Path, threshold: int = 200) -> tuple[bool, str]:
    """Broken fix: treat everything below the floor as a pass, including empty."""
    n = path.stat().st_size if path.is_file() else 0
    if n < threshold:
        return True, "exempt-small"
    return True, "pass"


def _load_ready_units():
    path = REPO / "command-center" / "ready_units.py"
    spec = importlib.util.spec_from_file_location("adv0089_ready_units", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def eval_text_body(text: str, sentinel: str) -> tuple[bool, str]:
    ru = _load_ready_units()
    if ru is None:
        return False, "ready_units-unreadable"
    unit = {
        "id": UNIT,
        "output_path": "scratch.md",
        "completion_sentinel": sentinel,
    }
    ok, why = ru.text_artifact_verdict(unit, text)
    return bool(ok), str(why)


def eval_json_delivered(path: Path) -> tuple[bool, str]:
    ru = _load_ready_units()
    if ru is None:
        return False, "ready_units-unreadable"
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        # tempfile outside repo: copy the empty/size checks only
        try:
            size = path.stat().st_size
        except OSError:
            return False, "absent"
        if size <= 0:
            return False, "empty"
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"unparseable:{type(exc).__name__}"
        if isinstance(doc, dict):
            st = str(doc.get("state") or "").upper()
            if st in ru.NOT_DELIVERING:
                return False, f"self-declared:{st}"
        return True, "delivered-no-schema-resolver"
    unit = {
        "id": UNIT,
        "output_path": rel,
        "output_schema": "",
        "completion_sentinel": CATALOG_SENTINEL,
    }
    ok, why = ru.artifact_delivered(unit, resolver=None)
    return bool(ok), str(why)


def _row(gate_id: str, threshold: int, empty, small, padded) -> dict[str, Any]:
    e_ok, e_why = empty
    s_ok, s_why = small
    p_ok, p_why = padded
    return {
        "id": gate_id,
        "threshold": threshold,
        "empty": {"pass": e_ok, "why": e_why},
        "small": {"pass": s_ok, "why": s_why},
        "padded": {"pass": p_ok, "why": p_why},
        "volume_defect": (not s_ok) and p_ok,
        "empty_fails": not e_ok,
    }


def compare_outputs() -> dict[str, Any]:
    small_doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0089",
        "overall_verdict": "REFUTED",
        "note": "compact high-value falsification",
    }
    small_bytes = json.dumps(small_doc, separators=(",", ":")).encode("utf-8")
    padded_doc = dict(small_doc)
    padded_doc["padding"] = "Q" * 2200
    padded_bytes = json.dumps(padded_doc, separators=(",", ":")).encode("utf-8")
    md_sentinel = "SUCCESS:ADV-0089-TEXT"
    small_md = md_sentinel + "\nrefute.\n"
    padded_md = md_sentinel + "\n" + ("refute with varied evidence " * 40) + "\n"

    with tempfile.TemporaryDirectory(prefix="adv0089-") as tmp:
        root = Path(tmp)
        empty_p = root / "empty.json"
        small_p = root / "small.json"
        padded_p = root / "padded.json"
        _write(empty_p, b"")
        _write(small_p, small_bytes)
        _write(padded_p, padded_bytes)

        rows = [
            _row(
                "named-probe-stat-size-200",
                200,
                named_probe_size_floor(empty_p, 200),
                named_probe_size_floor(small_p, 200),
                named_probe_size_floor(padded_p, 200),
            ),
            _row(
                "p2lib-min-bytes-threshold-2048",
                2048,
                p2lib_min_bytes_floor(empty_p, 2048),
                p2lib_min_bytes_floor(small_p, 2048),
                p2lib_min_bytes_floor(padded_p, 2048),
            ),
            _row(
                "p2lib-min-bytes-threshold-1",
                1,
                p2lib_min_bytes_floor(empty_p, 1),
                p2lib_min_bytes_floor(small_p, 1),
                p2lib_min_bytes_floor(padded_p, 1),
            ),
            _row(
                "ready-units-json-delivery",
                0,
                eval_json_delivered(empty_p),
                eval_json_delivered(small_p),
                eval_json_delivered(padded_p),
            ),
        ]

        text_empty = eval_text_body("", md_sentinel)
        text_small = eval_text_body(small_md, md_sentinel)
        text_padded = eval_text_body(padded_md, md_sentinel)
        rows.append(
            _row(
                "ready-units-text-body-floor",
                200,
                text_empty,
                text_small,
                text_padded,
            )
        )

        mutant_empty = naive_exempt_small(empty_p, 200)
        mutant_small = naive_exempt_small(small_p, 200)
        honest_empty = named_probe_size_floor(empty_p, 200)
        # Detector: empty must fail.
        fired_on_bad = mutant_empty[0] is True
        silent_on_good = honest_empty[0] is False

        volume_defects = [r for r in rows if r["volume_defect"]]

    return {
        "unit_id": UNIT,
        "fixtures": {
            "empty_bytes": 0,
            "small_bytes": len(small_bytes),
            "padded_bytes": len(padded_bytes),
            "small_md_chars": len(small_md),
            "padded_md_chars": len(padded_md),
            "small_is_falsification": True,
            "small_overall_verdict": "REFUTED",
        },
        "gates": rows,
        "volume_defect_count": len(volume_defects),
        "volume_defect_ids": [r["id"] for r in volume_defects],
        "empty_fails_on_all_volume_gates": all(r["empty_fails"] for r in rows),
        "empty_control_ok": all(r["empty_fails"] for r in rows),
        "exemption_mutant": {
            "id": "NC-EMPTY-SMALL-EXEMPTION",
            "empty_pass": mutant_empty[0],
            "small_pass": mutant_small[0],
            "honest_empty_pass": honest_empty[0],
            "fired_on_bad_state": fired_on_bad,
            "silent_on_good_state": silent_on_good,
            "both_states": fired_on_bad and silent_on_good,
        },
    }


def targets_from(enum: dict[str, Any], cmp: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {g["id"]: g for g in cmp["gates"]}
    schema_present = bool(enum.get("declared_schema_present"))
    r2e_absent = not any(
        a["target_id"] == "r2e-runner-tail-complete" and a["exists"]
        for a in enum["absent_sources"]
    )
    c3_absent = not any(
        a["target_id"] == "receipt-schema-gate-c3" and a["exists"]
        for a in enum["absent_sources"]
    )
    b7_absent = not any(
        a["target_id"] == "fan-out-contract-B7" and a["exists"]
        for a in enum["absent_sources"]
    )
    json_g = by_id["ready-units-json-delivery"]
    text_g = by_id["ready-units-text-body-floor"]
    floor200 = by_id["named-probe-stat-size-200"]
    floor2048 = by_id["p2lib-min-bytes-threshold-2048"]
    floor1 = by_id["p2lib-min-bytes-threshold-1"]
    out = [
        {
            "target_id": "r2e-runner-tail-complete",
            "verdict": "NOT-CHECKED",
            "basis": "command-center/p2-wave/r2e_loop.py is absent on this worktree",
            "source_absent": r2e_absent,
        },
        {
            "target_id": "receipt-schema-gate-c3",
            "verdict": "NOT-CHECKED",
            "basis": "platform/lib/receipt_schema_gate.py is absent on this worktree",
            "source_absent": c3_absent,
        },
        {
            "target_id": "fan-out-contract-B7",
            "verdict": "NOT-CHECKED",
            "basis": "rules/common/fan-out-contract.md is absent; probe 1 reads live rules not docs",
            "source_absent": b7_absent,
        },
        {
            "target_id": "named-probe-stat-size-200",
            "verdict": "CONFIRMED" if floor200["volume_defect"] else "REFUTED",
            "basis": (
                f"{enum['named_probe_size_floor_200_count']} live compare hits at 200 bytes; "
                f"small={floor200['small']} padded={floor200['padded']}"
            ),
        },
        {
            "target_id": "p2lib-min-bytes-threshold",
            "verdict": "CONFIRMED" if floor2048["volume_defect"] else "REFUTED",
            "basis": (
                f"write_if_valid size<floor live={enum['p2lib_write_if_valid_size_lt_floor']}; "
                f"2048 small={floor2048['small']} padded={floor2048['padded']}"
            ),
        },
        {
            "target_id": "ready-units-text-body-floor",
            "verdict": "CONFIRMED" if text_g["volume_defect"] else "REFUTED",
            "basis": f"text_artifact_verdict small={text_g['small']} padded={text_g['padded']}",
        },
        {
            "target_id": "ready-units-json-delivery-empty-only",
            "verdict": "REFUTED" if (json_g["small"]["pass"] and json_g["padded"]["pass"] and json_g["empty_fails"] and not json_g["volume_defect"]) else (
                "CONFIRMED" if json_g["volume_defect"] else "PARTIAL"
            ),
            "basis": (
                "JSON delivered() rejects empty and self-declared failure, not a size floor "
                f"above 1 byte; small={json_g['small']} padded={json_g['padded']}"
            ),
        },
        {
            "target_id": "empty-only-floor-is-not-volume",
            "verdict": "REFUTED" if (floor1["small"]["pass"] and not floor1["volume_defect"] and floor1["empty_fails"]) else "PARTIAL",
            "basis": f"min_bytes_threshold default 1: small={floor1['small']} padded={floor1['padded']}",
        },
        {
            "target_id": "benchmark-integrity-schema",
            "verdict": "CONFIRMED" if schema_present else "REFUTED",
            "basis": (
                "declared schema present and garbage-rejecting"
                if schema_present
                else "command-center/schema/benchmark-integrity.schema.json absent"
            ),
        },
        {
            "target_id": "token-count-as-unit-quality-gate",
            "verdict": "REFUTED",
            "basis": (
                "tools/council/antifail/participation.py token_count scores council "
                "dominance, not work-unit artifact pass/fail"
                if enum["token_count_module_present"]
                else "no token_count module"
            ),
        },
    ]
    return out


def overall_verdict(targets: list[dict[str, Any]]) -> str:
    vals = {t["verdict"] for t in targets}
    if "CONFIRMED" in vals:
        return "CONFIRMED"
    if vals <= {"REFUTED", "NOT-CHECKED"}:
        return "REFUTED"
    return "PARTIAL"


def dump_probe1() -> str:
    body = json.dumps(enumerate_gates(), sort_keys=True)
    return body + "\nSUCCESS:ADV-0089-probe1 enumerated volume-sensitive gates from source"


def dump_probe2() -> str:
    body = json.dumps(compare_outputs(), sort_keys=True)
    return body + "\nSUCCESS:ADV-0089-probe2 empty/small/padded differential"
