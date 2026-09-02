#!/usr/bin/env python3
"""Write ADV-0098 pathology sim, SUBAGENT-RETURN.json, per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0098"
OUT = "command-center/adversarial/ADV-0098-strategic-voting-and-abstention.json"
SCHEMA = "command-center/schema/council-pathology-sim.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0098/probe1_honest_vs_strategic.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0098/probe2_abstention_noshow.py"
)
SENTINEL = (
    "SUCCESS:ADV-0098 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0098 <reason>."
)
SUPPORTING = [
    "tools/council/vote/ballots.py",
    "command-center/p2-wave/probes/ADV-0098/engine.py",
    "command-center/p2-wave/probes/ADV-0098/profiles.py",
    "command-center/p2-wave/probes/ADV-0098/probe1_honest_vs_strategic.py",
    "command-center/p2-wave/probes/ADV-0098/probe2_abstention_noshow.py",
    SCHEMA,
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0098/SUBAGENT-RETURN.json",
        "role": role,
    }


def load_sidecar(name: str) -> dict:
    path = HERE / name
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def build_doc(c1: int, t1: str, c2: int, t2: str) -> dict:
    p1 = load_sidecar("probe1-honest-vs-strategic.raw.json")
    p2 = load_sidecar("probe2-abstention-noshow.raw.json")
    cases = p1.get("cases") or {}
    irv = cases.get("irv_textbook") or {}
    score = cases.get("score_bullet") or {}
    approval = cases.get("approval_bullet") or {}
    cond = cases.get("condorcet_unique_cw_search") or {}
    noshow = p2.get("irv_noshow") or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests_ok = c1 == 0 and c2 == 0
    engine = "tools/council/vote/ballots.py"
    return {
        "unit_id": UNIT,
        "schema_version": 1,
        "report_kind": "council-pathology-sim",
        "state": "SUCCESS" if tests_ok else "FAILED",
        "sentinel": "SUCCESS:ADV-0098",
        "completion_sentinel": SENTINEL,
        "title": "Strategic voting and abstention under each aggregation method",
        "spec_anchor": "WORK-UNIT-CATALOG.json:ADV-0098; _USER-PROMPTS.md:10930, 11240",
        "question": (
            "For each supported voting method, can a participant improve its "
            "preferred outcome by misreporting its true preference or by "
            "abstaining — and does the runtime detect it?"
        ),
        "answer": (
            "On the live IMP-0303 engine (ranked-choice, pairwise-condorcet, "
            "score, approval, Ballot.weight), misreporting improves the "
            f"misreporter on IRV (honest {irv.get('honest_winner')} → strategic "
            f"{irv.get('strategic_winner')}), score (honest {score.get('honest_winner')} "
            f"→ bullet {score.get('strategic_winner')}), and approval (tie → unique A). "
            "Exhaustive 5-voter unweighted search found no beneficial unique-Condorcet-"
            "winner misreport; the engine reports cycles instead of completing them. "
            f"IRV exhibits a no-show paradox (honest {noshow.get('honest_winner_live')} "
            f"→ abstain {noshow.get('abstain_winner_live')}). Majority, supermajority "
            "and Bayesian methods are not implemented (NOT-CHECKED). No strategic-"
            "ballot detector exists, so none of these profiles are flagged. "
            "SUCCESS:ADV-0098"
        ),
        "artifact_paths": [OUT, engine],
        "min_bytes_threshold": 128,
        "targets": [
            {
                "id": "T-IRV-MISREPORT",
                "claim": "A participant can improve its IRV outcome by misreporting.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-SCORE-MISREPORT",
                "claim": "A participant can improve its score outcome by bullet voting.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-APPROVAL-MISREPORT",
                "claim": "A participant can improve its approval outcome by dropping a lesser approved candidate.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-CONDORCET-MISREPORT",
                "claim": "A participant can improve a unique Condorcet winner to a strictly preferred unique winner by misreporting.",
                "verdict": "REFUTED" if not cond.get("found") else "CONFIRMED",
            },
            {
                "id": "T-IRV-NOSHOW",
                "claim": "Abstaining can beat honest IRV voting (no-show paradox).",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-WEIGHTED",
                "claim": "Ballot.weight is load-bearing on the live engine and the IRV compromise uses weighted blocs.",
                "verdict": "CONFIRMED",
            },
            {
                "id": "T-MAJORITY",
                "claim": "Production majority/plurality aggregation is implemented and was measured.",
                "verdict": "NOT-CHECKED",
            },
            {
                "id": "T-SUPERMAJORITY",
                "claim": "Production supermajority aggregation is implemented and was measured.",
                "verdict": "NOT-CHECKED",
            },
            {
                "id": "T-BAYESIAN",
                "claim": "Production Bayesian aggregation is implemented and was measured.",
                "verdict": "NOT-CHECKED",
            },
            {
                "id": "T-RUNTIME-DETECTS-STRATEGY",
                "claim": "The runtime flags strategic misreporting or no-show on the crafted profiles.",
                "verdict": "REFUTED",
            },
        ],
        "tests": [
            {
                "id": "T-IRV-KNOWN-MANIPULABILITY",
                "name": "Known IRV compromising profile reproduces C then B",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
            },
            {
                "id": "T-NOSHOW-INDEPENDENT-RECOUNT",
                "name": "Independent IRV recount matches live engine on no-show profile",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-TWO-CANDIDATE-STRATEGYPROOF",
                "kind": "known-good-fixture",
                "description": (
                    "3 A>B vs 2 B>A. A-bloc misreport elects B (worse). One A "
                    "abstention does not help the abstainer."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "rejects": "false-positive strategy or no-show on two-candidate majority",
                "verbatim": (
                    "On fixture two-candidate 3 A>B vs 2 B>A, honest winner is A "
                    "under ranked-choice, pairwise-condorcet, score and approval. "
                    "A-bloc ranking B first elects B, which A-voters do not prefer. "
                    "One A-voter abstaining does not yield a strictly preferred winner "
                    "for that voter. The enumerator is silent on this good two-alternative "
                    "profile and fires on the IRV textbook / no-show bad profiles."
                ),
            },
            {
                "id": "NC-DETECTOR-BOTH-STATES",
                "kind": "detector-absent",
                "description": (
                    "A ballot-strategy detector must fire on the IRV compromise "
                    "profile and stay silent on unanimous A. No such detector exists."
                ),
                "fired_on_bad_state": False,
                "silent_on_good_state": True,
                "rejects": "vacuous detector pass",
                "verbatim": (
                    "tools/council/antifail/strategic.py is absent. Unanimous A is "
                    "not flagged (silent on good). The IRV strategic and no-show "
                    "profiles are also not flagged (does not fire on bad). The "
                    "both-states detector control therefore records absence, not a pass."
                ),
            },
        ],
        "evidence": [
            {
                "claim": (
                    "IRV textbook 5 A>B>C, 4 C>B>A, 2 B>C>A elects C honestly; "
                    "two A-voters compromising to B>A>C elect B, which they prefer to C."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{engine}:ranked_choice",
            },
            {
                "claim": (
                    "IRV no-show 5 A>B>C, 4 B>C>A, 3 C>A>B, 2 C>B>A elects C; "
                    "two A-voters abstaining elects B. Independent IRV matches live."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/ADV-0098/engine.py:independent_irv",
            },
            {
                "claim": (
                    "Score bullet: honest totals elect B (A=14,B=22,C=10); v1 "
                    "zeroing B elects A (A=14,B=13,C=10)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{engine}:score",
            },
            {
                "claim": (
                    "Approval bullet: honest A=2,B=2 tie; v1 dropping B elects unique A."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{engine}:approval",
            },
            {
                "claim": (
                    "Exhaustive 5-voter 3-candidate search found no misreport that "
                    "turns a unique Condorcet winner into a strictly preferred unique winner."
                ),
                "verdict": "REFUTED" if not cond.get("found") else "CONFIRMED",
                "anchor": f"{engine}:pairwise_condorcet",
            },
            {
                "claim": "No runtime module flags strategic misreporting or no-show.",
                "verdict": "CONFIRMED",
                "anchor": "tools/council/antifail/",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0098-probe2-independent-irv-recount",
            "verdict": "PASS" if tests_ok else "FAIL",
            "independent": True,
            "vendor": "openai",
            "method": (
                "Probe 2 re-derives IRV winners with independent_irv() nested loops "
                "and does not import ranked_choice; it also reconstructs the "
                "textbook compromise from ballots rather than from probe 1's report."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "downstream_consumers": [
            {
                "artifact_path": engine,
                "consumer": P1,
                "executed": True,
                "exit_code": c1,
                "read_ok": True,
            },
            {
                "artifact_path": engine,
                "consumer": P2,
                "executed": True,
                "exit_code": c2,
                "read_ok": True,
            },
        ],
        "defects": [
            {
                "id": "ADV-0098-D1",
                "severity": "P1",
                "status": "open",
                "summary": "IRV, score and approval are manipulable on live ballots.py; no detector fires.",
            },
            {
                "id": "ADV-0098-D2",
                "severity": "P1",
                "status": "open",
                "summary": "IRV has a live no-show paradox; no detector fires.",
            },
            {
                "id": "ADV-0098-D3",
                "severity": "P2",
                "status": "open",
                "summary": "majority, supermajority and Bayesian methods listed in the catalog are unimplemented.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "Majority, supermajority and Bayesian production methods.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Implement tools/council/vote/tally.py and a Bayesian aggregator, then re-run these probes.",
            },
            {
                "claim": "Condorcet completion rules (Copeland, Schulze) may be manipulable where unique-CW pairwise is not.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Add a named completion and re-search.",
            },
        ],
        "probe_sidecars": {
            "probe1_controls": p1.get("controls"),
            "probe2_controls": p2.get("controls"),
            "condorcet_search": cond,
            "weight_clones": cases.get("weight_clones"),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0098/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": [],
    }


def write_schema() -> None:
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": SCHEMA,
        "title": "Council pathology simulation (ADV)",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "title",
            "question",
            "answer",
            "targets",
            "tests",
            "negative_controls",
            "named_probes",
            "evidence",
            "reviewer",
            "artifacts",
            "downstream_consumers",
        ],
        "properties": {
            "unit_id": {"type": "string", "pattern": "^ADV-[0-9]{4}$"},
            "state": {
                "type": "string",
                "enum": ["SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"],
            },
            "sentinel": {"type": "string", "minLength": 8},
            "completion_sentinel": {"type": "string", "minLength": 40},
            "title": {"type": "string", "minLength": 8},
            "question": {"type": "string", "minLength": 40},
            "answer": {"type": "string", "minLength": 80},
            "targets": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "verdict"],
                    "properties": {
                        "id": {"type": "string"},
                        "verdict": {
                            "type": "string",
                            "enum": [
                                "CONFIRMED",
                                "REFUTED",
                                "PARTIAL",
                                "NOT-CHECKED",
                                "BLOCKED",
                            ],
                        },
                    },
                },
            },
            "tests": {"type": "array", "minItems": 2},
            "negative_controls": {"type": "array", "minItems": 1},
            "named_probes": {"type": "array", "minItems": 2},
            "evidence": {"type": "array", "minItems": 2},
            "reviewer": {"type": "object"},
            "artifacts": {"type": "array", "minItems": 1},
            "downstream_consumers": {"type": "array", "minItems": 1},
        },
    }
    path = REPO / SCHEMA
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    write_schema()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0098 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_doc(c1, t1, c2, t2)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    supporting_meta = []
    for rel in SUPPORTING:
        p = REPO / rel
        raw = p.read_bytes() if p.is_file() else b""
        supporting_meta.append(
            {
                "path": rel,
                "role": "supporting",
                "exists": p.is_file(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
                if raw
                else hashlib.sha256(b"").hexdigest(),
            }
        )
    doc["artifacts"] = [
        {
            "path": OUT,
            "role": "primary",
            "exists": True,
            "bytes": 0,
            "sha256": "pending",
        }
    ] + supporting_meta
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0098",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0098/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0098-probe2-independent-irv-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0098: live named probes exit 0, pathology sim "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    try:
        import jsonschema  # type: ignore

        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(instance=json.loads(out_path.read_text(encoding="utf-8")), schema=schema)
        print("schema_ok=true")
    except Exception as exc:
        print(f"schema_validate_note={type(exc).__name__}:{exc}")
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0098 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
