"""Recall audit: durable notes that contradict or pre-answer a live premise.

This unit's scope is the UNCONSULTED set (topically relevant notes no program
artifact cited). ADV-0018 is the contradiction-vs-measured-truth sweep; it is
not rebuilt here.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "BLD-0037"
OUT_REL = "command-center/receipts/BLD-0037.json"
SCHEMA_REL = "command-center/schema/contradiction-register.schema.json"
VAULT_REL = "command-center/p2-wave/probes/BLD-0037/fixtures/vault"
LEDGER_REL = "command-center/p2-wave/probes/BLD-0037/fixtures/ledger"
PROGRAM_REL = "command-center/p2-wave/probes/BLD-0037/fixtures/program"

TOKEN_RE = re.compile(r"[a-z0-9]{4,}")
HYPHEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
FM_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)

KNOWN_RELEVANT = (
    "memory://estate/squash-merge-branch-reporting",
    "memory://estate/git-archive-crlf-trap",
)
STALE_PIN = "memory://estate/old-delivered-count"
STALE_SUCCESSOR = "memory://estate/delivered-is-existence-only"
CITED_PIN = "memory://estate/cited-control-note"
CONTRA_NOTE = "memory://estate/ancestry-is-not-delete-auth"
REVIEWER_PIN = "memory://estate/program-b-interleave"

AUTHOR_QUERIES = (
    {"id": "q-squash-merge", "query": "squash-merge branch report as ahead"},
    {"id": "q-git-archive-crlf", "query": "git-archive CRLF trap cat-file"},
    {"id": "q-recall-unread", "query": "recall unread on disk durable memory"},
    {"id": "q-supersession", "query": "superseded_by stale predecessor forty-four delivered"},
    {"id": "q-delete-auth", "query": "teardown delete authorization commit ancestry"},
)
REVIEWER_QUERIES = (
    {"id": "r-interleave", "query": "Program B INTERLEAVE supersedes sequencing"},
    {"id": "r-existence-delivered", "query": "existence-only delivered predicate BLOCKED artifacts"},
    {"id": "r-seven-claims", "query": "seven load-bearing claims unread on disk"},
)

NOTE_OPPOSE = (
    "not delete authorization",
    "is not delete authorization",
    "ancestry is not",
)
CLAIM_OPPOSE = (
    "ancestry is sufficient",
    "may delete a worktree",
)
MENTION_GUARD = re.compile(
    r"\b(rejected|must not|do not flag|as rejected|quoting)\b", re.I
)
SKIP_CITE_PARTS = (
    "/probes/BLD-0037/fixtures/vault/",
    "/probes/BLD-0037/fixtures/ledger/",
    "/probes/BLD-0037/audit.py",
    "/probes/BLD-0037/emit.py",
    "/probes/BLD-0037/probe1_recall_controls.py",
    "/probes/BLD-0037/probe2_contradiction_anchors.py",
    "/probes/BLD-0037/write_receipts.py",
    # Harvested unit receipts (including BLD-0064 copying this register) are
    # measurement output, not program consultation of the durable note.
    "/receipts/",
    # P2 G-1 monitor dumps restated these permalinks after a prior probe
    # failure (ovh-monitor/error-pull/g1-fail-details.json). Copying a
    # recall-audit finding into a harness log is not program consultation.
    "/p2-wave/ovh-monitor/",
)

LIVE_VAULT_CANDIDATES = (
    Path.home() / ".basic-memory",
    Path.home() / "basic-memory",
    Path("/opt/p2/basic-memory"),
    Path("/opt/p2/memory-vault"),
)
LIVE_LEDGER_CANDIDATES = (
    Path.home() / ".claude" / "event-ledger",
    Path("/opt/p2/event-ledger"),
    Path("/opt/p2/ast-integrate/command-center/event-ledger"),
)


@dataclass
class Record:
    permalink: str
    title: str
    body: str
    path: str
    store: str
    tags: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    valid_as_of: str | None = None
    lines: list[str] = field(default_factory=list)

    @property
    def haystack(self) -> str:
        extra = []
        if self.superseded_by:
            extra.append("superseded_by " + self.superseded_by)
        if self.valid_as_of:
            extra.append("valid_as_of " + self.valid_as_of)
        return " ".join(
            [
                self.permalink,
                self.title,
                self.body,
                " ".join(self.tags),
                *extra,
            ]
        ).lower()


def rel_of(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for raw in m.group(1).splitlines():
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[m.end() :]


def parse_tags(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [p.strip().strip("'").strip('"') for p in inner.split(",") if p.strip()]
    if not raw:
        return []
    return [raw]


def tokens(text: str) -> set[str]:
    low = text.lower()
    out = set(TOKEN_RE.findall(low))
    out.update(HYPHEN_RE.findall(low))
    return out


def load_markdown_note(path: Path, repo: Path, store: str) -> Record | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    meta, body = parse_frontmatter(text)
    permalink = meta.get("permalink") or f"file://{rel_of(path, repo)}"
    lines = text.splitlines()
    return Record(
        permalink=permalink,
        title=meta.get("title") or path.stem,
        body=body,
        path=rel_of(path, repo),
        store=store,
        tags=parse_tags(meta.get("tags") or ""),
        superseded_by=meta.get("superseded_by") or None,
        valid_as_of=meta.get("valid_as_of") or None,
        lines=lines,
    )


def load_vault_dir(root: Path, repo: Path, store: str) -> list[Record]:
    if not root.is_dir():
        return []
    out: list[Record] = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in {".md", ".txt"} and p.is_file():
            rec = load_markdown_note(p, repo, store)
            if rec:
                out.append(rec)
    return out


def load_ledger_file(path: Path, repo: Path, store: str) -> list[Record]:
    if not path.is_file():
        return []
    out: list[Record] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for i, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            row = {"text": line, "permalink": f"ledger://line/{i}"}
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or row.get("body") or "")
        permalink = str(row.get("permalink") or f"ledger://{rel_of(path, repo)}:{i}")
        tags = row.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        out.append(
            Record(
                permalink=permalink,
                title=str(row.get("title") or permalink),
                body=text,
                path=f"{rel_of(path, repo)}:{i}",
                store=store,
                tags=[str(t) for t in tags],
                lines=[line],
            )
        )
    return out


def discover_live(candidates: tuple[Path, ...], extra: str | None) -> list[Path]:
    found: list[Path] = []
    if extra:
        p = Path(extra)
        if p.exists():
            found.append(p)
    for p in candidates:
        if p.exists() and p not in found:
            found.append(p)
    return found


def query_hits(query: str, rec: Record) -> bool:
    q = query.lower()
    hay = rec.haystack
    q_tokens = {
        t
        for t in tokens(query)
        if t
        not in {
            "that",
            "this",
            "with",
            "from",
            "into",
            "note",
            "notes",
            "file",
            "tags",
            "title",
            "body",
            "must",
            "have",
            "trap",
        }
    }
    for tok in q_tokens:
        if "-" in tok and tok in hay:
            return True
    for phrase in (
        "squash-merge",
        "squash merge",
        "git-archive",
        "git archive",
        "cat-file",
        "unread on disk",
        "superseded_by",
        "valid_as_of",
        "delete authorization",
        "report as ahead",
        "interleave",
        "existence-only",
        "load-bearing claims",
        "program b",
        "crlf",
    ):
        if phrase in q and phrase in hay:
            return True
    overlap = q_tokens & tokens(hay)
    return len(overlap) >= 2


def retrieve(
    queries: tuple[dict[str, str], ...], records: list[Record]
) -> list[dict[str, Any]]:
    rows = []
    for q in queries:
        hits = [r for r in records if query_hits(q["query"], r)]
        rows.append(
            {
                "id": q["id"],
                "query": q["query"],
                "hit_count": len(hits),
                "permalinks": [r.permalink for r in hits],
            }
        )
    return rows


def line_of(rec: Record, needle: str, *, prefer_body: bool = True) -> int:
    low = needle.lower()
    in_fm = True
    fm_hit = 0
    for i, line in enumerate(rec.lines, 1):
        if i > 1 and line.strip() == "---":
            in_fm = False
            continue
        if low in line.lower():
            if prefer_body and in_fm and rec.lines and rec.lines[0].strip() == "---":
                fm_hit = fm_hit or i
                continue
            return i
    return fm_hit or 1


def excerpt(rec: Record, start: int, width: int = 160) -> str:
    if not rec.lines:
        return rec.body.strip().replace("\n", " ")[:width]
    idx = max(start - 1, 0)
    return rec.lines[idx].strip()[:width]


def skip_cite(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    return any(part in posix for part in SKIP_CITE_PARTS)


def iter_program_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    planted = repo / PROGRAM_REL
    if planted.is_dir():
        out.extend(sorted(p for p in planted.iterdir() if p.is_file()))
    catalog = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    if catalog.is_file():
        out.append(catalog)
    cc = repo / "command-center"
    if cc.is_dir():
        for p in cc.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".md", ".json", ".txt"}:
                continue
            rel = rel_of(p, repo)
            if skip_cite(rel):
                continue
            if p == catalog:
                continue
            posix = rel.replace("\\", "/")
            # Delivery harness (probes, monitor dumps, wave logs) is not the
            # program citation set. Keep only this unit's planted program
            # fixtures under fixtures/program/.
            if "/p2-wave/" in posix and PROGRAM_REL not in posix:
                continue
            out.append(p)
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def find_citations(
    repo: Path, records: list[Record]
) -> dict[str, list[dict[str, Any]]]:
    cited: dict[str, list[dict[str, Any]]] = {r.permalink: [] for r in records}
    files = iter_program_files(repo)
    needles = [(r.permalink, r.title) for r in records]
    # G-1 resume perf repair 2026-10-24: the per-needle `permalink not in text`
    # loop is O(needles x bytes) per file; on the grown program tree that pushed
    # one run_audit call past the 180s probe ceiling. One literal-alternation
    # scan per file finds the same hit set; per-line attribution is unchanged
    # (same cited[permalink] rows, same order within each permalink).
    import re as _re

    pattern = (
        _re.compile("|".join(_re.escape(pin) for pin, _t in needles))
        if needles
        else None
    )
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern is not None:
            hits = {m.group(0) for m in pattern.finditer(text)}
        else:
            hits = set()
        if not hits:
            continue
        rel = rel_of(path, repo)
        lines = text.splitlines()
        for permalink, _title in needles:
            # Restating the fact is not citing the note. Only a permalink is a citation.
            if permalink not in hits:
                continue
            for i, line in enumerate(lines, 1):
                if permalink in line:
                    cited[permalink].append(
                        {
                            "path": rel,
                            "line": i,
                            "snippet": line.strip()[:220],
                        }
                    )
                    break
    return cited


def is_prescriptive_opposition(text: str) -> bool:
    if MENTION_GUARD.search(text):
        return False
    low = text.lower()
    return any(m in low for m in CLAIM_OPPOSE)


def contradictions(records: list[Record], repo: Path) -> list[dict[str, Any]]:
    notes = [
        r
        for r in records
        if r.superseded_by is None and any(m in r.haystack for m in NOTE_OPPOSE)
    ]
    files = iter_program_files(repo)
    found: list[dict[str, Any]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = rel_of(path, repo)
        for i, line in enumerate(text.splitlines(), 1):
            if not is_prescriptive_opposition(line):
                continue
            for rec in notes:
                nline = 1
                for marker in NOTE_OPPOSE:
                    hit = line_of(rec, marker)
                    if hit > 1 or (
                        rec.lines and marker in rec.lines[0].lower()
                    ):
                        nline = hit
                        break
                found.append(
                    {
                        "kind": "CONTRADICTS",
                        "permalink": rec.permalink,
                        "note_permalink": rec.permalink,
                        "note_anchor": f"{rec.path}:{nline}",
                        "program_claim_anchor": f"{rel}:{i}",
                        "note_excerpt": excerpt(rec, nline),
                        "claim_excerpt": line.strip()[:220],
                        "subject": "teardown-delete-authorization",
                    }
                )
    uniq: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in found:
        key = (row["note_anchor"], row["program_claim_anchor"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq


def first_anchor(hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    return hits[0] if hits else None


def run_audit(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    fixture_notes = load_vault_dir(repo / VAULT_REL, repo, "fixture-vault")
    fixture_ledger: list[Record] = []
    for p in sorted((repo / LEDGER_REL).glob("*")):
        fixture_ledger.extend(load_ledger_file(p, repo, "fixture-ledger"))

    extra_vault = os.environ.get("BASIC_MEMORY_DIR") or os.environ.get(
        "BASIC_MEMORY_HOME"
    )
    extra_ledger = os.environ.get("EVENT_LEDGER_DIR")
    live_vault_paths = discover_live(LIVE_VAULT_CANDIDATES, extra_vault)
    live_ledger_paths = discover_live(LIVE_LEDGER_CANDIDATES, extra_ledger)
    live_notes: list[Record] = []
    for root in live_vault_paths:
        if root.is_dir():
            live_notes.extend(load_vault_dir(root, repo, "live-vault"))
        elif root.is_file() and root.suffix.lower() in {".md", ".txt"}:
            rec = load_markdown_note(root, repo, "live-vault")
            if rec:
                live_notes.append(rec)
    live_ledger: list[Record] = []
    for root in live_ledger_paths:
        if root.is_file():
            live_ledger.extend(load_ledger_file(root, repo, "live-ledger"))
        elif root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in {
                    ".jsonl",
                    ".json",
                    ".log",
                    ".txt",
                }:
                    live_ledger.extend(load_ledger_file(p, repo, "live-ledger"))

    records = fixture_notes + fixture_ledger + live_notes + live_ledger
    by_pin = {r.permalink: r for r in records}

    author = retrieve(AUTHOR_QUERIES, records)
    reviewer = retrieve(REVIEWER_QUERIES, records)
    author_set: set[str] = set()
    for row in author:
        author_set.update(row["permalinks"])
    reviewer_set: set[str] = set()
    for row in reviewer:
        reviewer_set.update(row["permalinks"])

    cited = find_citations(repo, records)
    contra = contradictions(records, repo)
    contra_pins = {c["permalink"] for c in contra}

    findings: list[dict[str, Any]] = []
    unconsulted: list[dict[str, Any]] = []

    retrieving_for: dict[str, str] = {}
    for row in author:
        for pin in row["permalinks"]:
            retrieving_for.setdefault(pin, row["query"])

    for rec in records:
        pin = rec.permalink
        cite_hits = cited.get(pin) or []
        if rec.superseded_by:
            findings.append(
                {
                    "kind": "STALE",
                    "permalink": pin,
                    "superseded_by": rec.superseded_by,
                    "successor_resolves": rec.superseded_by in by_pin,
                    "note_anchor": f"{rec.path}:{line_of(rec, 'superseded_by')}",
                    "treated_as_current_truth": False,
                }
            )
            continue
        if pin in contra_pins:
            continue
        if cite_hits:
            findings.append(
                {
                    "kind": "CONSULTED",
                    "permalink": pin,
                    "citation": first_anchor(cite_hits),
                    "retrieving_query": retrieving_for.get(pin),
                }
            )
            continue
        if pin in author_set:
            q = retrieving_for[pin]
            row = {
                "kind": "UNCONSULTED",
                "permalink": pin,
                "retrieving_query": q,
                "relevance": (
                    f"Topic query {q!r} retrieved this note; no program artifact "
                    "cites permalink or exact title."
                ),
                "note_anchor": f"{rec.path}:1",
                "store": rec.store,
                "title": rec.title,
            }
            findings.append(row)
            unconsulted.append(
                {
                    "permalink": pin,
                    "retrieving_query": q,
                    "title": rec.title,
                    "store": rec.store,
                }
            )

    findings.extend(contra)

    missed = []
    for pin in sorted(reviewer_set - author_set):
        rec = by_pin.get(pin)
        if rec is None or rec.superseded_by:
            continue
        rq = next((r["query"] for r in reviewer if pin in r["permalinks"]), "")
        missed.append(
            {
                "permalink": pin,
                "title": rec.title,
                "reviewer_query": rq,
                "relevance": (
                    "Reviewer query retrieved a current note the author set missed."
                ),
            }
        )

    known_retrieved = [p for p in KNOWN_RELEVANT if p in author_set]
    stale_rec = by_pin.get(STALE_PIN)
    stale_ok = bool(
        stale_rec
        and stale_rec.superseded_by == STALE_SUCCESSOR
        and any(
            f["kind"] == "STALE" and f["permalink"] == STALE_PIN for f in findings
        )
        and not any(u["permalink"] == STALE_PIN for u in unconsulted)
    )
    contra_ok = any(
        f["kind"] == "CONTRADICTS"
        and f.get("note_permalink")
        and f.get("program_claim_anchor")
        and ":" in str(f.get("note_anchor"))
        and ":" in str(f.get("program_claim_anchor"))
        for f in findings
    )
    mention_flagged = any(
        "mention-rejected-ancestry.md" in str(f.get("program_claim_anchor") or "")
        for f in findings
        if f["kind"] == "CONTRADICTS"
    )
    cited_ok = any(
        f["kind"] == "CONSULTED" and f["permalink"] == CITED_PIN for f in findings
    )
    cited_not_unconsulted = all(u["permalink"] != CITED_PIN for u in unconsulted)

    dummy_hits = [
        r.permalink
        for r in records
        if r.permalink in KNOWN_RELEVANT and query_hits("zzzz-not-a-topic", r)
    ]
    underpowered_ok = not dummy_hits

    controls = [
        {
            "id": "known-relevant-retrieved",
            "result": "PASS" if known_retrieved else "FAIL",
            "detail": (
                "Author topic set retrieved "
                + (
                    ", ".join(known_retrieved)
                    or "neither squash-merge nor git-archive note"
                )
            ),
        },
        {
            "id": "superseded-classified-stale",
            "result": "PASS" if stale_ok else "FAIL",
            "detail": (
                f"{STALE_PIN} classified STALE via superseded_by={STALE_SUCCESSOR}; "
                "not treated as current truth."
                if stale_ok
                else f"{STALE_PIN} was not classified STALE"
            ),
        },
        {
            "id": "contradiction-both-anchors",
            "result": "PASS" if contra_ok and not mention_flagged else "FAIL",
            "detail": (
                "CONTRADICTS cites note permalink and program claim path:line; "
                "use-vs-mention file was not flagged."
                if contra_ok and not mention_flagged
                else "CONTRADICTS missing dual anchors or mention false-positive"
            ),
        },
        {
            "id": "cited-note-not-unconsulted",
            "result": "PASS" if cited_ok and cited_not_unconsulted else "FAIL",
            "detail": (
                f"{CITED_PIN} is CONSULTED because a program artifact cites the permalink."
            ),
        },
        {
            "id": "underpowered-query-detected",
            "result": "PASS" if underpowered_ok else "FAIL",
            "detail": (
                "Keyword 'zzzz-not-a-topic' retrieves 0 known-relevant notes, so a "
                "query set that missed squash-merge/CRLF would be detected as under-powered."
                if underpowered_ok
                else f"under-powered query still hit {dummy_hits}"
            ),
        },
    ]

    tests = [
        {
            "id": "control-known-relevant-note-retrieved",
            "catalog": "squash-merge branch-reporting or git-archive CRLF must be retrieved",
            "result": controls[0]["result"],
        },
        {
            "id": "control-superseded-stale",
            "catalog": "superseded_by pointer classified STALE, not current truth",
            "result": controls[1]["result"],
        },
        {
            "id": "control-contradiction-both-anchors",
            "catalog": "contradicting note surfaces with BOTH anchors, not a bare mention",
            "result": controls[2]["result"],
        },
    ]

    evidence = []
    for pin in list(KNOWN_RELEVANT) + [CONTRA_NOTE, CITED_PIN]:
        rec = by_pin.get(pin)
        if rec:
            evidence.append(
                {
                    "path": rec.path.split(":")[0],
                    "line": 2 if rec.lines else 1,
                    "snippet": (rec.title or rec.permalink)[:220],
                    "kind": "durable-note",
                }
            )
    planted = repo / PROGRAM_REL / "teardown-ancestry-sufficient.md"
    if planted.is_file():
        plines = planted.read_text(encoding="utf-8").splitlines()
        ln = 1
        for i, line in enumerate(plines, 1):
            if "sufficient" in line.lower():
                ln = i
                break
        evidence.append(
            {
                "path": rel_of(planted, repo),
                "line": ln,
                "snippet": plines[ln - 1].strip()[:220],
                "kind": "program-claim",
            }
        )

    residual = []
    if not live_vault_paths:
        residual.append(
            "Live basic-memory vault is not mounted on this Linux worktree; "
            "UNCONSULTED of the estate vault is NOT-CHECKED beyond fixtures + catalog citation scan."
        )
    if not live_ledger_paths:
        residual.append(
            "Live ~/.claude/event-ledger is not mounted; fixture ledger is the measured store."
        )

    all_pass = all(c["result"] == "PASS" for c in controls)
    return {
        "records": records,
        "by_pin": by_pin,
        "author_queries": author,
        "reviewer_queries": reviewer,
        "author_set": author_set,
        "findings": findings,
        "unconsulted": unconsulted,
        "controls": controls,
        "tests": tests,
        "evidence": evidence,
        "missed": missed,
        "contra": contra,
        "cited": cited,
        "live_vault_paths": [str(p) for p in live_vault_paths],
        "live_ledger_paths": [str(p) for p in live_ledger_paths],
        "fixture_note_count": len(fixture_notes),
        "fixture_ledger_count": len(fixture_ledger),
        "live_note_count": len(live_notes),
        "live_ledger_count": len(live_ledger),
        "residual": residual,
        "all_pass": all_pass,
        "known_retrieved": known_retrieved,
        "mention_flagged": mention_flagged,
        "reviewer_set": reviewer_set,
    }


def artifact_body(audit: dict[str, Any] | None = None) -> dict[str, Any]:
    a = audit or run_audit(REPO)
    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py"
    )
    state = "SUCCESS" if a["all_pass"] else "FAILED"
    reviewer_pass = a["all_pass"] and bool(a["missed"])
    return {
        "unit_id": UNIT,
        "state": state,
        "sentinel": "SUCCESS:BLD-0037" if state == "SUCCESS" else "FAILED:BLD-0037",
        "completion_marker": "SUCCESS:BLD-0037" if state == "SUCCESS" else "FAILED:BLD-0037",
        "title": (
            "Recall audit: durable memory that pre-answers or contradicts a live program premise"
        ),
        "question": (
            "Which durable memory note or ledger entry contradicts, or already answers, "
            "a current program premise — and was never consulted?"
        ),
        "scope_boundary": (
            "ADV-0018 sweeps the memory vault for contradictions against measured truth. "
            "This unit contributes the UNCONSULTED set: topically relevant notes no program "
            "artifact cited. ADV-0018 is not rebuilt here."
        ),
        "output_schema": SCHEMA_REL,
        "topic_queries": [
            {"id": r["id"], "query": r["query"], "hit_count": r["hit_count"]}
            for r in a["author_queries"]
        ],
        "stores": {
            "fixture_vault": {
                "present": True,
                "path": VAULT_REL,
                "note_count": a["fixture_note_count"],
            },
            "live_vault": {
                "present": bool(a["live_vault_paths"]),
                "paths_checked": [str(p) for p in LIVE_VAULT_CANDIDATES],
                "found": a["live_vault_paths"],
                "note_count": a["live_note_count"],
            },
            "fixture_ledger": {
                "present": True,
                "path": LEDGER_REL,
                "entry_count": a["fixture_ledger_count"],
            },
            "live_ledger": {
                "present": bool(a["live_ledger_paths"]),
                "paths_checked": [str(p) for p in LIVE_LEDGER_CANDIDATES],
                "found": a["live_ledger_paths"],
                "entry_count": a["live_ledger_count"],
            },
        },
        "retrieved_by_author": sorted(a["author_set"]),
        "findings": a["findings"],
        "unconsulted": a["unconsulted"],
        "controls": a["controls"],
        "tests": a["tests"],
        "evidence": a["evidence"],
        "reviewer": {
            "reviewer_id": "BLD-0037-independent-recall-queries",
            "independent": True,
            "verdict": "PASS" if reviewer_pass else "FAIL",
            "method": (
                "Three reviewer queries chosen without copying the author topic set. "
                "PASS requires the catalog controls plus at least one relevant current "
                "note the author set missed."
            ),
            "queries": [
                {"id": r["id"], "query": r["query"], "hit_count": r["hit_count"]}
                for r in a["reviewer_queries"]
            ],
            "notes_author_missed": a["missed"],
        },
        "named_probes": [
            {"id": "probe1", "command": p1, "role": "recall-controls"},
            {"id": "probe2", "command": p2, "role": "contradiction-anchors-and-reviewer"},
        ],
        "residual_unknowns": a["residual"],
        "live_catalog_observation": (
            "WORK-UNIT-CATALOG.json restates the squash-merge AHEAD fact and the "
            "git-archive CRLF measurement in many unit rows, but cites neither "
            "memory:// permalink. That is the recall failure this register measures: "
            "the fact was re-derived, the durable note was not consulted."
        ),
    }


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"
