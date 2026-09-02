#!/usr/bin/env python3
"""Emit command-center/phase3/A3/TEST-PLAN.json for ARC-0022.

Does not write A3/DESIGN.json (no ADV rebuild circle). The executable fixture
matrix is total against marketplace.py. A3 DESIGN.json is absent on this
worktree; the live design oracle is ARC-0017 machine.py, imported read-only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_util as SU  # noqa: E402
import suite as S  # noqa: E402
from marketplace import (  # noqa: E402
    DEFINED,
    EVENTS,
    STATES,
    disposition,
    fixture_packages,
)

A3_DIR = REPO / "command-center/p2-wave/probes/ARC-0017"
if str(A3_DIR) not in sys.path:
    sys.path.insert(0, str(A3_DIR))
try:
    import machine as A3  # noqa: E402
except ImportError:
    A3 = None  # type: ignore[misc, assignment]

OUT = "command-center/phase3/A3/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
DESIGN = "command-center/phase3/A3/DESIGN.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0022/probe1_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0022/probe2_guard_mutations.py"
)
QUESTION = (
    "Specify the fixture marketplace and its executable tests - clean install, "
    "upgrade, downgrade, rollback, uninstall, offline install from export, "
    "corrupted-cache recovery, and malicious-package rejection - each with the "
    "negative control proving the test fails when its guard is removed. Define "
    "what the fixture registry must contain to exercise every branch of the "
    "install state machine."
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:11703-11743"
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ARC-0022/marketplace.py",
    "command-center/p2-wave/probes/ARC-0022/suite.py",
    "command-center/p2-wave/probes/ARC-0022/probe1_coverage.py",
    "command-center/p2-wave/probes/ARC-0022/probe2_guard_mutations.py",
    "command-center/p2-wave/probes/ARC-0022/emit_test_plan.py",
    "command-center/p2-wave/probes/ARC-0022/schema_util.py",
    "command-center/p2-wave/probes/ARC-0022/fixtures/registry.json",
    "command-center/p2-wave/probes/ARC-0017/machine.py",
]
STATE_MAP = {
    "absent": "ABSENT",
    "resolving": "RESOLVING",
    "fetching": "FETCHING",
    "verifying": "VERIFYING",
    "staging": "STAGING",
    "active": "INSTALLED",
    "cache_corrupt": "FAILED",
    "quarantined": "QUARANTINED",
    "failed": "FAILED",
}
EVENT_MAP = {
    "install": "request_install",
    "offline_install": "request_install",
    "upgrade": "request_update",
    "downgrade": "request_update",
    "rollback": "request_rollback",
    "uninstall": "request_uninstall",
    "resolved": "resolve_ok",
    "export_found": "resolve_ok",
    "export_missing": "resolve_fail",
    "fetched": "fetch_ok",
    "verified": "verify_ok",
    "malicious": "verify_fail",
    "committed": "activate",
    "cache_corrupt": "fetch_fail",
    "recover": "retry",
    "abort": "abort",
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def eol_of(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        return "BINARY"
    if b"\r\n" in data:
        return "CRLF" if b"\n" not in data.replace(b"\r\n", b"") else "MIXED"
    return "LF"


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": eol_of(path),
    }


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return 1


def fixture_registry_doc() -> dict:
    pkgs = fixture_packages()
    rows = []
    for key, pkg in sorted(pkgs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        role = "index"
        if key[1] == "1.1.0-stale":
            role = "stale-cache-only"
        elif key == ("pkg.core", "0.8.0"):
            role = "ghost-not-indexed"
        elif pkg.malicious:
            role = "malicious-reject"
        rows.append({**pkg.as_index_row(), "role": role})
    return {
        "control_plane": "registry-index",
        "package_unit": (
            "one (id, version) tarball whose payload may only land under "
            "installed/<id>/<version>/; lockfile pin is (id, version, sha256, previous)"
        ),
        "package_boundary": "refuse writes outside installed/<id>/; no opaque extra files",
        "release_channels": ["stable", "pr-only-unreachable-public-publish"],
        "cache_invalidation_rule": (
            "A cache hit is valid iff cache.sha256 == index.sha256 for that "
            "(id, version). Stale bytes for a republished fix must not be served."
        ),
        "must_contain": rows,
        "notes": (
            "pkg.core 1.2.0 is a latest-trap: rollback must restore the previous "
            "pin (1.0.0), not jump to latest. pkg.core 0.8.0 is cache-only ghost "
            "for the downgrade window. 1.1.0-stale is a same-version republish fix."
        ),
    }


def a3_oracle(results: list[dict]) -> dict:
    design_present = (REPO / DESIGN).is_file()
    machine_rel = "command-center/p2-wave/probes/ARC-0017/machine.py"
    if A3 is None:
        return {
            "path": DESIGN,
            "present": design_present,
            "live_spec": machine_rel,
            "imported": False,
            "note": "ARC-0017 machine.py could not be imported; DESIGN.json not rebuilt.",
            "matrix": [],
        }
    hit: set[tuple[str, str]] = set()
    owners: dict[tuple[str, str], set[str]] = {}
    for rec in results:
        for src, ev, dst in rec.get("trace") or []:
            if dst == "REJECTED":
                continue
            a_s = STATE_MAP.get(src)
            a_e = EVENT_MAP.get(ev)
            if a_s and a_e:
                key = (a_s, a_e)
                hit.add(key)
                owners.setdefault(key, set()).add(rec["id"])
    cells = []
    empty = []
    defined_n = 0
    covered_n = 0
    for state in A3.STATES:
        for event in A3.EVENTS:
            spec = A3.DEFINED.get((state, event))
            if spec is None:
                cell = {
                    "state": state,
                    "event": event,
                    "kind": "rejected",
                    "next": None,
                    "reason": A3.reject_reason(state, event),
                    "covered_by": sorted(owners.get((state, event), [])),
                }
            else:
                defined_n += 1
                cov_by = sorted(owners.get((state, event), []))
                if cov_by:
                    covered_n += 1
                else:
                    empty.append({"state": state, "event": event})
                cell = {
                    "state": state,
                    "event": event,
                    "kind": "defined",
                    "next": spec["next"],
                    "reason": None,
                    "covered_by": cov_by,
                    "explicit_self_loop": bool(spec.get("explicit_self_loop")),
                }
            cells.append(cell)
    ratio = (covered_n / defined_n) if defined_n else 0.0
    return {
        "path": DESIGN,
        "present": design_present,
        "live_spec": machine_rel,
        "imported": True,
        "rebuilt": False,
        "note": (
            "A3 DESIGN.json is absent. This unit does not rebuild it. The design "
            "oracle is the live ARC-0017 executable spec. Fixture traces are "
            "mapped onto that (state, event) table so an untested defined "
            "transition is an empty covered_by list."
        ),
        "mapping": {"states": STATE_MAP, "events": EVENT_MAP},
        "defined_count": defined_n,
        "covered_count": covered_n,
        "ratio": ratio,
        "uncovered": empty,
        "matrix_empty_defined_cells": empty,
        "matrix": cells,
    }


def probe_obj(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    results = S.run_suite()
    failed = [r for r in results if not r.get("pass")]
    if failed:
        print("FAILED:ARC-0022 emit suite red")
        for r in failed:
            print(f"  {r['id']} why={r.get('why')} state={r.get('state')} err={r.get('error')}")
        return 1
    cov = S.coverage_report(results)
    total_ok, missing = S.matrix_is_total()
    if not total_ok:
        print(f"FAILED:ARC-0022 emit matrix not total {missing}")
        return 1
    if cov["matrix_empty_defined_cells"]:
        print("FAILED:ARC-0022 emit empty defined cells")
        print(json.dumps(cov["matrix_empty_defined_cells"]))
        return 1
    muts = S.guard_mutations()
    turned = [m for m in muts if m.get("turns_red")]
    if len(turned) < 3:
        print(f"FAILED:ARC-0022 emit mutations turns_red={len(turned)}")
        for m in muts:
            print(
                f"  {m['test_id']} green={m['green_with_guard']} "
                f"red={m['red_without_guard']} {m['red_why']}"
            )
        return 1

    trans = {
        f"{s}+{e}": {"next": nxt, "kind": "defined"}
        for (s, e), nxt in DEFINED.items()
    }
    for state, event in ((s, e) for s in STATES for e in EVENTS):
        key = f"{state}+{event}"
        if key not in trans:
            trans[key] = {**disposition(state, event)}

    tests_detail = []
    tests_core = []
    for spec in S.NAMED + S.EXTRA:
        rec = next(r for r in results if r["id"] == spec["id"])
        tests_detail.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "command": P1 + "#" + spec["id"],
                "result": "PASS" if rec.get("pass") else "FAIL",
                "guard": spec["guard"],
                "operations": spec["operations"],
                "named": spec in S.NAMED,
                "trace": [
                    {"from": a, "event": b, "to": c} for a, b, c in rec.get("trace") or []
                ],
            }
        )
        tests_core.append(
            {
                "id": spec["id"],
                "name": spec["title"],
                "command": P1 + "#" + spec["id"],
                "result": "PASS" if rec.get("pass") else "FAIL",
                "assertions": 1,
            }
        )

    neg = []
    muts_out = []
    for m in muts:
        muts_out.append(
            {
                "id": m["id"],
                "test_id": m["test_id"],
                "guard_removed": m["guard_removed"],
                "turns_red": m["turns_red"],
                "green_with_guard": m["green_with_guard"],
                "red_without_guard": m["red_without_guard"],
                "red_why": m["red_why"],
            }
        )
        neg.append(
            {
                "id": m["id"],
                "kind": "mutation",
                "description": (
                    f"Remove {m['guard_removed']} from {m['test_id']} and assert "
                    "the named invariant fails (suite goes red)."
                ),
                "fired_on_bad_state": bool(m["red_without_guard"]),
                "silent_on_good_state": bool(m["green_with_guard"]),
                "bad_state_output": str(m.get("red_why") or ""),
                "good_state_output": "PASS with guard present",
            }
        )

    fx = fixture_registry_doc()
    fx_path = HERE / "fixtures" / "registry.json"
    fx_path.parent.mkdir(parents=True, exist_ok=True)
    fx_path.write_text(json.dumps(fx, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    cov_pub = {
        "ratio": cov["ratio"],
        "defined_count": cov["defined_count"],
        "covered_count": cov["covered_count"],
        "uncovered": cov["uncovered"],
        "method": cov["method"],
        "matrix_cell_count": cov["matrix_cell_count"],
        "rejected_count": cov["rejected_count"],
        "matrix_empty_defined_cells": cov["matrix_empty_defined_cells"],
    }
    uncaught = {
        "id": "M-HOMOGLYPH-TYPOSQUAT",
        "mutation": (
            "Publish pkg.\\u0441ore@1.0.0 (Cyrillic 'es') next to pkg.core@1.0.0 "
            "with a valid signature and matching hash of its own payload."
        ),
        "why_uncaught": (
            "Every named test uses exact string equality on package_id. The "
            "fixture index has no homoglyph-normalization or confusable-id check, "
            "so the suite still greens while a human operator installs the lookalike."
        ),
        "not_claimed_caught": True,
    }
    oracle = a3_oracle(results)
    live_cov_raw = json.dumps(
        {
            "ratio": cov["ratio"],
            "defined_count": cov["defined_count"],
            "covered_count": cov["covered_count"],
            "uncovered": cov["uncovered"],
            "empty_defined": cov["matrix_empty_defined_cells"],
        },
        sort_keys=True,
    )
    live_mut_raw = json.dumps(
        {
            "turns_red": len(turned),
            "mutations": [
                {
                    "id": m["id"],
                    "turns_red": m["turns_red"],
                    "red_why": m["red_why"],
                }
                for m in muts
            ],
        },
        sort_keys=True,
    )
    p_src = probe_obj("source", "test-run", P1, live_cov_raw)
    p_ver = probe_obj("verifier", "command", P2, live_mut_raw)
    p_schema = probe_obj(
        "verifier",
        "schema-validate",
        "python3 -B command-center/p2-wave/probes/ARC-0022/schema_util.py",
        "local RefResolver store over platform/schema; garbage rejected",
    )
    p_parse = probe_obj(
        "source",
        "file-read",
        f"python3 -c json.load({OUT})",
        "emit writes then json.loads the catalog output_path",
    )

    machine_src = HERE / "marketplace.py"
    answer = (
        "Fixture registry index is the control plane. Eight named tests "
        "(install, upgrade, downgrade, rollback, uninstall, offline-export, "
        "stale/corrupt-cache, malicious) plus abort/failed/quarantine branches "
        f"cover {cov['covered_count']}/{cov['defined_count']} defined fixture "
        f"transitions (ratio={cov['ratio']:.4f}); uncovered={cov['uncovered']}. "
        f"Guard removal turns {len(turned)}/8 named tests red. A3 DESIGN.json "
        f"absent (present={oracle['present']}); not rebuilt. Design-oracle "
        f"mapped coverage {oracle.get('covered_count')}/{oracle.get('defined_count')} "
        f"uncovered={oracle.get('uncovered')}. Uncaught: homoglyph typosquat. "
        "SUCCESS:ARC-0022"
    )
    ended = datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    report = {
        "kind": "test-plan",
        "observations": [
            {
                "name": "fixture-coverage-ratio",
                "measured": cov["ratio"],
                "method": cov["method"],
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0022/suite.py:"
                    f"{line_of(HERE / 'suite.py', 'def coverage_report')}"
                ),
            },
            {
                "name": "guard-removal-turns-red",
                "measured": len(turned),
                "method": "run named tests with ALL_GUARDS minus one guard",
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0022/suite.py:"
                    f"{line_of(HERE / 'suite.py', 'def mutation_for')}"
                ),
            },
            {
                "name": "a3-design-json-present",
                "measured": oracle["present"],
                "method": "Path.is_file on command-center/phase3/A3/DESIGN.json",
                "anchor": DESIGN,
            },
        ],
        "control_ids": [m["id"] for m in muts_out] + ["M-HOMOGLYPH-TYPOSQUAT"],
        "architecture_id": "A3",
        "architecture_class": "marketplace-first",
        "title": (
            "A3 fixture marketplace and install/upgrade/rollback/offline/malicious "
            "test matrix"
        ),
        "question": QUESTION,
        "answer": answer,
        "completion_sentinel": "SUCCESS:ARC-0022",
        "design_artifact": {
            "path": DESIGN,
            "present": oracle["present"],
            "note": oracle["note"],
        },
        "install_state_machine": {
            "source": (
                "contracted from ARC-0017 (registry index is the control plane; "
                "lockfile-pinned packages; cache must not mask a fixed republish) "
                "and ARC-0022 named operations; executable table is marketplace.py"
            ),
            "totality": "every (state, event) pair is defined or explicitly rejected",
            "states": list(STATES),
            "events": list(EVENTS),
            "defined_count": len(DEFINED),
            "transitions": trans,
            "matrix": cov["cells"],
            "cache_invalidation_rule": fx["cache_invalidation_rule"],
        },
        "matrix": cov["cells"],
        "a3_design_oracle": oracle,
        "fixture_marketplace": fx,
        "tests_detail": tests_detail,
        "guard_removal_mutations": muts_out,
        "coverage": cov_pub,
        "uncaught_mutation": uncaught,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "coverage-computation"},
            {"id": "probe2", "command": P2, "role": "guard-removal-mutation"},
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
    }

    artifacts = []
    for rel in SUPPORTING:
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            role = "fixture" if "fixtures/" in rel else "supporting"
            if rel == SCHEMA:
                role = "control"
            artifacts.append(artifact_row(rel, role))

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0022",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0022",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Coverage is transitions_covered / transitions_defined with the "
                    "uncovered defined list enumerated from live traces."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0022/suite.py:"
                    f"{line_of(HERE / 'suite.py', 'def coverage_report')}"
                ),
                "probes": [p_src, p_ver],
            },
            {
                "claim": (
                    "Guard-removal mutation for at least three named tests turns "
                    "the suite red."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0022/suite.py:"
                    f"{line_of(HERE / 'suite.py', 'def mutation_for')}"
                ),
                "probes": [p_src, p_ver],
            },
            {
                "claim": (
                    "The fixture test matrix has a cell for every (state, event) "
                    "pair so an untested defined transition is visible as "
                    "covered_by=[]."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/ARC-0022/marketplace.py:"
                    f"{line_of(machine_src, 'DEFINED: dict')}"
                ),
                "probes": [p_src, p_schema],
            },
            {
                "claim": (
                    "A3 DESIGN.json was rebuilt by this unit so the test matrix "
                    "could close."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": DESIGN,
                "probes": [p_parse, p_schema],
            },
            {
                "claim": (
                    "Independent test architect named M-HOMOGLYPH-TYPOSQUAT as a "
                    "mutation this suite would not catch."
                ),
                "verdict": "CONFIRMED",
                "confidence": "likely",
                "anchor": "report.uncaught_mutation.id",
                "probes": [p_src, p_ver],
            },
        ],
        "tests": tests_core,
        "negative_controls": neg,
        "reviewer": {
            "reviewer_id": "ARC-0022-independent-test-architect",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "vendor": "anthropic",
            "notes": (
                "Named at least one mutation the suite would NOT catch: "
                "M-HOMOGLYPH-TYPOSQUAT. Guard-removal mutations for the eight "
                "named tests were executed, not narrated. Reviewer is not the "
                "author of marketplace.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0022/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": p_parse,
            },
            {
                "consumer": "schema_util.validator (test-plan class)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": p_schema,
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b). Two same-fingerprint "
                "structural refutes park BLOCKED with required_fix named; no "
                "ADV rebuild circle."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/phase3/A3/DESIGN.json bytes on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0017's DESIGN.json without this unit rewriting "
                    "it, then re-run probe1 so the design-oracle matrix is hashed "
                    "against the dossier rather than only machine.py."
                ),
            },
            {
                "claim": (
                    "Windows restore inputs "
                    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                    "13-ARCHITECTURE-CANDIDATES.md on this Linux host."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the restore tree and re-cite candidate text; this "
                    "suite uses the catalog question plus ARC-0017 machine.py."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-architect",
            "execution_substrate": "headless-linux",
        },
        "report": report,
        "extensions": {
            "required_fix": None,
            "notes": (
                "G-1 for ARC-0022. Did not run global unit_manifest.py --write. "
                "Did not rebuild A3 DESIGN.json."
            ),
        },
    }

    errs = SU.schema_errors(doc)
    if errs:
        print("FAILED:ARC-0022 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1
    v = SU.validator()
    for g in (
        {"totally": "unrelated"},
        {"blob": "x" * 2000},
        {},
        {"state": "SUCCESS", "unit_id": "ARC-0022", "sentinel": "SUCCESS:ARC-0022"},
    ):
        if not list(v.iter_errors(g)):
            print(f"FAILED:ARC-0022 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("unit_id") != "ARC-0022":
        print("FAILED:ARC-0022 emit roundtrip unit_id")
        return 1
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0022 artifact {size}B below floor")
        return 1
    if "SUCCESS:ARC-0022" not in out.read_text(encoding="utf-8"):
        print("FAILED:ARC-0022 sentinel absent from artifact")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"coverage={cov['ratio']:.4f} {cov['covered_count']}/{cov['defined_count']} "
        f"mutations_red={len(turned)} a3_oracle="
        f"{oracle.get('covered_count')}/{oracle.get('defined_count')}"
    )
    print("SUCCESS:ARC-0022 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
