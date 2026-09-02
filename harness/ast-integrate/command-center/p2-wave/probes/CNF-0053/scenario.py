"""CNF-0053 paths, commit ids, and latency-budget search (no invented threshold)."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/confirmation/CNF-0053-startup-overhead.json"
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
BEFORE_ID = "CNF-0053-before"
AFTER_ID = "CNF-0053-after"
BEFORE_SRC = HERE / "fixtures" / "commits" / "before"
AFTER_SRC = HERE / "fixtures" / "commits" / "after"
ENTRY = "tool_startup.entry"
REPS = 11
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0053 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the per-module cost table "
    "exists for both commits and at least one cold-cache measurement is included. "
    "Any other terminal state is FAILED:CNF-0053 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Did the change make the tool slower to start? Measure cold-start and "
    "import time before and after with repetitions, and answer: what is the "
    "delta in milliseconds, which imported module accounts for the largest "
    "share of any increase, and does the delta exceed the declared latency budget?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0053/probe1_interleaved_importtime.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0053/probe2_cold_cache_budget.py"
)

BUDGET_NAME_HINTS = ("latency-budget", "latency_budget", "startup-budget", "startup_budget")


def find_latency_budget(repo: Path = REPO) -> dict:
    """Search the worktree for a declared latency budget. Never invent one."""
    hits: list[str] = []
    roots = [repo / "tools", repo / "command-center"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(repo).as_posix()
            if path.name == "WORK-UNIT-CATALOG.json":
                continue
            if "CNF-0053" in rel and path.suffix == ".json":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 400_000:
                continue
            name = path.name.lower()
            if any(h in name for h in BUDGET_NAME_HINTS):
                hits.append(rel)
                continue
            if path.suffix.lower() not in {".json", ".yml", ".yaml", ".toml", ".md", ".txt"}:
                continue
            if "budget" not in name and "sla" not in name:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = text.lower()
            if "latency budget" in low or "startup budget" in low:
                hits.append(rel)
    declared = bool(hits)
    if declared:
        return {
            "declared": True,
            "status": "NOT-CHECKED",
            "hits": hits,
            "reason": (
                "name-matched budget-like files exist but none declare a numeric "
                "startup/import latency threshold for this tool; not invented"
            ),
        }
    return {
        "declared": False,
        "status": "NOT-CHECKED",
        "hits": [],
        "reason": (
            "no latency budget file or numeric startup threshold is declared in "
            "tools/ or command-center/ on this worktree; NOT-CHECKED rather than "
            "an invented threshold"
        ),
    }
