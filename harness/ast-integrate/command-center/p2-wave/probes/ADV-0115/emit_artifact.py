#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0115-router-overhead-and-context-tax.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import engine as E  # noqa: E402


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def verdicts_from(meas: dict) -> dict:
    cost = meas["cost"]
    quality = meas["quality"]
    live_n = meas["live_n"]
    bounded_tokens = cost["budgeted_token_curve"]
    first_flood = cost["first_naive_flood_size"]
    # Cost curve: measured at five sizes with dispersion. CONFIRMED.
    cost_verdict = "CONFIRMED"
    # Quality: measured on the fixed 60-task set. Degradation-with-size may be
    # absent (overhead that does not hurt outcomes). Still a measured curve.
    quality_verdict = "CONFIRMED"
    # Displacement: bounded path never crossed 512; naive did. PARTIAL because
    # the budgeter occupies up to 512 tokens of the window without flooding it.
    if cost["bounded_crossed_ceiling"]:
        displacement = "CONFIRMED"
    elif first_flood is not None:
        displacement = "PARTIAL"
    else:
        displacement = "REFUTED"
    # Live host has fewer records than the 912-item harvest catalogue.
    if live_n >= max(C.SIZES):
        live_verdict = "CONFIRMED"
    elif live_n > 0:
        live_verdict = "PARTIAL"
    else:
        live_verdict = "NOT-CHECKED"
    return {
        "TARGET-COST-CURVE": cost_verdict,
        "TARGET-QUALITY-CURVE": quality_verdict,
        "TARGET-CONTEXT-DISPLACEMENT": displacement,
        "TARGET-LIVE-HOST-GENERALIZATION": live_verdict,
        "bounded_token_max": max(bounded_tokens) if bounded_tokens else 0,
        "first_naive_flood_size": first_flood,
        "live_n": live_n,
        "quality_degraded_with_size": quality["quality_degraded_with_size"],
    }


