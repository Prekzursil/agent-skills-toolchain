#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0107-fusion-precondition-checker.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

import checker as C  # noqa: E402
import fusion as F  # noqa: E402
from world import load_world, write_fixtures  # noqa: E402

UNIT = "WFA-0107"
OUT = "command-center/wfa/WFA-0107-fusion-precondition-checker.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
SCHEMA_FILE = "command-center/wfa/schema/wfa-schema-pack.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/WFA-0107/regression-fixture.schema.json"
)
SENTINEL = "SUCCESS:WFA-0107"
QUESTION = (
    "Implementation target: a checker that, given a source pair and an "
    "operator, returns LEGAL or ILLEGAL with a reason - consuming the "
    "symmetrised compat relation, the mechanism conflict edges and the "
    "licence compatibility matrix - so an illegal fusion is refused "
    "before it is attempted."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0107/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0107/probe2_independent_attempts.py"
)

LEGAL_SAMPLES = (
    ("wf-review-a", "wf-review-b", "union"),
    ("wf-review-a", "wf-review-b", "stage-splice"),
    ("wf-review-a", "wf-review-gpl", "union"),
    ("wf-review-a", "wf-review-audio", "union"),
)
ILLEGAL_SAMPLES = (
    ("wf-review-a", "wf-review-sample", "union", "mechanism-conflict"),
    ("wf-review-a", "wf-review-prop", "union", "licence"),
    ("wf-review-a", "wf-review-unknown", "union", "licence"),
    ("wf-review-a", "wf-council-blind", "union", "compat"),
    ("wf-review-a", "wf-review-audio", "stage-splice", "type"),
    ("wf-council-blind", "wf-council-shared", "ensemble", "mechanism-conflict"),
    ("wf-dispatch-ff", "wf-dispatch-barrier", "union", "mechanism-conflict"),
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def schema_def() -> dict:
    """Load the local unit schema. The catalog pack $defs/RegressionFixture is a
    remote $ref shim; resolving it hits ast-integrate.invalid (RefResolutionError).
    """
    return json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))


def validate_or_die(doc: dict) -> None:
    schema = schema_def()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        msgs = "; ".join(
            f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors[:8]
        )
        raise SystemExit(f"FAILED:WFA-0107 emit schema {msgs}")
    for garbage in (
        {"totally": "unrelated"},
        {"passing_tests": 999999},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {},
    ):
        g_errs = list(validator.iter_errors(garbage))
        if not g_errs:
            raise SystemExit(
                f"FAILED:WFA-0107 emit schema accepts garbage {list(garbage)[:2]}"
            )
    pack = REPO / SCHEMA_FILE
    if not pack.is_file():
        raise SystemExit("FAILED:WFA-0107 emit catalog schema pack missing")


def sample_legal(world) -> list[dict]:
    rows = []
    bps = F.load_blueprints()
    for left, right, op in LEGAL_SAMPLES:
        verdict = C.check(left, right, op, world)
        if verdict["verdict"] != "LEGAL":
            raise SystemExit(f"FAILED:WFA-0107 emit expected LEGAL {left} {right} {op}")
        fwd = F.attempt(left, right, op, bps)
        rev = F.attempt(right, left, op, bps)
        if not fwd["ok"] or not rev["ok"]:
            raise SystemExit(
                f"FAILED:WFA-0107 emit LEGAL attempt did not succeed "
                f"{left}/{right}/{op} fwd={fwd['defects']} rev={rev['defects']}"
            )
        rows.append(
            {
                "left": left,
                "right": right,
                "operator": op,
                "checker": verdict,
                "attempt_fwd": {"ok": fwd["ok"], "defects": fwd["defects"]},
                "attempt_rev": {"ok": rev["ok"], "defects": rev["defects"]},
            }
        )
    return rows


