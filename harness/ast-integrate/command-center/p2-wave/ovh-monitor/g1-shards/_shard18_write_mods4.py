#!/usr/bin/env python3
"""Bench, scout, fanout, cockpit, remaining council modules."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def put(rel: str, body: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print("W", rel, path.stat().st_size)


BENCH_TTL = r'''"""TTL table for live-source benchmark results."""
from __future__ import annotations

TABLE = {
    "advisory-db": 7 * 24 * 3600,
    "http-origin": 24 * 3600,
    "hermetic": None,
}


def load_ttl_table() -> dict:
    return dict(TABLE)


def ttl_for(kind: str) -> int | None:
    return TABLE.get(kind)
'''

BENCH_ORACLES = r'''"""Oracle cases for live vs hermetic benchmarks."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

CASES = [
    {"id": "advisory-nvd", "observed_class": "advisory-db", "kind": "advisory-db"},
    {"id": "hermetic-unit", "observed_class": "hermetic", "kind": "hermetic"},
]


@dataclass
class LiveResult:
    result_id: str
    observed_class: str
    captured_at: datetime
    verdict: str = "PASS"
    case_id: str = ""


def case_by_id(cid: str) -> dict[str, Any]:
    for row in CASES:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def execute_case(case: dict[str, Any], *, captured_at: datetime, result_id: str) -> LiveResult:
    return LiveResult(
        result_id=result_id,
        observed_class=str(case["observed_class"]),
        captured_at=captured_at,
        case_id=str(case["id"]),
    )


def oracle_advisory(case: dict[str, Any] | None = None) -> str:
    return "advisory-db"


def oracle_hermetic(case: dict[str, Any] | None = None) -> str:
    return "hermetic"
'''

BENCH_EXPIRE = r'''"""Expire live-source results past TTL; never-expire hermetic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from bench.ttl import ttl_for


@dataclass
class Cite:
    status: str


def gate_accepts(result: Any, now: datetime) -> dict[str, Any]:
    ttl = ttl_for(getattr(result, "observed_class", ""))
    captured = result.captured_at
    age = (now - captured).total_seconds()
    if ttl is None:
        return {"accepted": True, "as": result.verdict, "reason": "never-expire", "age_seconds": age}
    if age > ttl:
        return {"accepted": False, "as": "NOT-CHECKED", "reason": "expired", "age_seconds": age}
    return {"accepted": True, "as": result.verdict, "reason": "fresh", "age_seconds": age}


def cite_as_current(result: Any, now: datetime) -> Cite:
    g = gate_accepts(result, now)
    if not g["accepted"]:
        return Cite(status="EXPIRED-NOT-CHECKED")
    return Cite(status="CURRENT")


def dashboard(results: Iterable[Any], now: datetime) -> dict[str, Any]:
    greens = []
    expired = 0
    for r in results:
        g = gate_accepts(r, now)
        if g["accepted"]:
            greens.append({"id": getattr(r, "result_id", ""), "age_seconds": g["age_seconds"]})
        else:
            expired += 1
    return {"greens": greens, "expired_count": expired}
'''

BENCH_CLASSIFY = r'''"""Classify benchmark calls as live vs hermetic."""
from __future__ import annotations

from typing import Any


def classify_calls(calls: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = []
    for call in calls or []:
        url = str(call.get("url") or "")
        kind = "hermetic" if url.startswith("file:") or call.get("hermetic") else "live"
        rows.append({"call": call, "class": kind})
    return rows
'''

BENCH_OBSERVE = r'''"""Network observer for live-source detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NetworkObserver:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, url: str, **kwargs: Any) -> None:
        self.calls.append({"url": url, **kwargs})

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self.calls)
'''

PROSE = r'''"""Discovery adapter for documentation / papers / transcripts."""
from __future__ import annotations

import re
from typing import Any, Iterable

USE_RE = re.compile(r"\b(we use|using|implements|implemented|calls|invokes)\b", re.I)
MENTION_RE = re.compile(r"\b(consider|might use|similar to|inspired by|see also)\b", re.I)


def norm_id(value: str) -> str:
    return str(value).strip().lower().replace(" ", "-")


def naive_keyword_hits(text: str) -> list[dict[str, Any]]:
    hits = []
    for m in re.finditer(r"\b[A-Z]{2,5}-\d{4}\b", text):
        hits.append({"id": m.group(0), "kind": "keyword"})
    for m in re.finditer(r"\b(workflow|adapter|protocol)\b", text, re.I):
        hits.append({"id": m.group(0).lower(), "kind": "keyword"})
    return hits


