"""ADV-0008 clause enumeration + scratch-system violation harness.

Probe 1 indexes contract clauses and maps them to TEST-REGISTRY test ids.
Probe 2 copies the mini-system into a scratch directory, mutates SYSTEM flags
(not tests), runs the named test, then reverts the mutation. A clause whose
named test stays green is uncovered regardless of the registry claim.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0008"

FIXTURE_CONTRACT = HERE / "fixtures" / "14-NO-REGRESSION-CONTRACT.md"
FIXTURE_REGISTRY = HERE / "fixtures" / "TEST-REGISTRY.json"
SYSTEM_DIR = HERE / "fixtures" / "system"
MUTATIONS_PATH = HERE / "fixtures" / "mutations.json"

LIVE_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"
LIVE_CONTRACT_CANDIDATES = (
    REPO / "14-NO-REGRESSION-CONTRACT.md",
    REPO / "command-center" / "14-NO-REGRESSION-CONTRACT.md",
    REPO / "command-center" / "sources" / "14-NO-REGRESSION-CONTRACT.md",
    REPO / "docs" / "14-NO-REGRESSION-CONTRACT.md",
    Path.home() / ".claude" / "harness-restore-20260806" / "14-NO-REGRESSION-CONTRACT.md",
)

HEADING_RE = re.compile(r"^###\s+(CLAUSE-[A-Z0-9-]+)(?:\s+(\S.*))?$")


def sha256_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def live_inputs() -> dict[str, Any]:
    contract_hits: list[str] = []
    for path in LIVE_CONTRACT_CANDIDATES:
        if path.is_file() and path.stat().st_size > 0:
            rel = str(path)
            try:
                rel = str(path.resolve().relative_to(REPO.resolve()))
            except ValueError:
                rel = str(path)
            contract_hits.append(rel)
    for base in (REPO, REPO / "command-center"):
        if not base.is_dir():
            continue
        for path in base.glob("*NO-REGRESSION*"):
            if path.is_file():
                rel = str(path.relative_to(REPO)).replace("\\", "/")
                if rel not in contract_hits:
                    contract_hits.append(rel)
    registry_present = LIVE_REGISTRY.is_file() and LIVE_REGISTRY.stat().st_size > 0
    return {
        "contract_hits": contract_hits,
        "contract_present": bool(contract_hits),
        "registry_path": "command-center/TEST-REGISTRY.json",
        "registry_present": registry_present,
        "fixture_contract": str(
            FIXTURE_CONTRACT.relative_to(REPO)
        ).replace("\\", "/"),
        "fixture_registry": str(
            FIXTURE_REGISTRY.relative_to(REPO)
        ).replace("\\", "/"),
    }


def parse_clauses(markdown: str) -> list[dict[str, Any]]:
    lines = markdown.replace("\r\n", "\n").split("\n")
    clauses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal current, body
        if current is None:
            return
        text = " ".join(part.strip() for part in body if part.strip())
        current["text"] = text
        current["atomic"] = bool(
            re.search(r"\b(MUST(?:\s+NOT)?|SHALL(?:\s+NOT)?)\b", text, re.I)
        )
        clauses.append(current)
        current = None
        body = []

    for line in lines:
        match = HEADING_RE.match(line.strip())
        if match:
            flush()
            current = {
                "id": match.group(1),
                "slug": (match.group(2) or "").strip(),
            }
            body = []
            continue
        if current is not None:
            if line.startswith("#"):
                flush()
                continue
            body.append(line)
    flush()
    return clauses


def clause_map_from_registry(reg: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}

    def add(cid: str, tid: str) -> None:
        if not cid or not tid:
            return
        bucket = mapping.setdefault(cid, [])
        if tid not in bucket:
            bucket.append(tid)

    for row in reg.get("clause_map") or []:
        if isinstance(row, dict):
            add(str(row.get("clause_id") or ""), str(row.get("test_id") or ""))
    for suite in reg.get("suites") or []:
        if not isinstance(suite, dict):
            continue
        for test in suite.get("tests") or []:
            if not isinstance(test, dict):
                continue
            tid = str(test.get("id") or "")
            for cid in test.get("covers") or []:
                add(str(cid), tid)
    return mapping


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def defined_tests(test_path: Path) -> set[str]:
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def enumerate_clauses() -> dict[str, Any]:
    live = live_inputs()
    contract_text = FIXTURE_CONTRACT.read_text(encoding="utf-8")
    clauses = parse_clauses(contract_text)
    registry = load_registry(FIXTURE_REGISTRY)
    mapping = clause_map_from_registry(registry)
    tests_on_disk = defined_tests(SYSTEM_DIR / "test_contract_gate.py")
    rows = []
    for clause in clauses:
        cid = clause["id"]
        tests = list(mapping.get(cid) or [])
        missing = [t for t in tests if t not in tests_on_disk]
        rows.append(
            {
                "id": cid,
                "slug": clause.get("slug") or "",
                "text": clause["text"],
                "atomic": clause["atomic"],
                "mapped_tests": tests,
                "mapped": bool(tests),
                "missing_tests": missing,
                "source": "fixture-contract",
            }
        )
    return {
        "unit_id": UNIT,
        "probe": "probe1-enumerate",
        "live": live,
        "contract_sha256": sha256_text(contract_text),
        "registry_sha256": sha256_file(FIXTURE_REGISTRY),
        "n_clauses": len(rows),
        "n_mapped": sum(1 for r in rows if r["mapped"]),
        "n_unmapped": sum(1 for r in rows if not r["mapped"]),
        "n_missing_tests": sum(1 for r in rows if r["missing_tests"]),
        "clauses": rows,
        "defined_tests": sorted(tests_on_disk),
    }


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_named_test(scratch: Path, test_id: str) -> dict[str, Any]:
    gate_path = scratch / "contract_gate.py"
    test_path = scratch / "test_contract_gate.py"
    if test_id not in defined_tests(test_path):
        return {
            "test_id": test_id,
            "status": "MISSING",
            "passed": False,
            "error": "test-function-absent",
        }
    names = ("contract_gate", "test_contract_gate")
    saved = {name: sys.modules.pop(name, None) for name in names}
    inserted = False
    try:
        sys.path.insert(0, str(scratch))
        inserted = True
        importlib.invalidate_caches()
        _load_module(gate_path, "contract_gate")
        test_mod = _load_module(test_path, "test_contract_gate")
        fn = getattr(test_mod, test_id, None)
        if fn is None:
            return {
                "test_id": test_id,
                "status": "MISSING",
                "passed": False,
                "error": "attribute-absent",
            }
        fn()
        return {"test_id": test_id, "status": "PASS", "passed": True, "error": ""}
    except AssertionError as exc:
        return {
            "test_id": test_id,
            "status": "FAIL",
            "passed": False,
            "error": f"AssertionError:{exc}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "test_id": test_id,
            "status": "ERROR",
            "passed": False,
            "error": f"{type(exc).__name__}:{exc}\n{traceback.format_exc()[-500:]}",
        }
    finally:
        for name in names:
            sys.modules.pop(name, None)
            if saved[name] is not None:
                sys.modules[name] = saved[name]
        if inserted:
            try:
                sys.path.remove(str(scratch))
            except ValueError:
                pass


def classify_pair(baseline: dict[str, Any], after: dict[str, Any], reverted: dict[str, Any]) -> str:
    if baseline.get("status") == "MISSING" or after.get("status") == "MISSING":
        return "uncovered-missing-test"
    if baseline.get("status") != "PASS":
        return "baseline-not-green"
    if after.get("status") == "FAIL" and reverted.get("status") == "PASS":
        return "covered"
    if after.get("status") == "FAIL" and reverted.get("status") != "PASS":
        return "harness-broken"
    if after.get("status") == "PASS":
        return "uncovered-survived"
    return "uncovered-other"


def violate_mapped_pairs() -> dict[str, Any]:
    enumerated = enumerate_clauses()
    mutations = json.loads(MUTATIONS_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="adv0008-scratch-") as tmp:
        scratch = Path(tmp) / "system"
        shutil.copytree(SYSTEM_DIR, scratch)
        test_sha_before = sha256_file(scratch / "test_contract_gate.py")
        for clause in enumerated["clauses"]:
            cid = clause["id"]
            tests = list(clause["mapped_tests"] or [])
            mutation = mutations.get(cid)
            if not tests:
                results.append(
                    {
                        "clause_id": cid,
                        "mapped_tests": [],
                        "classification": "uncovered-unmapped",
                        "mutated_system": False,
                        "mutated_test": False,
                    }
                )
                continue
            # Evidence requires one named test per mapped pair. Use the first
            # registry id; extra ids are recorded but not required for settle.
            test_id = tests[0]
            system_path = scratch / "contract_gate.py"
            original = system_path.read_text(encoding="utf-8")
            baseline = run_named_test(scratch, test_id)
            applied = False
            mutation_error = ""
            if isinstance(mutation, dict):
                old, new = mutation["old"], mutation["new"]
                if old not in original:
                    mutation_error = "old-string-absent"
                elif original.count(old) != 1:
                    mutation_error = "old-string-not-unique"
                else:
                    system_path.write_text(original.replace(old, new, 1), encoding="utf-8")
                    applied = True
            else:
                mutation_error = "no-mutation-recipe"
            after = run_named_test(scratch, test_id)
            system_path.write_text(original, encoding="utf-8")
            reverted = run_named_test(scratch, test_id)
            test_sha_after = sha256_file(scratch / "test_contract_gate.py")
            classification = classify_pair(baseline, after, reverted)
            if mutation_error and classification == "covered":
                classification = "harness-broken"
            results.append(
                {
                    "clause_id": cid,
                    "mapped_tests": tests,
                    "named_test": test_id,
                    "mutation": mutation,
                    "mutated_system": applied,
                    "mutated_test": test_sha_after != test_sha_before,
                    "mutation_error": mutation_error,
                    "baseline": baseline,
                    "after_violation": after,
                    "after_revert": reverted,
                    "classification": classification,
                }
            )
        test_sha_final = sha256_file(scratch / "test_contract_gate.py")
        tests_untouched = test_sha_final == test_sha_before

    killed = [r for r in results if r["classification"] == "covered"]
    survived = [r for r in results if r["classification"] == "uncovered-survived"]
    missing = [r for r in results if r["classification"] == "uncovered-missing-test"]
    unmapped = [r for r in results if r["classification"] == "uncovered-unmapped"]
    broken = [r for r in results if r["classification"] == "harness-broken"]
    revert_green = all(
        r.get("after_revert", {}).get("status") == "PASS" for r in killed
    )
    return {
        "unit_id": UNIT,
        "probe": "probe2-violate",
        "n_pairs": len(results),
        "n_killed": len(killed),
        "n_survived": len(survived),
        "n_missing_test": len(missing),
        "n_unmapped": len(unmapped),
        "n_harness_broken": len(broken),
        "killed_ids": [r["clause_id"] for r in killed],
        "survived_ids": [r["clause_id"] for r in survived],
        "missing_test_ids": [r["clause_id"] for r in missing],
        "unmapped_ids": [r["clause_id"] for r in unmapped],
        "harness_broken_ids": [r["clause_id"] for r in broken],
        "revert_returns_green": bool(killed) and revert_green,
        "tests_file_untouched": tests_untouched,
        "at_least_one_killed": bool(killed),
        "pairs": results,
        "enumeration_n_clauses": enumerated["n_clauses"],
    }


def settle(enumerated: dict[str, Any], violated: dict[str, Any]) -> dict[str, Any]:
    by_clause = {p["clause_id"]: p for p in violated["pairs"]}
    targets: list[dict[str, Any]] = []
    for clause in enumerated["clauses"]:
        cid = clause["id"]
        pair = by_clause.get(cid) or {}
        klass = pair.get("classification") or "uncovered-other"
        claim = (
            f"Clause {cid} is asserted only in prose: no executable test goes "
            f"red when the clause is violated in the system. {clause['text']}"
        )
        if klass == "covered":
            verdict = "REFUTED"
            why = (
                "Named test went red after SYSTEM mutation and returned green "
                "after revert, so the mapping is load-bearing."
            )
        elif klass in {
            "uncovered-survived",
            "uncovered-missing-test",
            "uncovered-unmapped",
            "uncovered-other",
        }:
            verdict = "CONFIRMED"
            why = f"classification={klass}"
        elif klass == "harness-broken":
            verdict = "NOT-CHECKED"
            why = "revert did not restore green; red may be harness-caused"
        elif klass == "baseline-not-green":
            verdict = "NOT-CHECKED"
            why = "baseline named test was not green; mutation is uninterpretable"
        else:
            verdict = "NOT-CHECKED"
            why = f"classification={klass}"
        targets.append(
            {
                "id": cid,
                "text": claim,
                "verdict": verdict,
                "why": why,
                "classification": klass,
                "mapped_tests": clause["mapped_tests"],
                "named_test": pair.get("named_test"),
                "slug": clause.get("slug") or "",
            }
        )
    live = enumerated["live"]
    targets.append(
        {
            "id": "live-contract-clause-coverage",
            "text": (
                "Live 14-NO-REGRESSION-CONTRACT.md clause coverage on this "
                "worktree. Document hits="
                f"{live['contract_hits'] or []}."
            ),
            "verdict": "NOT-CHECKED",
            "why": (
                "live contract document absent; fixture clauses are labeled "
                "fixture and are not a substitute byte-copy"
            ),
            "classification": "live-absent",
        }
    )
    targets.append(
        {
            "id": "live-test-registry",
            "text": (
                "Live command-center/TEST-REGISTRY.json mappings for the "
                "no-regression contract."
            ),
            "verdict": "NOT-CHECKED",
            "why": "live TEST-REGISTRY.json absent; fixture registry is labeled fixture",
            "classification": "live-absent",
        }
    )
    return {
        "targets": targets,
        "live": live,
        "enumerated": enumerated,
        "violated": violated,
    }
