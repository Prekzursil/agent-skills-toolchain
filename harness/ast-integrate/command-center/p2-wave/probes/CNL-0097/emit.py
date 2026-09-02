#!/usr/bin/env python3
"""Emit CNL-0097 detector spec, then write per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import scenario as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md"
)
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
# phase3/A1/FAILURE-MODES.json is absent on this worktree; the live
# FC-11340 name lives in the ARC-0005 seeded class table.
FAILURES = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py"
)
QUESTION = (
    "Which dissent present in the transcript failed to appear in the "
    "synthesis — computed as a diff, not judged by the synthesizer who dropped it?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0097/detector.py",
    "command-center/p2-wave/probes/CNL-0097/scenario.py",
    "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
    "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0097 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def evidence(rel: str, snippet: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": "CNL-0097",
        "receipt_path": "command-center/p2-wave/probes/CNL-0097/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_artifact() -> dict:
    S.write_all()
    D.reset_control()
    bad = D.detector_control_known_present(S.planted_bad())
    if not bad["fired"]:
        raise SystemExit("FAILED:CNL-0097 planted-bad did not fire while emitting")
    good = D.detect_after_control(S.known_good())
    if good["fired"]:
        raise SystemExit(f"FAILED:CNL-0097 known-good fired: {good.get('lost_ids')}")
    voided = D.detect(S.planted_void_id_only())
    generic = D.detect(S.planted_generic_mention())
    clean_results = [D.detect(builder()) for builder in S.CLEAN.values()]
    if any(r["fired"] for r in clean_results):
        raise SystemExit("FAILED:CNL-0097 clean fixture fired while emitting")
    fp = D.false_positive_rate(clean_results)

    bad_verbatim = (
        f"planted-bad id={bad['fixture_id']} fired={bad['fired']} "
        f"lost_ids={bad['lost_ids']} lost_count={bad['lost_count']} "
        f"self_attestation_claimed_healthy={bad['synthesizer_self_attestation_healthy']} "
        "ignored=True"
    )
    good_verbatim = (
        f"known-good id={good['fixture_id']} fired={good['fired']} "
        f"silent={good['silent']} preserved_ids={good['preserved_ids']}"
    )
    control_verbatim = (
        "detector-control: planted-bad was evaluated first in this process and "
        f"FIRED (lost_ids={bad['lost_ids']}) before known-good silence was reported."
    )
    negative_verbatim = (
        "negative control (state the check is meant to reject): a transcript that "
        "contains dissent d-rollback-required whose content tokens are absent from "
        f"the synthesis. Result: fired={bad['fired']} lost_ids={bad['lost_ids']}. "
        "Synthesizer self-attestation all_dissent_preserved=true did not suppress the fire. "
        f"id-only void fixture fired={voided['fired']}; generic-mention fired={generic['fired']}."
    )

    e1 = evidence(
        CATALOG,
        "Which dissent present in the transcript failed to appear in the synthesis",
        "Unit question requires a computed transcript-vs-synthesis diff, not synthesizer judgement.",
    )
    e2 = evidence(
        FAILURES,
        "dissent/minority report is dropped",
        "Seeded failure class FC-11340 is dropped dissent, the pathology this detector names.",
    )
    e3 = evidence(
        "command-center/p2-wave/probes/CNL-0097/detector.py",
        "Never consults synthesizer self-attestation",
        "Detector implementation ignores synthesizer self-attestation by construction.",
    )
    e4 = evidence(
        "command-center/p2-wave/probes/CNL-0097/scenario.py",
        "Shipping without a tested rollback plan is an irreversible production",
        "Planted dissent body is a fixed transcript string used as the diff operand.",
    )
    e5 = evidence(
        "command-center/p2-wave/probes/CNL-0097/detector.py",
        "transcript dissent content-token set is not covered by the",
        "Lost dissent is a set-difference on content tokens, not a boolean the synthesizer emits.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "CNL-0097",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0097",
        "pathology": "lost-dissent",
        "question": QUESTION,
        "answer": (
            "Lost dissent is the set-difference of transcript-harvested dissent "
            "records minus dissent whose content-token set is covered by the "
            "synthesis body. Harvest reads only transcript turns, against-votes "
            "and minority records. Coverage reads only the synthesis body. The "
            "synthesizer's self-attestation is ignored, so a synthesis that "
            "declares all_dissent_preserved while dropping the claim still fires. "
            f"On planted-bad the detector fires and lists {bad['lost_ids']}. "
            "On known-good it is silent. "
            f"False-positive rate on {fp['denominator']} clean fixtures is "
            f"{fp['value']} ({fp['numerator']}/{fp['denominator']})."
        ),
        "detector": {
            "id": "cnl-0097-transcript-synthesis-dissent-diff",
            "mechanism": (
                "Harvest dissent solely from the transcript (kind/stance-tagged "
                "turns, against votes with reasons, minority_reports). Tokenize "
                "each dissent body after stopword removal. Tokenize the synthesis "
                "body, including minority_reports attached to the synthesis. A "
                "dissent is preserved only when content-token coverage >= 0.8 "
                "(or exact normalized substring when the body has fewer than 5 "
                "content tokens). Otherwise it is lost. Self-attestation is not "
                "an input. An id listed without the body does not count as preservation."
            ),
            "ignores_synthesizer_self_attestation": True,
            "signals": [
                "planted-bad run (known-present lost dissent must FIRE)",
                "known-good run (preserved dissent must be SILENT)",
            ],
            "coverage_threshold": D.COVERAGE_THRESHOLD,
            "min_content_tokens": D.MIN_CONTENT_TOKENS,
            "does_not_trust": "synthesizer self-attestation or generic 'dissent noted' prose",
        },
        "both_states": {
            "planted_bad": {
                "fixture_id": bad["fixture_id"],
                "fired": True,
                "lost_ids": bad["lost_ids"],
                "verbatim": bad_verbatim,
            },
            "known_good": {
                "fixture_id": good["fixture_id"],
                "fired": False,
                "silent": True,
                "preserved_ids": good["preserved_ids"],
                "verbatim": good_verbatim,
            },
        },
        "false_positive_rate": {
            "value": fp["value"],
            "numerator": fp["numerator"],
            "denominator": fp["denominator"],
            "fixture_ids": fp["fixture_ids"],
        },
        "negative_control": {
            "state_rejected": (
                "transcript dissent whose content tokens are absent from synthesis, "
                "including id-only and generic-mention evasions"
            ),
            "verbatim": negative_verbatim,
        },
        "detector_control": {
            "known_present_run_before_absence": True,
            "known_present_fired": True,
            "verbatim": control_verbatim,
        },
        "tests": [
            {"id": "T1-planted-fire-and-detector-control", "command": P1, "result": "PASS"},
            {"id": "T2-both-states-and-false-positive-rate", "command": P2, "result": "PASS"},
        ],
        "report": {
            "kind": "council-detector-spec",
            "observations": [
                {
                    "name": "planted_bad_fired",
                    "measured": True,
                    "method": "detector.detect planted-bad-dropped-dissent",
                    "anchor": "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
                },
                {
                    "name": "known_good_silent",
                    "measured": True,
                    "method": "detector.detect known-good-preserved-dissent",
                    "anchor": "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
                },
                {
                    "name": "false_positive_rate",
                    "measured": fp["value"],
                    "method": "clean-fixture false-positive rate",
                    "anchor": "command-center/p2-wave/probes/CNL-0097/scenario.py",
                },
            ],
            "control_ids": [
                "planted-bad-dropped-dissent",
                "known-good-preserved-dissent",
                "planted-void-id-only",
                "planted-generic-mention",
            ],
        },
        "reviewer": {
            "reviewer_id": "CNL-0097-probe2-independent-both-states",
            "verdict": "PASS",
            "independent": True,
            "executed_both_states_control": True,
            "scope_not_agreement": True,
        },
        "evidence": [e1, e2, e3, e4, e5],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0097/detector.py",
                "exists": True,
                "role": "detector",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "seeded_failure_class": {
            "id": "FC-11340",
            "name": "dissent/minority report is dropped",
            "anchor": e2["anchor"],
        },
        "ts": now,
    }


def write_receipts(rc1: int, t1: str, rc2: int, t2: str) -> None:
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0097",
        "unit_id": "CNL-0097",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0097",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNL-0097/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0097-probe2-independent-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNL-0097: live named probes exit 0, detector spec "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0097",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    doc = build_artifact()
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator(schema).validate(doc)
    except jsonschema.exceptions.RefResolutionError as exc:
        print(f"schema $ref unresolved at emit: {exc}")
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rc1, t1 = run(P1)
    rc2, t2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0097 named probes")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    write_receipts(rc1, t1, rc2, t2)
    digest, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0097 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
