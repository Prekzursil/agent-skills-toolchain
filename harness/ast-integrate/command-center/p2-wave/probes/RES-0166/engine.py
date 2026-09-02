#!/usr/bin/env python3
"""RES-0166 topology comparison: live fixture + Goose-threshold lead/worker.

Discrete-tick simulator. Numbers are computed. A happy-path-only ranking is
not a complete comparison (hung-worker injection is required).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LINEAGE_PATH = HERE / "fixtures" / "sources" / "LINEAGE.json"
ARTIFACT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0166-suborchestrator-topology-comparison.json"
)
SCHEMA_REL = "command-center/p2-wave/probes/RES-0166/design-spec.schema.json"
SENTINEL = "SUCCESS:RES-0166"
UNIT = "RES-0166"

# Goose lead/worker at commit 58f3cc9e (aaif-goose/goose, formerly block/goose).
GOOSE_COMMIT = "58f3cc9e"
GOOSE_LEAD_TURNS = 3
GOOSE_FAILURE_THRESHOLD = 2
GOOSE_FALLBACK_TURNS = 2
LEAD_TOKEN_MULT = 3
WORKER_TOKEN_MULT = 1
HUNG_DETECT_TICKS = 3
TICK_LIMIT = 24
TOPOLOGIES = ("flat", "lead-worker", "tree", "hierarchical-fanin")

QUESTION = (
    "Design and specify the comparison that would decide our topology - what "
    "is measured (time to first finding, total distinct findings, deadlock "
    "rate, token cost, recovery from a hung worker), on what fixed task set, "
    "with what controls - and what does the existing evidence already say "
    "about lead-worker escalation thresholds?"
)

# Fixed task set. Hang flags fire only when inject_hung=True.
TASKS: tuple[dict[str, Any], ...] = (
    {
        "id": "T-SCAN",
        "title": "parallel extract of three distinct findings",
        "items": (
            {"id": "F-SCAN-A", "worker": "W0", "ticks": 2, "fails": 0},
            {"id": "F-SCAN-B", "worker": "W1", "ticks": 2, "fails": 0},
            {"id": "F-SCAN-C", "worker": "W2", "ticks": 3, "fails": 0},
        ),
    },
    {
        "id": "T-HANG",
        "title": "one worker never heartbeats (hung-worker injection)",
        "items": (
            {"id": "F-HANG-A", "worker": "W0", "ticks": 2, "fails": 0},
            {"id": "F-HANG-B", "worker": "W1", "ticks": 4, "fails": 0, "hang": True},
        ),
    },
    {
        "id": "T-FAIL2",
        "title": "two consecutive task failures then success (Goose threshold)",
        "items": (
            {"id": "F-FAIL2", "worker": "W2", "ticks": 2, "fails": 2},
        ),
    },
    {
        "id": "T-DEADLOCK",
        "title": "cyclic wait between W0 and W1",
        "items": (
            {"id": "F-DL-A", "worker": "W0", "ticks": 2, "fails": 0, "wait": "W1"},
            {"id": "F-DL-B", "worker": "W1", "ticks": 2, "fails": 0, "wait": "W0"},
        ),
        "deadlock": True,
    },
    {
        "id": "T-COST",
        "title": "long exploratory scan (token-cost instrument)",
        "items": (
            {"id": "F-COST", "worker": "W3", "ticks": 8, "fails": 0, "token_mult": 2},
        ),
    },
    {
        "id": "T-RECOVER",
        "title": "remaining items must finish after a hung worker is removed",
        "items": (
            {"id": "F-REC-A", "worker": "W0", "ticks": 2, "fails": 0},
            {"id": "F-REC-B", "worker": "W1", "ticks": 3, "fails": 0, "hang": True},
            {"id": "F-REC-C", "worker": "W2", "ticks": 2, "fails": 0},
        ),
    },
)

HUNG_TASK_IDS = frozenset({"T-HANG", "T-RECOVER"})
SUBTREE_A = frozenset({"W0", "W1"})
SUBTREE_B = frozenset({"W2", "W3"})

METRICS = (
    {
        "id": "time_to_first_finding",
        "instrument": (
            "min discrete tick at which a canonical finding id is accepted "
            "(committed, not a draft buffer)"
        ),
        "known_failure_mode": (
            "clock skew or counting an uncommitted draft as a finding "
            "under-reports TTFF; wall-clock without a shared tick source "
            "is not this instrument"
        ),
    },
    {
        "id": "total_distinct_findings",
        "instrument": (
            "cardinality of the canonical finding-id set after collapsing "
            "paraphrase duplicates"
        ),
        "known_failure_mode": (
            "raw string uniqueness inflates the count when two workers "
            "emit paraphrase duplicates of the same id"
        ),
    },
    {
        "id": "deadlock_rate",
        "instrument": (
            "fraction of deadlock-capable tasks that end with a wait-for "
            "cycle and zero progress until TICK_LIMIT"
        ),
        "known_failure_mode": (
            "classifying a hung worker as deadlock (or a timeout as a cycle) "
            "confounds two failure classes"
        ),
    },
    {
        "id": "token_cost",
        "instrument": (
            "sum of billed role-ticks (lead tick x3, worker tick x1, extra "
            "item token_mult) including retries and fallback turns"
        ),
        "known_failure_mode": (
            "omitting retry/fallback tokens or counting a hung slot after "
            "kill as still billing"
        ),
    },
    {
        "id": "recovery_from_hung_worker",
        "instrument": (
            "fraction of hung-injected tasks whose full required finding "
            "set is accepted after watchdog detect + reassignment or "
            "equivalent"
        ),
        "known_failure_mode": (
            "counting the hung worker's partial buffer as recovered, or "
            "vacuous 100% on a happy-path arm with no hang"
        ),
    },
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_lineage() -> dict[str, Any]:
    return json.loads(LINEAGE_PATH.read_text(encoding="utf-8"))


def verify_lineage() -> list[dict[str, Any]]:
    doc = load_lineage()
    rows = []
    for src in doc.get("sources") or []:
        if not isinstance(src, dict):
            continue
        rel = str(src.get("path") or "")
        path = REPO / rel
        present = path.is_file()
        live = digest_file(path) if present else None
        recorded = src.get("sha256")
        rows.append(
            {
                "file": src.get("file"),
                "path": rel,
                "present": present,
                "match": bool(present and recorded and live == recorded),
                "live_sha256": live,
                "recorded_sha256": recorded,
                "http_status": src.get("http_status"),
                "resolved_url": src.get("resolved_url"),
                "requested_url": src.get("requested_url"),
                "fetch_timestamp": src.get("fetch_timestamp"),
                "bytes": src.get("bytes"),
            }
        )
    return rows


def source_by_file(name: str) -> dict[str, Any]:
    for src in load_lineage().get("sources") or []:
        if src.get("file") == name:
            return src
    raise KeyError(name)


def file_has(name: str, needle: str) -> bool:
    path = REPO / source_by_file(name)["path"]
    return needle in path.read_text(encoding="utf-8", errors="replace")


def line_has(rel: str, line_no: int, needle: str) -> bool:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    idx = line_no - 1
    if idx < 0 or idx >= len(lines):
        return False
    return needle in lines[idx]


def _item_active(item: dict[str, Any], inject_hung: bool) -> dict[str, Any]:
    row = dict(item)
    row["hang"] = bool(inject_hung and item.get("hang"))
    return row


def _run_items_flat(items: list[dict[str, Any]], deadlock: bool) -> dict[str, Any]:
    """All workers in parallel; fan-in waits for every assigned worker."""
    findings: list[str] = []
    first = None
    tokens = 0
    deadlock_hit = False
    complete = True
    recovered = True
    t = 0
    if deadlock:
        deadlock_hit = True
        complete = False
        recovered = False
        tokens += TICK_LIMIT * WORKER_TOKEN_MULT * 2
        t = TICK_LIMIT
        return _pack(findings, first, tokens, deadlock_hit, complete, recovered, t)

    for it in items:
        mult = int(it.get("token_mult") or 1)
        fails = int(it.get("fails") or 0)
        work = int(it["ticks"])
        if it.get("hang"):
            tokens += HUNG_DETECT_TICKS * WORKER_TOKEN_MULT * mult
            tokens += (TICK_LIMIT - HUNG_DETECT_TICKS) * WORKER_TOKEN_MULT
            complete = False
            recovered = False
            t = max(t, TICK_LIMIT)
            continue
        spent = fails + work
        tokens += spent * WORKER_TOKEN_MULT * mult
        done_at = spent
        findings.append(it["id"])
        first = done_at if first is None else min(first, done_at)
        t = max(t, done_at)
    return _pack(findings, first, tokens, deadlock_hit, complete, recovered, t)


def _run_items_lead(items: list[dict[str, Any]], deadlock: bool) -> dict[str, Any]:
    """Goose-style: lead for N turns, then workers; 2 consecutive failures escalate."""
    findings: list[str] = []
    first = None
    tokens = GOOSE_LEAD_TURNS * LEAD_TOKEN_MULT
    t = GOOSE_LEAD_TURNS
    deadlock_hit = False
    complete = True
    recovered = True
    if deadlock:
        tokens += GOOSE_FALLBACK_TURNS * LEAD_TOKEN_MULT
        t += GOOSE_FALLBACK_TURNS
        for it in items:
            work = int(it["ticks"])
            tokens += work * WORKER_TOKEN_MULT
            t += work
            findings.append(it["id"])
            first = t if first is None else min(first, t)
        return _pack(findings, first, tokens, False, True, True, t)

    for it in items:
        mult = int(it.get("token_mult") or 1)
        fails = int(it.get("fails") or 0)
        work = int(it["ticks"])
        if it.get("hang"):
            tokens += HUNG_DETECT_TICKS * WORKER_TOKEN_MULT
            consec = 1
            if consec < GOOSE_FAILURE_THRESHOLD:
                tokens += HUNG_DETECT_TICKS * WORKER_TOKEN_MULT
                consec += 1
            tokens += GOOSE_FALLBACK_TURNS * LEAD_TOKEN_MULT
            t += HUNG_DETECT_TICKS + GOOSE_FALLBACK_TURNS + work
            tokens += work * WORKER_TOKEN_MULT * mult
            findings.append(it["id"])
            first = t if first is None else min(first, t)
            continue
        if fails >= GOOSE_FAILURE_THRESHOLD:
            tokens += GOOSE_FAILURE_THRESHOLD * WORKER_TOKEN_MULT * mult
            tokens += GOOSE_FALLBACK_TURNS * LEAD_TOKEN_MULT
            t += GOOSE_FAILURE_THRESHOLD + GOOSE_FALLBACK_TURNS + work
            tokens += work * LEAD_TOKEN_MULT * mult
        else:
            spent = fails + work
            tokens += spent * WORKER_TOKEN_MULT * mult
            t += spent
        findings.append(it["id"])
        first = t if first is None else min(first, t)
    return _pack(findings, first, tokens, deadlock_hit, complete, recovered, t)


def _run_items_tree(items: list[dict[str, Any]], deadlock: bool) -> dict[str, Any]:
    """Two sub-leads. Hung leaf is reassigned inside its subtree; siblings continue."""
    findings: list[str] = []
    first = None
    tokens = 2 * LEAD_TOKEN_MULT
    t = 1
    if deadlock:
        tokens += GOOSE_FALLBACK_TURNS * LEAD_TOKEN_MULT
        t += GOOSE_FALLBACK_TURNS
        for it in items:
            work = int(it["ticks"])
            tokens += work * WORKER_TOKEN_MULT
            t = max(t, work + GOOSE_FALLBACK_TURNS)
            findings.append(it["id"])
            first = work if first is None else min(first, work)
        return _pack(findings, first, tokens, False, True, True, t)

    done_at = []
    complete = True
    recovered = True
    for it in items:
        mult = int(it.get("token_mult") or 1)
        fails = int(it.get("fails") or 0)
        work = int(it["ticks"])
        if it.get("hang"):
            tokens += HUNG_DETECT_TICKS * WORKER_TOKEN_MULT
            tokens += GOOSE_FALLBACK_TURNS * LEAD_TOKEN_MULT
            tokens += work * WORKER_TOKEN_MULT * mult
            at = HUNG_DETECT_TICKS + GOOSE_FALLBACK_TURNS + work
            findings.append(it["id"])
            done_at.append(at)
            first = at if first is None else min(first, at)
            continue
        spent = fails + work
        tokens += spent * WORKER_TOKEN_MULT * mult
        done_at.append(spent)
        findings.append(it["id"])
        first = spent if first is None else min(first, spent)
    t = max(done_at) if done_at else t
    return _pack(findings, first, tokens, False, complete, recovered, t)


def _run_items_hier(items: list[dict[str, Any]], deadlock: bool) -> dict[str, Any]:
    """CNF-0095 conjunction fan-in: any TIMEOUT/INCOMPLETE child keeps parent incomplete.

    No parent retry. Hung or deadlock child => parent not complete.
    Sibling findings still count.
    """
    findings: list[str] = []
    first = None
    tokens = 0
    complete = True
    recovered = True
    deadlock_hit = False
    t = 0
    if deadlock:
        deadlock_hit = True
        complete = False
        recovered = False
        tokens += TICK_LIMIT * WORKER_TOKEN_MULT
        for it in items:
            if it["worker"] not in SUBTREE_A:
                work = int(it["ticks"])
                tokens += work * WORKER_TOKEN_MULT
                findings.append(it["id"])
                first = work if first is None else min(first, work)
                t = max(t, work)
        t = max(t, TICK_LIMIT)
        return _pack(findings, first, tokens, deadlock_hit, complete, recovered, t)

    for it in items:
        mult = int(it.get("token_mult") or 1)
        fails = int(it.get("fails") or 0)
        work = int(it["ticks"])
        if it.get("hang"):
            tokens += HUNG_DETECT_TICKS * WORKER_TOKEN_MULT
            complete = False
            recovered = False
            t = max(t, HUNG_DETECT_TICKS)
            continue
        spent = fails + work
        tokens += spent * WORKER_TOKEN_MULT * mult
        findings.append(it["id"])
        first = spent if first is None else min(first, spent)
        t = max(t, spent)
    return _pack(findings, first, tokens, deadlock_hit, complete, recovered, t)


def _pack(
    findings: list[str],
    first: int | None,
    tokens: int,
    deadlock_hit: bool,
    complete: bool,
    recovered: bool,
    t: int,
) -> dict[str, Any]:
    return {
        "findings": findings,
        "ttff": first,
        "tokens": tokens,
        "deadlock": deadlock_hit,
        "complete": complete,
        "recovered": recovered,
        "ticks": t,
    }


RUNNERS = {
    "flat": _run_items_flat,
    "lead-worker": _run_items_lead,
    "tree": _run_items_tree,
    "hierarchical-fanin": _run_items_hier,
}


def run_topology(topology: str, inject_hung: bool, inject_deadlock: bool) -> dict[str, Any]:
    runner = RUNNERS[topology]
    tasks_out = []
    all_findings: list[str] = []
    ttffs: list[int] = []
    tokens = 0
    deadlock_n = 0
    deadlock_capable = 0
    hung_n = 0
    hung_recovered = 0
    for spec in TASKS:
        deadlock = bool(inject_deadlock and spec.get("deadlock"))
        if spec.get("deadlock"):
            deadlock_capable += 1
        items = [_item_active(it, inject_hung) for it in spec["items"]]
        row = runner(items, deadlock)
        row["task_id"] = spec["id"]
        row["required"] = [it["id"] for it in spec["items"]]
        row["hung_injected"] = bool(inject_hung and spec["id"] in HUNG_TASK_IDS)
        tasks_out.append(row)
        all_findings.extend(row["findings"])
        if row["ttff"] is not None:
            ttffs.append(row["ttff"])
        tokens += row["tokens"]
        if row["deadlock"]:
            deadlock_n += 1
        if row["hung_injected"]:
            hung_n += 1
            required = set(row["required"])
            got = set(row["findings"])
            if required <= got and row["complete"]:
                hung_recovered += 1
    distinct = sorted(set(all_findings))
    return {
        "topology": topology,
        "inject_hung": inject_hung,
        "inject_deadlock": inject_deadlock,
        "tasks": tasks_out,
        "time_to_first_finding": min(ttffs) if ttffs else None,
        "total_distinct_findings": len(distinct),
        "distinct_finding_ids": distinct,
        "deadlock_rate": (deadlock_n / deadlock_capable) if deadlock_capable else 0.0,
        "token_cost": tokens,
        "recovery_from_hung_worker": (hung_recovered / hung_n) if hung_n else None,
        "hung_tasks": hung_n,
        "hung_recovered": hung_recovered,
        "all_complete": all(t["complete"] for t in tasks_out),
    }


def _rank(rows: list[dict[str, Any]], *, hung_arm: bool) -> list[str]:
    """Hung arm: recovery desc, deadlock_rate asc, tokens asc. Happy: tokens asc, ttff asc."""

    def key(r: dict[str, Any]) -> tuple:
        rec = r["recovery_from_hung_worker"]
        rec_v = -1.0 if rec is None else float(rec)
        ttff = r["time_to_first_finding"] if r["time_to_first_finding"] is not None else 10**9
        if hung_arm:
            return (-rec_v, r["deadlock_rate"], r["token_cost"], ttff, -r["total_distinct_findings"])
        return (r["token_cost"], ttff, -r["total_distinct_findings"], r["deadlock_rate"])

    return [r["topology"] for r in sorted(rows, key=key)]


def run_comparison() -> dict[str, Any]:
    happy = [run_topology(t, False, False) for t in TOPOLOGIES]
    hung = [run_topology(t, True, True) for t in TOPOLOGIES]
    happy_rank = _rank(happy, hung_arm=False)
    hung_rank = _rank(hung, hung_arm=True)
    happy_only_valid = False
    return {
        "task_ids": [t["id"] for t in TASKS],
        "topologies": list(TOPOLOGIES),
        "goose_threshold_used": {
            "lead_turns": GOOSE_LEAD_TURNS,
            "failure_threshold": GOOSE_FAILURE_THRESHOLD,
            "fallback_turns": GOOSE_FALLBACK_TURNS,
            "commit": GOOSE_COMMIT,
        },
        "arms": {
            "happy": {
                "id": "happy-path",
                "inject_hung": False,
                "inject_deadlock": False,
                "rows": happy,
                "ranking": happy_rank,
            },
            "hung_injection": {
                "id": "hung-worker-injection",
                "inject_hung": True,
                "inject_deadlock": True,
                "rows": hung,
                "ranking": hung_rank,
            },
        },
        "happy_path_only_is_complete_comparison": happy_only_valid,
        "rankings_differ": happy_rank != hung_rank,
        "happy_winner": happy_rank[0],
        "hung_winner": hung_rank[0],
        "negative_control": {
            "id": "NC-HUNG-INJECTION-REQUIRED",
            "fires_on": "a ranking that uses only the happy-path arm",
            "silent_on": "a ranking that includes the hung-worker injection arm",
            "happy_path_only_accepted": happy_only_valid,
            "injection_changed_winner": happy_rank[0] != hung_rank[0],
        },
    }


def mutant_happy_path_only_accepted(matrix: dict[str, Any]) -> bool:
    """Forbidden model: treat happy-path ranking as the topology decision."""
    fake = dict(matrix)
    fake["happy_path_only_is_complete_comparison"] = True
    fake["decision"] = matrix["happy_winner"]
    return fake["happy_path_only_is_complete_comparison"] is True


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "topology": row["topology"],
        "time_to_first_finding": row["time_to_first_finding"],
        "total_distinct_findings": row["total_distinct_findings"],
        "distinct_finding_ids": row["distinct_finding_ids"],
        "deadlock_rate": row["deadlock_rate"],
        "token_cost": row["token_cost"],
        "recovery_from_hung_worker": row["recovery_from_hung_worker"],
        "all_complete": row["all_complete"],
        "hung_tasks": row["hung_tasks"],
        "hung_recovered": row["hung_recovered"],
        "task_complete": {t["task_id"]: t["complete"] for t in row["tasks"]},
        "task_findings": {t["task_id"]: t["findings"] for t in row["tasks"]},
    }
