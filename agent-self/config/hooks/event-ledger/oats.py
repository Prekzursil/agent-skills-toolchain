#!/usr/bin/env python
"""oats.py — Tier-3 self-learning scaffold (OATS: Online Adaptive Tool Selection).

This module becomes active once >=100 'selection' events are recorded in the ledger.
Until then it runs cleanly and prints an inert status message.

HOW OATS WORKS (embedding-nudge plan):
    Each 'selection' event carries:
        query        : str — the user query / task description text
        chosen_tool  : str — the tool/skill the agent selected
        success      : bool — did the invocation succeed?

    Two centroid pools are maintained in a compact JSON file:
        positive centroids  Q+  — embeddings of queries where the tool WORKED
        negative centroids  Q-  — embeddings of queries where the tool FAILED

    The embedding for a candidate tool is nudged after each batch:
        ê  =  (1 - α) * e  +  α * mean(Q+)  -  β * mean(Q-)
        α = 0.3   (positive pull — moderately strong)
        β = 0.1   (negative push — gentle, avoids over-correction)

    This produces a 'personalised' retrieval direction that drifts toward your
    successful invocations and away from your dead-ends — the cross-layer synergy
    described in §E / N3 of the workspace design.

    At Tier-3 maturity this file would:
      1. Read the week's 'selection' events from the ledger.
      2. Embed queries with a local model (e.g. all-MiniLM-L6-v2 via sentence-transformers
         or a stdlib-accessible embedding endpoint).
      3. Compute the nudge and write updated centroids to oats-centroids.json.
      4. Expose a rank(query, tools) function used by the goal-reinject hook to surface
         the most relevant tools in the additionalContext injection.

CURRENT STATUS:
    No 'selection' events exist yet — the Stop hook records 'turn' events only.
    Selection logging must be added (a PostToolUse hook that writes
    kind='selection', query=…, chosen_tool=…, success=… to the ledger).
    OATS becomes active automatically once >=100 selection events are present.

This file is safe to import and call at any time. It never writes, never raises,
and never modifies any ledger — it is read-only analysis code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger  # noqa: E402

# Thresholds / hyper-parameters
MIN_SELECTION_EVENTS = 100
ALPHA = 0.3  # positive-centroid pull weight
BETA = 0.1  # negative-centroid push weight

# Centroids are stored next to the ledger root so they survive across sessions.
CENTROIDS_FILE = ledger.ROOT / "oats-centroids.json"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_selection_events(project_path: str | None = None) -> list[dict]:
    """Return all 'selection' events across all projects (or one project)."""
    if project_path:
        dirs = [ledger._dir(project_path)]  # noqa: SLF001
    else:
        dirs = (
            [d for d in ledger.ROOT.iterdir() if d.is_dir()]
            if ledger.ROOT.exists()
            else []
        )

    events: list[dict] = []
    for d in dirs:
        ef = d / "events.jsonl"
        if not ef.exists():
            continue
        for line in ef.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("kind") == "selection":
                events.append(ev)
    return events


def _load_centroids() -> dict:
    """Load persisted centroids (or return empty structure)."""
    if CENTROIDS_FILE.exists():
        try:
            return json.loads(CENTROIDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tools": {}}


def _save_centroids(data: dict) -> None:
    """Persist updated centroids. Best-effort — never raises."""
    try:
        CENTROIDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CENTROIDS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    """Element-wise add two equal-length vectors."""
    return [x + y for x, y in zip(a, b)]


def _vec_scale(v: list[float], scalar: float) -> list[float]:
    return [x * scalar for x in v]


def _mean_vector(vecs: list[list[float]]) -> list[float] | None:
    """Return the arithmetic mean of a list of equal-length vectors, or None if empty."""
    if not vecs:
        return None
    n = len(vecs)
    dim = len(vecs[0])
    acc = [0.0] * dim
    for v in vecs:
        acc = _vec_add(acc, v)
    return _vec_scale(acc, 1.0 / n)


def nudge(
    embedding: list[float],
    positive_vecs: list[list[float]],
    negative_vecs: list[list[float]],
    alpha: float = ALPHA,
    beta: float = BETA,
) -> list[float]:
    """Compute the OATS embedding nudge.

    ê = (1-α)*e + α*mean(Q+) - β*mean(Q-)

    If Q+ or Q- is empty the corresponding term is skipped (no change in that direction).
    Returns the original embedding unchanged when both pools are empty.
    """
    e = list(embedding)
    result = _vec_scale(e, 1.0 - alpha)
    q_pos = _mean_vector(positive_vecs)
    if q_pos is not None:
        result = _vec_add(result, _vec_scale(q_pos, alpha))
    q_neg = _mean_vector(negative_vecs)
    if q_neg is not None:
        result = _vec_add(result, _vec_scale(_mean_vector(negative_vecs), -beta))
    return result


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def status() -> str:
    """Return a human-readable OATS status string. Safe at all times."""
    try:
        events = _load_selection_events()
        n = len(events)
    except Exception as exc:
        return f"OATS status: error reading ledger ({exc}) — treating as inert."

    if n < MIN_SELECTION_EVENTS:
        return (
            f"OATS inert: {n} selection events logged yet "
            f"(needs >={MIN_SELECTION_EVENTS})\n"
            "  Selection logging is not yet wired. Add a PostToolUse hook that appends\n"
            "  kind='selection', query=..., chosen_tool=..., success=True/False\n"
            "  to the ledger. OATS activates automatically once the threshold is reached."
        )

    # Sufficient data path — report summary of the centroid state.
    positive = [e for e in events if e.get("success") is True]
    negative = [e for e in events if e.get("success") is False]
    tool_names = {e.get("chosen_tool") for e in events if e.get("chosen_tool")}
    centroids = _load_centroids()
    n_centroid_tools = len(centroids.get("tools", {}))

    return (
        f"OATS ACTIVE: {n} selection events "
        f"({len(positive)} positive, {len(negative)} negative), "
        f"{len(tool_names)} distinct tools, "
        f"{n_centroid_tools} centroid vectors persisted.\n"
        "  Run oats.py --update to recompute centroids for the latest batch."
    )


def update(project_path: str | None = None, dry_run: bool = False) -> str:
    """Read selection events, compute nudge direction per tool, persist centroids.

    In the scaffold phase (no embeddings backend) this documents the shape of the
    operation without actually computing real embeddings. Real embeddings require
    either a local sentence-transformers install or an API call — neither is
    wired in this stdlib-only scaffold.

    Returns a status string describing what was (or would be) done.
    """
    events = _load_selection_events(project_path)
    n = len(events)
    if n < MIN_SELECTION_EVENTS:
        return status()

    # Aggregate per-tool: list of query texts split by success flag.
    tool_pos: dict[str, list[str]] = {}
    tool_neg: dict[str, list[str]] = {}
    for ev in events:
        tool = ev.get("chosen_tool", "")
        if not tool:
            continue
        query = ev.get("query", "")
        if ev.get("success"):
            tool_pos.setdefault(tool, []).append(query)
        else:
            tool_neg.setdefault(tool, []).append(query)

    all_tools = set(tool_pos) | set(tool_neg)
    lines = [
        f"OATS update: {n} selection events, {len(all_tools)} tools to nudge.",
        f"  α={ALPHA}, β={BETA}",
        "  (Scaffold mode — no real embeddings backend; documenting nudge plan.)",
    ]
    for t in sorted(all_tools):
        pos_n = len(tool_pos.get(t, []))
        neg_n = len(tool_neg.get(t, []))
        lines.append(
            f"  {t}: {pos_n} positive queries, {neg_n} negative queries "
            f"→ nudge ê = (1-{ALPHA})*e + {ALPHA}*mean(Q+[{pos_n}]) - {BETA}*mean(Q-[{neg_n}])"
        )

    if not dry_run:
        # In the real implementation: embed queries, compute centroids, call nudge(), persist.
        # Here we persist the raw query text grouped by tool as a blueprint for the
        # full implementation that will run once an embeddings backend is available.
        centroids = _load_centroids()
        for t in all_tools:
            centroids["tools"].setdefault(t, {})["pos_queries"] = tool_pos.get(t, [])[
                -200:
            ]
            centroids["tools"][t]["neg_queries"] = tool_neg.get(t, [])[-200:]
        _save_centroids(centroids)
        lines.append(f"  Centroids written to: {CENTROIDS_FILE}")
    else:
        lines.append("  (dry-run: no writes)")

    return "\n".join(lines)


def rank(query: str, tools: list[str]) -> list[str]:
    """Return tools ranked by proximity to positive centroids for this query.

    In the scaffold phase (no real embedding backend) this returns the original
    order unchanged. Once embedding infrastructure is added, this function is
    the retrieval hook: embed `query`, compute cosine similarity to each tool's
    centroid, return sorted list.

    This function is called by the goal-reinject hook to surface the most
    relevant tools in the additionalContext injection.
    """
    # Scaffold: no-op ranking until embeddings are wired.
    return list(tools)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="OATS self-learning tool-selection scaffold."
    )
    ap.add_argument(
        "--status",
        action="store_true",
        default=False,
        help="Print OATS status (default action).",
    )
    ap.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Recompute nudge centroids from selection events.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="With --update: show plan without writing.",
    )
    ap.add_argument(
        "--project", default=None, help="Restrict to a single project path."
    )
    a = ap.parse_args()

    try:
        if a.update:
            print(update(project_path=a.project, dry_run=a.dry_run))
        else:
            print(status())
    except Exception as exc:
        print(f"OATS error (non-fatal): {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
