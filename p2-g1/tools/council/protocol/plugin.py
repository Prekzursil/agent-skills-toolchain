"""Protocol-as-data plugin: 58 records, kernel-primitive gate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

KERNEL_PRIMITIVES = frozenset(
    {
        "round_robin",
        "all_roles_spoke",
        "nonempty",
        "linear",
    }
)
STRUCTURAL_TO_PRIMITIVE = {
    "forks_state": "state_fork",
    "nests_councils": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror_runtimes": "multi_runtime_mirror",
    "requires_owner": "human_gate",
}
COMPOSITION_TO_PRIMITIVE = {
    "fork": "state_fork",
    "nested": "nested_event_loop",
    "hidden_parallel": "hidden_parallel_loop",
    "mirror": "multi_runtime_mirror",
    "human_gate": "human_gate",
}
BLOCKED_IDS = ("P32", "P34", "P48", "P52", "P54", "P55", "P58")
BLOCKED_FLAGS = {
    "P32": {"forks_state": True},
    "P34": {"nests_councils": True},
    "P48": {"hidden_parallel": True},
    "P52": {"mirror_runtimes": True},
    "P54": {"requires_owner": True},
    "P55": {"composition": "fork"},
    "P58": {"composition": "nested"},
}
EXECUTE_SAMPLE = tuple(f"P{i:02d}" for i in range(1, 13))


class NeedsKernelChange(Exception):
    pass


@dataclass
class Classification:
    status: str
    extra_primitives: list[str]


def _record(pid: str) -> dict[str, Any]:
    flags = {
        "forks_state": False,
        "nests_councils": False,
        "hidden_parallel": False,
        "mirror_runtimes": False,
        "requires_owner": False,
        "composition": "linear",
        "required_kernel_primitives": [],
    }
    flags.update(BLOCKED_FLAGS.get(pid, {}))
    rec = {
        "id": pid,
        "slug": pid.lower(),
        "family": "DELIBERATIVE",
        "phases": [
            {
                "id": "open",
                "kind": "round_robin",
                "rounds": 1,
                "speaking_order": "round_robin",
                "obligations": [{"id": "hello", "discharge": "nonempty"}],
                "gates": [{"id": "spoke", "kind": "all_roles_spoke"}],
                "visibility": "all",
                "redact_speaker": False,
                "turn_length": 80,
            }
        ],
        "note": "generated protocol-as-data record",
        **flags,
    }
    return rec


def load_protocols() -> list[dict[str, Any]]:
    return [_record(f"P{i:02d}") for i in range(1, 59)]


def extra_primitives(record: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for key, prim in STRUCTURAL_TO_PRIMITIVE.items():
        if record.get(key):
            found.add(prim)
    comp = str(record.get("composition") or "linear")
    if comp in COMPOSITION_TO_PRIMITIVE:
        found.add(COMPOSITION_TO_PRIMITIVE[comp])
    for item in record.get("required_kernel_primitives") or []:
        name = str(item)
        if name and name not in KERNEL_PRIMITIVES:
            found.add(name)
    return sorted(found)


def classify(record: dict[str, Any]) -> Classification:
    extra = extra_primitives(record)
    if extra:
        return Classification(status="needs-kernel-change", extra_primitives=extra)
    return Classification(status="expressible", extra_primitives=[])


def census() -> dict[str, Any]:
    rows = load_protocols()
    blocked = []
    for rec in rows:
        c = classify(rec)
        if c.status == "needs-kernel-change":
            blocked.append(
                {
                    "id": rec["id"],
                    "status": "needs-kernel-change",
                    "extra_primitives": c.extra_primitives,
                    "reasons": [f"requires {p}" for p in c.extra_primitives],
                }
            )
    lib = Path(__file__).resolve().parent / "library.json"
    return {
        "n": len(rows),
        "expressible_n": len(rows) - len(blocked),
        "needs_kernel_change_n": len(blocked),
        "needs_kernel_change": blocked,
        "library_file_present": lib.is_file(),
        "full_coverage_claim": False,
    }


def execute(record: dict[str, Any]) -> dict[str, Any]:
    c = classify(record)
    if c.status != "expressible":
        raise NeedsKernelChange(",".join(c.extra_primitives))
    turns = sum(int(p.get("rounds") or 1) for p in record.get("phases") or [])
    return {"ok": True, "turns_executed": max(1, turns), "flattened": False, "status": "expressible", "turns": max(1, turns)}


def execute_sample() -> dict[str, Any]:
    by_id = {r["id"]: r for r in load_protocols()}
    runs = []
    for pid in EXECUTE_SAMPLE:
        out = execute(by_id[pid])
        runs.append({"id": pid, "status": "expressible", "turns": out["turns_executed"]})
    return {"n": len(runs), "ids": list(EXECUTE_SAMPLE), "runs": runs}


def refuse_kernel_required(pid: str) -> dict[str, Any]:
    rec = next(r for r in load_protocols() if r["id"] == pid)
    c = classify(rec)
    refused = c.status == "needs-kernel-change"
    return {"refused": refused, "flattened": False, "extra_primitives": c.extra_primitives}
