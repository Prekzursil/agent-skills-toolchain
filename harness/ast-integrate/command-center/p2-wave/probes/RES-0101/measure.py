"""Run the frozen gold set against catalog slices. Gold is never edited here."""
from __future__ import annotations

from typing import Any

from common import (
    GOLD_PATH,
    MEASUREMENT_PATH,
    UNIT_ID,
    dump_json,
    load_json,
    sha256_file,
)
from inventory import write_inventory
from router import ROUTERS


def _by_name(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {t["name"]: t for t in tools}


def _slice_catalogs(tools: list[dict[str, Any]], gold_names: list[str]) -> list[dict[str, Any]]:
    index = _by_name(tools)
    missing = [n for n in gold_names if n not in index]
    if missing:
        raise SystemExit(f"gold tools absent from inventory: {missing}")
    curated = [index[n] for n in gold_names]
    remaining = [t for t in tools if t["name"] not in set(gold_names)]
    remaining.sort(key=lambda t: t["name"])
    n_mid = len(curated) + max(1, (len(remaining) + 1) // 2)
    mid_names = gold_names + [t["name"] for t in remaining[: n_mid - len(curated)]]
    mid = [index[n] for n in mid_names]
    full = list(tools)
    slices = [
        {"label": "curated-gold-only", "size": len(curated), "tools": curated},
        {"label": "mid-plus-distractors", "size": len(mid), "tools": mid},
        {"label": "full-live-inventory", "size": len(full), "tools": full},
    ]
    sizes = [s["size"] for s in slices]
    if len(set(sizes)) < 3:
        raise SystemExit(f"need 3 distinct catalog sizes, got {sizes}")
    if not sizes[0] < sizes[1] < sizes[2]:
        raise SystemExit(f"sizes must strictly increase, got {sizes}")
    return slices


def evaluate(gold: dict[str, Any], inventory: dict[str, Any], router_name: str) -> dict[str, Any]:
    router = ROUTERS[router_name]
    tasks = gold["tasks"]
    gold_names = []
    for t in tasks:
        n = t["gold_tool"]
        if n not in gold_names:
            gold_names.append(n)
    slices = _slice_catalogs(inventory["tools"], gold_names)
    table: list[dict[str, Any]] = []
    per_task: list[dict[str, Any]] = []
    control_ok_every_size = True
    for sl in slices:
        catalog = sl["tools"]
        cat_names = [t["name"] for t in catalog]
        correct = 0
        control_ok = True
        rows = []
        for task in tasks:
            selected = router(task["query"], catalog)
            ok = selected == task["gold_tool"]
            if ok:
                correct += 1
            if task.get("control") and not ok:
                control_ok = False
                control_ok_every_size = False
            rows.append(
                {
                    "task_id": task["id"],
                    "gold_tool": task["gold_tool"],
                    "selected": selected,
                    "correct": ok,
                    "control": bool(task.get("control")),
                }
            )
        n = len(tasks)
        acc = correct / n if n else 0.0
        table.append(
            {
                "label": sl["label"],
                "catalog_size": sl["size"],
                "correct": correct,
                "n_tasks": n,
                "accuracy": round(acc, 6),
                "control_ok": control_ok,
                "catalog_tool_names": cat_names,
            }
        )
        per_task.append({"label": sl["label"], "catalog_size": sl["size"], "rows": rows})
    return {
        "router": router_name,
        "n_tasks": len(tasks),
        "n_sizes": len(table),
        "control_ok_every_size": control_ok_every_size,
        "accuracy_versus_catalog_size": table,
        "per_task": per_task,
    }


def run_measurement() -> dict[str, Any]:
    if not GOLD_PATH.is_file():
        raise SystemExit("gold_task_set.json missing; publish gold before measuring")
    gold = load_json(GOLD_PATH)
    if gold.get("unit_id") != UNIT_ID:
        raise SystemExit("gold unit_id mismatch")
    if not gold.get("published_before_measurement"):
        raise SystemExit("gold set is not marked published-before-measurement")
    if not gold.get("tasks") or len(gold["tasks"]) < 8:
        raise SystemExit("gold task set too small")
    gold_sha = sha256_file(GOLD_PATH)
    inventory = write_inventory()
    primary = evaluate(gold, inventory, "tfidf-cosine-nameboost")
    secondary = evaluate(gold, inventory, "jaccard-description")
    if not primary["control_ok_every_size"]:
        raise SystemExit("control task failed at a catalog size; harness is broken")
    doc = {
        "unit_id": UNIT_ID,
        "gold_path": "command-center/p2-wave/probes/RES-0101/gold_task_set.json",
        "gold_sha256": gold_sha,
        "gold_published_at": gold.get("published_at"),
        "inventory_sha256": inventory["inventory_sha256"],
        "inventory_tool_count": inventory["tool_count"],
        "primary": primary,
        "secondary": secondary,
        "independence": {
            "signal_a": "python TF-IDF cosine over name+description with name-token boost",
            "signal_b": "python Jaccard token overlap over description only (no name boost)",
            "not_the_same_probe_rerun": True,
        },
    }
    dump_json(MEASUREMENT_PATH, doc)
    return doc


if __name__ == "__main__":
    d = run_measurement()
    table = d["primary"]["accuracy_versus_catalog_size"]
    print("gold_sha256", d["gold_sha256"])
    print("inventory_tools", d["inventory_tool_count"])
    for row in table:
        print(
            f"size={row['catalog_size']} acc={row['accuracy']} "
            f"correct={row['correct']}/{row['n_tasks']} control_ok={row['control_ok']} {row['label']}"
        )
    print("control_ok_every_size", d["primary"]["control_ok_every_size"])
