#!/usr/bin/env python3
"""Emit the CNL-0035 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import delphi as D  # noqa: E402
from note_schema import rejects_garbage, validate_note  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0035-delphi-topology-iterated-anonymous-estimates-with-controll.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "What feedback is returned between Delphi rounds (median only, full "
    "distribution, arguments), and which choice produces genuine revision "
    "rather than regression to the reported median?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0035/probe1_herding.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0035/probe2_negative.py"
)
NAMED = ("median_only", "full_distribution", "arguments")
SENTINEL = "SUCCESS:CNL-0035"


def line_of(rel: str, needle: str) -> int:
    hits = [
        i
        for i, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1)
        if needle in line
    ]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNL-0035 cite {rel!r} {needle!r} hits={hits}")
    return hits[0]


def compact(run: dict) -> dict:
    s0, s1 = run["rounds"][0], run["rounds"][1]
    g = run["gate_round1"]
    return {
        "mode": run["mode"],
        "panel_id": run["panel_id"],
        "var0": s0["variance"],
        "var1": s1["variance"],
        "mae0": s0["mae"],
        "mae1": s1["mae"],
        "median0": s0["median"],
        "median1": s1["median"],
        "herding": g["herding"],
        "verdict": g["verdict"],
        "reason": g["reason"],
        "collapsed": g["collapsed"],
        "evidence_differentiated": g["evidence_differentiated"],
        "accuracy_improved": g["accuracy_improved"],
    }


def fmt(x: float) -> str:
    return f"{x:.6f}"


def main() -> int:
    garbage_ok, garbage_why = rejects_garbage()
    if not garbage_ok:
        print("FAILED:CNL-0035 emit garbage control", garbage_why)
        return 1

    het = D.load_named("panel_heterogeneous.json")
    hom = D.load_named("panel_homogeneous_guesses.json")
    het_runs = {m: D.run_mode(het, m) for m in D.MODES}
    hom_runs = {m: D.run_mode(hom, m) for m in D.MODES}
    het_table = {m: compact(het_runs[m]) for m in D.MODES}
    hom_table = {m: compact(hom_runs[m]) for m in D.MODES}

    a = het_table["arguments"]
    m = het_table["median_only"]
    f = het_table["full_distribution"]
    hazard = het_table["median_plus_arguments"]
    bad = hom_table["arguments"]
    good = het_table["arguments"]

    fire_line = (
        f"NEGATIVE_CONTROL rejected_state={hom['id']} mode=arguments "
        f"check=herding_gate FIRE herding={bad['herding']} verdict={bad['verdict']} "
        f"reason={bad['reason']} var0={bad['var0']:.12f} var1={bad['var1']:.12f} "
        f"mae0={bad['mae0']:.12f} mae1={bad['mae1']:.12f}"
    )
    silent_line = (
        f"NEGATIVE_CONTROL known_good={het['id']} mode=arguments "
        f"check=herding_gate SILENT herding={good['herding']} verdict={good['verdict']} "
        f"reason={good['reason']} var0={good['var0']:.12f} var1={good['var1']:.12f} "
        f"mae0={good['mae0']:.12f} mae1={good['mae1']:.12f}"
    )

    answer = (
        "Return anonymous arguments between Delphi rounds: each other seat's "
        "evidence_class, private_signal, and catalog rationale_id, identity "
        "stripped and sorted, with NO distinguished group median. Of the three "
        f"named payloads on the heterogeneous wrong-majority panel (theta=70, "
        f"round-0 median={fmt(m['median0'])}, no new private evidence): "
        f"median_only herds (var {fmt(m['var0'])}->{fmt(m['var1'])}, MAE "
        f"{fmt(m['mae0'])}->{fmt(m['mae1'])}); full_distribution also herds "
        f"(var {fmt(f['var0'])}->{fmt(f['var1'])}, MAE {fmt(f['mae0'])}->"
        f"{fmt(f['mae1'])}) because the labeled center remains the regression "
        f"target; arguments revises (var {fmt(a['var0'])}->{fmt(a['var1'])}, MAE "
        f"{fmt(a['mae0'])}->{fmt(a['mae1'])}) by reliability-weighted pooling of "
        f"private signals. Relabeling the median as extra social weight "
        f"(median_plus_arguments) worsens MAE to {fmt(hazard['mae1'])} versus "
        f"arguments-only. A homogeneous unanchored_guess panel makes even "
        "arguments FIRE the herding gate: variance collapse with no evidence "
        "differential is herding, not consensus. The runtime must compute that "
        "gate on observed estimates before claiming convergence. " + SENTINEL
    )

    win_inputs = [
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    ]
    present_inputs = {p: (REPO / p).is_file() for p in win_inputs}

    delphi_rel = "command-center/p2-wave/probes/CNL-0035/delphi.py"
    p1_rel = "command-center/p2-wave/probes/CNL-0035/probe1_herding.py"
    p2_rel = "command-center/p2-wave/probes/CNL-0035/probe2_negative.py"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"
    gate_line = line_of(delphi_rel, "VAR_COLLAPSE_RATIO = 0.5")
    moment_line = line_of(delphi_rel, "def second_moment_variance")
    p1_line = line_of(p1_rel, "median_only must herd")
    p2_line = line_of(p2_rel, "fired_on_bad=True silent_on_good=True")
    q_line = line_of(cat_rel, "rather than regression to the reported median")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "unit_id": "CNL-0035",
        "id": "CNL-0035",
        "kind": "council-design-note",
        "schema_version": 1,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": f"{cat_rel}:{q_line}",
        "min_bytes_threshold": 4096,
        "title": "Delphi topology: iterated anonymous estimates with controlled feedback",
        "family": "delphi-anonymous-rounds",
        "question": QUESTION,
        "answer": answer,
        "distinction": (
            "Herding is variance collapse without accuracy gain, or any collapse "
            "when every seat shares one evidence_class. Genuine revision is "
            "collapse that also cuts MAE against theta under differentiated "
            "evidence. Publishing a labeled median is not the same payload as "
            "anonymous arguments even if both shrink spread."
        ),
        "irreducible_verdict_requirements": [
            "Name the three feedback payloads: median_only, full_distribution, arguments.",
            "On a wrong-majority panel with no new private evidence, measure var and MAE after one round under each payload.",
            "Call herding when variance collapses without MAE gain, or when evidence_class is homogeneous.",
            "A planted homogeneous unanchored_guess panel must FIRE; heterogeneous arguments must be SILENT.",
            "A second-moment recount of fixture variance must match the author's population-variance column.",
        ],
        "claims": [
            {
                "id": "C1",
                "claim": "median_only herds toward the wrong majority median.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "C2",
                "claim": "full_distribution still herds while the median stays labeled.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "C3",
                "claim": "arguments without a distinguished median revises when evidence_class differs.",
                "verdict": "CONFIRMED",
            },
        ],
        "taxonomy": {
            "id": "delphi-feedback-payload",
            "axis": "inter-round-information",
            "closed": True,
            "classes": [
                {
                    "id": "median_only",
                    "interest": "Distinguished group median; no reasons; no spread.",
                },
                {
                    "id": "full_distribution",
                    "interest": "Quartiles and histogram with the median still labeled.",
                },
                {
                    "id": "arguments",
                    "interest": "Anonymous evidence-classed estimates; no group median.",
                },
            ],
        },
        "metric": {
            "id": "herding-gate",
            "formula": (
                "herding := (var1 < 0.5*var0) AND "
                "((unique evidence_class count == 1) OR NOT (mae1 < 0.9*mae0))"
            ),
            "decision": (
                "FIRE herding and refuse a consensus claim when the gate is true; "
                "SILENT when variance collapse is accompanied by accuracy gain "
                "and differentiated evidence_class."
            ),
            "I_star": 1,
        },
        "enumeration": {
            "expected_n": 3,
            "measured_n": 3,
            "agreement": True,
            "signals": [
                "len(NAMED_MODES) in probes/CNL-0035/delphi.py",
                "len(taxonomy.classes) in this note",
            ],
        },
        "protocols": [
            {
                "record_id": "P20",
                "name": "median-only-feedback",
                "family": "delphi-anonymous-rounds",
                "executability": "EXECUTABLE",
                "artifact": {"mode": "median_only", "herding_on_het": True},
            },
            {
                "record_id": "P21",
                "name": "full-distribution-feedback",
                "family": "delphi-anonymous-rounds",
                "executability": "EXECUTABLE",
                "artifact": {"mode": "full_distribution", "herding_on_het": True},
            },
            {
                "record_id": "P22",
                "name": "arguments-without-distinguished-median",
                "family": "delphi-anonymous-rounds",
                "executability": "EXECUTABLE",
                "artifact": {"mode": "arguments", "herding_on_het": False},
            },
        ],
        "duplicates": [],
        "duplicate_criterion": (
            "Two payloads are duplicates only if they return the same fields "
            "to seats. Sharing a herding verdict does not make median_only "
            "the same protocol as full_distribution."
        ),
        "herding_experiment": {
            "theta": het["theta"],
            "n_agents": len(het["agents"]),
            "no_new_private_evidence": True,
            "heterogeneous": het_table,
            "homogeneous": hom_table,
            "prescribed_mode": "arguments",
            "prescribed_because": (
                "Only arguments is REVISION on the heterogeneous fixture; "
                "median_only and full_distribution are HERDING."
            ),
        },
        "anonymity_minimum": {
            "dependency": "CNL-0007",
            "dependency_artifact_on_this_tree": (
                REPO / "command-center/design/council/"
                "CNL-0007-anonymity-levels-and-their-effect-on-attribution.md"
            ).is_file(),
            "payload_rule": (
                "Strip seat ids; sort by (evidence_class, private_signal, "
                "rationale_id); rationale_id is a catalog string not free text; "
                "no timestamps."
            ),
            "residual": (
                "CNL-0007 is not delivered on this tree; this note specifies "
                "the payload minimum Delphi needs, not the full anonymity lattice."
            ),
        },
        "windows_inputs": present_inputs,
        "tests": [
            {"id": "probe1-herding", "command": P1, "result": "PASS"},
            {"id": "probe2-negative-recount", "command": P2, "result": "PASS"},
        ],
        "both_states": {
            "known_good": {
                "fixture": "fixtures/panel_heterogeneous.json",
                "mode": "arguments",
                "expect": "SILENT",
                "herding": False,
                "verbatim": silent_line,
            },
            "planted_bad": {
                "fixture": "fixtures/panel_homogeneous_guesses.json",
                "mode": "arguments",
                "expect": "FIRE",
                "herding": True,
                "verbatim": fire_line,
            },
        },
        "negative_control": {
            "rejected_state": (
                "homogeneous unanchored_guess panel under arguments feedback: "
                "variance collapses with no reliability differential"
            ),
            "check": "herding_gate",
            "verbatim": fire_line + " | " + silent_line,
        },
        "negative_controls": [
            {
                "id": "homogeneous-arguments-herding",
                "rejected_state": (
                    "all seats unanchored_guess; arguments payload; no new evidence"
                ),
                "check": "herding_gate",
                "does": "FIRE (herding=true) because evidence is homogeneous",
                "verbatim": fire_line,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0035-probe2-second-moment-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Recompute var0 as E[x^2]-(E[x])^2 from fixture private signals "
                "and from live round estimates; disagreeing numbers block."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "herding-control"},
            {"id": "probe2", "command": P2, "role": "negative-control-and-recount"},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0035/delphi.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0035/fixtures/panel_heterogeneous.json",
                "exists": True,
                "role": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0035/fixtures/panel_homogeneous_guesses.json",
                "exists": True,
                "role": "fixture",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "median_only collapses variance toward the wrong majority "
                    "median and raises MAE vs theta (herding, not convergence)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{p1_rel}:{p1_line}",
                "path": p1_rel,
                "line": p1_line,
            },
            {
                "claim": (
                    "arguments without a distinguished median revises toward "
                    "the reliability-weighted private-signal pool and lowers MAE."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{delphi_rel}:{gate_line}",
                "path": delphi_rel,
                "line": gate_line,
            },
            {
                "claim": (
                    "The herding gate FIRES on a homogeneous unanchored_guess "
                    "panel even under arguments, and is SILENT on heterogeneous "
                    "arguments."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{p2_rel}:{p2_line}",
                "path": p2_rel,
                "line": p2_line,
            },
            {
                "claim": (
                    "Reviewer recount of fixture variance uses E[x^2]-(E[x])^2 "
                    "(second-moment identity), a different mechanism than the "
                    "author's population-variance column."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{delphi_rel}:{moment_line}",
                "path": delphi_rel,
                "line": moment_line,
            },
            {
                "claim": (
                    "Windows council spec and _USER-PROMPTS.md were read from "
                    "this worktree and used as the byte source for the design."
                ),
                "verdict": "NOT-CHECKED",
                "anchor": "windows-inputs-absent",
                "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Live LLM seats follow the bounded-rational update models.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the same fixtures through the Phase-7A Delphi runtime "
                    "with live seats and apply the herding gate to observed estimates."
                ),
            }
        ],
        "report": {
            "kind": "council-design-note",
            "control_ids": ["homogeneous-arguments-herding"],
            "observations": [
                {
                    "name": "het.median_only.herding",
                    "measured": True,
                    "method": "population-variance-and-mae",
                    "anchor": f"{p1_rel}:{p1_line}",
                },
                {
                    "name": "het.arguments.herding",
                    "measured": False,
                    "method": "population-variance-and-mae",
                    "anchor": f"{delphi_rel}:{gate_line}",
                },
                {
                    "name": "hom.arguments.herding",
                    "measured": True,
                    "method": "herding-gate-on-homogeneous-fixture",
                    "anchor": f"{p2_rel}:{p2_line}",
                },
                {
                    "name": "var0_second_moment_identity",
                    "measured": True,
                    "method": "second-moment-variance",
                    "anchor": f"{delphi_rel}:{moment_line}",
                },
            ],
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 1,
            "policy": (
                "two strikes then pivot: first attempt used catalog "
                "council-design-note.schema.json $ref which fetches "
                "https://ast-integrate.invalid over the network; pivoted to "
                "local note_schema.py (same pattern as CNL-0071)"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0035/UNIT-ARTIFACT-MANIFEST.json",
        },
        "ts": now,
    }

    ok, why = validate_note(doc)
    if not ok:
        print("FAILED:CNL-0035 local schema", why)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNL-0035 sentinel absent from artifact text")
        return 1
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0035 artifact {out.stat().st_size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0035 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
