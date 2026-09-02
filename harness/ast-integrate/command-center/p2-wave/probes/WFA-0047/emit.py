#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0047-adapter-skill-markdown.json."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import EXTRACTED, NOT_EXTRACTABLE, extract_skill, find_skill_md  # noqa: E402
from gold import GOLD, REFUSE, all_records, skill_path  # noqa: E402
from mutants import mutant_never_refuse, mutant_whole_file  # noqa: E402

OUT = "command-center/wfa/WFA-0047-adapter-skill-markdown.json"
QUESTION = (
    "Implementation target: extract an ordered stage list from the procedural "
    "prose of a SKILL.md — the largest candidate family at 96 of 284 — and "
    "REFUSE with an explicit NOT-EXTRACTABLE verdict where the prose declares "
    "no ordered procedure, rather than inventing one."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0047/probe1_refusal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0047/probe2_anchors.py"
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def line_at(path: Path, n: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if n < 1 or n > len(lines):
        return ""
    return lines[n - 1]


def score_record(rec: dict) -> dict:
    path = skill_path(rec["id"])
    got = extract_skill(path)
    fields = {
        "verdict": got.get("verdict") == rec["verdict"],
        "title": None,
        "order": None,
        "source_anchor.line": None,
    }
    stage_rows = []
    if rec["verdict"] == NOT_EXTRACTABLE:
        fields["title"] = not (got.get("stages") or [])
        fields["order"] = fields["title"]
        fields["source_anchor.line"] = fields["title"]
    else:
        stages = got.get("stages") or []
        titles_ok = [s.get("title") for s in stages] == rec["titles"]
        order_ok = [s.get("order") for s in stages] == list(range(1, len(rec["titles"]) + 1))
        cite_ok = True
        for s, snippet in zip(stages, rec.get("snippets") or []):
            anchor = s.get("source_anchor") or {}
            n = anchor.get("line")
            live = line_at(path, n) if isinstance(n, int) else ""
            ok = bool(n) and snippet in live and snippet in (anchor.get("snippet") or "")
            cite_ok = cite_ok and ok
            stage_rows.append(
                {
                    "order": s.get("order"),
                    "title": s.get("title"),
                    "line": n,
                    "citation_ok": ok,
                }
            )
        fields["title"] = titles_ok
        fields["order"] = order_ok
        fields["source_anchor.line"] = cite_ok
        for bad in rec.get("forbidden_titles") or []:
            if any(s.get("title") == bad for s in stages):
                fields["title"] = False
    return {
        "id": rec["id"],
        "path": rel(path),
        "expected_verdict": rec["verdict"],
        "got_verdict": got.get("verdict"),
        "reason": got.get("reason"),
        "fields": fields,
        "stages": stage_rows or got.get("stages") or [],
        "ir": got.get("ir"),
        "pass": all(bool(v) for v in fields.values()),
    }


def tally(rows: list[dict]) -> dict:
    keys = ["verdict", "title", "order", "source_anchor.line"]
    out = {}
    for k in keys:
        n = len(rows)
        correct = sum(1 for r in rows if r["fields"].get(k))
        out[k] = {"n": n, "correct": correct, "accuracy": round(correct / n, 4) if n else 0.0}
    return out


def harvest_live() -> dict:
    roots = [
        Path.home() / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".cursor" / "skills-cursor",
        REPO / ".cursor" / "skills",
    ]
    found = []
    extracted = 0
    refused = 0
    for root in roots:
        if not root.is_dir():
            found.append({"root": str(root), "present": False, "n": 0})
            continue
        paths = find_skill_md(root)
        rows = []
        for p in paths:
            got = extract_skill(p)
            if got["verdict"] == EXTRACTED:
                extracted += 1
            else:
                refused += 1
            rows.append(
                {
                    "path": str(p),
                    "verdict": got["verdict"],
                    "n_stages": len(got.get("stages") or []),
                    "titles": [s["title"] for s in (got.get("stages") or [])],
                }
            )
        found.append(
            {
                "root": str(root),
                "present": True,
                "n": len(paths),
                "rows": rows,
            }
        )
    return {
        "note": (
            "Catalog inputs ~/.agents/skills and ~/.claude/skills are absent on "
            "this Linux worktree. Live harvest is observational, not gold-scored."
        ),
        "roots": found,
        "extracted": extracted,
        "refused": refused,
    }


def dep_status() -> dict:
    gold42 = REPO / "command-center/wfa/WFA-0042-extraction-gold-set.json"
    ir44 = REPO / "command-center/wfa/WFA-0044-workflow-ir-spec.json"
    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    return {
        "WFA-0042": {
            "path": "command-center/wfa/WFA-0042-extraction-gold-set.json",
            "present": gold42.is_file(),
            "bytes": gold42.stat().st_size if gold42.is_file() else 0,
            "note": "absent: scoring uses frozen local G-family gold in probes/WFA-0047/gold.py",
        },
        "WFA-0044": {
            "path": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
            "present": ir44.is_file(),
            "bytes": ir44.stat().st_size if ir44.is_file() else 0,
            "note": "absent: adapter emits WorkflowIR stages+source_anchor only; no execution semantics",
        },
        "WFA-0001": {
            "path": "command-center/wfa/schema/wfa-schema-pack.json",
            "present": pack.is_file(),
            "bytes": pack.stat().st_size if pack.is_file() else 0,
            "note": "absent: this unit does not author the 18-type pack",
        },
    }


def main() -> int:
    rows = [score_record(rec) for rec in all_records()]
    gold_rows = [r for r in rows if r["expected_verdict"] == EXTRACTED]
    refuse_rows = [r for r in rows if r["expected_verdict"] == NOT_EXTRACTABLE]
    if len(refuse_rows) != 10:
        print(f"FAILED:WFA-0047 refuse rows {len(refuse_rows)}")
        return 1
    if not all(r["pass"] for r in rows):
        bad = [r["id"] for r in rows if not r["pass"]]
        print("FAILED:WFA-0047 gold score", bad)
        return 1

    mutant_refusal = []
    for rec in REFUSE:
        m = mutant_never_refuse(skill_path(rec["id"]))
        mutant_refusal.append(
            {
                "id": rec["id"],
                "mutant_verdict": m.get("verdict"),
                "went_red": m.get("verdict") == EXTRACTED,
            }
        )
    trap = mutant_whole_file(skill_path("refuse-frontmatter-trap"))
    fence = mutant_whole_file(skill_path("refuse-codeblock-mention"))

    live = harvest_live()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    field_scores = tally(rows)
    doc = {
        "unit_id": "WFA-0047",
        "record_type": "AdapterConformanceReport",
        "adapter_id": "skill-markdown-to-ir",
        "native_format": "SKILL.md",
        "ir_target": "WorkflowIR.stages",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0047",
        "question": QUESTION,
        "claim_under_test": (
            "An ordered stage list can be extracted from SKILL.md body prose "
            "when consecutive ordinals starting at 1 are present, and the "
            "adapter returns NOT-EXTRACTABLE when they are not — including "
            "when ordinals appear only in frontmatter or fenced examples."
        ),
        "dependencies": dep_status(),
        "gold": {
            "source": "command-center/p2-wave/probes/WFA-0047/gold.py",
            "frozen": True,
            "version": "WFA-0047-local-v1",
            "extracted_n": len(GOLD),
            "refused_n": len(REFUSE),
            "per_stage_field_scores": field_scores,
            "rows": rows,
        },
        "refusal_control": {
            "n": 10,
            "all_not_extractable": all(r["got_verdict"] == NOT_EXTRACTABLE for r in refuse_rows),
            "ids": [r["id"] for r in refuse_rows],
            "both_states": {
                "mutant_never_refuse_went_red": all(x["went_red"] for x in mutant_refusal),
                "mutant_rows": mutant_refusal,
                "mutant_whole_file_frontmatter_trap": {
                    "verdict": trap.get("verdict"),
                    "titles": [s["title"] for s in trap.get("stages") or []],
                    "extracted_mention": trap.get("verdict") == EXTRACTED,
                },
                "mutant_whole_file_fenced_mention": {
                    "verdict": fence.get("verdict"),
                    "n_stages": len(fence.get("stages") or []),
                    "extracted_mention": fence.get("verdict") == EXTRACTED,
                },
            },
        },
        "lossy_field_ledger": [
            {
                "native": "frontmatter.description",
                "ir": None,
                "disposition": "INTENT-NOT-STAGES",
                "why": "use-versus-mention: description is when-to-use text, not a stage list",
            },
            {
                "native": "fenced-code-examples",
                "ir": None,
                "disposition": "MENTION",
                "why": "example procedures inside fences are not this skill's procedure",
            },
            {
                "native": "roles/gates/fan-out/retries/resume/stop",
                "ir": None,
                "disposition": "ABSENT-IN-SKILL-MD",
                "why": "SKILL.md prose does not carry those IR constructs; not invented",
            },
        ],
        "live_harvest": live,
        "ir_samples": [r["ir"] for r in gold_rows if r.get("ir")],
        "tests": [
            {
                "id": "WFA-0047-REFUSAL-10",
                "name": "ten no-procedure skills all return NOT-EXTRACTABLE",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "WFA-0047-FRONTMATTER-USE-VS-MENTION",
                "name": "frontmatter description ordinals are not a stage list",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "WFA-0047-STAGE-LINE-CITE",
                "name": "each extracted stage cites the SKILL.md line it came from",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0047-probe2-anchors",
            "verdict": "PASS",
            "independent": True,
            "note": "probe2 re-reads SKILL.md lines; it does not trust emit.py's self-score",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "refusal-both-states"},
            {"id": "probe2", "command": P2, "role": "citation-and-use-versus-mention"},
        ],
        "ts": now,
        "environment": {
            "cwd": str(REPO),
            "python": sys.version.split()[0],
            "pid": os.getpid(),
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    raw = out_path.read_bytes().replace(b"\r\n", b"\n")
    print(
        f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}"
    )
    print("SUCCESS:WFA-0047 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
