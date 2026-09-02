#!/usr/bin/env python3
"""Shared control-plane census for WFA-0141.

One counter. Two trigger points (acquisition, fusion). Count distinct
orchestration planes a workflow introduces. Home plane is prompt-native.
A second orchestrator (LangGraph, CrewAI, AutoGen, Temporal, Airflow,
Prefect, Dagster, ...) raises the count above one and the gate fires.

The candidate `runtime` field is one signal. Imports / own-runner flags /
fused definitions are another. The two readings are kept separate; the
gate uses their union so a lying runtime string cannot hide a runner.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HOME_PLANE = "prompt-native"

HOME_ALIASES = frozenset(
    {
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
        "mechanism-only",
        "pure-mechanism",
        "none",
        "null",
        "",
    }
)

LANGUAGE_NOT_PLANE = frozenset(
    {
        "python",
        "python3",
        "py",
        "node",
        "nodejs",
        "javascript",
        "js",
        "typescript",
        "ts",
        "bash",
        "sh",
        "shell",
        "zsh",
        "powershell",
        "pwsh",
        "go",
        "golang",
        "rust",
        "ruby",
        "java",
        "lua",
        "r",
        "php",
    }
)

FOREIGN_RUNTIME: dict[str, str] = {
    "langgraph": "langgraph",
    "langchain": "langgraph",
    "langchain_core": "langgraph",
    "langchain-core": "langgraph",
    "langsmith": "langgraph",
    "crewai": "crewai",
    "crew-ai": "crewai",
    "crew_ai": "crewai",
    "autogen": "autogen",
    "pyautogen": "autogen",
    "ag2": "autogen",
    "autogen-agentchat": "autogen",
    "temporal": "temporal",
    "temporalio": "temporal",
    "airflow": "airflow",
    "apache-airflow": "airflow",
    "apache_airflow": "airflow",
    "prefect": "prefect",
    "dagster": "dagster",
    "n8n": "n8n",
    "haystack-agent": "haystack",
    "semantic-kernel": "semantic-kernel",
    "semantickernel": "semantic-kernel",
    "openai-agents": "openai-agents",
    "openai_agents": "openai-agents",
    "swarm": "openai-agents",
    "llamaindex-workflow": "llamaindex",
    "llama-index-workflows": "llamaindex",
}

FOREIGN_IMPORT_MARKERS: dict[str, str] = {
    "langgraph": "langgraph",
    "langchain": "langgraph",
    "langchain_core": "langgraph",
    "crewai": "crewai",
    "autogen": "autogen",
    "pyautogen": "autogen",
    "temporalio": "temporal",
    "airflow": "airflow",
    "prefect": "prefect",
    "dagster": "dagster",
}

MECHANISM_FOR_PLANE: dict[str, str] = {
    "langgraph": (
        "Transfer the typed state graph, checkpointer and interrupt-before "
        "human as IR nodes/edges/checkpoints. Do not import LangGraph."
    ),
    "crewai": (
        "Transfer crew/task/process as IR roles and turn policy. "
        "Do not import CrewAI."
    ),
    "autogen": (
        "Transfer conversable-agent group chat as IR roles and termination. "
        "Do not import AutoGen."
    ),
    "temporal": (
        "Transfer workflow/activity/retry as IR stages plus retry algebra. "
        "Do not import the Temporal SDK."
    ),
    "airflow": (
        "Transfer DAG/operator/sensor as IR stages and gates. "
        "Do not import Airflow."
    ),
    "prefect": "Transfer flow/task as IR stages. Do not import Prefect.",
    "dagster": (
        "Transfer job/op/asset as IR stages plus lineage. Do not import Dagster."
    ),
    "n8n": "Transfer node graph as IR stages. Do not import n8n.",
    "semantic-kernel": (
        "Transfer planner/plugin dispatch as IR tool calls. "
        "Do not import Semantic Kernel."
    ),
    "openai-agents": (
        "Transfer handoff/guardrail as IR gates. Do not import the Agents SDK."
    ),
    "llamaindex": (
        "Transfer workflow events as IR stages. Do not import LlamaIndex workflows."
    ),
    "haystack": (
        "Transfer pipeline nodes as IR stages. Do not import Haystack agents."
    ),
}

REGISTRY_NAMES = ("08-WORKFLOW-CANDIDATE-REGISTRY.json",)
MERGE_NAMES = ("10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",)
PROMPT_NAMES = ("_USER-PROMPTS.md",)

SEARCH_BASES = (
    HERE / "fixtures" / "live",
    Path.home() / ".claude/harness-restore-20260806",
    Path("/home/Prekzursil/.claude/harness-restore-20260806"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    REPO,
    REPO / "command-center",
    REPO / "command-center/p2-wave",
    REPO / "harness-restore-20260806",
    HERE / "fixtures" / "live",
)


def _norm_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    text = str(value).strip().lower()
    text = text.replace("\\", "/")
    text = re.sub(r"[\s]+", "-", text)
    text = text.replace("_", "-")
    return text.strip("-")


def canonicalize_plane(token: Any) -> str | None:
    raw = _norm_token(token)
    if raw in HOME_ALIASES:
        return HOME_PLANE
    if raw in LANGUAGE_NOT_PLANE:
        return None
    collapsed = raw.replace("-", "")
    for key, plane in FOREIGN_RUNTIME.items():
        key_n = _norm_token(key)
        if key_n == raw or key.replace("_", "").replace("-", "") == collapsed:
            return plane
    if raw.startswith("unknown:") or raw.startswith("unclassified:"):
        return raw
    if raw:
        return f"unclassified:{raw}"
    return None


def _field_values(obj: Any, keys: Iterable[str]) -> list[Any]:
    if not isinstance(obj, dict):
        return []
    return [obj[key] for key in keys if key in obj]


def _walk_runtime_tokens(value: Any, into: list[str]) -> None:
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        for part in re.split(r"[|,;/]+", value):
            token = part.strip()
            if token:
                into.append(token)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _walk_runtime_tokens(item, into)
        return
    if isinstance(value, dict):
        for key in (
            "runtime",
            "runtimes",
            "name",
            "id",
            "engine",
            "orchestrator",
            "control_plane",
            "controlPlane",
            "kind",
            "type",
        ):
            if key in value:
                _walk_runtime_tokens(value[key], into)


def runtime_tokens_from_candidate(candidate: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for value in _field_values(
        candidate,
        (
            "runtime",
            "runtimes",
            "control_plane",
            "control_planes",
            "orchestrator",
            "engine",
        ),
    ):
        _walk_runtime_tokens(value, tokens)
    return tokens


def import_tokens(candidate: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for value in _field_values(
        candidate, ("imports", "requires", "dependencies", "packages", "pip")
    ):
        _walk_runtime_tokens(value, tokens)
    return tokens


def foreign_planes_from_imports(tokens: Iterable[str]) -> set[str]:
    planes: set[str] = set()
    for token in tokens:
        raw = _norm_token(token).replace("-", "_")
        head = raw.split(".")[0]
        if head in FOREIGN_IMPORT_MARKERS:
            planes.add(FOREIGN_IMPORT_MARKERS[head])
        elif raw in FOREIGN_IMPORT_MARKERS:
            planes.add(FOREIGN_IMPORT_MARKERS[raw])
        else:
            plane = canonicalize_plane(token)
            if (
                plane
                and plane != HOME_PLANE
                and not str(plane).startswith("unclassified:")
            ):
                planes.add(plane)
    return planes


def extracted_mechanism(
    planes: Iterable[str], candidate: dict[str, Any] | None = None
) -> str:
    if candidate:
        explicit = candidate.get("extracted_mechanism") or candidate.get("mechanism")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        mechs = candidate.get("mechanisms")
        if isinstance(mechs, list) and mechs:
            joined = ", ".join(str(m) for m in mechs)
            foreign = [p for p in planes if p != HOME_PLANE]
            if foreign:
                return (
                    f"Keep [{joined}] as IR on {HOME_PLANE}; refuse runner(s) "
                    + ", ".join(sorted(foreign))
                    + "."
                )
            return f"Keep [{joined}] on {HOME_PLANE}."
    bits = []
    for plane in sorted(set(planes)):
        if plane == HOME_PLANE:
            continue
        bits.append(
            MECHANISM_FOR_PLANE.get(
                plane, f"Extract the mechanism; refuse runtime {plane}."
            )
        )
    if bits:
        return " ".join(bits)
    return f"No second plane; run on {HOME_PLANE}."


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "yes",
            "1",
            "own-runner",
            "own_runner",
        }
    return False


def planes_from_runtime_field(candidate: dict[str, Any]) -> set[str]:
    planes: set[str] = set()
    for token in runtime_tokens_from_candidate(candidate):
        plane = canonicalize_plane(token)
        if plane:
            planes.add(plane)
    if not planes:
        planes.add(HOME_PLANE)
    return planes


def planes_from_guard(candidate: dict[str, Any]) -> set[str]:
    planes: set[str] = set()
    if (
        _boolish(candidate.get("carries_own_runner"))
        or _boolish(candidate.get("has_own_runner"))
        or _boolish(candidate.get("own_runner"))
    ):
        runtime_planes = planes_from_runtime_field(candidate)
        foreign = {p for p in runtime_planes if p != HOME_PLANE}
        if foreign:
            planes |= foreign
        else:
            planes.add("unclassified:own-runner")
    for value in _field_values(candidate, ("runner", "scheduler", "executor")):
        tokens: list[str] = []
        _walk_runtime_tokens(value, tokens)
        if isinstance(value, dict) and value and not tokens:
            planes.add("unclassified:own-runner")
        for token in tokens:
            plane = canonicalize_plane(token)
            if plane and plane != HOME_PLANE:
                planes.add(plane)
            elif plane is None and token:
                planes.add("unclassified:own-runner")
    planes |= foreign_planes_from_imports(import_tokens(candidate))
    return planes


def count_planes(
    candidate: dict[str, Any],
    *,
    trigger: str,
    extra_docs: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """THE shared counter. Used at acquisition and at fusion."""
    docs = [candidate]
    if extra_docs:
        docs.extend(list(extra_docs))
    runtime_reading: set[str] = set()
    guard_reading: set[str] = set()
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        runtime_reading |= planes_from_runtime_field(doc)
        guard_reading |= planes_from_guard(doc)
    union = set(runtime_reading) | set(guard_reading)
    if not union:
        union.add(HOME_PLANE)
    ordered = sorted(union)
    count = len(ordered)
    known_foreign = [
        p
        for p in ordered
        if p in MECHANISM_FOR_PLANE or p in set(FOREIGN_RUNTIME.values())
    ]
    over = count > 1 or bool(known_foreign)
    subject_id = str(
        candidate.get("id")
        or candidate.get("name")
        or candidate.get("slug")
        or "unnamed"
    )
    return {
        "trigger": trigger,
        "subject_id": subject_id,
        "runtime_field_planes": sorted(runtime_reading),
        "guard_planes": sorted(guard_reading),
        "planes": ordered,
        "count": count,
        "over_one": over,
        "gate": "FIRE" if over else "PASS",
        "extracted_mechanism": extracted_mechanism(ordered, candidate),
        "counter": "count_planes",
    }


def acquire(candidate: dict[str, Any]) -> dict[str, Any]:
    return count_planes(candidate, trigger="acquisition")


def fuse(
    fusion: dict[str, Any],
    catalog: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalog = catalog or {}
    source_docs: list[dict[str, Any]] = []
    source_ids = fusion.get("sources") or fusion.get("source_ids") or []
    if isinstance(source_ids, str):
        source_ids = [source_ids]
    unresolved: list[str] = []
    for sid in source_ids:
        key = str(sid)
        if key in catalog:
            source_docs.append(catalog[key])
        elif isinstance(sid, dict):
            source_docs.append(sid)
        else:
            unresolved.append(key)
            source_docs.append({"id": key, "runtime": HOME_PLANE})
    definition = fusion.get("definition")
    extra: list[dict[str, Any]] = list(source_docs)
    if isinstance(definition, dict):
        extra.append(definition)
    elif definition is not None:
        extra.append({"runtime": definition})
    reading = count_planes(fusion, trigger="fusion", extra_docs=extra)
    source_runtime: set[str] = set()
    source_guard: set[str] = set()
    for doc in source_docs:
        source_runtime |= planes_from_runtime_field(doc)
        source_guard |= planes_from_guard(doc)
    fused_runtime: set[str] = set()
    fused_guard: set[str] = set()
    fused_doc = definition if isinstance(definition, dict) else {"runtime": definition}
    if definition is not None:
        fused_runtime |= planes_from_runtime_field(fused_doc)
        fused_guard |= planes_from_guard(fused_doc)
    reading["source_runtime_field_planes"] = sorted(source_runtime)
    reading["source_guard_planes"] = sorted(source_guard)
    reading["fused_definition_runtime_planes"] = sorted(fused_runtime)
    reading["fused_definition_guard_planes"] = sorted(fused_guard)
    reading["unresolved_sources"] = unresolved
    reading["source_ids"] = [
        str(s) if not isinstance(s, dict) else s.get("id") for s in source_ids
    ]
    return reading


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_planted_candidates() -> list[dict[str, Any]]:
    doc = load_json(HERE / "fixtures" / "candidates.json")
    rows = doc.get("candidates") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise RuntimeError("planted candidates missing")
    return [r for r in rows if isinstance(r, dict)]


def load_planted_fusions() -> list[dict[str, Any]]:
    doc = load_json(HERE / "fixtures" / "fusions.json")
    rows = doc.get("fusions") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise RuntimeError("planted fusions missing")
    return [r for r in rows if isinstance(r, dict)]


def candidate_catalog(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("id") or row.get("name") or "")
        if cid:
            out[cid] = row
    return out


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def hunt_named(names: tuple[str, ...]) -> dict[str, Any]:
    tried: list[str] = []
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for base in SEARCH_BASES:
        for name in names:
            if base.is_file():
                continue
            path = base / name
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            tried.append(key)
            if path.is_file():
                sha, size = digest_file(path)
                hits.append(
                    {
                        "path": key,
                        "exists": True,
                        "sha256": sha,
                        "bytes": size,
                    }
                )
    return {
        "names": list(names),
        "tried": tried,
        "hits": hits,
        "available": bool(hits),
    }


def extract_candidate_rows(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "records", "items", "workflows"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def extract_fusion_rows(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("merge_units", "fusions", "compositions", "merge_map"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            rows = []
            for k, v in val.items():
                if isinstance(v, dict):
                    row = dict(v)
                    row.setdefault("id", k)
                    rows.append(row)
            if rows:
                return rows
    return []


def census_acquisition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    readings = [acquire(row) for row in rows]
    raised = [r for r in readings if r["over_one"]]
    return {
        "n": len(readings),
        "n_over_one": len(raised),
        "n_pass": len(readings) - len(raised),
        "raised_ids": [r["subject_id"] for r in raised],
        "readings": readings,
    }


def census_fusion(
    fusions: list[dict[str, Any]], catalog: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    readings = [fuse(row, catalog) for row in fusions]
    raised = [r for r in readings if r["over_one"]]
    return {
        "n": len(readings),
        "n_over_one": len(raised),
        "n_pass": len(readings) - len(raised),
        "raised_ids": [r["subject_id"] for r in raised],
        "readings": readings,
    }


def live_bundle() -> dict[str, Any]:
    registry = hunt_named(REGISTRY_NAMES)
    merges = hunt_named(MERGE_NAMES)
    prompts = hunt_named(PROMPT_NAMES)
    live_candidates: list[dict[str, Any]] = []
    live_fusions: list[dict[str, Any]] = []
    registry_load: dict[str, Any] = {"loaded": False}
    merge_load: dict[str, Any] = {"loaded": False}
    if registry["hits"]:
        path = Path(registry["hits"][0]["path"])
        try:
            doc = load_json(path)
            live_candidates = extract_candidate_rows(doc)
            registry_load = {
                "loaded": True,
                "path": str(path),
                "n": len(live_candidates),
                "top_keys": sorted(doc.keys())
                if isinstance(doc, dict)
                else ["<list>"],
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            registry_load = {
                "loaded": False,
                "error": type(exc).__name__,
                "path": str(path),
            }
    if merges["hits"]:
        path = Path(merges["hits"][0]["path"])
        try:
            doc = load_json(path)
            live_fusions = extract_fusion_rows(doc)
            merge_load = {
                "loaded": True,
                "path": str(path),
                "n": len(live_fusions),
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            merge_load = {
                "loaded": False,
                "error": type(exc).__name__,
                "path": str(path),
            }
    catalog = candidate_catalog(live_candidates)
    acq = census_acquisition(live_candidates) if live_candidates else None
    fus = census_fusion(live_fusions, catalog) if live_fusions else None
    return {
        "registry_hunt": registry,
        "merge_hunt": merges,
        "prompts_hunt": prompts,
        "registry_load": registry_load,
        "merge_load": merge_load,
        "acquisition": acq,
        "fusion": fus,
        "live_available": bool(live_candidates),
    }


def planted_bundle() -> dict[str, Any]:
    candidates = load_planted_candidates()
    fusions = load_planted_fusions()
    catalog = candidate_catalog(candidates)
    return {
        "candidates": candidates,
        "fusions": fusions,
        "acquisition": census_acquisition(candidates),
        "fusion": census_fusion(fusions, catalog),
        "catalog_ids": sorted(catalog),
    }


def line_anchor(rel: str, needle: str) -> str:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines, 1) if needle in line]
    if not hits:
        return f"{rel}:MISSING"
    return f"{rel}:{hits[0]}"


# Stable call-site aliases used by probes/emitters.
planted_bundle = planted_bundle
candidate_catalog = candidate_catalog
acquire = acquire
fuse = fuse
live_bundle = live_bundle
HOME_PLANE = HOME_PLANE
line_anchor = line_anchor
digest_file = digest_file
