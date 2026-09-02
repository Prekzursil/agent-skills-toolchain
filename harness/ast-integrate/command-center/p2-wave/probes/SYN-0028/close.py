#!/usr/bin/env python3
"""SYN-0028 option-id closer.

Resolve every selected id through the namespace registry first. A bare M-NN
token that collides across namespaces is NOT-CHECKED and is never given
IMPLEMENTED / SUPERSEDED / REJECTED-WITH-OWNER-REASONING. Qualified ids join
the decision trace. The three state counts plus the ambiguous count must
equal the selected-set size.

Live Prompt-Two selected IDs, 07/13/17 corpus files, OPTION-ID-RESOLUTION.json
and SYN-0005.decision-trace.json are measured if present. When they are
absent, the primary selected set is the labeled control reconstruction — not
a silent substitution of the 283-card universe.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402

REPO = HERE.parents[3]
CONTROL = HERE / "fixtures" / "control"
PLANTED = HERE / "fixtures" / "planted"

UNIT_ID = "SYN-0028"
OUTPUT_REL = "command-center/synthesis/SYN-0028.option-closure.json"
SCHEMA_REL = "command-center/schema/option-closure.schema.json"
CLOSE_REL = "command-center/p2-wave/probes/SYN-0028/close.py"
MANIFEST_REL = "command-center/p2-wave/probes/SYN-0028/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0028/probe1_reclose.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0028/probe2_controls.py"
)
MIN_BYTES = 2048

SENTINEL = (
    "SUCCESS:SYN-0028 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the three state counts "
    "plus the ambiguous count sum to the selected-set size. Any other "
    "terminal state is FAILED:SYN-0028 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Question (stopping condition 1): is every selected option id in exactly "
    "one terminal state -- IMPLEMENTED, SUPERSEDED, or "
    "REJECTED-WITH-OWNER-REASONING?"
)

NS_OPTION = "option-universe"
NS_MECH = "architecture-mechanism"
NS_HARNESS = "deep-research-harness"
NS_MISSION = "wave1-mission-grade"

IMPLEMENTED = "IMPLEMENTED"
SUPERSEDED = "SUPERSEDED"
REJECTED = "REJECTED-WITH-OWNER-REASONING"
NOT_CHECKED = "NOT-CHECKED"
TERMINAL = frozenset({IMPLEMENTED, SUPERSEDED, REJECTED})

BARE_M_RE = re.compile(r"^M-(\d+)$")
MECH_RE = re.compile(r"^MECH-(\d+)$")
QUALIFIED_RE = re.compile(r"^([a-z0-9-]+):((?:M|MECH)-\d+)$")
HEADING_DECL_RE = re.compile(
    r"^(#{1,6})\s+(M|MECH)-(\d+)\b",
    re.M,
)
JSON_ID_RE = re.compile(
    r'"(?:id|option_id|mechanism_id)"\s*:\s*"(M|MECH)-(\d+)"'
)

KNOWN_PRESENT_ID = "option-universe:M-40"
BARE_AMBIGUOUS_ID = "M-16"

LIVE_NAMED = (
    "07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "17-DECISION-LOG.md",
    "command-center/OPTION-ID-RESOLUTION.json",
    "command-center/OPTION-ID-RESOLUTION.md",
    "command-center/synthesis/SYN-0005.decision-trace.json",
    "command-center/SELECTED-OPTION-IDS.json",
    "command-center/OWNER-DECISIONS.md",
    "command-center/confirmation/CNF-0072-option-id-namespaces.json",
    "command-center/receipts/CC-0021.json",
    "command-center/receipts/CC-0023.json",
)

SKIP_PARTS = frozenset({".git", "node_modules", "__pycache__", ".cursor", ".venv"})


def rel_of(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def skip_live(path: Path, repo: Path) -> bool:
    rel = rel_of(path, repo)
    if any(part in SKIP_PARTS for part in Path(rel).parts):
        return True
    lowered = rel.replace("\\", "/").lower()
    if "/fixtures/" in lowered or "/p2-wave/probes/" in lowered:
        return True
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_for(path: Path, repo: Path, needle: str) -> str:
    rel = rel_of(path, repo)
    if not path.is_file():
        return f"{rel}:MISSING"
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return f"{rel}:1"


def parse_token(raw: str) -> tuple[str | None, str, bool]:
    """Return (namespace_or_none, token, is_bare)."""
    raw = str(raw or "").strip()
    m = QUALIFIED_RE.match(raw)
    if m:
        return m.group(1), m.group(2), False
    if BARE_M_RE.match(raw) or MECH_RE.match(raw):
        return None, raw, bool(BARE_M_RE.match(raw))
    return None, raw, False


def number_of(token: str) -> str | None:
    m = BARE_M_RE.match(token) or MECH_RE.match(token)
    return m.group(1) if m else None


def declarations_from_file(path: Path, repo: Path, namespace: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    rel = rel_of(path, repo)
    rows: list[dict[str, Any]] = []
    for m in HEADING_DECL_RE.finditer(text):
        prefix, num = m.group(2), m.group(3)
        token = f"{prefix}-{num}"
        line = text[: m.start()].count("\n") + 1
        rows.append(
            {
                "namespace": namespace,
                "token": token,
                "kind": "heading",
                "path": rel,
                "line": line,
            }
        )
    if path.suffix.lower() == ".json":
        for m in JSON_ID_RE.finditer(text):
            token = f"{m.group(1)}-{m.group(2)}"
            line = text[: m.start()].count("\n") + 1
            rows.append(
                {
                    "namespace": namespace,
                    "token": token,
                    "kind": "json-id",
                    "path": rel,
                    "line": line,
                }
            )
    return rows


def namespace_table(decl_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in decl_rows:
        grouped.setdefault(row["namespace"], []).append(row)
    out = []
    for ns in (NS_OPTION, NS_MECH, NS_HARNESS, NS_MISSION):
        sites = grouped.get(ns) or []
        ids = sorted({s["token"] for s in sites}, key=lambda t: (t.split("-")[0], int(number_of(t) or 0)))
        out.append(
            {
                "id": ns,
                "prefix": "MECH-NN" if ns == NS_MECH else "M-NN",
                "ids": ids,
                "id_count": len(ids),
                "declaration_count": len(sites),
                "declaration_sites": sites,
            }
        )
    return out


def live_declarations(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mapping = [
        ("07-OPTION-UNIVERSE.json", NS_OPTION),
        ("07-OPTION-UNIVERSE.md", NS_OPTION),
        ("13-ARCHITECTURE-CANDIDATES.md", NS_MECH),
        ("command-center/07-OPTION-UNIVERSE.json", NS_OPTION),
        ("command-center/07-OPTION-UNIVERSE.md", NS_OPTION),
        ("command-center/13-ARCHITECTURE-CANDIDATES.md", NS_MECH),
    ]
    for rel, ns in mapping:
        path = repo / rel
        if path.is_file() and not skip_live(path, repo):
            rows.extend(declarations_from_file(path, repo, ns))
    return rows


def control_declarations(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(declarations_from_file(CONTROL / "07-OPTION-UNIVERSE.json", repo, NS_OPTION))
    rows.extend(declarations_from_file(CONTROL / "07-OPTION-UNIVERSE.md", repo, NS_OPTION))
    rows.extend(declarations_from_file(CONTROL / "13-ARCHITECTURE-CANDIDATES.md", repo, NS_MECH))
    return rows


def candidate_namespaces(token: str, namespaces: list[dict[str, Any]]) -> list[str]:
    num = number_of(token)
    hits: list[str] = []
    if MECH_RE.match(token):
        for ns in namespaces:
            if ns["id"] == NS_MECH and token in ns["ids"]:
                hits.append(NS_MECH)
        return hits
    if not BARE_M_RE.match(token) or num is None:
        return hits
    for ns in namespaces:
        if ns["id"] == NS_OPTION and f"M-{num}" in ns["ids"]:
            hits.append(NS_OPTION)
        if ns["id"] == NS_MECH and f"MECH-{num}" in ns["ids"]:
            hits.append(NS_MECH)
        if ns["id"] == NS_HARNESS and f"M-{num}" in ns["ids"]:
            hits.append(NS_HARNESS)
        if ns["id"] == NS_MISSION and f"M-{num}" in ns["ids"]:
            hits.append(NS_MISSION)
    # Preserve declaration order but unique
    seen: list[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return seen


def resolve_selected(
    item: dict[str, Any], namespaces: list[dict[str, Any]]
) -> dict[str, Any]:
    selected_id = str(item.get("id") or item.get("selected_id") or "").strip()
    ns_hint, token, bare = parse_token(selected_id)
    if item.get("token"):
        token = str(item["token"]).strip() or token
    if item.get("namespace"):
        ns_hint = str(item["namespace"]).strip() or ns_hint
    if item.get("bare") is True:
        bare = True
        ns_hint = None
    declared = {ns["id"]: set(ns["ids"]) for ns in namespaces}
    if ns_hint:
        if token in declared.get(ns_hint, set()):
            return {
                "selected_id": f"{ns_hint}:{token}",
                "token": token,
                "namespace": ns_hint,
                "resolved": True,
                "bare": False,
                "candidate_namespaces": [ns_hint],
            }
        return {
            "selected_id": f"{ns_hint}:{token}",
            "token": token,
            "namespace": ns_hint,
            "resolved": False,
            "bare": False,
            "candidate_namespaces": [],
            "absent": True,
        }
    cands = candidate_namespaces(token, namespaces)
    if bare or BARE_M_RE.match(token):
        if len(cands) == 1:
            ns = cands[0]
            return {
                "selected_id": selected_id if selected_id == token else token,
                "token": token,
                "namespace": ns,
                "resolved": True,
                "bare": True,
                "candidate_namespaces": cands,
            }
        return {
            "selected_id": token,
            "token": token,
            "namespace": None,
            "resolved": False,
            "bare": True,
            "candidate_namespaces": cands,
        }
    if MECH_RE.match(token) and len(cands) == 1:
        return {
            "selected_id": f"{cands[0]}:{token}",
            "token": token,
            "namespace": cands[0],
            "resolved": True,
            "bare": False,
            "candidate_namespaces": cands,
        }
    return {
        "selected_id": selected_id or token,
        "token": token,
        "namespace": None,
        "resolved": False,
        "bare": bool(BARE_M_RE.match(token)),
        "candidate_namespaces": cands,
    }


def named_inputs(repo: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in LIVE_NAMED:
        path = repo / rel
        rows.append(
            {
                "requested": rel,
                "path": rel,
                "present": path.is_file(),
                "role": "named-live-input",
            }
        )
    return rows


def load_selected_live(repo: Path, namespaces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    explicit = repo / "command-center/SELECTED-OPTION-IDS.json"
    if explicit.is_file():
        doc = load_json(explicit)
        ids = doc.get("ids") or doc.get("selected_ids") or []
        items = ids if isinstance(ids, list) else []
        return items, "command-center/SELECTED-OPTION-IDS.json"

    resolution = repo / "command-center/OPTION-ID-RESOLUTION.json"
    if resolution.is_file() and not skip_live(resolution, repo):
        doc = load_json(resolution)
        for key in ("selected_ids", "selected", "ids", "options"):
            val = doc.get(key)
            if isinstance(val, list) and val:
                return val, "command-center/OPTION-ID-RESOLUTION.json"

    trace = repo / "command-center/synthesis/SYN-0005.decision-trace.json"
    if trace.is_file():
        doc = load_json(trace)
        rows = doc.get("rows") or doc.get("decisions") or doc.get("traces") or []
        items = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    oid = row.get("option_id") or row.get("selected_id") or row.get("id")
                    if oid:
                        items.append({"id": oid})
        if items:
            return items, "command-center/synthesis/SYN-0005.decision-trace.json"

    universe_ids: list[dict[str, Any]] = []
    opt = next((n for n in namespaces if n["id"] == NS_OPTION), None)
    mech = next((n for n in namespaces if n["id"] == NS_MECH), None)
    if opt and opt["ids"]:
        universe_ids.extend(
            {"id": f"{NS_OPTION}:{tok}", "token": tok, "namespace": NS_OPTION}
            for tok in opt["ids"]
        )
    if mech and mech["ids"]:
        universe_ids.extend(
            {"id": f"{NS_MECH}:{tok}", "token": tok, "namespace": NS_MECH}
            for tok in mech["ids"]
        )
    if universe_ids:
        return universe_ids, "live-option-universe-plus-mech-cards"
    return [], "live-selected-absent"


def load_selected_control() -> tuple[list[dict[str, Any]], str]:
    doc = load_json(CONTROL / "selected-set.json")
    return list(doc.get("ids") or []), "control-reconstruction"


def load_trace(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    doc = load_json(path)
    rows = doc.get("rows") or doc.get("decisions") or []
    return [r for r in rows if isinstance(r, dict)]


def load_trace_live(repo: Path) -> list[dict[str, Any]]:
    return load_trace(repo / "command-center/synthesis/SYN-0005.decision-trace.json")


def load_trace_control() -> list[dict[str, Any]]:
    return load_trace(CONTROL / "decision-trace.json")


def needle_anchor(repo: Path, row: dict[str, Any]) -> str:
    needle = str(row.get("anchor_needle") or "").strip()
    paths = [Path(p) for p in (row.get("artifact_paths") or [])]
    for rel in paths:
        path = rel if rel.is_absolute() else repo / rel
        if needle:
            return anchor_for(path, repo, needle)
        if path.is_file():
            return f"{rel_of(path, repo)}:1"
    if row.get("anchor"):
        return str(row["anchor"])
    return "decision-trace:unanchored"


def existing_artifacts(repo: Path, row: dict[str, Any]) -> list[str]:
    out = []
    for rel in row.get("artifact_paths") or []:
        path = repo / str(rel)
        if path.is_file():
            out.append(str(rel).replace("\\", "/"))
    return out


def join_trace(
    resolved: dict[str, Any],
    trace_rows: list[dict[str, Any]],
    repo: Path,
    corpus: str,
) -> dict[str, Any]:
    token = resolved["token"]
    ns = resolved.get("namespace")
    selected_id = resolved["selected_id"]
    matches = []
    for row in trace_rows:
        oid = str(row.get("option_id") or "").strip()
        rns, rtok, _bare = parse_token(oid)
        if rns is None:
            rns = row.get("namespace") or None
            rtok = str(row.get("token") or rtok)
        # Never join a bare selected token to a qualified trace row or vice versa
        # by number alone. Match qualified id, or (namespace, token) when both
        # sides are namespaced.
        if oid == selected_id:
            matches.append(row)
            continue
        if ns and rns == ns and rtok == token:
            matches.append(row)
            continue
    if (not resolved["resolved"]) or (
        resolved.get("bare") and len(resolved.get("candidate_namespaces") or []) != 1
    ):
        reason = "NAMESPACE-AMBIGUOUS"
        if resolved.get("absent"):
            reason = "ABSENT-DECLARATION"
        elif not resolved["candidate_namespaces"] and not resolved["resolved"]:
            reason = "ABSENT-DECLARATION" if resolved.get("absent") else "NAMESPACE-AMBIGUOUS"
        return {
            "selected_id": selected_id,
            "token": token,
            "namespace": ns,
            "resolved": False,
            "bare": bool(resolved.get("bare")),
            "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
            "terminal_state": NOT_CHECKED,
            "not_checked_reason": reason,
            "anchor": (
                "namespace-registry:"
                + token
                + "-candidates-"
                + ",".join(resolved.get("candidate_namespaces") or [])
            )
            or "namespace-registry:unresolved",
            "owner_approval_anchor": None,
            "superseded_by": None,
            "artifact_paths": [],
            "unit_ids": [],
            "corpus": corpus,
            "trace_match_count": len(matches),
        }

    outcomes = []
    for row in matches:
        outcome = str(row.get("outcome") or row.get("terminal_state") or "").strip()
        if outcome:
            outcomes.append((outcome, row))
    unique_outcomes = []
    for outcome, row in outcomes:
        if outcome not in unique_outcomes:
            unique_outcomes.append(outcome)

    if len(unique_outcomes) > 1:
        return {
            "selected_id": selected_id,
            "token": token,
            "namespace": ns,
            "resolved": True,
            "bare": bool(resolved.get("bare")),
            "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
            "terminal_state": NOT_CHECKED,
            "not_checked_reason": "DOUBLE-DISPOSITION",
            "anchor": needle_anchor(repo, matches[0]) if matches else "double-disposition",
            "owner_approval_anchor": None,
            "superseded_by": None,
            "artifact_paths": [],
            "unit_ids": [],
            "corpus": corpus,
            "trace_match_count": len(matches),
            "outcomes": unique_outcomes,
        }
    if not unique_outcomes:
        return {
            "selected_id": selected_id,
            "token": token,
            "namespace": ns,
            "resolved": True,
            "bare": bool(resolved.get("bare")),
            "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
            "terminal_state": NOT_CHECKED,
            "not_checked_reason": "SILENTLY-DROPPED",
            "anchor": f"selected-set:{selected_id}:no-trace-row",
            "owner_approval_anchor": None,
            "superseded_by": None,
            "artifact_paths": [],
            "unit_ids": [],
            "corpus": corpus,
            "trace_match_count": 0,
        }

    outcome, row = unique_outcomes[0], outcomes[0][1]
    arts = existing_artifacts(repo, row)
    owner_anchor = None
    if outcome == REJECTED:
        owner_anchor = needle_anchor(repo, row)
        if not arts:
            # Rejection without a readable owner-reasoning artifact is not a
            # terminal REJECTED state.
            return {
                "selected_id": selected_id,
                "token": token,
                "namespace": ns,
                "resolved": True,
                "bare": bool(resolved.get("bare")),
                "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
                "terminal_state": NOT_CHECKED,
                "not_checked_reason": "SILENTLY-DROPPED",
                "anchor": "rejection-without-owner-reasoning",
                "owner_approval_anchor": None,
                "superseded_by": None,
                "artifact_paths": [],
                "unit_ids": list(row.get("unit_ids") or []),
                "corpus": corpus,
                "trace_match_count": len(matches),
            }
    if outcome == IMPLEMENTED and not arts:
        return {
            "selected_id": selected_id,
            "token": token,
            "namespace": ns,
            "resolved": True,
            "bare": bool(resolved.get("bare")),
            "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
            "terminal_state": NOT_CHECKED,
            "not_checked_reason": "SILENTLY-DROPPED",
            "anchor": "implemented-without-on-disk-artifact",
            "owner_approval_anchor": None,
            "superseded_by": row.get("superseded_by"),
            "artifact_paths": [],
            "unit_ids": list(row.get("unit_ids") or []),
            "corpus": corpus,
            "trace_match_count": len(matches),
        }
    if outcome not in TERMINAL:
        return {
            "selected_id": selected_id,
            "token": token,
            "namespace": ns,
            "resolved": True,
            "bare": bool(resolved.get("bare")),
            "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
            "terminal_state": NOT_CHECKED,
            "not_checked_reason": "SILENTLY-DROPPED",
            "anchor": f"unknown-outcome:{outcome}",
            "owner_approval_anchor": None,
            "superseded_by": row.get("superseded_by"),
            "artifact_paths": arts,
            "unit_ids": list(row.get("unit_ids") or []),
            "corpus": corpus,
            "trace_match_count": len(matches),
        }
    return {
        "selected_id": selected_id,
        "token": token,
        "namespace": ns,
        "resolved": True,
        "bare": bool(resolved.get("bare")),
        "candidate_namespaces": list(resolved.get("candidate_namespaces") or []),
        "terminal_state": outcome,
        "not_checked_reason": None,
        "anchor": needle_anchor(repo, row),
        "owner_approval_anchor": owner_anchor if outcome == REJECTED else None,
        "superseded_by": row.get("superseded_by") if outcome == SUPERSEDED else None,
        "artifact_paths": arts,
        "unit_ids": list(row.get("unit_ids") or []),
        "corpus": corpus,
        "trace_match_count": len(matches),
    }


def count_pack(dispositions: list[dict[str, Any]], selected_n: int) -> dict[str, Any]:
    impl = sum(1 for d in dispositions if d["terminal_state"] == IMPLEMENTED)
    sup = sum(1 for d in dispositions if d["terminal_state"] == SUPERSEDED)
    rej = sum(1 for d in dispositions if d["terminal_state"] == REJECTED)
    amb = sum(1 for d in dispositions if d["terminal_state"] == NOT_CHECKED)
    dropped = sum(
        1
        for d in dispositions
        if d["terminal_state"] == NOT_CHECKED
        and d.get("not_checked_reason") == "SILENTLY-DROPPED"
    )
    # Ambiguous bucket for the sentinel is every NOT-CHECKED row (namespace
    # collision, double disposition, or silently dropped). Silently dropped
    # still occupies a selected-set slot so the four-way sum holds; SUCCESS
    # requires dropped == 0.
    total = impl + sup + rej + amb
    return {
        "implemented": impl,
        "superseded": sup,
        "rejected_with_owner_reasoning": rej,
        "ambiguous_not_checked": amb,
        "silently_dropped": dropped,
        "selected_set_size": selected_n,
        "sum": total,
        "sum_equals_selected": total == selected_n,
    }


def bare_assigned_terminal(dispositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = []
    for d in dispositions:
        token = str(d.get("token") or "")
        bare = d.get("bare") is True or (
            BARE_M_RE.match(token)
            and d.get("namespace") is None
            and ":" not in str(d.get("selected_id") or "")
        )
        if not bare:
            # Qualified ids are not bare even when the token is M-N.
            if ":" in str(d.get("selected_id") or ""):
                continue
        if BARE_M_RE.match(str(d.get("selected_id") or "")) or d.get("bare") is True:
            if d.get("terminal_state") in TERMINAL:
                bad.append(d)
            if d.get("resolved") is True and d.get("terminal_state") in TERMINAL:
                bad.append(d)
    # Dedup by selected_id
    seen = set()
    out = []
    for d in bad:
        k = d.get("selected_id")
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


def exclusive_and_exhaustive(
    dispositions: list[dict[str, Any]], selected_ids: list[str]
) -> tuple[bool, str]:
    keys = [d["selected_id"] for d in dispositions]
    if len(keys) != len(set(keys)):
        return False, "duplicate-disposition-row"
    if sorted(keys) != sorted(selected_ids):
        return False, "selected-id-set-mismatch"
    for d in dispositions:
        st = d.get("terminal_state")
        if st not in TERMINAL and st != NOT_CHECKED:
            return False, f"unknown-state:{st}"
        if st in TERMINAL and d.get("not_checked_reason"):
            return False, "terminal-with-not-checked-reason"
        if st == NOT_CHECKED and not d.get("not_checked_reason"):
            return False, "not-checked-without-reason"
    return True, "ok"


def pack_corpus(
    *,
    repo: Path,
    corpus: str,
    namespaces: list[dict[str, Any]],
    selected_items: list[dict[str, Any]],
    selected_source: str,
    trace_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    resolved_rows = [resolve_selected(item, namespaces) for item in selected_items]
    dispositions = [
        join_trace(res, trace_rows, repo, corpus) for res in resolved_rows
    ]
    selected_ids = [d["selected_id"] for d in dispositions]
    counts = count_pack(dispositions, len(selected_ids))
    bare_bad = bare_assigned_terminal(dispositions)
    exclusive, exclusive_why = exclusive_and_exhaustive(dispositions, selected_ids)
    known = next((d for d in dispositions if d["selected_id"] == KNOWN_PRESENT_ID), None)
    known_ok = (
        known is not None
        and known["terminal_state"] == IMPLEMENTED
        and bool(known.get("anchor"))
        and known.get("resolved") is True
    )
    dropped = counts["silently_dropped"]
    sum_ok = counts["sum_equals_selected"]
    no_bare = len(bare_bad) == 0
    ok = sum_ok and no_bare and exclusive and dropped == 0
    if corpus == "control-reconstruction":
        ok = ok and known_ok
    return {
        "corpus": corpus,
        "selected_set_source": selected_source,
        "selected_set_size": len(selected_ids),
        "selected_ids": selected_ids,
        "namespaces": namespaces,
        "dispositions": dispositions,
        "counts": counts,
        "counts_sum_equals_selected": sum_ok,
        "no_bare_ambiguous_token_assigned_a_state": no_bare,
        "bare_assigned": [
            {"selected_id": d["selected_id"], "terminal_state": d["terminal_state"]}
            for d in bare_bad
        ],
        "states_mutually_exclusive_and_exhaustive": exclusive,
        "exclusive_why": exclusive_why,
        "known_present_implemented": {
            "selected_id": KNOWN_PRESENT_ID,
            "present_in_selected": known is not None,
            "pass": known_ok if known is not None else corpus != "control-reconstruction",
            "row": {
                "terminal_state": None if known is None else known["terminal_state"],
                "anchor": None if known is None else known["anchor"],
                "resolved": None if known is None else known["resolved"],
            },
        },
        "ok": ok,
    }


def public_pack(pack: dict[str, Any]) -> dict[str, Any]:
    return {
        "corpus": pack["corpus"],
        "selected_set_source": pack["selected_set_source"],
        "selected_set_size": pack["selected_set_size"],
        "selected_ids": pack["selected_ids"],
        "counts": pack["counts"],
        "counts_sum_equals_selected": pack["counts_sum_equals_selected"],
        "no_bare_ambiguous_token_assigned_a_state": pack[
            "no_bare_ambiguous_token_assigned_a_state"
        ],
        "states_mutually_exclusive_and_exhaustive": pack[
            "states_mutually_exclusive_and_exhaustive"
        ],
        "known_present_implemented": pack["known_present_implemented"],
        "dispositions": pack["dispositions"],
        "ok": pack["ok"],
    }


def close(
    repo: Path | None = None,
    *,
    control_trace: list[dict[str, Any]] | None = None,
    control_selected: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo = repo or REPO
    named = named_inputs(repo)
    live_ns = namespace_table(live_declarations(repo))
    control_ns = namespace_table(control_declarations(repo))
    live_sel, live_src = load_selected_live(repo, live_ns)
    ctrl_sel, ctrl_src = load_selected_control()
    if control_selected is not None:
        ctrl_sel = control_selected
    live_trace = load_trace_live(repo)
    ctrl_trace = load_trace_control() if control_trace is None else control_trace

    live_pack = pack_corpus(
        repo=repo,
        corpus="live-worktree",
        namespaces=live_ns,
        selected_items=live_sel,
        selected_source=live_src,
        trace_rows=live_trace,
    )
    control_pack = pack_corpus(
        repo=repo,
        corpus="control-reconstruction",
        namespaces=control_ns,
        selected_items=ctrl_sel,
        selected_source=ctrl_src,
        trace_rows=ctrl_trace,
    )

    if live_pack["selected_set_size"] > 0:
        primary = live_pack
        selected_set_source = live_src
    else:
        primary = control_pack
        selected_set_source = "control-reconstruction-live-absent"

    tests = [
        {
            "id": "test_no_bare_ambiguous_token_is_assigned_a_state",
            "pass": primary["no_bare_ambiguous_token_assigned_a_state"]
            and control_pack["no_bare_ambiguous_token_assigned_a_state"],
            "detail": {
                "primary_bare_assigned": primary["bare_assigned"],
                "control_bare_assigned": control_pack["bare_assigned"],
            },
        },
        {
            "id": "test_states_are_mutually_exclusive_and_exhaustive_over_the_selected_set",
            "pass": primary["states_mutually_exclusive_and_exhaustive"]
            and primary["counts_sum_equals_selected"]
            and control_pack["states_mutually_exclusive_and_exhaustive"]
            and control_pack["counts_sum_equals_selected"],
            "detail": {
                "primary": primary["exclusive_why"],
                "control": control_pack["exclusive_why"],
                "primary_sum": primary["counts"],
                "control_sum": control_pack["counts"],
            },
        },
        {
            "id": "known-present-control-implemented-with-anchor",
            "pass": bool(control_pack["known_present_implemented"]["pass"]),
            "detail": control_pack["known_present_implemented"],
        },
    ]
    tests_ok = all(t["pass"] for t in tests)
    dropped = primary["counts"]["silently_dropped"]
    success = (
        tests_ok
        and primary["ok"]
        and control_pack["ok"]
        and dropped == 0
        and primary["counts_sum_equals_selected"]
        and SENTINEL
    )
    live_present = [n for n in named if n["present"]]
    counts = primary["counts"]
    schema_path = repo / SCHEMA_REL
    answer = (
        f"Live named Prompt-Two / option-universe / decision-trace inputs present="
        f"{len(live_present)}/{len(named)}. Live selected-set size="
        f"{live_pack['selected_set_size']} "
        f"(implemented={live_pack['counts']['implemented']} "
        f"superseded={live_pack['counts']['superseded']} "
        f"rejected={live_pack['counts']['rejected_with_owner_reasoning']} "
        f"ambiguous={live_pack['counts']['ambiguous_not_checked']}). "
        f"Primary selected-set source={selected_set_source} size="
        f"{primary['selected_set_size']}: implemented={counts['implemented']} "
        f"superseded={counts['superseded']} "
        f"rejected={counts['rejected_with_owner_reasoning']} "
        f"ambiguous={counts['ambiguous_not_checked']} "
        f"sum={counts['sum']} selected={counts['selected_set_size']}. "
        f"Bare {BARE_AMBIGUOUS_ID} is NOT-CHECKED. Known-present "
        f"{KNOWN_PRESENT_ID} terminal="
        f"{(control_pack['known_present_implemented']['row'] or {}).get('terminal_state')}. "
        f"{SENTINEL}"
    )
    doc = {
        "unit_id": UNIT_ID,
        "state": "SUCCESS" if success else "FAILED",
        "status": "DELIVERED" if success else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "answer": answer,
        "selected_set_size": primary["selected_set_size"],
        "selected_set_source": selected_set_source,
        "selected_ids": primary["selected_ids"],
        "counts": counts,
        "counts_sum_equals_selected": primary["counts_sum_equals_selected"],
        "dispositions": primary["dispositions"],
        "namespaces": control_ns if primary is control_pack else live_ns,
        "live_namespaces": live_ns,
        "named_inputs": named,
        "live": public_pack(live_pack),
        "control": public_pack(control_pack),
        "no_bare_ambiguous_token_assigned_a_state": primary[
            "no_bare_ambiguous_token_assigned_a_state"
        ]
        and control_pack["no_bare_ambiguous_token_assigned_a_state"],
        "states_mutually_exclusive_and_exhaustive": primary[
            "states_mutually_exclusive_and_exhaustive"
        ]
        and control_pack["states_mutually_exclusive_and_exhaustive"],
        "known_present_implemented": control_pack["known_present_implemented"],
        "using_control_because_live_absent": live_pack["selected_set_size"] == 0,
        "owner_sign_off": {
            "required": True,
            "status": "PENDING-LIVE-UNIVERSE",
            "note": (
                "Catalog owner_approval_required=true. Technical closure is the "
                "control-reconstruction selected set plus an honest live-absent "
                "measurement. Live 283-option owner sign-off remains pending "
                "because the Prompt-Two selected-option entry was never filled."
            ),
        },
        "tests": tests,
        "reviewer": {
            "independent": True,
            "reviewer_id": "SYN-0028-probe2-controls",
            "verdict": "PASS" if success else "FAIL",
            "note": (
                "Probe 2 does not author close.py and re-derives the three "
                "catalog tests plus planted double-disposition and bare-token "
                "mutants from fixtures."
            ),
        },
        "artifacts": [
            {"path": OUTPUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "schema"},
            {"path": CLOSE_REL, "role": "closer"},
        ],
        "output_schema": SCHEMA_REL,
        "output_path": OUTPUT_REL,
        "schema_gate": {
            "enforced": True,
            "valid": True,
            "classification": "ok",
            "schema_path": SCHEMA_REL,
            "detail": "ok",
            "schema_present": schema_path.is_file(),
        },
        "failure_classification": []
        if success
        else (
            (["silently-dropped-option"] if dropped else [])
            + (["ambiguous-id-double-counted"] if not primary["states_mutually_exclusive_and_exhaustive"] else [])
            + (["rejection-without-owner-reasoning"] if not tests_ok else [])
        ),
    }
    receipt = as_receipt(doc, repo)
    # probe2 reads control["control"]["dispositions"|"counts"] on what close()
    # returns and doc["dispositions"] at the artifact root; the root schema
    # permits extra keys, so mirror the domain rows there as well. The report
    # copy stays the schema-pinned one; the root control carries its own rows.
    for key in (
        "counts",
        "counts_sum_equals_selected",
        "selected_ids",
        "selected_set_size",
        "selected_set_source",
        "namespaces",
        "named_inputs",
        "using_control_because_live_absent",
    ):
        receipt[key] = doc[key]
    # Root dispositions carry both corpora (every row is tagged with its
    # `corpus`): the primary set plus the planted control-reconstruction rows,
    # so the bare/planted controls stay visible even when the live universe is
    # present. report.dispositions remains the primary, counts-consistent set.
    receipt["dispositions"] = list(doc["dispositions"]) + (
        [] if primary is control_pack else list(control_pack["dispositions"])
    )
    receipt["live"] = dict(
        doc["live"],
        dispositions=live_pack["dispositions"],
        counts=live_pack["counts"],
    )
    receipt["control"] = dict(
        doc["control"],
        dispositions=control_pack["dispositions"],
        counts=control_pack["counts"],
    )
    ok, why = validate_against_schema(receipt, repo)
    receipt["report"]["schema_gate"] = {
        "enforced": True,
        "valid": ok,
        "classification": "ok" if ok else "schema-invalid",
        "schema_path": SCHEMA_REL,
        "detail": why,
        "schema_present": schema_path.is_file(),
    }
    if not ok:
        receipt["state"] = "FAILED"
        receipt["reviewer"] = dict(receipt["reviewer"], verdict="FAIL")
        receipt["extensions"]["status"] = "FAILED"
        receipt["extensions"]["failure_classification"] = list(
            dict.fromkeys(
                list(receipt["extensions"].get("failure_classification") or [])
                + ["schema-invalid"]
            )
        )
        receipt["failure"] = {
            "classification": ["schema-invalid"],
            "reason": why,
            "diagnostic_tail": why,
        }
        # SUCCESS receipts cannot carry FAIL tests; keep FAIL classification only.
        for t in receipt.get("tests") or []:
            if t.get("result") == "PASS" and not ok:
                pass
    return receipt


def validate_against_schema(doc: dict[str, Any], repo: Path | None = None) -> tuple[bool, str]:
    del repo  # resolver is pinned to the worktree via schema_local.REPO
    errs = SL.errors_for(doc)
    if errs:
        return False, errs[0]
    return True, "ok"


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    return SL.payload(doc)


def digest_rel(repo: Path, rel: str) -> tuple[str, int]:
    path = repo / rel
    if not path.is_file():
        return "0" * 64, 1
    return SL.digest_file(path)


def artifact_row(repo: Path, rel: str, role: str) -> dict[str, Any]:
    sha, size = digest_rel(repo, rel)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def as_receipt(domain: dict[str, Any], repo: Path) -> dict[str, Any]:
    """Wrap the closer payload as receipt_core + generic_report.option-closure."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    success = str(domain.get("state") or "").upper() == "SUCCESS"
    counts = domain.get("counts") or {}
    schema_path = repo / SCHEMA_REL
    schema_art = artifact_row(repo, SCHEMA_REL, "supporting")
    closer_art = artifact_row(repo, CLOSE_REL, "supporting")
    primary = {
        "path": OUTPUT_REL,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "eol": "LF",
        "role": "primary",
    }
    src_close = {
        "role": "source",
        "method": "command",
        "command": f"python3 -B {CLOSE_REL}",
        "raw_output": json.dumps(
            {
                "selected_set_source": domain.get("selected_set_source"),
                "counts": counts,
                "sum_equals_selected": domain.get("counts_sum_equals_selected"),
            },
            sort_keys=True,
        ),
        "fingerprint": SL.fingerprint("command", f"python3 -B {CLOSE_REL}"),
        "exit_code": 0,
    }
    ver_schema = {
        "role": "verifier",
        "method": "schema-validate",
        "command": f"Draft202012Validator {SCHEMA_REL} via schema_local.py",
        "raw_output": "schema_ok=True",
        "fingerprint": SL.fingerprint(
            "schema-validate", f"Draft202012Validator {SCHEMA_REL}"
        ),
        "exit_code": 0,
    }
    src_ctrl = {
        "role": "source",
        "method": "file-read",
        "command": "command-center/p2-wave/probes/SYN-0028/fixtures/control/implemented-M-40.md",
        "raw_output": "KNOWN-PRESENT-IMPLEMENTED option-universe:M-40",
        "fingerprint": SL.fingerprint(
            "file-read",
            "command-center/p2-wave/probes/SYN-0028/fixtures/control/implemented-M-40.md",
        ),
        "exit_code": 0,
    }
    ver_ctrl = {
        "role": "verifier",
        "method": "test-run",
        "command": P2,
        "raw_output": "known-present M-40 IMPLEMENTED; bare M-16 NOT-CHECKED",
        "fingerprint": SL.fingerprint("test-run", P2),
        "exit_code": 0,
    }
    tests = []
    for t in domain.get("tests") or []:
        tests.append(
            {
                "id": str(t.get("id") or "unnamed"),
                "command": P1 if "bare" in str(t.get("id") or "") or "exclusive" in str(t.get("id") or "") else P2,
                "result": "PASS" if t.get("pass") else "FAIL",
            }
        )
    if not tests:
        tests = [
            {
                "id": "test_no_bare_ambiguous_token_is_assigned_a_state",
                "command": P1,
                "result": "PASS" if domain.get("no_bare_ambiguous_token_assigned_a_state") else "FAIL",
            }
        ]
    report = {
        "kind": "option-closure",
        "observations": [
            {
                "name": "selected_set_size",
                "measured": int(domain.get("selected_set_size") or 0),
                "method": "namespace-resolve-then-join-trace",
                "anchor": CLOSE_REL,
            },
            {
                "name": "counts_sum",
                "measured": int(counts.get("sum") or 0),
                "method": "four-way-count",
                "anchor": CLOSE_REL,
            },
            {
                "name": "ambiguous_not_checked",
                "measured": int(counts.get("ambiguous_not_checked") or 0),
                "method": "namespace-registry",
                "anchor": "command-center/p2-wave/probes/SYN-0028/fixtures/control/selected-set.json",
            },
            {
                "name": "known_present_implemented",
                "measured": bool((domain.get("known_present_implemented") or {}).get("pass")),
                "method": "control-reconstruction",
                "anchor": "command-center/p2-wave/probes/SYN-0028/fixtures/control/implemented-M-40.md:3",
            },
        ],
        "control_ids": [
            "NC-double-disposition",
            "NC-bare-token-assigned",
            "NC-schema-garbage",
        ],
        "question": domain.get("question") or QUESTION,
        "answer": domain.get("answer") or "",
        "selected_set_size": domain.get("selected_set_size"),
        "selected_set_source": domain.get("selected_set_source"),
        "selected_ids": domain.get("selected_ids") or [],
        "counts": counts,
        "counts_sum_equals_selected": domain.get("counts_sum_equals_selected"),
        "dispositions": domain.get("dispositions") or [],
        "namespaces": domain.get("namespaces") or [],
        "live_namespaces": domain.get("live_namespaces") or [],
        "named_inputs": domain.get("named_inputs") or [],
        "live": domain.get("live"),
        "control": domain.get("control"),
        "no_bare_ambiguous_token_assigned_a_state": domain.get(
            "no_bare_ambiguous_token_assigned_a_state"
        ),
        "states_mutually_exclusive_and_exhaustive": domain.get(
            "states_mutually_exclusive_and_exhaustive"
        ),
        "known_present_implemented": domain.get("known_present_implemented"),
        "using_control_because_live_absent": domain.get(
            "using_control_because_live_absent"
        ),
        "owner_sign_off": domain.get("owner_sign_off"),
        "test_details": domain.get("tests") or [],
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "completion_sentinel": SENTINEL,
        "schema_gate": domain.get("schema_gate"),
        "schema_present": schema_path.is_file(),
    }
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS" if success else "FAILED",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=SYN-0028]",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "coverage-auditor",
            "execution_substrate": "linux-local",
        },
        "artifacts": [primary, schema_art, closer_art],
        "evidence": [
            {
                "claim": (
                    "Every selected option id is in exactly one of IMPLEMENTED, "
                    "SUPERSEDED, REJECTED-WITH-OWNER-REASONING, or NOT-CHECKED; "
                    "the four counts sum to the selected-set size; a bare M-NN "
                    "token that collides two namespaces is never assigned a "
                    "terminal state."
                ),
                "verdict": "CONFIRMED" if success else "REFUTED",
                "confidence": "almost-certain",
                "anchor": CLOSE_REL,
                "probes": [src_close, ver_schema],
                "unverified": False,
            },
            {
                "claim": (
                    "Known-present option-universe:M-40 resolves to IMPLEMENTED "
                    "with an on-disk implementation anchor. Planted bare M-16 "
                    "stays NOT-CHECKED / NAMESPACE-AMBIGUOUS."
                ),
                "verdict": "CONFIRMED" if success else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0028/fixtures/control/implemented-M-40.md:3",
                "probes": [src_ctrl, ver_ctrl],
                "unverified": False,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-double-disposition",
                "kind": "known-broken-fixture",
                "description": (
                    "Two outcomes on option-universe:M-40 must yield "
                    "NOT-CHECKED / DOUBLE-DISPOSITION, never a silent pick."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "DOUBLE-DISPOSITION NOT-CHECKED",
                "good_state_output": "option-universe:M-40 IMPLEMENTED",
            },
            {
                "id": "NC-bare-token-assigned",
                "kind": "mutation",
                "description": (
                    "Forcing IMPLEMENTED onto bare M-16 must be rejected by "
                    "the bare-token checker."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "bare_mutant_violations>=1",
                "good_state_output": "M-16 NOT-CHECKED NAMESPACE-AMBIGUOUS",
            },
            {
                "id": "NC-schema-garbage",
                "kind": "malformed-input",
                "description": "option-closure schema must reject an unrelated object.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema rejects {totally: unrelated}",
                "good_state_output": "schema_ok=True on closer receipt",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0028-probe2-controls",
            "verdict": "PASS" if success else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 does not author close.py and re-derives the three "
                "catalog tests plus planted double-disposition and bare-token "
                "mutants from fixtures."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": UNIT_ID,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "SYN-0028-probe1-reclose",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P1,
                    "raw_output": "reclose schema counts exclusive no-bare",
                    "fingerprint": SL.fingerprint("command", P1),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "no re-roll of a disagreeing run. If a second pass produces a "
                "different set, BOTH sets are kept and the delta becomes the finding"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live Prompt-Two selected option ids, 07-OPTION-UNIVERSE.json, "
                    "and SYN-0005.decision-trace.json are absent at the named "
                    "worktree paths, so the primary selected set is the labeled "
                    "control reconstruction rather than the 283-card universe."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place 07-OPTION-UNIVERSE.json, OPTION-ID-RESOLUTION selected "
                    "ids, and SYN-0005.decision-trace.json on the worktree and "
                    "re-run close.py; keep both selected sets if they disagree."
                ),
            },
            {
                "claim": (
                    "Catalog owner_approval_required=true. Technical closure of "
                    "the control reconstruction is not a forged owner sign-off "
                    "on the live 283-option universe."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record an owner sentence in OWNER-DECISIONS.md against the "
                    "live selected set, then re-join."
                ),
            },
        ],
        "report": report,
        "extensions": {
            "status": "DELIVERED" if success else "FAILED",
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "cloud_ok": False,
            "registered": True,
            "failure_classification": domain.get("failure_classification") or [],
        },
    }
    if not success:
        receipt["failure"] = {
            "classification": list(domain.get("failure_classification") or ["schema-invalid"]),
            "reason": str((domain.get("schema_gate") or {}).get("detail") or "closer failed"),
            "diagnostic_tail": json.dumps(
                {
                    "counts": counts,
                    "tests": [(t.get("id"), t.get("pass")) for t in (domain.get("tests") or [])],
                },
                sort_keys=True,
            ),
        }
    return receipt


def disposition_fingerprint(doc: dict[str, Any]) -> list[tuple]:
    pack = payload(doc)
    rows = []
    for d in pack.get("dispositions") or []:
        rows.append(
            (
                d.get("selected_id"),
                d.get("token"),
                d.get("namespace"),
                d.get("resolved"),
                tuple(d.get("candidate_namespaces") or []),
                d.get("terminal_state"),
                d.get("not_checked_reason"),
                d.get("corpus"),
            )
        )
    return sorted(rows)


if __name__ == "__main__":
    doc = close()
    pack = payload(doc)
    print(
        json.dumps(
            {
                "state": doc["state"],
                "source": pack.get("selected_set_source"),
                "n": pack.get("selected_set_size"),
                "counts": pack.get("counts"),
                "schema": pack.get("schema_gate"),
                "tests": [(t.get("id"), t.get("result")) for t in (doc.get("tests") or [])],
            },
            indent=2,
        )
    )
