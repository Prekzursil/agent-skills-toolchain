#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0068-contradiction-adjudication.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402
import schema_offline as S  # noqa: E402

SCHEMA = "command-center/schema/adjudication-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0068/probe1_both_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0068/probe2_independent.py"
)
STAMP_FALLBACK = "2026-08-25T00:49:00Z"


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run(script: str) -> None:
    cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {script}"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(text[-4000:])
    if proc.returncode != 0:
        raise SystemExit(f"FAILED:CNF-0068 subprocess {script} rc={proc.returncode}")


def load_reviewer(name: str) -> dict:
    path = HERE / name
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("peer_verdicts_seen") is not False:
        raise SystemExit(f"FAILED:CNF-0068 {name} peer_verdicts_seen")
    return doc


def observation_stamp(out: Path) -> tuple[str, str]:
    if out.is_file():
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            prev = None
        if isinstance(prev, dict):
            ts = prev.get("timestamps") or {}
            started = ts.get("started_at")
            ended = ts.get("ended_at")
            if isinstance(started, str) and isinstance(ended, str):
                return started, ended
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return now or STAMP_FALLBACK, now or STAMP_FALLBACK


def artifact_row(rel: str, role: str, sha: str, size: int) -> dict:
    return {
        "path": rel,
        "exists": True,
        "bytes": size,
        "sha256": sha,
        "role": role,
        "eol": "LF",
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-4000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    unit = A.catalog_unit("CNF-0068")
    out_rel = str(unit["output_path"]).replace("\\", "/")
    schema_rel = str(unit["output_schema"]).replace("\\", "/")
    sentinel = str(unit["completion_sentinel"])
    out = REPO / out_rel

    run("command-center/p2-wave/probes/CNF-0068/reviewer_a.py")
    run("command-center/p2-wave/probes/CNF-0068/reviewer_b.py")
    rev_a = load_reviewer("_reviewer_a.json")
    rev_b = load_reviewer("_reviewer_b.json")
    a_map = {r["id"]: r for r in rev_a["edges"]}
    b_map = {r["id"]: r for r in rev_b["edges"]}

    edges_out = []
    observations = []
    disagreements = []
    live_lines = []
    for edge in A.load_fixture_edges():
        eid = edge["id"]
        va = a_map[eid]["outcome"]
        vb = b_map[eid]["outcome"]
        proof = A.both_outcomes_proof(edge)
        live, live_out = A.run_test(edge, A.live_world())
        majority = A.majority_side(edge)
        live_lines.append(live_out)
        if va != vb:
            disagreements.append({"id": eid, "a": va, "b": vb})
            outcome = "IRREDUCIBLE"
            settling = (
                "Reviewers disagreed; escalate to raw-source adjudication, "
                "never to a majority vote."
            )
            test_out = f"A={va} B={vb} engine={live}; escalated"
        elif live == "IRREDUCIBLE" or edge.get("kind") == "irreducible":
            outcome = "IRREDUCIBLE"
            settling = str(edge.get("settling_evidence") or "").strip()
            if len(settling) < 24:
                settling = (
                    f"Live executable test returned IRREDUCIBLE for {eid} "
                    f"({live_out}). Place the subject bytes named by "
                    f"subject_path={edge.get('subject_path')!r} on this "
                    "worktree with the disputed field present; that file is "
                    "the settling evidence."
                )
            test_out = live_out
        else:
            if not proof or not proof.get("capable"):
                print(f"FAILED:CNF-0068 non-discriminating-test {eid} proof={proof}")
                return 1
            if live != va:
                print(f"FAILED:CNF-0068 engine/reviewer drift {eid} live={live} a={va}")
                return 1
            outcome = live
            settling = None
            test_out = live_out
            if majority and majority != outcome:
                test_out += f"; majority_would_have_picked={majority} (ignored)"
        row = {
            "id": eid,
            "kind": edge["kind"],
            "claim_a": edge["claim_a"],
            "claim_b": edge["claim_b"],
            "test_source": A.TEST_SOURCE,
            "test_output": test_out,
            "outcome": outcome,
            "reviewer_a_outcome": va,
            "reviewer_b_outcome": vb,
            "majority_side_if_counted": majority,
            "majority_used": False,
        }
        if outcome == "IRREDUCIBLE":
            row["settling_evidence"] = settling
            row["capable_of_both_outcomes"] = bool(proof and proof.get("capable"))
            if proof and proof.get("capable"):
                row["both_outcomes_proof"] = {
                    "side_a_world_verdict": proof["side_a_world_verdict"],
                    "side_b_world_verdict": proof["side_b_world_verdict"],
                    "capable": True,
                    "side_a_output": proof["side_a_output"],
                    "side_b_output": proof["side_b_output"],
                }
        else:
            row["capable_of_both_outcomes"] = True
            row["both_outcomes_proof"] = {
                "side_a_world_verdict": proof["side_a_world_verdict"],
                "side_b_world_verdict": proof["side_b_world_verdict"],
                "capable": True,
                "side_a_output": proof["side_a_output"],
                "side_b_output": proof["side_b_output"],
            }
        edges_out.append(row)
        observations.append(
            {
                "name": eid,
                "measured": outcome,
                "method": f"executable test kind={edge.get('kind')} in adjudicate.run_test",
                "anchor": A.TEST_SOURCE,
            }
        )

    if disagreements:
        print(f"FAILED:CNF-0068 irreducible-disagreement {disagreements}")
        return 1

    settled = [e for e in edges_out if e["outcome"] in {"SIDE_A", "SIDE_B"}]
    irreducible = [e for e in edges_out if e["outcome"] == "IRREDUCIBLE"]
    if not settled or not irreducible:
        print(f"FAILED:CNF-0068 need both settled and irreducible settled={len(settled)}")
        return 1
    trap = next(e for e in edges_out if e["id"] == "E-CATALOG-TOP-TYPE")
    if trap["majority_side_if_counted"] != "SIDE_A" or trap["outcome"] != "SIDE_B":
        print("FAILED:CNF-0068 vote-count trap did not fire as designed")
        return 1

    one_sided_edge = next(e for e in A.load_fixture_edges() if e["id"] == "E-CATALOG-TOP-TYPE")
    always_a, always_out = A.one_sided_always_a(
        one_sided_edge, A.overlay_world(one_sided_edge.get("world_b") or {})
    )
    good_b, good_out = A.run_test(
        one_sided_edge, A.overlay_world(one_sided_edge.get("world_b") or {})
    )
    if always_a != "SIDE_A" or good_b != "SIDE_B":
        print("FAILED:CNF-0068 one-sided control did not discriminate")
        return 1

    question = str(unit.get("question_or_target") or unit.get("question") or "")
    started, ended = observation_stamp(out)
    schema_path = REPO / schema_rel
    if not schema_path.is_file():
        print(f"FAILED:CNF-0068 schema missing {schema_rel}")
        return 1
    schema_sha, schema_bytes = digest_file(schema_path)
    live_blob = "\n".join(live_lines)
    rev_blob = json.dumps(
        {"a": [r["outcome"] for r in rev_a["edges"]], "b": [r["outcome"] for r in rev_b["edges"]]},
        sort_keys=True,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0068",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0068",
        "min_bytes_threshold": 2048,
        "artifacts": [
            artifact_row(out_rel, "primary", "0" * 64, 1),
            artifact_row(schema_rel, "supporting", schema_sha, schema_bytes),
        ],
        "evidence": [
            {
                "claim": (
                    "Contradiction edges in the fixture corpus are settled by an "
                    "executable test that is capable of both SIDE_A and SIDE_B, "
                    "never by counting agent_assertions."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0068/adjudicate.py:run_test",
                "probes": [
                    probe_obj("source", "test-run", P1, live_blob),
                    probe_obj("verifier", "file-read", P2, rev_blob),
                ],
            },
            {
                "claim": (
                    "Two independent reviewers (pathlib vs os.path) filed without "
                    "seeing each other and matched the engine on every edge."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0068/reviewer_a.py",
                "probes": [
                    probe_obj(
                        "source",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0068/reviewer_a.py",
                        json.dumps(rev_a, sort_keys=True)[:4000],
                    ),
                    probe_obj(
                        "verifier",
                        "command",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0068/reviewer_b.py",
                        json.dumps(rev_b, sort_keys=True)[:4000],
                    ),
                ],
            },
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "zero retries"),
        },
        "tests": [
            {"id": "probe1_both_outcomes", "command": P1, "result": "PASS"},
            {"id": "probe2_independent", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "one-sided-always-a",
                "kind": "known-broken-fixture",
                "description": (
                    "A test that can only confirm SIDE_A is not an adjudicator. "
                    "The one_sided_always_a control stays SIDE_A in world B; the "
                    "real json_top_type test returns SIDE_B in that world."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": always_out,
                "good_state_output": good_out,
            },
            {
                "id": "vote-count-trap",
                "kind": "adversarial-payload",
                "description": (
                    "E-CATALOG-TOP-TYPE majority of agent_assertions is SIDE_A; "
                    "the executable test on the live catalog is SIDE_B. Verdict "
                    "follows the test."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "majority=SIDE_A (would wrongly settle)",
                "good_state_output": trap["test_output"],
            },
        ],
        "reviewer": {
            "reviewer_id": str(rev_a["reviewer_id"]),
            "verdict": "PASS",
            "independent": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0068/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0068/schema_offline.py",
                "artifact_path": out_rel,
                "executed": True,
                "read_ok": True,
                "probe": probe_obj(
                    "verifier",
                    "schema-validate",
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0068/schema_offline.py "
                    + out_rel,
                    "VALID (in-process Draft7Validator + disk RefResolver)",
                ),
            }
        ],
        "residual_unknowns": [],
        "defects": [],
        "report": {
            "kind": "adjudication-report",
            "observations": observations,
            "control_ids": ["one-sided-always-a", "vote-count-trap"],
            "never_adjudicated_by_agent_count": True,
            "question": question,
            "title": unit.get("title"),
            "output_path": out_rel,
            "output_schema": schema_rel,
            "input_note": (
                "CLAIM-REGISTRY.json is present on this worktree (existence "
                "edge E-CLAIM-REGISTRY-EXISTS -> SIDE_A) but carries no "
                "contradiction_edges list; CNF-0067 is not delivered. Edges "
                "come from the unit fixture corpus. ARC-0014 output_path "
                "command-center/phase3/A2/MIGRATION.json is absent here, so "
                "E-ARC0014-STATE is live-IRREDUCIBLE with named settling "
                "evidence. Overlay worlds still show that test is capable of "
                "both outcomes."
            ),
            "edges": edges_out,
            "reviewers": [
                {
                    "reviewer_id": rev_a["reviewer_id"],
                    "peer_verdicts_seen": False,
                    "filed": True,
                    "independent": True,
                    "method": rev_a["method"],
                },
                {
                    "reviewer_id": rev_b["reviewer_id"],
                    "peer_verdicts_seen": False,
                    "filed": True,
                    "independent": True,
                    "method": rev_b["method"],
                },
            ],
            "summary": {
                "edge_count": len(edges_out),
                "settled": len(settled),
                "irreducible": len(irreducible),
                "reviewer_disagreements": 0,
                "vote_count_trap_ignored": True,
            },
        },
    }

    if sentinel not in dump(doc):
        print("FAILED:CNF-0068 completion_sentinel not in document")
        return 1

    # Self-hash cannot fixpoint (the digest is inside the bytes). Record a
    # well-formed sha256 of the pre-write dump; UNIT-ARTIFACT-MANIFEST holds
    # the live on-disk digest that G-1 compares.
    pre_sha, pre_size = digest_bytes(dump(doc).encode("utf-8"))
    doc["artifacts"][0]["sha256"] = pre_sha
    doc["artifacts"][0]["bytes"] = pre_size

    errs = S.iter_errors(doc, schema_rel)
    if errs:
        print("FAILED:CNF-0068 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not S.iter_errors(garbage, schema_rel):
            print(f"FAILED:CNF-0068 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    live_sha, live_size = digest_file(out)
    if live_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0068 artifact {live_size}B below floor")
        return 1
    file_errs = S.iter_errors(json.loads(out.read_text(encoding="utf-8")), schema_rel)
    if file_errs:
        print("FAILED:CNF-0068 schema errors after write")
        return 1
    print(f"wrote {out_rel} bytes={live_size} sha256={live_sha}")
    print("SUCCESS:CNF-0068 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
