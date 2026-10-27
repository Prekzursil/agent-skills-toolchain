"""CI gate: the mechanism registry stays closed, anchored, and non-colliding.

The measured estate defect this exists to close (WFA-0067 evidence B):
a completeness check that is disarmed by its own default argument, and that
passes a deletion of the entire block it guards. This gate therefore:

  * runs under bare argv (the CI form). There is no ``--require`` /
    ``--check`` / ``--enable`` flag that would arm the checks only when
    passed; CI invoking ``python tools/command-center/mechanism_registry_gate.py``
    with empty extra flags is the live invocation.
  * fails closed on an empty or deleted ``mechanisms`` block (MECH-EMPTY,
    the no-op-hole control). Zero rows is not a vacuous pass.
  * reads git blobs via ``git cat-file -p HEAD:<path>`` when the tree is a
    git checkout, so a CRLF working copy cannot change the verdict.

Checks, each independently falsifiable:

  MECH-EMPTY    the vocabulary ``mechanisms`` block is missing, not a list,
                or empty. Deleting the whole block must turn the gate red.
  MECH-UNDEF    a mechanism id is present without a non-empty definition
                (and discriminating example).
  MECH-DANGLING an artifact cites a mechanism id that is not in the registry.
  MECH-COLLIDE  a mechanism id collides with the candidate (wf-*), blueprint
                (BP-*), or option (M-NN) namespaces.
  MECH-MISSING  a guarded artifact is missing or unparseable (fail closed).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REL_REGISTRY = "command-center/wfa/mechanism-registry.json"
REL_INCIDENCE = "command-center/wfa/mechanism-incidence.json"
REL_NAMESPACES = "command-center/wfa/mechanism-namespaces.json"

CANDIDATE_RE = re.compile(r"^wf-", re.I)
BLUEPRINT_RE = re.compile(r"^BP-[0-9]+$", re.I)
OPTION_RE = re.compile(r"^M-[0-9]+$", re.I)
NS_KIND = {
    "candidate": CANDIDATE_RE,
    "blueprint": BLUEPRINT_RE,
    "option": OPTION_RE,
}
NS_KEYS = {
    "candidate": "candidate_ids",
    "blueprint": "blueprint_ids",
    "option": "option_ids",
}


class Violation(dict):
    """A single finding. `dict` so the JSON report needs no encoder."""

    def __init__(self, check: str, item_id: str, detail: str) -> None:
        super().__init__(check=check, id=item_id, detail=detail)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self['check']} {self['id']}: {self['detail']}"


def repo_root() -> Path:
    """Checkout root, derived from this file (tools/command-center/)."""
    return Path(__file__).resolve().parents[2]


def read_blob(root: Path, rel: str) -> tuple[bytes, str]:
    rel = rel.replace("\\", "/")
    git_dir = root / ".git"
    if git_dir.exists():
        proc = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            cwd=str(root),
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout, "git-cat-file-HEAD"
    path = root / rel
    raw = path.read_bytes() if path.is_file() else b""
    return raw.replace(b"\r\n", b"\n"), "working-tree-lf-normalized"


def load_json_blob(root: Path, rel: str) -> tuple[Any, str]:
    raw, source = read_blob(root, rel)
    if not raw:
        return None, source
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, source
    try:
        return json.loads(text), source
    except json.JSONDecodeError:
        return None, source


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _as_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        token = value.strip()
        return [token] if token else []
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            token = str(item.get("id") or "").strip()
            if token:
                out.append(token)
    return out


def citations(doc: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not isinstance(doc, dict):
        return out
    rows = doc.get("artifacts")
    if not isinstance(rows, list):
        rows = doc.get("citations")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or row.get("artifact") or "")
        ids = row.get("mechanism_ids")
        if ids is None:
            ids = row.get("ids")
        for mid in _as_id_list(ids):
            out.append((path, mid))
    return out


def check(root: Path) -> tuple[list[Violation], dict[str, Any]]:
    """Run every check. Returns (violations, stats). Never raises on bad data."""
    violations: list[Violation] = []
    blob_sources: list[str] = []
    blobs: list[dict[str, Any]] = []

    def load(rel: str) -> Any:
        doc, source = load_json_blob(root, rel)
        blob_sources.append(source)
        raw, _ = read_blob(root, rel)
        blobs.append({"path": rel, "source": source, "bytes": len(raw)})
        if not isinstance(doc, dict):
            violations.append(
                Violation(
                    "MECH-MISSING",
                    rel,
                    "guarded artifact missing or unparseable (fail closed)",
                )
            )
            return {}
        return doc

    registry = load(REL_REGISTRY)
    incidence = load(REL_INCIDENCE)
    namespaces = load(REL_NAMESPACES)

    mechanisms = registry.get("mechanisms") if isinstance(registry, dict) else None
    if not isinstance(mechanisms, list) or len(mechanisms) == 0:
        violations.append(
            Violation(
                "MECH-EMPTY",
                "mechanisms",
                "vocabulary mechanisms block is missing or empty "
                "(no-op-hole: a completeness check that passes deletion of "
                "the block it guards)",
            )
        )
        mechanisms = []

    defined: dict[str, dict[str, Any]] = {}
    for entry in mechanisms:
        if not isinstance(entry, dict):
            violations.append(
                Violation("MECH-UNDEF", "<non-object>", "mechanism entry is not an object")
            )
            continue
        mid = str(entry.get("id") or "").strip()
        if not mid:
            violations.append(
                Violation("MECH-UNDEF", "<blank>", "mechanism id added without a definition")
            )
            continue
        if mid in defined:
            violations.append(Violation("MECH-DUP", mid, "duplicate mechanism id"))
        defined[mid] = entry
        if not _nonempty_str(entry.get("definition")):
            violations.append(
                Violation("MECH-UNDEF", mid, "mechanism id added without a definition")
            )
        elif not _nonempty_str(entry.get("discriminating_example")):
            violations.append(
                Violation(
                    "MECH-UNDEF",
                    mid,
                    "mechanism id added without a discriminating example",
                )
            )

        kind = None
        if OPTION_RE.match(mid):
            kind = "option"
        elif BLUEPRINT_RE.match(mid):
            kind = "blueprint"
        elif CANDIDATE_RE.match(mid):
            kind = "candidate"
        if kind is None:
            for ns_kind, key in NS_KEYS.items():
                tokens = namespaces.get(key) if isinstance(namespaces, dict) else None
                if isinstance(tokens, list) and mid in {str(t) for t in tokens}:
                    kind = ns_kind
                    break
        if kind is not None:
            violations.append(
                Violation(
                    "MECH-COLLIDE",
                    mid,
                    f"mechanism id collides with the {kind} namespace",
                )
            )

    cited = citations(incidence)
    for path, mid in cited:
        if mid not in defined:
            violations.append(
                Violation(
                    "MECH-DANGLING",
                    mid,
                    f"artifact {path} references unknown mechanism id",
                )
            )

    unique_sources = sorted(set(blob_sources))
    stats: dict[str, Any] = {
        "mechanisms": len(defined),
        "citations": len(cited),
        "closed": bool(registry.get("closed")) if isinstance(registry, dict) else False,
        "blob_sources": unique_sources,
        "blobs": blobs,
    }
    return violations, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the mechanism registry (always-on CI gate)."
    )
    parser.add_argument(
        "--json", action="store_true", help="emit the machine-readable report"
    )
    args = parser.parse_args(argv)

    violations, stats = check(repo_root())
    sources = ",".join(stats.get("blob_sources") or [])
    summary = (
        "mech-registry-gate "
        f"mechanisms={stats['mechanisms']} "
        f"citations={stats['citations']} "
        f"blob_sources={sources}"
    )
    if args.json:
        print(
            json.dumps(
                {"violations": violations, "stats": stats}, indent=2, sort_keys=True
            )
        )
    else:
        for violation in violations:
            print(f"  {violation}")
        print(summary)
    if violations:
        print(f"FAILED:mech-registry-gate violations={len(violations)}")
        return 1
    closed = "true" if stats.get("closed") else "false"
    print(
        f"SUCCESS:mech-registry-gate mechanisms={stats['mechanisms']} "
        f"citations={stats['citations']} closed={closed}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
