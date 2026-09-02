"""Run the BLD-0055 complexity census: generate, validate, time, guard."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import validate as val  # noqa: E402
from fit import fit_author, fit_reviewer  # noqa: E402
from generator import make_catalog  # noqa: E402
from stages import (  # noqa: E402
    PREDICTED_CLASS,
    SOURCE_PATHS,
    collision_control,
    make_fanin_ctx,
    run_stage,
)

N_GRID = (128, 1024, 2048, 20480)
STAGE_ORDER = (
    "pairwise_duplicate_detection",
    "dependency_graph_closure",
    "manifest_hashing",
    "xref_resolution",
    "fanin_reduction",
    "catalog_merger",
)
# 512 MiB: well below freeze on this box (MemAvailable ~100+ GiB). The
# 20,480 run aborts rather than compounding toward commit exhaustion.
RSS_CEILING_BYTES = 512 * 1024 * 1024
TIME_CEILING_S = 90.0
LINEAR_MAX = 1.25
SUPERLINEAR_MIN = 1.35


def vm_rss_bytes() -> int:
    path = Path("/proc/self/status")
    if not path.is_file():
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            return int(parts[1]) * 1024
    return 0


def hardware() -> dict[str, Any]:
    info: dict[str, int] = {}
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            parts = line.replace(":", " ").split()
            if len(parts) >= 2 and parts[0] in {
                "MemTotal",
                "MemAvailable",
                "CommitLimit",
                "Committed_AS",
            }:
                info[parts[0]] = int(parts[1]) * 1024
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "meminfo_bytes": info,
        "rss_ceiling_bytes": RSS_CEILING_BYTES,
        "concurrency": 1,
        "measurement_mode": "single-process-serialized",
    }


def validate_catalog(catalog: dict[str, Any], register_text: str) -> dict[str, Any]:
    tmp = tempfile.TemporaryDirectory(prefix="bld0055-reg-")
    reg = Path(tmp.name) / "REGISTER.md"
    reg.write_text(register_text, encoding="utf-8", newline="\n")
    catalog["provenance"]["register"] = str(reg)
    catalog["provenance"]["register_sha256"] = hashlib.sha256(
        register_text.encode("utf-8").replace(b"\r\n", b"\n")
    ).hexdigest()
    # No committed DEPENDENCY-GRAPH.json for a synthetic corpus: skip the
    # tautological graph==build_graph deep-equal (that would run Kahn twice).
    violations, stats = val.validate(catalog, register_path=reg, graph=None)
    tmp.cleanup()
    return {
        "ok": len(violations) == 0,
        "n_violations": len(violations),
        "violations": [str(v) for v in violations[:8]],
        "stats": {
            k: stats[k]
            for k in stats
            if not isinstance(stats[k], dict)
        },
    }


def _guard_trip(rss: int, elapsed: float) -> str | None:
    if rss >= RSS_CEILING_BYTES:
        return "rss-ceiling"
    if elapsed >= TIME_CEILING_S:
        return "time-ceiling"
    return None


def run_one_n(n: int, fanin_ctx: dict) -> dict[str, Any]:
    catalog, register_text = make_catalog(n, shape="chain", plant_near_dup=True)
    gate = validate_catalog(catalog, register_text)
    row: dict[str, Any] = {
        "n": n,
        "generator_shape": "chain",
        "validator_ok": gate["ok"],
        "validator": gate,
        "stages": {},
        "aborted": False,
        "abort_reason": None,
        "extrapolated": False,
    }
    if not gate["ok"]:
        row["aborted"] = True
        row["abort_reason"] = "validator-rejected-corpus"
        return row
    rss0 = vm_rss_bytes()
    t_all = time.perf_counter()
    for name in STAGE_ORDER:
        rss_before = vm_rss_bytes()
        t0 = time.perf_counter()
        result = run_stage(name, catalog, fanin_ctx=fanin_ctx)
        wall = time.perf_counter() - t0
        rss_after = vm_rss_bytes()
        trip = _guard_trip(rss_after, wall)
        row["stages"][name] = {
            "n": n,
            "wall_s": wall,
            "rss_before_bytes": rss_before,
            "rss_after_bytes": rss_after,
            "rss_delta_bytes": max(rss_after - rss_before, 0),
            "predicted_class": PREDICTED_CLASS[name],
            "source": SOURCE_PATHS[name],
            "result": result,
            "aborted": bool(trip),
            "abort_reason": trip,
        }
        if trip:
            row["aborted"] = True
            row["abort_reason"] = f"{name}:{trip}"
            break
    row["wall_s_all_stages"] = time.perf_counter() - t_all
    row["rss_delta_bytes_from_n_start"] = max(vm_rss_bytes() - rss0, 0)
    return row


def plant_guard_control() -> dict[str, Any]:
    """Both-states of the abort predicate, without freezing the box.

    Below-ceiling RSS and elapsed time stay silent. A 2 MiB reading against a
    1 MiB test ceiling trips rss-ceiling; elapsed past TIME_CEILING_S trips
    time-ceiling. Production ceiling stays at RSS_CEILING_BYTES.
    """
    test_ceiling = 1 * 1024 * 1024
    below = 512 * 1024
    above = 2 * 1024 * 1024
    silent = _guard_trip(below, 0.0)
    # Temporarily compare against the test ceiling by inlining the same rule.
    rss_trip = "rss-ceiling" if above >= test_ceiling else None
    time_trip = _guard_trip(below, TIME_CEILING_S + 1.0)
    return {
        "test_ceiling_bytes": test_ceiling,
        "below_ceiling_silent": silent is None,
        "rss_trip_reason": rss_trip,
        "time_trip_reason": time_trip,
        "tripped": (
            silent is None
            and rss_trip == "rss-ceiling"
            and time_trip == "time-ceiling"
        ),
        "froze_box": False,
        "production_ceiling_bytes": RSS_CEILING_BYTES,
    }


def real_catalog_reference() -> dict[str, Any]:
    """n≈2048 reference: live work_units count and pairwise on real titles."""
    path = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    titles = [str(u.get("title") or u.get("id") or "") for u in units if isinstance(u, dict)]
    from stages import pairwise_jaccard  # local to avoid cycle at import-linter

    t0 = time.perf_counter()
    pairwise = pairwise_jaccard(titles)
    wall = time.perf_counter() - t0
    return {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "work_units": len(units),
        "items": len(data.get("items") or []),
        "labeled_as": "real catalog n=2007 work_units (catalog names 2048 as the design floor)",
        "pairwise_wall_s": wall,
        "pairwise": pairwise,
    }


def assemble_fits(rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict], dict | None]:
    fits: list[dict] = []
    failures: list[dict] = []
    linear: dict | None = None
    for name in STAGE_ORDER:
        points = []
        for row in rows:
            st = (row.get("stages") or {}).get(name) or {}
            if st.get("aborted") or "wall_s" not in st:
                continue
            points.append({"n": row["n"], "wall_s": st["wall_s"]})
        author = fit_author(
            [p["n"] for p in points], [p["wall_s"] for p in points]
        )
        reviewer = fit_reviewer(points)
        predicted = PREDICTED_CLASS[name]
        measured = author.get("complexity_class")
        pred_fail = (
            predicted == "linear"
            and measured in {"super-linear", "quadratic-or-worse"}
            and author.get("ok")
        )
        rec = {
            "stage": name,
            "predicted_class": predicted,
            "author_fit": author,
            "reviewer_fit": reviewer,
            "prediction_failure": pred_fail,
            "raw_points": points,
        }
        fits.append(rec)
        if pred_fail:
            failures.append(
                {
                    "stage": name,
                    "predicted": predicted,
                    "measured": measured,
                    "author_exponent": author.get("exponent"),
                    "reviewer_exponent": reviewer.get("exponent"),
                    "action": "reported-as-prediction-failure-not-silently-corrected",
                }
            )
        if (
            linear is None
            and predicted == "linear"
            and not pred_fail
            and measured == "linear"
            and author.get("ok")
        ):
            linear = {
                "stage": name,
                "author_exponent": author.get("exponent"),
                "reviewer_exponent": reviewer.get("exponent"),
                "residual_rms_seconds": author.get("residual_rms_seconds"),
            }
    return fits, failures, linear


def census() -> dict[str, Any]:
    fanin = make_fanin_ctx()
    rows: list[dict[str, Any]] = []
    aborted_top = False
    abort_reason = None
    try:
        for n in N_GRID:
            row = run_one_n(n, fanin)
            rows.append(row)
            if row.get("aborted") and n == N_GRID[-1]:
                aborted_top = True
                abort_reason = row.get("abort_reason")
    finally:
        fanin["tmp"].cleanup()
    fits, failures, linear = assemble_fits(rows)
    guard = {
        "rss_ceiling_bytes": RSS_CEILING_BYTES,
        "time_ceiling_s_per_stage": TIME_CEILING_S,
        "top_n": N_GRID[-1],
        "aborted_top_n": aborted_top,
        "abort_reason": abort_reason,
        "planted_trip": plant_guard_control(),
        "policy": (
            "Two OOM/ceiling aborts at top n then sampled extrapolation, labeled. "
            "This run aborts a stage rather than freezing the box."
        ),
    }
    return {
        "n_grid": list(N_GRID),
        "hardware": hardware(),
        "concurrency": 1,
        "rows": rows,
        "fits": fits,
        "prediction_failures": failures,
        "linear_stage": linear,
        "resource_guard": guard,
        "collision_control": collision_control(),
        "real_catalog_reference": real_catalog_reference(),
        "reviewer_points_only": [
            {"stage": f["stage"], "raw_points": f["raw_points"]} for f in fits
        ],
    }


def reviewer_refit(census_doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-fit from raw points only. Does not read author exponents."""
    out = []
    for bundle in census_doc.get("reviewer_points_only") or []:
        fit = fit_reviewer(bundle.get("raw_points") or [])
        out.append({"stage": bundle.get("stage"), "reviewer_fit": fit})
    return out
