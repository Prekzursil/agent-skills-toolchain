"""build/wfa-5 : extract machine-readable features from every on-disk executed
workflow script, join the run telemetry, and measure pairwise distinctness.

Reads only. Writes one intermediate JSON under command-center/.
"""

import glob
import json
import os
import re

PROJ = os.path.expanduser("~/.claude/projects")
OUT = "C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa5_features.json"
CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"

# ---------------------------------------------------------------- run telemetry
runs_by_id = {}
for p in glob.glob(os.path.join(PROJ, "*", "*", "workflows", "wf_*.json")):
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:  # noqa: BLE001
        continue
    rid = d.get("runId") or os.path.splitext(os.path.basename(p))[0]
    runs_by_id.setdefault(rid, []).append(
        {
            "record": p,
            "workflowName": d.get("workflowName"),
            "status": d.get("status"),
            "agentCount": d.get("agentCount"),
            "durationMs": d.get("durationMs"),
            "totalTokens": d.get("totalTokens"),
            "totalToolCalls": d.get("totalToolCalls"),
            "timestamp": d.get("timestamp"),
            "defaultModel": d.get("defaultModel"),
            "phase_titles": [
                x.get("title") for x in (d.get("phases") or []) if isinstance(x, dict)
            ],
            "logs_n": len(d.get("logs") or []),
            "result_ok": (d.get("result") or {}).get("ok")
            if isinstance(d.get("result"), dict)
            else None,
        }
    )

# ---------------------------------------------------------------- mechanism map
MECH = {
    "phase-declaration": r"\bphase\s*\(",
    "parallel-fanout": r"\bparallel\s*\(",
    "typed-schema-fanin": r"\bschema\s*:",
    "null-tolerant-barrier": r"filter\s*\(\s*Boolean\s*\)",
    "worktree-isolation": r"isolation\s*:\s*['\"]worktree|worktree",
    "longrun-wrapper": r"longrun",
    "adversarial-reviewer": r"adversar",
    "gate-verdict": r"\b(PASS|FAIL|APPROVE|BLOCK|GO|NO-GO|verdict)\b",
    "write-as-you-go": r"write[- ]?as[- ]?you[- ]?go|writeAsYouGo|skeleton",
    "retry-policy": r"\bretry|attempt\s*<|maxAttempts|twoStrikes|two-strikes",
    "bounded-loop": r"for\s*\(\s*let\s+\w+\s*=\s*0|while\s*\(|maxRounds|rounds\s*<",
    "per-unit-pipeline": r"work[- ]?unit|\bWU\d|per-unit|perUnit",
    "cross-vendor-codex": r"codex",
    "model-pinning": r"model\s*:\s*['\"]",
    "agent-type-routing": r"agentType\s*:",
    "explicit-timeout": r"timeout",
    "mcp-tool-call": r"mcp__[a-z0-9_-]+",
    "monitor-integration": r"Monitor|run_in_background|background",
    "self-repair-loop": r"self[- ]?repair|repair loop|fix loop|bounded self",
    "consensus-vote": r"consensus|unanim|majorit|vote|quorum",
    "dedup-or-merge": r"dedup|de-duplicat|merge[- ]?map|reconcil",
    "coverage-gate": r"coverage|--cov|threshold",
    "commit-stage": r"git commit|git add|stagedPaths|commit\(",
    "pr-stage": r"gh pr |pull request|createPullRequest",
}
TOOLS = {
    "Bash": r"\bBash\b|bash -|Bash\(",
    "Read": r"\bRead\b",
    "Write": r"\bWrite\b",
    "Grep": r"\bGrep\b",
    "Glob": r"\bGlob\b",
    "WebSearch": r"WebSearch|web_search",
    "WebFetch": r"WebFetch|web_fetch|firecrawl|tavily|exa",
    "git": r"\bgit \b",
    "gh": r"\bgh \b",
    "python": r"\bpython\b|pytest",
    "codex-cli": r"codex exec|codex mcp|mcp__codex",
    "playwright": r"playwright|browser_",
    "frida-adb": r"\bfrida\b|\badb\b",
}
STOP_PAT = re.compile(
    r"(?i)^.*?(stop(ping)?\s*(rule|when|condition)|until\s|halt|abort|"
    r"if\s*\(\s*!.*\)\s*(return|break)|break\s*;|return\s+out|"
    r"maxRounds|rounds\s*[<>=]|attempt\s*[<>=]|unanim|consensus|"
    r"all\s+must\s+(pass|approve)|blocking|NO-GO).*$"
)
FAIL_PAT = re.compile(
    r"(?i)(filter\s*\(\s*Boolean\s*\)|try\s*\{|catch\s*\(|\|\|\s*null|"
    r"\?\?\s*|killed|timeout|FAILED:|partial|degrade|fallback)"
)
LIC_PAT = re.compile(
    r"(?i)SPDX-License-Identifier|Copyright \(c\)|\bMIT License\b|Apache License"
)

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
STEM = re.compile(r"^(?P<name>.+?)-(?P<rid>wf_[0-9a-f]{3,}[0-9a-f-]*)$")