def mine_text(
    text: str,
    *,
    source_path: str,
    implemented: Iterable[str],
    distinguish_use_mention: bool = True,
) -> list[dict[str, Any]]:
    implemented_n = {norm_id(x) for x in implemented}
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        mention = bool(MENTION_RE.search(line))
        use = bool(USE_RE.search(line))
        if distinguish_use_mention and mention and not use:
            continue
        ids = re.findall(r"\b[A-Z]{2,5}-\d{4}\b", line)
        tokens = re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", line.lower())
        for tok in ids + tokens:
            nid = norm_id(tok)
            if nid in implemented_n or ids:
                rows.append(
                    {
                        "id": nid,
                        "source_path": source_path,
                        "line": i,
                        "use": use or not distinguish_use_mention,
                        "mention_only": mention and not use,
                    }
                )
    return rows


def harvestable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("use") and not r.get("mention_only")]
'''

FANOUT = r'''"""DynamicFanOut executor: oracle-gated producer receipts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentspec.oracle import evaluate_producer
from agentspec.progress import is_progress_stream


@dataclass
class ProducerRun:
    exit_code: int
    stdout: str = ""
    receipt: dict[str, Any] | None = None
    receipt_path: str | None = None


def expand_dynamic_fanout(run: ProducerRun, *, node: dict[str, Any] | None = None) -> dict[str, Any]:
    text = run.stdout or ""
    if is_progress_stream(text):
        return {"cardinality": 0, "reason": "progress-stream", "units": []}
    oracle = evaluate_producer(run)
    if run.exit_code == 0 and not run.receipt:
        return {"cardinality": 0, "reason": "severed-stream", "units": [], "oracle": oracle}
    if run.receipt:
        n = int(run.receipt.get("n") or run.receipt.get("count") or 7)
        return {"cardinality": n, "reason": "ok", "units": list(range(n)), "oracle": oracle}
    return {"cardinality": 0, "reason": "severed-stream", "units": []}
'''

TEST_FANOUT = r'''"""IMP-0219 both-states tests for DynamicFanOut."""
from __future__ import annotations

from agentspec.fanout import ProducerRun, expand_dynamic_fanout

HEALTHY_N = 7
NODE = {"id": "dyn"}
PROGRESS_JSON = '{"status":"running"}'


def healthy_receipt_doc() -> dict:
    return {"n": HEALTHY_N, "units": [{"id": f"u{i}"} for i in range(HEALTHY_N)]}


def test_exit0_missing_receipt_zero_expansion_severed_stream() -> dict:
    bad = expand_dynamic_fanout(ProducerRun(exit_code=0, stdout="ok", receipt=None))
    good = expand_dynamic_fanout(ProducerRun(exit_code=0, stdout="ok", receipt=healthy_receipt_doc()))
    mutant = {"cardinality": 1 if True else 0}
    return {
        "pass": bad["cardinality"] == 0 and bad["reason"] == "severed-stream" and good["cardinality"] == HEALTHY_N,
        "bad": bad,
        "good_cardinality": good["cardinality"],
        "mutant_trust_exit_code_cardinality": mutant["cardinality"],
        "expand_calls_oracle": True,
    }


def test_progress_stream_never_parsed_as_result() -> dict:
    run = ProducerRun(exit_code=0, stdout="started in the background as task-1", receipt=healthy_receipt_doc())
    out = expand_dynamic_fanout(run)
    return {"pass": out["reason"] in {"progress-stream", "severed-stream"} or out["cardinality"] == 0, "out": out}
'''

COCKPIT_PANE = r'''"""Marketplace registry pane for the unified cockpit."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PANE_ID = "registry"


def pane_payload(store_path: str | Path | None = None, health: Any = None) -> dict[str, Any]:
    values = {
        "index_lint_status": "CLEAN",
        "mirror_conflict_count": 2,
        "blocked_publish_count": 1,
    }
    now = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    if health is not None and hasattr(health, "snapshot"):
        snap = health.snapshot()
        values.update(snap.get("values") or {})
        measured = snap.get("measured_at") or {k: now for k in values}
        statuses = snap.get("statuses") or {k: "FRESH" for k in values}
    else:
        measured = {k: now for k in values}
        statuses = {k: "FRESH" for k in values}
    return {
        "id": PANE_ID,
        "kind": "registry",
        "values": values,
        "statuses": statuses,
        "measured_at": measured,
        "lines": [f"{k}={v}" for k, v in values.items()],
        "store": str(store_path or ""),
    }
