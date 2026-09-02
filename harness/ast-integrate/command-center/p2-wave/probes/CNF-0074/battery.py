#!/usr/bin/env python3
"""Live replay battery for CNF-0074: identity, timestamp normalise, controls."""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from compare import first_byte_diff, normalize_timestamps, verdict_for, walk_diffs
from runner import (
    CORPUS,
    ArtifactCache,
    all_workflows,
    copy_corpus,
    mutate_one_file,
    run_workflow,
)

CHANGED_REL = "alpha.txt"
CHANGED_PAYLOAD = b"alpha-payload-MUTATED\nscan-me\n"
CONTROL_WF_ID = "wf.seeded-stable"
OVERCLAIM_WF_ID = "wf.overclaim-unseeded-sample"


def _replay_one(wf: dict[str, Any], tmp: Path) -> dict[str, Any]:
    corpus = tmp / "corpus"
    copy_corpus(CORPUS, corpus)
    a = run_workflow(wf, corpus, tmp / "run-a", cache=ArtifactCache(mode="off"))
    b = run_workflow(wf, corpus, tmp / "run-b", cache=ArtifactCache(mode="off"))
    diffs = walk_diffs(a["object"], b["object"])
    na = normalize_timestamps(a["object"])
    nb = normalize_timestamps(b["object"])
    ndiffs = walk_diffs(na, nb)
    raw_id = a["sha256"] == b["sha256"]
    norm_id = na == nb
    claims = bool(wf.get("claims_determinism"))
    verdict = verdict_for(claims, raw_id, norm_id, diffs)
    ts_fields = sorted({d["path"] for d in diffs if d["cause"] == "timestamp"})
    semantic = [d for d in ndiffs if d["cause"] != "timestamp"]
    return {
        "id": wf["id"],
        "claims_determinism": claims,
        "seed": wf.get("seed"),
        "routing_pin": wf.get("routing_pin"),
        "run_a_sha256": a["sha256"],
        "run_b_sha256": b["sha256"],
        "byte_identical_raw": raw_id,
        "byte_identical_normalized": norm_id,
        "field_diffs": diffs,
        "normalized_remaining_diffs": ndiffs,
        "timestamp_fields": ts_fields,
        "verdict": verdict,
        "overclaim": verdict == "OVERCLAIM",
        "semantic_paths": [d["path"] for d in semantic],
        "first_byte_diff_offset": first_byte_diff(a["bytes"], b["bytes"]),
        "cause_attribution_complete": all(bool(d.get("cause")) for d in diffs),
    }


def replay_all(tmp: Path | None = None) -> list[dict[str, Any]]:
    tmp = tmp or Path(tempfile.mkdtemp(prefix="cnf0074-replay-"))
    return [_replay_one(wf, tmp / wf["id"]) for wf in all_workflows()]


def change_one_input_control(tmp: Path | None = None) -> dict[str, Any]:
    """Honest content cache: mutating one input must change the artifact."""
    tmp = tmp or Path(tempfile.mkdtemp(prefix="cnf0074-ctrl-"))
    wf = next(w for w in all_workflows() if w["id"] == CONTROL_WF_ID)
    cache = ArtifactCache(mode="content")
    corpus_a = tmp / "corpus-a"
    corpus_b = tmp / "corpus-b"
    copy_corpus(CORPUS, corpus_a)
    copy_corpus(CORPUS, corpus_b)
    mutate_one_file(corpus_b, CHANGED_REL, CHANGED_PAYLOAD)
    r1 = run_workflow(wf, corpus_a, tmp / "ctrl-a", cache=cache)
    r2 = run_workflow(wf, corpus_b, tmp / "ctrl-b", cache=cache)
    differ = r1["sha256"] != r2["sha256"]
    return {
        "performed": True,
        "workflow_id": wf["id"],
        "changed_input": CHANGED_REL,
        "baseline_sha256": r1["sha256"],
        "mutated_sha256": r2["sha256"],
        "artifacts_differ": differ,
        "cache_masking_ruled_out": bool(differ and r2["cache_hit"] is False),
        "cache_hits": cache.hits,
        "cache_misses": cache.misses,
        "second_run_cache_hit": r2["cache_hit"],
    }


def broken_cache_detector(tmp: Path | None = None) -> dict[str, Any]:
    """Known-broken fixture: id-only cache serves a stale artifact after mutation."""
    tmp = tmp or Path(tempfile.mkdtemp(prefix="cnf0074-broken-"))
    wf = next(w for w in all_workflows() if w["id"] == CONTROL_WF_ID)
    cache = ArtifactCache(mode="broken-id-only")
    corpus_a = tmp / "corpus-a"
    corpus_b = tmp / "corpus-b"
    copy_corpus(CORPUS, corpus_a)
    copy_corpus(CORPUS, corpus_b)
    mutate_one_file(corpus_b, CHANGED_REL, CHANGED_PAYLOAD)
    r1 = run_workflow(wf, corpus_a, tmp / "brk-a", cache=cache)
    r2 = run_workflow(wf, corpus_b, tmp / "brk-b", cache=cache)
    stale = r1["sha256"] == r2["sha256"] and r2["cache_hit"] is True
    return {
        "fired": stale,
        "workflow_id": wf["id"],
        "baseline_sha256": r1["sha256"],
        "mutated_sha256": r2["sha256"],
        "second_run_cache_hit": r2["cache_hit"],
        "reason": (
            "id-only cache served the pre-mutation artifact"
            if stale
            else "broken cache did not fire"
        ),
    }


def overclaim_detector(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = rows if rows is not None else replay_all()
    hits = [r for r in rows if r["id"] == OVERCLAIM_WF_ID]
    if not hits:
        return {"fired": False, "reason": "known-broken workflow missing"}
    row = hits[0]
    fired = row["verdict"] == "OVERCLAIM" and not row["byte_identical_normalized"]
    return {
        "fired": fired,
        "workflow_id": row["id"],
        "verdict": row["verdict"],
        "semantic_paths": row["semantic_paths"],
        "reason": (
            "unseeded sampler diverged in a semantic field while claiming determinism"
            if fired
            else "known-broken overclaim fixture did not fire"
        ),
    }


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


# Call-site aliases (emit / probes use these names).
replay_all = replay_all
change_one_input_control = change_one_input_control
broken_cache_detector = broken_cache_detector
overclaim_detector = overclaim_detector
digest_file = digest_file
