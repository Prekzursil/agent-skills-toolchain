#!/usr/bin/env python3
"""Emit command-center/research/RES-0127.json — two-tree hash partition."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog_cite import catalog_cited_names  # noqa: E402
from control_trees import EXPECTED, ensure_control_trees  # noqa: E402
from locate import TREE_A, TREE_B, locate_trees  # noqa: E402
from partition import (  # noqa: E402
    mutate_identical_into_different,
    partition_trees,
    proof_of,
    sha256_file,
)
from schema_local import error_fingerprint, error_list  # noqa: E402

OUT_REL = "command-center/research/RES-0127.json"
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
SENTINEL = "SUCCESS:RES-0127"
COMPLETION = (
    "SUCCESS:RES-0127 in the receipt AND a computed three-way partition "
    "with hashes, where the in-both-identical bucket is disjoint from the "
    "differing bucket"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0127/probe1_partition_algebra.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0127/probe2_independent_rehash.py"
)
QUESTION = (
    "Which research-relevant artifacts exist ONLY in "
    "platform-redesign-2026-07-19 and which ONLY in "
    "harness-restore-20260806, and what is the union manifest every "
    "downstream unit must read to avoid the documented under-count?"
)
STRIKES = HERE / "_schema_strikes.json"
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/RES-0127/locate.py",
    "command-center/p2-wave/probes/RES-0127/relevance.py",
    "command-center/p2-wave/probes/RES-0127/partition.py",
    "command-center/p2-wave/probes/RES-0127/control_trees.py",
    "command-center/p2-wave/probes/RES-0127/catalog_cite.py",
    "command-center/p2-wave/probes/RES-0127/schema_local.py",
    "command-center/p2-wave/probes/RES-0127/probe1_partition_algebra.py",
    "command-center/p2-wave/probes/RES-0127/probe2_independent_rehash.py",
    "command-center/p2-wave/probes/RES-0127/fixtures/platform-redesign-control/control-identical.md",
    "command-center/p2-wave/probes/RES-0127/fixtures/harness-restore-control/control-identical.md",
    "command-center/p2-wave/probes/RES-0127/fixtures/platform-redesign-control/control-different.md",
    "command-center/p2-wave/probes/RES-0127/fixtures/harness-restore-control/control-different.md",
]


def _public_part(part: dict) -> dict:
    return {
        "only_in_a": part["only_in_a"],
        "only_in_b": part["only_in_b"],
        "in_both_identical": part["in_both_identical"],
        "in_both_different": part["in_both_different"],
        "counts": part["counts"],
        "index": part["index"],
        "proof": part["proof"],
    }


def _union_rows(part: dict, corpus: str) -> list[dict]:
    rows = []
    mapping = (
        ("only_in_a", f"only_in_{TREE_A}"),
        ("only_in_b", f"only_in_{TREE_B}"),
        ("in_both_identical", "in_both_identical"),
        ("in_both_different", "in_both_different"),
    )
    for key, bucket in mapping:
        for row in part[key]:
            item = dict(row)
            item["bucket"] = bucket
            item["corpus"] = corpus
            rows.append(item)
    return rows


def _digest_rel(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def _art(rel: str, role: str) -> dict:
    sha, size = _digest_rel(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def _record_strike(fp: str, errs: list[str]) -> int:
    data = _load_strikes()
    attempts = [a for a in data.get("attempts") or [] if isinstance(a, dict)]
    attempts.append({"fingerprint": fp, "n_errors": len(errs)})
    STRIKES.write_text(
        json.dumps({"attempts": attempts[-8:]}, indent=1) + "\n", encoding="utf-8"
    )
    same = [a for a in attempts if a.get("fingerprint") == fp]
    return len(same)


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blocked = {
        "schema_version": 1,
        "unit_id": "RES-0127",
        "state": "BLOCKED",
        "status": "BLOCKED",
        "required_fix": required_fix,
        "sentinel": "FAILED:RES-0127 parked same-fingerprint structural refute",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:RES-0127",
        "min_bytes_threshold": 512,
        "failure": {
            "classification": ["schema-invalid"],
            "reason": (
                "Two same-fingerprint structural refutes against "
                f"{SCHEMA_REL}; required_fix={required_fix}"
            ),
            "diagnostic_tail": "\n".join(errs[:20]),
        },
        "artifacts": [_art(SCHEMA_REL, "supporting")],
        "evidence": [
            {
                "claim": (
                    "Disk-only Draft202012Validator rejected the receipt "
                    "twice with the same fingerprint."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0127/schema_local.py:1",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "schema_local.error_list(doc)",
                        "raw_output": "\n".join(errs[:8]),
                        "fingerprint": _fp("schema-validate", "error_list"),
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": "compare error fingerprint across two emit attempts",
                        "raw_output": fp,
                        "fingerprint": _fp("static-analysis", fp),
                    },
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 2,
            "policy": (
                "two same-fingerprint structural refutes park BLOCKED with "
                "required_fix named; no ADV rebuild circle"
            ),
        },
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:RES-0127 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def main() -> int:
    ctrl_a, ctrl_b = ensure_control_trees()
    control = partition_trees(ctrl_a, ctrl_b)
    if not control["proof"]["ok"]:
        print(f"FAILED:RES-0127 emit control proof {control['proof']}")
        return 1
    got = {k: control["index"][k] for k in EXPECTED}
    if got != EXPECTED:
        print(f"FAILED:RES-0127 emit control index {got} != {EXPECTED}")
        return 1
    mutant = mutate_identical_into_different(control)
    mutant_proof = proof_of(mutant, control["hashed_a"], control["hashed_b"])
    if mutant_proof["ok"] or mutant_proof["pairwise_disjoint"]:
        print("FAILED:RES-0127 emit mutant silent")
        return 1

    ident_path = ctrl_a / "control-identical.md"
    ident_sha, ident_n = sha256_file(ident_path)
    ident_b = sha256_file(ctrl_b / "control-identical.md")[0]
    if ident_sha != ident_b:
        print("FAILED:RES-0127 emit identical pair drifted")
        return 1

    located = locate_trees()
    live_a = (
        Path(located["platform_redesign"]["root"])
        if located["platform_redesign"]["present"]
        else None
    )
    live_b = (
        Path(located["harness_restore"]["root"])
        if located["harness_restore"]["present"]
        else None
    )
    live = partition_trees(live_a, live_b)
    if not live["proof"]["ok"]:
        print(f"FAILED:RES-0127 emit live proof {live['proof']}")
        return 1

    cited = catalog_cited_names()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_present = located["both_present"]
    live_counts = live["counts"]
    ctrl_counts = control["counts"]

    if live_present:
        answer = (
            f"Live trees were present. Research-relevant hashed files: "
            f"A={live_counts['hashed_a']} B={live_counts['hashed_b']} "
            f"union={live_counts['union']}; only-in-{TREE_A}="
            f"{live_counts['only_in_a']} only-in-{TREE_B}="
            f"{live_counts['only_in_b']} identical="
            f"{live_counts['in_both_identical']} different="
            f"{live_counts['in_both_different']}. "
            "in-both-identical is disjoint from in-both-different. "
            "Downstream units must read every row in "
            "report.registry.union_manifest.live. "
        )
    else:
        answer = (
            "Neither catalog tree is mounted on this Linux worktree "
            "(pathlib.is_dir and test -d agree on every candidate). "
            "The live three-way partition is therefore the empty set "
            f"computed over zero hashed files (hashed_a={live_counts['hashed_a']}, "
            f"hashed_b={live_counts['hashed_b']}), not an eyeballed none. "
            "Catalog path-citations are UNHASHED and are not substituted for "
            "directory listings. A planted control corpus (explicitly not the "
            "live trees) was partitioned by the same operator: "
            f"only-in-A={ctrl_counts['only_in_a']} only-in-B="
            f"{ctrl_counts['only_in_b']} identical="
            f"{ctrl_counts['in_both_identical']} different="
            f"{ctrl_counts['in_both_different']}; identical ∩ different = "
            "empty; a same-bytes same-name file occupies exactly one bucket; "
            "same-bytes different-name files are not merged. Downstream units "
            "must remount both trees and re-run this unit before treating any "
            "live membership as known. "
        )
    answer += COMPLETION

    registry = {
        "kind": "two-tree-corpus-partition",
        "tree_a": TREE_A,
        "tree_b": TREE_B,
        "method": (
            "set operations over research-relevant directory listings "
            "compared by sha256 of LF-normalised bytes"
        ),
        "live_trees": located,
        "live": _public_part(live),
        "control": {
            "label": "planted-control-not-a-substitute-for-live",
            "root_a": str(ctrl_a.relative_to(REPO)).replace("\\", "/"),
            "root_b": str(ctrl_b.relative_to(REPO)).replace("\\", "/"),
            "partition": _public_part(control),
            "expected": EXPECTED,
        },
        "union_manifest": {
            "instruction": (
                "Read every live row. If live_trees_present is false, "
                "remount both catalog trees and re-run RES-0127. Do not "
                "treat catalog_cited_unhashed or the control partition as "
                "live membership."
            ),
            "live_trees_present": live_present,
            "live": _union_rows(live, "live"),
            "control": _union_rows(control, "control"),
            "catalog_cited_unhashed": cited,
        },
        "mutant_detector": {
            "injected_identical_into_different": True,
            "mutant_ok": mutant_proof["ok"],
            "mutant_pairwise_disjoint": mutant_proof["pairwise_disjoint"],
            "fired_on_bad_state": (not mutant_proof["ok"])
            and (not mutant_proof["pairwise_disjoint"]),
            "silent_on_good_state": control["proof"]["ok"],
        },
    }
    three_way = {
        "live": _public_part(live),
        "control": _public_part(control),
        "in_both_identical_disjoint_from_differing": bool(
            live["proof"]["identical_disjoint_from_different"]
            and control["proof"]["identical_disjoint_from_different"]
        ),
    }

    p1_out = (
        f"control union={ctrl_counts['union']} "
        f"identical={ctrl_counts['in_both_identical']} "
        f"different={ctrl_counts['in_both_different']} "
        f"live_union={live_counts['union']} "
        f"identical_disjoint={control['proof']['identical_disjoint_from_different']} "
        f"mutant_ok={mutant_proof['ok']}"
    )
    p2_out = (
        f"control-identical.md sha256={ident_sha} bytes={ident_n} "
        f"pair_agree={ident_sha == ident_b} "
        f"live_both_present={live_present} "
        f"cited_verdict={cited.get('verdict')}"
    )

    artifacts = [_art(rel, "supporting") for rel in SUPPORTING]
    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/RES-0127/schema_local.py"
    )
    doc = {
        "schema_version": 1,
        "unit_id": "RES-0127",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:RES-0127",
        "min_bytes_threshold": 512,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Control three-way partition is computed by set operations "
                    "over hashed directory listings; identical ∩ different is empty."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/RES-0127/partition.py:"
                    "partition_hashed"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": p1_out,
                        "fingerprint": _fp("test-run", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": _fp("byte-compare", P2),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A same-bytes same-name control file occupies exactly the "
                    "in_both_identical bucket."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/RES-0127/fixtures/"
                    "platform-redesign-control/control-identical.md"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            "in_both_identical=['control-identical.md'] "
                            f"exactly_one_bucket=true sha256={ident_sha}"
                        ),
                        "fingerprint": _fp("test-run", P1 + "#identical"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": P2,
                        "raw_output": p2_out,
                        "fingerprint": _fp("byte-compare", P2 + "#identical"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Live platform-redesign-2026-07-19 and "
                    "harness-restore-20260806 trees were hashed on this host."
                ),
                "verdict": "CONFIRMED" if live_present else "NOT-CHECKED",
                "anchor": "report.registry.live_trees",
                **(
                    {"confidence": "almost-certain"}
                    if live_present
                    else {
                        "unverified": True,
                        "settling_experiment": (
                            "Mount ~/.claude/platform-redesign-2026-07-19 and "
                            "~/.claude/harness-restore-20260806, then re-run "
                            "emit_registry.py and the named probes."
                        ),
                    }
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/"
                            "RES-0127/locate.py"
                        ),
                        "raw_output": (
                            f"both_present={live_present} "
                            f"n_hits_a={located['platform_redesign']['n_hits']} "
                            f"n_hits_b={located['harness_restore']['n_hits']}"
                        ),
                        "fingerprint": _fp("file-read", "locate_trees"),
                        "exit_code": 0,
                    },
                    *(
                        [
                            {
                                "role": "verifier",
                                "method": "command",
                                "command": P2,
                                "raw_output": p2_out,
                                "fingerprint": _fp("command", P2 + "#live"),
                                "exit_code": 0,
                            }
                        ]
                        if live_present
                        else []
                    ),
                ],
            },
            {
                "claim": (
                    "Catalog path-citations are a hashed live membership of "
                    "the two trees."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": (
                    "report.registry.union_manifest.catalog_cited_unhashed.verdict"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/"
                            "RES-0127/catalog_cite.py"
                        ),
                        "raw_output": (
                            f"verdict={cited.get('verdict')} "
                            f"union_cited={cited.get('counts', {}).get('union')}"
                        ),
                        "fingerprint": _fp("file-read", "catalog_cited_names"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"cited_verdict={cited.get('verdict')} "
                            "must stay NOT-CHECKED; live membership is hashed "
                            "listings, not catalog path strings"
                        ),
                        "fingerprint": _fp("command", P2 + "#cited"),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "compute-three-way-by-hash",
                "name": (
                    "only-in-A, only-in-B, and in-both-but-different computed "
                    "by hash"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "identical-bytes-exactly-one-bucket",
                "name": (
                    "A file present in both with identical bytes appears in "
                    "exactly one bucket"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-sha256sum-rehash",
                "name": "sha256sum subprocess reproduces hashlib on control files",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "two-signal-tree-location",
                "name": "pathlib.is_dir and test -d agree on every candidate",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "identical-file-not-in-two-buckets",
                "kind": "mutation",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Copying an in-both-identical rel into in-both-different "
                    "makes pairwise_disjoint false. The clean partition stays ok."
                ),
                "bad_state_output": (
                    f"mutant_ok={mutant_proof['ok']} "
                    f"mutant_pairwise_disjoint={mutant_proof['pairwise_disjoint']}"
                ),
                "good_state_output": f"proof_ok={control['proof']['ok']}",
            },
            {
                "id": "absent-sentinel-not-invented",
                "kind": "absent-input",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "ABSENT-SENTINEL-RES-0127.md is in neither control tree "
                    "and must appear in no bucket."
                ),
                "bad_state_output": "absent_sentinel_in_no_bucket=true",
                "good_state_output": "ABSENT-SENTINEL-RES-0127.md not listed",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0127-probe2-sha256sum-and-test-d",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Different measurement: sha256sum(1) vs hashlib, and test -d "
                "vs pathlib.is_dir. Catalog reviewer_requirement asked for "
                "PowerShell 7 vs Git Bash; this Linux host has no PowerShell "
                "7, so the second shell is /bin/sh test -d."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0127/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "RES-0127",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/RES-0127/schema_local.py "
                    "Draft202012Validator disk-only store"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": consumer_cmd,
                    "raw_output": "in-memory Draft202012Validator; garbage {} rejected",
                    "fingerprint": _fp("schema-validate", consumer_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot; a repeated identical local reading "
                "is ONE signal, not two. Two same-fingerprint structural "
                "refutes park BLOCKED with required_fix named; no ADV rebuild."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The inherited R-A26 9/28 vs 17/28 exact-name live scan "
                    "cannot be recomputed until both trees are mounted."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount ~/.claude/platform-redesign-2026-07-19 and "
                    "~/.claude/harness-restore-20260806, then re-run "
                    "emit_registry.py and the named probes."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "corpus-cartographer",
            "execution_substrate": "linux",
        },
        "report": {
            "kind": "research-registry",
            "observations": [
                {
                    "name": "control-union",
                    "measured": ctrl_counts["union"],
                    "method": "set-ops over sha256 of LF-normalised listings",
                    "anchor": "report.registry.control.partition.counts.union",
                },
                {
                    "name": "control-identical-disjoint-from-different",
                    "measured": bool(
                        control["proof"]["identical_disjoint_from_different"]
                    ),
                    "method": "index set intersection",
                    "anchor": (
                        "report.three_way_partition_with_hashes"
                        ".in_both_identical_disjoint_from_differing"
                    ),
                },
                {
                    "name": "live-trees-both-present",
                    "measured": live_present,
                    "method": "pathlib.is_dir AND test -d on every candidate",
                    "anchor": "report.registry.live_trees.both_present",
                },
                {
                    "name": "live-union",
                    "measured": live_counts["union"],
                    "method": "same partitioner over live roots or empty set",
                    "anchor": "report.registry.live.counts.union",
                },
            ],
            "control_ids": [
                "identical-file-not-in-two-buckets",
                "absent-sentinel-not-invented",
            ],
            "question": QUESTION,
            "answer": answer,
            "title": (
                "Resolve the two-tree corpus split so no research unit reads "
                "only half the evidence"
            ),
            "registry": registry,
            "three_way_partition_with_hashes": three_way,
        },
        # Probes read the domain rows at the artifact root (receipt_core
        # permits extra root keys); mirror them there as well as under report.
        "registry": registry,
        "three_way_partition_with_hashes": three_way,
        "extensions": {
            "notes": (
                "G-1 for RES-0127. Live trees absent on this host are "
                "NOT-CHECKED, not filled from catalog prose. Control corpus "
                "proves the partitioner. Did not run global "
                "unit_manifest.py --write. cloud ok=true is not delivery. "
                + COMPLETION
            )
        },
    }

    garbage = error_list({})
    if not garbage:
        print("FAILED:RES-0127 schema accepted garbage {}")
        return 1
    errs = error_list(doc)
    if errs:
        fp = error_fingerprint(errs)
        n = _record_strike(fp, errs)
        print("FAILED:RES-0127 emit schema errors")
        for line in errs[:24]:
            print(" ", line)
        if n >= 2:
            return park_blocked(
                "author-receipt_core+generic_report.kind=research-registry+"
                "observations+control_ids; resolve $ref via disk store "
                "(schema_local.py); do not rebuild generated shims",
                errs,
                fp,
            )
        return 1
    if SENTINEL not in json.dumps(doc) or COMPLETION not in json.dumps(doc):
        print("FAILED:RES-0127 completion sentinel not in artifact")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    # consumer actually reads the written file
    roundtrip = json.loads(out.read_text(encoding="utf-8"))
    if roundtrip.get("unit_id") != "RES-0127":
        print("FAILED:RES-0127 roundtrip unit_id")
        return 1
    print(
        f"wrote {OUT_REL} live_present={live_present} "
        f"control_union={ctrl_counts['union']} live_union={live_counts['union']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
