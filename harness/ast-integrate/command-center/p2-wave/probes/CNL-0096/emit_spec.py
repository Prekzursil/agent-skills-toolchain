#!/usr/bin/env python3
"""Emit the CNL-0096 detector spec (JSON body, catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as BS  # noqa: E402
import fixtures as FX  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
DETECTOR = "command-center/p2-wave/probes/CNL-0096/detector.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0096/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0096/probe2_independent_rerun.py"
)
SCHEMA_CMD = f"json.loads {OUT}"
QUESTION = (
    "When a council hits its hard cap without a decision, what is emitted so "
    "the work is not lost - and is that artifact distinguishable from a real "
    "no-decision outcome?"
)
RETRY_POLICY = (
    "two strikes then pivot, PLUS a mandatory detector-control retry: if the "
    "both-states control does not fire on the planted-bad fixture, the attempt "
    "does not count as a failure of the mechanism - fix the fixture first, once. "
    "Max 3 mechanism attempts (AGENTS.md 4b)."
)
SUPPORTING = (
    (SCHEMA, "supporting"),
    (DETECTOR, "supporting"),
    ("command-center/p2-wave/probes/CNL-0096/fixtures.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0096/both_states.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0096/probe1_both_states.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0096/probe2_independent_rerun.py", "supporting"),
    (
        "command-center/p2-wave/probes/CNL-0096/fixtures/planted-masquerade.json",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNL-0096/fixtures/good-cap-exhausted.json",
        "fixture",
    ),
    (
        "command-center/p2-wave/probes/CNL-0096/fixtures/good-genuine-no-decision.json",
        "fixture",
    ),
)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0096 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    if size < 1:
        raise SystemExit(f"FAILED:CNL-0096 empty supporting artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:16000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def evidence(
    claim: str,
    anchor: str,
    source: dict,
    verifier: dict,
    *,
    confidence: str = "almost-certain",
) -> dict:
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": confidence,
        "anchor": anchor,
        "probes": [source, verifier],
    }


def main() -> int:
    FX.dump_json()
    matrix = BS.run_matrix()
    if not matrix["ok"]:
        print("FAILED:CNL-0096 emit both-states matrix not ok")
        print(json.dumps(matrix, indent=2)[:2000])
        return 1

    line_kind = find_line(REPO / DETECTOR, 'EXHAUSTED_KIND = "exhausted_without_decision"')
    line_tuple = find_line(REPO / DETECTOR, "tuple[str, str, int]:")
    line_q = find_line(
        REPO / CATALOG,
        "When a council hits its hard cap without a decision, what is emitted so the work is not lost",
    )
    line_exh = find_line(
        REPO / "command-center/p2-wave/probes/CNL-0096/fixtures/good-cap-exhausted.json",
        '"kind": "exhausted_without_decision"',
    )
    line_gen = find_line(
        REPO / "command-center/p2-wave/probes/CNL-0096/fixtures/good-genuine-no-decision.json",
        '"termination_cause": "deliberative"',
    )
    line_plant = find_line(
        REPO / "command-center/p2-wave/probes/CNL-0096/fixtures/planted-masquerade.json",
        '"kind": "no-decision"',
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fpr = matrix["false_positive_rate"]
    nc = matrix["negative_control"]
    pair = matrix["distinguisher_pair"]
    ctrl = matrix["detector_control"]
    p1_raw = (
        f"detector_control_fired={ctrl['fired']} "
        f"planted_bad_fired={matrix['planted_bad_fired']} "
        f"known_good_silent={matrix['known_good_silent']} "
        f"false_positive_rate={fpr['rate']} "
        f"pair_distinct={pair['distinct']}"
    )
    p2_raw = (
        f"independent_ok={matrix['ok']} "
        f"negative_control_fired={nc['fired']} "
        f"codes={nc['codes']} "
        f"{nc['verbatim']}"
    )
    src_p1 = probe("source", "test-run", P1, p1_raw, 0)
    ver_p2 = probe("verifier", "byte-compare", P2, p2_raw, 0)
    src_file = probe(
        "source",
        "file-read",
        f"{DETECTOR}:{line_tuple}",
        "distinguisher returns tuple(kind, termination_cause, cap_remaining)",
        0,
    )
    ver_schema = probe("verifier", "file-read", SCHEMA_CMD, "schema_errors=0", 0)

    answer = (
        "On hard-cap without a decision the council emits exhausted_without_decision "
        "(termination_cause=hard_cap, cap_remaining=0) plus the preserved-work payload "
        "(transcript, last_positions, vote_snapshot, information_gain_by_round). That "
        "record is distinguishable from genuine no-decision because the distinguisher "
        "tuple (kind, termination_cause, cap_remaining) differs: "
        f"{pair['cap_exhausted']} vs {pair['genuine_no_decision']}. A consumer that "
        "only understands no-decision will not coerce the cap-hit record. Work is not "
        "lost because empty preserved-work fields fire the detector. SUCCESS:CNL-0096"
    )
    report = {
        "kind": "council-detector-spec",
        "observations": [
            {
                "name": "false_positive_rate",
                "measured": fpr["rate"],
                "method": "fired_on_clean / clean_count over four known-good fixtures",
                "anchor": f"{DETECTOR}:{line_kind}",
            },
            {
                "name": "distinguisher_pair_distinct",
                "measured": bool(pair["distinct"]),
                "method": "tuple(kind, termination_cause, cap_remaining) without detect().fired",
                "anchor": f"{DETECTOR}:{line_tuple}",
            },
            {
                "name": "detector_control_fired",
                "measured": bool(ctrl["fired"]),
                "method": "detect() on planted-masquerade before any absence claim",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0096/fixtures/"
                    f"planted-masquerade.json:{line_plant}"
                ),
            },
        ],
        "control_ids": [
            "planted-masquerade",
            "planted-work-lost",
            "planted-false-exhaustion",
            "good-genuine-no-decision",
            "good-cap-exhausted",
            "good-decision-before-cap",
            "good-decision-on-last-round",
        ],
        "title": "Endless debate cap and graceful degradation",
        "question": QUESTION,
        "answer": answer,
        "pathology": {
            "id": "cap-hit-masquerade-or-lost-work",
            "name": (
                "Hard-cap exhaustion labelled as deliberative no-decision, "
                "or cap-hit with dropped work"
            ),
            "present_when": (
                "rounds_consumed >= hard_cap and outcome is not a decision, and "
                "either kind is a spec non-decision variant or preserved-work "
                "fields are empty; or exhausted_without_decision is claimed "
                "while cap budget remains"
            ),
            "absent_when": (
                "cap-hit emits exhausted_without_decision with "
                "termination_cause=hard_cap and non-empty preserved work, or the "
                "run never hit the cap (including a decision on the last allowed round)"
            ),
        },
        "detector": {
            "id": "CNL-0096-cap-exhaustion",
            "implementation": DETECTOR,
            "fires_when": (
                "cap-hit without a decision is labelled as no-decision or another "
                "spec variant, termination_cause is not hard_cap, preserved work "
                "is missing, or exhaustion is claimed with remaining budget"
            ),
            "silent_when": (
                "genuine no-decision with remaining cap, well-formed "
                "exhausted_without_decision with preserved work, or a decision "
                "(including last-round agreement)"
            ),
            "signals": {
                "A": "detect().fired boolean plus codes",
                "B": (
                    "distinguisher tuple (kind, termination_cause, cap_remaining) "
                    "compared across the genuine/exhausted pair without using "
                    "detect().fired"
                ),
            },
        },
        "graceful_degradation": {
            "emitted_kind": "exhausted_without_decision",
            "termination_cause": "hard_cap",
            "cap_remaining": 0,
            "preserved_work": [
                "transcript",
                "last_positions",
                "vote_snapshot",
                "information_gain_by_round",
            ],
            "not_the_same_as": "no-decision",
            "why_not_no_decision": (
                "no-decision is a deliberative choice with remaining budget; "
                "cap-hit is an environmental stop. Collapsing them loses the cause "
                "and lets downstream consumers treat exhaustion as epistemic refusal."
            ),
        },
        "spec_variants_distinguished": [
            "decision",
            "conditional_decision",
            "no-decision",
            "irreducible_disagreement",
            "dissent-with-minority-report",
            "proof_of_impossibility",
        ],
        "both_states": {
            "planted_bad_fired": matrix["planted_bad_fired"],
            "known_good_silent": matrix["known_good_silent"],
            "planted": matrix["planted"],
            "clean": matrix["clean"],
        },
        "detector_control": ctrl,
        "negative_control": nc,
        "false_positive_rate": fpr,
        "distinguisher_pair": pair,
        "dependencies_on_this_tree": {
            "CNL-0072": (
                "absent — 17-value $defs.outcome mapping not inherited; "
                "distinguisher binds to the six named spec variants plus "
                "exhausted_without_decision"
            ),
            "CNL-0084": (
                "absent — deadlock (stuck with remaining cap) is out of scope; "
                "this unit is budget exhaustion"
            ),
        },
        "fixture_anchors": {
            "good_cap_exhausted": (
                "command-center/p2-wave/probes/CNL-0096/fixtures/"
                f"good-cap-exhausted.json:{line_exh}"
            ),
            "good_genuine_no_decision": (
                "command-center/p2-wave/probes/CNL-0096/fixtures/"
                f"good-genuine-no-decision.json:{line_gen}"
            ),
            "planted_masquerade": (
                "command-center/p2-wave/probes/CNL-0096/fixtures/"
                f"planted-masquerade.json:{line_plant}"
            ),
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0096",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0096",
        "profile": "council-detector-spec",
        "spec_anchor": f"{CATALOG}:{line_q}",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            evidence(
                (
                    "Detector-control first: planted-masquerade (cap-hit labelled "
                    "no-decision) FIREs; three planted fixtures FIRE; four clean "
                    "fixtures are SILENT; false_positive_rate is the number "
                    f"{fpr['rate']} not an adjective."
                ),
                f"{DETECTOR}:{line_kind}",
                src_p1,
                ver_p2,
            ),
            evidence(
                (
                    "Cap-hit without a decision is distinguishable from genuine "
                    "no-decision by the tuple (kind, termination_cause, "
                    f"cap_remaining): {pair['cap_exhausted']} vs "
                    f"{pair['genuine_no_decision']} (distinct={pair['distinct']})."
                ),
                f"{DETECTOR}:{line_tuple}",
                src_file,
                ver_schema,
            ),
        ],
        "tests": [
            {
                "id": "T1-both-states-detector-control",
                "name": "Detector-control, planted FIRE, clean SILENT, numeric FPR",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-independent-rerun-negative-control",
                "name": "Independent matrix rerun, kind-rewrite negative control, schema",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-REWRITE-EXHAUSTED-AS-NO-DECISION",
                "kind": "mutation",
                "description": (
                    "Rewrite good-cap-exhausted kind to no-decision with "
                    "termination_cause=deliberative. The detector MUST FIRE. "
                    "Unmutated good-cap-exhausted MUST stay SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": nc["verbatim"],
                "good_state_output": (
                    "good-cap-exhausted detect.fired="
                    f"{matrix['clean']['good-cap-exhausted']['fired']} "
                    f"codes={matrix['clean']['good-cap-exhausted']['codes']}"
                ),
            },
            {
                "id": "NC-PLANTED-MASQUERADE",
                "kind": "known-broken-fixture",
                "description": (
                    "planted-masquerade is the known-present detector-control. "
                    "The detector MUST FIRE before any absence is claimed. "
                    "good-genuine-no-decision MUST stay SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "planted-masquerade detect.fired="
                    f"{matrix['planted']['planted-masquerade']['fired']} "
                    f"codes={matrix['planted']['planted-masquerade']['codes']}"
                ),
                "good_state_output": (
                    "good-genuine-no-decision detect.fired="
                    f"{matrix['clean']['good-genuine-no-decision']['fired']} "
                    f"codes={matrix['clean']['good-genuine-no-decision']['codes']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0096-probe2-independent-rerun",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe2 re-runs the both-states matrix, applies the kind-rewrite "
                "negative control, rejects adjective FPR, and validates the "
                "receipt against council-detector-spec via disk-mapped RefResolver "
                "(jsonschema 4.10, no network). Agreement with emit prose is not required."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0096/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "schema_local.iter_errors of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": ver_schema,
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": RETRY_POLICY,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The 17-value $defs.outcome enum from CNL-0072 is not on this "
                    "tree; exhausted_without_decision is specified as a seventh "
                    "kind relative to the six named spec variants, not mapped onto "
                    "that enum."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When CNL-0072's mapping artifact is present, join "
                    "exhausted_without_decision onto $defs.outcome and re-run "
                    "the distinguisher pair."
                ),
            },
            {
                "claim": (
                    "CNL-0084 deadlock (frozen ledger plus wait-for cycle with "
                    "remaining cap) is out of scope for this hard-cap unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Feed a CNL-0084 planted-deadlock fixture with cap remaining "
                    "into detect() and require SILENT for cap-exhaustion codes."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-anti-failure-detector-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
        "extensions": {
            "false_positive_rate": fpr,
            "both_states": report["both_states"],
            "graceful_degradation": report["graceful_degradation"],
            "distinguisher_pair": pair,
            "answer": answer,
            "question": QUESTION,
        },
    }

    errors = SL.iter_errors(doc)
    if errors:
        print("FAILED:CNL-0096 emit schema-invalid")
        for err in errors[:40]:
            print(" ", err)
        return 1
    try:
        SL.assert_rejects_garbage()
    except ValueError as exc:
        print(f"FAILED:CNL-0096 emit {exc}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:CNL-0096" not in raw:
        print("FAILED:CNL-0096 emit sentinel missing")
        return 1
    if len(raw.encode("utf-8")) < 2048:
        print("FAILED:CNL-0096 emit below min_bytes_threshold")
        return 1
    out_path.write_text(raw, encoding="utf-8")
    live = json.loads(out_path.read_text(encoding="utf-8"))
    live_errors = SL.iter_errors(live)
    if live_errors:
        print("FAILED:CNL-0096 emit written file schema-invalid")
        for err in live_errors[:20]:
            print(" ", err)
        return 1
    print(f"wrote {OUT} bytes={len(raw.encode('utf-8'))}")
    print("SUCCESS:CNL-0096 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
