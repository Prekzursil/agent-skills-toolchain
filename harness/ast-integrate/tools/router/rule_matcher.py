"""Deterministic rule-based matcher: the first-stage router (IMP-0389).

A trigger table of four disjoint kinds is matched against the *structured
role fields* of a query - never against its free-text payload:

* ``keyword``  literal keyword, matched against ``query["keyword"]``
* ``glob``     path glob, matched against ``query["path"]``
* ``cwd``      directory prefix, matched against ``query["cwd"]``
* ``verb``     tool verb, matched against ``query["tool_verb"]``

Properties the probes hold this module to:

* **No model call.** ``MatchResult.model_calls`` is always 0; nothing here
  imports or invokes a model.
* **Explainable.** Every non-empty selection names the exact table rows that
  fired (``fired_row_ids``), in table order.
* **Empty set is reachable.** A query whose role fields are unset, or match
  no row, returns ``[]``; there is no default row and ``FORBIDDEN_GLOBS`` /
  ``FORBIDDEN_CWD`` keep an always-fire pattern out of the table.
* **Use vs mention.** Payload text that merely *names* a pattern does not fire
  it.  ``naive_payload_scan`` is the deliberately wrong scanner kept as the
  contrast: it reads the payload and over-fires on mentions.

The table is authored in ``builtin_table`` and mirrored to ``TABLE_REL`` by
``dump_trigger_table`` so an owner can read the rows without importing this
module; ``load_table`` reads the mirror back and ``validate_table`` fails
closed on duplicates, unknown kinds or always-fire patterns.
"""
from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

__all__ = [
    "FORBIDDEN_CWD",
    "FORBIDDEN_GLOBS",
    "KINDS",
    "MUTATION_ROW_ID",
    "MatchResult",
    "TABLE_REL",
    "TriggerRow",
    "builtin_table",
    "dump_trigger_table",
    "kind_unit_queries",
    "labelled_corpus",
    "load_table",
    "match_query",
    "mutation_reds",
    "naive_payload_scan",
    "posix_norm",
    "trace_corpus",
    "validate_table",
]

TABLE_REL = "tools/router/trigger_table.json"
KINDS: tuple[str, ...] = ("keyword", "glob", "cwd", "verb")
MUTATION_ROW_ID = "kw.pytest"

# Patterns that would fire on every query.  validate_table rejects them so the
# empty set can never be swallowed by a default row.
FORBIDDEN_GLOBS = frozenset({"", "*", "**", "**/*", "*/**", "**/**", "?*", "*.*"})
FORBIDDEN_CWD = frozenset({"", "/", ".", "//", "~"})

KEYWORDS: tuple[str, ...] = (
    "pytest",
    "deploy",
    "lint",
    "schema",
    "receipt",
    "catalog",
    "probe",
    "router",
    "capability",
    "fusion",
    "embed",
    "hatch",
    "census",
)
GLOB_EXTS: tuple[str, ...] = (
    "py",
    "json",
    "md",
    "toml",
    "yml",
    "sql",
    "html",
    "css",
    "tf",
    "jsonl",
    "rs",
    "go",
    "ts",
)
VERBS: tuple[str, ...] = (
    "Read",
    "Write",
    "Edit",
    "Grep",
    "Glob",
    "Bash",
    "Task",
    "Delete",
    "WebSearch",
    "WebFetch",
    "AskQuestion",
    "CallMcpTool",
    "GenerateImage",
)
CWD_ROOT = "/workspace/imp0389"
GLOB_ROOT = "src/imp0389"
ROWS_PER_KIND = 13

# The keywords a kind-unit payload *mentions* without using them as a role.
_MENTION_POOL: tuple[str, ...] = ("pytest", "deploy", "lint", "schema", "receipt")
_MENTION_PREFIX = "mention-only (not a role): "

_TOKEN = re.compile(r"[A-Za-z0-9_./*\-]+")


@dataclass(frozen=True)
class TriggerRow:
    """One row of the trigger table."""

    row_id: str
    kind: str
    pattern: str
    capability_id: str = ""
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatchResult:
    """What the first stage returns for one query."""

    query_id: str
    fired_row_ids: list[str] = field(default_factory=list)
    fired_kinds: list[str] = field(default_factory=list)
    explanations: list[dict[str, str]] = field(default_factory=list)
    model_calls: int = 0

    @property
    def empty(self) -> bool:
        return not self.fired_row_ids


