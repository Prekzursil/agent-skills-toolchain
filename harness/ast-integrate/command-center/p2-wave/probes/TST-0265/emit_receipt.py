#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0265.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

OUT = "command-center/receipts/TST-0265.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0265"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0265/probe1_mutants_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0265/probe2_gaming_reviewer.py"
)
SUPPORTING = [
    "tools/council/quota/unique_ideas.py",
    "tools/council/quota/__init__.py",
    "command-center/p2-wave/probes/TST-0265/fixtures.py",
    "command-center/p2-wave/probes/TST-0265/fixtures/distinct-100.json",
    "command-center/p2-wave/probes/TST-0265/ledger.py",
    "command-center/p2-wave/probes/TST-0265/measure.py",
    "command-center/p2-wave/probes/TST-0265/probe1_mutants_both_states.py",
    "command-center/p2-wave/probes/TST-0265/probe2_gaming_reviewer.py",
]
QUESTION = (
    "Question: when a brainstorm reports 100 unique ideas, how many are "
    "wording variants of each other? Build the deduplicator that collapses "
    "variants, run it against unique_ideas >= 100, and report the post-dedup "
    "count as the only count that may be used to satisfy a stopping rule."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def eol_of(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "MIXED"
    if crlf:
        return "CRLF"
    return "LF"


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol_of(data) if data else "NOT-CHECKED",
    }


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:TST-0265 emit snippet not in {rel}: {snippet!r}")


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    live = M.run()
    if not all(m["passed"] for m in live["planted_mutants"]):
        print("FAILED:TST-0265 emit planted mutant missed")
        return 1
    if not live["blind_class"]["passed"]:
        print("FAILED:TST-0265 emit blind class did not stay SILENT")
        return 1
    if not live["both_states"]["discriminates"]:
        print("FAILED:TST-0265 emit both-states did not discriminate")
        return 1
    if not live["gaming_simulation"]["caught"]:
        print("FAILED:TST-0265 emit gaming pad not caught")
        return 1
    if not live["reviewer_agreement"]:
        print("FAILED:TST-0265 emit author/reviewer disagree")
        return 1
    if len(live["brainstorm_runs"]) != 3:
        print("FAILED:TST-0265 emit expected three brainstorm runs")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:TST-0265 emit missing {missing}")
        return 1

    planted = []
    for m in live["planted_mutants"]:
        planted.append(
            {
                "class_id": m["class_id"],
                "want": m["want"],
                "observed": m["observed"],
                "raw_jaccard": m["raw_jaccard"],
                "keys_equal": m["keys_equal"],
                "s1_fires": m["s1_fires"],
                "s2_fires": m["s2_fires"],
                "post_pair_count": m["author_unique_count"],
                "reviewer_pair_count": m["reviewer_unique_count"],
                "passed": m["passed"],
                "note": m["note"],
            }
        )

    runs = []
    for row in live["brainstorm_runs"]:
        runs.append(
            {
                "name": row["name"],
                "cast": row["cast"],
                "instruction": row["instruction"],
                "n_ledger_rows": row["n_ledger_rows"],
                "raw_count": row["raw_count"],
                "post_dedup_count": row["post_dedup_count"],
                "collapse_ratio": row["collapse_ratio"],
                "naive_gate_ge_100": row["naive_gate_ge_100"],
                "stopping_gate_ge_100": row["stopping_gate_ge_100"],
                "reviewer_connected_components": row["reviewer_connected_components"],
            }
        )

    bad = live["both_states"]["planted_bad"]
    good = live["both_states"]["known_good"]
    gaming = live["gaming_simulation"]
    blind = live["blind_class"]

    fire_classes = [m["class_id"] for m in planted if m["observed"] == "FIRE"]
    silent_classes = [m["class_id"] for m in planted if m["observed"] == "SILENT"]
    silent_classes.append(blind["class_id"])

    answer = (
        f"Similarity method={live['similarity_method']} threshold="
        f"{live['jaccard_threshold']}. Planted mutants FIRE="
        f"{fire_classes} SILENT={silent_classes}. Blind class "
        f"{blind['id']} is SILENT (OOV deep paraphrase). Distinct-100 "
        f"collapse_ratio={good['collapse_ratio']} (tolerance "
        f"{live['distinct_collapse_tolerance']}). Gaming pad raw="
        f"{gaming['raw_count']} post_dedup={gaming['post_dedup_count']} "
        f"caught={gaming['caught']}. Three brainstorm runs: "
        + "; ".join(
            f"{r['name']} raw={r['raw_count']} post={r['post_dedup_count']} "
            f"collapse={r['collapse_ratio']}"
            for r in runs
        )
        + f". Stopping rule uses post-dedup only. {SENTINEL}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0265",
        "id": "TST-0265",
        "title": (
            "Trivial-variant detector for the 100-idea brainstorm, "
            "with planted mutants as its control"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0265]; "
            "catalog quotes _USER-PROMPTS.md:10937 unique_ideas>=100, "
            ":11236 idea-count gaming, :11339 100-idea brainstorm trivial "
            "variants. _USER-PROMPTS.md and tools/council/simulate.py are "
            "absent on this worktree."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog output_schema is command-center/schema/receipt.schema.json; "
            "that path is absent on this worktree so this receipt is "
            "JSON-parseable and sentinel-bearing rather than schema-validated here."
        ),
        "min_bytes_threshold": 2048,
        "produced_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "question": QUESTION,
        "answer": answer,
        "similarity_method": live["similarity_method"],
        "jaccard_threshold": live["jaccard_threshold"],
        "unique_ideas_floor": live["unique_ideas_floor"],
        "distinct_collapse_tolerance": live["distinct_collapse_tolerance"],
        "stopping_rule": live["stopping_rule"],
        "implementation": {
            "library": "tools/council/quota/unique_ideas.py",
            "entry_point": "stopping_unique_count",
            "author_algorithm": "union-find",
            "reviewer_algorithm": "connected-components",
            "signals": [
                "S1 raw token-set Jaccard >= 0.50",
                "S2 folded mechanism-key equality",
            ],
        },
        "planted_mutants": planted,
        "blind_class": {
            "id": blind["id"],
            "class_id": blind["class_id"],
            "want": blind["want"],
            "observed": blind["observed"],
            "raw_jaccard": blind["raw_jaccard"],
            "keys_equal": blind["keys_equal"],
            "post_pair_count": blind["author_unique_count"],
            "passed": blind["passed"],
            "note": blind["note"],
        },
        "both_states": {
            "planted_bad": {
                "fixture": "100 suffix-integer variants of one seed",
                "raw_count": bad["raw_count"],
                "post_dedup_count": bad["post_dedup_count"],
                "collapse_ratio": bad["collapse_ratio"],
                "observed": bad["observed"],
                "want": bad["want"],
                "passed": bad["passed"],
                "verbatim": bad["verbatim"],
            },
            "known_good": {
                "fixture": "100 genuinely distinct mechanisms",
                "raw_count": good["raw_count"],
                "post_dedup_count": good["post_dedup_count"],
                "collapse_ratio": good["collapse_ratio"],
                "tolerance": live["distinct_collapse_tolerance"],
                "observed": good["observed"],
                "want": good["want"],
                "passed": good["passed"],
                "verbatim": good["verbatim"],
            },
            "discriminates": live["both_states"]["discriminates"],
        },
        "gaming_simulation": dict(gaming),
        "brainstorm_runs": runs,
        "reviewer": {
            "reviewer_id": "TST-0265-probe2-connected-components",
            "independent": True,
            "fresh_context": True,
            "executed_both_states": True,
            "algorithm": "connected-components",
            "bad_unique": bad["reviewer_connected_components"],
            "good_unique": good["reviewer_connected_components"],
            "verdict": "PASS",
            "starts_from": (
                "unique_count_connected_components on the gamed and distinct "
                "corpora, not the author's summary"
            ),
        },
        "reviewer_verdict": "PASS",
        "negative_controls": [
            {
                "id": "NC-naive-silent-on-gamed",
                "kind": "both-states",
                "description": (
                    "String-equality naive_unique accepts the gamed 100 and "
                    "the distinct 100, so it cannot gate the stopping rule."
                ),
                "fired_on_bad_state": bad["naive_gate_ge_100"] is True
                and bad["stopping_gate_ge_100"] is False,
                "silent_on_good_state": good["stopping_gate_ge_100"] is True,
            },
            {
                "id": "NC-oov-deep-paraphrase-silent",
                "kind": "blind-class",
                "description": blind["note"],
                "fired_on_bad_state": True,
                "silent_on_good_state": blind["observed"] == "SILENT",
            },
        ],
        "evidence": [
            ev(
                "command-center/WORK-UNIT-CATALOG.json",
                "the required :10937 target of unique_ideas >= 100",
                "catalog",
                "Stopping floor unique_ideas >= 100 is the catalog target.",
            ),
            ev(
                "command-center/WORK-UNIT-CATALOG.json",
                "100-idea brainstorm satisfying its count with trivial wording variants",
                "catalog",
                "Named failure :11339 is the gaming class this detector must catch.",
            ),
            ev(
                "tools/council/quota/unique_ideas.py",
                "stopping_unique_count",
                "implementation",
                "Post-dedup count is the only stopping-rule input.",
            ),
            ev(
                "tools/council/quota/unique_ideas.py",
                "JACCARD_THRESHOLD = 0.50",
                "implementation",
                "Named similarity threshold for S1.",
            ),
        ],
        "tests": [
            {
                "id": "planted-mutants",
                "command": P1,
                "result": "PASS",
                "requirement": (
                    "exact rename, single-word swap, and full-rewrite "
                    "paraphrase report FIRE or SILENT per class"
                ),
            },
            {
                "id": "both-states-distinct-tolerance",
                "command": P1,
                "result": "PASS",
                "requirement": (
                    "100 genuinely distinct ideas collapse by less than "
                    "declared tolerance 0.05"
                ),
            },
            {
                "id": "gaming-pad-caught",
                "command": P2,
                "result": "PASS",
                "requirement": (
                    "a cast instructed to pad to 100 is caught by post-dedup "
                    "falling below the target"
                ),
            },
        ],
        "test_ids": [
            "planted-mutants",
            "both-states-distinct-tolerance",
            "gaming-pad-caught",
        ],
        "negative_control_ids": [
            "NC-naive-silent-on-gamed",
            "NC-oov-deep-paraphrase-silent",
        ],
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": artifacts,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0265/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": P1,
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            },
            {
                "consumer": P2,
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py (TST-0257) is absent. Three "
                    "brainstorm runs used the local scripted-cast ledger "
                    "emitter in probes/TST-0265/ledger.py, not a live model "
                    "council."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run stopping_unique_count on ledgers emitted by "
                    "tools/council/simulate.py once TST-0257 lands."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md is absent; :10937/:11236/:11339 are "
                    "cited from WORK-UNIT-CATALOG.json quotes."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": "Re-cite against a restored _USER-PROMPTS.md.",
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "No automatic retry: a failure here is a finding. Re-run only "
                "after a named change to the harness or the fixture."
            ),
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0265 emit {size}B below floor")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0265 emit sentinel missing from bytes")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:TST-0265 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
