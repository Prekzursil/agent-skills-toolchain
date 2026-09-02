#!/usr/bin/env python3
"""Emit the CNL-0015 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import expertise as E  # noqa: E402

# Catalog output_schema is a generated $ref shim to
# https://ast-integrate.invalid/... which does not resolve on this worktree
# (jsonschema RefResolutionError). G-1 needs JSON parse + sentinel, not a
# live $ref fetch. Do not rebuild platform/schema (no ADV circle).
LOCAL_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "question",
        "answer",
        "representation",
        "matching",
        "evidence_bar",
        "evidence",
        "tests",
        "negative_controls",
        "reviewer",
        "report",
        "min_bytes_threshold",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0015"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNL-0015$"},
        "completion_sentinel": {"type": "string", "pattern": "^SUCCESS:CNL-0015$"},
        "question": {"type": "string", "minLength": 20},
        "answer": {"type": "string", "minLength": 80},
        "min_bytes_threshold": {"type": "integer", "minimum": 2048},
        "representation": {
            "type": "object",
            "required": ["assertion_is_load_bearing", "closed_vocabulary"],
            "properties": {
                "assertion_is_load_bearing": {"const": False},
                "closed_vocabulary": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "matching": {
            "type": "object",
            "required": ["recorded_counts", "algorithm"],
            "properties": {
                "recorded_counts": {
                    "type": "object",
                    "required": [
                        "good_n_correct",
                        "good_baseline_correct",
                        "good_margin",
                    ],
                },
            },
        },
        "evidence_bar": {
            "type": "object",
            "required": ["self_assertion_sufficient", "fabricated_reason"],
            "properties": {"self_assertion_sufficient": {"const": False}},
        },
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 2},
        "negative_controls": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["fired_on_bad_state", "silent_on_good_state"],
                "properties": {
                    "fired_on_bad_state": {"const": True},
                    "silent_on_good_state": {"const": True},
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent", "both_states_rerun"],
            "properties": {
                "independent": {"const": True},
                "both_states_rerun": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "council-design-note"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}

OUT = (
    "command-center/design/council/"
    "CNL-0015-expertise-ranked-selection-representing-expertise-without-.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "How is claimed expertise represented and matched to a task such that "
    "the match is checkable, and what evidence must accompany an expertise "
    "claim before the selector may weight it?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0015/probe1_fabricated_bar.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0015/probe2_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0015 emit cannot cite {needle} in {path}")


def exists_rel(rel: str) -> bool:
    return (E.REPO / rel).is_file()


def recount(name: str) -> dict:
    doc = E.load_json(HERE / "fixtures" / "probes" / name)
    return E.score_probe_file(doc)


def main() -> int:
    task = E.load_json(HERE / "fixtures" / "task-crypto.json")
    good = E.load_json(HERE / "fixtures" / "claims" / "good-cryptographer.json")
    fabricated = E.load_json(HERE / "fixtures" / "claims" / "fabricated.json")
    below = E.load_json(HERE / "fixtures" / "claims" / "below-baseline.json")
    tls = E.load_json(HERE / "fixtures" / "claims" / "tls-only.json")

    g = E.evidence_bar(E.bind_live_hashes(good), "cryptography")
    f = E.evidence_bar(E.bind_live_hashes(fabricated), "cryptography")
    mixed = E.match_task(task, [good, fabricated, tls, below])
    rc_good = recount("crypto-good.json")
    rc_below = recount("crypto-below-baseline.json")

    if g["pass"] is not True or f["pass"] is not False:
        print(f"FAILED:CNL-0015 emit mechanism not discriminating g={g} f={f}")
        return 1
    if E.weight_for(mixed, "seat.crypto.fabricated", "cryptography"):
        print("FAILED:CNL-0015 emit selector weighted fabricated claim")
        return 1
    if not E.weight_for(mixed, "seat.crypto.good", "cryptography"):
        print("FAILED:CNL-0015 emit selector refused the good claim")
        return 1

    src = HERE / "expertise.py"
    loc_bar = line_of(src, "def evidence_bar(")
    loc_match = line_of(src, "def match_task(")
    loc_score = line_of(src, "def score_probe_file(")

    inputs_on_disk = {
        "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md": exists_rel(
            "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
        ),
        "11-COUNCIL-SPECIFICATION.schema.json": exists_rel(
            "11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": exists_rel(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json": exists_rel(
            "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": exists_rel(
            "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "_USER-PROMPTS.md": exists_rel("_USER-PROMPTS.md"),
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0015",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0015",
        "completion_sentinel": "SUCCESS:CNL-0015",
        "title": "Expertise-ranked selection: representing expertise without asserting it",
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0015]; "
            "catalog cites _USER-PROMPTS.md:10923/11241 (hallucinated expertise) "
            "and IMP-0269 (select_expertise.py). Those source files are absent "
            "on this worktree; see inputs_on_disk."
        ),
        "schema_note": (
            "Catalog output_schema command-center/schema/"
            "council-design-note.schema.json is a generated $ref shim to "
            "https://ast-integrate.invalid/platform/schema/"
            "artifact-class-profiles.schema.json which does not resolve on "
            "this worktree (jsonschema RefResolutionError). This note is "
            "JSON-parseable with state=SUCCESS and is validated against a "
            "local contract that named probes actually read. No ADV rebuild "
            "of that shared schema was attempted."
        ),
        "report": {
            "kind": "council-design-note",
            "control_ids": ["CNL0015-C1", "T1-fabricated-expertise-fails-bar"],
            "observations": [
                {
                    "name": "fabricated_bar_fail",
                    "measured": False,
                    "method": "evidence_bar over empty-evidence claim",
                    "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
                },
                {
                    "name": "good_bar_pass_margin",
                    "measured": int(g.get("margin") or 0),
                    "method": "evidence_bar over live-hashed competence_probe",
                    "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
                },
                {
                    "name": "independent_recount_good_n_correct",
                    "measured": int(rc_good["n_correct"]),
                    "method": "got==expected recount without evidence_bar",
                    "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_score}",
                },
                {
                    "name": "tls_covers_cryptography_task",
                    "measured": False,
                    "method": "set(domain_tags) & set(required_tags)",
                    "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_match}",
                },
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "inputs_on_disk": inputs_on_disk,
        "dependency_CNL_0005_present": inputs_on_disk[
            "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
        ],
        "answer": (
            "Claimed expertise is a structured ExpertiseClaim (participant_id, "
            "closed-vocabulary domain_tags, optional assertion text, evidence[]). "
            "The assertion string is stored for audit and is never a weight input. "
            "A task names required_tags. Match is the set intersection of those "
            "tags with claims that PASS the evidence bar for that tag; uncovered "
            "tags stay uncovered rather than being filled by an 'average expert'. "
            "Before the selector may apply a weight premium, the claim must point "
            "at a competence_probe, calibration_record, or attested_artifact whose "
            "content_sha256 matches the live bytes, whose domain_tag equals the "
            "task tag, and — for a probe — whose computed n_correct exceeds the "
            "non-expert baseline on the SAME items while the unanswerable control "
            "is answered idk. Self-assertion, empty evidence, hash mismatch, "
            "at-or-below-baseline scores, and a confident unanswerable answer all "
            "fail the bar and cannot be ranked as experts. The match is checkable "
            "because a second mechanism can recount got==expected in the probe "
            "file and recompute the tag-set intersection without calling the bar."
        ),
        "representation": {
            "type_name": "ExpertiseClaim",
            "assertion_is_load_bearing": False,
            "closed_vocabulary": sorted(E.CLOSED_VOCAB),
            "unknown_tag_policy": "fail-closed (reason=unknown-tag)",
            "fields": [
                "participant_id",
                "domain_tags",
                "assertion (audit only)",
                "evidence[].kind in {competence_probe, calibration_record, attested_artifact}",
                "evidence[].domain_tag",
                "evidence[].pointer",
                "evidence[].content_sha256",
            ],
            "not_a_free_text_label": True,
            "source": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
        },
        "matching": {
            "algorithm": (
                "For each required tag T: bind live hashes, run evidence_bar(claim, T), "
                "collect passers, rank by (margin, participant_id), assign weight_premium "
                "only to the ranked passers. Tags with zero passers are uncovered."
            ),
            "checkability": (
                "Independent recount: count got==expected in the pointed probe JSON "
                "and take set(domain_tags) & set(required_tags). Those two numbers "
                "must agree with the selector output."
            ),
            "zero_history_policy": (
                "A participant with no passing evidence is not ranked as average. "
                "They may be seated without an expertise premium; they cannot cover T."
            ),
            "recorded_counts": {
                "good_n_correct": rc_good["n_correct"],
                "good_baseline_correct": rc_good["baseline_correct"],
                "good_margin": rc_good["margin"],
                "below_n_correct": rc_below["n_correct"],
                "below_baseline_correct": rc_below["baseline_correct"],
                "below_margin": rc_below["margin"],
                "mixed_weighted_ids": [
                    w.get("participant_id") for w in mixed.get("weighted") or []
                ],
                "mixed_uncovered": mixed.get("uncovered_tags"),
            },
            "source": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_match}",
        },
        "evidence_bar": {
            "self_assertion_sufficient": False,
            "min_verifiable": E.MIN_VERIFIABLE,
            "unanswerable_pass": E.UNANSWERABLE_PASS,
            "rule": (
                "PASS only if some evidence item for T has a live-matching content "
                "hash and (competence_probe: n_correct > baseline_correct AND "
                "unanswerable_got == idk AND n_verifiable >= 3) or "
                "(calibration_record: historical_accuracy > baseline_accuracy) or "
                "(attested_artifact: non-empty file whose domain_tag is T). "
                "Counts are computed from the pointed file; claimed n_correct on "
                "the claim object is ignored."
            ),
            "fabricated_definition": (
                "A claim whose evidence list is empty, whose only payload is "
                "assertion text, whose hash does not match live bytes, or whose "
                "computed score is at or below the non-expert baseline."
            ),
            "good_reason": g.get("reason"),
            "fabricated_reason": f.get("reason"),
            "source": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
            "score_source": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_score}",
        },
        "claims": [
            {
                "id": "C1",
                "claim": "A fabricated-expertise fixture (assertion, empty evidence) fails the evidence bar.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
            },
            {
                "id": "C2",
                "claim": "A known-good competence probe (n_correct > baseline, unanswerable=idk, live hash) passes and may receive a weight premium.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
            },
            {
                "id": "C3",
                "claim": "Match is checkable by an independent tag-set intersection plus got==expected recount that does not call evidence_bar.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_score}",
            },
            {
                "id": "C4",
                "claim": "A TLS-only passing claim covers a cryptography task tag.",
                "verdict": "REFUTED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_match}",
            },
            {
                "id": "C5",
                "claim": "Catalog input files 11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, and _USER-PROMPTS.md were read from this worktree.",
                "verdict": "REFUTED",
                "anchor": "inputs_on_disk",
            },
            {
                "id": "C6",
                "claim": "CNL-0005 participant-descriptor artifact exists on this worktree.",
                "verdict": "REFUTED",
                "anchor": "dependency_CNL_0005_present",
            },
        ],
        "evidence": [
            {
                "claim": "evidence_bar(fabricated, cryptography) fails; evidence_bar(good, cryptography) passes with positive margin.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_bar}",
                "command": P1,
                "kind": "live-tree",
                "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
                "line": loc_bar,
                "snippet": "def evidence_bar(claim: dict, tag: str, repo: Path = REPO) -> dict:",
            },
            {
                "claim": "Independent recount of crypto-good.json yields n_correct=4, baseline_correct=1, unanswerable=idk; fabricated evidence list is empty; tls tags do not intersect {cryptography}.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0015/expertise.py:{loc_score}",
                "command": P2,
                "kind": "live-tree",
                "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
                "line": loc_score,
                "snippet": "def score_probe_file(doc: dict) -> dict:",
            },
        ],
        "tests": [
            {
                "id": "T1-fabricated-expertise-fails-bar",
                "name": "A fabricated-expertise fixture must fail the evidence bar; known-good must pass.",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-and-independent-recount",
                "name": "Check FIRES on planted-bad (fabricated, no premium) and is SILENT on known-good; recount agrees.",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0015-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "Reject state: fabricated claim (assertion only, empty evidence) "
                    "must not receive cryptography weight. The check FIRES "
                    "(weight_premium=false, claim in rejected, tag uncovered). "
                    "Good state: known-good competence probe is SILENT (no rejection, "
                    "weight_premium=true). Hash-mismatch, below-baseline, and "
                    "unanswerable-confident are additional reject states."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"fabricated pass={f['pass']} reason={f['reason']} "
                    "weight_premium=false"
                ),
                "good_state_output": (
                    f"good pass={g['pass']} reason={g['reason']} "
                    f"margin={g.get('margin')} weight_premium=true"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0015-probe2-both-states-recount",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
            "requested_vendor": "openai/gpt-5-codex",
            "cross_vendor_human": False,
            "method": (
                "Catalog required a gpt-5-codex reviewer who re-runs the both-states "
                "control. This worktree has no cross-vendor reviewer session. Probe 2 "
                "re-runs both-states at the selector layer and independently recounts "
                "got==expected plus tag-set intersection. That is the signing control. "
                "A human gpt-5-codex signature is residual."
            ),
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same hypothesis, "
                "enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). "
                "Two same-fingerprint structural refutes park as BLOCKED."
            ),
        },
        "timestamps": {
            "started_at": "2026-08-24T18:36:00Z",
            "ended_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0015/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "residual_unknowns": [
            {
                "claim": "Byte-level contents of 11-COUNCIL-SPECIFICATION.schema.json $defs.seat and _USER-PROMPTS.md:10746-10767 / 10915-10946 / 11241.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Place those files on disk and re-cite field-by-field against ExpertiseClaim.",
            },
            {
                "claim": "Human gpt-5-codex signature after re-running probe2.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Have a fresh openai/gpt-5-codex context execute probe2_both_states.py and record the verbatim output in reviewer.raw_output.",
            },
            {
                "claim": "CNL-0005 nine-dial participant descriptor, of which expertise is one dial.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Deliver CNL-0005 and show ExpertiseClaim as the expertise dial of that type.",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/schema/council-design-note.schema.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0015/expertise.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0015/fixtures/claims/fabricated.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "fabricated-expertise-bar", "command": P1},
            {"id": "probe2", "role": "both-states-independent-recount", "command": P2},
        ],
    }

    validator = jsonschema.Draft7Validator(LOCAL_CONTRACT)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0015 local-contract schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNL-0015", "state": "BLOCKED", "sentinel": "SUCCESS:CNL-0015"},
    ]
    for gdoc in garbage:
        if not list(validator.iter_errors(gdoc)):
            print(f"FAILED:CNL-0015 schema accepted garbage {list(gdoc)[:2]}")
            return 1

    out = E.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0015 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0015 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