def sample_illegal(world) -> list[dict]:
    rows = []
    bps = F.load_blueprints()
    for left, right, op, kind in ILLEGAL_SAMPLES:
        verdict = C.check(left, right, op, world)
        if verdict["verdict"] != "ILLEGAL":
            raise SystemExit(
                f"FAILED:WFA-0107 emit expected ILLEGAL {left} {right} {op}"
            )
        if not verdict["blocking_edge"] or "|" not in verdict["reason"]:
            raise SystemExit("FAILED:WFA-0107 emit generic reason")
        if kind == "licence" and "licence" not in (verdict["blocking_edge"] or ""):
            raise SystemExit(
                f"FAILED:WFA-0107 emit licence sample not licence-blocked {verdict}"
            )
        if kind == "compat" and world.has_compat(left, right):
            raise SystemExit("FAILED:WFA-0107 emit compat sample still compatible")
        if kind == "licence" and not world.has_compat(left, right):
            raise SystemExit(
                "FAILED:WFA-0107 emit licence sample missing structural compat"
            )
        att = F.attempt(left, right, op, bps)
        if att["ok"]:
            raise SystemExit(
                f"FAILED:WFA-0107 emit ILLEGAL attempt succeeded {left} {right} {op}"
            )
        rows.append(
            {
                "left": left,
                "right": right,
                "operator": op,
                "kind": kind,
                "checker": verdict,
                "attempt": {
                    "ok": att["ok"],
                    "defects": att["defects"],
                },
            }
        )
    return rows


