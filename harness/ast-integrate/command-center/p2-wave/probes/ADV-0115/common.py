"""ADV-0115 shared constants, catalogue, scoring, and stats.

Measures the live Phase-8 capability router (tools/router/injection_budget.py)
rather than a reimplementation of the packer.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from router.injection_budget import (  # noqa: E402
    HARD_CEILING_TOKENS,
    Capability,
    budget_inject,
    naive_inject,
)
from router.tokenizer import count_tokens  # noqa: E402

UNIT_ID = "ADV-0115"
OUT_REL = "command-center/adversarial/ADV-0115-router-overhead-and-context-tax.json"
SCHEMA_DECLARED = "command-center/schema/fault-injection-run.schema.json"
PROBE1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0115/probe1_cost_curve.py"
)
PROBE2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0115/probe2_quality_curve.py"
)

# Catalog completion_sentinel, copied verbatim. G-1 requires this string in the artifact.
SENTINEL = (
    "SUCCESS:ADV-0115 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0115 <reason>."
)

QUESTION = (
    "What is the per-turn latency and token cost the capability router adds "
    "when the full skill/plugin/workflow catalogue is installed, and at what "
    "catalogue size does injection start displacing task context?"
)

# Five catalogue sizes, including the harvest-era 912 and a point past it.
SIZES = (60, 200, 500, 912, 1368)
N_TASKS = 60
N_TRIALS = 9
WARMUP = 1
TASK_SET_REL = "command-center/p2-wave/probes/ADV-0115/task-set.json"
SCORE_THRESHOLD = 0.5
HOT_BODY_WORDS = 36
PAYLOAD_WORD = "injectpayloadtoken"

# Topic stems so gold markers are distinctive and neighbours share three tokens.
_A = (
    "extract",
    "parse",
    "index",
    "route",
    "fuse",
    "rank",
    "pack",
    "scan",
    "hash",
    "diff",
)
_B = (
    "invoice",
    "skill",
    "plugin",
    "workflow",
    "ledger",
    "hook",
    "schema",
    "token",
    "probe",
    "gate",
)
_C = (
    "pdf",
    "json",
    "yaml",
    "markdown",
    "binary",
    "unicode",
    "posix",
    "win32",
    "http",
    "git",
)
_D = (
    "totals",
    "frontmatter",
    "ceiling",
    "budget",
    "latency",
    "quality",
    "flood",
    "drift",
    "collision",
    "closure",
)


def skip_dir(path: Path) -> bool:
    banned = {"__pycache__", ".git", "node_modules", ".venv", ".mypy_cache"}
    return any(part in banned for part in path.parts)


def task_tokens(i: int) -> list[str]:
    return [
        _A[i % 10],
        _B[(i // 10) % 10],
        _C[(i * 3) % 10],
        f"goldmark{i:02d}",
    ]


def build_task_set() -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for i in range(N_TASKS):
        tokens = task_tokens(i)
        tasks.append(
            {
                "id": f"T{i:02d}",
                "gold_id": f"gold-{i:02d}",
                "tokens": tokens,
                "query": " ".join(tokens),
            }
        )
    return tasks


def write_task_set(path: Path | None = None) -> list[dict[str, Any]]:
    tasks = build_task_set()
    dest = path or (REPO / TASK_SET_REL)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"tasks": tasks, "n": len(tasks)}, indent=1) + "\n", encoding="utf-8")
    return tasks


def load_task_set() -> list[dict[str, Any]]:
    path = REPO / TASK_SET_REL
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        tasks = doc.get("tasks") or []
        if len(tasks) == N_TASKS:
            return tasks
    return write_task_set()


def live_platform_records(repo: Path | None = None) -> list[dict[str, str]]:
    """Enumerate skill/plugin/workflow-like files actually on this tree."""
    root = repo or REPO
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(rel: str, kind: str) -> None:
        rel = rel.replace("\\", "/")
        if rel in seen:
            return
        seen.add(rel)
        records.append({"id": rel, "kind": kind, "path": rel})

    tools = root / "tools"
    if tools.is_dir():
        for path in sorted(tools.rglob("*.py")):
            if skip_dir(path):
                continue
            add(path.relative_to(root).as_posix(), "tools-python")
        bp = tools / "blueprints" / "library"
        if bp.is_dir():
            for path in sorted(bp.rglob("*")):
                if path.is_file() and not skip_dir(path):
                    add(path.relative_to(root).as_posix(), "blueprint")
    for path in sorted(root.rglob("SKILL.md")):
        if skip_dir(path):
            continue
        add(path.relative_to(root).as_posix(), "skill")
    plugin = tools / "plugin"
    if plugin.is_dir():
        for path in sorted(plugin.rglob("*.py")):
            if skip_dir(path):
                continue
            add(path.relative_to(root).as_posix(), "plugin")
    return records


def _hot_body(tag: str) -> str:
    return " ".join([PAYLOAD_WORD] * HOT_BODY_WORDS + [tag])


def _gold_body(tokens: list[str]) -> str:
    filler = " ".join([PAYLOAD_WORD] * 8)
    return f"{filler} {' '.join(tokens)}"


def _neighbour_body(tokens: list[str], k: int) -> str:
    shared = tokens[:3]
    filler = " ".join([PAYLOAD_WORD] * 8)
    return f"{filler} {' '.join(shared)} neighbour{k:03d}"


def catalogue_for_cost(n: int, live: list[dict[str, str]] | None = None) -> list[Capability]:
    """Static-score catalogue for a representative turn (probe 1).

    Hot (above-threshold) count grows with n, so unbounded injection can flood
    while the live budgeter stays under HARD_CEILING_TOKENS.
    """
    n_hot = min(n, 20 + n // 20)
    caps: list[Capability] = []
    live = live or []
    for i in range(n):
        if i < n_hot:
            score = 0.95 - (i * 0.002)
            if score < SCORE_THRESHOLD:
                score = SCORE_THRESHOLD + 0.01
            body = _hot_body(f"hot{i:04d}")
            cid = f"hot-{i:04d}"
        elif i < len(live) + n_hot:
            rec = live[(i - n_hot) % max(1, len(live))] if live else None
            cid = f"live-{(i - n_hot):04d}"
            if rec:
                cid = f"live:{rec['id'][:80]}"
            score = 0.20
            body = f"live record {cid}"
        else:
            cid = f"cold-{i:04d}"
            score = 0.15
            body = f"cold filler {cid}"
        caps.append(Capability(capability_id=cid, score=float(score), body=body))
    return caps


def catalogue_for_quality(
    n: int, tasks: list[dict[str, Any]], live: list[dict[str, str]] | None = None
) -> list[dict[str, Any]]:
    """Template rows (not yet scored) for the fixed 60-task quality curve."""
    rows: list[dict[str, Any]] = []
    for i, task in enumerate(tasks):
        rows.append(
            {
                "capability_id": task["gold_id"],
                "role": "gold",
                "task_index": i,
                "body": _gold_body(list(task["tokens"])),
            }
        )
    n_neighbours = max(0, n // 40)
    for k in range(n_neighbours):
        task = tasks[k % len(tasks)]
        rows.append(
            {
                "capability_id": f"near-{k:04d}",
                "role": "neighbour",
                "task_index": k % len(tasks),
                "body": _neighbour_body(list(task["tokens"]), k),
            }
        )
    live = live or []
    while len(rows) < n:
        idx = len(rows)
        if live and (idx % 7 == 0):
            rec = live[idx % len(live)]
            rows.append(
                {
                    "capability_id": f"liveq-{idx:04d}:{rec['id'][:60]}",
                    "role": "live",
                    "task_index": None,
                    "body": f"live {rec['kind']} {rec['id']}",
                }
            )
        else:
            rows.append(
                {
                    "capability_id": f"dist-{idx:04d}",
                    "role": "distractor",
                    "task_index": None,
                    "body": f"distractor {idx} {PAYLOAD_WORD}",
                }
            )
    return rows[:n]


def score_for_task(rows: list[dict[str, Any]], task: dict[str, Any]) -> list[Capability]:
    gold_id = task["gold_id"]
    task_i = int(task["id"][1:])
    caps: list[Capability] = []
    for row in rows:
        role = row["role"]
        if row["capability_id"] == gold_id:
            score = 0.99
        elif role == "neighbour" and row.get("task_index") == task_i:
            score = 0.82
        elif role == "gold":
            score = 0.42
        else:
            score = 0.18
        caps.append(
            Capability(
                capability_id=row["capability_id"],
                score=score,
                body=row["body"],
            )
        )
    return caps


def overlap(task_tokens_list: list[str], body: str) -> int:
    body_tokens = set(body.split())
    return sum(1 for t in task_tokens_list if t in body_tokens)


def answer_from_injection(task: dict[str, Any], selected: list[Capability]) -> str | None:
    if not selected:
        return None
    ranked = sorted(
        selected,
        key=lambda c: (-overlap(list(task["tokens"]), c.body), c.capability_id),
    )
    return ranked[0].capability_id


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        raise ValueError("empty sample")
    ordered = sorted(xs)
    if len(ordered) == 1:
        return float(ordered[0])
    idx = (p / 100.0) * (len(ordered) - 1)
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return float(ordered[lo])
    frac = idx - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def summarize_ms(samples_ms: list[float]) -> dict[str, float]:
    return {
        "n": float(len(samples_ms)),
        "mean": float(statistics.fmean(samples_ms)),
        "stdev": float(statistics.pstdev(samples_ms) if len(samples_ms) > 1 else 0.0),
        "p10": percentile(samples_ms, 10),
        "p50": percentile(samples_ms, 50),
        "p90": percentile(samples_ms, 90),
        "min": float(min(samples_ms)),
        "max": float(max(samples_ms)),
    }


def flood_red(measured_tokens: int, ceiling: int = HARD_CEILING_TOKENS) -> bool:
    return int(measured_tokens) > int(ceiling)
