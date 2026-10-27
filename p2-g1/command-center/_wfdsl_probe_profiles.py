#!/usr/bin/env python3
"""Second pass: fix the tool-token regex, then measure PROFILE-level pass/fail unions.

Read-only. Emits JSON to stdout.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "WORK-UNIT-CATALOG.json"

ID_RE = re.compile(r"^[A-Z]{2,4}-[0-9]{4}$")
BUCKET_RE = re.compile(r"^B[0-9]{2}$")
# corrected: mcp tool method segments legitimately contain hyphens (mcp__codex__codex-reply)
# and a wildcard form is used for tool FAMILIES; an optional parenthetical carries scope prose.
TOOL_RE = re.compile(
    r"^(?:"
    r"[A-Z][A-Za-z0-9]*"
    r"|[A-Z][A-Za-z0-9]*:[A-Za-z0-9_.\-]+"
    r"|mcp__[a-z0-9_.\-]+__(?:[A-Za-z0-9_\-]+|\*)"
    r")(?:\s*\([^)]*\))?$"
)
REL_PATH_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._\-/]*$")
SCHEMA_REF_RE = re.compile(
    r"^(?:https?://[^\s#]+(?:#[^\s]*)?|[A-Za-z0-9._][A-Za-z0-9._\-/]*\.json(?:#[^\s]*)?)$"
)
AMVR_STR_RE = re.compile(r"^[^/\s]+/[^/\s]+/[^/]+$")
FAILCLS_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PHASE_RE = re.compile(r"^(?:[0-9]|1[0-9]|2[0-9])[A-Z]?$")
SUBSTRATES = {
    "local-parallel",
    "local-serialized",
    "worktree-isolated",
    "cloud-batch",
    "local-windows-pwsh7",
    "databricks-job",
    "modal-sandbox",
    "container",
}


def structural_fails(u: dict) -> list[str]:
    f = []
    a = u.get("assigned_model_vendor_role")
    if not (
        (isinstance(a, dict) and {"model", "vendor", "role"} <= set(a))
        or (isinstance(a, str) and AMVR_STR_RE.match(a))
    ):
        f.append("amvr-shape")
    if not (
        isinstance(u.get("inputs"), list)
        and u["inputs"]
        and all(isinstance(x, str) and x.strip() for x in u["inputs"])
    ):
        f.append("inputs")
    if not (
        isinstance(u.get("dependencies"), list)
        and all(isinstance(x, str) and x.strip() for x in u["dependencies"])
    ):
        f.append("dependencies")
    if not (isinstance(u.get("tool_permissions"), list) and u["tool_permissions"]):
        f.append("tool_permissions")
    t = u.get("tests_required")
    if not ((isinstance(t, list) and t) or (isinstance(t, str) and len(t) >= 10)):
        f.append("tests_required")
    c = u.get("failure_classification")
    if not ((isinstance(c, list) and c) or (isinstance(c, str) and len(c) >= 3)):
        f.append("failure_classification")
    if not (
        isinstance(u.get("timeout_seconds"), int)
        and not isinstance(u["timeout_seconds"], bool)
        and 60 <= u["timeout_seconds"] <= 86400
    ):
        f.append("timeout_seconds")
    if not isinstance(u.get("owner_approval_required"), bool):
        f.append("owner_approval_required")
    for k, mn in (
        ("title", 3),
        ("question_or_target", 10),
        ("evidence_requirement", 20),
        ("reviewer_requirement", 10),
        ("completion_sentinel", 8),
        ("retry_policy", 10),
        ("output_path", 3),
        ("output_schema", 3),
        ("phase", 1),
        ("id", 4),
    ):
        v = u.get(k)
        if not (isinstance(v, str) and len(v) >= mn):
            f.append(k)
    return f


def normative_fails(u: dict) -> list[str]:
    f = list(structural_fails(u))
    if not ID_RE.match(u["id"]):
        f.append("id-pattern")
    if not PHASE_RE.match(u["phase"]):
        f.append("phase-pattern")
    if u["execution_substrate"] not in SUBSTRATES:
        f.append("substrate-enum")
    if not (REL_PATH_RE.match(u["output_path"]) and ".." not in u["output_path"]):
        f.append("output_path-form")
    if not all(ID_RE.match(t) or BUCKET_RE.match(t) for t in u["dependencies"]):
        f.append("dep-token-form")
    if not all(TOOL_RE.match(t) for t in u["tool_permissions"] if isinstance(t, str)):
        f.append("tool-token-form")
    if not SCHEMA_REF_RE.match(u["output_schema"]):
        f.append("output_schema-ref-form")
    cls = u["failure_classification"]
    if isinstance(cls, list) and not all(
        isinstance(t, str) and FAILCLS_RE.match(t) for t in cls
    ):
        f.append("failcls-token-form")
    return f


def strict_fails(u: dict) -> list[str]:
    f = list(normative_fails(u))
    if not isinstance(u["assigned_model_vendor_role"], dict):
        f.append("amvr-must-be-object")
    if not isinstance(u["tests_required"], list):
        f.append("tests_required-must-be-array")
    if not isinstance(u["failure_classification"], list):
        f.append("failure_classification-must-be-array")
    return f


def main() -> int:
    d = json.loads(CATALOG.read_text(encoding="utf-8"))
    wu = d["work_units"]
    ids = {u["id"] for u in wu}
    out: dict[str, object] = {"n": len(wu)}

    for name, fn in (
        ("structural", structural_fails),
        ("normative", normative_fails),
        ("strict", strict_fails),
    ):
        reasons: Counter = Counter()
        failing = []
        for u in wu:
            fl = fn(u)
            if fl:
                failing.append(u["id"])
                for r in fl:
                    reasons[r] += 1
        out[name] = {
            "pass": len(wu) - len(failing),
            "fail": len(failing),
            "reason_histogram": dict(reasons.most_common()),
            "sample_fail": failing[:15],
        }

    # semantic (cross-field / referential) rules a JSON Schema cannot express
    sem: dict[str, object] = {}
    unresolved = [
        (
            u["id"],
            [t for t in u["dependencies"] if t not in ids and not BUCKET_RE.match(t)],
        )
        for u in wu
    ]
    unresolved = [(i, t) for i, t in unresolved if t]
    sem["SEM-001_dependency_resolvable"] = {
        "violations": len(unresolved),
        "refs": sum(len(t) for _, t in unresolved),
        "sample": unresolved[:12],
    }
    bad_sent = [
        u["id"] for u in wu if ("SUCCESS:" + u["id"]) not in u["completion_sentinel"]
    ]
    sem["SEM-002_sentinel_names_own_id"] = {
        "violations": len(bad_sent),
        "sample": bad_sent[:12],
    }
    dup = [i for i, c in Counter(u["id"] for u in wu).items() if c > 1]
    sem["SEM-003_unique_ids"] = {"violations": len(dup), "sample": dup[:12]}
    pc = Counter(u["output_path"] for u in wu)
    dpaths = [(p, c) for p, c in pc.items() if c > 1]
    sem["SEM-004_unique_output_path"] = {
        "violations": len(dpaths),
        "sample": dpaths[:12],
    }
    selfdep = [u["id"] for u in wu if u["id"] in u["dependencies"]]
    sem["SEM-005_no_self_dependency"] = {"violations": len(selfdep), "sample": selfdep}

    # cycle detection over unit-id edges only
    graph = {u["id"]: [t for t in u["dependencies"] if t in ids] for u in wu}
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    cycles: list[list[str]] = []
    for start in graph:
        if color[start] != WHITE:
            continue
        stack = [(start, iter(graph[start]))]
        color[start] = GREY
        path = [start]
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color.get(nxt, BLACK) == GREY:
                    if len(cycles) < 10:
                        cycles.append(path[path.index(nxt) :] + [nxt])
                elif color.get(nxt, BLACK) == WHITE:
                    color[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, iter(graph[nxt])))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
                if path:
                    path.pop()
    sem["SEM-006_no_dependency_cycle"] = {
        "violations": len(cycles),
        "sample": cycles[:5],
    }
    out["semantic_rules"] = sem

    # who are the 96 / 128 outlier blocks
    out["outlier_blocks"] = {
        "string_amvr": dict(
            Counter(
                u["_source_slice_file"]
                for u in wu
                if isinstance(u["assigned_model_vendor_role"], str)
            ).most_common()
        ),
        "string_tests_required": dict(
            Counter(
                u["_source_slice_file"]
                for u in wu
                if isinstance(u["tests_required"], str)
            ).most_common()
        ),
        "output_schema_prose": dict(
            Counter(
                u["_source_slice_file"] for u in wu if " " in u["output_schema"]
            ).most_common()
        ),
        "dep_token_bad": dict(
            Counter(
                u["_source_slice_file"]
                for u in wu
                if not all(
                    ID_RE.match(t) or BUCKET_RE.match(t) for t in u["dependencies"]
                )
            ).most_common()
        ),
    }
    json.dump(out, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
