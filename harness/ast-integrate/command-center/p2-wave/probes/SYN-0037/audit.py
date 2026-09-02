"""Reviewer-independence audit: self-review, review-chain cycles, missing fields.

A receipt missing author_id or reviewer_id is a VIOLATION, never a skip.
Independence is measured from ledger fields, not from prompt prose.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

def _repo_root() -> Path:
    cur = Path(__file__).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return parent
    raise RuntimeError("cannot locate worktree root from SYN-0037/audit.py")


REPO = _repo_root()
RECEIPTS_DIR = REPO / "command-center" / "receipts"
EVENTS_PATH = REPO / "command-center" / "events" / "EVENTS.jsonl"
CATALOG_PATH = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SELF_UNIT = "SYN-0037"

MISSING_AUTHOR = "missing-author-field"
MISSING_REVIEWER = "missing-reviewer-field"
MISSING_BOTH = "missing-author-and-reviewer-fields"
SELF_REVIEW = "self-review"
CIRCULAR = "circular-review"
SKIPPED = "missing-reviewer-field-skipped"


def _norm(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def identity_from_mapping(obj: Any) -> str | None:
    """Stable agent id from vendor|model|role (or an explicit id field)."""
    if not isinstance(obj, dict):
        return None
    for key in ("author_id", "agent_id"):
        got = _norm(obj.get(key))
        if got:
            return got
    parts: list[str] = []
    for key in ("vendor", "model", "role"):
        got = _norm(obj.get(key))
        if got:
            parts.append(got)
    if parts:
        return "|".join(parts)
    return None


def extract_author_id(doc: dict) -> str | None:
    got = _norm(doc.get("author_id"))
    if got:
        return got
    author = doc.get("author")
    if isinstance(author, str):
        return _norm(author)
    if isinstance(author, dict):
        ident = identity_from_mapping(author)
        if ident:
            return ident
    produced = doc.get("produced_by")
    if isinstance(produced, dict):
        return identity_from_mapping(produced)
    return None


def extract_reviewer_id(doc: dict) -> str | None:
    got = _norm(doc.get("reviewer_id"))
    if got:
        return got
    reviewer = doc.get("reviewer")
    if isinstance(reviewer, str):
        return _norm(reviewer)
    if isinstance(reviewer, dict):
        for key in ("reviewer_id", "agent_id"):
            ident = _norm(reviewer.get(key))
            if ident:
                return ident
        return identity_from_mapping(reviewer)
    return None


def missing_classification(author_id: str | None, reviewer_id: str | None) -> str | None:
    if author_id is None and reviewer_id is None:
        return MISSING_BOTH
    if author_id is None:
        return MISSING_AUTHOR
    if reviewer_id is None:
        return MISSING_REVIEWER
    return None


def _canonicalize_cycle(nodes: list[str]) -> tuple[str, ...]:
    if not nodes:
        return tuple()
    i = nodes.index(min(nodes))
    return tuple(nodes[i:] + nodes[:i])


def directed_cycles(edges: Iterable[tuple[str, str]]) -> list[dict]:
    """Simple directed cycles of length >= 2 (self-loops are self-review, not here)."""
    adj: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    seen_e: set[tuple[str, str]] = set()
    for src, dst in edges:
        if not src or not dst or src == dst:
            continue
        key = (src, dst)
        if key in seen_e:
            continue
        seen_e.add(key)
        adj[src].append(dst)
        nodes.add(src)
        nodes.add(dst)

    found: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str], instack: set[str]) -> None:
        instack.add(node)
        path.append(node)
        for nxt in adj.get(node, []):
            if nxt in instack:
                start = path.index(nxt)
                cyc = path[start:]
                if len(cyc) >= 2:
                    found.add(_canonicalize_cycle(cyc))
            else:
                dfs(nxt, path, instack)
        path.pop()
        instack.remove(node)

    for n in sorted(nodes):
        dfs(n, [], set())

    out = []
    for cyc in sorted(found, key=lambda t: (len(t), t)):
        out.append({"nodes": list(cyc), "length": len(cyc)})
    return out


def kahn_cyclic(edges: Iterable[tuple[str, str]]) -> bool:
    """Independent cycle check: leftover nodes after Kahn topo-sort => cyclic."""
    adj: dict[str, set[str]] = defaultdict(set)
    indeg: dict[str, int] = defaultdict(int)
    nodes: set[str] = set()
    for src, dst in edges:
        if not src or not dst or src == dst:
            continue
        if dst in adj[src]:
            continue
        adj[src].add(dst)
        indeg[dst] += 1
        nodes.add(src)
        nodes.add(dst)
        indeg.setdefault(src, indeg[src])
    queue = [n for n in sorted(nodes) if indeg[n] == 0]
    seen = 0
    while queue:
        n = queue.pop(0)
        seen += 1
        for nxt in sorted(adj[n]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return seen != len(nodes)


def audit_records(
    records: list[dict],
    *,
    missing_is_violation: bool = True,
) -> dict:
    """Audit a list of {path, doc} records.

    missing_is_violation=False is the skip mutant: receipts without reviewer_id
    are dropped. That mutant is the failure class missing-reviewer-field-skipped.
    """
    self_reviews: list[dict] = []
    missing: list[dict] = []
    skipped: list[dict] = []
    edges: list[dict] = []
    chain_edges: list[tuple[str, str]] = []
    authors: set[str] = set()
    reviewers: set[str] = set()

    for rec in records:
        path = str(rec.get("path") or rec.get("id") or "")
        doc = rec.get("doc")
        if not isinstance(doc, dict):
            missing.append(
                {
                    "path": path,
                    "missing_fields": ["author_id", "reviewer_id"],
                    "classification": MISSING_BOTH,
                }
            )
            continue
        author_id = extract_author_id(doc)
        reviewer_id = extract_reviewer_id(doc)
        miss = missing_classification(author_id, reviewer_id)
        if miss:
            if not missing_is_violation and reviewer_id is None:
                skipped.append({"path": path, "classification": SKIPPED})
                continue
            fields = []
            if author_id is None:
                fields.append("author_id")
            if reviewer_id is None:
                fields.append("reviewer_id")
            missing.append(
                {
                    "path": path,
                    "missing_fields": fields,
                    "classification": miss,
                }
            )
            continue
        assert author_id is not None and reviewer_id is not None
        authors.add(author_id)
        reviewers.add(reviewer_id)
        if author_id == reviewer_id:
            self_reviews.append(
                {
                    "path": path,
                    "agent_id": author_id,
                    "classification": SELF_REVIEW,
                }
            )
            continue
        edges.append(
            {
                "author_id": author_id,
                "reviewer_id": reviewer_id,
                "path": path,
            }
        )
        chain_edges.append((reviewer_id, author_id))

    cycles = directed_cycles(chain_edges)
    intersection = sorted(authors & reviewers)
    return {
        "receipt_count": len(records),
        "author_partition": sorted(authors),
        "reviewer_partition": sorted(reviewers),
        "author_reviewer_intersection": intersection,
        "self_reviews": self_reviews,
        "missing_field_receipts": missing,
        "missing_field_count": len(missing),
        "skipped_missing_reviewer": skipped,
        "skipped_count": len(skipped),
        "bipartite_edges": edges,
        "chain_edges": [{"from": a, "to": b} for a, b in chain_edges],
        "cycles": cycles,
        "acyclic": len(cycles) == 0,
        "kahn_cyclic": kahn_cyclic(chain_edges),
        "classifications": sorted(
            ({SELF_REVIEW} if self_reviews else set())
            | ({CIRCULAR} if cycles else set())
            | {m["classification"] for m in missing}
        ),
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_receipt_paths(root: Path | None = None) -> list[Path]:
    base = root or RECEIPTS_DIR
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob("*.json") if p.is_file())


def load_receipt_records(
    root: Path | None = None,
    *,
    exclude_unit_ids: Iterable[str] = (),
) -> list[dict]:
    skip = {s.strip() for s in exclude_unit_ids if s}
    records: list[dict] = []
    for path in iter_receipt_paths(root):
        rel = path.relative_to(REPO).as_posix()
        try:
            doc = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            records.append({"path": rel, "doc": None, "unit_id": path.stem})
            continue
        if not isinstance(doc, dict):
            records.append({"path": rel, "doc": None, "unit_id": path.stem})
            continue
        uid = str(doc.get("unit_id") or doc.get("id") or path.stem)
        if uid in skip:
            continue
        records.append({"path": rel, "doc": doc, "unit_id": uid})
    return records


def load_dispatch_records(path: Path | None = None) -> dict:
    target = path or EVENTS_PATH
    if not target.is_file():
        return {
            "present": False,
            "path": target.relative_to(REPO).as_posix() if REPO in target.parents else str(target),
            "dispatch_count": 0,
            "records": [],
        }
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("event") == "dispatch":
            rows.append(rec)
    return {
        "present": True,
        "path": target.relative_to(REPO).as_posix(),
        "dispatch_count": len(rows),
        "records": rows[:50],
    }


def catalog_reviewer_requirements(path: Path | None = None) -> dict:
    target = path or CATALOG_PATH
    if not target.is_file():
        return {"present": False, "units_with_reviewer_requirement": 0}
    data = load_json(target)
    units = data.get("work_units") if isinstance(data, dict) else []
    n = 0
    nonempty = 0
    by_id: dict[str, str] = {}
    for u in units or []:
        if not isinstance(u, dict):
            continue
        uid = u.get("id")
        req = u.get("reviewer_requirement")
        if isinstance(uid, str):
            n += 1
            if isinstance(req, str) and req.strip():
                nonempty += 1
                by_id[uid] = req.strip()
    return {
        "present": True,
        "path": target.relative_to(REPO).as_posix(),
        "units_total": n,
        "units_with_reviewer_requirement": nonempty,
        "sample": {k: by_id[k] for k in list(by_id)[:3]},
    }


def audit_live(*, exclude_self: bool = True) -> dict:
    skip = (SELF_UNIT,) if exclude_self else ()
    records = load_receipt_records(exclude_unit_ids=skip)
    result = audit_records(records, missing_is_violation=True)
    result["events"] = load_dispatch_records()
    result["catalog"] = catalog_reviewer_requirements()
    result["excluded_unit_ids"] = list(skip)
    return result


def published_payload(doc: dict) -> dict:
    """Independence-audit body: report.kind pin, else legacy top-level fields."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "independence-audit"
        or "missing_field_count" in report
        or "planted_violations" in report
    ):
        return report
    return doc


def as_public_graph(result: dict) -> tuple[dict, dict]:
    bipartite = {
        "author_partition": result["author_partition"],
        "reviewer_partition": result["reviewer_partition"],
        "edges": result["bipartite_edges"],
    }
    chain = {
        "nodes": sorted(
            set(result["author_partition"]) | set(result["reviewer_partition"])
        ),
        "edges": result["chain_edges"],
        "acyclic": result["acyclic"],
    }
    return bipartite, chain
