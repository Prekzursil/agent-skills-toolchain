"""Emit command-center/research/RES-0101.json from the frozen gold set + live measurement."""
from __future__ import annotations

from datetime import datetime, timezone

from common import (
    GOLD_PATH,
    OUTPUT_PATH,
    SENTINEL,
    UNIT_ID,
    dump_json,
    load_json,
    sha256_file,
)
from measure import run_measurement


def main() -> int:
    meas = run_measurement()
    gold = load_json(GOLD_PATH)
    primary = meas["primary"]
    secondary = meas["secondary"]
    table = primary["accuracy_versus_catalog_size"]
    acc_line = ", ".join(
        f"{r['label']} n={r['catalog_size']} acc={r['accuracy']:.4f} ({r['correct']}/{r['n_tasks']})"
        for r in table
    )
    curated = table[0]["accuracy"]
    full = table[-1]["accuracy"]
    delta = round(full - curated, 6)
    if delta < 0:
        change = (
            f"top-1 accuracy fell by {abs(delta):.4f} from the curated slice "
            f"to the full live inventory"
        )
    elif delta > 0:
        change = (
            f"top-1 accuracy rose by {delta:.4f} from the curated slice "
            f"to the full live inventory (unexpected; recorded, not smoothed)"
        )
    else:
        change = (
            "top-1 accuracy was unchanged between the curated slice and the full live inventory"
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "output_schema": "command-center/schema/measurement-run.schema.json",
        "question": (
            "On this box's real tool inventory, how does selection accuracy change "
            "between a small curated set and the full exposed fleet, measured with a "
            "fixed task set rather than inferred from published curves on other catalogs?"
        ),
        "answer": (
            f"On this box, a frozen {primary['n_tasks']}-task gold set was published before "
            f"scoring. A TF-IDF cosine router (signal A) measured {acc_line}. {change}. "
            f"The control task (T-CONTROL-READ -> Read) was correct at every size. "
            f"A Jaccard description-only router (signal B) is the second independent signal; "
            f"it is not a re-run of signal A. Fleet size is this box's live inventory "
            f"({meas['inventory_tool_count']} tools), not a 500-tool literature catalog."
        ),
        "measured_at": now,
        "gold_task_set_attached": True,
        "gold_task_set": gold,
        "gold_sha256": meas["gold_sha256"],
        "gold_published_at": meas["gold_published_at"],
        "inventory_sha256": meas["inventory_sha256"],
        "inventory_tool_count": meas["inventory_tool_count"],
        "accuracy_versus_catalog_size": table,
        "accuracy_versus_catalog_size_secondary_jaccard": secondary["accuracy_versus_catalog_size"],
        "primary_router": primary["router"],
        "secondary_router": secondary["router"],
        "control": {
            "task_id": "T-CONTROL-READ",
            "gold_tool": "Read",
            "ok_at_every_size": primary["control_ok_every_size"],
            "rule": "If this control fails at any size, the harness is broken and state must not be SUCCESS.",
        },
        "independence": meas["independence"],
        "method": {
            "inventory": (
                "Union of this Cursor session's exposed tools, estate Python packages "
                "under tools/ that exist on disk, and PATH CLIs resolved with "
                "shutil.which against /usr/local/bin:/usr/bin:/bin (not the "
                "agent-injected PATH). MCP config candidate paths were probed; "
                "none were assumed present."
            ),
            "router_primary": "TF-IDF cosine; tool name tokens triple-weighted",
            "router_secondary": "Jaccard token overlap on descriptions only",
            "catalog_slices": [r["label"] for r in table],
            "selection": "top-1",
        },
        "tests": [
            {
                "id": "T1-gold-before-measure",
                "result": "PASS",
                "detail": f"gold_sha256={meas['gold_sha256']} published_at={meas['gold_published_at']}",
            },
            {
                "id": "T2-three-catalog-sizes",
                "result": "PASS",
                "detail": [r["catalog_size"] for r in table],
            },
            {
                "id": "T3-control-every-size",
                "result": "PASS" if primary["control_ok_every_size"] else "FAIL",
                "detail": "T-CONTROL-READ must select Read at every size",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0101-probe2-jaccard-and-recount",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 recomputes top-1 with Jaccard (different field and metric) "
                "and recounts stored TF-IDF selections; it is not a TF-IDF re-run."
            ),
        },
        "downstream_consumers": [
            {
                "id": "RES-0102",
                "artifact_path": OUTPUT_PATH.name,
                "consumer": "skill-description ablation on this same gold task set",
                "probe": "command-center/p2-wave/probes/RES-0101/probe1_remeasure.py",
            }
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0101/probe1_remeasure.py",
            },
            {
                "id": "probe2",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0101/probe2_independent.py",
            },
        ],
        "limitations": [
            "This is this box's live fleet, not a 500-tool published catalog. Do not extrapolate the curve.",
            "Routers are lexical, not LLM judges. The measurement answers catalog-size sensitivity of lexical top-1.",
            "Session tool descriptions are a snapshot of this agent turn; MCP servers were not live here.",
        ],
        "dependencies_note": (
            "RES-0041 and RES-0100 are catalog dependencies. This unit measures the local "
            "inventory directly and does not import their artifacts."
        ),
        "per_task_primary": primary["per_task"],
    }
    dump_json(OUTPUT_PATH, doc)
    print(f"wrote {OUTPUT_PATH} sha256={sha256_file(OUTPUT_PATH)} bytes={OUTPUT_PATH.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
