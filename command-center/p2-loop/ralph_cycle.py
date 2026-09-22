#!/usr/bin/env python3
"""P2 ralph-style cycle: emit next READY batch + refresh census/READY.

Does not mint SUCCESS. Prints a machine-readable queue for fan-out agents.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CC = REPO / "command-center"
LOOP = CC / "p2-loop"
CATALOG = CC / "WORK-UNIT-CATALOG.json"
READY = CC / "READY-UNITS.json"
QUEUE = LOOP / "RALPH-QUEUE.json"
STATE = LOOP / "RALPH-STATE.json"


def phase_key(phase: object) -> tuple[int, str]:
    s = "" if phase is None else str(phase)
    m = re.match(r"^(\d+)", s)
    return (int(m.group(1)) if m else 99, s)


def refresh_ready() -> None:
    subprocess.run(
        [sys.executable, str(CC / "ready_units.py")],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )


def census() -> dict:
    from census import census as run_census  # type: ignore

    sys.path.insert(0, str(LOOP))
    return run_census()


def rank(limit: int) -> list[dict]:
    cat = {
        u["id"]: u
        for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]
    }
    ready = json.loads(READY.read_text(encoding="utf-8"))["ready_units"]
    power: Counter[str] = Counter()
    for u in cat.values():
        for dep in u.get("dependencies") or []:
            if dep in cat:
                power[dep] += 1
    ranked = sorted(ready, key=lambda i: (phase_key(cat[i].get("phase")), -power[i], i))
    rows = []
    for i in ranked[:limit]:
        u = cat[i]
        title = u.get("title") or ""
        hostile = any(
            w in title.lower()
            for w in ("windows", "pwsh", "powershell", "acl", "scheduled task")
        )
        rows.append(
            {
                "id": i,
                "phase": u.get("phase"),
                "power": power[i],
                "substrate": u.get("execution_substrate"),
                "output_path": u["output_path"],
                "output_schema": u.get("output_schema"),
                "title": title,
                "linux_feasible": not hostile,
                "owner_approval_required": bool(u.get("owner_approval_required")),
            }
        )
    return rows


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    refresh_ready()
    sys.path.insert(0, str(LOOP))
    from census import census as run_census

    c = run_census()
    rows = [r for r in rank(limit * 2) if r["linux_feasible"]][:limit]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queue = {
        "updated_at": now,
        "census": c,
        "batch_size": len(rows),
        "batch": rows,
        "instructions": (
            "For each unit: measure honestly; emit SUCCESS only with independent "
            "fresh-context review PASS; else BLOCKED. No stub SUCCESS. No nest dumps."
        ),
    }
    QUEUE.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    state = {
        "updated_at": now,
        "mode": "ralph-auto",
        "goal": "green_SUCCESS == 2007",
        "last_census": c,
        "queue_path": str(QUEUE.relative_to(REPO)),
    }
    if STATE.exists():
        prev = json.loads(STATE.read_text(encoding="utf-8"))
        state["cycles"] = int(prev.get("cycles", 0)) + 1
        state["history"] = (prev.get("history") or [])[-20:] + [
            {
                "at": now,
                "green": c["green_SUCCESS"],
                "ready_batch": [r["id"] for r in rows],
            }
        ]
    else:
        state["cycles"] = 1
        state["history"] = [
            {
                "at": now,
                "green": c["green_SUCCESS"],
                "ready_batch": [r["id"] for r in rows],
            }
        ]
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"cycle": state["cycles"], "census": c, "batch": [r["id"] for r in rows]},
            indent=2,
        )
    )
    return 0 if c.get("owner_hard_bar_met") else 1


if __name__ == "__main__":
    raise SystemExit(main())
