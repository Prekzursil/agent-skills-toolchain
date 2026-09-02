"""Binding owner decisions for BLD-0014.

Named inputs: command-center/OWNER-DECISIONS.md (present on this worktree;
OQ-3 is the PR-ONLY record) and 17-DECISION-LOG.md (absent at repo root).
The other three named decisions are taken from catalog anchors the unit
itself names, with 17-DECISION-LOG.md present=false recorded rather than
fabricated.
"""
from __future__ import annotations

from pathlib import Path

NAMED_DECISION_FILES = (
    "command-center/OWNER-DECISIONS.md",
    "17-DECISION-LOG.md",
)

# Needles must match in the named source (or we fail closed).
BINDING = (
    {
        "id": "DEC-PR-ONLY",
        "title": "Release mode is PR-ONLY",
        "normative": (
            "Release mode is PR-ONLY: propose changes as pull requests, "
            "never a private canary and never a public marketplace release."
        ),
        "source_rel": "command-center/OWNER-DECISIONS.md",
        "needle": (
            "Release mode is PR-ONLY: propose changes as pull requests, "
            "never a private canary and never a public marketplace release."
        ),
    },
    {
        "id": "DEC-DELETE-ALL",
        "title": "Retirement scope is DELETE-ALL across five trees",
        "normative": (
            "Retirement scope = DELETE-ALL across five trees "
            "(owner-approved retirement of 77 files)."
        ),
        "source_rel": "command-center/WORK-UNIT-CATALOG.json",
        "needle": "retirement scope = DELETE-ALL across five trees",
    },
    {
        "id": "DEC-SALVAGE-HOME",
        "title": "Salvage home is tools/lib/",
        "normative": "Salvage home = tools/lib/ shared tree.",
        "source_rel": "command-center/WORK-UNIT-CATALOG.json",
        "needle": "salvage home = tools/lib/",
    },
    {
        "id": "DEC-NO-REMOTE",
        "title": "No-remote repos: triage first, never create remotes",
        "normative": (
            "No-remote repositories: triage first, report, owner decides; "
            "never create remotes or push."
        ),
        "source_rel": "command-center/WORK-UNIT-CATALOG.json",
        "needle": "do NOT create remotes or push",
    },
)


def find_anchor(repo: Path, rel: str, needle: str) -> dict:
    path = repo / rel
    if not path.is_file():
        return {
            "path": rel,
            "line": 0,
            "snippet": "",
            "present": False,
            "error": "file-absent",
        }
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [
        (i, line.strip())
        for i, line in enumerate(lines, 1)
        if needle in line
    ]
    if not hits:
        return {
            "path": rel,
            "line": 0,
            "snippet": "",
            "present": True,
            "error": "needle-absent",
        }
    if len(hits) != 1:
        # Prefer the first; record multiplicity so a silent collapse is visible.
        line_no, snippet = hits[0]
        return {
            "path": rel,
            "line": line_no,
            "snippet": snippet[:240],
            "present": True,
            "error": f"needle-not-unique:{len(hits)}",
        }
    line_no, snippet = hits[0]
    return {
        "path": rel,
        "line": line_no,
        "snippet": snippet[:240],
        "present": True,
        "error": None,
    }


def named_inputs(repo: Path) -> list[dict]:
    rows = []
    for rel in NAMED_DECISION_FILES:
        rows.append({"path": rel, "present": (repo / rel).is_file()})
    return rows


def load_decisions(repo: Path) -> list[dict]:
    out = []
    for spec in BINDING:
        anchor = find_anchor(repo, spec["source_rel"], spec["needle"])
        if not anchor.get("present") or anchor.get("line", 0) < 1:
            raise RuntimeError(
                f"decision {spec['id']} anchor failed: {anchor}"
            )
        out.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "normative": spec["normative"],
                "anchor": {
                    "path": anchor["path"],
                    "line": anchor["line"],
                    "snippet": anchor["snippet"],
                },
                "anchor_error": anchor.get("error"),
            }
        )
    return out
