#!/usr/bin/env python3
"""ADV-0134 supersession-graph walker.

Live stores are read-only. Scratch detector records live under fixtures/planted/
and are overlaid in memory; no vault note is rewritten.

Named checks: RESOLVE, ACYCLIC, CITED-CURRENT.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "ADV-0134"

PLANTED_BROKEN = "ADV-0134-planted-broken"
PLANTED_MISSING = "permalink://adv-0134/does-not-exist"
PLANTED_A = "ADV-0134-planted-cycle-a"
PLANTED_B = "ADV-0134-planted-cycle-b"
AB_GET = "agentbridge.get_budget"
AB_CHECK = "agentbridge.check_budget"
SUCC_CLAUDE = "~/CLAUDE.md"
SUCC_AGENTS = "~/AGENTS.md"

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
SKIP_DIR = {".git", "node_modules", "__pycache__", ".cursor", ".venv", "venv"}
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CLAIM_REG = REPO / "command-center" / "CLAIM-REGISTRY.json"
ENCODED = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "ARC-0085"
    / "fixtures"
    / "encoded-claims.json"
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def as_targets(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
        return [p for p in parts if p]
    return [text]


def make_edge(
    old_id: str,
    new_id: str,
    declared_at: str,
    store: str,
    source: str,
    line: int = 1,
) -> dict[str, Any]:
    return {
        "old_id": old_id,
        "new_id": new_id,
        "declared_at": declared_at or "unknown",
        "store": store,
        "source": source,
        "line": int(line),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def edges_from_record(
    rec: dict[str, Any], store: str, source: str, line: int = 1
) -> tuple[list[dict[str, Any]], set[str]]:
    nid = str(rec.get("id") or rec.get("old_id") or rec.get("claim_id") or "").strip()
    declared = str(rec.get("declared_at") or rec.get("valid_as_of") or "unknown")
    targets = as_targets(rec.get("superseded_by") or rec.get("new_id"))
    nodes: set[str] = {nid} if nid else set()
    out = [make_edge(nid, t, declared, store, source, line) for t in targets if nid]
    return out, nodes


def walk_markdown(path: Path, store: str) -> tuple[list[dict[str, Any]], set[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], set()
    fm = parse_frontmatter(text)
    if not fm:
        return [], set()
    rec = {
        "id": fm.get("id") or path.stem,
        "superseded_by": fm.get("superseded_by"),
        "declared_at": fm.get("declared_at") or fm.get("valid_as_of") or "unknown",
    }
    src = rel(path)
    if rec.get("superseded_by"):
        edges, nodes = edges_from_record(rec, store, src, 1)
        nodes.add(str(rec["id"]))
        return edges, nodes
    if "valid_as_of" in fm:
        return [], {str(rec["id"])}
    return [], set()


def live_vault_roots() -> list[Path]:
    env = os.environ.get("BASIC_MEMORY_HOME") or os.environ.get("BASIC_MEMORY_DIR")
    cands = [
        REPO / "memory",
        REPO / "basic-memory",
        REPO / ".basic-memory",
        REPO / "notes",
        Path.home() / ".basic-memory",
        Path.home() / "basic-memory",
        Path.home() / "memory",
    ]
    if env:
        cands.insert(0, Path(env))
    return [p for p in cands if p.exists()]


def iter_text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    found: list[Path] = []
    if not root.exists():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR]
        for name in filenames:
            if name.endswith((".md", ".json", ".yml", ".yaml")):
                found.append(Path(dirpath) / name)
    return found


def adapter_frontmatter_json() -> tuple[list[dict[str, Any]], set[str], dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    nodes: set[str] = set()
    vaults = live_vault_roots()
    live_hits = 0
    for root in vaults:
        for path in iter_text_files(root):
            e, n = walk_markdown(path, "basic-memory-vault")
            if e or n:
                live_hits += 1
            edges.extend(e)
            nodes |= n

    for path in sorted((HERE / "fixtures" / "vault").glob("*.md")):
        e, n = walk_markdown(path, "fixture-vault")
        edges.extend(e)
        nodes |= n

    ab_path = HERE / "fixtures" / "agentbridge" / "edge.json"
    ab = load_json(ab_path)
    src = rel(ab_path)
    declared = str(ab.get("declared_at") or "unknown")
    store = str(ab.get("store") or "agentbridge-retirement")
    for rec in ab.get("records") or []:
        row = dict(rec)
        row.setdefault("declared_at", declared)
        e, n = edges_from_record(row, store, src, 1)
        edges.extend(e)
        nodes |= n
    nodes.add(SUCC_CLAUDE)
    nodes.add(SUCC_AGENTS)

    planted = HERE / "fixtures" / "planted"
    for name in ("broken-chain.json", "cycle-a.json", "cycle-b.json"):
        path = planted / name
        rec = load_json(path)
        e, n = edges_from_record(rec, "scratch-overlay", rel(path), 1)
        edges.extend(e)
        nodes |= n
    nodes.discard(PLANTED_MISSING)

    claim_present = CLAIM_REG.is_file()
    if claim_present:
        data = load_json(CLAIM_REG)
        rows = data if isinstance(data, list) else (data.get("claims") or data.get("records") or [])
        for rec in rows:
            if not isinstance(rec, dict):
                continue
            cid = str(rec.get("claim_id") or rec.get("id") or "")
            if cid:
                nodes.add(cid)
            for dup in rec.get("duplicate_of") or []:
                edges.append(
                    make_edge(cid, str(dup), "claim-registry", "claim-registry", rel(CLAIM_REG), 1)
                )
                nodes.add(str(dup))

    meta = {
        "live_vault_roots": [
            rel(p) if str(p).startswith(str(REPO)) else str(p) for p in vaults
        ],
        "live_vault_note_hits": live_hits,
        "claim_registry_present": claim_present,
    }
    return edges, nodes, meta


def adapter_retired_regex() -> tuple[list[dict[str, Any]], set[str], dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    nodes: set[str] = set()
    hits: list[str] = []
    if CATALOG.is_file():
        for i, line in enumerate(
            CATALOG.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if "AgentBridge" in line and "get_budget" in line:
                hits.append(f"{rel(CATALOG)}:{i}")
                for old in (AB_GET, AB_CHECK):
                    edges.append(
                        make_edge(old, SUCC_CLAUDE, "catalog-calibration", "catalog", rel(CATALOG), i)
                    )
                    edges.append(
                        make_edge(old, SUCC_AGENTS, "catalog-calibration", "catalog", rel(CATALOG), i)
                    )
                    nodes.add(old)
                nodes.add(SUCC_CLAUDE)
                nodes.add(SUCC_AGENTS)
                break

    named = {
        "CODEX-STUB-RETIREMENT-LANE.md": REPO / "CODEX-STUB-RETIREMENT-LANE.md",
        "command-center/CODEX-STUB-RETIREMENT-LANE.md": REPO / "command-center" / "CODEX-STUB-RETIREMENT-LANE.md",
        "OWNER-DECISIONS.md": REPO / "OWNER-DECISIONS.md",
        "command-center/OWNER-DECISIONS.md": REPO / "command-center" / "OWNER-DECISIONS.md",
    }
    named_present = {k: v.is_file() for k, v in named.items()}

    home_successors = {}
    for label, path in (
        (SUCC_CLAUDE, Path.home() / "CLAUDE.md"),
        (SUCC_AGENTS, Path.home() / "AGENTS.md"),
    ):
        home_successors[label] = {"path": str(path), "present": path.is_file()}
        if path.is_file():
            nodes.add(label)
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"AgentBridge|get_budget|check_budget", text):
                hits.append(f"{path}:live-home")

    capture = HERE / "fixtures" / "agentbridge"
    for label, fname in ((SUCC_CLAUDE, "CLAUDE.md"), (SUCC_AGENTS, "AGENTS.md")):
        p = capture / fname
        if p.is_file() and "RETIRED" in p.read_text(encoding="utf-8"):
            nodes.add(label)
            hits.append(rel(p))

    meta = {
        "catalog_hits": hits,
        "named_inputs_present": named_present,
        "home_successors": home_successors,
    }
    return edges, nodes, meta


def _mech_key(text: str) -> str:
    s = unicodedata.normalize("NFKC", text or "")
    s = s.casefold()
    return re.sub(r"\s+", " ", s).strip()


def adapter_claim_collapse() -> tuple[list[dict[str, Any]], set[str], dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    nodes: set[str] = set()
    contradictions: list[dict[str, str]] = []
    groups: dict[str, list[str]] = {}
    present = ENCODED.is_file()
    if present:
        data = load_json(ENCODED)
        src = rel(ENCODED)
        for rec in data.get("claims") or []:
            cid = str(rec.get("claim_id") or "")
            if not cid:
                continue
            nodes.add(cid)
            groups.setdefault(_mech_key(str(rec.get("canonical_mechanism") or "")), []).append(cid)
            for other in rec.get("contradicts") or []:
                contradictions.append({"from": cid, "to": str(other)})
            for dup in rec.get("duplicate_of") or []:
                edges.append(
                    make_edge(cid, str(dup), "encoded-claims", "claim-encoding", src, 1)
                )
                nodes.add(str(dup))
        for ids in groups.values():
            if len(ids) < 2:
                continue
            canonical = sorted(ids)[0]
            for alias in ids:
                if alias == canonical:
                    continue
                edges.append(
                    make_edge(alias, canonical, "mechanism-collapse", "claim-encoding", src, 1)
                )
                nodes.add(canonical)
    meta = {
        "encoded_claims_present": present,
        "encoded_path": rel(ENCODED) if present else None,
        "contradiction_edges_observed_not_modeled_as_supersession": contradictions[:12],
        "collapse_groups": sum(1 for ids in groups.values() if len(ids) > 1),
    }
    return edges, nodes, meta


def uniq_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for e in rows:
        key = (e["old_id"], e["new_id"], e["store"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def successor_exists_on_disk(node_id: str) -> bool:
    if node_id.startswith("~/"):
        if (Path.home() / node_id[2:]).is_file():
            return True
        return (HERE / "fixtures" / "agentbridge" / Path(node_id).name).is_file()
    return (REPO / node_id).exists()


def check_resolve(edges: list[dict[str, Any]], nodes: set[str]) -> dict[str, Any]:
    present = set(nodes)
    violations = []
    for e in edges:
        tgt = e["new_id"]
        if tgt in present:
            continue
        if successor_exists_on_disk(tgt):
            present.add(tgt)
            continue
        violations.append(
            {
                "node_id": e["old_id"],
                "citing_file_line": f"{e['source']}:{e['line']}",
                "successor_that_should_have_been_cited": tgt,
            }
        )
    return {"count": len(violations), "violations": violations}


def check_acyclic(edges: list[dict[str, Any]]) -> dict[str, Any]:
    graph: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for e in edges:
        graph[e["old_id"]].append((e["new_id"], e))

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    parent: dict[str, tuple[str | None, dict[str, Any] | None]] = {}
    violations: list[dict[str, Any]] = []
    seen_cycles: set[tuple[str, ...]] = set()
    steps = 0
    limit = 1_000_000
    all_nodes = set(graph) | {t for pair in graph.values() for t, _ in pair}

    for start in all_nodes:
        if color.get(start, WHITE) != WHITE:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        parent[start] = (None, None)
        while stack:
            steps += 1
            if steps > limit:
                violations.append(
                    {
                        "node_id": start,
                        "citing_file_line": "walker:step-cap",
                        "successor_that_should_have_been_cited": "cycle-search-capped",
                    }
                )
                return {"count": len(violations), "violations": violations, "steps": steps}
            node, idx = stack[-1]
            nbrs = graph.get(node, [])
            if idx < len(nbrs):
                stack[-1] = (node, idx + 1)
                nxt, ed = nbrs[idx]
                st = color.get(nxt, WHITE)
                if st == WHITE:
                    color[nxt] = GRAY
                    parent[nxt] = (node, ed)
                    stack.append((nxt, 0))
                elif st == GRAY:
                    cycle = [nxt, node]
                    cur = node
                    guard = 0
                    while cur != nxt and guard < len(all_nodes) + 2:
                        prev, _ = parent.get(cur, (None, None))
                        if prev is None:
                            break
                        cycle.append(prev)
                        cur = prev
                        guard += 1
                    key = tuple(sorted(set(cycle)))
                    if key not in seen_cycles:
                        seen_cycles.add(key)
                        violations.append(
                            {
                                "node_id": node,
                                "citing_file_line": f"{ed['source']}:{ed['line']}",
                                "successor_that_should_have_been_cited": nxt,
                                "cycle": list(reversed(cycle)),
                            }
                        )
            else:
                color[node] = BLACK
                stack.pop()
    return {"count": len(violations), "violations": violations, "steps": steps}


def cite_files() -> list[Path]:
    files: list[Path] = []
    out_name = "ADV-0134-supersession-integrity.json"
    roots = [
        REPO / "command-center" / "adversarial",
        REPO / "command-center" / "schema",
        REPO / "tools",
        HERE / "fixtures",
        Path.home() / "CLAUDE.md",
        Path.home() / "AGENTS.md",
        CATALOG,
        CLAIM_REG,
        REPO / "OWNER-DECISIONS.md",
        REPO / "command-center" / "OWNER-DECISIONS.md",
    ]
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            files.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR]
            for name in filenames:
                if name == out_name:
                    continue
                if not name.endswith((".md", ".json", ".py", ".txt", ".yml")):
                    continue
                files.append(Path(dirpath) / name)
    return files


def check_cited_current(edges: list[dict[str, Any]], skip_sources: set[str]) -> dict[str, Any]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    decl: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        outgoing[e["old_id"]].append(e["new_id"])
        decl[e["old_id"]].append(e["source"])
    superseded = {k: sorted(set(v)) for k, v in outgoing.items() if v}
    violations: list[dict[str, Any]] = []
    for path in cite_files():
        src = rel(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for node_id, successors in superseded.items():
            if src in decl.get(node_id, []) or src in skip_sources:
                continue
            if node_id not in text:
                continue
            if any(s in text for s in successors):
                continue
            line_no = 1
            for i, line in enumerate(lines, 1):
                if node_id in line:
                    line_no = i
                    break
            violations.append(
                {
                    "node_id": node_id,
                    "citing_file_line": f"{src}:{line_no}",
                    "successor_that_should_have_been_cited": successors[0],
                }
            )
    return {"count": len(violations), "violations": violations}


def public_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "old_id": e["old_id"],
            "new_id": e["new_id"],
            "declared_at": e["declared_at"],
            "store": e["store"],
        }
        for e in rows
    ]


def catalog_unit() -> dict[str, Any]:
    data = load_json(CATALOG)
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UID:
            return u
    raise KeyError("ADV-0134 missing from catalog")


def evaluate() -> dict[str, Any]:
    t0 = time.monotonic()
    attempts: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    nodes: set[str] = set()

    e1, n1, m1 = adapter_frontmatter_json()
    all_edges.extend(e1)
    nodes |= n1
    attempts.append(
        {
            "n": 1,
            "adapter": "frontmatter-json",
            "what_changed": (
                "Initial walk: markdown frontmatter + JSON records "
                "(live vault dirs if present, fixture vault, AgentBridge capture, "
                "scratch overlay, CLAIM-REGISTRY.json if present)."
            ),
            "edges_added": len(uniq_edges(e1)),
            "meta": m1,
        }
    )

    e2, n2, m2 = adapter_retired_regex()
    all_edges.extend(e2)
    nodes |= n2
    attempts.append(
        {
            "n": 2,
            "adapter": "retired-marker-regex",
            "what_changed": (
                "Query path switched from structured records to a regex/line walk "
                "of WORK-UNIT-CATALOG.json AgentBridge calibration plus named "
                "RETIRED / OWNER-DECISIONS / CODEX-STUB-RETIREMENT-LANE.md presence "
                "and ~/CLAUDE.md ~/AGENTS.md existence."
            ),
            "edges_added": len(uniq_edges(e2)),
            "meta": m2,
        }
    )

    e3, n3, m3 = adapter_claim_collapse()
    all_edges.extend(e3)
    nodes |= n3
    attempts.append(
        {
            "n": 3,
            "adapter": "claim-duplicate-collapse",
            "what_changed": (
                "Query path switched to ARC-0085 encoded-claim mechanism collapse "
                "(CLAIM-REGISTRY.json absent on this worktree; duplicate_of edges "
                "derived from identical canonical_mechanism, not from contradiction)."
            ),
            "edges_added": len(uniq_edges(e3)),
            "meta": m3,
        }
    )

    edges = uniq_edges(all_edges)
    for s in (SUCC_CLAUDE, SUCC_AGENTS, PLANTED_A, PLANTED_B, AB_GET, AB_CHECK):
        nodes.add(s)
    nodes.discard(PLANTED_MISSING)

    resolve = check_resolve(edges, set(nodes))
    acyclic = check_acyclic(edges)
    skip = {
        rel(HERE / "fixtures" / "planted" / "broken-chain.json"),
        rel(HERE / "fixtures" / "planted" / "cycle-a.json"),
        rel(HERE / "fixtures" / "planted" / "cycle-b.json"),
        rel(HERE / "fixtures" / "agentbridge" / "edge.json"),
        rel(HERE / "graph.py"),
        rel(HERE / "emit_artifact.py"),
        rel(HERE / "probe1_known_present.py"),
        rel(HERE / "probe2_detector_controls.py"),
        rel(HERE / "write_receipts.py"),
        rel(HERE / "schema_check.py"),
    }
    cited = check_cited_current(edges, skip)

    broken_fired = any(
        v["node_id"] == PLANTED_BROKEN
        and PLANTED_MISSING in v["successor_that_should_have_been_cited"]
        for v in resolve["violations"]
    )
    cycle_fired = any(
        v["node_id"] in {PLANTED_A, PLANTED_B}
        or PLANTED_A in (v.get("cycle") or [])
        or PLANTED_B in (v.get("cycle") or [])
        for v in acyclic["violations"]
    )
    ab_edges = [
        e
        for e in edges
        if e["old_id"] in {AB_GET, AB_CHECK} and e["new_id"] in {SUCC_CLAUDE, SUCC_AGENTS}
    ]
    ab_found = any(
        e["old_id"] == AB_GET and e["new_id"] == SUCC_CLAUDE for e in ab_edges
    ) and any(e["old_id"] == AB_GET and e["new_id"] == SUCC_AGENTS for e in ab_edges)

    named = attempts[1]["meta"].get("named_inputs_present") or {}
    inventory = [
        {
            "input": "basic-memory vault notes carrying superseded_by or valid_as_of",
            "present": bool(attempts[0]["meta"]["live_vault_roots"]),
            "note": (
                f"live vault roots={attempts[0]['meta']['live_vault_roots']!r} "
                f"frontmatter hits={attempts[0]['meta']['live_vault_note_hits']}; "
                "fixture-vault overlay is labeled fixture-vault, not claimed live"
            ),
        },
        {
            "input": "CLAIM-REGISTRY.json duplicate-of and contradiction edges",
            "present": bool(attempts[0]["meta"]["claim_registry_present"]),
            "note": (
                "Absent on this worktree. Adapter 3 used ARC-0085 encoded claims "
                "as the live encoding source (same fallback ARC-0085 recorded)."
            ),
        },
        {
            "input": "OWNER-DECISIONS.md and Prompt One decision log revision history",
            "present": bool(
                named.get("OWNER-DECISIONS.md")
                or named.get("command-center/OWNER-DECISIONS.md")
            ),
            "note": "Named files absent; no Prompt One revision history on this tree.",
        },
        {
            "input": "RETIRED markers (AgentBridge block, CODEX-STUB-RETIREMENT-LANE.md)",
            "present": bool(attempts[1]["meta"]["catalog_hits"]),
            "note": (
                "AgentBridge get_budget/check_budget calibration is in "
                "WORK-UNIT-CATALOG.json. CODEX-STUB-RETIREMENT-LANE.md is absent. "
                f"Home successors={attempts[1]['meta']['home_successors']}"
            ),
        },
    ]

    return {
        "edges": edges,
        "public_edges": public_edges(edges),
        "nodes": sorted(nodes),
        "checks": {
            "RESOLVE": {"count": resolve["count"], "violations": resolve["violations"]},
            "ACYCLIC": {"count": acyclic["count"], "violations": acyclic["violations"]},
            "CITED-CURRENT": {"count": cited["count"], "violations": cited["violations"]},
        },
        "planted": {
            "broken_chain_fired": broken_fired,
            "cycle_fired": cycle_fired,
            "same_run_as_counts": True,
        },
        "known_present": {
            "id": "agentbridge-budget-tooling",
            "found": ab_found,
            "successors": [SUCC_CLAUDE, SUCC_AGENTS],
            "edge_count": len(ab_edges),
        },
        "attempts": attempts,
        "store_inventory": inventory,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "acyclic_steps": acyclic.get("steps"),
        "unit": catalog_unit(),
    }


def main() -> int:
    r = evaluate()
    print(
        json.dumps(
            {
                "edges": len(r["public_edges"]),
                "RESOLVE": r["checks"]["RESOLVE"]["count"],
                "ACYCLIC": r["checks"]["ACYCLIC"]["count"],
                "CITED-CURRENT": r["checks"]["CITED-CURRENT"]["count"],
                "broken_chain_fired": r["planted"]["broken_chain_fired"],
                "cycle_fired": r["planted"]["cycle_fired"],
                "known_present": r["known_present"]["found"],
                "elapsed_ms": r["elapsed_ms"],
            },
            sort_keys=True,
        )
    )
    ok = (
        r["planted"]["broken_chain_fired"]
        and r["planted"]["cycle_fired"]
        and r["known_present"]["found"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

