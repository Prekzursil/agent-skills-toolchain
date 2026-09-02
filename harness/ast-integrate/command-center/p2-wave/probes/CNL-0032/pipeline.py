#!/usr/bin/env python3
"""Strict proposer-critic-judge pipeline: judge-input extraction and loss.

A stage that 'sees only the previous stage's output' receives that output
object, not the actor envelope and not earlier stages. The judge in a
strict pipeline therefore receives critic.output and nothing else.

Two independent measurements on the same fixture:
  signal 1 — token-id set algebra (structured field walk)
  signal 2 — canonical-JSON sha256 and byte-length (byte measurement)
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "pcj-run.json"

POINT_KINDS = frozenset({"identity", "rhetoric", "discarded_alternative"})
DEFECT_KINDS = frozenset({"claim", "evidence", "constraint", "question"})
LOSS_KINDS = POINT_KINDS | DEFECT_KINDS


def load_run(path: Path | None = None) -> dict:
    p = path or FIXTURE
    return json.loads(p.read_text(encoding="utf-8"))


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest_bytes(raw: bytes) -> tuple[str, int]:
    return hashlib.sha256(raw).hexdigest(), len(raw)


def digest_pair(a: Any, b: Any) -> dict:
    """Signal 2: canonical sha256 + byte-length of two judge-input documents."""
    ca, cb = canon(a), canon(b)
    sa, na = digest_bytes(ca)
    sb, nb = digest_bytes(cb)
    return {
        "pipeline_sha256": sa,
        "pipeline_bytes": na,
        "full_sha256": sb,
        "full_bytes": nb,
        "sha256_match": sa == sb,
        "byte_delta": nb - na,
    }


def _as_token(obj: dict) -> dict | None:
    tid = obj.get("id")
    kind = obj.get("kind")
    if not isinstance(tid, str) or not isinstance(kind, str):
        return None
    if kind not in LOSS_KINDS and kind != "critique_point":
        return None
    loss_class = obj.get("loss_class")
    if loss_class not in {"defect", "point", "operational"}:
        if kind in DEFECT_KINDS:
            loss_class = "defect"
        elif kind in POINT_KINDS:
            loss_class = "point"
        else:
            loss_class = "operational"
    return {
        "id": tid,
        "kind": kind,
        "loss_class": loss_class,
        "load_bearing": bool(obj.get("load_bearing")),
        "status": obj.get("status"),
        "text": obj.get("text"),
    }


def walk_tokens(obj: Any, acc: list[dict] | None = None) -> list[dict]:
    """Collect unique token records by id (first occurrence wins)."""
    if acc is None:
        acc = []
    seen = {t["id"] for t in acc}

    def rec(node: Any) -> None:
        if isinstance(node, dict):
            tok = _as_token(node)
            if tok is not None and tok["id"] not in seen:
                acc.append(tok)
                seen.add(tok["id"])
            for v in node.values():
                rec(v)
        elif isinstance(node, list):
            for v in node:
                rec(v)

    rec(obj)
    return acc


def token_ids(tokens: Iterable[dict], *, loss_class: str | None = None) -> list[str]:
    out = []
    for t in tokens:
        if loss_class is not None and t.get("loss_class") != loss_class:
            continue
        out.append(t["id"])
    return sorted(set(out))


def pipeline_judge_input(run: dict) -> dict:
    """Strict pipeline: judge sees only the critic's output body."""
    critic = run["stages"]["critic"]
    return {
        "handoff": "critic->judge",
        "body": copy.deepcopy(critic["output"]),
    }


def full_transcript_judge_input(run: dict) -> dict:
    """Full-transcript judge: question + proposer envelope + critic envelope."""
    return {
        "handoff": "full-transcript",
        "question": copy.deepcopy(run["question"]),
        "proposer": copy.deepcopy(run["stages"]["proposer"]),
        "critic": copy.deepcopy(run["stages"]["critic"]),
    }


def token_loss(full_tokens: list[dict], pipe_tokens: list[dict]) -> dict:
    """Signal 1: set algebra on token ids, partitioned by loss_class."""
    full_ids = {t["id"] for t in full_tokens if t["loss_class"] in {"defect", "point"}}
    pipe_ids = {t["id"] for t in pipe_tokens if t["loss_class"] in {"defect", "point"}}
    lost_ids = full_ids - pipe_ids
    by_id = {t["id"]: t for t in full_tokens}
    lost = [by_id[i] for i in sorted(lost_ids)]
    defect_lost = [t for t in lost if t["loss_class"] == "defect"]
    point_lost = [t for t in lost if t["loss_class"] == "point"]
    return {
        "full_ids": sorted(full_ids),
        "pipeline_ids": sorted(pipe_ids),
        "lost_ids": sorted(lost_ids),
        "defect_lost_ids": [t["id"] for t in defect_lost],
        "point_lost_ids": [t["id"] for t in point_lost],
        "lost": lost,
        "defect_lost": defect_lost,
        "point_lost": point_lost,
    }