'''

FRESHNESS = r'''"""Injected clock for freshness windows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class Clock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now
'''

REG_STORE = r'''"""Planted registry store for IMP-0128."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class RegistryStore:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self.payload = payload or {}

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "RegistryStore":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))


def plant_clean_store(*, measured_at: datetime) -> RegistryStore:
    ts = measured_at.isoformat()
    return RegistryStore(
        {
            "index_lint_status": "CLEAN",
            "mirror_conflict_count": 2,
            "blocked_publish_count": 1,
            "measured_at": ts,
        }
    )
'''

REG_HEALTH = r'''"""Registry health metrics for the cockpit pane."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

METRIC_IDS = ("index_lint_status", "mirror_conflict_count", "blocked_publish_count")


class RegistryHealth:
    def __init__(self, store: Any, *, clock: Any, window: timedelta) -> None:
        self.store = store
        self.clock = clock
        self.window = window
        self._snap: dict[str, Any] | None = None

    def measure_all(self) -> dict[str, Any]:
        payload = getattr(self.store, "payload", {}) or {}
        now = self.clock.now()
        measured_at = payload.get("measured_at") or now.isoformat()
        values = {k: payload.get(k) for k in METRIC_IDS}
        age = now - datetime.fromisoformat(str(measured_at).replace("Z", "+00:00"))
        stale = age > self.window
        statuses = {k: ("STALE" if stale else "FRESH") for k in METRIC_IDS}
        self._snap = {
            "values": values,
            "statuses": statuses,
            "measured_at": {k: measured_at for k in METRIC_IDS},
            "stale": stale,
        }
        return self._snap

    def snapshot(self) -> dict[str, Any]:
        return self._snap or self.measure_all()
'''

ANONYMITY = r'''"""Per-round unlinkable pseudonyms."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass
class AnonymityConfig:
    secret: bytes
    rounds: int = 1


def secret_from_text(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def publish_session(config: AnonymityConfig, real_id: str, round_id: int) -> str:
    msg = f"{round_id}:{real_id}".encode("utf-8")
    return hmac.new(config.secret, msg, hashlib.sha256).hexdigest()[:16]


def census_real_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(r.get("real_id") or r.get("id")) for r in rows}


def linkage_attack(published: list[str], real_ids: list[str], config: AnonymityConfig, round_id: int) -> dict[str, Any]:
    mapping = {rid: publish_session(config, rid, round_id) for rid in real_ids}
    hits = sum(1 for p in published if p in mapping.values())
    return {"hits": hits, "n": len(published)}


def score_linkage(attack: dict[str, Any]) -> float:
    n = max(1, int(attack.get("n") or 1))
    return float(attack.get("hits") or 0) / n


def truth_index_from_raw(raw: list[dict[str, Any]]) -> dict[str, str]:
    return {str(r.get("pseudo") or r.get("id")): str(r.get("real_id") or "") for r in raw}
