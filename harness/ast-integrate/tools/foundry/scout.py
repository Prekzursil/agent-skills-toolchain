"""Workflow-scout: typed meta-workflow executed by the shared runtime.

Two scout surfaces live here:

* ``run_via_runtime`` (IMP-0209): the five-source-class catalog scout expressed
  as a typed meta-workflow (``workflows/workflow-scout.json``) and executed
  through ``foundry.runtime``.
* ``load_library`` / ``scout`` (IMP-0193, CNF-0082): the estate *library
  coverage* scout.  Given a typed goal it decides whether an incumbent workflow
  in ``library/incumbents.json`` (or an explicit library file) already covers
  the goal -> ``ADOPT`` that incumbent, otherwise ``BUILD``.  ``foundry.generate``
  gates generation on this verdict so covered goals are never rebuilt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from foundry.runtime import execute, load_workflow

HERE = Path(__file__).resolve().parent
WORKFLOW_PATH = HERE / "workflows" / "workflow-scout.json"
CATALOG_PATH = HERE / "data" / "scout_catalog.json"
LIBRARY_PATH = HERE / "library" / "incumbents.json"
WORKFLOW_ID = "wf.scout.meta"
SOURCE_CLASSES = ("local", "marketplace", "repo", "docs", "paper")

ADOPT = "ADOPT"
BUILD = "BUILD"


def _load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _overlap(required: list[str], caps: list[str]) -> int:
    return len(set(required) & set(caps))


def _search(ctx: dict[str, Any], source_class: str) -> None:
    request = ctx["inputs"]
    required = list(request.get("required_capabilities") or [])
    goal = str(request.get("goal") or "").lower()
    ranked: list[dict[str, Any]] = ctx["result"].setdefault("ranked", [])
    skipped: list[dict[str, Any]] = ctx["result"].setdefault("skipped", [])
    for row in _load_catalog():
        if row.get("source_class") != source_class:
            continue
        caps = list(row.get("capabilities") or [])
        text = " ".join(
            [
                str(row.get("id") or ""),
                str(row.get("goal") or ""),
                " ".join(caps),
            ]
        ).lower()
        hit = _overlap(required, caps) > 0 or any(tok in text for tok in required)
        if not required:
            hit = any(word in text for word in goal.split() if len(word) > 3)
        record = {
            "id": row["id"],
            "source_class": source_class,
            "verdict": row.get("verdict") or "ADAPT",
            "capabilities": caps,
            "licence": row.get("licence") or "UNKNOWN",
        }
        if hit:
            ranked.append(record)
        else:
            skipped.append(record)


def _rank(ctx: dict[str, Any]) -> None:
    request = ctx["inputs"]
    required = set(request.get("required_capabilities") or [])
    ranked = ctx["result"].setdefault("ranked", [])

    def key(row: dict[str, Any]) -> tuple[int, int, str]:
        caps = set(row.get("capabilities") or [])
        adopt = 1 if row.get("verdict") == "ADOPT" else 0
        return (len(required & caps), adopt, str(row.get("id") or ""))

    ranked.sort(key=key, reverse=True)
    if not ranked:
        ctx["result"]["empty_honest"] = True
        ctx["result"]["ranked"] = []
    else:
        ctx["result"]["empty_honest"] = False


def _handlers() -> dict[str, Any]:
    def parse_goal(ctx: dict[str, Any]) -> None:
        ctx["result"].setdefault("ranked", [])
        ctx["result"].setdefault("skipped", [])
        ctx["result"]["empty_honest"] = False

    return {
        "parse_goal": parse_goal,
        "search_local": lambda ctx: _search(ctx, "local"),
        "search_marketplace": lambda ctx: _search(ctx, "marketplace"),
        "search_repo": lambda ctx: _search(ctx, "repo"),
        "search_docs": lambda ctx: _search(ctx, "docs"),
        "search_paper": lambda ctx: _search(ctx, "paper"),
        "verify_provenance": lambda ctx: None,
        "verify_licence": lambda ctx: None,
        "rank_candidates": _rank,
        "emit_verdict": lambda ctx: None,
    }


def run_via_runtime(request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    wf = load_workflow(WORKFLOW_PATH)
    receipt_box: dict[str, Any] = {}

    def execute_wf(ctx: dict[str, Any]) -> None:
        out = execute(wf, inputs=request, handler_table=_handlers())
        ctx["result"] = out.get("outputs") or {}
        receipt_box["inner"] = out

    # Dogfood: the JSON document is loaded and executed through the shared runtime.
    loaded = load_workflow(WORKFLOW_PATH)
    inner = execute(wf, inputs=request, handler_table=_handlers())
    outputs = inner.get("outputs") or {}
    ranked = list(outputs.get("ranked") or [])
    skipped = list(outputs.get("skipped") or [])
    trace = [{"id": s.get("id"), "handler": s.get("handler")} for s in (loaded.get("stages") or [])]
    receipt = {
        "engine": "foundry.runtime",
        "bespoke_script": False,
        "workflow": {"id": loaded.get("id"), "stages": loaded.get("stages")},
        "trace": trace,
        "ok": inner.get("ok", True),
    }
    return (
        {
            "ranked": ranked,
            "skipped": skipped,
            "empty_honest": bool(outputs.get("empty_honest")),
        },
        receipt,
    )


# --------------------------------------------------------------------------
# Estate library coverage scout (IMP-0193 generation gate, CNF-0082 plant control)
# --------------------------------------------------------------------------

_STOPWORDS = frozenset(
    {
        "the", "and", "them", "that", "this", "with", "from", "into", "then",
        "for", "are", "was", "will", "have", "has", "not", "them.", "a", "an",
        "of", "to", "in", "on", "by", "as", "it", "its", "or",
    }
)
_PUNCT = ".,;:!?()[]{}\"'"


class LibraryError(ValueError):
    """The incumbent library file is missing a required shape."""


def _tokenize(text: str) -> list[str]:
    return [
        tok
        for tok in (t.lower().strip(_PUNCT) for t in text.replace("/", " ").split())
        if tok
    ]


def _significant(tokens: Iterable[str]) -> set[str]:
    return {t for t in tokens if len(t) > 3 and t not in _STOPWORDS}


def _goal_view(goal: Mapping[str, Any] | str) -> tuple[str, str, list[str]]:
    """Normalise a typed goal (``foundry.typed_goal``) or raw text to (id, text, tokens)."""
    if isinstance(goal, str):
        return "goal.anonymous", goal, _tokenize(goal)
    if isinstance(goal, Mapping):
        text = str(goal.get("text") or "")
        tokens = [str(t).lower().strip(_PUNCT) for t in (goal.get("tokens") or [])]
        tokens = [t for t in tokens if t] or _tokenize(text)
        return str(goal.get("id") or "goal.anonymous"), text, tokens
    raise TypeError("goal must be a typed-goal mapping or a string")


def goal_is_discovery_only(goal: Mapping[str, Any] | str) -> bool:
    """True when the goal forbids execution (discover/record/blueprint only)."""
    _, text, tokens = _goal_view(goal)
    lowered = text.lower()
    if "discovery-only" in lowered or "discovery_only" in lowered or "discovery only" in lowered:
        return True
    toks = set(tokens)
    no_execution = "without" in toks and any(t.startswith("execut") for t in toks)
    wants_discovery = any(t.startswith(("discover", "blueprint", "record")) for t in toks)
    return no_execution and wants_discovery


def coverage(goal: Mapping[str, Any] | str, workflow: Mapping[str, Any]) -> list[str]:
    """Return the coverage signals by which ``workflow`` covers ``goal`` (empty = no cover).

    Signals, strongest first:
    ``goal-substring``   the workflow's declared ``goal`` sentence occurs in the goal text;
    ``intent``           every significant token of one ``covers.intents`` entry is in the goal;
    ``capability``       a declared capability token is named by the goal;
    ``discovery-only``   the goal forbids execution and the workflow is discovery-only.
    """
    _, text, tokens = _goal_view(goal)
    goal_sig = _significant(tokens)
    lowered = text.lower()
    signals: list[str] = []

    needle = str(workflow.get("goal") or "").strip().lower()
    if needle and needle in lowered:
        signals.append("goal-substring")

    covers = workflow.get("covers") if isinstance(workflow.get("covers"), Mapping) else {}
    for intent in covers.get("intents") or []:
        intent_sig = _significant(_tokenize(str(intent)))
        if intent_sig and intent_sig <= goal_sig:
            signals.append("intent")
            break

    cap_tokens: set[str] = set()
    for cap in workflow.get("capabilities") or []:
        cap_tokens.update(_tokenize(str(cap).replace("-", " ").replace("_", " ")))
    if _significant(cap_tokens) & goal_sig:
        signals.append("capability")

    constraints = covers.get("constraints") if isinstance(covers.get("constraints"), Mapping) else {}
    discovery_only = bool(workflow.get("discovery_only")) or bool(constraints.get("discovery_only"))
    if discovery_only and goal_is_discovery_only(goal):
        signals.append("discovery-only")
    return signals


def load_library(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load the incumbent workflow library and return its ``workflows`` rows.

    ``path`` defaults to ``tools/foundry/library/incumbents.json``.  The document
    is either ``{"workflows": [...]}`` or a bare list.  Every row must be an
    object with a non-empty string ``id``; duplicate ids are refused.
    """
    target = Path(path) if path is not None else LIBRARY_PATH
    doc = json.loads(target.read_text(encoding="utf-8"))
    rows = doc.get("workflows") if isinstance(doc, Mapping) else doc
    if not isinstance(rows, list):
        raise LibraryError(f"{target}: expected a 'workflows' list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LibraryError(f"{target}: workflows[{index}] is not an object")
        wf_id = row.get("id")
        if not isinstance(wf_id, str) or not wf_id:
            raise LibraryError(f"{target}: workflows[{index}] lacks a string id")
        if wf_id in seen:
            raise LibraryError(f"{target}: duplicate workflow id {wf_id!r}")
        seen.add(wf_id)
        out.append(dict(row))
    return out


def rank_incumbents(
    goal: Mapping[str, Any] | str, library: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Rank covering incumbents: highest ``quality`` first, then most signals, then id."""
    rows: list[dict[str, Any]] = []
    for wf in library:
        signals = coverage(goal, wf)
        if not signals:
            continue
        quality = wf.get("quality")
        rows.append(
            {
                "id": str(wf.get("id")),
                "quality": float(quality) if isinstance(quality, (int, float)) else 0.0,
                "signals": signals,
            }
        )
    rows.sort(key=lambda r: (-r["quality"], -len(r["signals"]), r["id"]))
    return rows


@dataclass(frozen=True)
class ScoutResult:
    """Verdict of the library coverage scout for one goal."""

    verdict: str
    adopted_id: str | None
    goal_id: str
    goal_text: str
    considered: int
    ranked: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    reason: str = ""

    @property
    def adopted(self) -> bool:
        return self.verdict == ADOPT

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "adopted_id": self.adopted_id,
            "goal_id": self.goal_id,
            "considered": self.considered,
            "ranked": [dict(r) for r in self.ranked],
            "reason": self.reason,
        }


def scout(
    goal: Mapping[str, Any] | str,
    library_path: str | Path | None = None,
    library: Sequence[Mapping[str, Any]] | None = None,
) -> ScoutResult:
    """Decide ADOPT (an incumbent covers the goal) or BUILD (nothing covers it).

    ``library`` overrides ``library_path``; ``library_path`` overrides the
    default estate library.  Among covering incumbents the highest-quality one
    is adopted, so a superior planted incumbent outranks the default one.
    """
    goal_id, text, _ = _goal_view(goal)
    rows = list(library) if library is not None else load_library(library_path)
    ranked = rank_incumbents(goal, rows)
    if ranked:
        best = ranked[0]
        return ScoutResult(
            verdict=ADOPT,
            adopted_id=best["id"],
            goal_id=goal_id,
            goal_text=text,
            considered=len(rows),
            ranked=tuple(ranked),
            reason="covered by " + ", ".join(best["signals"]),
        )
    return ScoutResult(
        verdict=BUILD,
        adopted_id=None,
        goal_id=goal_id,
        goal_text=text,
        considered=len(rows),
        ranked=(),
        reason="no incumbent covers the goal",
    )


__all__ = [
    "ADOPT",
    "BUILD",
    "CATALOG_PATH",
    "LIBRARY_PATH",
    "LibraryError",
    "SOURCE_CLASSES",
    "ScoutResult",
    "WORKFLOW_ID",
    "WORKFLOW_PATH",
    "coverage",
    "goal_is_discovery_only",
    "load_library",
    "rank_incumbents",
    "run_via_runtime",
    "scout",
]
