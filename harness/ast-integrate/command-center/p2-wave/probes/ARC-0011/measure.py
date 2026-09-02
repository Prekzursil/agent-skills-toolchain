#!/usr/bin/env python3
"""Timed full vs incremental A2 generation against the ARC-0010 analogue."""
from __future__ import annotations

import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent / "ARC-0010"))
import generator as G  # noqa: E402

from scale import (  # noqa: E402
    HALF,
    TARGET,
    analogue_skill_count,
    build_registry,
    dirty_ids_for,
    expected_file_count,
    live_skill_md_count,
    mutate_preset_quorum,
    mutate_workflow_on_error,
)

SPREAD_LIMIT = 0.30
RUNS = 3
STATED_COMMIT_BUDGET_S = 2.0


def _pick(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(str(names))


JSON_PROV = _pick(G, "json_with_prov", "json_with_prov")
VALIDATE = _pick(G, "validate_registry", "validate_registry")
WRITE_TREE = _pick(G, "write_tree", "write_tree")
RENDER_SKILL = _pick(G, "_render_skill", "_render_skill")
RENDER_MD = _pick(G, "_render_markdown", "_render_markdown")
OUTPUT_PATH = _pick(G, "output_path", "output_path")


def machine_state(timer: str) -> dict[str, Any]:
    cpu = platform.processor() or "unknown"
    mem_kb = 1
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_kb = int(line.split()[1])
                break
    except OSError:
        pass
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_model": cpu,
        "nproc": os.cpu_count() or 1,
        "mem_kb": mem_kb,
        "timer": timer,
    }


def clock_fn(name: str) -> Callable[[], float]:
    return time.monotonic if name == "monotonic" else time.perf_counter


