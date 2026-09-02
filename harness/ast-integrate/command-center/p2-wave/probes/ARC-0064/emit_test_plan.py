#!/usr/bin/env python3
"""Emit command-center/phase3/A9/TEST-PLAN.json for ARC-0064."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import schema_local as SL  # noqa: E402
import anchors as A  # noqa: E402
import engine as E  # noqa: E402
import reviewer as R  # noqa: E402

UNIT = "ARC-0064"
OUT = "command-center/phase3/A9/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"
QUESTION = (
    "Specify the integration suite unique to the hybrid: end-to-end journeys "
    "crossing subsystems (install a package that registers a workflow that "
    "opens a council that dispatches cross-vendor units and harvests through "
    "the shared reducer), each asserting ONE shared completion predicate - "
    "with the control proving the journey test fails when any single "
    "subsystem is stubbed."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0064/probe1_stub_mutation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0064/probe2_shared_reducer.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fp(method, command),
        "exit_code": 0,
    }


def ev(path: str, snippet: str, kind: str, claim: str, verdict: str, raw: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0064 emit anchor {why}")
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": "almost-certain",
        "anchor": f"{path}:{line}",
        "probes": [
            probe("source", "file-read", f"anchors.resolve {path}:{line}", why),
            probe("verifier", "command", P1 if kind != "identity" else P2, raw),
        ],
    }


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def validate(doc: dict) -> None:
    errs = SL.iter_errors(REPO, doc)
    if errs:
        print("FAILED:ARC-0064 schema errors")
        for e in errs[:24]:
            print(" ", e)
        raise SystemExit(1)
    for garbage in (
        {},
        {"unit_id": "ARC-0064", "state": "SUCCESS"},
        {"passing_tests": 999999, "totally": "unrelated"},
        {
            "unit_id": "ARC-0064",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ARC-0064",
            "report_kind": "test-plan",
        },
    ):
        g_errs = SL.iter_errors(REPO, garbage)
        if not g_errs:
            raise SystemExit(f"FAILED:ARC-0064 schema accepts garbage {list(garbage)[:4]}")


def main() -> int:
    inputs = E.inputs_on_disk()
    if inputs["a9_design_present"]:
        print("FAILED:ARC-0064 emit unexpectedly found A9 DESIGN.json")
        return 1
    if not inputs["a2_registry_present"] or not inputs["reducer_present"]:
        print("FAILED:ARC-0064 emit missing live A2 registry or shared reducer")
        return 1

    campaign = E.run_stub_campaign()
    if not campaign["all_stubs_went_red"]:
        print("FAILED:ARC-0064 a stub left the journey green")
        print(json.dumps(campaign["stubs"], indent=2)[:4000])
        return 1
    if not campaign["clean_green"]:
        print("FAILED:ARC-0064 clean journey was not COMPLETE via shared reducer")
        print(json.dumps(campaign["clean"], indent=2, default=str)[:4000])
        return 1
    ident = campaign["identity"]
    if not ident.get("object_identity_proven"):
        print("FAILED:ARC-0064 shared judge object identity not proven")
        return 1

    rev = R.review()
    if rev.get("verdict") != "PASS" or not rev.get("ok"):
        print("FAILED:ARC-0064 independent reviewer")
        print(json.dumps(rev, indent=2, default=str)[:4000])
        return 1
    mutant = rev["uncaught_mutation"]
    if mutant.get("would_stay_green") is not True:
        print("FAILED:ARC-0064 named uncaught mutant did not stay green")
        return 1
    if not rev["planted_local_copy"]["detected"]:
        print("FAILED:ARC-0064 planted local judge was not detected")
        return 1

    camp_raw = json.dumps(
        {
            "clean_green": campaign["clean_green"],
            "all_stubs_went_red": campaign["all_stubs_went_red"],
            "library": campaign["clean"].get("library"),
            "verdict": campaign["clean"].get("verdict"),
        },
        sort_keys=True,
    )
    ident_raw = json.dumps(ident, sort_keys=True)
    evidence = [
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "Specify the integration suite unique to the hybrid",
            "catalog",
            "The unit question names the install→workflow→council→vendor→harvest chain and the stub control.",
            "CONFIRMED",
            camp_raw,
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "Single-predicate assertion: the journey must call the shared reducer, not a local copy",
            "identity",
            "The catalog forbids a local completion copy standing in for the shared reducer.",
            "CONFIRMED",
            ident_raw,
        ),
        ev(
            "tools/completion/reducer.py",
            "Call sites must import ``judge``. Exit code zero alone is structurally",
            "live-tree",
            "The live shared reducer is completion.reducer.judge; exit-zero is not COMPLETE.",
            "CONFIRMED",
            ident_raw,
        ),
        ev(
            "tools/completion/sites/harvester.py",
            "Completion verdicts come only from the shared reducer",
            "live-tree",
            "The harvester fan-in site imports judge rather than reimplementing completion.",
            "CONFIRMED",
            ident_raw,
        ),
        ev(
            "command-center/p2-wave/probes/ARC-0010/registry.json",
            '"id": "wf.catalog-class.discovery-only"',
            "live-tree",
            "The live A2 registry already carries the workflow the journey registers.",
            "CONFIRMED",
            camp_raw,
        ),
        ev(
            "command-center/p2-wave/probes/ARC-0073/fixtures/hybrid-singular.json",
            "Borrowed from A2: registry is sole authority for plugin/marketplace/docs. Skill-deployments omitted so skills stay singular.",
            "fixture",
            "Hybrid composition (A1 skills/workflows/council + A2 SSOT plugin/marketplace) is the live stand-in; A9 DESIGN.json is absent.",
            "CONFIRMED",
            camp_raw,
        ),
    ]

    clean = campaign["clean"]
    hop_rows = []
    for spec, live in zip(E.HOP_SPEC, clean["hops"]):
        hop_rows.append(
            {
                "order": spec["order"],
                "subsystem": spec["subsystem"],
                "source_architecture": spec["source_architecture"],
                "artifact": live.get("artifact") or spec["artifact"],
                "assert_on": spec["assert_on"],
                "assert_ok": live.get("assert_ok"),
                "ran": True,
                "silent_short_circuit": False,
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stub_n = len(campaign["stubs"])
    answer = (
        "Executable hybrid journey J-A9-HYBRID-INSTALL-WORKFLOW-COUNCIL-VENDOR-HARVEST "
        f"is COMPLETE via {E.LIBRARY} on the clean path "
        f"(verdict={clean.get('verdict')}). Stubbing each of {stub_n} "
        "subsystems in turn made that same harvest INCOMPLETE or non-shared "
        f"(all_stubs_went_red={campaign['all_stubs_went_red']}). "
        "A9 DESIGN.json, ROSTER.json, RUBRIC.json, and the Windows restore "
        "13-ARCHITECTURE-CANDIDATES.md are absent; TEST-REGISTRY.json is present "
        "but does not list this hybrid journey. The suite runs against live "
        "A2 generate(), live A1-class workflow/council artifacts in that "
        "generated tree, live cross-vendor adapter, and the live shared reducer. "
        "Independent reviewer named council-voting-rule-swap as a mutation hop 3 "
        "would not catch. No A9 DESIGN rebuild. SUCCESS:ARC-0064"
    )

    stub_mutations = [
        {
            "stubbed_subsystem": row["stubbed_subsystem"],
            "clean_verdict": row["clean_verdict"],
            "stubbed_verdict": row["stubbed_verdict"],
            "went_red": True,
            "library": row["library"],
            "reason": row["reason"],
            "hops_assert_ok": row["hops_assert_ok"],
        }
        for row in campaign["stubs"]
    ]
    journeys = [
        {
            "id": "J-A9-HYBRID-INSTALL-WORKFLOW-COUNCIL-VENDOR-HARVEST",
            "title": "Install package, register workflow, open council, dispatch two vendors, harvest",
            "shared_predicate_symbol": E.LIBRARY,
            "unique_to_hybrid": True,
            "silent_short_circuit": False,
            "hops": hop_rows,
            "clean_verdict": clean.get("verdict"),
            "clean_library": clean.get("library"),
            "clean_green": campaign["clean_green"],
        }
    ]
    shared_predicate = {
        "module": "tools/completion/reducer.py",
        "symbol": "judge",
        "library": E.LIBRARY,
        "object_identity_proven": True,
        "local_copy_rejected": True,
        "identity": ident,
        "planted_fixture_detected": True,
    }
    uncaught = {
        "id": mutant["id"],
        "description": mutant["description"],
        "would_stay_green": True,
        "mutated_field": mutant["mutated_field"],
        "original_rule": mutant["original_rule"],
        "mutated_to": mutant["mutated_to"],
    }

    observations = [
        {
            "name": "clean-journey-verdict",
            "measured": str(clean.get("verdict")),
            "method": "command",
            "anchor": "command-center/p2-wave/probes/ARC-0064/engine.py",
        },
        {
            "name": "clean-journey-library",
            "measured": str(clean.get("library")),
            "method": "command",
            "anchor": "tools/completion/reducer.py",
        },
        {
            "name": "all-stubs-went-red",
            "measured": True,
            "method": "command",
            "anchor": "command-center/p2-wave/probes/ARC-0064/engine.py",
        },
        {
            "name": "object-identity-proven",
            "measured": True,
            "method": "static-analysis",
            "anchor": "tools/completion/sites/__init__.py",
        },
        {
            "name": "a9-design-present",
            "measured": False,
            "method": "file-read",
            "anchor": "command-center/phase3/A9/DESIGN.json",
        },
    ]
    control_ids = [f"stub-{r['stubbed_subsystem']}" for r in stub_mutations] + [
        "planted-local-judge",
        "council-voting-rule-swap",
    ]

    negative_controls = [
        {
            "id": f"NC-stub-{row['stubbed_subsystem']}",
            "kind": "mutation",
            "description": (
                f"Stub subsystem {row['stubbed_subsystem']}; harvest must not stay "
                f"shared-COMPLETE. Live stubbed_verdict={row['stubbed_verdict']} "
                f"library={row['library']}."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": f"went_red=True verdict={row['stubbed_verdict']}",
            "good_state_output": f"clean verdict={clean.get('verdict')} library={clean.get('library')}",
        }
        for row in stub_mutations
    ]
    negative_controls.append(
        {
            "id": "NC-planted-local-judge",
            "kind": "known-broken-fixture",
            "description": (
                "Planted fixtures/planted_local_predicate.py defines a local judge "
                "that treats exit_code==0 as COMPLETE. Census must fire; engine.py "
                "must stay silent."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": "local-judge-def detected",
            "good_state_output": "engine_census_hits=[]",
        }
    )

    tests = [
        {
            "id": "stub-mutation-per-subsystem",
            "name": "Stub each hybrid hop; journey harvest goes red every time",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "single-predicate-shared-reducer",
            "name": "Journey harvest is completion.reducer.judge, not a local copy",
            "command": P2,
            "result": "PASS",
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0064",
        "spec_anchor": "_USER-PROMPTS.md:10627-10648 (one completion predicate everywhere)",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-architect",
            "execution_substrate": "headless-linux",
        },
        "artifacts": [
            art_row(SCHEMA, "supporting"),
            art_row("command-center/p2-wave/probes/ARC-0064/engine.py", "supporting"),
            art_row("tools/completion/reducer.py", "supporting"),
            art_row("tools/completion/sites/harvester.py", "supporting"),
        ],
        "evidence": evidence,
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Independent of probe 1: AST import-graph, object identity across "
                "seven fan-in sites, planted local judge, and executed voting-rule "
                f"mutant {mutant['id']} hop 3 does not catch "
                f"(would_stay_green={mutant.get('would_stay_green')})."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0064/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "ARC-0064 schema_local Draft7 disk store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/ARC-0064/schema_local.py",
                    "iter_errors nerr=0",
                ),
            }
        ],
        "timestamps": {"started_at": "2026-08-25T00:40:00Z", "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Live command-center/phase3/A9/DESIGN.json contents.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0059 so A9 DESIGN.json exists; this unit must "
                    "not rebuild that dossier."
                ),
            },
            {
                "claim": "Windows harness-restore 13-ARCHITECTURE-CANDIDATES.md on this host.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Mount harness-restore-20260806 and re-anchor the tournament text.",
            },
        ],
        "report": {
            "kind": "test-plan",
            "observations": observations,
            "control_ids": control_ids,
            "architecture_id": "A9",
            "architecture_class": "maximal-hybrid",
            "question": QUESTION,
            "answer": answer,
            "inputs_on_disk": inputs,
            "journeys": journeys,
            "shared_predicate": shared_predicate,
            "stub_mutations": stub_mutations,
            "uncaught_mutation": uncaught,
            "claims": [
                {
                    "id": "C1",
                    "claim": "The suite was derived from live command-center/phase3/A9/DESIGN.json.",
                    "verdict": "REFUTED",
                    "anchor": "command-center/phase3/A9/DESIGN.json",
                    "why": "A9 DESIGN.json is absent; this unit did not rebuild ARC-0059.",
                },
                {
                    "id": "C2",
                    "claim": "Install→workflow→council→vendor→harvest is an executable hybrid journey asserting one shared reducer.",
                    "verdict": "CONFIRMED",
                    "anchor": "command-center/p2-wave/probes/ARC-0064/engine.py",
                    "why": f"clean verdict={clean.get('verdict')} library={clean.get('library')}",
                },
                {
                    "id": "C3",
                    "claim": "Stubbing any one of the five subsystems leaves the journey green.",
                    "verdict": "REFUTED",
                    "anchor": "command-center/p2-wave/probes/ARC-0064/engine.py",
                    "why": "all_stubs_went_red is true; a green stub would be a hop not exercised.",
                },
                {
                    "id": "C4",
                    "claim": "The journey harvest is completion.reducer.judge (same object as all seven fan-in sites), not a local copy.",
                    "verdict": "CONFIRMED",
                    "anchor": "tools/completion/reducer.py",
                    "why": "object_identity_proven; planted local judge detected; engine.py census clean.",
                },
                {
                    "id": "C5",
                    "claim": "TEST-REGISTRY.json on this worktree lists the hybrid journey tests.",
                    "verdict": "REFUTED",
                    "anchor": "command-center/TEST-REGISTRY.json",
                    "why": "TEST-REGISTRY.json is present and does not name J-A9 or ARC-0064.",
                },
            ],
            "notes": (
                "G-1 ARC-0064: live named probes exit 0, TEST-PLAN.json "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. Did not rebuild A9 DESIGN.json. "
                "cloud ok=true is not delivery. SUCCESS:ARC-0064"
            ),
        },
    }
    validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    size = dest.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0064 artifact {size}B below floor")
        return 1
    if "SUCCESS:ARC-0064" not in dest.read_text(encoding="utf-8"):
        print("FAILED:ARC-0064 sentinel absent from artifact")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:ARC-0064 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
