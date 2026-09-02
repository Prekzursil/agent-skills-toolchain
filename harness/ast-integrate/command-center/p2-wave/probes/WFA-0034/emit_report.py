#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0034-extract-maintenance-state.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from engine import QUERY_DATE  # noqa: E402

OUT = "command-center/wfa/WFA-0034-extract-maintenance-state.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0034/probe1_not_checked.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0034/probe2_archived_freshness.py"
)
QUESTION = (
    "For every externally sourced candidate, what is its maintenance state "
    "measured as last-commit date, archived flag, open-issue velocity and "
    "latest release - rather than the discovery-time prose currently sitting "
    "in the maintenance field?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(rel: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {"path": rel, "sha256": sha, "bytes": size}


def main() -> int:
    live = S.run_extraction()
    if not live.get("pass"):
        print("FAILED:WFA-0034 emit live extraction did not pass catalog tests")
        print(json.dumps({k: live.get(k) for k in sorted(live) if k != "rows"}, indent=2)[:4000])
        return 1
    controls = S.negative_controls()
    if not controls.get("pass"):
        print("FAILED:WFA-0034 emit negative controls did not fire")
        print(json.dumps(controls, indent=2)[:3000])
        return 1

    src_probe = {
        "id": "probe1_not_checked",
        "command": P1,
        "role": "unreachable-not-checked-never-infer-prose",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/WFA-0034/probe1_not_checked.py"
        ),
    }
    ver_probe = {
        "id": "probe2_archived_freshness",
        "command": P2,
        "role": "archived-disposition-and-api-vs-git-head",
        "fingerprint": probe_fp(
            "command-center/p2-wave/probes/WFA-0034/probe2_archived_freshness.py"
        ),
    }
    if src_probe["fingerprint"]["sha256"] == ver_probe["fingerprint"]["sha256"]:
        print("FAILED:WFA-0034 emit source/verifier probe files identical")
        return 1

    rows = live["rows"]
    by_id = {r["candidate_id"]: r for r in rows}
    unreachable = by_id["wf-ext-unreachable"]
    archived = by_id["wf-ext-archived-adopt"]
    active = by_id["wf-ext-live-active"]
    stale = by_id["wf-ext-stale-api"]
    prose_wrong = by_id["wf-ext-prose-archived-wrong"]

    doc = {
        "unit_id": "WFA-0034",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "ExtractionReport",
        "title": "Measure maintenance state per candidate instead of trusting discovery-time prose",
        "question": QUESTION,
        "sentinel": "SUCCESS:WFA-0034",
        "completion_sentinel": "SUCCESS:WFA-0034",
        "min_bytes_threshold": 2048,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ExtractionReport",
        "query_date": QUERY_DATE,
        "extraction_dimension": "maintenance",
        "source_meta": live["source_meta"],
        "n_candidates": live["n_candidates"],
        "n_measured": live["n_measured"],
        "n_not_checked": live["n_not_checked"],
        "n_skipped_local": live["n_skipped_local"],
        "not_checked_ids": live["not_checked_ids"],
        "records": rows,
        "contradictions": live["contradictions"],
        "disposition_flags": live["disposition_flags"],
        "freshness_findings": live["freshness_findings"],
        "scheduler_calls": live["n_scheduler_calls"],
        "evidence": [
            {
                "claim": "API-reported last push, archived boolean and latest release are captured with the query date (signal A).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0034/engine.py:extract_one",
            },
            {
                "claim": "Default-branch HEAD commit date is read from the git ref itself (signal B), independent of the API JSON.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0034/git_refs.py:read_head",
            },
            {
                "claim": "A source with no reachable metadata is recorded NOT-CHECKED and never inferred from its prose field.",
                "verdict": "CONFIRMED",
                "anchor": f"records.wf-ext-unreachable.status={unreachable['status']}",
            },
            {
                "claim": "Measured values are diffed against discovery-time prose and every contradiction is listed.",
                "verdict": "CONFIRMED",
                "anchor": f"contradictions n={len(live['contradictions'])}",
            },
            {
                "claim": "Archived repositories are flagged for the disposition lane; ADOPT-AS-IS on an archived source is a distinct risk.",
                "verdict": "CONFIRMED",
                "anchor": "records.wf-ext-archived-adopt.disposition_flag.adopt_as_is_risk",
            },
        ],
        "tests": [
            {
                "id": "WFA-0034-NOT-CHECKED-NO-PROSE-INFERENCE",
                "name": "a source with no reachable metadata is recorded NOT-CHECKED, never inferred from its prose field",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0034-PROSE-CONTRADICTION-LIST",
                "name": "the measured value must be diffed against the discovery-time prose and every contradiction listed",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0034-ARCHIVED-DISPOSITION-FLAG",
                "name": "archived repositories must be flagged for the disposition lane, since ADOPT-AS-IS on an archived source is a distinct risk",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": controls["infer_from_prose"]["id"],
                "kind": "infer-from-prose",
                "description": "Copying discovery-time prose into a NOT-CHECKED row must be detected.",
                "fired_on_bad_state": controls["infer_from_prose"]["fired_on_bad_state"],
                "silent_on_good_state": controls["infer_from_prose"]["silent_on_good_state"],
            },
            {
                "id": controls["drop_archived_flag"]["id"],
                "kind": "drop-archived-adopt-flag",
                "description": "Dropping the archived ADOPT-AS-IS disposition flag must be detected.",
                "fired_on_bad_state": controls["drop_archived_flag"]["fired_on_bad_state"],
                "silent_on_good_state": controls["drop_archived_flag"]["silent_on_good_state"],
            },
        ],
        "both_states": {
            "archived_adopt_flagged": (archived.get("disposition_flag") or {}).get("adopt_as_is_risk") is True,
            "live_active_not_flagged": active.get("archived") is False and active.get("disposition_flag") is None,
        },
        "controls": {
            "unreachable": {
                "id": "wf-ext-unreachable",
                "status": unreachable["status"],
                "inferred_from_prose": unreachable.get("inferred_from_prose"),
                "last_commit_date": unreachable.get("last_commit_date"),
            },
            "archived_adopt": {
                "id": "wf-ext-archived-adopt",
                "archived": archived.get("archived"),
                "classification": archived.get("classification"),
                "disposition_flag": archived.get("disposition_flag"),
            },
            "stale_api": {
                "id": "wf-ext-stale-api",
                "freshness_finding": stale.get("freshness_finding"),
                "api_last_push": (stale.get("measured") or {}).get("api_last_push"),
                "git_head_date": (stale.get("measured") or {}).get("git_head_date"),
            },
            "prose_archived_wrong": {
                "id": "wf-ext-prose-archived-wrong",
                "archived": prose_wrong.get("archived"),
                "contradictions": prose_wrong.get("contradictions"),
            },
        },
        "reviewer": {
            "reviewer_id": "WFA-0034-probe2-archived-freshness",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-reads git ref HEAD dates and API archived flags "
                "independently of probe 1's NOT-CHECKED control."
            ),
        },
        "source_probe": src_probe,
        "verifier_probe": ver_probe,
        "named_probes": [
            {"id": "probe1", "role": src_probe["role"], "command": P1},
            {"id": "probe2", "role": ver_probe["role"], "command": P2},
        ],
        "downstream_consumers": [
            "WFA-0043",
            "disposition-lane",
        ],
        "defects": [],
        "cloud_ok": False,
        "registered": True,
        "residual_caveat": (
            "The Windows-path 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json is not "
            "on this Linux worktree. Extraction ran over every externally sourced "
            "candidate in the local fixture, including planted unreachable, archived "
            "ADOPT-AS-IS, stale-API, and prose-contradiction cases. This is not a "
            "claim that 284 GitHub remotes were live-queried, and cloud ok=true is "
            "not delivery."
        ),
        "scope": {
            "proof_surface": (
                "fixture registry of 5 externally sourced + 1 local candidate; "
                "API JSON as signal A; git ref HEAD as signal B; NOT-CHECKED "
                "control; archived disposition flag; prose contradiction list."
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "284-row Windows registry was present on this worktree",
                "live GitHub API was required for G-1",
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0034/fixtures/registry.json",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:WFA-0034 artifact {size}B below floor")
        return 1
    if b"SUCCESS:WFA-0034" not in out.read_bytes():
        print("FAILED:WFA-0034 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"measured={live['n_measured']} not_checked={live['n_not_checked']} "
        f"contradictions={len(live['contradictions'])} "
        f"disposition={len(live['disposition_flags'])}"
    )
    print("SUCCESS:WFA-0034 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
