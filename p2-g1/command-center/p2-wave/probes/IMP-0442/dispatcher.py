"""Work-unit dispatcher honoring the declared execution substrate (IMP-0442).

local-serialized means STRICTLY one at a time when serial_lock is armed.
Dry-run simulation: deterministic ticks, no processes, peak accounting only.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

SUBSTRATES = ("cloud-batch", "local-parallel", "local-serialized",
              "worktree-isolated")
SERIAL_SUBSTRATE = "local-serialized"
PER_SUBSTRATE_CAP = 10

# Locked dry-run slice from the IMP-0442 receipt (10 units per substrate).
RECEIPT_IDS = {
    "local-serialized": ["ADV-0009", "ADV-0011", "ADV-0012", "ADV-0014",
                         "ADV-0016", "ADV-0017", "ADV-0018", "ADV-0019",
                         "ADV-0021", "ADV-0023"],
    "local-parallel": ["ADV-0002", "ADV-0004", "ADV-0005", "ADV-0006",
                       "ADV-0007", "ADV-0013", "ADV-0015", "ADV-0035",
                       "ADV-0041", "ADV-0045"],
    "worktree-isolated": ["ADV-0001", "ADV-0003", "ADV-0008", "ADV-0010",
                          "ADV-0022", "ADV-0024", "ADV-0025", "ADV-0027",
                          "ADV-0028", "ADV-0029"],
    "cloud-batch": ["ADV-0020", "ADV-0080", "ADV-0083", "ADV-0129",
                    "ADV-0135", "ARC-0072", "ARC-0099", "ARC-0105",
                    "ARC-0109", "AUD-0023"],
}


def load_substrates(catalog_path: Path | None = None) -> dict:
    doc = json.loads((catalog_path or CATALOG).read_text(encoding="utf-8"))
    out = {}
    for u in doc.get("work_units") or []:
        uid = u.get("id")
        sub = u.get("execution_substrate")
        if uid and sub in SUBSTRATES:
            out[uid] = sub
    return out


def build_assignments(substrates: dict) -> tuple[dict, list]:
    """Prefer the receipt's locked ids; swap in same-substrate live ids on drift."""
    assignments = {}
    swaps = []
    pool = {s: sorted(u for u, v in substrates.items() if v == s)
            for s in SUBSTRATES}
    for sub in SUBSTRATES:
        taken = []
        for uid in RECEIPT_IDS[sub]:
            if substrates.get(uid) == sub:
                taken.append(uid)
            else:
                swaps.append({"unit_id": uid, "receipt_substrate": sub,
                              "live_catalog_substrate": substrates.get(uid)})
        for uid in pool[sub]:
            if len(taken) >= PER_SUBSTRATE_CAP:
                break
            if uid not in taken:
                taken.append(uid)
        for uid in taken:
            assignments[uid] = sub
    return assignments, swaps


def run_dry_run(assignments: dict, duration_ticks: int = 8,
                serial_lock: bool = True,
                per_substrate_cap: int = PER_SUBSTRATE_CAP) -> dict:
    """Simulate concurrent dispatch; return per-tick concurrency + peaks."""
    queues = {s: [u for u, v in sorted(assignments.items()) if v == s]
              for s in SUBSTRATES}
    in_flight = {s: [] for s in SUBSTRATES}
    finished = {s: 0 for s in SUBSTRATES}
    series = []

    tick = 0
    while any(queues[s] or in_flight[s] for s in SUBSTRATES) or tick == 0:
        concurrent = {}
        for s in SUBSTRATES:
            in_flight[s] = [u for u in in_flight[s] if tick - u[1] < duration_ticks]
            if s == SERIAL_SUBSTRATE and serial_lock:
                if not in_flight[s]:
                    if queues[s]:
                        u = queues[s].pop(0)
                        in_flight[s].append((u, tick))
            else:
                while queues[s] and len(in_flight[s]) < per_substrate_cap:
                    u = queues[s].pop(0)
                    in_flight[s].append((u, tick))
            concurrent[s] = len(in_flight[s])
        series.append({"tick": tick, "concurrent": concurrent})
        still = any(queues[s] or in_flight[s] for s in SUBSTRATES)
        if not still:
            break
        tick += 1

    peaks = {s: max(row["concurrent"][s] for row in series) for s in SUBSTRATES}
    return {
        "dry_run": True,
        "unit_count": len(assignments),
        "duration_ticks": duration_ticks,
        "serial_lock": serial_lock,
        "time_series": series,
        "peaks": peaks,
        "finished": finished,
    }


def can_start(substrate: str, in_flight_count: int, serial_lock: bool) -> bool:
    """Gate used by the real dispatcher loop (asserted by the mutation probe)."""
    if substrate != SERIAL_SUBSTRATE:
        return in_flight_count < PER_SUBSTRATE_CAP
    if serial_lock:
        return in_flight_count == 0
    return in_flight_count < PER_SUBSTRATE_CAP