def render_one(entry: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> tuple[str, bytes]:
    kind = entry["kind"]
    path = OUTPUT_PATH(entry)
    if kind == "skill":
        return path, RENDER_SKILL(entry)
    if kind in {"rule", "doc"}:
        return path, RENDER_MD(entry, entry["title"], entry["body"])
    if kind == "plugin_manifest":
        payload = {
            "description": entry["description"],
            "hooks": [OUTPUT_PATH(by_id[i]) for i in sorted(entry["hook_ids"])],
            "name": entry["name"],
            "rules": [OUTPUT_PATH(by_id[i]) for i in sorted(entry["rule_ids"])],
            "skills": [OUTPUT_PATH(by_id[i]) for i in sorted(entry["skill_ids"])],
            "version": entry["version"],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "marketplace_entry":
        payload = {
            "category": entry["category"],
            "description": entry["description"],
            "name": entry["name"],
            "plugin_id": entry["plugin_id"],
            "version": entry["version"],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "hook":
        payload = {
            "enabled": entry["enabled"],
            "event": entry["event"],
            "id": entry["id"],
            "script": entry["script"],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "workflow_blueprint":
        payload = {
            "discovery_only": entry["discovery_only"],
            "id": entry["id"],
            "stages": entry["stages"],
            "stopping": entry["stopping"],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "council_preset":
        payload = {
            "id": entry["id"],
            "roles": entry["roles"],
            "stopping": entry["stopping"],
            "voting": entry["voting"],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "workflow_catalog":
        members = [by_id[i] for i in sorted(entry["member_ids"])]
        payload = {
            "id": entry["id"],
            "members": [
                {
                    "discovery_only": m["discovery_only"],
                    "id": m["id"],
                    "stages": m["stages"],
                    "stopping": m["stopping"],
                }
                for m in members
            ],
        }
        return path, JSON_PROV(entry, payload)
    if kind == "council_catalog":
        members = [by_id[i] for i in sorted(entry["member_ids"])]
        payload = {
            "id": entry["id"],
            "members": [
                {
                    "id": m["id"],
                    "roles": m["roles"],
                    "stopping": m["stopping"],
                    "voting": m["voting"],
                }
                for m in members
            ],
        }
        return path, JSON_PROV(entry, payload)
    raise ValueError(f"unrendered-kind:{kind}")


def generate_selected(
    registry: dict[str, Any], ids: set[str], *, validate: bool
) -> dict[str, bytes]:
    if validate:
        VALIDATE(registry)
    entries = sorted(registry["entries"], key=lambda e: (e["kind"], e["id"]))
    by_id = {e["id"]: e for e in entries}
    out: dict[str, bytes] = {}
    for entry in entries:
        if entry["id"] in ids:
            path, raw = render_one(entry, by_id)
            out[path] = raw
    return out


def write_subset(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in sorted(files.items()):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def _spread(xs: list[float]) -> float:
    med = statistics.median(xs)
    if med <= 0:
        return 0.0
    return (max(xs) - min(xs)) / med


def _timed(clk: Callable[[], float], fn: Callable[[], Any]) -> tuple[Any, float]:
    t0 = clk()
    val = fn()
    return val, clk() - t0


def _pack(xs: list[float]) -> dict[str, Any]:
    return {
        "runs_s": xs,
        "median_s": statistics.median(xs),
        "min_s": min(xs),
        "max_s": max(xs),
        "spread": _spread(xs),
    }


def measure_size(
    n_wf: int,
    n_proto: int,
    n_preset: int,
    n_skill: int,
    *,
    mutate: str,
    timer_name: str,
    runs: int = RUNS,
) -> dict[str, Any]:
    clk = clock_fn(timer_name)
    mutator = (
        mutate_workflow_on_error if mutate == "workflow_on_error" else mutate_preset_quorum
    )
    expected = expected_file_count(n_wf, n_proto, n_preset, n_skill)
    registry = build_registry(n_wf, n_proto, n_preset, n_skill)
    warmup = G.generate(registry)
    if len(warmup) != expected:
        raise RuntimeError(f"file-count {len(warmup)} != expected {expected}")

    full_gen: list[float] = []
    full_val: list[float] = []
    full_write: list[float] = []
    full_pipe: list[float] = []
    incr_render: list[float] = []
    incr_write: list[float] = []
    incr_with_val: list[float] = []
    incr_skip_val: list[float] = []
    incr_files = 0
    incr_bytes = 0
    full_bytes = 0
    byte_match = True

    with tempfile.TemporaryDirectory(prefix="arc0011-") as tmp:
        full_root = Path(tmp) / "full"
        incr_root = Path(tmp) / "incr"
        WRITE_TREE(warmup, incr_root)
        for _ in range(runs):
            changed = mutator(registry)
            dirty = dirty_ids_for(registry, changed)

            _, tv = _timed(clk, lambda: VALIDATE(registry))
            files, tg = _timed(clk, lambda: G.generate(registry))
            full_bytes = sum(len(v) for v in files.values())
            _, tw = _timed(clk, lambda: WRITE_TREE(files, full_root))
            full_val.append(tv)
            full_gen.append(tg)
            full_write.append(tw)
            full_pipe.append(tg + tw)

            sel, tr = _timed(
                clk, lambda: generate_selected(registry, dirty, validate=False)
            )
            incr_files = len(sel)
            incr_bytes = sum(len(v) for v in sel.values())
            for rel, raw in sel.items():
                if files.get(rel) != raw:
                    byte_match = False
            _, tiw = _timed(clk, lambda: write_subset(sel, incr_root))
            incr_render.append(tr)
            incr_write.append(tiw)
            incr_skip_val.append(tr + tiw)
            incr_with_val.append(tv + tr + tiw)

    return {
        "workflows": n_wf,
        "protocols": n_proto,
        "presets": n_preset,
        "skills": n_skill,
        "mutate": mutate,
        "timer": timer_name,
        "full_file_writes": expected,
        "incremental_file_writes": incr_files,
        "full_bytes": full_bytes,
        "incremental_bytes": incr_bytes,
        "incremental_bytes_match_full_for_dirty_paths": byte_match,
        "validate": _pack(full_val),
        "full_generate_includes_validate": _pack(full_gen),
        "full_write_tree": _pack(full_write),
        "full_pipeline": _pack(full_pipe),
        "incremental_render_no_validate": _pack(incr_render),
        "incremental_write_subset": _pack(incr_write),
        "incremental_pipeline_with_validate": _pack(incr_with_val),
        "incremental_pipeline_skip_validate": _pack(incr_skip_val),
    }


def campaign(*, mutate: str, timer_name: str) -> dict[str, Any]:
    n_skill = analogue_skill_count()
    live_skills = live_skill_md_count(REPO)
    sizes = []
    for label, spec in (("half", HALF), ("target", TARGET)):
        row = measure_size(
            spec["workflows"],
            spec["protocols"],
            spec["presets"],
            n_skill,
            mutate=mutate,
            timer_name=timer_name,
        )
        row["label"] = label
        sizes.append(row)
    half, target = sizes[0], sizes[1]
    max_spread = max(
        target["full_pipeline"]["spread"],
        target["incremental_pipeline_with_validate"]["spread"],
        half["full_pipeline"]["spread"],
    )
    files_h = half["full_file_writes"]
    files_t = target["full_file_writes"]
    t_h = half["full_pipeline"]["median_s"]
    t_t = target["full_pipeline"]["median_s"]
    slope = (t_t - t_h) / (files_t - files_h) if files_t != files_h else None
    fit_files = None
    if slope and slope > 0:
        fit_files = files_t + (STATED_COMMIT_BUDGET_S - t_t) / slope
    return {
        "analogue_skill_count": n_skill,
        "live_skill_md_excluding_p2_wave": live_skills,
        "mutate": mutate,
        "timer": timer_name,
        "sizes": sizes,
        "max_spread": max_spread,
        "claim_valid": max_spread <= SPREAD_LIMIT,
        "crossover_reached_at_target": bool(t_t >= STATED_COMMIT_BUDGET_S),
        "stated_commit_budget_s": STATED_COMMIT_BUDGET_S,
        "two_point_slope_s_per_file": slope,
        "fit_files_at_budget": fit_files,
        "libraries_present": {
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json": (
                REPO / "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
            ).is_file(),
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": (
                REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ).is_file(),
        },
        "machine": machine_state(timer_name),
        "file_write_formula": "7_shared + skills + protocol_docs + workflows + presets",
        "spread_limit": SPREAD_LIMIT,
    }


def agree(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    for sa, sb in zip(a["sizes"], b["sizes"]):
        if sa["full_file_writes"] != sb["full_file_writes"]:
            return False, (
                f"full file-write disagree {sa['full_file_writes']} vs {sb['full_file_writes']}"
            )
        if sa["incremental_file_writes"] != sb["incremental_file_writes"]:
            return False, (
                "incr file-write disagree "
                f"{sa['incremental_file_writes']} vs {sb['incremental_file_writes']}"
            )
        ta = sa["full_pipeline"]["median_s"]
        tb = sb["full_pipeline"]["median_s"]
        if abs(ta - tb) / max(ta, tb, 1e-9) > SPREAD_LIMIT:
            return False, f"full_pipeline median disagree {ta:.6f} vs {tb:.6f}"
    return True, "ok"
