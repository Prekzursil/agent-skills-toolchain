"""Run baseline + per-component ablations on the frozen gold task set."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from catalog import COMPONENTS, CONTROL_COMPONENT, ablate, load_catalog
from router import ABSTAIN, route

HERE = Path(__file__).resolve().parent
GOLD_PATH = HERE / "gold_tasks.json"
EPS = 0.02  # |delta| <= EPS is approximately zero (declared before scoring)


def load_gold() -> dict:
    raw = GOLD_PATH.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    tasks = doc["tasks"]
    if len(tasks) < 12:
        raise ValueError(f"gold set too small n={len(tasks)}")
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate gold task ids")
    return {
        "doc": doc,
        "tasks": tasks,
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "bytes": len(raw.replace(b"\r\n", b"\n")),
    }


def evaluate(skills: list[dict], tasks: list[dict]) -> dict:
    rows = []
    n_ok = 0
    for t in tasks:
        pred = route(t["query"], skills)
        ok = pred["chosen"] == t["gold"]
        n_ok += int(ok)
        rows.append(
            {
                "id": t["id"],
                "gold": t["gold"],
                "chosen": pred["chosen"],
                "correct": ok,
                "best_score": pred["best_score"],
                "abstained": pred["abstained"],
                "top": pred["ranked"][:3],
            }
        )
    n = len(tasks)
    return {
        "n": n,
        "n_correct": n_ok,
        "accuracy": n_ok / n if n else 0.0,
        "rows": rows,
    }


def run_experiment() -> dict:
    gold = load_gold()
    skills = load_catalog()
    baseline = evaluate(skills, gold["tasks"])
    table = []
    traces = {"full": baseline}

    def row_for(name: str, acc: dict, *, control: bool) -> dict:
        delta = acc["accuracy"] - baseline["accuracy"]
        return {
            "component": name,
            "accuracy": round(acc["accuracy"], 6),
            "n_correct": acc["n_correct"],
            "n_tasks": acc["n"],
            "delta_from_baseline": round(delta, 6),
            "abs_delta": round(abs(delta), 6),
            "approximately_zero": abs(delta) <= EPS,
            "is_control": control,
            "effect": (
                "none-measured"
                if abs(delta) <= EPS
                else ("hurts" if delta < 0 else "helps")
            ),
        }

    table.append(row_for("full", baseline, control=False))
    for comp in COMPONENTS:
        acc = evaluate(ablate(skills, comp), gold["tasks"])
        traces[comp] = acc
        table.append(row_for(comp, acc, control=(comp == CONTROL_COMPONENT)))

    control_rows = [r for r in table if r["is_control"]]
    if len(control_rows) != 1:
        raise RuntimeError("control row missing")
    control = control_rows[0]

    movers = [
        r
        for r in table
        if r["component"] not in {"full", CONTROL_COMPONENT}
        and not r["approximately_zero"]
    ]
    return {
        "gold": {
            "id": gold["doc"]["id"],
            "sha256": gold["sha256"],
            "bytes": gold["bytes"],
            "n_tasks": len(gold["tasks"]),
            "res0101_task_set": gold["doc"]["res0101_task_set"],
            "published_before_measurement": gold["doc"][
                "published_before_measurement"
            ],
        },
        "catalog": [
            {
                "id": s["id"],
                "source": s["source"],
                "path": s["path"],
                "sha256": s["sha256"],
                "component_chars": s["component_chars"],
            }
            for s in skills
        ],
        "baseline": {
            "accuracy": round(baseline["accuracy"], 6),
            "n_correct": baseline["n_correct"],
            "n_tasks": baseline["n"],
        },
        "ablation_delta_table": table,
        "approximately_zero_control": control,
        "components_with_measured_effect": [r["component"] for r in movers],
        "components_with_no_measured_effect": [
            r["component"]
            for r in table
            if r["component"] not in {"full"} and r["approximately_zero"]
        ],
        "eps": EPS,
        "abstain_label": ABSTAIN,
        "traces": traces,
    }