def required_defect_ids(run: dict) -> list[str]:
    src = {"question": run["question"], "proposer": run["stages"]["proposer"]}
    toks = walk_tokens(src)
    return sorted(
        t["id"]
        for t in toks
        if t["loss_class"] == "defect" and t.get("load_bearing")
    )


def mechanical_rulings(run: dict) -> dict:
    """Pipeline judge can only require what it sees. Full-transcript judge
    refuses if a load-bearing defect token was neither forwarded nor rejected.
    """
    required = set(required_defect_ids(run))
    pipe = pipeline_judge_input(run)
    visible = set(token_ids(walk_tokens(pipe), loss_class="defect"))
    critic_present = set(token_ids(walk_tokens(run["stages"]["critic"]["output"])))
    unaddressed = sorted(required - critic_present)
    pipeline_verdict = "ACCEPT"
    full_verdict = "REFUSE-INCOMPLETE" if unaddressed else "ACCEPT"
    return {
        "required_defect_ids": sorted(required),
        "pipeline_visible_defect_ids": sorted(visible),
        "critic_present_ids": sorted(critic_present),
        "unaddressed_required_ids": unaddressed,
        "pipeline_verdict": pipeline_verdict,
        "full_transcript_verdict": full_verdict,
        "verdicts_diverge": pipeline_verdict != full_verdict,
    }


def measure(run: dict) -> dict:
    pipe = pipeline_judge_input(run)
    full = full_transcript_judge_input(run)
    sig1 = token_loss(walk_tokens(full), walk_tokens(pipe))
    sig2 = digest_pair(pipe, full)
    rulings = mechanical_rulings(run)
    return {
        "fixture_id": run.get("id"),
        "topology": run.get("topology"),
        "signal1_token_sets": {
            "full_ids": sig1["full_ids"],
            "pipeline_ids": sig1["pipeline_ids"],
            "lost_ids": sig1["lost_ids"],
            "defect_lost_ids": sig1["defect_lost_ids"],
            "point_lost_ids": sig1["point_lost_ids"],
        },
        "signal2_canonical_bytes": sig2,
        "rulings": rulings,
        "defect_lost": sig1["defect_lost"],
        "point_lost": sig1["point_lost"],
    }


def make_faithful(run: dict) -> dict:
    """Forward every defect-class token; still strip identity/rhetoric/workshop."""
    out = copy.deepcopy(run)
    out["id"] = "pcj-run-faithful"
    src = {"question": run["question"], "proposer": run["stages"]["proposer"]}
    defect = [
        copy.deepcopy(t)
        for t in walk_tokens(src)
        if t["loss_class"] == "defect"
    ]
    for t in defect:
        t["status"] = "forwarded"
    keep_ops = [
        copy.deepcopy(t)
        for t in walk_tokens(run["stages"]["critic"]["output"])
        if t["loss_class"] == "operational"
    ]
    out["stages"]["critic"]["output"]["tokens"] = defect + keep_ops
    out["stages"]["critic"]["output"]["omitted_without_rejection"] = []
    return out


def make_explicit_reject(run: dict) -> dict:
    """Same as drop, except omitted load-bearing tokens are explicitly rejected."""
    out = copy.deepcopy(run)
    out["id"] = "pcj-run-explicit-reject"
    existing = {t["id"] for t in out["stages"]["critic"]["output"]["tokens"]}
    src = {"question": run["question"], "proposer": run["stages"]["proposer"]}
    extra = []
    for t in walk_tokens(src):
        if t["loss_class"] == "defect" and t["id"] not in existing:
            rec = copy.deepcopy(t)
            rec["status"] = "rejected"
            rec["text"] = f"REJECTED: {t.get('text')}"
            extra.append(rec)
    out["stages"]["critic"]["output"]["tokens"].extend(extra)
    out["stages"]["critic"]["output"]["omitted_without_rejection"] = []
    return out


def partition_rule() -> dict:
    return {
        "point_class": sorted(POINT_KINDS),
        "defect_class": sorted(DEFECT_KINDS),
        "rule": (
            "A strict pipeline MAY strip identity, rhetoric, and discarded "
            "alternatives at the critic->judge handoff; that loss is the point "
            "of isolation. A strict pipeline MUST NOT omit a load-bearing "
            "question, claim, evidence, or constraint token: omission is "
            "uncontrolled silence. Explicit rejection (token present with "
            "status=rejected) is the critic doing its job; silence is not."
        ),
    }