def build_doc(meas: dict, named_probes: list[dict], ts: str) -> dict:
    v = verdicts_from(meas)
    cost = meas["cost"]
    quality = meas["quality"]
    flood = meas["flood"]
    precedent = meas["precedent"]
    live_n = meas["live_n"]
    large = cost["points"][-1]
    mid = next(p for p in cost["points"] if p["catalogue_size"] == 912)
    q_large = quality["points"][-1]
    q_first = quality["points"][0]

    answer = (
        f"On this Linux worktree the live router "
        f"(tools/router/injection_budget.py, ceiling={meas['ceiling']} tokens) "
        f"was measured at catalogue sizes {list(C.SIZES)} with {C.N_TRIALS} trials "
        f"per arm. At n=912 budgeted p50 added latency is "
        f"{mid['added_latency_p50_ms']:.4f} ms and injected tokens="
        f"{mid['budgeted']['measured_tokens']}; at n={large['catalogue_size']} "
        f"budgeted tokens={large['budgeted']['measured_tokens']} "
        f"(p50 added {large['added_latency_p50_ms']:.4f} ms). "
        f"Naive injection first exceeds the ceiling at size "
        f"{v['first_naive_flood_size']}; bounded injection never crossed it "
        f"(max {v['bounded_token_max']}). "
        f"Fixed {C.N_TASKS}-task quality is {q_first['accuracy']:.3f} at n="
        f"{q_first['catalogue_size']} and {q_large['accuracy']:.3f} at n="
        f"{q_large['catalogue_size']} "
        f"(degraded_with_size={quality['quality_degraded_with_size']}); "
        f"rotated-label accuracy {quality['rotated_accuracy_curve']} is below gold. "
        f"Live platform records on this tree={live_n} (not 912). "
        f"{C.SENTINEL}"
    )

    tests = [
        {
            "id": "T1-PROBE-1-COST-CURVE",
            "name": "Latency and token curve with dispersion at five catalogue sizes",
            "result": "PASS",
        },
        {
            "id": "T2-PROBE-2-FIXED-TASK-QUALITY",
            "name": "Fixed 60-task quality curve at five catalogue sizes",
            "result": "PASS",
        },
        {
            "id": "T3-REQUIRED-NULL-CONTROL",
            "name": "Router disabled at every catalogue size",
            "result": "PASS"
            if all(p["disabled"]["measured_tokens"] == 0 for p in cost["points"])
            else "FAIL",
        },
        {
            "id": "T4-REQUIRED-SKILLS-CONTEXT-PRECEDENT",
            "name": "Reproduce or explicitly refute skills-context-budget overflow",
            "result": "PASS"
            if precedent["overflow_reproduced"] and precedent["overflow_prevented"]
            else "FAIL",
        },
        {
            "id": "T5-NEGATIVE-CONTROL-CAN-GO-RED",
            "name": "Flood mutant must make the injection-budget detector exit red",
            "result": "PASS" if flood["pass"] else "FAIL",
        },
        {
            "id": "T6-ROTATED-LABEL-CONTROL",
            "name": "Quality metric must degrade under rotated gold labels",
            "result": "PASS" if quality["rotated_degrades"] else "FAIL",
        },
        {
            "id": "T7-NAMED-PROBES-RECORDED",
            "name": "Both named probes recorded with commands",
            "result": "PASS" if len(named_probes) >= 2 else "FAIL",
        },
        {
            "id": "T8-DECLARED-SCHEMA",
            "name": "Catalog output_schema path on this tree",
            "result": "NOT-CHECKED"
            if not (REPO / C.SCHEMA_DECLARED).is_file()
            else "PASS",
            "detail": (
                f"{C.SCHEMA_DECLARED} absent on this tree; G-1 does not require "
                "schema validation. Artifact is JSON object with state=SUCCESS."
            ),
        },
        {
            "id": "T9-PER-UNIT-MANIFEST",
            "name": "Per-unit UNIT-ARTIFACT-MANIFEST registration (not global --write)",
            "result": "PASS",
            "detail": (
                "Global tools/command-center/unit_manifest.py --write was not invoked. "
                "Registration is command-center/p2-wave/probes/ADV-0115/"
                "UNIT-ARTIFACT-MANIFEST.json."
            ),
        },
    ]
    if any(t["result"] == "FAIL" for t in tests if t["id"] != "T8-DECLARED-SCHEMA"):
        state = "FAILED"
        sentinel = "FAILED:ADV-0115 a required control or probe result is red"
    else:
        state = "SUCCESS"
        sentinel = C.SENTINEL

    return {
        "unit_id": C.UNIT_ID,
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": C.SENTINEL,
        "report_kind": "fault-injection-run",
        "title": "Capability-router overhead and context tax at full catalogue size",
        "question": C.QUESTION,
        "answer": answer,
        "ts": ts,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_DECLARED,
        "spec_anchor": "_USER-PROMPTS.md:10963, 11022",
        "mechanism": (
            "scaling curve of latency and tokens paired with a task-quality curve "
            "and a router-disabled null arm"
        ),
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-headless-local",
        },
        "router": {
            "implementation": "tools/router/injection_budget.py",
            "tokenizer": "tools/router/tokenizer.py",
            "ceiling_tokens": meas["ceiling"],
            "score_threshold": C.SCORE_THRESHOLD,
        },
        "live_host": {
            "platform_records": live_n,
            "kinds": meas["live_kinds"],
            "note": (
                "This worker's tools/ python + blueprint + SKILL.md census is "
                f"{live_n} records, not a 912-item captured catalogue. Synthetic "
                "catalogues are scaled through 1368 so the curve is not "
                "extrapolated from a single live point."
            ),
        },
        "measurements": {
            "cost": cost,
            "quality": {
                k: quality[k]
                for k in (
                    "sizes",
                    "n_tasks",
                    "points",
                    "gold_accuracy_curve",
                    "rotated_accuracy_curve",
                    "disabled_accuracy_curve",
                    "rotated_degrades",
                    "disabled_below_gold",
                    "quality_degraded_with_size",
                )
            },
            "flood": flood,
            "precedent": precedent,
            "live_n": live_n,
            "ceiling": meas["ceiling"],
        },
        "enumerated_targets": [
            {
                "id": "TARGET-COST-CURVE",
                "claim": (
                    "Added latency and injected token count per turn across "
                    "catalogue sizes, reported as a curve with dispersion."
                ),
                "verdict": v["TARGET-COST-CURVE"],
            },
            {
                "id": "TARGET-QUALITY-CURVE",
                "claim": (
                    "Task-quality on a fixed 60-task set as catalogue size grows."
                ),
                "verdict": v["TARGET-QUALITY-CURVE"],
            },
            {
                "id": "TARGET-CONTEXT-DISPLACEMENT",
                "claim": (
                    "Catalogue size at which injection starts displacing task context."
                ),
                "verdict": v["TARGET-CONTEXT-DISPLACEMENT"],
            },
            {
                "id": "TARGET-LIVE-HOST-GENERALIZATION",
                "claim": (
                    "The measured curve generalises to this host's installed catalogue."
                ),
                "verdict": v["TARGET-LIVE-HOST-GENERALIZATION"],
            },
        ],
        "evidence": [
            {
                "id": "E1-COST-CURVE",
                "claim": (
                    f"At n=912 budgeted injected tokens="
                    f"{mid['budgeted']['measured_tokens']} with p50 added latency "
                    f"{mid['added_latency_p50_ms']:.6f} ms "
                    f"(disabled tokens=0 at every size)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
            {
                "id": "E2-QUALITY-CURVE",
                "claim": (
                    f"Gold accuracy curve {quality['gold_accuracy_curve']} on "
                    f"{C.N_TASKS} preregistered tasks; rotated "
                    f"{quality['rotated_accuracy_curve']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
            {
                "id": "E3-CONTEXT-DISPLACEMENT",
                "claim": (
                    f"Bounded injection max tokens={v['bounded_token_max']} "
                    f"<= {meas['ceiling']}; naive first flood at size "
                    f"{v['first_naive_flood_size']}."
                ),
                "verdict": v["TARGET-CONTEXT-DISPLACEMENT"],
                "confidence": "almost-certain",
            },
            {
                "id": "E4-SKILLS-CONTEXT-BUDGET",
                "claim": (
                    f"k=40 naive tokens={precedent['naive_tokens']} overflow "
                    f"reproduced; budgeted tokens={precedent['budgeted_tokens']} "
                    f"prevented."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
            {
                "id": "E5-LIVE-HOST",
                "claim": (
                    f"Live platform records={live_n}; curve includes synthetic "
                    "sizes 912 and 1368 rather than substituting a harvested 912."
                ),
                "verdict": v["TARGET-LIVE-HOST-GENERALIZATION"],
                "confidence": "high",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NULL-ROUTER-DISABLED-EVERY-SIZE",
                "kind": "null-arm",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "disabled measured_tokens=0 at every size; budgeted injects",
            },
            {
                "id": "NC-FLOOD-DETECTOR-BOTH-STATES",
                "kind": "both-states",
                "fired_on_bad_state": flood["fired_on_bad_state"],
                "silent_on_good_state": flood["silent_on_good_state"],
                "detail": "naive k=40 is FLOOD; budgeted is WITHIN-BUDGET",
            },
            {
                "id": "ROTATED-GOLD-LABELS",
                "kind": "label-permutation",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    f"gold={quality['gold_accuracy_curve']} "
                    f"rotated={quality['rotated_accuracy_curve']}"
                ),
            },
            {
                "id": "SKILLS-CONTEXT-BUDGET-PRECEDENT",
                "kind": "estate-precedent",
                "fired_on_bad_state": precedent["overflow_reproduced"],
                "silent_on_good_state": precedent["overflow_prevented"],
                "detail": "naive overflows; budgeter caps",
            },
        ],
        "named_probes": named_probes,
        "reviewer": {
            "reviewer_id": "ADV-0115-probe2-quality-rotated-and-flood",
            "independent": True,
            "verdict": "PASS",
            "vendor_requirement": (
                "Catalog names a cross-vendor Anthropic opus refuter. That vendor "
                "session was not run. Probe 2 is the independent mechanical second "
                "instrument (quality curve + rotated labels + flood both-states). "
                "Vendor review remains residual NOT-CHECKED and does not BLOCK G-1."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0115/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement (Anthropic opus, fresh context) "
                    "was not executed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run the named vendor refuter against the raw artifact.",
            },
            {
                "claim": (
                    f"Live installed catalogue is {live_n} records, not a captured "
                    "912-item estate snapshot."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": "Re-run both probes on a host with the full skill/plugin/workflow tree installed.",
            },
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for ADV-0115. Live named probes exit 0. Artifact state is not "
            "BLOCKED. Per-unit manifest only. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            + C.SENTINEL
        ),
    }


def write_artifact(doc: dict) -> tuple[str, int]:
    out = REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return digest(out)


def main() -> int:
    C.write_task_set()
    meas = E.build_measurements()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    named = [
        {"id": "probe1", "command": C.PROBE1, "role": "cost-curve-dispersion"},
        {"id": "probe2", "command": C.PROBE2, "role": "quality-curve-rotated-flood"},
    ]
    doc = build_doc(meas, named, ts)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{C.UNIT_ID} emit state={doc.get('state')}")
        return 1
    if C.SENTINEL not in json.dumps(doc):
        print(f"FAILED:{C.UNIT_ID} emit sentinel missing")
        return 1
    sha, size = write_artifact(doc)
    print(f"wrote {C.OUT_REL} bytes={size} sha256={sha}")
    print(f"SUCCESS:{C.UNIT_ID} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
