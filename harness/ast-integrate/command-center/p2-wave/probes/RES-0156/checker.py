#!/usr/bin/env python3
"""Apply the RES-0156 evidence standard to a single finding.

GROUNDED: at least one citation that resolves to a real file:line in this
worktree. External-only is the wrong standard. Empty is ZERO_CITATION.

IDEATION: at least one external URL or DOI. Using a repo file:line as THE
finding is FORBIDDEN_GROUNDING. A file:line tagged already-present-negative
is allowed (the gem is rejected because it is already here) and does not
count as grounding.

CONTESTED: if object_scope is unbound, do not assign a standard. The
deciding experiment is bind-object-scope, not a preference.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lenses import (
    CONTESTED,
    GROUNDED,
    IDEATION,
    LENS_BY_ID,
    REPO,
    effective_standard,
)

FILE_LINE_RE = re.compile(
    r"^(?P<path>(?:command-center|rules|tools|docs|hooks)/[^\s:]+):(?P<line>\d+)$"
)
URL_RE = re.compile(r"^https?://", re.I)
DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")
FIXTURE_URL_RE = re.compile(r"^fixture://", re.I)


def resolve_file_line(anchor: str) -> dict[str, Any]:
    m = FILE_LINE_RE.match(str(anchor or "").replace("\\", "/").strip())
    if not m:
        return {"ok": False, "reason": "not-file-line"}
    rel = m.group("path")
    line_no = int(m.group("line"))
    path = REPO / rel
    if not path.is_file():
        return {"ok": False, "reason": "missing-file", "path": rel, "line": line_no}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if line_no < 1 or line_no > len(lines):
        return {
            "ok": False,
            "reason": "line-out-of-range",
            "path": rel,
            "line": line_no,
            "n_lines": len(lines),
        }
    text = lines[line_no - 1]
    if not text.strip():
        return {"ok": False, "reason": "empty-line", "path": rel, "line": line_no}
    return {
        "ok": True,
        "path": rel,
        "line": line_no,
        "text": text[:240],
    }


def classify_citation(cite: Any) -> dict[str, Any]:
    if isinstance(cite, str):
        cite = {"value": cite}
    if not isinstance(cite, dict):
        return {"kind": "invalid", "external": False, "repo": False}
    value = str(cite.get("value") or cite.get("anchor") or "").strip()
    kind = str(cite.get("kind") or "").lower()
    role = str(cite.get("role") or "").lower()
    if kind in {"url", "doi"} or URL_RE.match(value) or DOI_RE.match(value) or FIXTURE_URL_RE.match(value):
        return {
            "kind": "external",
            "external": True,
            "repo": False,
            "value": value,
            "role": role,
        }
    resolved = resolve_file_line(value)
    if resolved["ok"]:
        return {
            "kind": "repo",
            "external": False,
            "repo": True,
            "value": value,
            "role": role,
            "resolved": resolved,
        }
    if FILE_LINE_RE.match(value):
        return {
            "kind": "broken-file-line",
            "external": False,
            "repo": False,
            "value": value,
            "role": role,
            "resolved": resolved,
        }
    return {"kind": "none", "external": False, "repo": False, "value": value, "role": role}


def check_finding(finding: dict[str, Any]) -> dict[str, Any]:
    lens_id = str(finding.get("lens_id") or "")
    if lens_id not in LENS_BY_ID:
        return {
            "compliant": False,
            "status": "UNKNOWN-LENS",
            "violations": [{"code": "UNKNOWN_LENS", "detail": lens_id}],
            "lens_id": lens_id,
        }
    scope = finding.get("object_scope")
    applied = effective_standard(lens_id, None if scope is None else str(scope))
    citations = finding.get("citations") or []
    if not isinstance(citations, list):
        citations = []
    classified = [classify_citation(c) for c in citations]
    repo_findings = [
        c for c in classified if c.get("repo") and c.get("role") != "already-present-negative"
    ]
    repo_negatives = [
        c for c in classified if c.get("repo") and c.get("role") == "already-present-negative"
    ]
    external = [c for c in classified if c.get("external")]
    broken = [c for c in classified if c.get("kind") == "broken-file-line"]

    violations: list[dict[str, Any]] = []
    if applied == CONTESTED:
        return {
            "compliant": False,
            "status": CONTESTED,
            "applied_standard": CONTESTED,
            "lens_id": lens_id,
            "object_scope": scope,
            "violations": [
                {
                    "code": "UNBOUND_OBJECT_SCOPE",
                    "detail": (
                        "Deciding experiment: bind object_scope to estate "
                        "(GROUNDED) or external (IDEATION). Do not assign "
                        "by preference."
                    ),
                }
            ],
            "citation_kinds": [c.get("kind") for c in classified],
        }

    if applied == GROUNDED:
        if repo_findings:
            status = "PASS"
        elif broken:
            status = "BROKEN_FILE_LINE"
            violations.append({"code": "BROKEN_FILE_LINE", "detail": broken[0].get("value")})
        elif external and not repo_findings:
            status = "WRONG_STANDARD"
            violations.append(
                {
                    "code": "GROUNDED_NEEDS_FILE_LINE",
                    "detail": "external-only citation on a GROUNDED lens",
                }
            )
        else:
            status = "ZERO_CITATION"
            violations.append(
                {
                    "code": "ZERO_CITATION",
                    "detail": "GROUNDED lens produced no resolving file:line",
                }
            )
        return {
            "compliant": status == "PASS",
            "status": status,
            "applied_standard": GROUNDED,
            "lens_id": lens_id,
            "object_scope": scope,
            "violations": violations,
            "citation_kinds": [c.get("kind") for c in classified],
            "n_repo": len(repo_findings),
            "n_external": len(external),
        }

    # IDEATION
    if external:
        if repo_findings:
            status = "FORBIDDEN_GROUNDING"
            violations.append(
                {
                    "code": "FORBIDDEN_GROUNDING",
                    "detail": (
                        "IDEATION lens cited this repository as the finding; "
                        "file:line is allowed only as already-present-negative"
                    ),
                }
            )
        else:
            status = "PASS"
    elif repo_findings:
        status = "FORBIDDEN_GROUNDING"
        violations.append(
            {
                "code": "FORBIDDEN_GROUNDING",
                "detail": "IDEATION lens grounded only in this repository",
            }
        )
    else:
        status = "ZERO_CITATION"
        violations.append(
            {
                "code": "ZERO_CITATION",
                "detail": "IDEATION lens produced no external URL/DOI",
            }
        )
    return {
        "compliant": status == "PASS",
        "status": status,
        "applied_standard": IDEATION,
        "lens_id": lens_id,
        "object_scope": scope,
        "violations": violations,
        "citation_kinds": [c.get("kind") for c in classified],
        "n_repo": len(repo_findings),
        "n_external": len(external),
        "n_already_present_negative": len(repo_negatives),
    }
