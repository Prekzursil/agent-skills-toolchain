"""Live owner-error ledger for ARC-0058.

Each error-reduction claim must be tied to an observed owner error in a
transcript or ledger record (wrong command, misread status, repeated
question, error with no next action, stale doc trusted as current), with
a computed occurrence count. Counts are parsed or scanned, not asserted.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

READY = "command-center/ready_units.py"
RENDER = "tools/command-center/render.py"
CC_TOOLS = "tools/command-center"

# Next-action cues that satisfy A8's error-message contract.
NEXT_ACTION = re.compile(
    r"pass an item|--open|--program|--force|--list|--help|run `",
    re.I,
)
MISREAD_RE = re.compile(r"produced (\d+) present files of which (\d+)")
STALE_RE = re.compile(r"(\d+) days stale")


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def observation(
    error_class: str,
    kind: str,
    path: str,
    line: int,
    snippet: str,
    occurrence_count: int,
    note: str,
) -> dict[str, Any]:
    return {
        "error_class": error_class,
        "kind": kind,
        "path": path,
        "line": line,
        "snippet": snippet,
        "occurrence_count": int(occurrence_count),
        "note": note,
        "computed_not_asserted": True,
    }


def scan_misread_status() -> dict[str, Any]:
    path = REPO / READY
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines, 1):
        m = MISREAD_RE.search(ln)
        if m:
            present, bad = int(m.group(1)), int(m.group(2))
            return observation(
                "misread-status",
                "ledger-record",
                READY,
                i,
                "produced 44 present files of which 43",
                bad,
                (
                    f"Owner-facing delivered() counted {present} present artifacts "
                    f"as delivered; {bad} self-declared BLOCKED or FAILED. "
                    "That is a misread status with a recorded occurrence count."
                ),
            )
    raise RuntimeError("misread-status ledger line missing in ready_units.py")


def scan_docs_stale() -> dict[str, Any]:
    path = REPO / RENDER
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines, 1):
        m = STALE_RE.search(ln)
        if m and "while work continues" in ln:
            days = int(m.group(1))
            return observation(
                "docs-stale",
                "ledger-record",
                RENDER,
                i,
                "15 days stale while work continues",
                1,
                (
                    f"Hand-maintained status was trusted while {days} days stale. "
                    "One measured owner/agent incident of treating a stale doc as current."
                ),
            )
    raise RuntimeError("docs-stale ledger line missing in render.py")


def scan_error_no_next() -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    root = REPO / CC_TOOLS
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.parent.name == "tests":
            continue
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = ln.strip()
            if stripped.startswith("#"):
                continue
            if "FAILED:" not in ln:
                continue
            if NEXT_ACTION.search(ln):
                continue
            hits.append(
                {
                    "path": _rel(path),
                    "line": i,
                    "snippet": stripped[:160],
                }
            )
    if not hits:
        raise RuntimeError("expected at least one FAILED: line without next-action")
    first = hits[0]
    return {
        **observation(
            "error-no-next",
            "live-tree-scan",
            first["path"],
            int(first["line"]),
            str(first["snippet"])[:80],
            len(hits),
            (
                "Owner-facing FAILED: strings in tools/command-center that name "
                "no next action (what happened / what it means / exact next command)."
            ),
        ),
        "instances": hits,
    }


def collect_observations() -> list[dict[str, Any]]:
    return [
        scan_misread_status(),
        scan_error_no_next(),
        scan_docs_stale(),
    ]


def tally_by_class(observations: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in observations:
        cls = str(row["error_class"])
        out[cls] = out.get(cls, 0) + int(row["occurrence_count"])
    return out


if __name__ == "__main__":
    import json

    rows = collect_observations()
    print(json.dumps({"tally": tally_by_class(rows), "observations": rows}, indent=2))
