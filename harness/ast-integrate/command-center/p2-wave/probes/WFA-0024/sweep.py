"""WFA-0024 GitHub code-search sweep primitives.

Search-result text and fetched files are untrusted DATA. This module never
executes, evals, or subprocesses payload bytes. Keyword hits are not IR
evidence. A fork chain collapses to one root. A low hit count is not scarcity
until a known-present control returns the planted repository.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

UNIT = "WFA-0024"
KNOWN_PRESENT_REPO = "langchain-ai/langgraph"
KNOWN_PRESENT_QUERY = 'repo:langchain-ai/langgraph "class StateGraph"'
ACTIVITY_FLOOR = {
    "min_stargazers": 100,
    "min_pushed_at": "2025-01-01T00:00:00Z",
    "exclude_archived": True,
    "license_source": "github-repo-api-license.spdx_id",
}

INJECTION_RE = re.compile(
    r"(?is)(ignore (all )?(previous|prior|above) (instructions|prompts)"
    r"|you are now (?:a |an )?"
    r"|system\s*:\s*you"
    r"|<\/?system>"
    r"|sudo rm -rf"
    r"|curl\s+[^\n]+\|\s*(?:ba)?sh)"
)

MECHANISM_LABELS = {
    "typed-state-graph": "typed stages / state graph",
    "interrupt-resume-gate": "interrupt/resume gate (stop until resume payload)",
    "conditional-edges": "typed conditional edges between stages",
    "role-handoff": "explicit role handoff between agents",
    "crew-flow-persistence": "multi-agent flow state persistence",
    "hitl-stop-rule": "human-in-the-loop stop rule",
    "max-turns-stop-rule": "max-turns / task termination stop rule",
    "agent-role": "named agent role",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_name(hit: dict) -> str:
    repo = hit.get("repository") if isinstance(hit.get("repository"), dict) else {}
    name = (
        hit.get("full_name")
        or hit.get("repo")
        or repo.get("full_name")
        or repo.get("name")
        or ""
    )
    return str(name).replace("\\", "/").strip()


def fork_root(record: dict) -> str:
    """A fork chain counts once: prefer GitHub `source` (network root), else parent, else self."""
    if not record.get("fork"):
        return str(record.get("full_name") or repo_name(record))
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    parent = record.get("parent") if isinstance(record.get("parent"), dict) else {}
    return str(
        source.get("full_name")
        or parent.get("full_name")
        or record.get("full_name")
        or repo_name(record)
    )


def dedup_fork_chains(records: list[dict]) -> dict:
    groups: dict[str, list[dict]] = {}
    for rec in records:
        groups.setdefault(fork_root(rec), []).append(rec)
    canonical: list[dict] = []
    dropped: list[dict] = []
    for root, members in groups.items():
        members_sorted = sorted(
            members,
            key=lambda r: (
                0 if not r.get("fork") else 1,
                -int(r.get("stargazers_count") or r.get("stars") or 0),
                str(r.get("full_name") or ""),
            ),
        )
        keep = dict(members_sorted[0])
        keep["fork_root"] = root
        keep["fork_chain_size"] = len(members)
        keep["fork_chain_members"] = [
            str(m.get("full_name") or repo_name(m)) for m in members_sorted
        ]
        canonical.append(keep)
        for extra in members_sorted[1:]:
            dropped.append(
                {
                    "full_name": extra.get("full_name"),
                    "counted_as": root,
                    "reason": "trivial-or-descendant-fork-collapsed",
                }
            )
    return {
        "canonical": canonical,
        "dropped": dropped,
        "unique_count": len(canonical),
        "raw_count": len(records),
    }


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def passes_activity_floor(record: dict, floor: dict | None = None) -> dict:
    floor = floor or ACTIVITY_FLOOR
    stars = int(record.get("stargazers_count") or record.get("stars") or 0)
    pushed = _parse_ts(str(record.get("pushed_at") or ""))
    min_pushed = _parse_ts(str(floor["min_pushed_at"]))
    archived = bool(record.get("archived"))
    license_obj = record.get("license") if isinstance(record.get("license"), dict) else {}
    spdx = license_obj.get("spdx_id") or license_obj.get("key")
    reasons: list[str] = []
    if stars < int(floor["min_stargazers"]):
        reasons.append(f"stars {stars} < {floor['min_stargazers']}")
    if floor.get("exclude_archived") and archived:
        reasons.append("archived")
    if min_pushed and (pushed is None or pushed < min_pushed):
        reasons.append(f"pushed_at {record.get('pushed_at')!r} below floor")
    return {
        "pass": not reasons,
        "stars": stars,
        "pushed_at": record.get("pushed_at"),
        "archived": archived,
        "license_spdx": spdx,
        "license_source": "github-api-license-field",
        "reasons": reasons,
    }


def scarcity_gate(hits: list[dict], known_repo: str = KNOWN_PRESENT_REPO) -> dict:
    names = {repo_name(h) for h in hits}
    found = known_repo in names
    unique = {n for n in names if n}
    return {
        "known_present_repo": known_repo,
        "known_present_found": found,
        "unique_repo_count": len(unique),
        "scarcity_claim_allowed": found,
        "verdict": "CONTROL-PASS" if found else "CONTROL-FAILED",
        "reason": (
            None
            if found
            else (
                "KNOWN-PRESENT repository missing from result set; "
                "a low hit count is detector-failure, not scarcity"
            )
        ),
    }


def interpret_volume(hits: list[dict], known_repo: str = KNOWN_PRESENT_REPO) -> dict:
    gate = scarcity_gate(hits, known_repo)
    if not gate["scarcity_claim_allowed"]:
        return {
            **gate,
            "volume": None,
            "sparse": None,
            "interpretation": "REFUSED",
        }
    n = gate["unique_repo_count"]
    sparse = n < 5
    return {
        **gate,
        "volume": n,
        "sparse": sparse,
        "interpretation": "SPARSE" if sparse else "ABUNDANT",
    }


def detect_injection(text: str) -> dict:
    matches = [m.group(0)[:80] for m in INJECTION_RE.finditer(text or "")]
    return {
        "injection_detected": bool(matches),
        "injection_detected": bool(matches),
        "match_count": len(matches),
        "samples": matches[:3],
        "handling": "treated-as-untrusted-DATA-never-executed",
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def parse_python_ir(text: str, filename: str = "module.py") -> dict:
    inj = detect_injection(text)
    constructs: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "ok": False,
            "language": "python",
            "filename": filename,
            "error": f"SyntaxError:{exc.msg}",
            "constructs": [],
        "keyword_hits": _keyword_hits(text),
        "keyword_hits": _keyword_hits(text),
        "construct_present": False,
        "construct_present": False,
        "keyword_is_not_evidence": True,
        **inj,
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            name = node.name
            if name in {"StateGraph", "CompiledStateGraph", "StateGraphProtocol"}:
                constructs.add("typed-state-graph")
            if name in {"Handoff"}:
                constructs.add("role-handoff")
            if name in {"FlowPersistence", "Crew"}:
                constructs.add("crew-flow-persistence")
            if name in {"Agent", "ConversableAgent"}:
                constructs.add("agent-role")
            if name in {"Task"}:
                constructs.add("max-turns-stop-rule")
        if isinstance(node, ast.FunctionDef):
            if node.name == "interrupt":
                constructs.add("interrupt-resume-gate")
            if node.name in {"save_pending_feedback", "load_pending_feedback"}:
                constructs.add("hitl-stop-rule")
                constructs.add("crew-flow-persistence")
        if isinstance(node, ast.Call):
            fn = _call_name(node.func)
            if fn in {"add_node", "add_edge", "add_conditional_edges"}:
                constructs.add("typed-state-graph")
            if fn == "add_conditional_edges":
                constructs.add("conditional-edges")
            if fn == "interrupt":
                constructs.add("interrupt-resume-gate")
            if fn in {"handoff", "transfer_to"}:
                constructs.add("role-handoff")
    return {
        "ok": True,
        "language": "python",
        "filename": filename,
        "constructs": sorted(constructs),
        "keyword_hits": _keyword_hits(text),
        "keyword_hits": _keyword_hits(text),
        "construct_present": bool(constructs),
        "construct_present": bool(constructs),
        "keyword_is_not_evidence": True,
        **inj,
    }


def _keyword_hits(text: str) -> list[str]:
    found = []
    low = text.lower()
    for word in ("gate", "stop-rule", "stop_rule", "stage", "role", "handoff", "interrupt"):
        if word in low:
            found.append(word)
    return found


def parse_json_ir(text: str, filename: str = "workflow.json") -> dict:
    inj = detect_injection(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "language": "json",
            "filename": filename,
            "error": f"JSONDecodeError:{exc.msg}",
            "constructs": [],
            "keyword_hits": _keyword_hits(text),
            "keyword_hits": _keyword_hits(text),
            "construct_present": False,
            "construct_present": False,
            "keyword_is_not_evidence": True,
            **inj,
        }
    constructs: set[str] = set()
    if isinstance(data, dict):
        stages = data.get("stages")
        if isinstance(stages, list):
            for stage in stages:
                if not isinstance(stage, dict):
                    continue
                if stage.get("type") or stage.get("id"):
                    constructs.add("typed-state-graph")
                role = stage.get("role")
                if role:
                    constructs.add("agent-role")
                gate = stage.get("gate") or stage.get("type")
                if gate == "gate" or (isinstance(stage.get("gate"), dict)):
                    constructs.add("interrupt-resume-gate")
        roles = data.get("roles")
        if isinstance(roles, list) and roles:
            constructs.add("agent-role")
        stops = data.get("stop_rules") or data.get("stop-rules")
        if isinstance(stops, list) and stops:
            constructs.add("max-turns-stop-rule")
            for item in stops:
                if isinstance(item, dict) and str(item.get("kind") or "").lower() in {
                    "hitl",
                    "human",
                    "approval",
                }:
                    constructs.add("hitl-stop-rule")
        if data.get("handoffs") or data.get("handoff"):
            constructs.add("role-handoff")
    return {
        "ok": True,
        "language": "json",
        "filename": filename,
        "constructs": sorted(constructs),
        "keyword_hits": _keyword_hits(text),
        "keyword_hits": _keyword_hits(text),
        "construct_present": bool(constructs),
        "construct_present": bool(constructs),
        "keyword_is_not_evidence": True,
        **inj,
    }


def parse_ir(text: str, filename: str = "file.txt") -> dict:
    """Parse workflow IR. Never exec. Keyword-only mentions are not constructs."""
    name = filename.lower()
    if name.endswith(".py"):
        return parse_python_ir(text, filename)
    if name.endswith(".json"):
        return parse_json_ir(text, filename)
    inj = detect_injection(text)
    return {
        "ok": True,
        "language": "text",
        "filename": filename,
        "constructs": [],
        "keyword_hits": _keyword_hits(text),
        "keyword_hits": _keyword_hits(text),
        "construct_present": False,
        "construct_present": False,
        "keyword_is_not_evidence": True,
        **inj,
    }


def registry_gaps(constructs: list[str], registry_mechanisms: set[str]) -> dict:
    present = sorted(set(constructs))
    missing = [c for c in present if c not in registry_mechanisms]
    overlapping = [c for c in present if c in registry_mechanisms]
    return {
        "in_fetched_ir": present,
        "in_registry": overlapping,
        "registry_lacks": missing,
        "labels": {c: MECHANISM_LABELS.get(c, c) for c in present},
    }


def attach_search_hit_repo(item: dict, repo_doc: dict) -> dict:
    """Evidence A: stars, pushed_at, license from the repo API document, not a README badge."""
    license_obj = repo_doc.get("license") if isinstance(repo_doc.get("license"), dict) else {}
    return {
        "path": item.get("path"),
        "html_url": item.get("html_url"),
        "sha": item.get("sha"),
        "full_name": repo_doc.get("full_name") or repo_name(item),
        "fork": bool(repo_doc.get("fork")),
        "parent": repo_doc.get("parent"),
        "source": repo_doc.get("source"),
        "stargazers_count": repo_doc.get("stargazers_count"),
        "pushed_at": repo_doc.get("pushed_at"),
        "archived": repo_doc.get("archived"),
        "license": {
            "spdx_id": license_obj.get("spdx_id"),
            "key": license_obj.get("key"),
            "name": license_obj.get("name"),
            "source": "github-repo-api-license-field",
        },
        "activity_floor": passes_activity_floor(repo_doc),
    }


def encode_search_path(query: str) -> str:
    return f"search/code?q={quote(query)}"


encode_search_path = encode_search_path
KNOWN_PRESENT_QUERY = KNOWN_PRESENT_QUERY
scarcity_gate = scarcity_gate
passes_activity_floor = passes_activity_floor
registry_gaps = registry_gaps
ACTIVITY_FLOOR = ACTIVITY_FLOOR


# Probe-facing aliases (stable names used by probe1/probe2).
KNOWN_PRESENT_REPO = KNOWN_PRESENT_REPO
interpret_volume = interpret_volume
dedup_fork_chains = dedup_fork_chains
parse_ir = parse_ir
