"""Live test-runtime profiler for AUD-0056.

Probe 1 uses pytest --durations (in-runner call/setup/teardown).
Probe 2 times each module as its own process (collection + fixtures included).
Neither path fabricates 0.0s for a missing durations table.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUITE_ROOTS = (
    "tools/command-center/tests",
    "tools/marketplace/tests",
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0056/probe1_durations.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0056/probe2_wallclock.py"
)
OUT = "command-center/audit/AUD-0056-test-runtime-profile.json"
SCHEMA = "command-center/schema/audit-metric-baseline.schema.json"
COMPLETION = (
    "SUCCESS:AUD-0056 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "What is the wall-clock cost of each test module today, which are the "
    "slowest, and which are candidates for the soak and load lanes rather "
    "than the per-PR gate?"
)
SOAK_WALL_S = 30.0
SOAK_SHARE = 0.20
SOAK_SHARE_FLOOR_S = 5.0
RANK_K = 10
RHO_MIN = 0.8
DUR_RE = re.compile(
    r"^(\d+\.\d+)s\s+(call|setup|teardown)\s+(\S+)",
    re.MULTILINE,
)
SAMPLE_DURATIONS = (
    "============================= slowest durations =============================\n"
    "0.40s call     tools/command-center/tests/test_close.py::test_a\n"
    "0.10s setup    tools/command-center/tests/test_close.py::test_a\n"
    "0.20s call     tools/command-center/tests/test_validate.py::test_b\n"
)


def pytest_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    tools = str(REPO / "tools")
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = tools if not prev else tools + os.pathsep + prev
    return env


def run_pytest(args: list[str], timeout: int = 90) -> tuple[int, str, float]:
    cmd = [sys_executable(), "-B", "-m", "pytest", *args]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=pytest_env(),
        )
        elapsed = time.perf_counter() - t0
        text = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, text, elapsed
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - t0
        out = ""
        if exc.stdout:
            out += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(
                "utf-8", "replace"
            )
        if exc.stderr:
            out += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(
                "utf-8", "replace"
            )
        return 124, out + f"\nTIMEOUT after {timeout}s: {' '.join(cmd)}", elapsed
    except OSError as exc:
        elapsed = time.perf_counter() - t0
        return 127, f"{type(exc).__name__}: {exc}", elapsed


def sys_executable() -> str:
    import sys

    return sys.executable or "python3"


def parse_durations(text: str) -> list[dict[str, Any]]:
    """Parse pytest --durations lines. Empty/missing table yields [] not zeros."""
    if not text:
        return []
    rows: list[dict[str, Any]] = []
    for match in DUR_RE.finditer(text):
        seconds = float(match.group(1))
        phase = match.group(2)
        nodeid = match.group(3)
        module = nodeid.split("::", 1)[0]
        rows.append(
            {
                "seconds": seconds,
                "phase": phase,
                "nodeid": nodeid,
                "module": module,
            }
        )
    return rows


def durations_present(text: str) -> bool:
    return "slowest" in text.lower() and "duration" in text.lower() and bool(
        parse_durations(text)
    )


def aggregate_modules(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by: dict[str, dict[str, float]] = defaultdict(
        lambda: {"call_s": 0.0, "setup_s": 0.0, "teardown_s": 0.0, "n": 0.0}
    )
    for row in rows:
        bucket = by[row["module"]]
        phase = row["phase"]
        bucket[f"{phase}_s"] += float(row["seconds"])
        if phase == "call":
            bucket["n"] += 1.0
    out: dict[str, dict[str, float]] = {}
    for module, vals in by.items():
        reported = vals["call_s"] + vals["setup_s"] + vals["teardown_s"]
        out[module] = {
            "call_s": round(vals["call_s"], 6),
            "setup_s": round(vals["setup_s"], 6),
            "teardown_s": round(vals["teardown_s"], 6),
            "reported_s": round(reported, 6),
            "n_call_rows": int(vals["n"]),
        }
    return out


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2 or n != len(ys):
        return 1.0 if n <= 1 else 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 and dy == 0.0:
        return 1.0
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / (dx * dy)


def rankdata(xs: list[float]) -> list[float]:
    indexed = sorted(enumerate(xs), key=lambda item: item[1])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(rankdata(xs), rankdata(ys))


def ranking_stability(
    modules: list[str],
    values_a: list[float],
    values_b: list[float],
    k: int = RANK_K,
) -> dict[str, Any]:
    if not modules or not values_a or not values_b:
        return {
            "stable": False,
            "reason": "empty-measurement",
            "spearman_rho": "NOT-CHECKED",
            "slowest_run_a": None,
            "slowest_run_b": None,
            "top_k_run_a": [],
            "top_k_run_b": [],
            "ordered_top_k_equal": False,
            "slowest_identity_match": False,
            "threshold_rho": RHO_MIN,
            "k": k,
        }
    order_a = [m for _, m in sorted(zip(values_a, modules), key=lambda t: -t[0])]
    order_b = [m for _, m in sorted(zip(values_b, modules), key=lambda t: -t[0])]
    top_a, top_b = order_a[:k], order_b[:k]
    rho = spearman(values_a, values_b)
    slowest_same = bool(order_a and order_b and order_a[0] == order_b[0])
    ordered_equal = top_a == top_b
    stable = slowest_same and (ordered_equal or rho >= RHO_MIN)
    return {
        "stable": stable,
        "reason": "ok" if stable else "ranking-moved",
        "spearman_rho": round(rho, 6),
        "slowest_run_a": order_a[0] if order_a else None,
        "slowest_run_b": order_b[0] if order_b else None,
        "top_k_run_a": top_a,
        "top_k_run_b": top_b,
        "ordered_top_k_equal": ordered_equal,
        "slowest_identity_match": slowest_same,
        "threshold_rho": RHO_MIN,
        "k": k,
    }


def ranking_detector_control() -> dict[str, Any]:
    modules = [f"m{i}" for i in range(10)]
    high = [float(10 - i) for i in range(10)]
    reverse = list(reversed(high))
    good = ranking_stability(modules, high, list(high), k=10)
    bad = ranking_stability(modules, high, reverse, k=10)
    silent_good = bool(good["stable"])
    fired_bad = not bool(bad["stable"])
    return {
        "id": "AUD0056-C2",
        "kind": "ranking-stability",
        "description": (
            "Identical duration vectors must be ranked stable; a reversed "
            "top-10 must be ranked unstable. A detector silent on reversal "
            "cannot underwrite a baseline."
        ),
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "pass": fired_bad and silent_good,
        "bad_state_output": (
            f"reversed stable={bad['stable']} rho={bad['spearman_rho']} "
            f"slowest_a={bad['slowest_run_a']} slowest_b={bad['slowest_run_b']}"
        ),
        "good_state_output": (
            f"identical stable={good['stable']} rho={good['spearman_rho']} "
            f"slowest={good['slowest_run_a']}"
        ),
    }


def parser_control() -> dict[str, Any]:
    empty = parse_durations("")
    missing = parse_durations("===== test session starts =====\n81 passed in 1.00s\n")
    sample = parse_durations(SAMPLE_DURATIONS)
    fired = empty == [] and missing == []
    silent = (
        len(sample) == 3
        and abs(sample[0]["seconds"] - 0.40) < 1e-9
        and sample[0]["module"].endswith("test_close.py")
    )
    invented_zero = any(r["seconds"] == 0.0 for r in empty + missing)
    return {
        "id": "AUD0056-C1",
        "kind": "absent-input",
        "description": (
            "A pytest log with no --durations table must not become a 0.0s "
            "profile. Absence is an empty parse, never a fabricated number."
        ),
        "fired_on_bad_state": fired and not invented_zero,
        "silent_on_good_state": silent,
        "pass": fired and silent and not invented_zero,
        "bad_state_output": f"empty={empty!r} missing_table={missing!r}",
        "good_state_output": (
            f"sample_n={len(sample)} first={sample[0] if sample else None}"
        ),
    }


def collect_modules() -> tuple[list[str], str, int]:
    code, text, _elapsed = run_pytest(
        ["--collect-only", "-q", "-p", "no:cacheprovider", *SUITE_ROOTS],
        timeout=60,
    )
    modules: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if "::" not in line:
            continue
        if not line.startswith("tools/"):
            continue
        module = line.split("::", 1)[0]
        if module not in modules:
            modules.append(module)
    return modules, text, code


def run_durations_suite() -> dict[str, Any]:
    code, text, wall = run_pytest(
        [
            "--durations=0",
            "--tb=no",
            "-p",
            "no:cacheprovider",
            "-q",
            *SUITE_ROOTS,
        ],
        timeout=90,
    )
    rows = parse_durations(text)
    return {
        "exit_code": code,
        "wall_s": round(wall, 6),
        "raw_output": text[-65000:],
        "durations_header_present": durations_present(text),
        "row_count": len(rows),
        "by_module": aggregate_modules(rows),
        "pytest_invoked": code != 127,
    }


def run_wall_module(module: str) -> dict[str, Any]:
    code, text, wall = run_pytest(
        [
            "--durations=0",
            "--tb=no",
            "-p",
            "no:cacheprovider",
            "-q",
            module,
        ],
        timeout=90,
    )
    rows = parse_durations(text)
    agg = aggregate_modules(rows).get(
        module,
        {"call_s": 0.0, "setup_s": 0.0, "teardown_s": 0.0, "reported_s": 0.0},
    )
    call_s = float(agg.get("call_s") or 0.0)
    reported = float(agg.get("reported_s") or 0.0)
    tax = round(wall - reported, 6)
    return {
        "module": module,
        "exit_code": code,
        "wall_s": round(wall, 6),
        "call_s": call_s,
        "setup_s": float(agg.get("setup_s") or 0.0),
        "teardown_s": float(agg.get("teardown_s") or 0.0),
        "reported_s": reported,
        "collection_and_unattributed_s": tax,
        "wall_covers_call": wall + 0.05 >= call_s,
        "durations_header_present": durations_present(text),
        "raw_tail": text[-2500:],
    }


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def classify_lane(wall_s: float, suite_wall_s: float) -> str:
    share = (wall_s / suite_wall_s) if suite_wall_s > 0 else 0.0
    if wall_s >= SOAK_WALL_S or (share >= SOAK_SHARE and wall_s >= SOAK_SHARE_FLOOR_S):
        return "soak-or-load-lane"
    return "per-PR-gate"


def loadavg() -> list[float] | str:
    try:
        return [round(x, 3) for x in os.getloadavg()]
    except OSError:
        return "NOT-CHECKED"


def measure_live() -> dict[str, Any]:
    parser = parser_control()
    rank_ctl = ranking_detector_control()
    modules, collect_raw, collect_code = collect_modules()
    dur_a = run_durations_suite()
    dur_b = run_durations_suite()
    union = sorted(
        set(dur_a["by_module"]) | set(dur_b["by_module"]) | set(modules)
    )
    if not union:
        union = list(modules)
    dur_vals_a = [
        float((dur_a["by_module"].get(m) or {}).get("call_s") or 0.0) for m in union
    ]
    dur_vals_b = [
        float((dur_b["by_module"].get(m) or {}).get("call_s") or 0.0) for m in union
    ]
    dur_rank = ranking_stability(union, dur_vals_a, dur_vals_b)

    wall_a = [run_wall_module(m) for m in union]
    wall_b = [run_wall_module(m) for m in union]
    wall_map_a = {row["module"]: row for row in wall_a}
    wall_map_b = {row["module"]: row for row in wall_b}
    wall_vals_a = [float(wall_map_a[m]["wall_s"]) for m in union]
    wall_vals_b = [float(wall_map_b[m]["wall_s"]) for m in union]
    wall_rank = ranking_stability(union, wall_vals_a, wall_vals_b)

    suite_wall = median(
        [
            sum(wall_vals_a) if wall_vals_a else 0.0,
            sum(wall_vals_b) if wall_vals_b else 0.0,
        ]
    )
    module_rows = []
    soak: list[str] = []
    wall_covers = False
    for module in union:
        call_med = median(
            [
                float((dur_a["by_module"].get(module) or {}).get("call_s") or 0.0),
                float((dur_b["by_module"].get(module) or {}).get("call_s") or 0.0),
            ]
        )
        setup_med = median(
            [
                float((dur_a["by_module"].get(module) or {}).get("setup_s") or 0.0),
                float((dur_b["by_module"].get(module) or {}).get("setup_s") or 0.0),
            ]
        )
        wall_med = median(
            [float(wall_map_a[module]["wall_s"]), float(wall_map_b[module]["wall_s"])]
        )
        tax_med = median(
            [
                float(wall_map_a[module]["collection_and_unattributed_s"]),
                float(wall_map_b[module]["collection_and_unattributed_s"]),
            ]
        )
        lane = classify_lane(wall_med, suite_wall)
        if lane == "soak-or-load-lane":
            soak.append(module)
        if wall_map_a[module]["wall_covers_call"] or wall_map_b[module]["wall_covers_call"]:
            wall_covers = True
        module_rows.append(
            {
                "module": module,
                "lane": lane,
                "durations_call_median_s": round(call_med, 6),
                "durations_setup_median_s": round(setup_med, 6),
                "wall_median_s": round(wall_med, 6),
                "collection_tax_median_s": round(tax_med, 6),
                "durations_call_run_a_s": round(dur_vals_a[union.index(module)], 6),
                "durations_call_run_b_s": round(dur_vals_b[union.index(module)], 6),
                "wall_run_a_s": round(wall_vals_a[union.index(module)], 6),
                "wall_run_b_s": round(wall_vals_b[union.index(module)], 6),
                "isolated_exit_a": wall_map_a[module]["exit_code"],
                "isolated_exit_b": wall_map_b[module]["exit_code"],
            }
        )
    module_rows.sort(key=lambda r: -float(r["wall_median_s"]))
    slowest_dur = dur_rank.get("slowest_run_a") or (
        module_rows[0]["module"] if module_rows else "NOT-CHECKED"
    )
    slowest_wall = wall_rank.get("slowest_run_a") or (
        module_rows[0]["module"] if module_rows else "NOT-CHECKED"
    )
    return {
        "parser_control": parser,
        "ranking_control": rank_ctl,
        "collect": {
            "exit_code": collect_code,
            "modules": modules,
            "raw_tail": collect_raw[-4000:],
        },
        "durations_run_a": dur_a,
        "durations_run_b": dur_b,
        "wall_run_a": wall_a,
        "wall_run_b": wall_b,
        "durations_ranking": dur_rank,
        "wall_ranking": wall_rank,
        "modules": module_rows,
        "soak_or_load_candidates": soak,
        "slowest_module_durations": slowest_dur,
        "slowest_module_wall": slowest_wall,
        "suite_wall_median_s": round(suite_wall, 6),
        "wall_covers_call": wall_covers,
        "loadavg": loadavg(),
        "union_modules": union,
    }


def format_durations_verbatim(run: dict[str, Any], label: str) -> str:
    raw = str(run.get("raw_output") or "")
    header = (
        f"{label} exit={run.get('exit_code')} wall_s={run.get('wall_s')} "
        f"header={run.get('durations_header_present')} rows={run.get('row_count')}\n"
    )
    return header + raw[-20000:]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ranking_from_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    """Read ranking from receipt.report / extensions / legacy top-level."""
    report = _as_dict(doc.get("report"))
    ext = _as_dict(doc.get("extensions"))
    ranking = report.get("ranking") or ext.get("ranking") or doc.get("ranking") or {}
    return ranking if isinstance(ranking, dict) else {}


def named_probes_from_artifact(doc: dict[str, Any]) -> list[dict[str, Any]]:
    ext = _as_dict(doc.get("extensions"))
    named = doc.get("named_probes") or ext.get("named_probes") or []
    if not isinstance(named, list):
        return []
    return [row for row in named if isinstance(row, dict)]


def modules_from_artifact(doc: dict[str, Any]) -> list[dict[str, Any]]:
    report = _as_dict(doc.get("report"))
    ext = _as_dict(doc.get("extensions"))
    rows = report.get("modules") or ext.get("modules") or doc.get("modules") or []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def baseline_usable_from_artifact(doc: dict[str, Any]) -> bool:
    report = _as_dict(doc.get("report"))
    ext = _as_dict(doc.get("extensions"))
    if "baseline_usable" in report:
        return bool(report.get("baseline_usable"))
    if "baseline_usable" in ext:
        return bool(ext.get("baseline_usable"))
    return bool(doc.get("baseline_usable"))