# -- normalisation --------------------------------------------------------------
def posix_norm(value: Any) -> str:
    """Forward slashes, no trailing slash (except root), no ``./`` prefix."""
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    while text.startswith("./"):
        text = text[2:]
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _cwd_prefix_match(cwd: str, pattern: str) -> bool:
    """``pattern`` is ``cwd`` itself or a proper directory ancestor of it."""
    cwd_n = posix_norm(cwd)
    pat_n = posix_norm(pattern)
    if not cwd_n or not pat_n or pat_n in FORBIDDEN_CWD:
        return False
    if cwd_n == pat_n:
        return True
    return cwd_n.startswith(pat_n + "/")


def _glob_match(path: str, pattern: str) -> bool:
    path_n = posix_norm(path)
    if not path_n or not pattern or pattern in FORBIDDEN_GLOBS:
        return False
    if fnmatch.fnmatchcase(path_n, pattern):
        return True
    # A bare ``*.ext`` style pattern may also match the basename.
    if "/" not in pattern:
        return fnmatch.fnmatchcase(PurePosixPath(path_n).name, pattern)
    return False


# -- table ---------------------------------------------------------------------
def builtin_table() -> list[TriggerRow]:
    """The 52-row trigger table: 13 rows for each of the four kinds."""
    rows: list[TriggerRow] = []
    for word in KEYWORDS:
        rows.append(
            TriggerRow(
                row_id=f"kw.{word}",
                kind="keyword",
                pattern=word,
                capability_id=f"cap.kw.{word}",
                note=f"literal keyword role == {word!r}",
            )
        )
    for i, ext in enumerate(GLOB_EXTS, start=1):
        rows.append(
            TriggerRow(
                row_id=f"glob.k{i:02d}",
                kind="glob",
                pattern=f"{GLOB_ROOT}/k{i:02d}/*.{ext}",
                capability_id=f"cap.glob.k{i:02d}",
                note=f"path role matches glob {GLOB_ROOT}/k{i:02d}/*.{ext}",
            )
        )
    for i in range(1, ROWS_PER_KIND + 1):
        rows.append(
            TriggerRow(
                row_id=f"cwd.c{i:02d}",
                kind="cwd",
                pattern=f"{CWD_ROOT}/c{i:02d}",
                capability_id=f"cap.cwd.c{i:02d}",
                note=f"cwd role is {CWD_ROOT}/c{i:02d} or a directory below it",
            )
        )
    for verb in VERBS:
        rows.append(
            TriggerRow(
                row_id=f"verb.{verb}",
                kind="verb",
                pattern=verb,
                capability_id=f"cap.verb.{verb}",
                note=f"tool_verb role == {verb!r}",
            )
        )
    return rows


def validate_table(table: Iterable[TriggerRow]) -> list[TriggerRow]:
    """Fail closed on anything that would make a selection unexplainable."""
    rows = list(table)
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, TriggerRow):
            raise TypeError(f"table row is not a TriggerRow: {row!r}")
        if not row.row_id or row.row_id in seen:
            raise ValueError(f"duplicate or empty row_id: {row.row_id!r}")
        seen.add(row.row_id)
        if row.kind not in KINDS:
            raise ValueError(f"{row.row_id}: unknown kind {row.kind!r}")
        if not str(row.pattern).strip():
            raise ValueError(f"{row.row_id}: empty pattern")
        if row.kind == "glob" and row.pattern in FORBIDDEN_GLOBS:
            raise ValueError(f"{row.row_id}: always-fire glob {row.pattern!r}")
        if row.kind == "cwd" and posix_norm(row.pattern) in FORBIDDEN_CWD:
            raise ValueError(f"{row.row_id}: always-fire cwd prefix {row.pattern!r}")
        if row.kind == "keyword" and (" " in row.pattern or row.pattern != row.pattern.lower()):
            raise ValueError(f"{row.row_id}: keyword must be one lower-case literal")
    return rows


def dump_trigger_table(path: Path | str, table: Iterable[TriggerRow]) -> Path:
    """Mirror the table to JSON so owners can read it without importing code."""
    rows = validate_table(table)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0389",
        "kinds": list(KINDS),
        "forbidden_globs": sorted(FORBIDDEN_GLOBS),
        "forbidden_cwd": sorted(FORBIDDEN_CWD),
        "model_call": False,
        "default_row": None,
        "rows": [r.to_json() for r in rows],
    }
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return out