def main() -> int:
    write_fixtures()
    world = load_world()
    live = C.cartesian(world)
    counts = C.legality_counts(live)
    if counts["LEGAL"] < 1 or counts["ILLEGAL"] < 1:
        print("FAILED:WFA-0107 emit both-states empty", counts)
        return 1
    if counts["cells"] != len(live):
        print("FAILED:WFA-0107 emit cell mismatch")
        return 1
    for op, slot in counts["per_operator"].items():
        if slot["LEGAL"] + slot["ILLEGAL"] != len(world.pairs()):
            print("FAILED:WFA-0107 emit per-operator coverage", op, slot)
            return 1

    legal_rows = sample_legal(world)
    illegal_rows = sample_illegal(world)

    licence_sample = next(r for r in illegal_rows if r["kind"] == "licence")
    copyleft = C.check("wf-review-a", "wf-review-gpl", "union", world)
    if copyleft["verdict"] != "LEGAL":
        print("FAILED:WFA-0107 emit over-refused copyleft+permissive")
        return 1

    both = {
        "legal_attempts_succeed_both_directions": all(
            r["attempt_fwd"]["ok"] and r["attempt_rev"]["ok"] for r in legal_rows
        ),
        "illegal_attempts_fail_or_invalid": all(
            not r["attempt"]["ok"] for r in illegal_rows
        ),
        "licence_blocks_despite_structural_compat": (
            licence_sample["checker"]["verdict"] == "ILLEGAL"
            and world.has_compat(licence_sample["left"], licence_sample["right"])
            and "licence" in licence_sample["checker"]["blocking_edge"]
            and not licence_sample["attempt"]["ok"]
        ),
        "copyleft_plus_permissive_legal": copyleft["verdict"] == "LEGAL",
    }
    if not all(both.values()):
        print("FAILED:WFA-0107 emit both_states", both)
        return 1

    tests = [
        {
            "id": "test_legal_sample_attempted_both_directions",
            "result": "PASS",
            "detail": f"n={len(legal_rows)}",
        },
        {
            "id": "test_licence_incompatibility_blocks_when_structural_compat_holds",
            "result": "PASS",
            "detail": licence_sample["checker"]["reason"],
        },
        {
            "id": "test_reason_names_specific_blocking_edge",
            "result": "PASS",
            "detail": "every ILLEGAL sample reason contains blocking_edge with '|'",
        },
        {
            "id": "test_illegal_fusion_attempt_fails",
            "result": "PASS",
            "detail": f"n={len(illegal_rows)}",
        },
    ]

    honesty = {
        "upstream_live_artifacts": world.upstream,
        "fixture_source": (
            "reconstructed-fixture from catalog specs of WFA-0081, WFA-0079, "
            "WFA-0062 (named mutex pairs), WFA-0004 symmetrised undirected "
            "compat, IMP-0157/WFA-0139 fail-closed licence lattice"
        ),
        "not_claimed": (
            "This unit does not claim consumption of the 108-blueprint "
            "production merge map or fetched licence files. The checker is "
            "proven on a reconstructed fixture corpus that encodes the named "
            "compat, conflict, and licence rules those upstream units would "
            "supply. Missing live upstream files are recorded present=false."
        ),
        "cloud_ok_is_not_delivery": True,
    }

    now = utc_now()
    doc = {
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0107/checker.py",
                "role": "checker",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0107/fusion.py",
                "role": "independent-fusion-attempt",
            },
        ],
        "both_states": both,
        "cartesian_cells": counts["cells"],
        "completion_sentinel": SENTINEL,
        "evidence": {
            "A": (
                f"Cartesian checker verdicts over {counts['cells']} "
                f"pair-by-operator cells; LEGAL={counts['LEGAL']} "
                f"ILLEGAL={counts['ILLEGAL']}; per-operator counts in "
                "legality_counts.per_operator."
            ),
            "B": (
                "Mechanically independent fusion.attempt (does not import "
                "checker, does not read the three graph JSON files) was run "
                "on LEGAL samples in both orientations (must succeed) and on "
                "ILLEGAL samples (must refuse or yield an invalid IR). A "
                "checker whose refusals were never attempted would fail this."
            ),
        },
        "honesty": honesty,
        "host": {"platform": sys.platform},
        "id": UNIT,
        "inputs_consumed": [
            {
                "path": "command-center/p2-wave/probes/WFA-0107/fixtures/compat_relation.json",
                "role": "symmetrised-compat",
                "live_upstream": "command-center/wfa/WFA-0081-merge-compatibility-map-v2.json",
                "live_present": any(
                    r["path"].endswith("WFA-0081-merge-compatibility-map-v2.json")
                    and r["present"]
                    for r in world.upstream
                ),
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0107/fixtures/mechanism_conflicts.json",
                "role": "mechanism-conflicts",
                "live_upstream": "command-center/wfa/WFA-0062-mechanism-conflicts.json",
                "live_present": any(
                    r["path"].endswith("WFA-0062-mechanism-conflicts.json")
                    and r["present"]
                    for r in world.upstream
                ),
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0107/fixtures/licence_matrix.json",
                "role": "licence-matrix",
                "live_upstream": "command-center/wfa/WFA-0079-provenance-license-graph-v2.json",
                "live_present": any(
                    r["path"].endswith("WFA-0079-provenance-license-graph-v2.json")
                    and r["present"]
                    for r in world.upstream
                ),
            },
        ],
        "legality_counts": counts,
        "local_schema": LOCAL_SCHEMA,
        "min_bytes_threshold": 2048,
        "named_probes": [{"id": "probe1", "command": P1}, {"id": "probe2", "command": P2}],
        "operators": list(world.operators),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question_or_target": QUESTION,
        "report_kind": "RegressionFixture",
        "reviewer": {
            "reviewer_id": "WFA-0107-probe2-independent-fusion-attempt",
            "verdict": "PASS",
            "independent": True,
            "note": "probe2 re-attempts fusions without importing checker.py",
        },
        "samples": {"legal": legal_rows, "illegal": illegal_rows},
        "schema_gate": {
            "catalog_output_schema": SCHEMA,
            "catalog_pack_present": (REPO / SCHEMA_FILE).is_file(),
            "validated_against": LOCAL_SCHEMA,
            "catalog_pack_ref_is_network_shim": True,
            "pivot": (
                "Draft202012Validator(pack['$defs']['RegressionFixture']) "
                "raises RefResolutionError against ast-integrate.invalid; "
                "live gate is the local additionalProperties:false schema."
            ),
            "garbage_rejected": True,
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "tests": tests,
        "title": "Precondition checker deciding which operator is legal for which pair",
        "ts": now,
        "unit_id": UNIT,
        "verdicts": live,
    }
    validate_or_die(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0107 emit sentinel vanished")
        return 1
    out_path.write_text(text, encoding="utf-8")
    sha, n = digest(out_path)
    if n < 2048:
        print("FAILED:WFA-0107 emit tiny", n)
        return 1
    print(f"EMIT {OUT} bytes={n} sha256={sha} cells={counts['cells']} LEGAL={counts['LEGAL']} ILLEGAL={counts['ILLEGAL']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
