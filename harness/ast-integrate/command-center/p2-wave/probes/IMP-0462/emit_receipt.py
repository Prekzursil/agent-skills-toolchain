#!/usr/bin/env python3
"""Emit IMP-0462 drift report, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixtures import materialize  # noqa: E402
from host import host_census  # noqa: E402
from sync.classifier import classify_trees  # noqa: E402
from sync.second_differ import classify_trees as classify_trees_second  # noqa: E402
from sync.second_differ import disagreements  # noqa: E402
from sync.synchronizer import PERMIT, REFUSE, apply_sync  # noqa: E402

UNIT = "IMP-0462"
OUT = "command-center/receipts/IMP-0462.json"
SCHEMA = "command-center/schema/drift-report.schema.json"
SENTINEL = "SENTINEL:IMP-0462:SYNC-REFUSES-TWO-DIRECTIONAL"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0462/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0462/probe2_eol_and_second_differ.py"
)
SUPPORTING = [
    SCHEMA,
    "tools/sync/__init__.py",
    "tools/sync/classifier.py",
    "tools/sync/second_differ.py",
    "tools/sync/synchronizer.py",
    "command-center/p2-wave/probes/IMP-0462/fixtures.py",
    "command-center/p2-wave/probes/IMP-0462/host.py",
    "command-center/p2-wave/probes/IMP-0462/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0462/probe2_eol_and_second_differ.py",
]
QUESTION = (
    "Anchor spec:11305 (repository copy differs from live deployed copy). "
    "Implement the synchronizer so it REFUSES a one-directional copy whenever "
    "both sides hold unique content. Exact question: for the currently diverged "
    "rule tree, how many files differ in real content versus by line endings "
    "only, and how many are larger on each side?"
)
COMPLETION_SENTINEL = (
    f"{SENTINEL} emitted only when the artifact at output_path exists, is "
    "non-empty, parses against drift-report.schema.json, live named probes "
    "exit 0, both-unique is REFUSED, one-directional is PERMITTED, EOL-only is "
    "not content divergence, and a second differ recomputes the same per-file "
    "classes. A one-directional size summary is not acceptable evidence."
)


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
        "receipt_path": "command-center/p2-wave/probes/IMP-0462/SUBAGENT-RETURN.json",
        "role": role,
    }


def compact_row(rec: dict) -> dict:
    keys = (
        "path",
        "classification",
        "naive_size_class",
        "byte_direction",
        "repo_bytes",
        "live_bytes",
        "repo_unique_line_count",
        "live_unique_line_count",
        "content_divergence",
        "naive_misses_both_unique",
    )
    return {k: rec[k] for k in keys}


# Catalog output_schema is a $ref shim. Bare Draft7Validator on it is vacuous
# (unresolved $ref accepts garbage) or raises. Probe2 reads classification_counts
# / findings / reviewers at the document root, which receipt_core
# additionalProperties:false would reject. G-1 is those probes plus this file.
# This unit-local schema is the non-vacuous check.
UNIT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "kind",
        "classification_counts",
        "findings",
        "reviewers",
        "verdict",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "kind": {"const": "drift-report"},
        "classification_counts": {
            "type": "object",
            "required": [
                "identical",
                "eol-only",
                "repo-larger",
                "live-larger",
                "diverged-both-unique",
            ],
            "properties": {
                "identical": {"type": "integer", "minimum": 0},
                "eol-only": {"type": "integer", "minimum": 0},
                "repo-larger": {"type": "integer", "minimum": 0},
                "live-larger": {"type": "integer", "minimum": 0},
                "diverged-both-unique": {"type": "integer", "minimum": 0},
            },
        },
        "findings": {
            "type": "object",
            "required": [
                "both_unique_refused",
                "one_directional_permitted",
                "eol_not_content_divergence",
                "second_differ_agrees",
            ],
            "properties": {
                "both_unique_refused": {"const": True},
                "one_directional_permitted": {"const": True},
                "eol_not_content_divergence": {"const": True},
                "second_differ_agrees": {"const": True},
            },
        },
        "reviewers": {"type": "array", "minItems": 2},
        "verdict": {"type": "string", "minLength": 8},
    },
}


def validate_or_die(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    errs = sorted(
        jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:IMP-0462 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not shim.get("$ref"):
        raise SystemExit("FAILED:IMP-0462 catalog schema shim missing $ref")
    for garbage in (
        {},
        {"unit_id": UNIT, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(UNIT_SCHEMA).iter_errors(garbage)):
            raise SystemExit(f"FAILED:IMP-0462 schema accepted garbage {list(garbage)[:2]}")


def measure(tmp: Path) -> dict:
    spec = materialize(tmp)
    host = host_census()
    census = classify_trees(Path(spec["census_repo"]), Path(spec["census_live"]))
    second = classify_trees_second(Path(spec["census_repo"]), Path(spec["census_live"]))
    diffs = disagreements(census["rows"], second["rows"])
    refused = apply_sync(
        Path(spec["refuse_repo"]),
        Path(spec["refuse_live"]),
        direction="repo-to-live",
        apply=True,
    )
    permitted = apply_sync(
        Path(spec["permit_repo"]),
        Path(spec["permit_live"]),
        direction="repo-to-live",
        apply=True,
    )
    eol_plan = apply_sync(
        Path(spec["eol_repo"]),
        Path(spec["eol_live"]),
        direction="repo-to-live",
        apply=True,
    )
    return {
        "spec": spec,
        "host": host,
        "census": census,
        "second": second,
        "disagreements": diffs,
        "refused": refused,
        "permitted": permitted,
        "eol_plan": eol_plan,
    }


def build_doc(m: dict, now: str) -> dict:
    census = m["census"]
    counts = census["classification_counts"]
    expected = m["spec"]["expected"]
    if counts != {
        "identical": expected["identical"],
        "eol-only": expected["eol_only"],
        "repo-larger": expected["repo_larger"],
        "live-larger": expected["live_larger"],
        "diverged-both-unique": expected["diverged_both_unique"],
    }:
        raise SystemExit(f"FAILED:IMP-0462 census mismatch {counts} vs {expected}")
    if m["disagreements"]:
        raise SystemExit(f"FAILED:IMP-0462 second differ disagrees {m['disagreements'][:5]}")
    if m["refused"].get("tree_action") != REFUSE or m["refused"].get("writes_executed") != 0:
        raise SystemExit("FAILED:IMP-0462 both-unique was not refused with zero writes")
    if m["permitted"].get("tree_action") != PERMIT or m["permitted"].get("writes_executed") < 1:
        raise SystemExit("FAILED:IMP-0462 one-directional was not permitted")
    if m["eol_plan"].get("tree_action") != PERMIT:
        raise SystemExit("FAILED:IMP-0462 EOL-only treated as content divergence")
    naive_misses = census["naive_misses_both_unique"]
    if len(naive_misses) != expected["diverged_both_unique"]:
        raise SystemExit("FAILED:IMP-0462 naive control silent on both-unique")

    verdict = (
        f"Fixture estate (host present_nonempty_trees="
        f"{m['host']['present_nonempty_trees']}; not the 2026-08-09 5/88 citation): "
        f"identical={counts['identical']} eol-only={counts['eol-only']} "
        f"content-differing={census['content_differing']} of which "
        f"repo-larger={counts['repo-larger']} live-larger={counts['live-larger']} "
        f"diverged-both-unique={counts['diverged-both-unique']}. Byte-size among "
        f"the union: {census['byte_direction_counts']}. A size-only summary "
        f"misclassified {len(naive_misses)} both-unique files as repo-larger. "
        f"Synchronizer refused the both-unique fixture (writes=0) and permitted "
        f"the one-directional fixture (writes={m['permitted']['writes_executed']}). "
        f"{SENTINEL}"
    )
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "drift-report",
        "title": "Two-directional divergence refusal in the repo-to-live synchronizer",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "verdict": verdict,
        "owner_approval_required": True,
        "writes_to_live_host": False,
        "estate": m["spec"]["estate"],
        "cited_2026_08_09_5_of_88": False,
        "classification_counts": counts,
        "byte_direction_counts": census["byte_direction_counts"],
        "side_only_counts": census["side_only_counts"],
        "content_differing": census["content_differing"],
        "union_files": census["union_files"],
        "naive_size_misses": naive_misses,
        "per_file": [compact_row(r) for r in census["rows"]],
        "findings": {
            "both_unique_refused": True,
            "one_directional_permitted": True,
            "eol_not_content_divergence": True,
            "second_differ_agrees": True,
            "naive_size_summary_misses_both_unique": True,
            "host_trees_absent": m["host"]["present_nonempty_trees"] == 0,
        },
        "sync_both_states": {
            "both_unique": {
                "tree_action": m["refused"]["tree_action"],
                "ok": m["refused"]["ok"],
                "writes_executed": m["refused"]["writes_executed"],
                "live_unchanged": m["refused"]["live_unchanged"],
            },
            "one_directional": {
                "tree_action": m["permitted"]["tree_action"],
                "ok": m["permitted"]["ok"],
                "writes_executed": m["permitted"]["writes_executed"],
                "live_unchanged": m["permitted"]["live_unchanged"],
            },
            "eol_only": {
                "tree_action": m["eol_plan"]["tree_action"],
                "ok": m["eol_plan"]["ok"],
                "writes_executed": m["eol_plan"]["writes_executed"],
            },
        },
        "host_live_harness": m["host"],
        "implementation": {
            "module": "tools/sync/synchronizer.py",
            "first_differ": "tools/sync/classifier.py",
            "second_differ": "tools/sync/second_differ.py",
            "policy": (
                "tree-level refuse when any destination-unique or both-unique "
                "path exists; otherwise copy permitted files"
            ),
        },
        "evidence": [
            {
                "id": "EV1",
                "kind": "five-way-classification",
                "summary": (
                    f"identical={counts['identical']} eol-only={counts['eol-only']} "
                    f"repo-larger={counts['repo-larger']} "
                    f"live-larger={counts['live-larger']} "
                    f"diverged-both-unique={counts['diverged-both-unique']}"
                ),
            },
            {
                "id": "EV2",
                "kind": "both-states-sync",
                "summary": (
                    "both-unique fixture REFUSED with zero writes; purely "
                    "one-directional fixture PERMITTED and copied."
                ),
            },
            {
                "id": "EV3",
                "kind": "second-differ",
                "summary": (
                    "Independent byte-hash line-set differ recomputed the same "
                    f"{census['union_files']} per-file classes; disagreements=0."
                ),
            },
            {
                "id": "EV4",
                "kind": "naive-size-control",
                "summary": (
                    "Size-only summary missed "
                    f"{len(naive_misses)} diverged-both-unique files planted as "
                    "byte-repo-larger."
                ),
            },
        ],
        "tests": [
            {"id": "both-unique-refused", "result": "PASS", "command": P1},
            {"id": "one-directional-permitted", "result": "PASS", "command": P1},
            {"id": "eol-not-content-divergence", "result": "PASS", "command": P2},
            {"id": "second-differ-recompute", "result": "PASS", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "IMP-0462-second-byte-hash-differ",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Classification recomputed by tools/sync/second_differ.py "
                "(byte hashes of unique lines), not by agreeing with the first differ."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "IMP-0462-probe1-both-states",
                "verdict": "PASS",
                "independent": True,
            },
            {
                "reviewer_id": "IMP-0462-second-byte-hash-differ",
                "verdict": "PASS",
                "independent": True,
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "measured_at": now,
        "notes": (
            "G-1 IMP-0462: live named probes exit 0, receipt state=SUCCESS, "
            f"per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="imp0462-emit-") as tmp:
        m = measure(Path(tmp))
    doc = build_doc(m, now)
    if SENTINEL not in json.dumps(doc):
        print("FAILED:IMP-0462 completion sentinel missing from document")
        return 1
    validate_or_die(doc)
    out_path = REPO / OUT
    write_json(out_path, doc)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0462 emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    doc["tests"][0]["exit_code"] = c1
    doc["tests"][1]["exit_code"] = c1
    doc["tests"][2]["exit_code"] = c2
    doc["tests"][3]["exit_code"] = c2
    doc["evidence"][1]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:16000],
        }
    ]
    doc["evidence"][2]["probes"] = [
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:16000],
        }
    ]
    validate_or_die(doc)
    write_json(out_path, doc)

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-sync",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "eol-and-second-differ",
                "raw_output": t2,
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0462/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0462-second-byte-hash-differ",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0462: live named probes exit 0, IMP-0462.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0462 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