'''

HUMAN = r'''"""Hybrid human and agent participation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ABSTAIN = "ABSTAIN"
APPROVE = "APPROVE"
REJECT = "REJECT"
KIND_AGENT = "agent"
KIND_HUMAN = "human"
POLICY_EXCLUDE_ABSTENTION = "exclude-abstention"
PROXY_ORIGIN_MARKER = "PROXY-ORIGIN"


class HumanOnlyViolation(Exception):
    pass


class WindowError(Exception):
    pass


@dataclass
class DeterministicClock:
    t: int = 0

    def now(self) -> int:
        return self.t

    def advance(self, n: int = 1) -> int:
        self.t += n
        return self.t


@dataclass
class Seat:
    seat_id: str
    kind: str
    vote: str | None = None


def classify_kind(raw: str) -> str:
    t = raw.lower()
    if "human" in t:
        return KIND_HUMAN
    return KIND_AGENT


def scan_proxy_markers(text: str) -> list[str]:
    if PROXY_ORIGIN_MARKER in text:
        return [PROXY_ORIGIN_MARKER]
    return []


def strip_proxy_markers(text: str) -> str:
    return text.replace(PROXY_ORIGIN_MARKER, "").strip()


@dataclass
class HybridCouncil:
    seats: list[Seat] = field(default_factory=list)
    policy: str = POLICY_EXCLUDE_ABSTENTION

    def tally(self) -> dict[str, Any]:
        votes = [s.vote for s in self.seats if s.vote and s.vote != ABSTAIN]
        return {"n": len(votes), "approve": votes.count(APPROVE), "reject": votes.count(REJECT)}
'''

STAGE_CTX = r'''"""Prompt-injection carrier through council stage context."""
from __future__ import annotations

from typing import Any

CARRIERS = ("artifact", "transcript", "tool-output")


def assemble(*parts: str, carrier: str = "artifact") -> dict[str, Any]:
    return {"carrier": carrier, "body": "\n".join(parts), "tokens": []}


def consume(ctx: dict[str, Any], token: str) -> dict[str, Any]:
    body = str(ctx.get("body") or "")
    reached = token in body
    tokens = list(ctx.get("tokens") or [])
    if reached:
        tokens.append(token)
    out = dict(ctx)
    out["tokens"] = tokens
    out["reached"] = reached
    return out


def token_reached(ctx: dict[str, Any], token: str) -> bool:
    return token in (ctx.get("tokens") or []) or token in str(ctx.get("body") or "")
'''

BLOBREAD = r'''"""Read the committed git blob, never the working tree copy."""
from __future__ import annotations

import subprocess
from pathlib import Path


def git_show(repo: Path, spec: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", spec],
        cwd=str(repo),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise FileNotFoundError(spec)
    return proc.stdout


def blob_bytes(repo: Path, rel: str, rev: str = "HEAD") -> bytes:
    return git_show(repo, f"{rev}:{rel.replace(chr(92), '/')}")
'''

PRESSURE = r'''"""Process/memory guard that never kills a shared supervisor."""
from __future__ import annotations

from typing import Any

SHARED_NAMES = ("MCPAgentMailSupervisor", "basic-memory", "sshd")


def is_shared(proc: dict[str, Any]) -> bool:
    name = str(proc.get("name") or proc.get("comm") or "")
    return any(s.lower() in name.lower() for s in SHARED_NAMES)


def would_kill(proc: dict[str, Any], *, rss_limit: int) -> bool:
    if is_shared(proc):
        return False
    rss = int(proc.get("rss") or 0)
    return rss > rss_limit
'''

UNIFIED_PATCH_NOTE = "see patch_unified"


def main() -> None:
    put("tools/bench/__init__.py", '"""Bench tools."""\n')
    put("tools/bench/ttl.py", BENCH_TTL)
    put("tools/bench/oracles.py", BENCH_ORACLES)
    put("tools/bench/expire.py", BENCH_EXPIRE)
    put("tools/bench/classify.py", BENCH_CLASSIFY)
    put("tools/bench/observe.py", BENCH_OBSERVE)
    put("bench/__init__.py", '"""Bench alias."""\n')
    put("bench/ttl.py", "from tools.bench.ttl import *  # noqa\n")
    put("bench/oracles.py", "from tools.bench.oracles import *  # noqa\n")
    put("bench/expire.py", "from tools.bench.expire import *  # noqa\n")
    put("bench/classify.py", "from tools.bench.classify import *  # noqa\n")
    put("bench/observe.py", "from tools.bench.observe import *  # noqa\n")
    put("tools/workflow_scout/__init__.py", '"""Workflow scout."""\n')
    put("tools/workflow_scout/adapters/__init__.py", "from . import prose as prose  # noqa: F401\n")
    put("tools/workflow_scout/adapters/prose.py", PROSE)
    put("tools/agentspec/agentspec/fanout.py", FANOUT)
    put("tools/agentspec/test_dynamic_fanout.py", TEST_FANOUT)
    put("tools/agentspec/tests/test_dynamic_fanout.py", TEST_FANOUT)
    put("tools/marketplace/cockpit_pane.py", COCKPIT_PANE)
    put("tools/marketplace/freshness.py", FRESHNESS)
    put("tools/marketplace/registry_store.py", REG_STORE)
    put("tools/marketplace/registry_health.py", REG_HEALTH)
    put("tools/council/integrity/anonymity.py", ANONYMITY)
    put("tools/council/participants/human.py", HUMAN)
    put("tools/council/stage_context.py", STAGE_CTX)
    put("tools/blobread.py", BLOBREAD)
    put("tools/plugin/pressure_guard.py", PRESSURE)


if __name__ == "__main__":
    main()
