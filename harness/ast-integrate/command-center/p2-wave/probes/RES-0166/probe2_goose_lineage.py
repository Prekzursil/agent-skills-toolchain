#!/usr/bin/env python3
"""Probe 2: Goose file:line + source-byte lineage. Does not rank topologies.

Independent of probe1: re-hashes frozen captures, re-reads Goose needles at
file:line, checks dual rails on load-bearing claims, and defaults to REFUTED
when lineage is missing. Refuses an overclaim that escalation beats retry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / E.ARTIFACT_REL

NEEDLES = (
    (
        "goose-init.rs",
        "const DEFAULT_FAILURE_THRESHOLD: usize = 2;",
    ),
    (
        "goose-init.rs",
        "const DEFAULT_LEAD_TURNS: usize = 3;",
    ),
    (
        "goose-init.rs",
        "const DEFAULT_FALLBACK_TURNS: usize = 2;",
    ),
    (
        "goose-lead-worker.rs",
        "max_failures_before_fallback: 2, // Fallback after 2 consecutive failures",
    ),
    (
        "goose-env-vars.md",
        "`GOOSE_LEAD_FAILURE_THRESHOLD` | Consecutive failures before falling back to the lead model | Integer | 2 |",
    ),
    (
        "goose-lead-worker-tutorial.md",
        "The lead/worker model is a smart hand-off system.",
    ),
    (
        "goose-pr-7989.json",
        "Remove lead/worker provider",
    ),
    (
        "anthropic-multi-agent.html",
        "orchestrator-worker pattern",
    ),
    (
        "autogen-group-chat-core.html",
        "GroupChatManager",
    ),
    (
        "temporal-activity-failures.md",
        "Heartbeat Timeout",
    ),
)

ESTATE = (
    (
        "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        34,
        "TWO_STRIKES = 2",
    ),
    (
        "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        35,
        "WORKER_TIMEOUT_SEC = 90 * 60",
    ),
    (
        "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        460,
        "now - child[\"started\"] > WORKER_TIMEOUT_SEC",
    ),
    (
        "command-center/p2-wave/probes/CNF-0095/reducer.py",
        4,
        "Conjunction, not averaging",
    ),
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0166-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if E.SENTINEL not in text:
        return fail("sentinel-absent")

    rows = E.verify_lineage()
    mismatches = [r for r in rows if not r["match"] or not r["present"]]
    if mismatches:
        return fail(f"lineage-mismatch:{[m['file'] for m in mismatches]}")
    if len(rows) < 10:
        return fail(f"lineage-short:{len(rows)}")

    art_src = {
        s.get("file"): s
        for s in (doc.get("source_lineage") or [])
        if isinstance(s, dict)
    }
    hashed = 0
    for row in rows:
        art = art_src.get(row["file"])
        if not isinstance(art, dict):
            return fail(f"artifact-source-missing:{row['file']}")
        if art.get("sha256") != row["live_sha256"]:
            return fail(f"artifact-sha-mismatch:{row['file']}")
        if not art.get("resolved_url"):
            return fail(f"url-missing:{row['file']}")
        if not art.get("fetch_timestamp"):
            return fail(f"ts-missing:{row['file']}")
        if art.get("http_status") != 200:
            return fail(f"http:{row['file']}:{art.get('http_status')}")
        hashed += 1

    hits = []
    for fname, needle in NEEDLES:
        if not E.file_has(fname, needle):
            return fail(f"needle-miss:{fname}:{needle[:48]}")
        hits.append(fname)

    if not E.line_has(
        "command-center/p2-wave/probes/RES-0166/fixtures/sources/goose-init.rs",
        44,
        "const DEFAULT_FAILURE_THRESHOLD: usize = 2;",
    ):
        return fail("init.rs:44 needle")
    if not E.line_has(
        "command-center/p2-wave/probes/RES-0166/fixtures/sources/goose-lead-worker.rs",
        52,
        "max_failures_before_fallback: 2",
    ):
        return fail("lead_worker.rs:52 needle")
    if not E.line_has(
        "command-center/p2-wave/probes/RES-0166/fixtures/sources/goose-env-vars.md",
        142,
        "GOOSE_LEAD_FAILURE_THRESHOLD",
    ):
        return fail("env-vars.md:142 needle")

    for rel, line, needle in ESTATE:
        if not E.line_has(rel, line, needle):
            return fail(f"estate-needle:{rel}:{line}")

    ge = doc.get("goose_escalation") or {}
    if ge.get("defaults", {}).get("failure_threshold") != 2:
        return fail("artifact threshold not 2")
    if ge.get("kind") != "intra-session-model-handoff":
        return fail("goose kind drift")
    if ge.get("beats_same_worker_retry") in {"CONFIRMED", "TRUE", True, "beats"}:
        return fail("overclaim: escalation beats retry")
    if ge.get("canonical_repo") != "aaif-goose/goose":
        return fail("canonical repo")
    removed = ge.get("removed_by") or {}
    if removed.get("merged") is not True:
        return fail("PR 7989 not recorded merged")

    block = json.loads(
        (REPO / E.source_by_file("goose-repo-block.json")["path"]).read_text(
            encoding="utf-8"
        )
    )
    aaif = json.loads(
        (REPO / E.source_by_file("goose-repo-aaif.json")["path"]).read_text(
            encoding="utf-8"
        )
    )
    if block.get("id") != aaif.get("id") or aaif.get("full_name") != "aaif-goose/goose":
        return fail("repo rename mismatch")
    if E.source_by_file("goose-repo-block.json")["sha256"] != E.source_by_file(
        "goose-repo-aaif.json"
    )["sha256"]:
        return fail("block/aaif body sha mismatch")

    claims = doc.get("claims") or []
    if len(claims) < 8:
        return fail(f"claims-short:{len(claims)}")
    by_id = {c.get("id"): c for c in claims if isinstance(c, dict)}
    c6 = by_id.get("RES-0166-C6-ESCALATION-BEATS-RETRY-UNMEASURED")
    if not isinstance(c6, dict):
        return fail("C6 missing")
    if str(c6.get("verdict") or "").upper() != "REFUTED":
        return fail(f"C6 must be REFUTED, got {c6.get('verdict')}")
    for claim in claims:
        cid = claim.get("id")
        signals = claim.get("signals") or []
        lineage = claim.get("source_lineage") or []
        if len(signals) < 2:
            return fail(f"single-signal:{cid}")
        backends = {s.get("backend") for s in signals if isinstance(s, dict)}
        kinds = {s.get("kind") for s in signals if isinstance(s, dict)}
        if len(signals) >= 2 and len(backends) < 2 and len(kinds) < 2:
            return fail(f"signals-not-independent:{cid}")
        if len(lineage) < 1:
            return fail(f"claim-no-lineage:{cid}")
        if not claim.get("confidence_band") and not claim.get("sherman_kent"):
            return fail(f"claim-no-kent:{cid}")
        if not claim.get("independent_verification_path"):
            return fail(f"claim-no-verify:{cid}")
        if str(claim.get("verdict") or "").upper() == "CONFIRMED" and cid == (
            "RES-0166-C6-ESCALATION-BEATS-RETRY-UNMEASURED"
        ):
            return fail("C6 overclaim")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer-not-independent")
    if str(reviewer.get("verdict") or "").upper() in {"REFUTED", "CHANGES-REQUESTED"}:
        return fail(f"reviewer:{reviewer.get('verdict')}")

    print(
        json.dumps(
            {
                "probe": "probe2-goose-lineage",
                "sources_hashed": hashed,
                "needles": len(hits),
                "repo_id": aaif.get("id"),
                "canonical": aaif.get("full_name"),
                "threshold": 2,
                "c6": c6.get("verdict"),
            },
            sort_keys=True,
        )
    )
    print(
        f"sources_hashed={hashed} needles={len(hits)} "
        f"canonical={aaif.get('full_name')} c6=REFUTED"
    )
    print("SUCCESS:RES-0166-probe2 Goose file:line lineage and anti-overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