def norm_tokens(body: str) -> set:
    b = re.sub(r"//.*|/\*.*?\*/", " ", body, flags=re.S)
    return set(w.lower() for w in WORD.findall(b))


records = []
paths = sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "scripts", "*")))
for p in paths:
    base = os.path.basename(p)
    stem = os.path.splitext(base)[0]
    m = STEM.match(stem)
    name = m.group("name") if m else stem
    rid = m.group("rid") if m else None
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except Exception as exc:  # noqa: BLE001
        records.append({"path": p, "read_error": str(exc)})
        continue
    lines = body.splitlines()

    def first_line(pat):
        rx = re.compile(pat)
        for i, ln in enumerate(lines, 1):
            if rx.search(ln):
                return i, ln.strip()[:220]
        return None, None

    mech = {}
    for k, pat in MECH.items():
        hits = len(re.findall(pat, body))
        if hits:
            ln, txt = first_line(pat)
            mech[k] = {"hits": hits, "line": ln, "anchor_text": txt}
    tools = sorted(k for k, pat in TOOLS.items() if re.search(pat, body))

    mm = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", body)
    md = re.search(r"description\s*:\s*['\"]([^'\"]{0,400})['\"]", body)
    stages = [
        {"title": t, "detail": d[:220]}
        for t, d in re.findall(
            r"\{\s*title\s*:\s*['\"]([^'\"]+)['\"]\s*,\s*detail\s*:\s*['\"]([^'\"]*)['\"]",
            body,
        )
    ]
    if not stages:
        stages = [
            {"title": t, "detail": ""}
            for t in re.findall(r"phase\s*\(\s*['\"]([^'\"]+)['\"]", body)
        ]
    labels = sorted(set(re.findall(r"label\s*:\s*[`'\"]([^`'\"$]{2,60})", body)))
    agent_types = sorted(set(re.findall(r"agentType\s*:\s*['\"]([^'\"]+)['\"]", body)))
    models = sorted(set(re.findall(r"model\s*:\s*['\"]([^'\"]+)['\"]", body)))

    stops = []
    for i, ln in enumerate(lines, 1):
        if STOP_PAT.match(ln) and len(stops) < 6:
            stops.append({"line": i, "text": ln.strip()[:200]})
    fails = sorted(set(x.group(0).strip() for x in FAIL_PAT.finditer(body)))[:10]

    tel = runs_by_id.get(rid, []) if rid else []
    records.append(
        {
            "path": p,
            "name": name,
            "runId": rid,
            "meta_name": mm.group(1) if mm else None,
            "description": md.group(1) if md else None,
            "bytes": len(body),
            "lines": len(lines),
            "mtime": os.path.getmtime(p),
            "stages": stages[:14],
            "agent_sites": len(re.findall(r"\bagent\s*\(", body)),
            "parallel_sites": len(re.findall(r"\bparallel\s*\(", body)),
            "labels": labels[:25],
            "agent_types": agent_types,
            "models": models,
            "mechanisms": mech,
            "tools": tools,
            "stop_rule_lines": stops,
            "failure_constructs": fails,
            "license_header_hits": len(LIC_PAT.findall(body)),
            "telemetry": tel,
            "_tokens": sorted(norm_tokens(body)),
        }
    )

# ------------------------------------------------------- detector control (S3b)
ctrl_hit = None
for cand in glob.glob(
    "C:/Users/Prekzursil/source/ast-integrate/**/*.py", recursive=True
)[:4000]:
    try:
        with open(cand, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
    except Exception:  # noqa: BLE001
        continue
    if LIC_PAT.search(t):
        ctrl_hit = cand
        break

# --------------------------------------------------------- pairwise distinctness
ok = [r for r in records if "_tokens" in r]
toks = [set(r["_tokens"]) for r in ok]
n = len(ok)
nn = []
for i in range(n):
    best, bj = None, 0.0
    for j in range(n):
        if i == j:
            continue
        a, b = toks[i], toks[j]
        if not a or not b:
            continue
        inter = len(a & b)
        jac = inter / float(len(a | b))
        if jac > bj:
            bj, best = jac, j
    nn.append(
        {
            "nearest": ok[best]["name"] if best is not None else None,
            "jaccard": round(bj, 4),
        }
    )
for r, x in zip(ok, nn):
    r["nearest_neighbour"] = x

for r in records:
    r.pop("_tokens", None)

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(
        {
            "scripts_scanned": len(records),
            "run_records_indexed": sum(len(v) for v in runs_by_id.values()),
            "license_detector_control_file": ctrl_hit,
            "records": records,
        },
        fh,
        indent=1,
    )
print("scripts scanned      :", len(records))
print("run records indexed  :", sum(len(v) for v in runs_by_id.values()))
print("licence detector control (known-present header):", ctrl_hit)
print(
    "scripts with a licence header of their own     :",
    sum(1 for r in records if r.get("license_header_hits")),
)
print("wrote", OUT)