def load_table(path: Path | str) -> list[TriggerRow]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_rows = doc.get("rows") if isinstance(doc, dict) else doc
    rows: list[TriggerRow] = []
    for raw in raw_rows or []:
        if not isinstance(raw, dict):
            raise ValueError(f"table row is not an object: {raw!r}")
        rows.append(
            TriggerRow(
                row_id=str(raw.get("row_id") or raw.get("id") or ""),
                kind=str(raw.get("kind") or ""),
                pattern=str(raw.get("pattern") or ""),
                capability_id=str(raw.get("capability_id") or ""),
                note=str(raw.get("note") or ""),
            )
        )
    return validate_table(rows)


# -- matching ------------------------------------------------------------------
def _role(query: dict[str, Any], name: str) -> str:
    value = query.get(name)
    if value is None:
        return ""
    return str(value).strip()


def row_fires(row: TriggerRow, query: dict[str, Any]) -> bool:
    """Does ``row`` fire on the query's role fields?  Payload is never read."""
    if row.kind == "keyword":
        keyword = _role(query, "keyword").lower()
        return bool(keyword) and keyword == row.pattern
    if row.kind == "glob":
        return _glob_match(_role(query, "path"), row.pattern)
    if row.kind == "cwd":
        return _cwd_prefix_match(_role(query, "cwd"), row.pattern)
    if row.kind == "verb":
        verb = _role(query, "tool_verb")
        return bool(verb) and verb == row.pattern
    return False


def match_query(query: dict[str, Any], table: Iterable[TriggerRow]) -> MatchResult:
    """First-stage selection: the rows that fire, each named by row_id."""
    result = MatchResult(query_id=str(query.get("query_id") or ""))
    for row in table:
        if row_fires(row, query):
            result.fired_row_ids.append(row.row_id)
            if row.kind not in result.fired_kinds:
                result.fired_kinds.append(row.kind)
            role = {"keyword": "keyword", "glob": "path", "cwd": "cwd", "verb": "tool_verb"}[row.kind]
            result.explanations.append(
                {
                    "row_id": row.row_id,
                    "kind": row.kind,
                    "pattern": row.pattern,
                    "role": role,
                    "role_value": _role(query, role),
                }
            )
    result.model_calls = 0
    return result


def naive_payload_scan(query: dict[str, Any], table: Iterable[TriggerRow]) -> list[str]:
    """The wrong scanner, kept as a contrast: fires on payload *mentions*."""
    tokens = _TOKEN.findall(str(query.get("payload") or ""))
    lowered = {t.lower() for t in tokens}
    fired: list[str] = []
    for row in table:
        hit = False
        if row.kind == "keyword":
            hit = row.pattern in lowered
        elif row.kind == "verb":
            hit = row.pattern in tokens
        elif row.kind == "glob":
            hit = any(_glob_match(t, row.pattern) for t in tokens)
        elif row.kind == "cwd":
            hit = any(_cwd_prefix_match(t, row.pattern) for t in tokens)
        if hit:
            fired.append(row.row_id)
    return fired


# -- labelled corpus -----------------------------------------------------------
def _query(
    query_id: str,
    payload: str,
    *,
    kind: str,
    keyword: str | None = None,
    path: str | None = None,
    cwd: str | None = None,
    tool_verb: str | None = None,
    expected_row_ids: list[str] | None = None,
) -> dict[str, Any]:
    expected = list(expected_row_ids or [])
    return {
        "query_id": query_id,
        "payload": payload,
        "keyword": keyword,
        "path": path,
        "cwd": cwd,
        "tool_verb": tool_verb,
        "expected_row_ids": expected,
        "expected_empty": not expected,
        "kind": kind,
    }


def _mention_payload(exclude: str = "") -> str:
    words = [w for w in _MENTION_POOL if w != exclude][:4]
    return _MENTION_PREFIX + " ".join(words)


def _positive_query(row: TriggerRow) -> dict[str, Any]:
    """The labelled query that exercises exactly one row via its role field."""
    qid = f"q-{row.row_id}"
    if row.kind == "keyword":
        return _query(
            qid, _mention_payload(row.pattern), kind="keyword", keyword=row.pattern,
            expected_row_ids=[row.row_id],
        )
    if row.kind == "glob":
        # pattern: src/imp0389/kNN/*.ext -> a concrete file under that directory
        directory, _, tail = row.pattern.rpartition("/")
        ext = tail.rsplit(".", 1)[-1]
        return _query(
            qid, _mention_payload(), kind="glob", path=f"{directory}/mod.{ext}",
            expected_row_ids=[row.row_id],
        )
    if row.kind == "cwd":
        return _query(
            qid, _mention_payload(), kind="cwd", cwd=f"{row.pattern}/src",
            expected_row_ids=[row.row_id],
        )
    return _query(
        qid, _mention_payload(), kind="verb", tool_verb=row.pattern,
        expected_row_ids=[row.row_id],
    )


