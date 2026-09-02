"""Deterministic 36-record control reconstructions for the 08 and 09 pairs.

Not the live 284-candidate / 108-blueprint corpora. Traps are planted so
the heading regex can be proven silent on the measured false-positive class.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONTROL = HERE / "fixtures" / "control"

FAMILIES: list[tuple[str, str, str]] = [
    ("A-saved-workflow", "wf-saved-control", "bp-saved-control"),
    ("B-repo-workflow", "wf-repo-control", "bp-repo-control"),
    ("C-repo-tool", "wf-tool-control", "bp-tool-control"),
    ("D-harness-runtime", "wf-harness-control", "bp-harness-control"),
    ("E-agent", "wf-agent-control", "bp-agent-control"),
    ("F-plugin", "wf-plugin-control", "bp-plugin-control"),
    ("G-skill", "wf-skill-control", "bp-skill-control"),
    ("H-executed-corpus", "wf-exec-control", "bp-exec-control"),
    ("I-command", "cmd-control", "bp-cmd-control"),
]

CLASSIFICATIONS = [
    "ADOPT-AS-IS",
    "UNKNOWN-NEEDS-PROBE",
    "DISTILL",
    "RETIRE",
    "ADOPT-WITH-WRAPPER",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "SPECIALIZE",
]
LICENCES = ["MIT", "Apache-2.0", "BSD-3-Clause", "GPL-3.0"]

PAIR_FILES = {
    "08": {
        "md": "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
        "json": "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "array": "candidates",
        "title": "Workflow archaeology and source catalog (control reconstruction)",
        "prefix": 1,
    },
    "09": {
        "md": "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
        "json": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "array": "blueprints",
        "title": "Workflow blueprint library (control reconstruction)",
        "prefix": 2,
    },
}


def records_for(pair: str) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []
    pidx = 1 if pair == "08" else 2
    for fam, p08, p09 in FAMILIES:
        prefix = p08 if pair == "08" else p09
        for i in range(1, 5):
            n = len(recs)
            recs.append(
                {
                    "id": f"{prefix}-{i:02d}",
                    "family": fam,
                    "classification": CLASSIFICATIONS[n % len(CLASSIFICATIONS)],
                    "licence": LICENCES[n % len(LICENCES)],
                    "name": f"{prefix}-{i:02d}",
                }
            )
        _ = pidx
    return recs


def render_markdown(title: str, recs: list[dict[str, str]], pair: str) -> str:
    body_trap = "wf-body-mention-trap" if pair == "08" else "bp-body-mention-trap"
    inline_trap = (
        "wf-inline-heading-mention" if pair == "08" else "bp-inline-heading-mention"
    )
    lines = [
        f"# {title}",
        "",
        "Control reconstruction for WFA-0011. Not the live 284/108 corpus.",
        "",
        f"The id `{body_trap}` is backtick-delimited in prose and is not a heading.",
        "",
        "## Background",
        "",
        "Planted non-id heading. The honest heading regex must stay silent.",
        "",
        f"## Overview of `{inline_trap}`",
        "",
        "Heading that mentions a backtick-delimited id; it is not an id heading.",
        "",
    ]
    for rec in recs:
        lines.extend(
            [
                f"## `{rec['id']}`",
                "",
                f"- classification: {rec['classification']}",
                f"- licence: {rec['licence']}",
                f"- family: {rec['family']}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def render_json(pair: str, recs: list[dict[str, str]]) -> dict[str, Any]:
    meta = PAIR_FILES[pair]
    key = meta["array"]
    rows = []
    for rec in recs:
        rows.append(
            {
                "classification": rec["classification"],
                "does": "control-reconstruction",
                "evidence": "WFA-0011-control",
                "family": rec["family"],
                "id": rec["id"],
                "license": rec["licence"],
                "maintenance": "control",
                "mechanisms": [],
                "name": rec["name"],
                "notes": "control row; not a live registry record",
                "origin": "control",
                "provenance": "WFA-0011-control",
                "runtime": "n/a",
            }
        )
    return {
        "artifact": f"WFA-0011-control-{pair}",
        key: rows,
        "classification_vocabulary": list(CLASSIFICATIONS),
        "counts": {"n": len(rows), "families": 9},
        "generated_by": "command-center/p2-wave/probes/WFA-0011/fixtures.py",
        "mirror": meta["md"],
        "source_of_truth_ref": "control-reconstruction-not-live-corpus",
        "note": (
            "Not the live 284-row candidate registry or 108-row blueprint "
            "library. Control corpus for the MD/JSON parity gate."
        ),
    }


def write_control(dest: Path | None = None) -> dict[str, Path]:
    dest = CONTROL if dest is None else dest
    dest.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for pair, meta in PAIR_FILES.items():
        recs = records_for(pair)
        md_path = dest / meta["md"]
        js_path = dest / meta["json"]
        md_path.write_text(render_markdown(meta["title"], recs, pair), encoding="utf-8")
        js_path.write_text(
            json.dumps(render_json(pair, recs), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written[f"{pair}_md"] = md_path
        written[f"{pair}_json"] = js_path
    return written


def control_paths() -> dict[str, Path]:
    return {
        "08_md": CONTROL / PAIR_FILES["08"]["md"],
        "08_json": CONTROL / PAIR_FILES["08"]["json"],
        "09_md": CONTROL / PAIR_FILES["09"]["md"],
        "09_json": CONTROL / PAIR_FILES["09"]["json"],
    }


if __name__ == "__main__":
    paths = write_control()
    for k, p in paths.items():
        print(f"{k} {p} bytes={p.stat().st_size}")
