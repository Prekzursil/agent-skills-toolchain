"""Interleaved before/after import-time measurement plus one cold-cache run."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from profiler import (
    PAYLOAD_BYTES,
    iqr,
    median,
    run_import,
    stage_commit,
)
from scenario import (
    AFTER_ID,
    AFTER_SRC,
    BEFORE_ID,
    BEFORE_SRC,
    ENTRY,
    HERE,
    REPS,
)


def _stage_pair(work: Path) -> tuple[Path, Path]:
    before = stage_commit(BEFORE_SRC, work / "before", with_payload=False)
    after = stage_commit(AFTER_SRC, work / "after", with_payload=True)
    return before, after


def module_median_table(samples: list[dict]) -> list[dict]:
    acc: dict[str, list[int]] = {}
    cum: dict[str, list[int]] = {}
    for sample in samples:
        for row in sample.get("package_modules") or []:
            acc.setdefault(row["module"], []).append(int(row["self_us"]))
            cum.setdefault(row["module"], []).append(int(row["cumulative_us"]))
    out = []
    for name in sorted(acc):
        selfs = acc[name]
        cums = cum[name]
        out.append(
            {
                "module": name,
                "self_us": int(median([float(x) for x in selfs])),
                "cumulative_us": int(median([float(x) for x in cums])),
                "self_ms": round(median([float(x) for x in selfs]) / 1000.0, 6),
                "n": len(selfs),
            }
        )
    return out


def largest_increase(before_rows: list[dict], after_rows: list[dict]) -> dict:
    bmap = {r["module"]: r["self_us"] for r in before_rows}
    best = None
    for row in after_rows:
        delta = row["self_us"] - bmap.get(row["module"], 0)
        cand = {
            "module": row["module"],
            "delta_self_us": int(delta),
            "delta_self_ms": round(delta / 1000.0, 6),
            "after_self_us": int(row["self_us"]),
            "before_self_us": int(bmap.get(row["module"], 0)),
        }
        if best is None or cand["delta_self_us"] > best["delta_self_us"]:
            best = cand
    if best is None:
        raise RuntimeError("no after modules to attribute")
    return best


def run_campaign(work: Path | None = None) -> dict:
    work = work or (HERE / "_stage")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    before_root, after_root = _stage_pair(work)
    roots = {BEFORE_ID: before_root, AFTER_ID: after_root}

    raw: list[dict] = []
    by_commit: dict[str, list[dict]] = {BEFORE_ID: [], AFTER_ID: []}
    order = 0
    # Interleave A B A B ... (before=A, after=B). Not blocked AAAA then BBBB.
    for i in range(REPS):
        for cid in (BEFORE_ID, AFTER_ID):
            order += 1
            sample = run_import(roots[cid], cold=False)
            rec = {
                "order": order,
                "pair_index": i + 1,
                "commit_id": cid,
                "wall_ms": sample["wall_ms"],
                "cache": "warm",
                "package_self_us": sample["package_self_us"],
                "entry_cumulative_us": sample["entry_cumulative_us"],
                "importtime_self_ms": sample["importtime_self_ms"],
                "package_modules": sample["package_modules"],
            }
            raw.append(rec)
            by_commit[cid].append(sample)

    cold = run_import(after_root, cold=True)
    cold_rec = {
        "included": True,
        "commit_id": AFTER_ID,
        "method": (cold.get("fadvise") or {}).get(
            "method", "posix_fadvise(POSIX_FADV_DONTNEED)"
        ),
        "advised_files": (cold.get("fadvise") or {}).get("advised"),
        "wall_ms": cold["wall_ms"],
        "package_self_us": cold["package_self_us"],
        "payload_bytes": PAYLOAD_BYTES,
        "cache": "cold",
        "package_modules": cold["package_modules"],
    }

    before_walls = [s["wall_ms"] for s in by_commit[BEFORE_ID]]
    after_walls = [s["wall_ms"] for s in by_commit[AFTER_ID]]
    med_b = median(before_walls)
    med_a = median(after_walls)
    delta = med_a - med_b
    noise = max(iqr(before_walls), iqr(after_walls), 0.05)
    table = {
        BEFORE_ID: module_median_table(by_commit[BEFORE_ID]),
        AFTER_ID: module_median_table(by_commit[AFTER_ID]),
    }
    largest = largest_increase(table[BEFORE_ID], table[AFTER_ID])
    measurable = abs(delta) > noise
    slower = measurable and delta > 0

    return {
        "commits": [
            {
                "id": BEFORE_ID,
                "label": "fixture before (core+util only)",
                "entry_point": ENTRY,
                "tree": str(BEFORE_SRC.relative_to(HERE.parents[3]).as_posix()),
                "git": "NOT-CHECKED (this worktree has no .git; fixture commit stand-in)",
            },
            {
                "id": AFTER_ID,
                "label": "fixture after (adds tool_startup.extra payload read)",
                "entry_point": ENTRY,
                "tree": str(AFTER_SRC.relative_to(HERE.parents[3]).as_posix()),
                "git": "NOT-CHECKED (this worktree has no .git; fixture commit stand-in)",
            },
        ],
        "interleaving": "A B A B (before/after, 11 pairs, not blocked)",
        "repetitions": REPS,
        "raw_repetitions": [
            {
                "order": r["order"],
                "commit_id": r["commit_id"],
                "wall_ms": r["wall_ms"],
                "cache": r["cache"],
                "package_self_us": r["package_self_us"],
                "entry_cumulative_us": r["entry_cumulative_us"],
            }
            for r in raw
        ],
        "per_module_cost_table": table,
        "cold_cache_measurement": {
            "included": True,
            "commit_id": cold_rec["commit_id"],
            "method": cold_rec["method"],
            "advised_files": cold_rec["advised_files"],
            "wall_ms": cold_rec["wall_ms"],
            "payload_bytes": cold_rec["payload_bytes"],
            "package_self_us": cold_rec["package_self_us"],
        },
        "summaries": {
            BEFORE_ID: {
                "median_wall_ms": round(med_b, 4),
                "iqr_wall_ms": round(iqr(before_walls), 4),
                "n": len(before_walls),
                "raw_wall_ms": before_walls,
            },
            AFTER_ID: {
                "median_wall_ms": round(med_a, 4),
                "iqr_wall_ms": round(iqr(after_walls), 4),
                "n": len(after_walls),
                "raw_wall_ms": after_walls,
            },
        },
        "delta_ms": round(delta, 4),
        "noise_floor_ms": round(noise, 4),
        "measurable": measurable,
        "after_slower": slower,
        "largest_increase_module": largest,
        "cold_sample": cold_rec,
        "raw_full": raw,
    }


def write_raw(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    out = run_campaign()
    write_raw(out, HERE / "probe-campaign.raw.json")
    print(
        f"delta_ms={out['delta_ms']} noise={out['noise_floor_ms']} "
        f"largest={out['largest_increase_module']['module']} "
        f"cold_ms={out['cold_cache_measurement']['wall_ms']}"
    )
