"""
memory_bench.py — Basic-Memory Recall Benchmark
================================================
Measures whether basic-memory (local semantic vault) actually recalls facts
correctly across simulated "sessions" using deterministic substring/keyword
scoring — no LLM-as-judge, no same-context placebo.

Based on LongMemEval (arXiv:2410.10813) ability classes + LoCoMo-style probes.

Usage:
    python memory_bench.py [--probes PROBES_JSONL] [--results RESULTS_JSON]
                           [--project-name NAME] [--no-cleanup]

Requirements:
    - basic-memory 0.22.1+ CLI on PATH
    - Python 3.9+
    - No pip packages beyond stdlib (subprocess + json)
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PROBES = Path(__file__).parent / "probes.jsonl"
DEFAULT_RESULTS = Path(__file__).parent / "results.json"
SCRATCH_PROJECT_NAME = "bm-bench-scratch"

# Minimum search result score to consider a result "found"
# (basic-memory returns 0.0–1.0; below this threshold we treat as abstain)
RELEVANCE_THRESHOLD = 0.05

# Delay between write and search to allow indexing (seconds)
INDEXING_DELAY = 1.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    id: str
    ability_class: str
    setup_notes: list[dict]
    question: str
    expected_substrings: list[str]
    should_abstain: bool


@dataclass
class ProbeResult:
    probe_id: str
    ability_class: str
    passed: bool
    reason: str
    raw_results: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CLI wrappers
# ---------------------------------------------------------------------------

def run_bm(args: list[str], check: bool = True, retries: int = 3) -> subprocess.CompletedProcess:
    """
    Run a basic-memory CLI command and return the CompletedProcess.

    Retries up to `retries` times on transient startup failures (e.g.
    MemoryError in logfire/pydantic during rapid consecutive invocations).
    A 0.5s back-off is applied between attempts.
    """
    cmd = ["basic-memory"] + args
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0 or not check:
            return result
        # Detect transient startup crash (MemoryError / import error in stderr)
        is_transient = (
            "MemoryError" in result.stderr
            or "ImportError" in result.stderr
            or "ModuleNotFoundError" in result.stderr
        )
        if is_transient and attempt < retries:
            time.sleep(0.5 * attempt)
            continue
        last_exc = RuntimeError(
            f"basic-memory command failed (attempt {attempt}/{retries}): "
            f"{' '.join(cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        if not is_transient:
            break
    raise last_exc or RuntimeError(f"basic-memory command failed: {' '.join(cmd)}")


def project_add(name: str, path: str) -> None:
    run_bm(["project", "add", name, path])


def project_remove(name: str) -> None:
    run_bm(["project", "remove", name], check=False)


def write_note(title: str, folder: str, content: str, project: str) -> dict:
    result = run_bm([
        "tool", "write-note",
        "--title", title,
        "--folder", folder,
        "--content", content,
        "--project", project,
        "--overwrite",
    ])
    return json.loads(result.stdout)


def delete_note(identifier: str, project: str) -> None:
    run_bm(["tool", "delete-note", identifier, "--project", project], check=False)


def search_notes(query: str, project: str, page_size: int = 10) -> list[dict]:
    """
    Use --hybrid retrieval (BM25 + semantic/entity matching).

    Why --hybrid and not default (BM25-only):
    The default FTS index in basic-memory is NOT updated synchronously on
    write — notes appear in the entity store immediately but the full-text
    index requires an explicit `reindex` run to pick them up.  The --hybrid
    flag bypasses that gap by combining entity-store lookup with BM25, so
    freshly written notes are discoverable without an extra reindex step.
    This matches how the MCP server exposes search to LLMs in practice.
    """
    result = run_bm([
        "tool", "search-notes", query,
        "--project", project,
        "--hybrid",
        "--page-size", str(page_size),
    ])
    data = json.loads(result.stdout)
    return data.get("results", [])


# ---------------------------------------------------------------------------
# Probe loading
# ---------------------------------------------------------------------------

def load_probes(path: Path) -> list[Probe]:
    probes = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
                probes.append(Probe(
                    id=obj["id"],
                    ability_class=obj["class"],
                    setup_notes=obj["setup_notes"],
                    question=obj["question"],
                    expected_substrings=obj.get("expected_substrings", []),
                    should_abstain=obj.get("should_abstain", False),
                ))
            except (json.JSONDecodeError, KeyError) as exc:
                print(f"  [WARN] Skipping malformed probe at line {lineno}: {exc}",
                      file=sys.stderr)
    return probes


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_probe(probe: Probe, search_results: list[dict]) -> ProbeResult:
    """
    Deterministic scorer — NO LLM.

    Rules:
    - Abstention probe: PASS if no results returned (or all below threshold).
    - Recall probe: PASS if at least one expected_substring appears in any
      result's 'content' or 'matched_chunk' field (case-insensitive).
      expected_substrings is treated as OR-alternatives (any one match = pass).
    """
    relevant = [
        r for r in search_results
        if r.get("score", 0.0) >= RELEVANCE_THRESHOLD
    ]

    if probe.should_abstain:
        if not relevant:
            return ProbeResult(
                probe_id=probe.id,
                ability_class=probe.ability_class,
                passed=True,
                reason="Correctly returned no relevant results (abstention).",
                raw_results=search_results,
            )
        else:
            # Abstention failure: something was recalled when nothing should be
            found_titles = [r.get("title", "?") for r in relevant]
            return ProbeResult(
                probe_id=probe.id,
                ability_class=probe.ability_class,
                passed=False,
                reason=(
                    f"Expected abstention but got {len(relevant)} result(s): "
                    f"{found_titles}"
                ),
                raw_results=search_results,
            )

    # Recall probe: gather all text from results
    all_text = " ".join(
        (r.get("content") or "") + " " + (r.get("matched_chunk") or "")
        for r in relevant
    ).lower()

    if not probe.expected_substrings:
        # No expected_substrings means the probe itself is misconfigured
        return ProbeResult(
            probe_id=probe.id,
            ability_class=probe.ability_class,
            passed=False,
            reason="Probe misconfigured: no expected_substrings and not abstain.",
            raw_results=search_results,
        )

    for substring in probe.expected_substrings:
        if substring.lower() in all_text:
            return ProbeResult(
                probe_id=probe.id,
                ability_class=probe.ability_class,
                passed=True,
                reason=f"Found expected substring '{substring}' in results.",
                raw_results=search_results,
            )

    return ProbeResult(
        probe_id=probe.id,
        ability_class=probe.ability_class,
        passed=False,
        reason=(
            f"None of the expected substrings {probe.expected_substrings} "
            f"found. Retrieved {len(relevant)} relevant result(s)."
        ),
        raw_results=search_results,
    )


# ---------------------------------------------------------------------------
# Per-probe execution
# ---------------------------------------------------------------------------

def run_probe(probe: Probe, project: str, folder_prefix: str) -> ProbeResult:
    """Ingest setup_notes, search with question, score, then clean up notes."""
    # Each probe gets its own subfolder to avoid cross-contamination
    folder = f"{folder_prefix}/{probe.id}"
    written_ids: list[str] = []

    try:
        # Ingest setup notes
        for note in probe.setup_notes:
            info = write_note(
                title=note["title"],
                folder=folder,
                content=note["content"],
                project=project,
            )
            # The permalink returned is the stable identifier for deletion
            written_ids.append(info.get("permalink", ""))

        # Brief pause to allow the index to settle
        time.sleep(INDEXING_DELAY)

        # Issue the recall query
        results = search_notes(probe.question, project=project, page_size=15)

        # Score
        return score_probe(probe, results)

    finally:
        # Clean up the probe's notes so probes don't bleed into each other
        for note_id in written_ids:
            if note_id:
                # The permalink uses forward slashes; strip the project prefix
                # e.g. "bm-bench-scratch/bench/ie-01/Title" -> "bench/ie-01/Title"
                stripped = note_id
                if stripped.startswith(project + "/"):
                    stripped = stripped[len(project) + 1:]
                delete_note(stripped, project=project)


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    probes_path: Path,
    results_path: Path,
    project_name: str,
    cleanup: bool,
) -> int:
    """
    Run all probes. Returns exit code (0 = harness ran OK, 1 = harness error).
    Pass-rate < 100% is NOT a harness error; it is the measurement.
    """
    scratch_dir = Path(tempfile.gettempdir()) / "bm-bench"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print("  Basic-Memory Recall Benchmark")
    print(f"{'='*60}")
    print(f"  Probes file : {probes_path}")
    print(f"  Scratch dir : {scratch_dir}")
    print(f"  Project     : {project_name}")
    print(f"  Results out : {results_path}")
    print(f"{'='*60}\n")

    # --- Verify real vault is not involved --------------------------------
    real_vault = Path("D:/basic-memory")
    if real_vault.exists():
        print(f"[INFO] Real vault exists at {real_vault} — will NOT be touched.\n")

    # --- Load probes -------------------------------------------------------
    probes = load_probes(probes_path)
    if not probes:
        print("[ERROR] No probes loaded. Check probes.jsonl.", file=sys.stderr)
        return 1
    print(f"[INFO] Loaded {len(probes)} probes.\n")

    # --- Set up scratch project --------------------------------------------
    project_remove(project_name)          # remove stale if exists
    project_add(project_name, str(scratch_dir))
    print(f"[INFO] Scratch project '{project_name}' created at {scratch_dir}\n")

    probe_results: list[ProbeResult] = []
    folder_prefix = "bench"

    try:
        # --- Run each probe ------------------------------------------------
        for i, probe in enumerate(probes, 1):
            print(f"  [{i:02d}/{len(probes)}] {probe.id} ({probe.ability_class}) ... ", end="", flush=True)
            try:
                result = run_probe(probe, project=project_name, folder_prefix=folder_prefix)
                probe_results.append(result)
                status = "PASS" if result.passed else "FAIL"
                print(f"{status}  — {result.reason}")
            except Exception as exc:
                err_result = ProbeResult(
                    probe_id=probe.id,
                    ability_class=probe.ability_class,
                    passed=False,
                    reason=f"HARNESS ERROR: {exc}",
                )
                probe_results.append(err_result)
                print(f"ERROR — {exc}")

    finally:
        # --- Tear down scratch project & dir ------------------------------
        if cleanup:
            print(f"\n[INFO] Cleaning up project '{project_name}' ...")
            project_remove(project_name)
            if scratch_dir.exists():
                shutil.rmtree(scratch_dir, ignore_errors=True)
            print("[INFO] Cleanup complete.")
        else:
            print(f"\n[INFO] --no-cleanup set; scratch project '{project_name}' retained.")

    # --- Aggregate results ------------------------------------------------
    passed = sum(1 for r in probe_results if r.passed)
    total = len(probe_results)
    pass_rate = passed / total if total else 0.0

    # Per-class breakdown
    classes: dict[str, dict[str, int]] = {}
    for r in probe_results:
        cls = r.ability_class
        if cls not in classes:
            classes[cls] = {"passed": 0, "total": 0}
        classes[cls]["total"] += 1
        if r.passed:
            classes[cls]["passed"] += 1

    # --- Print summary ----------------------------------------------------
    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Overall pass-rate : {passed}/{total} ({pass_rate:.1%})")
    print()
    print("  Per-class breakdown:")
    for cls, counts in sorted(classes.items()):
        cls_rate = counts["passed"] / counts["total"] if counts["total"] else 0.0
        bar = "PASS" if cls_rate == 1.0 else ("PARTIAL" if cls_rate > 0 else "FAIL")
        print(f"    {cls:<30} {counts['passed']}/{counts['total']}  ({cls_rate:.0%})  [{bar}]")
    print(f"\n  Failed probes:")
    failed = [r for r in probe_results if not r.passed]
    if failed:
        for r in failed:
            print(f"    - {r.probe_id}: {r.reason}")
    else:
        print("    None — all probes passed.")
    print(f"{'='*60}\n")

    # --- Write JSON results -----------------------------------------------
    output: dict[str, Any] = {
        "overall_pass_rate": pass_rate,
        "passed": passed,
        "total": total,
        "per_class": {
            cls: {
                "passed": counts["passed"],
                "total": counts["total"],
                "pass_rate": counts["passed"] / counts["total"] if counts["total"] else 0.0,
            }
            for cls, counts in sorted(classes.items())
        },
        "probe_results": [
            {
                "id": r.probe_id,
                "class": r.ability_class,
                "passed": r.passed,
                "reason": r.reason,
            }
            for r in probe_results
        ],
    }
    results_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[INFO] Full results written to {results_path}\n")

    # Harness itself ran cleanly regardless of pass-rate
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Basic-Memory Recall Benchmark (LongMemEval-style)"
    )
    parser.add_argument(
        "--probes",
        type=Path,
        default=DEFAULT_PROBES,
        help="Path to probes.jsonl (default: ./probes.jsonl)",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS,
        help="Path to write results JSON (default: ./results.json)",
    )
    parser.add_argument(
        "--project-name",
        default=SCRATCH_PROJECT_NAME,
        help=f"Scratch project name (default: {SCRATCH_PROJECT_NAME})",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Retain the scratch project after the run (for debugging)",
    )
    args = parser.parse_args()

    exit_code = run_benchmark(
        probes_path=args.probes,
        results_path=args.results,
        project_name=args.project_name,
        cleanup=not args.no_cleanup,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
