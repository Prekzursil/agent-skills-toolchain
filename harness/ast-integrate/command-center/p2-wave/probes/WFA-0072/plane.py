#!/usr/bin/env python3
"""Chosen control-plane identifier set and translation-adapter map.

Identifier set is derived from live A1/A2 dossiers on this worktree plus the
catalog's prompt-native / Claude Code harness language. Adjacent orchestration
runtimes are the seven WFA-0027 teardown targets, plus GitHub Actions and
metaswarm (schedulers / duplicate planes named by sibling adapter units).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# WFA-0027 teardown targets: transferable mechanism, refuse the runtime.
TORN_DOWN = (
    "langgraph",
    "crewai",
    "autogen",
    "temporal",
    "airflow",
    "prefect",
    "dagster",
)

# Additional schedulers / planes that are not the chosen harness.
OTHER_FOREIGN = (
    "github-actions",
    "gha",
    "metaswarm",
    "n8n",
    "prefect-cloud",
)

ADOPT_CLASSES = frozenset({"ADOPT-AS-IS", "ADOPT-WITH-WRAPPER"})

ADAPTER_BY_RUNTIME = {
    "langgraph": {
        "adapter_id": "WFA-0049",
        "adapter_path": "command-center/wfa/WFA-0049-adapter-langgraph.json",
        "name": "LangGraph state-graph semantics to IR",
    },
    "crewai": {
        "adapter_id": "WFA-0050",
        "adapter_path": "command-center/wfa/WFA-0050-adapter-crew-autogen.json",
        "name": "CrewAI / AutoGen role-crew to IR",
    },
    "autogen": {
        "adapter_id": "WFA-0050",
        "adapter_path": "command-center/wfa/WFA-0050-adapter-crew-autogen.json",
        "name": "CrewAI / AutoGen role-crew to IR",
    },
    "temporal": {
        "adapter_id": "WFA-0051",
        "adapter_path": "command-center/wfa/WFA-0051-adapter-dag-schedulers.json",
        "name": "durable DAG schedulers to IR",
    },
    "airflow": {
        "adapter_id": "WFA-0051",
        "adapter_path": "command-center/wfa/WFA-0051-adapter-dag-schedulers.json",
        "name": "durable DAG schedulers to IR",
    },
    "prefect": {
        "adapter_id": "WFA-0051",
        "adapter_path": "command-center/wfa/WFA-0051-adapter-dag-schedulers.json",
        "name": "durable DAG schedulers to IR",
    },
    "dagster": {
        "adapter_id": "WFA-0051",
        "adapter_path": "command-center/wfa/WFA-0051-adapter-dag-schedulers.json",
        "name": "durable DAG schedulers to IR",
    },
    "github-actions": {
        "adapter_id": "WFA-0052",
        "adapter_path": "command-center/wfa/WFA-0052-adapter-github-actions.json",
        "name": "GitHub Actions workflow YAML to IR",
    },
    "gha": {
        "adapter_id": "WFA-0052",
        "adapter_path": "command-center/wfa/WFA-0052-adapter-github-actions.json",
        "name": "GitHub Actions workflow YAML to IR",
    },
    "metaswarm": {
        "adapter_id": "WFA-0046",
        "adapter_path": "command-center/wfa/WFA-0046-adapter-metaswarm-pipeline.json",
        "name": "metaswarm 9-phase pipeline to IR",
    },
}

ADAPTER_BY_FAMILY = {
    "A-saved-workflow": {
        "adapter_id": "WFA-0045",
        "adapter_path": "command-center/wfa/WFA-0045-adapter-saved-workflow.json",
        "name": "Claude Code saved Workflow to IR",
    },
    "B-repo-workflow": {
        "adapter_id": "WFA-0052",
        "adapter_path": "command-center/wfa/WFA-0052-adapter-github-actions.json",
        "name": "GitHub Actions workflow YAML to IR",
    },
    "G-skill": {
        "adapter_id": "WFA-0047",
        "adapter_path": "command-center/wfa/WFA-0047-adapter-skill-markdown.json",
        "name": "SKILL.md procedural prose to IR",
    },
    "I-command": {
        "adapter_id": "WFA-0048",
        "adapter_path": "command-center/wfa/WFA-0048-adapter-slash-command.json",
        "name": "slash-command markdown to IR",
    },
    "F-plugin": {
        "adapter_id": "WFA-0046",
        "adapter_path": "command-center/wfa/WFA-0046-adapter-metaswarm-pipeline.json",
        "name": "plugin pipeline to IR (metaswarm-class)",
    },
}

IR_FALLBACK = {
    "adapter_id": "WFA-0044",
    "adapter_path": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
    "name": "vendor-neutral workflow IR (generic translation target)",
}

# Libraries that must NOT trip the second-control-plane guard.
LEGITIMATE_LIBS = frozenset(
    {
        "jsonschema",
        "pytest",
        "hashlib",
        "pathlib",
        "json",
        "re",
        "yaml",
        "tomllib",
    }
)

TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.I)


def norm_token(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s


def tokens(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(str(text or ""))}


def _load_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def live_architecture_ids() -> list[dict]:
    rows = []
    for rel in (
        "command-center/phase3/A1/DESIGN.json",
        "command-center/phase3/A2/DESIGN.json",
    ):
        path = REPO / rel
        doc = _load_json(path)
        if not doc:
            continue
        rows.append(
            {
                "path": rel,
                "present": True,
                "architecture_id": doc.get("architecture_id"),
                "architecture_class": doc.get("architecture_class"),
            }
        )
    return rows


def chosen_identifier_set() -> dict:
    """Return the identifier set for the chosen control plane on this estate."""
    live = live_architecture_ids()
    ids = {
        "a1",
        "a2",
        "config-first-minimal",
        "config-first",
        "generated-ssot",
        "claude-code",
        "claude",
        "harness",
        "ast-integrate",
        "command-center",
        "prompt-native",
        "control-plane",
        "control-plane-a1",
        "control-plane-a2",
    }
    sources = [
        {
            "kind": "catalog-language",
            "note": "prompt-native Claude Code harness; mechanisms extracted, runtimes refused",
        }
    ]
    for row in live:
        aid = norm_token(str(row.get("architecture_id") or ""))
        aclass = norm_token(str(row.get("architecture_class") or ""))
        if aid:
            ids.add(aid)
        if aclass:
            ids.add(aclass)
        sources.append({"kind": "live-dossier", **row})
    arch_md = locate_architecture_md()
    if arch_md.get("present"):
        sources.append(arch_md)
        blob = str(arch_md.get("chosen_excerpt") or "")
        for tok in (
            "A1",
            "A2",
            "config-first",
            "generated SSOT",
            "claude-code",
            "prompt-native",
        ):
            if tok.lower() in blob.lower():
                ids.add(norm_token(tok))
    return {
        "identifiers": sorted(ids),
        "sources": sources,
        "architecture_md": arch_md,
        "live_dossiers": live,
        "chosen_on_this_estate": (
            "A1 config-first-minimal + A2 generated SSOT under "
            "command-center/control-plane/; saved-workflow dialect is claude-code. "
            "13-ARCHITECTURE-CANDIDATES.md is absent on this Linux worktree; "
            "identifiers are taken from live phase-3 dossiers, not from recovered "
            "tournament prose."
        ),
    }


def locate_architecture_md() -> dict:
    candidates = [
        Path(
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "13-ARCHITECTURE-CANDIDATES.md"
        ),
        Path(
            "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
            "13-ARCHITECTURE-CANDIDATES.md"
        ),
        Path("/root/.claude/harness-restore-20260806/13-ARCHITECTURE-CANDIDATES.md"),
        REPO / "13-ARCHITECTURE-CANDIDATES.md",
        REPO / "command-center/13-ARCHITECTURE-CANDIDATES.md",
        HERE / "fixtures/13-ARCHITECTURE-CANDIDATES.md",
    ]
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            text = path.read_text(encoding="utf-8", errors="replace")
            return {
                "present": True,
                "path": str(path),
                "bytes": path.stat().st_size,
                "chosen_excerpt": text[:400],
            }
    return {
        "present": False,
        "path": None,
        "sought": [str(p) for p in candidates],
        "bytes": 0,
    }


def runtime_is_chosen(runtime: str, identifiers: set[str] | None = None) -> bool:
    ident = identifiers if identifiers is not None else set(chosen_identifier_set()["identifiers"])
    n = norm_token(runtime)
    if not n:
        return False
    parts = set(n.split("-")) | {n}
    if n in ident:
        return True
    # "claude-code-workflow" contains chosen identifier claude-code
    for iid in ident:
        if iid and (n == iid or n.startswith(iid + "-") or iid in parts):
            # Avoid 'a1' matching unrelated tokens inside longer hashes; require
            # exact token membership for short ids.
            if len(iid) <= 2:
                return iid in parts or n == iid
            if n == iid or n.startswith(iid + "-") or f"-{iid}-" in f"-{n}-":
                return True
    return False


def named_foreign_runtime(runtime: str) -> str | None:
    n = norm_token(runtime)
    if not n:
        return None
    for name in TORN_DOWN + OTHER_FOREIGN:
        nn = norm_token(name)
        if n == nn or n.startswith(nn + "-") or f"-{nn}-" in f"-{n}-":
            return name
    return None


def adapter_for(candidate: dict, foreign_name: str | None) -> dict:
    if foreign_name and foreign_name in ADAPTER_BY_RUNTIME:
        row = dict(ADAPTER_BY_RUNTIME[foreign_name])
        row["matched_on"] = f"runtime:{foreign_name}"
        return row
    fam = str(candidate.get("family") or "")
    if fam in ADAPTER_BY_FAMILY:
        row = dict(ADAPTER_BY_FAMILY[fam])
        row["matched_on"] = f"family:{fam}"
        return row
    row = dict(IR_FALLBACK)
    row["matched_on"] = "ir-fallback"
    return row
