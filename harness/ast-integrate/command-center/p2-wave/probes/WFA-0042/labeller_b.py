"""Labeller B — token / prose scan with a different vocabulary than A.

Does not walk JSON keys that A uses as its primary signal. Looks at body
tokens, nested license strings, markdown numbered lists, and tool names.
Absence of a benchmark *token* is EMPTY (not HONEST-NULL): B refuses A's
near-zero prior. Independent of labeller_a / labeller_c.
"""
from __future__ import annotations

import re
from typing import Any

from dimensions import DIMENSIONS, empty_cell, evidenced

SPDX_TOKEN = re.compile(
    r"\b(MIT|Apache-2\.0|BSD-2-Clause|BSD-3-Clause|GPL-2\.0|GPL-3\.0|"
    r"LGPL-3\.0|MPL-2\.0|ISC|UNLICENSED|CC-BY-4\.0)\b"
)
GIT_SHA = re.compile(r"\b[0-9a-f]{40}\b")
FILE_LINE = re.compile(r"\b[\w./-]+\.(?:py|md|json|js|mjs|yml):(\d+)\b")
ROLE_TOKEN = re.compile(
    r"\b(reviewer|critic|judge|scribe|chair|moderator|operator|juror|"
    r"owner-veto|subagent)\b",
    re.I,
)
STAGE_HEAD = re.compile(
    r"^#{1,6}\s*((?:stage|step|phase|round)\s+\d+)\b",
    re.I | re.M,
)
PHASE_CALL = re.compile(r"\bphase\s*\(", re.I)
STOP_TOKEN = re.compile(
    r"\b(halt|max_stages|stop when|stop_rule|until the|fail-closed|"
    r"stopping point|on_error)\b",
    re.I,
)
TOOL_TOKEN = re.compile(
    r"\b(Read|Write|Edit|Grep|Glob|Bash|WebFetch|WebSearch|Task|"
    r"mcp__[A-Za-z0-9_]+__[A-Za-z0-9_]+)\b",
)
FAIL_TOKEN = re.compile(
    r"\b(timeout|hung unit|stall|dead monitor|partial result|"
    r"fail-closed|on_error|barrier-without-timeout)\b",
    re.I,
)
BENCH_TOKEN = re.compile(
    r"\bindependently_reproduced\b|\breproduction_status\b|"
    r"\bclaimed_delta\b|\bBenchmarkRecord\b",
)
MAINT_TOKEN = re.compile(r"\b(unmaintained|archived|stale|active-maintenance)\b", re.I)


def _first(rx: re.Pattern[str], text: str) -> str:
    match = rx.search(text)
    return match.group(0) if match else ""


def label_source(src: dict[str, Any]) -> dict[str, dict[str, Any]]:
    text = src["text"]
    out: dict[str, dict[str, Any]] = {}

    lic = SPDX_TOKEN.search(text)
    if lic:
        out["license"] = evidenced(lic.group(1), anchor=f"{src['path']}:spdx-token")
    else:
        out["license"] = empty_cell(note="no SPDX token in body")

    maint_hit = MAINT_TOKEN.search(text)
    if maint_hit:
        out["maintenance"] = evidenced(
            maint_hit.group(1).lower(), anchor=f"{src['path']}:maint-token"
        )
    else:
        out["maintenance"] = evidenced(
            "present-on-tree", anchor=src["path"], note="live nonempty file"
        )

    sha = GIT_SHA.search(text)
    loc = FILE_LINE.search(text)
    if sha:
        out["provenance"] = evidenced(sha.group(0), anchor=f"{src['path']}:git-sha")
    elif loc:
        out["provenance"] = evidenced(loc.group(0), anchor=f"{src['path']}:file-line")
    else:
        out["provenance"] = empty_cell(note="no git-sha or file:line token")

    roles = sorted({m.group(1).lower() for m in ROLE_TOKEN.finditer(text)})
    if roles:
        out["roles"] = evidenced(",".join(roles[:8]), anchor=f"{src['path']}:role-token")
    else:
        out["roles"] = empty_cell(note="no role tokens")

    heads = [m.group(1).lower() for m in STAGE_HEAD.finditer(text)]
    if heads:
        out["stages"] = evidenced(",".join(heads[:8]), anchor=f"{src['path']}:heading")
    elif PHASE_CALL.search(text):
        out["stages"] = evidenced("phase()", anchor=f"{src['path']}:phase-call")
    elif re.search(r"\b(nodes|steps|pipeline)\b", text, re.I) and (
        '"kind"' in text or "kind:" in text or "pipeline" in text.lower()
    ):
        out["stages"] = evidenced("nodes/steps/pipeline", anchor=src["path"])
    else:
        out["stages"] = empty_cell(note="no stage headings/nodes/phase()")

    stop = STOP_TOKEN.search(text)
    if stop:
        out["stop_rules"] = evidenced(stop.group(0).lower(), anchor=f"{src['path']}:stop-token")
    else:
        out["stop_rules"] = empty_cell(note="no stop/halt token")

    tools = sorted({m.group(1) for m in TOOL_TOKEN.finditer(text)})
    if tools:
        out["tools"] = evidenced(",".join(tools[:10]), anchor=f"{src['path']}:tool-token")
    else:
        out["tools"] = empty_cell(note="no named tool tokens")

    out["task_fit"] = evidenced(src["family"], anchor=src["path"], note="sampling family")

    fail = FAIL_TOKEN.search(text)
    if fail:
        out["failure_behaviour"] = evidenced(
            fail.group(0).lower(), anchor=f"{src['path']}:fail-token"
        )
    else:
        out["failure_behaviour"] = empty_cell(note="no failure-mode token")

    bench = BENCH_TOKEN.search(text)
    if bench:
        out["benchmark_evidence"] = evidenced(
            bench.group(0), anchor=f"{src['path']}:bench-token"
        )
    else:
        out["benchmark_evidence"] = empty_cell(
            note="no reproduction/benchmark token; B does not apply A's prior"
        )

    missing = [d for d in DIMENSIONS if d not in out]
    if missing:
        raise RuntimeError(f"labeller B missed {missing}")
    return out
