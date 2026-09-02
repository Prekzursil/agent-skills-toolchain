"""ONE shared completion reducer for flat fan-in and nested council-of-councils.

Exit code zero alone is never COMPLETE. A missing artifact is never COMPLETE.
Conjunction, not averaging: any non-COMPLETE child keeps the parent incomplete.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

COMPLETE = "COMPLETE"
INCOMPLETE = "INCOMPLETE"
BLOCKED = "BLOCKED"

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def predicate_fingerprint() -> str:
    raw = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _trace(site: str, verdict: str, failing: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "site": site,
        "predicate_module": "reducer",
        "predicate_qualname": "reduce_completion",
        "predicate_id": id(reduce_completion),
        "predicate_fingerprint": predicate_fingerprint(),
        "source_path": str(Path(__file__).resolve().relative_to(REPO)).replace("\\", "/"),
        "verdict": verdict,
        "failing_condition_id": failing,
    }
    if extra:
        row.update(extra)
    return row


def _artifact_path(receipt: dict[str, Any]) -> Path | None:
    rel = receipt.get("artifact_path")
    if not isinstance(rel, str) or not rel.strip():
        arts = receipt.get("artifacts")
        if isinstance(arts, list) and arts and isinstance(arts[0], dict):
            rel = arts[0].get("path")
    if not isinstance(rel, str) or not rel.strip():
        return None
    p = Path(rel)
    return p if p.is_absolute() else REPO / rel.replace("\\", "/")


def reduce_completion(receipt: dict[str, Any], *, site: str) -> dict[str, Any]:
    """Typed verdict for one receipt. Exit 0 is never sufficient."""
    conditions: list[dict[str, Any]] = []

    def fail(cid: str, reason: str) -> dict[str, Any]:
        conditions.append({"id": cid, "result": "FAIL", "reason": reason})
        verdict = BLOCKED if cid == "terminal-state" and str(receipt.get("state") or "").upper() == "BLOCKED" else INCOMPLETE
        return {
            "verdict": verdict,
            "failing_condition_id": cid,
            "conditions": conditions,
            "site": site,
            "source_id": receipt.get("source_id") or receipt.get("id"),
            "exit_code": receipt.get("exit_code"),
            "trace": [_trace(site, verdict, cid, {"reason": reason})],
        }

    def ok(cid: str, reason: str) -> None:
        conditions.append({"id": cid, "result": "PASS", "reason": reason})

    if not isinstance(receipt, dict):
        return fail("receipt-shape", "receipt is not an object")

    # Exit 0 alone must not short-circuit: evaluate artifact/sentinel even when rc==0.
    exit_code = receipt.get("exit_code")
    ok("exit-zero-never-sufficient", f"exit_code={exit_code!r} is recorded and ignored as a success signal")

    state = str(receipt.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return fail("terminal-state", f"self-declared {state}")
    if state not in {"SUCCESS", "COMPLETE", ""}:
        return fail("terminal-state", f"unusable terminal state {state!r}")
    ok("terminal-state", f"state={state or 'SUCCESS'}")

    path = _artifact_path(receipt)
    if path is None:
        return fail("artifact-declared", "no artifact_path")
    if not path.is_file():
        return fail("artifact-exists", f"missing {path}")
    ok("artifact-exists", str(path))

    raw = path.read_bytes()
    if len(raw) <= 0:
        return fail("artifact-nonempty", "empty artifact")
    ok("artifact-nonempty", f"bytes={len(raw)}")

    try:
        json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail("artifact-parses", type(exc).__name__)
    ok("artifact-parses", "json")

    sentinel = str(receipt.get("sentinel") or "")
    text = raw.decode("utf-8")
    if not sentinel:
        return fail("sentinel-present", "receipt names no sentinel")
    if sentinel not in text:
        return fail("sentinel-present", "sentinel not in artifact bytes")
    ok("sentinel-present", sentinel)

    return {
        "verdict": COMPLETE,
        "failing_condition_id": None,
        "conditions": conditions,
        "site": site,
        "source_id": receipt.get("source_id") or receipt.get("id"),
        "exit_code": exit_code,
        "trace": [_trace(site, COMPLETE, None)],
    }


def tally_sources(source_ids: list[str]) -> dict[str, Any]:
    counts = Counter(source_ids)
    tally_sum = len(source_ids)
    distinct = len(set(source_ids))
    doubled = [sid for sid, n in counts.items() if n > 1]
    return {
        "source_ids": list(source_ids),
        "counts_by_source": dict(counts),
        "tally_sum": tally_sum,
        "distinct_source_count": distinct,
        "double_counted_sources": doubled,
        "double_count": bool(doubled) or tally_sum != distinct,
        "formula": "tally_sum == distinct_source_count and max(counts.values(), default=0) <= 1",
        "arithmetic": f"{tally_sum} == {distinct} and double_counted={doubled}",
    }


def _as_receipt(child: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
    """Re-encode a child verdict as a receipt the SAME reducer can judge."""
    sid = str(original.get("source_id") or original.get("id") or child.get("source_id") or "child")
    if child["verdict"] == COMPLETE:
        return {
            "id": sid,
            "source_id": sid,
            "state": "SUCCESS",
            "exit_code": 0,
            "artifact_path": original.get("artifact_path"),
            "sentinel": original.get("sentinel"),
        }
    return {
        "id": sid,
        "source_id": sid,
        "state": "BLOCKED" if child["verdict"] == BLOCKED else "FAILED",
        "exit_code": original.get("exit_code", 0),
        "artifact_path": "command-center/p2-wave/probes/CNF-0095/fixtures/does-not-exist.json",
        "sentinel": "",
    }


def reduce_many(
    receipts: list[dict[str, Any]],
    *,
    site: str,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Fan-in: every child through reduce_completion; parent COMPLETE iff all are.

    Disagreement is recorded, never averaged. Double-counting is a failing condition
    even when every copy would otherwise be COMPLETE.
    """
    ids = list(source_ids if source_ids is not None else [str(r.get("source_id") or r.get("id") or i) for i, r in enumerate(receipts)])
    tally = tally_sources(ids)
    children: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for i, rec in enumerate(receipts):
        child_site = f"{site}[{i}:{ids[i] if i < len(ids) else i}]"
        child = reduce_completion(rec, site=child_site)
        children.append(child)
        traces.extend(child["trace"])

    complete_n = sum(1 for c in children if c["verdict"] == COMPLETE)
    blocked_n = sum(1 for c in children if c["verdict"] == BLOCKED)
    incomplete_n = sum(1 for c in children if c["verdict"] == INCOMPLETE)
    n = len(children)
    disagreement = complete_n > 0 and (blocked_n + incomplete_n) > 0

    if tally["double_count"]:
        verdict = INCOMPLETE
        failing = "double-counting"
    elif n == 0:
        verdict = INCOMPLETE
        failing = "empty-fanin"
    elif disagreement:
        verdict = INCOMPLETE
        failing = "disagreement-not-averaged"
    elif complete_n == n:
        verdict = COMPLETE
        failing = None
    elif blocked_n == n:
        verdict = BLOCKED
        failing = next(
            (c["failing_condition_id"] for c in children if c["verdict"] != COMPLETE),
            "child-blocked",
        )
    else:
        verdict = INCOMPLETE
        failing = next(
            (c["failing_condition_id"] for c in children if c["verdict"] != COMPLETE),
            "child-incomplete",
        )

    traces.append(
        _trace(
            site,
            verdict,
            failing,
            {
                "aggregator": "conjunction-not-average",
                "complete_n": complete_n,
                "n": n,
                "disagreement": disagreement,
                "reduce_many_id": id(reduce_many),
                "reduce_completion_id": id(reduce_completion),
            },
        )
    )

    first = receipts[0] if receipts else {}
    return {
        "verdict": verdict,
        "failing_condition_id": failing,
        "disagreement": disagreement,
        "complete_n": complete_n,
        "blocked_n": blocked_n,
        "incomplete_n": incomplete_n,
        "n": n,
        "tally": tally,
        "children": children,
        "trace": traces,
        "site": site,
        "same_predicate_id": id(reduce_completion),
        "same_reduce_many_id": id(reduce_many),
        "predicate_fingerprint": predicate_fingerprint(),
        "as_receipt": _as_receipt(
            {"verdict": verdict, "source_id": site},
            first if verdict == COMPLETE else {"source_id": site, "exit_code": 0},
        ),
    }


# Stable aliases so topology imports one object, not a wrapper.
FANIN = reduce_many
