#!/usr/bin/env python3
"""
triage_router.py — Cost-tier model router for software-engineering work-units.

Routes a work-unit to the cheapest model tier (Haiku / Sonnet / Opus) whose
complexity budget is sufficient, using static CODE-HEALTH metrics of the
target files as the routing signal.

Based on the three-tier SWE-bench protocol in arXiv:2604.07494.

Usage
-----
  # Route from file paths (lizard preferred, stdlib fallback):
  python triage_router.py --files path/to/a.py path/to/b.py

  # Provide pre-computed score (skips static analysis):
  python triage_router.py --files a.py b.py --health-score 6.2

  # Consume a JSON manifest produced by this tool:
  python triage_router.py --manifest manifest.json

  # Escalation mode (verification gate failed at <tier>):
  python triage_router.py --files a.py --escalate sonnet

  # Override tier config:
  python triage_router.py --files a.py \\
      --tiers '[{"name":"haiku","cost":1,"model_id":"claude-haiku-4-5"},
                {"name":"sonnet","cost":3,"model_id":"claude-sonnet-4-6"},
                {"name":"opus","cost":5,"model_id":"claude-opus-4-8"}]'

Exit codes
----------
  0 — verdict emitted (JSON to stdout)
  1 — unrecoverable error (health score unavailable AND fail-safe engaged)
  2 — bad arguments
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_TIERS: list[dict[str, Any]] = [
    {"name": "haiku", "cost": 1, "model_id": "claude-haiku-4-5"},
    {"name": "sonnet", "cost": 3, "model_id": "claude-sonnet-4-6"},
    {"name": "opus", "cost": 5, "model_id": "claude-opus-4-8"},
]

# Routing thresholds (AvgCCN-equivalent score):
#   score < HAIKU_MAX   → Haiku  (healthy / simple)
#   score < SONNET_MAX  → Sonnet (moderate)
#   score >= SONNET_MAX → Opus   (complex / unhealthy)
#
# These constants come from the three-tier paper's recommended starting point.
# Replace with your own measured values after running the two go/no-go checks
# documented in README.md.
HAIKU_MAX_DEFAULT = 5.0
SONNET_MAX_DEFAULT = 10.0

# Lizard warning threshold (CCN > this is flagged by lizard):
LIZARD_WARNING_CCN = 15

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class FileHealth:
    path: str
    avg_ccn: float
    max_ccn: int
    warning_fn_ratio: float  # fraction of functions above LIZARD_WARNING_CCN
    nloc: int
    signal_source: str  # "lizard" | "stdlib_heuristic" | "provided"


@dataclass
class Verdict:
    file_or_unit: str
    health_score: float
    signal_source: str
    recommended_tier: str
    model_id: str
    rationale: str
    escalated_from: str | None = None


# ---------------------------------------------------------------------------
# Static analysis: lizard
# ---------------------------------------------------------------------------


def _run_lizard(paths: list[str]) -> FileHealth | None:
    """
    Run lizard on one or more files and return an aggregate FileHealth.
    Returns None if lizard is not available or fails.
    """
    try:
        result = subprocess.run(
            ["lizard", "--csv", *paths],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode not in (0, 1):  # lizard exits 1 on warnings
        return None

    # lizard --csv columns: NLOC,CCN,token,PARAM,length,location
    # The last section "Total" is not in CSV; skip lines without numeric CCN.
    ccn_values: list[float] = []
    warning_count = 0
    total_nloc = 0
    parsed_funcs = 0

    for line in result.stdout.splitlines():
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            nloc_val = int(parts[0].strip())
            ccn_val = float(parts[1].strip())
        except ValueError:
            continue
        ccn_values.append(ccn_val)
        total_nloc += nloc_val
        parsed_funcs += 1
        if ccn_val > LIZARD_WARNING_CCN:
            warning_count += 1

    if not ccn_values:
        return None

    avg_ccn = sum(ccn_values) / len(ccn_values)
    max_ccn = int(max(ccn_values))
    warning_ratio = warning_count / parsed_funcs if parsed_funcs else 0.0

    return FileHealth(
        path=", ".join(paths),
        avg_ccn=avg_ccn,
        max_ccn=max_ccn,
        warning_fn_ratio=warning_ratio,
        nloc=total_nloc,
        signal_source="lizard",
    )


# ---------------------------------------------------------------------------
# Static analysis: stdlib heuristic fallback
# ---------------------------------------------------------------------------


def _count_max_nesting(tree: ast.AST) -> int:
    """Return maximum nesting depth of compound statements in an AST."""

    def _walk(node: ast.AST, depth: int) -> int:
        local_max = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.With,
                    ast.Try,
                    ast.ExceptHandler,
                    ast.AsyncFor,
                    ast.AsyncWith,
                ),
            ):
                local_max = max(local_max, _walk(child, depth + 1))
            else:
                local_max = max(local_max, _walk(child, depth))
        return local_max

    return _walk(tree, 0)


def _stdlib_health(paths: list[str]) -> FileHealth | None:
    """
    Cheap stdlib heuristics when lizard is unavailable.
    Returns a coarse AvgCCN-equivalent score: branch-count / function-count.
    CLEARLY labelled as heuristic in signal_source.
    """
    all_ccn: list[float] = []
    all_nloc = 0

    for path in paths:
        try:
            source = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError:
            lines = source.splitlines()
            all_nloc += sum(
                1 for ln in lines if ln.strip() and not ln.strip().startswith("#")
            )
            # Can't parse → treat as complex
            all_ccn.append(20.0)
            continue

        lines = source.splitlines()
        nloc = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
        all_nloc += nloc

        funcs = [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not funcs:
            # Module-level only: use branch density as proxy
            branches = sum(
                1
                for n in ast.walk(tree)
                if isinstance(
                    n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)
                )
            )
            all_ccn.append(1.0 + branches)
            continue

        for fn in funcs:
            branches = sum(
                1
                for n in ast.walk(fn)
                if isinstance(
                    n,
                    (
                        ast.If,
                        ast.For,
                        ast.While,
                        ast.ExceptHandler,
                        ast.With,
                        ast.BoolOp,
                        ast.IfExp,
                        ast.comprehension,
                    ),
                )
            )
            all_ccn.append(1.0 + branches)

    if not all_ccn:
        return None

    avg_ccn = sum(all_ccn) / len(all_ccn)
    max_ccn = int(max(all_ccn))
    warning_ratio = sum(1 for v in all_ccn if v > LIZARD_WARNING_CCN) / len(all_ccn)

    return FileHealth(
        path=", ".join(paths),
        avg_ccn=avg_ccn,
        max_ccn=max_ccn,
        warning_fn_ratio=warning_ratio,
        nloc=all_nloc,
        signal_source="stdlib_heuristic",
    )


# ---------------------------------------------------------------------------
# Score aggregation
# ---------------------------------------------------------------------------


def _composite_score(fh: FileHealth) -> float:
    """
    Map FileHealth → a single routing score (higher = more complex).

    Formula:
        score = avg_ccn + (max_ccn_penalty) + (warning_density_penalty)

    Penalise outlier hot-spots and density of flagged functions:
        max_ccn_penalty   = max(0, max_ccn - 15) * 0.25
        warning_penalty   = warning_fn_ratio * 5.0

    This keeps avg_ccn dominant while still routing files with a single
    catastrophically complex function upward.
    """
    max_penalty = max(0.0, fh.max_ccn - LIZARD_WARNING_CCN) * 0.25
    warning_penalty = fh.warning_fn_ratio * 5.0
    return fh.avg_ccn + max_penalty + warning_penalty


# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------


def _tier_order(tiers: list[dict]) -> list[dict]:
    """Return tiers sorted cheapest-first."""
    return sorted(tiers, key=lambda t: t["cost"])


def _pick_tier(
    score: float,
    tiers: list[dict],
    haiku_max: float,
    sonnet_max: float,
    escalate_from: str | None = None,
) -> dict:
    """
    Map score → cheapest sufficient tier; honour --escalate.
    FAIL-SAFE: if tiers is empty or score is infinite/NaN, return the costliest.
    """
    ordered = _tier_order(tiers)
    if not ordered:
        raise ValueError("No tiers configured.")

    # Determine the natural tier index from the score
    if score < haiku_max:
        natural_idx = 0
    elif score < sonnet_max:
        natural_idx = min(1, len(ordered) - 1)
    else:
        natural_idx = len(ordered) - 1

    chosen_idx = natural_idx

    # Apply escalation: one tier up from the named tier
    if escalate_from:
        current_names = [t["name"].lower() for t in ordered]
        if escalate_from.lower() in current_names:
            current_idx = current_names.index(escalate_from.lower())
            chosen_idx = max(chosen_idx, min(current_idx + 1, len(ordered) - 1))

    return ordered[chosen_idx]


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def route(
    paths: list[str],
    tiers: list[dict],
    haiku_max: float,
    sonnet_max: float,
    health_score: float | None = None,
    escalate_from: str | None = None,
) -> Verdict:
    """
    Core routing logic. Returns a Verdict dataclass.

    FAIL-SAFE rule: if health cannot be computed and no score is provided,
    route to the highest (costliest) tier.
    """
    ordered = _tier_order(tiers)
    top_tier = ordered[-1]

    # If a pre-computed score was provided, use it directly.
    if health_score is not None:
        fh = FileHealth(
            path=", ".join(paths),
            avg_ccn=health_score,
            max_ccn=0,
            warning_fn_ratio=0.0,
            nloc=0,
            signal_source="provided",
        )
        score = health_score
        sig = "provided"
    else:
        # Try lizard first, fall back to stdlib heuristic.
        fh = _run_lizard(paths)
        if fh is None:
            fh = _stdlib_health(paths)

        if fh is None:
            # FAIL-SAFE: can't compute health → highest tier
            return Verdict(
                file_or_unit=", ".join(paths),
                health_score=float("inf"),
                signal_source="unavailable",
                recommended_tier=top_tier["name"],
                model_id=top_tier["model_id"],
                rationale=(
                    "FAIL-SAFE: health score could not be computed "
                    "(lizard unavailable and files unreadable). "
                    "Defaulting to highest tier to avoid under-routing."
                ),
                escalated_from=escalate_from,
            )

        score = _composite_score(fh)
        sig = fh.signal_source

    # Pick tier
    tier = _pick_tier(score, tiers, haiku_max, sonnet_max, escalate_from)

    # Build rationale
    cost_note = ""
    if sig == "stdlib_heuristic":
        cost_note = " [WARNING: score from stdlib heuristic — lizard not available]"

    escalate_note = ""
    if escalate_from and tier["name"].lower() != (escalate_from or "").lower():
        escalate_note = f" Escalated from {escalate_from}."

    if score < haiku_max:
        complexity_label = "healthy/simple"
    elif score < sonnet_max:
        complexity_label = "moderate"
    else:
        complexity_label = "complex/unhealthy"

    rationale = (
        f"Composite score {score:.2f} ({complexity_label})"
        f" from {sig}{cost_note}."
        f" avg_ccn={getattr(fh, 'avg_ccn', score):.2f}"
        f" max_ccn={getattr(fh, 'max_ccn', 0)}"
        f" warn_ratio={getattr(fh, 'warning_fn_ratio', 0.0):.2%}."
        f" → {tier['name']} (cost={tier['cost']}x).{escalate_note}"
    )

    return Verdict(
        file_or_unit=", ".join(paths),
        health_score=round(score, 4),
        signal_source=sig,
        recommended_tier=tier["name"],
        model_id=tier["model_id"],
        rationale=rationale,
        escalated_from=escalate_from,
    )


# ---------------------------------------------------------------------------
# Manifest support
# ---------------------------------------------------------------------------


def _route_manifest(
    manifest_path: str,
    tiers: list[dict],
    haiku_max: float,
    sonnet_max: float,
    escalate_from: str | None = None,
) -> list[dict]:
    """
    Process a JSON manifest.  Format:
      [{"files": ["a.py", "b.py"]},  ...]
      or
      [{"files": ["a.py"], "health_score": 4.2}, ...]
    Returns a list of verdict dicts.
    """
    data = json.loads(Path(manifest_path).read_text())
    if not isinstance(data, list):
        data = [data]

    results = []
    for entry in data:
        files = entry.get("files", [])
        score = entry.get("health_score")
        v = route(files, tiers, haiku_max, sonnet_max, score, escalate_from)
        results.append(asdict(v))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="triage_router",
        description="Route a work-unit to the cheapest sufficient model tier.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    input_g = p.add_mutually_exclusive_group(required=True)
    input_g.add_argument(
        "--files",
        "-f",
        nargs="+",
        metavar="FILE",
        help="Target file path(s) for the work-unit.",
    )
    input_g.add_argument(
        "--manifest",
        metavar="PATH",
        help="JSON manifest of work-units (see --help for format).",
    )

    p.add_argument(
        "--health-score",
        type=float,
        default=None,
        metavar="SCORE",
        help="Pre-computed health score (skips static analysis).",
    )
    p.add_argument(
        "--escalate",
        default=None,
        metavar="TIER",
        help="Verification gate failed at this tier; return the next tier up.",
    )
    p.add_argument(
        "--tiers",
        default=None,
        metavar="JSON",
        help=(
            "JSON array of tier objects: "
            '[{"name":"haiku","cost":1,"model_id":"claude-haiku-4-5"}, ...]'
        ),
    )
    p.add_argument(
        "--haiku-max",
        type=float,
        default=HAIKU_MAX_DEFAULT,
        help=f"Score upper bound for Haiku tier (default {HAIKU_MAX_DEFAULT}).",
    )
    p.add_argument(
        "--sonnet-max",
        type=float,
        default=SONNET_MAX_DEFAULT,
        help=f"Score upper bound for Sonnet tier (default {SONNET_MAX_DEFAULT}).",
    )
    p.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    tiers = DEFAULT_TIERS
    if args.tiers:
        try:
            tiers = json.loads(args.tiers)
        except json.JSONDecodeError as e:
            print(f"ERROR: --tiers JSON parse failed: {e}", file=sys.stderr)
            return 2

    indent = 2 if args.pretty else None

    if args.manifest:
        try:
            results = _route_manifest(
                args.manifest,
                tiers,
                args.haiku_max,
                args.sonnet_max,
                args.escalate,
            )
        except Exception as e:
            print(f"ERROR: manifest error: {e}", file=sys.stderr)
            return 1
        print(json.dumps(results, indent=indent))
        return 0

    # Single work-unit from --files
    verdict = route(
        paths=args.files,
        tiers=tiers,
        haiku_max=args.haiku_max,
        sonnet_max=args.sonnet_max,
        health_score=args.health_score,
        escalate_from=args.escalate,
    )
    print(json.dumps(asdict(verdict), indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
