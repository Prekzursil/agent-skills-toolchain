#!/usr/bin/env python3
"""Namespace resolver and ambiguous-bare-token gate.

Resolution rules (never guess from surrounding prose):
  1. Disjoint assigned prefix (MECH / OPT / HRNS / MGRADE) resolves uniquely.
  2. An explicit per-file namespace declaration resolves uniquely.
  3. Use-vs-mention: mention-only files, mention paths, quoted/fenced examples
     are MENTION, not unresolved USE.
  4. Any remaining bare M-NN USE is AMBIGUOUS — the gate fires. Do not guess.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from extractor import Hit, extract

NS_COMMENT = re.compile(
    r"<!--\s*option-id-namespace:\s*([a-z0-9-]+)\s*-->", re.IGNORECASE
)
NS_JSON = re.compile(r'"option_id_namespace"\s*:\s*"([a-z0-9-]+)"')

ASSIGNED_PREFIX = {
    "option-universe-family-M": "OPT",
    "architecture-mechanism": "MECH",
    "research-harness": "HRNS",
    "wave1-mission-grade": "MGRADE",
}
PREFIX_TO_NS = {v: k for k, v in ASSIGNED_PREFIX.items()}

MENTION_PATH_MARKERS = (
    "WORK-UNIT-CATALOG.json",
    "/p2-wave/P2-",
    "P2-CLOUD-LEFTOVER",
    "/fixtures/mention/",
    "option-id-namespace.schema.json",
)


def file_namespace(text: str) -> str | None:
    m = NS_COMMENT.search(text)
    if m:
        return m.group(1).lower()
    m = NS_JSON.search(text[:8000])
    if m:
        return m.group(1).lower()
    return None


def is_mention_path(rel_posix: str) -> bool:
    n = rel_posix.replace("\\", "/")
    return any(marker in n for marker in MENTION_PATH_MARKERS)


def _line_quotes_token(line: str, token: str, column: int) -> bool:
    """True when the token is a quoted or backticked example on this line."""
    i = column - 1
    if i < 0 or i >= len(line):
        return False
    before = line[:i]
    after = line[i + len(token) :]
    if before.endswith("`") and after.startswith("`"):
        return True
    if before.endswith('"') and after.startswith('"'):
        return True
    if before.endswith("'") and after.startswith("'"):
        return True
    # Whole-line quotation of the collision.
    stripped = line.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        return True
    return False


def classify(
    hit: Hit,
    *,
    file_ns: str | None,
    rel_posix: str,
    line_text: str,
) -> dict:
    if hit.kind == "MECH":
        return {
            "verdict": "RESOLVES-ONE",
            "namespace": "architecture-mechanism",
            "via": "disjoint-prefix",
        }
    token = hit.token
    for prefix, ns in PREFIX_TO_NS.items():
        if token.startswith(prefix + "-"):
            return {
                "verdict": "RESOLVES-ONE",
                "namespace": ns,
                "via": "disjoint-prefix",
            }
    if file_ns == "mention-only" or is_mention_path(rel_posix):
        return {
            "verdict": "MENTION",
            "namespace": None,
            "via": "use-vs-mention",
        }
    if hit.in_fence or _line_quotes_token(line_text, token, hit.column):
        return {
            "verdict": "MENTION",
            "namespace": None,
            "via": "quoted-or-fenced",
        }
    if file_ns:
        return {
            "verdict": "RESOLVES-ONE",
            "namespace": file_ns,
            "via": "per-file-namespace-declaration",
        }
    return {
        "verdict": "AMBIGUOUS",
        "namespace": None,
        "via": "bare-m-no-declaration",
    }


def _line_map(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def resolve_tree(root: Path, *, which: str = "primary") -> list[dict]:
    rows: list[dict] = []
    files = {p.resolve(): p for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}
    ns_cache: dict[str, str | None] = {}
    line_cache: dict[str, list[str]] = {}
    hits = extract(root, kind="both", which=which)
    for hit in hits:
        fp = (root / hit.path) if root.is_dir() else root
        if not fp.is_file():
            # extract() paths are relative to root; try resolved walk
            cand = None
            for real in files.values():
                if real.as_posix().endswith("/" + hit.path) or real.as_posix().endswith(hit.path):
                    cand = real
                    break
            fp = cand or fp
        key = str(fp)
        if key not in ns_cache:
            text = fp.read_text(encoding="utf-8", errors="replace") if fp.is_file() else ""
            ns_cache[key] = file_namespace(text)
            line_cache[key] = text.splitlines()
        lines = line_cache[key]
        line_text = lines[hit.line - 1] if 0 < hit.line <= len(lines) else hit.snippet
        decision = classify(
            hit,
            file_ns=ns_cache[key],
            rel_posix=hit.path,
            line_text=line_text,
        )
        row = {
            "path": hit.path,
            "line": hit.line,
            "token": hit.token,
            "number": hit.number,
            "kind": hit.kind,
            "snippet": hit.snippet,
            **decision,
        }
        rows.append(row)
    return rows


def gate(rows: list[dict]) -> dict:
    ambiguous = [
        r
        for r in rows
        if r.get("verdict") == "AMBIGUOUS" and r.get("kind") == "M"
    ]
    return {
        "fired": bool(ambiguous),
        "ambiguous_use_count": len(ambiguous),
        "ambiguous_uses": ambiguous[:50],
        "rule": (
            "FAIL on any bare M-NN USE that lacks a disjoint assigned prefix "
            "and lacks a per-file namespace declaration. Mentions and MECH-NN "
            "are not bare-ambiguous."
        ),
    }


def gate_root(root: Path) -> dict:
    return gate(resolve_tree(root))


def main() -> int:
    """CLI: python3 resolver.py <root>  — exit 1 if the gate fires."""
    import sys

    if len(sys.argv) < 2:
        print("usage: resolver.py <root>")
        return 2
    root = Path(sys.argv[1])
    result = gate_root(root)
    print(json.dumps({k: result[k] for k in ("fired", "ambiguous_use_count", "rule")}, indent=2))
    return 1 if result["fired"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