_EMPTY_PAYLOADS: tuple[str, ...] = (
    "Please don't run pytest; this is a mention not a use of the pytest runner.",
    "We discussed deploy pipelines in the abstract, not as a selected trigger.",
    "The word Read appears here as a citation of the tool name, not a tool-verb role.",
    "Path src/imp0389/k01/mod.py is mentioned in prose, not selected as a glob path.",
    "cwd /workspace/imp0389/c01 is mentioned in a log snippet, not as the query cwd.",
    "Avoid Glob and Grep; this query has no tool-verb role and must yield zero rows.",
    "capability fusion embed hatch census are vocabulary mentions, not keywords.",
    "schema receipt catalog probe router lint are names in a paragraph, not roles.",
)


def labelled_corpus(table: Iterable[TriggerRow]) -> list[dict[str, Any]]:
    """60 labelled queries: one positive per row (52) plus 8 no-fit negatives."""
    corpus = [_positive_query(row) for row in table]
    for i, payload in enumerate(_EMPTY_PAYLOADS, start=1):
        corpus.append(_query(f"q-empty-{i:02d}", payload, kind="none"))
    return corpus


def kind_unit_queries(table: Iterable[TriggerRow]) -> dict[str, dict[str, Any]]:
    """One unit query per kind: the first row of that kind in the table."""
    out: dict[str, dict[str, Any]] = {}
    for row in table:
        if row.kind not in out:
            out[row.kind] = _positive_query(row)
    missing = [k for k in KINDS if k not in out]
    if missing:
        raise ValueError(f"table has no row for kinds {missing}")
    return out


def trace_corpus(corpus: Iterable[dict[str, Any]], table: Iterable[TriggerRow]) -> list[dict[str, Any]]:
    """Run every labelled query and record what fired against the label."""
    rows = list(table)
    traces: list[dict[str, Any]] = []
    for query in corpus:
        result = match_query(query, rows)
        expected = list(query.get("expected_row_ids") or [])
        traces.append(
            {
                "query_id": query.get("query_id"),
                "kind": query.get("kind"),
                "roles": {
                    "keyword": query.get("keyword"),
                    "path": query.get("path"),
                    "cwd": query.get("cwd"),
                    "tool_verb": query.get("tool_verb"),
                },
                "fired_row_ids": list(result.fired_row_ids),
                "fired_kinds": list(result.fired_kinds),
                "explanations": list(result.explanations),
                "expected_row_ids": expected,
                "empty": result.empty,
                "expected_empty": bool(query.get("expected_empty")),
                "label_ok": result.fired_row_ids == expected,
                "model_calls": result.model_calls,
                "naive_payload_scan": naive_payload_scan(query, rows),
            }
        )
    return traces


def mutation_reds(
    table: Iterable[TriggerRow],
    corpus: Iterable[dict[str, Any]],
    row_id: str,
) -> list[str]:
    """Delete ``row_id`` from a *copy* of the table; return the queries that go red."""
    mutated = [r for r in table if r.row_id != row_id]
    return [t["query_id"] for t in trace_corpus(corpus, mutated) if not t["label_ok"]]


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="deterministic first-stage rule matcher")
    parser.add_argument("--table", default=None, help=f"trigger table JSON (default: builtin / {TABLE_REL})")
    parser.add_argument("--keyword")
    parser.add_argument("--path")
    parser.add_argument("--cwd")
    parser.add_argument("--tool-verb")
    parser.add_argument("--payload", default="")
    args = parser.parse_args(argv)
    table = load_table(args.table) if args.table else builtin_table()
    query = {
        "query_id": "cli",
        "payload": args.payload,
        "keyword": args.keyword,
        "path": args.path,
        "cwd": args.cwd,
        "tool_verb": args.tool_verb,
    }
    result = match_query(query, table)
    json.dump(
        {
            "fired_row_ids": result.fired_row_ids,
            "empty": result.empty,
            "explanations": result.explanations,
            "model_calls": result.model_calls,
        },
        sys.stdout,
        indent=1,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
