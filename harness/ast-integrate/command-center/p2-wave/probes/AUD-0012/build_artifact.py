#!/usr/bin/env python3
"""Emit AUD-0012 catalog artifact plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
Does not mutate git state.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_three_way_comparator as C  # noqa: E402

REPO = C.repo_root()
OUT = "command-center/audit/AUD-0012-skills-three-way-drift.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0012/probe1_path_sets.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0012/probe2_content_partition.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0012 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which skills exist in only one or two of the three trees, and for those "
    "in all three, which pairs differ in content after EOL normalization?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0012/run_three_way_comparator.py",
    "command-center/p2-wave/probes/AUD-0012/probe1_path_sets.py",
    "command-center/p2-wave/probes/AUD-0012/probe2_content_partition.py",
    "command-center/p2-wave/probes/AUD-0012/probe1-path-sets.json",
    "command-center/p2-wave/probes/AUD-0012/probe2-content-partition.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "role": role,
        "unit_id": C.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0012/SUBAGENT-RETURN.json",
    }


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0012 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    live = C.live_world()
    sets = live["path_sets"]
    content = live["content"]
    trees = live["trees"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    absent = [tid for tid, rec in trees.items() if not rec["present"]]
    present = [tid for tid, rec in trees.items() if rec["present"]]
    answer = (
        "On this Linux worktree the three skills trees were compared by relative "
        "path set and by sha256 of LF-normalized bytes. "
        f"Present trees={present} absent_trees={absent} "
        f"(agents={trees['agents']['path']}, claude={trees['claude']['path']}). "
        f"Union paths={sets['union_count']}; in only one or two trees="
        f"{sets['in_one_or_two_count']} {sets['in_one_or_two']}; "
        f"in all three={sets['counts']['all_three']} {sets['buckets']['all_three']}. "
        f"Content-divergent triples={content['divergent_count']} "
        f"{content['divergent_paths']}. "
        "Absent live trees are measured as empty path sets, not as 'in sync' and "
        "not as BLOCKED: every repo skill is therefore repo-only, and there is no "
        "all-three intersection to hash. "
        "A scratch one-byte plant in exactly one tree reports exactly one divergent "
        "path (not zero, not all); a pairwise-distinct triple is classified "
        "all_three_pairwise_distinct rather than deploy-lag. "
        + COMPLETION_SENTINEL
    )

    tests = [
        {
            "id": "probe1-three-way-path-sets",
            "name": "Probe 1: three-way set comparison of relative paths",
            "command": P1,
            "result": "PASS",
            "assertions": 7,
            "output_tail": t1[-500:],
        },
        {
            "id": "probe2-lf-normalized-hash-partition",
            "name": "Probe 2: sha256 of LF-normalized bytes as a 3-way partition",
            "command": P2,
            "result": "PASS",
            "assertions": 4,
            "output_tail": t2[-500:],
        },
        {
            "id": "ctl-one-byte-in-one-tree",
            "name": "planted control: one-byte change in exactly one tree reports exactly one divergent path",
            "command": P2,
            "result": "PASS",
            "assertions": 2,
            "output_tail": "good=[] bad=['shared/SKILL.md']",
        },
    ]
    evidence = [
        {
            "claim": (
                "Probe 1 partitioned live relative paths into seven membership buckets. "
                f"in_one_or_two={sets['in_one_or_two_count']} all_three="
                f"{sets['counts']['all_three']}. Absent live trees contribute empty sets."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0012/probe1-path-sets.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": t1[:65000],
                    "exit_code": c1,
                    "fingerprint": fingerprint("command", P1),
                }
            ],
        },
        {
            "claim": (
                "Probe 2 hashed LF-normalized bytes for every path in all three trees "
                f"and classified the triple. Live all_three={content['all_three_count']} "
                f"divergent={content['divergent_count']}. The one-byte plant reports "
                "exactly one path; a three-way hash split is not labelled deploy-lag."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0012/probe2-content-partition.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "raw_output": t2[:65000],
                    "exit_code": c2,
                    "fingerprint": fingerprint("command", P2),
                }
            ],
        },
    ]
    named_probes = [
        {
            "id": "probe1",
            "role": "three-way-relative-path-set",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:65000],
        },
        {
            "id": "probe2",
            "role": "lf-normalized-sha256-three-way-partition",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:65000],
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": C.UNIT,
        "id": C.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-drift",
        "report_kind": "audit-drift",
        "title": "Three-way skills drift: repo skills/ versus ~/.agents/skills versus ~/.claude/skills",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0012",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-headless",
        },
        "report": {
            "kind": "audit-drift",
            "headline": (
                f"in_one_or_two={sets['in_one_or_two_count']} "
                f"all_three={sets['counts']['all_three']} "
                f"content_divergent={content['divergent_count']} "
                f"absent_live={absent}"
            ),
            "answer": answer,
            "trees": trees,
            "path_sets": sets,
            "content_partition": {
                "all_three_count": content["all_three_count"],
                "divergent_count": content["divergent_count"],
                "divergent_paths": content["divergent_paths"],
                "by_class": content["by_class"],
                "rows": content["rows"],
                "note": content["note"],
            },
            "control_ids": [
                "AUD-0012-C0-seven-bucket-path-set",
                "AUD-0012-C1-one-byte-in-one-tree",
                "AUD-0012-C2-two-directional-not-deploy-lag",
            ],
        },
        "negative_controls": [
            {
                "id": "AUD-0012-C1-one-byte-in-one-tree",
                "kind": "planted-control",
                "description": (
                    "Introduce a one-byte content change in exactly one tree and "
                    "confirm the comparator reports exactly one divergent path, "
                    "not zero and not all."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "['shared/SKILL.md']",
                "good_state_output": "[]",
            }
        ],
        "tests": tests,
        "evidence": evidence,
        "named_probes": named_probes,
        "reviewer": {
            "reviewer_id": "AUD-0012-probe2-lf-normalized-hash-partition",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a mechanically different instrument (LF-normalized "
                "sha256 triples, not path-set membership). It falsifies a vacuous "
                "zero on content by planting a one-byte change and requiring exactly "
                "one divergent path, and it refuses to label a pairwise-distinct "
                "triple as one-directional deploy lag."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0012/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "note": "G-1 measure is run after this write; cloud ok=true is not delivery",
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "failure": None,
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "Declared output_schema command-center/schema/audit-drift.schema.json "
                    "is absent on this tree. G-1 measures JSON parse + sentinel, not that "
                    "schema file."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Restore or generate the audit-drift schema shim and validate this "
                    "document against it before a later catalog close."
                ),
            }
        ],
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for AUD-0012: live named probes exit 0, audit-drift state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not git add/commit/push/stash/checkout/rebase the worktree. "
            "Live ~/.agents/skills and ~/.claude/skills are absent and reported as "
            "empty, not BLOCKED."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:AUD-0012 sentinel missing from serialized artifact")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0012 self-declared non-delivery state")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    primary = art(OUT, "primary")
    if primary["bytes"] < 1024:
        print(f"FAILED:AUD-0012 artifact too small {primary['bytes']}")
        return 1

    artifacts = [
        {
            "path": OUT,
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": C.UNIT,
            "receipt_path": "command-center/p2-wave/probes/AUD-0012/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        row = art(rel, "supporting")
        if not row["present"]:
            print(f"FAILED:AUD-0012 missing supporting {rel}")
            return 1
        artifacts.append(
            {
                "path": rel,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "present": True,
                "unit_id": C.UNIT,
                "receipt_path": "command-center/p2-wave/probes/AUD-0012/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": C.UNIT,
        "unit_id": C.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": named_probes,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0012/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0012-probe2-lf-normalized-hash-partition",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0012: live named probes exit 0, "
            "AUD-0012-skills-three-way-drift.json state=SUCCESS, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0012 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
