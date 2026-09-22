#!/usr/bin/env python3
"""Set comparator for required vs emitted CI contexts (AUD-0044).

Produces:
  - required_but_never_emitted
  - emitted_but_not_required
  - intersection
  - headline counts
  - symmetric_difference (union of the two exclusive sets)
"""

from __future__ import annotations

from typing import Iterable


def normalize(name: str) -> str:
    return (name or "").strip()


def compare(required: Iterable[str], emitted: Iterable[str]) -> dict:
    req = {normalize(x) for x in required if normalize(x)}
    em = {normalize(x) for x in emitted if normalize(x)}
    intersection = sorted(req & em)
    required_but_never_emitted = sorted(req - em)
    emitted_but_not_required = sorted(em - req)
    symmetric_difference = sorted(required_but_never_emitted + emitted_but_not_required)
    return {
        "required_count": len(req),
        "emitted_count": len(em),
        "intersection": intersection,
        "intersection_count": len(intersection),
        "required_but_never_emitted": required_but_never_emitted,
        "required_but_never_emitted_count": len(required_but_never_emitted),
        "emitted_but_not_required": emitted_but_not_required,
        "emitted_but_not_required_count": len(emitted_but_not_required),
        "symmetric_difference": symmetric_difference,
        "symmetric_difference_count": len(symmetric_difference),
    }


def yaml_job_names(text: str) -> list[str]:
    """Extract top-level `jobs.<id>.name:` values from a GitHub Actions workflow.

    Intentionally minimal (no full YAML dependency): walks for `name:` under the
    `jobs:` block at indent depth of a job property (4 spaces under default GHA).
    """
    names: list[str] = []
    in_jobs = False
    for line in text.splitlines():
        if not in_jobs:
            if line.strip() == "jobs:" or line.startswith("jobs:"):
                in_jobs = True
            continue
        # leave jobs block if a new top-level key appears (no indent)
        if (
            line
            and not line.startswith(" ")
            and not line.startswith("\t")
            and line.rstrip().endswith(":")
        ):
            break
        # job property `name:` is typically indented 4 spaces
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent == 4 and stripped.startswith("name:"):
            val = stripped[len("name:") :].strip().strip("'\"")
            if val:
                names.append(val)
    return names
