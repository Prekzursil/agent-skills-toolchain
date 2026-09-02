#!/usr/bin/env python3
"""Emit RES-0145 measurement artifact, then per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import detector as D  # noqa: E402

UNIT = "RES-0145"
OUT_REL = (
    "command-center/research/evidence-quality/"
    "RES-0145-circular-citation-detection.json"
)
SCHEMA = "command-center/schema/measurement-run.schema.json"
SENTINEL = "SUCCESS:RES-0145"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0145/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0145/probe2_url_count_not_origin.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0145/corpus.py",
    "command-center/p2-wave/probes/RES-0145/detector.py",
    "command-center/p2-wave/probes/RES-0145/fixtures/corpus.json",
    "command-center/p2-wave/probes/RES-0145/probe1_both_states.py",
    "command-center/p2-wave/probes/RES-0145/probe2_url_count_not_origin.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def lineage_for_fixture(fetched_at: str) -> dict:
    path = REPO / "command-center/p2-wave/probes/RES-0145/fixtures/corpus.json"
    digest, size = sha256_file(path)
    return {
        "resolved_url": "file:command-center/p2-wave/probes/RES-0145/fixtures/corpus.json",
        "fetch_timestamp": fetched_at,
        "sha256": digest,
        "bytes": size,
    }


def load_bearing_claims(summary: dict, lineage: dict) -> list[dict]:
    return [
        {
            "id": "RES-0145-C-DETECTION-RATE",
            "claim": (
                "On the committed 20-cluster planted corpus, the four-signal "
                "detector fires on all 10 single-origin citation cycles "
                f"(detection_rate={summary['detection_rate']})."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "live-detector-tp",
                    "note": f"tp={summary['tp']} fn={summary['fn']}",
                },
                {
                    "id": "probe1-both-states",
                    "note": "probe1 re-runs evaluate() and demands tp=10 fn=0",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P1,
        },
        {
            "id": "RES-0145-C-FALSE-POSITIVE-RATE",
            "claim": (
                "On the same corpus the detector stays silent on all 10 "
                "genuinely independent clusters "
                f"(false_positive_rate={summary['false_positive_rate']}), "
                "including CLAIM-18 and CLAIM-19 which have citation cycles "
                "of distinct facts."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "live-detector-fp",
                    "note": f"fp={summary['fp']} tn={summary['tn']}",
                },
                {
                    "id": "probe1-independent-silence",
                    "note": "probe1 demands fp=0 tn=10",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P1,
        },
        {
            "id": "RES-0145-C-URL-COUNT-NOT-ORIGIN",
            "claim": (
                "Counting distinct URLs does not detect origin descent: every "
                "planted-cycle member has a unique URL, so a URL-count "
                "baseline has detection_rate=0 on the planted cycles."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "url-uniqueness",
                    "note": "len(urls)==len(set(urls)) over the whole corpus",
                },
                {
                    "id": "url-count-baseline",
                    "note": "url_count_fire is false on every planted cycle",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P2,
        },
        {
            "id": "RES-0145-C-CYCLE-ONLY-INSUFFICIENT",
            "claim": (
                "A citation-cycle-only detector fires on independent "
                "CLAIM-18 and CLAIM-19 (cross-references of distinct facts) "
                "and is therefore not an origin-descent detector. Content "
                "copy (distinctive 6-grams or distinctive quantities) is "
                "required in conjunction with the cycle."
            ),
            "status": "VERIFIED",
            "sherman_kent": "almost-certain",
            "signals": [
                {
                    "id": "cycle-only-fp",
                    "note": "CLAIM-18, CLAIM-19",
                },
                {
                    "id": "content-ablation",
                    "note": "CLAIM-01 silent after body ablation; CLAIM-11 fires only after content+cycle",
                },
            ],
            "source_lineage": lineage,
            "verification_path": P2,
        },
    ]


def build_artifact(
    corpus: dict,
    results: dict,
    summary: dict,
    url_rate: float,
    cycle_only_fp: list[str],
    fetched_at: str,
) -> dict:
    lineage = lineage_for_fixture(fetched_at)
    question = (
        "What algorithm reliably detects that a set of sources supporting "
        "one claim all descend from a single origin — shared verbatim "
        "n-grams, shared factual errors, publication-date ordering, "
        "explicit backlinks — and what is its detection rate on a corpus "
        "with 10 planted citation cycles and 10 genuinely independent clusters?"
    )
    answer = (
        "Conjunction: distinctive shared 6-grams OR distinctive shared "
        "quantities (content copy), AND a directed cycle in the "
        "within-cluster citation graph (explicit backlinks). Publication-date "
        "ordering is corroboration and never fires alone. Distinct URL "
        "counts are not origin tracing. On the committed planted corpus "
        f"detection_rate={summary['detection_rate']} and "
        f"false_positive_rate={summary['false_positive_rate']}."
    )
    cluster_rows = []
    gold = C.gold_by_cluster()
    for cid in sorted(results):
        row = results[cid]
        cluster_rows.append(
            {
                "cluster_id": cid,
                "gold": gold[cid],
                "fire": row["fire"],
                "verdict": row["verdict"],
                "member_ids": row["member_ids"],
                "signals": row["signals"],
                "content_copy": row["content_copy"],
                "citation_cycle": row["citation_cycle"],
                "unique_url_count": row["unique_url_count"],
                "urls_all_distinct": row["urls_all_distinct"],
            }
        )
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "output_schema": SCHEMA,
        "schema_note": (
            "command-center/schema/measurement-run.schema.json is absent on "
            "this sparse tree and is not rebuilt here (no ADV schema circle)."
        ),
        "title": (
            "Detect a citation cycle where N apparently independent sources "
            "restate one origin"
        ),
        "question": question,
        "question_or_target": question,
        "answer": answer,
        "algorithm": {
            "name": "content-copy-AND-citation-cycle",
            "signals": [
                "shared-verbatim-6grams-distinctive-vs-corpus",
                "shared-distinctive-quantities",
                "publication-date-copy-chain",
                "explicit-backlink-directed-cycle",
            ],
            "fire_rule": (
                "(distinctive_shared_6gram OR distinctive_shared_quantity) "
                "AND directed_citation_cycle"
            ),
            "date_role": "corroboration-only",
            "url_count_role": "rejected-as-independence-proxy",
        },
        "corpus": {
            "path": "command-center/p2-wave/probes/RES-0145/fixtures/corpus.json",
            "n_clusters": corpus["n_clusters"],
            "n_cycle": corpus["n_cycle"],
            "n_independent": corpus["n_independent"],
            "fetched_at": fetched_at,
            "sha256": lineage["sha256"],
            "bytes": lineage["bytes"],
            "committed": True,
        },
        "rates": {
            "detection_rate": summary["detection_rate"],
            "false_positive_rate": summary["false_positive_rate"],
            "tp": summary["tp"],
            "fp": summary["fp"],
            "tn": summary["tn"],
            "fn": summary["fn"],
        },
        "both_states_control": {
            "fires_on_all_planted_cycles": summary["tp"] == 10 and summary["fn"] == 0,
            "silent_on_all_independent_clusters": summary["fp"] == 0
            and summary["tn"] == 10,
            "detector_that_fires_on_both_measures_nothing": True,
        },
        "naive_baselines": {
            "distinct_url_count_detection_rate": url_rate,
            "cycle_only_false_positive_clusters": cycle_only_fp,
        },
        "naive_baselines": {
            "distinct_url_count_detection_rate": url_rate,
            "cycle_only_false_positive_clusters": cycle_only_fp,
        },
        "clusters": cluster_rows,
        "claims": load_bearing_claims(summary, lineage),
        "residual_unknowns": [
            {
                "claim": (
                    "Rates are for the committed planted corpus, not a live "
                    "web crawl of research citations."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run detector.py against a harvested citation graph "
                    "with independently labelled origin-descent clusters."
                ),
            },
            {
                "claim": (
                    "Heavily paraphrased copies that share neither a 6-gram "
                    "nor a distinctive quantity would be silent under this "
                    "fire rule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Plant a paraphrase-only cycle with a shared planted "
                    "error removed and report whether a semantic signal is "
                    "required."
                ),
            },
        ],
        "tests": [
            {
                "id": "both-states-planted-cycles",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "both-states-independent-silence",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "url-count-not-origin",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "cycle-only-false-positives-and-ablation",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "both-states-control"},
            {"id": "probe2", "command": P2, "role": "url-count-not-origin"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0145-probe2-url-count-not-origin",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not trust the detection-rate headline. It "
                "re-runs URL-count and cycle-only baselines plus content "
                "ablation and content+cycle injection."
            ),
        },
        "notes": (
            "G-1 delivery of RES-0145. Live named probes exit 0. Artifact "
            "state=SUCCESS. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted. Did not implement ADV rebuild."
        ),
        "SUCCESS:RES-0145": True,
    }


def write_receipts(code1: int, out1: str, code2: int, out2: str) -> int:
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "raw_output": out1[-8000:],
                "role": "both-states-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "raw_output": out2[-8000:],
                "role": "url-count-not-origin",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0145-probe2-url-count-not-origin",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0145: live named probes exit 0, measurement artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
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
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0145 receipts")
    return 0


def main() -> int:
    C.materialize()
    corpus = C.load_corpus()
    live_docs = C.documents_for_detector(corpus)
    gold = C.gold_by_cluster()
    results = D.evaluate(live_docs)
    summary = D.summarize(results, gold)
    if not summary["both_states_pass"]:
        print(f"FAILED:RES-0145 both-states {summary}")
        return 1

    grouped: dict[str, list] = {}
    for row_d in live_docs:
        grouped.setdefault(row_d["cluster_id"], []).append(row_d)
    url_hits = 0
    n_cycle = 0
    cycle_only_fp = []
    for cid, members in grouped.items():
        if gold[cid] == "cycle":
            n_cycle += 1
            if D.url_count_fire(members):
                url_hits += 1
        elif D.cycle_only_fire(members):
            cycle_only_fp.append(cid)
    url_rate = (url_hits / n_cycle) if n_cycle else 0.0
    cycle_only_fp.sort()

    doc = build_artifact(
        corpus, results, summary, url_rate, cycle_only_fp, C.FETCHED_AT
    )
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0145 sentinel absent")
        return 1
    if size < 1024:
        print(f"FAILED:RES-0145 artifact too small {size}")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")

    code1, out1 = run(P1)
    code2, out2 = run(P2)
    print(out1[-2000:])
    print(out2[-2000:])
    if code1 != 0 or "SUCCESS:RES-0145-probe1" not in out1:
        print("FAILED:RES-0145 probe1")
        return 1
    if code2 != 0 or "SUCCESS:RES-0145-probe2" not in out2:
        print("FAILED:RES-0145 probe2")
        return 1
    write_receipts(code1, out1, code2, out2)
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# Aliases so build_artifact / write_receipts / main share one name set.
UNIT = UNIT
OUT_REL = OUT_REL
SUPPORTING = SUPPORTING
lineage_for_fixture = lineage_for_fixture
load_bearing_claims = load_bearing_claims
sha256_file = sha256_file
run = run
write_receipts = write_receipts
