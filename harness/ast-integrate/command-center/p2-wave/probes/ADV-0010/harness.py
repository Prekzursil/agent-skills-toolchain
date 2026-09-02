"""Scratch-copy mutation hunt against tools/command-center/validate.py.

Live tree is never edited. The suite is the gate's own checks, bound to the
live field names in validate.py.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_DIR = REPO / "tools" / "command-center"
GATE_SRC = GATE_DIR / "validate.py"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0010/probe1_mutations.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0010/probe2_survivors.py"
)

REGISTER_MD = """## 1. OUTSTANDING

### 1A. Program A - toolchain / Prompt Two (2)

| id | title |
| --- | --- |
| R-A01 | Root item |
| R-A02 | Child item |
"""


@dataclass(frozen=True)
class Mutation:
    mid: str
    kind: str
    needle: str
    repl: str
    fail_open: bool
    description: str


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        "invert_cli_exit_guard",
        "invert-comparison",
        "    if violations:\n"
        "        print(f\"FAILED:cc-validate violations={len(violations)}\")\n"
        "        return 1\n",
        "    if not violations:\n"
        "        print(f\"FAILED:cc-validate violations={len(violations)}\")\n"
        "        return 1\n",
        True,
        "Invert the CLI violations guard so a dirty catalog exits 0.",
    ),
    Mutation(
        "drop_empty_fail_closed",
        "drop-required-check",
        "    if not items:\n"
        "        violations.append(\n"
        "            Violation(\"V-EMPTY\", \"-\", \"catalog holds zero items (fail closed)\")\n"
        "        )\n"
        "        return violations, {\"items\": 0}\n",
        "    if False:\n"
        "        violations.append(\n"
        "            Violation(\"V-EMPTY\", \"-\", \"catalog holds zero items (fail closed)\")\n"
        "        )\n"
        "        return violations, {\"items\": 0}\n",
        True,
        "Drop the empty-catalog fail-closed so [] is silent.",
    ),
    Mutation(
        "invert_reach1_missing_dep",
        "invert-comparison",
        "            if dep not in index:",
        "            if dep in index:",
        True,
        "Invert REACH-1 missing-dependency comparison.",
    ),
    Mutation(
        "drop_vfields_guard",
        "drop-required-check",
        "    if unresolved and require_complete:",
        "    if False:",
        True,
        "Never emit V-FIELDS even when require_complete=True.",
    ),
    Mutation(
        "cli_ignore_require_complete",
        "flip-default",
        "        require_complete=args.require_complete,",
        "        require_complete=False,",
        True,
        "CLI --require-complete is ignored; V-FIELDS cannot be armed from the CLI.",
    ),
    Mutation(
        "skip_owner_approval_field",
        "drop-required-field",
        "        for field in cat.WORK_UNIT_FIELDS:",
        "        for field in (f for f in cat.WORK_UNIT_FIELDS if f != \"owner_approval_required\"):",
        True,
        "owner_approval_required is removed from the required-field set.",
    ),
    Mutation(
        "flip_require_complete_default_true",
        "flip-default",
        "    require_complete: bool = True,",
        "    require_complete: bool = False,",
        False,
        "Default require_complete False->True (stricter, fail-closed).",
    ),
    Mutation(
        "invert_reach5_terminal",
        "invert-comparison",
        "        if disposition not in cat.TERMINAL_DISPOSITIONS:",
        "        if disposition in cat.TERMINAL_DISPOSITIONS:",
        True,
        "Invert the terminal-disposition membership test.",
    ),
    Mutation(
        "unreadable_catalog_exit_0",
        "replace-raise-with-log",
        "        print(f\"FAILED:cc-validate cannot read {args.catalog}: {exc}\")\n"
        "        return 1\n",
        "        print(f\"FAILED:cc-validate cannot read {args.catalog}: {exc}\")\n"
        "        return 0\n",
        True,
        "Unreadable catalog CLI path returns 0 (log, do not fail).",
    ),
    Mutation(
        "drop_blank_register_digest",
        "drop-required-check",
        "        if not recorded:",
        "        if False and not recorded:",
        False,
        "Blank provenance.register_sha256 branch dropped; digest-mismatch still fires so this is not fail-open.",
    ),
    Mutation(
        "invert_vgraph_compare",
        "invert-comparison",
        "    if graph is not None and graph != expected:",
        "    if graph is not None and graph == expected:",
        False,
        "Matching graphs are treated as V-GRAPH failures (fail-closed noise).",
    ),
)


def complete_item(iid: str, **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": iid,
        "title": f"title {iid}",
        "phase": "0",
        "target": "target",
        "inputs": ["in"],
        "dependencies": [],
        "assignment": "impl",
        "tool_permissions": ["Read"],
        "execution_substrate": "local",
        "timeout_seconds": 60,
        "output_path": f"out/{iid}.json",
        "output_schema": "schema.json",
        "evidence_requirement": "probe",
        "tests_required": ["t"],
        "reviewer_requirement": "rev",
        "completion_sentinel": f"SUCCESS:{iid}",
        "retry_policy": "none",
        "failure_classification": ["overclaim"],
        "owner_approval_required": False,
        "next_smallest_action": "do work",
        "owner_gate": [],
        "disposition": None,
        "disposition_evidence": "",
        "program": "A-toolchain",
        "section": "OUTSTANDING",
        "status": "OPEN",
    }
    row.update(over)
    return row


def register_bytes() -> bytes:
    return REGISTER_MD.replace("\r\n", "\n").encode("utf-8")


def clean_catalog(register_rel: str, digest: str) -> dict[str, Any]:
    return {
        "items": [
            complete_item(
                "R-A01",
                disposition="DONE-VERIFIED",
                disposition_evidence="closed on evidence",
                next_smallest_action="",
            ),
            complete_item("R-A02", dependencies=["R-A01"]),
        ],
        "owner_questions": [{"id": "OQ-1", "state": "OPEN", "prompt": "q"}],
        "defaults": {
            "assignment": "impl",
            "tool_permissions": ["Read"],
            "execution_substrate": "local",
            "timeout_seconds": 60,
            "output_schema": "schema.json",
            "tests_required": ["t"],
            "reviewer_requirement": "rev",
            "retry_policy": "none",
            "failure_classification": ["overclaim"],
        },
        "provenance": {"register": register_rel, "register_sha256": digest},
    }


def checks(vios: list[dict[str, Any]]) -> set[str]:
    return {str(v.get("check")) for v in vios}


def _apply(src: str, mut: Mutation) -> str:
    n = src.count(mut.needle)
    if n != 1:
        raise RuntimeError(f"{mut.mid}: needle count {n} (want 1)")
    return src.replace(mut.needle, mut.repl, 1)


def _unload() -> None:
    for name in ("validate", "catalog", "register_parse"):
        sys.modules.pop(name, None)


def _load_gate(scratch: Path) -> Any:
    _unload()
    sys.path.insert(0, str(scratch))
    try:
        return importlib.import_module("validate")
    finally:
        if sys.path and sys.path[0] == str(scratch):
            sys.path.pop(0)


def _prepare_scratch(scratch: Path, source: str) -> None:
    shutil.copy2(GATE_DIR / "catalog.py", scratch / "catalog.py")
    shutil.copy2(GATE_DIR / "register_parse.py", scratch / "register_parse.py")
    (scratch / "validate.py").write_text(source, encoding="utf-8")


def run_suite(val: Any, cat: Any, tmp: Path) -> dict[str, str]:
    tmp.mkdir(parents=True, exist_ok=True)
    raw = register_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    regp = tmp / "REGISTER.md"
    regp.write_bytes(raw)
    base = clean_catalog("REGISTER.md", digest)

    def vrun(catalog: dict[str, Any], **kw: Any):
        graph = kw.pop("graph", None)
        if graph is None:
            graph = cat.build_graph(catalog)
        return val.validate(catalog, register_path=regp, graph=graph, **kw)

    def write_pair(catalog: dict[str, Any]) -> tuple[Path, Path]:
        cpath = tmp / "catalog.json"
        gpath = tmp / "graph.json"
        cpath.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        gpath.write_text(
            json.dumps(cat.build_graph(catalog), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return cpath, gpath

    results: dict[str, str] = {}

    def case(tid: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            results[tid] = "PASS"
        except Exception:
            results[tid] = "FAIL"

    def test_clean() -> None:
        vios, stats = vrun(base, require_complete=True)
        assert vios == [], vios
        assert stats["items"] == 2

    def test_empty() -> None:
        vios, _ = val.validate({"items": []}, register_path=regp)
        assert "V-EMPTY" in checks(vios)

    def test_dangling() -> None:
        bad = deepcopy(base)
        bad["items"][1]["dependencies"] = ["R-NOPE"]
        vios, _ = vrun(bad)
        assert "REACH-1" in checks(vios)

    def test_cycle() -> None:
        bad = deepcopy(base)
        bad["items"][0]["disposition"] = None
        bad["items"][0]["next_smallest_action"] = "x"
        bad["items"][0]["dependencies"] = ["R-A02"]
        vios, _ = vrun(bad)
        assert "REACH-2" in checks(vios)

    def test_dead_end() -> None:
        bad = deepcopy(base)
        bad["items"][1]["next_smallest_action"] = ""
        bad["items"][1]["dependencies"] = []
        vios, _ = vrun(bad)
        assert "REACH-3" in checks(vios)

    def test_bad_gate() -> None:
        bad = deepcopy(base)
        bad["items"][1]["owner_gate"] = ["OQ-999"]
        vios, _ = vrun(bad)
        assert "REACH-4" in checks(vios)

    def test_no_evidence() -> None:
        bad = deepcopy(base)
        bad["items"][0]["disposition_evidence"] = "  "
        vios, _ = vrun(bad)
        assert "REACH-5" in checks(vios)

    def test_missing_register() -> None:
        vios, _ = val.validate(
            base, register_path=tmp / "nope.md", graph=cat.build_graph(base)
        )
        assert "REACH-6" in checks(vios)

    def test_blank_digest() -> None:
        bad = deepcopy(base)
        bad["provenance"]["register_sha256"] = ""
        vios, _ = vrun(bad)
        assert "REACH-6" in checks(vios)

    def test_graph_mismatch() -> None:
        stale = deepcopy(cat.build_graph(base))
        stale["edge_count"] = 999
        vios, _ = val.validate(base, register_path=regp, graph=stale)
        assert "V-GRAPH" in checks(vios)

    def test_vfields_both() -> None:
        bad = deepcopy(base)
        bad["items"][1]["completion_sentinel"] = ""
        off, _ = vrun(bad, require_complete=False)
        on, _ = vrun(bad, require_complete=True)
        assert "V-FIELDS" not in checks(off)
        assert "V-FIELDS" in checks(on)

    def test_malformed_id() -> None:
        bad = deepcopy(base)
        bad["items"].append(complete_item("R-"))
        vios, _ = vrun(bad)
        assert "V-ID" in checks(vios)

    def test_cli_clean() -> None:
        cpath, gpath = write_pair(base)
        assert val.main(["--catalog", str(cpath), "--graph", str(gpath), "--register", str(regp)]) == 0

    def test_cli_dangling() -> None:
        bad = deepcopy(base)
        bad["items"][1]["dependencies"] = ["R-NOPE"]
        cpath, gpath = write_pair(bad)
        assert val.main(["--catalog", str(cpath), "--graph", str(gpath), "--register", str(regp)]) == 1

    def test_cli_unreadable() -> None:
        _, gpath = write_pair(base)
        rc = val.main(
            [
                "--catalog",
                str(tmp / "missing.json"),
                "--graph",
                str(gpath),
                "--register",
                str(regp),
            ]
        )
        assert rc == 1

    case("clean_catalog_silent", test_clean)
    case("empty_catalog_vempty", test_empty)
    case("dangling_dep_reach1", test_dangling)
    case("cycle_reach2", test_cycle)
    case("dead_end_reach3", test_dead_end)
    case("missing_owner_question_reach4", test_bad_gate)
    case("terminal_without_evidence_reach5", test_no_evidence)
    case("missing_register_reach6", test_missing_register)
    case("blank_register_digest_reach6", test_blank_digest)
    case("graph_mismatch_vgraph", test_graph_mismatch)
    case("vfields_require_complete_both_states", test_vfields_both)
    case("malformed_id_vid", test_malformed_id)
    case("cli_clean_exit_0", test_cli_clean)
    case("cli_dangling_exit_1", test_cli_dangling)
    case("cli_unreadable_exit_1", test_cli_unreadable)
    return results


def hunt() -> dict[str, Any]:
    live = GATE_SRC.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="adv0010-") as td:
        root = Path(td)
        base_scratch = root / "baseline"
        base_scratch.mkdir()
        _prepare_scratch(base_scratch, live)
        val = _load_gate(base_scratch)
        cat = importlib.import_module("catalog")
        baseline = run_suite(val, cat, root / "t-base")
        _unload()
        baseline_failed = [k for k, v in baseline.items() if v != "PASS"]
        for mut in MUTATIONS:
            mutated = _apply(live, mut)
            scratch = root / mut.mid
            scratch.mkdir()
            _prepare_scratch(scratch, mutated)
            mval = _load_gate(scratch)
            mcat = importlib.import_module("catalog")
            results = run_suite(mval, mcat, root / f"t-{mut.mid}")
            _unload()
            failed = [k for k, v in results.items() if v != "PASS"]
            killed = bool(failed)
            rows.append(
                {
                    "id": mut.mid,
                    "kind": mut.kind,
                    "description": mut.description,
                    "fail_open": mut.fail_open,
                    "status": "KILLED" if killed else "SURVIVED",
                    "failed_tests": failed,
                    "suite": results,
                }
            )
    survived = [r for r in rows if r["status"] == "SURVIVED"]
    return {
        "gate": "tools/command-center/validate.py",
        "baseline_all_pass": not baseline_failed,
        "baseline_failed_tests": baseline_failed,
        "baseline": baseline,
        "mutations": rows,
        "killed_count": sum(1 for r in rows if r["status"] == "KILLED"),
        "survived_count": len(survived),
        "survived_ids": [r["id"] for r in survived],
        "fail_open_survivors": [r["id"] for r in survived if r["fail_open"]],
    }


def demonstrate_survivor(mid: str) -> dict[str, Any]:
    mut = next(m for m in MUTATIONS if m.mid == mid)
    live = GATE_SRC.read_text(encoding="utf-8")
    mutated = _apply(live, mut)
    with tempfile.TemporaryDirectory(prefix="adv0010-p2-") as td:
        root = Path(td)
        scratch = root / "m"
        scratch.mkdir()
        _prepare_scratch(scratch, mutated)
        val = _load_gate(scratch)
        cat = importlib.import_module("catalog")
        raw = register_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        regp = root / "REGISTER.md"
        regp.write_bytes(raw)
        base = clean_catalog("REGISTER.md", digest)
        try:
            if mid == "cli_ignore_require_complete":
                bad = deepcopy(base)
                bad["items"][1]["completion_sentinel"] = ""
                cpath = root / "catalog.json"
                gpath = root / "graph.json"
                cpath.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                gpath.write_text(
                    json.dumps(cat.build_graph(bad), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                code = int(
                    val.main(
                        [
                            "--catalog",
                            str(cpath),
                            "--graph",
                            str(gpath),
                            "--register",
                            str(regp),
                            "--require-complete",
                        ]
                    )
                )
                detail = "CLI --require-complete + blank completion_sentinel"
            elif mid == "skip_owner_approval_field":
                bad = deepcopy(base)
                del bad["items"][1]["owner_approval_required"]
                vios, _ = val.validate(
                    bad,
                    register_path=regp,
                    graph=cat.build_graph(bad),
                    require_complete=True,
                )
                code = 0 if not vios else 1
                detail = f"missing owner_approval_required checks={sorted(checks(vios))}"
            elif mid == "drop_empty_fail_closed":
                vios, _ = val.validate({"items": []}, register_path=regp)
                code = 0 if not vios else 1
                detail = f"empty catalog checks={sorted(checks(vios))}"
            elif mid == "unreadable_catalog_exit_0":
                gpath = root / "graph.json"
                gpath.write_text("{}\n", encoding="utf-8")
                code = int(
                    val.main(
                        [
                            "--catalog",
                            str(root / "missing.json"),
                            "--graph",
                            str(gpath),
                            "--register",
                            str(regp),
                        ]
                    )
                )
                detail = "CLI missing catalog file"
            elif mid == "drop_vfields_guard":
                bad = deepcopy(base)
                bad["items"][1]["completion_sentinel"] = ""
                vios, _ = val.validate(
                    bad,
                    register_path=regp,
                    graph=cat.build_graph(bad),
                    require_complete=True,
                )
                code = 0 if "V-FIELDS" not in checks(vios) else 1
                detail = f"require_complete blank sentinel checks={sorted(checks(vios))}"
            elif mid == "drop_blank_register_digest":
                bad = deepcopy(base)
                bad["provenance"]["register_sha256"] = ""
                vios, _ = val.validate(
                    bad, register_path=regp, graph=cat.build_graph(bad)
                )
                code = 0 if "REACH-6" not in checks(vios) else 1
                detail = f"blank digest checks={sorted(checks(vios))}"
            elif mid == "invert_cli_exit_guard":
                bad = deepcopy(base)
                bad["items"][1]["dependencies"] = ["R-NOPE"]
                cpath = root / "catalog.json"
                gpath = root / "graph.json"
                cpath.write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                gpath.write_text(
                    json.dumps(cat.build_graph(bad), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                code = int(
                    val.main(
                        [
                            "--catalog",
                            str(cpath),
                            "--graph",
                            str(gpath),
                            "--register",
                            str(regp),
                        ]
                    )
                )
                detail = "CLI dangling dependency"
            elif mid == "invert_reach1_missing_dep":
                bad = deepcopy(base)
                bad["items"][1]["dependencies"] = ["R-NOPE"]
                vios, _ = val.validate(
                    bad, register_path=regp, graph=cat.build_graph(bad)
                )
                code = 0 if "REACH-1" not in checks(vios) else 1
                detail = f"dangling dep checks={sorted(checks(vios))}"
            elif mid == "invert_reach5_terminal":
                bad = deepcopy(base)
                bad["items"][0]["disposition"] = "PROBABLY-FINE"
                vios, _ = val.validate(
                    bad, register_path=regp, graph=cat.build_graph(bad)
                )
                code = 0 if "REACH-5" not in checks(vios) else 1
                detail = f"non-terminal disposition checks={sorted(checks(vios))}"
            else:
                vios, _ = val.validate(
                    base, register_path=regp, graph=cat.build_graph(base)
                )
                code = 0 if not vios else 1
                detail = f"clean catalog (not fail-open) checks={sorted(checks(vios))}"
        finally:
            _unload()
        return {
            "id": mid,
            "exit_code": code,
            "exits_zero_on_bad_input": code == 0,
            "detail": detail,
        }
