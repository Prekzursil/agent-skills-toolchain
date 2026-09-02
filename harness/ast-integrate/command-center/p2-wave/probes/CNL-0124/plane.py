"""Single control-plane primitives for CNL-0124.

Workflow node kinds are taken from catalog IMP-0129..IMP-0135 questions
(FanOut/Barrier/Pipeline already at agentspec/spec.py:77-108; Subworkflow,
Loop, HumanCheckpoint, DynamicFanOut, WorkUnit.routing, Param). Spec.py is
absent on this worktree; the primitive set is the catalog-cited frozen
surface, not an invented second engine.

Join functions BallotReduce / BlindEnvelope / Watch are required extensions
of that same plane. They are not orchestration runtimes.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

HOME_PLANE = "prompt-native"
HOME_SCHEDULERS = frozenset(
    {
        "agentspec",
        "prompt-native",
        "prompt_native",
        "native",
        "home",
        "home-plane",
        "this-plane",
        "estate",
        "harness",
        "claude-harness",
        "ast-integrate",
        "cursor-agent",
        "none",
        "null",
        "",
    }
)

# Node kinds the catalog already names on the frozen workflow spec.
NODE_KINDS = frozenset(
    {
        "WorkUnit",
        "Pipeline",
        "FanOut",
        "Barrier",
        "Subworkflow",
        "Loop",
        "HumanCheckpoint",
        "DynamicFanOut",
    }
)

# Surfaces that are not nodes but live on the same plane.
SURFACES = frozenset(
    {
        "Param",
        "routing",
        "completion-predicate",
        "workflow-receipts",
        "budget-rollup",
    }
)

ALLOWED_PRIMITIVES = NODE_KINDS | SURFACES

# Same-plane extensions a council compile may name. Not schedulers.
EXTENSION_KINDS = frozenset({"BallotReduce", "BlindEnvelope", "Watch"})

# Orchestration runtimes that raise the plane count above one.
FOREIGN_RUNTIME: dict[str, str] = {
    "langgraph": "langgraph",
    "langchain": "langgraph",
    "crewai": "crewai",
    "autogen": "autogen",
    "ag2": "autogen",
    "temporal": "temporal",
    "airflow": "airflow",
    "prefect": "prefect",
    "dagster": "dagster",
    "council-runtime": "council-runtime",
    "council.engine": "council-runtime",
    "own-scheduler": "council-runtime",
}

# Features that would need their own scheduler if not compiled onto agentspec.
SCHEDULER_FEATURES = (
    {
        "id": "own-round-dispatcher",
        "fields": ("dispatch_loop", "round_runner", "own_scheduler", "turn_engine"),
        "plane": "council-runtime",
        "why": (
            "CNL-0047 names turn-taking as one shared primitive; a council-owned "
            "round dispatcher is a second orchestration runtime."
        ),
    },
    {
        "id": "standing-event-loop",
        "fields": ("watch_loop", "resident_event_loop", "own_wake_clock"),
        "plane": "council-runtime",
        "why": (
            "A standing council that runs its own wake clock is a duplicate "
            "control plane. Watch is a workflow-plane node, not a council engine."
        ),
    },
    {
        "id": "nested-private-runtime",
        "fields": ("child_runtime", "nested_engine"),
        "plane": "council-runtime",
        "why": (
            "Child councils compile to Subworkflow on the parent graph. A private "
            "child runtime is a second scheduler."
        ),
    },
)

HARNESS_CANDIDATES = (
    "/root/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "/home/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    str(REPO / "_USER-PROMPTS.md"),
    str(REPO / "command-center" / "_USER-PROMPTS.md"),
    str(REPO / "harness-restore-20260806" / "_USER-PROMPTS.md"),
)

SCHEMA_CANDIDATES = (
    "/root/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    str(REPO / "11-COUNCIL-SPECIFICATION.schema.json"),
    str(REPO / "command-center" / "schema" / "councilspec.v2.schema.json"),
    str(REPO / "tools" / "agentspec" / "agentspec" / "spec.py"),
)


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_units_by_id() -> dict[str, dict[str, Any]]:
    data = load_catalog()
    out: dict[str, dict[str, Any]] = {}
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and isinstance(u.get("id"), str):
            out[u["id"]] = u
    return out


def catalog_line(needle: str) -> dict[str, Any]:
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": i,
                "snippet": line.strip()[:240],
            }
    raise KeyError(needle)


def hunt_paths(candidates: tuple[str, ...]) -> dict[str, Any]:
    hits = [p for p in candidates if Path(p).is_file()]
    return {"tried": list(candidates), "hits": hits, "available": bool(hits)}


def extract_primitives_from_catalog() -> dict[str, Any]:
    """Signal 2: parse IMP-0129..0135 questions; do not trust FROZEN alone."""
    units = catalog_units_by_id()
    found: set[str] = set()
    notes: list[dict[str, str]] = []

    def grab(uid: str, names: tuple[str, ...]) -> None:
        u = units.get(uid)
        if not u:
            notes.append({"id": uid, "status": "missing"})
            return
        blob = " ".join(
            [
                str(u.get("title") or ""),
                str(u.get("question_or_target") or ""),
            ]
        )
        for name in names:
            if name in blob:
                found.add(name)
                notes.append({"id": uid, "found": name})
            else:
                notes.append({"id": uid, "missing": name})

    grab("IMP-0129", ("Subworkflow", "FanOut", "Barrier", "Pipeline"))
    grab("IMP-0130", ("Loop",))
    grab("IMP-0131", ("HumanCheckpoint",))
    grab("IMP-0132", ("DynamicFanOut", "FanOut"))
    grab("IMP-0133", ("Param",))
    grab("IMP-0135", ("WorkUnit", "routing"))
    return {
        "extracted_nodes_and_surfaces": sorted(found),
        "frozen_nodes": sorted(NODE_KINDS),
        "frozen_surfaces": sorted(SURFACES),
        "notes": notes,
    }


def primitives_agree() -> dict[str, Any]:
    ext = extract_primitives_from_catalog()
    extracted = set(ext["extracted_nodes_and_surfaces"])
    expect = NODE_KINDS | {"Param", "routing"}
    missing = sorted(expect - extracted)
    extra = sorted(extracted - expect)
    return {
        **ext,
        "missing_from_catalog_parse": missing,
        "extra_from_catalog_parse": extra,
        "ok": not missing,
    }


_TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")


def blob_tokens(obj: Any) -> set[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    return set(_TOKEN_RE.findall(text)) | {text}


def foreign_planes_in(obj: Any) -> list[str]:
    text = json.dumps(obj, sort_keys=True).lower()
    planes: set[str] = set()
    for needle, plane in FOREIGN_RUNTIME.items():
        if needle in text:
            planes.add(plane)
    return sorted(planes)
