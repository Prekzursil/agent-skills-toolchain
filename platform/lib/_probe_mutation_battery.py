"""MUTATION HARNESS: does the conformance suite actually protect the schema?

A green suite is not evidence. This deliberately WEAKENS the schema (and the
reducer) one change at a time, in an isolated copy of the tree, and requires the
suite to go RED for every mutation. A mutation that SURVIVES is a hole in the
tests, reported as such.

Isolation: nothing is written to the real repo. The tree is rebuilt under a temp
directory; the 5.3 MB catalog is hardlinked (read-only use) rather than copied.

Run:  python platform/lib/_probe_mutation_battery.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "platform" / "lib"
SCHEMA = REPO / "platform" / "schema" / "receipt.schema.json"
CATALOG_REL = Path("command-center") / "WORK-UNIT-CATALOG.json"


# --------------------------------------------------------------------------- #
# schema mutations: each must break at least one test
# --------------------------------------------------------------------------- #


def m_additional_properties_open(s: dict[str, Any]) -> str:
    s["$defs"]["receipt_core"]["additionalProperties"] = True
    return "receipt_core.additionalProperties false -> true (typos become silent)"


def m_drop_success_branch(s: dict[str, Any]) -> str:
    core = s["$defs"]["receipt_core"]
    core["allOf"] = [b for b in core["allOf"] if "SUCCESS" != _const_of(b)]
    return "remove the state==SUCCESS conditional branch entirely"


def _const_of(branch: dict[str, Any]) -> str | None:
    try:
        return branch["if"]["properties"]["state"]["const"]
    except (KeyError, TypeError):
        return None


def m_sentinel_anything(s: dict[str, Any]) -> str:
    s["$defs"]["sentinel"]["pattern"] = ".*"
    s["$defs"]["sentinel"]["minLength"] = 0
    return "sentinel pattern -> .* (any prose accepted)"


def m_sha256_anything(s: dict[str, Any]) -> str:
    s["$defs"]["sha256"]["pattern"] = ".*"
    return "sha256 pattern -> .* (truncated/uppercase hashes accepted)"


def m_unit_id_anything(s: dict[str, Any]) -> str:
    s["$defs"]["unit_id"]["pattern"] = ".*"
    return "unit_id pattern -> .* (lowercase/short ids accepted)"


def m_zero_byte_artifact_ok(s: dict[str, Any]) -> str:
    s["$defs"]["artifact"]["properties"]["bytes"]["minimum"] = 0
    return "artifact.bytes minimum 1 -> 0 (empty artifact accepted)"


def m_drop_required(s: dict[str, Any]) -> str:
    s["$defs"]["receipt_core"]["required"] = ["schema_version"]
    return "receipt_core.required -> [schema_version] only"


def m_timestamp_pattern_open(s: dict[str, Any]) -> str:
    s["$defs"]["iso_timestamp"].pop("pattern", None)
    s["$defs"]["iso_timestamp"].pop("format", None)
    return "iso_timestamp loses its pattern (naive local times accepted)"


def m_tests_allow_skip(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"]["tests"].pop("not", None)
    return "SUCCESS branch no longer forbids FAIL/ERROR/SKIP test results"


def m_controls_may_be_inert(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"]["negative_controls"].pop("allOf", None)
    return "SUCCESS branch no longer requires both-states controls"


def m_reviewer_any_verdict(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"]["reviewer"] = {"type": "object"}
    return "SUCCESS branch accepts any reviewer verdict"


def m_consumer_claim_enough(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"]["downstream_consumers"].pop("allOf", None)
    return "condition 12 becomes decorative (executed=false accepted)"


def m_open_p0_ok(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"].pop("defects", None)
    return "SUCCESS branch permits an open P0 defect"


def m_drop_security_fragment(s: dict[str, Any]) -> str:
    s["$defs"].pop("security_report", None)
    return "delete the $defs/security_report fragment 24 units reference"


def m_evidence_single_ok(s: dict[str, Any]) -> str:
    for branch in s["$defs"]["receipt_core"]["allOf"]:
        if _const_of(branch) == "SUCCESS":
            branch["then"]["properties"]["evidence"].pop("minItems", None)
    return "SUCCESS branch accepts a single evidence item (single-signal)"


def m_failure_not_required(s: dict[str, Any]) -> str:
    core = s["$defs"]["receipt_core"]
    core["allOf"] = [
        b
        for b in core["allOf"]
        if not (
            isinstance(b.get("then"), dict) and b["then"].get("required") == ["failure"]
        )
    ]
    return "non-SUCCESS states no longer need a failure block"


SCHEMA_MUTATIONS: list[Callable[[dict[str, Any]], str]] = [
    m_additional_properties_open,
    m_drop_success_branch,
    m_sentinel_anything,
    m_sha256_anything,
    m_unit_id_anything,
    m_zero_byte_artifact_ok,
    m_drop_required,
    m_timestamp_pattern_open,
    m_tests_allow_skip,
    m_controls_may_be_inert,
    m_reviewer_any_verdict,
    m_consumer_claim_enough,
    m_open_p0_ok,
    m_drop_security_fragment,
    m_evidence_single_ok,
    m_failure_not_required,
]

# --------------------------------------------------------------------------- #
# reducer mutations: textual patches to receipt_schema_gate.py
# --------------------------------------------------------------------------- #

REDUCER_MUTATIONS: list[tuple[str, str, str]] = [
    (
        "reducer always reports SATISFIED (the no-op gate)",
        "        cond.append(ConditionOutcome(n, CONDITION_TEXT[n], outcome, basis))",
        "        cond.append(ConditionOutcome(n, CONDITION_TEXT[n], SATISFIED, basis))",
    ),
    (
        "NOT-CHECKED folded into a pass",
        "        return self.outcome in (UNSATISFIED, NOT_CHECKED)",
        "        return self.outcome == UNSATISFIED",
    ),
    (
        "sentinel no longer checked against unit_id",
        "    elif unit_id not in sentinel:",
        "    elif False:",
    ),
    (
        "sha256 no longer re-hashed off disk",
        "                digest = _sha256_file(p)",
        "                digest = a.get('sha256')",
    ),
    (
        "same-probe-rerun check removed",
        "                if srcs & vers:",
        "                if False:",
    ),
    (
        "complete() ignores schema errors",
        "        if self.schema_errors:\n            return False",
        "        if False:\n            return False",
    ),
]


#: Mutants proved to change NOTHING observable. An equivalent mutant is not a
#: test hole and must not be "fixed" by contorting a test -- but it may only be
#: listed here with a proof, never with an assumption.
EQUIVALENT_MUTANTS: dict[str, str] = {
    "complete() ignores schema errors": (
        "PROVED EQUIVALENT. evaluate_gate_a() adds condition 4 as UNSATISFIED iff "
        "schema_errors is non-empty (receipt_schema_gate.py, the `if schema_errors` branch of "
        "condition 4), and ConditionOutcome.blocking is true for UNSATISFIED, so "
        "complete is False through condition 4 with or without the short-circuit. The "
        "only other path, the non-dict early return, yields conditions==[] which "
        "complete already rejects via len(conditions) != 12. Pinned by "
        "test_schema_invalidity_is_caught_by_condition_4_alone."
    ),
}


def build_tree(dst: Path) -> Path:
    lib = dst / "platform" / "lib"
    sch = dst / "platform" / "schema"
    lib.mkdir(parents=True)
    sch.mkdir(parents=True)
    for name in ("receipt_schema_gate.py", "test_receipt_schema_gate.py"):
        shutil.copy2(LIB / name, lib / name)
    shutil.copy2(SCHEMA, sch / SCHEMA.name)
    (dst / CATALOG_REL.parent).mkdir(parents=True, exist_ok=True)
    src, tgt = REPO / CATALOG_REL, dst / CATALOG_REL
    try:
        os.link(src, tgt)
    except OSError:
        shutil.copy2(src, tgt)
    return lib


def run_suite(lib: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_receipt_schema_gate.py",
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
        ],
        cwd=lib,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    survivors: list[str] = []
    equivalent: list[str] = []
    killed = 0
    total = 0

    with tempfile.TemporaryDirectory(prefix="receipt-mut-") as td:
        base = Path(td) / "baseline"
        lib = build_tree(base)

        # CONTROL: the unmutated tree must be GREEN. If it is red, every
        # "mutation killed" below would be meaningless.
        rc, out = run_suite(lib)
        tail = out.strip().splitlines()[-1] if out.strip() else "<no output>"
        print(f"[CONTROL] unmutated suite rc={rc} :: {tail}")
        if rc != 0:
            print(
                "CONTROL-BROKEN: baseline suite is not green; mutation results are uncitable."
            )
            print(out[-3000:])
            return 1

        for fn in SCHEMA_MUTATIONS:
            total += 1
            work = Path(td) / f"schema-{total}"
            wlib = build_tree(work)
            spath = work / "platform" / "schema" / SCHEMA.name
            schema = json.loads(spath.read_bytes().decode("utf-8"))
            label = fn(schema)
            spath.write_text(json.dumps(schema, indent=2), encoding="utf-8")
            rc, out = run_suite(wlib)
            status = "KILLED" if rc != 0 else "SURVIVED"
            if rc != 0:
                killed += 1
            else:
                survivors.append(f"[schema] {label}")
            print(f"  [{status}] schema: {label}")

        for label, old, new in REDUCER_MUTATIONS:
            total += 1
            work = Path(td) / f"reducer-{total}"
            wlib = build_tree(work)
            gpath = wlib / "receipt_schema_gate.py"
            text = gpath.read_text(encoding="utf-8")
            if old not in text:
                print(
                    f"  [BROKEN-MUTANT] reducer: {label} :: anchor not found, mutation not applied"
                )
                survivors.append(f"[reducer-anchor-missing] {label}")
                continue
            gpath.write_text(text.replace(old, new, 1), encoding="utf-8")
            rc, out = run_suite(wlib)
            if rc != 0:
                killed += 1
                status = "KILLED"
            elif label in EQUIVALENT_MUTANTS:
                equivalent.append(f"[reducer] {label}")
                status = "EQUIVALENT"
            else:
                survivors.append(f"[reducer] {label}")
                status = "SURVIVED"
            print(f"  [{status}] reducer: {label}")

    print()
    print(
        f"mutations: {total}  killed: {killed}  "
        f"equivalent: {len(equivalent)}  survived: {len(survivors)}"
    )
    for e in equivalent:
        print(f"  EQUIVALENT (no observable change): {e}")
        print(f"      proof: {EQUIVALENT_MUTANTS[e.split('] ', 1)[1]]}")
    for s in survivors:
        print(f"  SURVIVOR: {s}")
    if survivors:
        print("FAILED:mutation-battery surviving mutants indicate untested behaviour")
        return 1
    print(
        f"SUCCESS:mutation-battery {killed}/{total} mutations turned the suite red; "
        f"{len(equivalent)} proved equivalent; 0 unexplained survivors"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
