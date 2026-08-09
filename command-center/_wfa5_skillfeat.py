"""build/wfa-5 : deep feature extraction for the 32 candidates in registry slice 129-160.

For each candidate skill:
  * every on-disk copy (live agents vault, live claude vault, repo HEAD, pinned 07f465f3)
    with byte sizes -> two-directional drift is measured, not assumed
  * frontmatter, headings (stages), role tokens, tool surface, stop rules, failure
    behaviour, measurement/benchmark sentences, licence anchors
  * git last-commit ISO for the repo path (maintenance state)
  * USAGE evidence: how many executed-workflow scripts / run records name the skill
  * pairwise token-Jaccard among the 32 bodies (anti-padding / renamed-copy control)

Reads only. Emits _wfa5_skillfeat.json.
"""

import glob
import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(REPO, "command-center", "_wfa5_skillfeat.json")
RESOLVE = os.path.join(REPO, "command-center", "_wfa5_resolve.json")
PINNED = "07f465f37d49710f7060dcc7b567d6c58213177b"
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, ".claude", "projects")

with open(RESOLVE, encoding="utf-8") as fh:
    rows = json.load(fh)["rows"]


def sh(args, cwd=REPO):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout or ""), (r.stderr or "")[:200]
    except Exception as exc:  # noqa: BLE001
        return -1, "", str(exc)[:200]


HEAD_RE = re.compile(r"^(#{2,4})\s+(.{2,110}?)\s*$")
STEP_RE = re.compile(
    r"(?i)\b(G[0-9]\b|step\s+\d+|phase\s+\d+|wave\s+[0-9a-z]|stage\s+\d+|round\s+\d+)"
)
ROLE_RE = re.compile(
    r"(?i)\b([a-z][a-z-]{2,24}(?:-(?:reviewer|critic|auditor|architect|analyst|judge|"
    r"operator|engineer|planner|designer|scout|lead|worker|adversary)))\b"
)
ROLE_LIST_RE = re.compile(
    r"(?i)(?:agents?|personas?|reviewers?|lenses|roles?)\s*[:(]\s*([^\n)]{6,180})"
)
MCP_RE = re.compile(r"mcp__[a-z0-9_-]+")
TOOLNAME_RE = re.compile(
    r"\b(Bash|Read|Write|Edit|Grep|Glob|Task|WebSearch|WebFetch|TodoWrite|NotebookEdit|"
    r"SendMessage|Monitor|AskUserQuestion|playwright|ffmpeg|pytest|ruff|semgrep|lizard|gh|git)\b"
)
STOP_RE = re.compile(
    r"(?i)(stop(?:ping)?\s+(?:rule|when|condition|criteri)|until\s+\w|"
    r"all\s+(?:must|\d+)\s+(?:pass|approve|agree)|halt|abort|"
    r"blocking\s+gate|revert[- ]gate|max(?:imum)?\s+(?:rounds?|reflections?|attempts?|iterations?)|"
    r"threshold|convergen|saturation|quorum|unanim|consensus|two[- ]strikes|cap(?:ped)?\s+at)"
)
FAIL_RE = re.compile(
    r"(?i)(shadow[- ]mode|advisory\s+only|never\s+blocks?|fail[- ]open|fallback|degrade[sd]?\s+gracefully|"
    r"retry|two[- ]strikes|timeout|escalat|partial\s+result|filter\(Boolean\)|abort\s+cleanly|"
    r"observe\s*\+\s*log)"
)
MEAS_RE = re.compile(
    r"(?i)(measured\s+20\d\d-\d\d-\d\d|measured[: ]|\b\d{1,3}(?:\.\d+)?%|\b\d+\s*/\s*\d+\b|"
    r"\bn\s*=\s*\d+|ledger[- ]proven|arxiv|\b20\d\d\.\d{4,5}\b|benchmark|kappa|accuracy)"
)
LIC_RE = re.compile(
    r"(?i)(SPDX-License-Identifier[^\n]{0,60}|MIT(?:\s+licen[cs]e)?|Apache[- ]2\.0|BSD-[23]|GPL|"
    r"CC\s?BY(?:-SA)?(?:\s?4\.0)?|licen[cs]e\s*[:=]\s*[^\n]{0,60}|proprietar|all rights reserved|"
    r"copyright\s*\(c\)[^\n]{0,60}|rider)"
)
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")

# ---------------------------------------------------------------- usage evidence
names = [r["skill_dir_name"] for r in rows]
usage = {n: {"scripts": [], "run_records": 0} for n in names}
for p in sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "scripts", "*"))):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except Exception:  # noqa: BLE001
        continue
    low = body.lower()
    for n in names:
        if n.lower() in low:
            usage[n]["scripts"].append(os.path.basename(p))
for p in sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "wf_*.json"))):
    try:
        with open(p, encoding="utf-8", errors="replace") as fh:
            low = fh.read().lower()
    except Exception:  # noqa: BLE001
        continue
    for n in names:
        if n.lower() in low:
            usage[n]["run_records"] += 1

# detector control for the usage scan: a token that must appear, and one that must not
ctrl_present = 0
ctrl_absent = 0
for p in sorted(glob.glob(os.path.join(PROJ, "*", "*", "workflows", "scripts", "*")))[
    :200
]:
    with open(p, encoding="utf-8", errors="replace") as fh:
        low = fh.read().lower()
    ctrl_present += 1 if "agent(" in low else 0
    ctrl_absent += 1 if "zzq-not-a-real-token-7f31" in low else 0

out_rows = []
bodies = []
for r in rows:
    name = r["skill_dir_name"]
    live = r["found"].get("agents-live") or r["found"].get("claude-live")
    primary = live["skill_md"] if live else None
    body = ""
    if primary:
        with open(primary, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    lines = body.splitlines()

    fm = {}
    if lines and lines[0].strip() == "---":
        for i, ln in enumerate(lines[1:60], 2):
            if ln.strip() == "---":
                break
            m = re.match(r"^([A-Za-z_-]+)\s*:\s*(.*)$", ln)
            if m:
                fm[m.group(1)] = m.group(2)[:400]

    headings = []
    for i, ln in enumerate(lines, 1):
        m = HEAD_RE.match(ln)
        if m and len(headings) < 30:
            headings.append({"line": i, "level": len(m.group(1)), "text": m.group(2)})

    def hits(rx, cap=8, want_lines=True):
        acc = []
        for i, ln in enumerate(lines, 1):
            m = rx.search(ln)
            if m:
                acc.append(
                    {"line": i, "text": ln.strip()[:200]} if want_lines else m.group(0)
                )
                if len(acc) >= cap:
                    break
        return acc

    roles = sorted(set(x.lower() for x in ROLE_RE.findall(body)))[:20]
    role_lists = [x.strip()[:180] for x in ROLE_LIST_RE.findall(body)][:6]
    tools = sorted(set(TOOLNAME_RE.findall(body)))
    mcps = sorted(set(MCP_RE.findall(body)))[:14]

    # every copy + drift
    copies = {}
    for k, v in r["found"].items():
        copies[k] = {"path": v["skill_md"], "bytes": v["bytes"]}
    rel = "skills/%s/SKILL.md" % name
    rc, head_bytes, _ = sh(["git", "cat-file", "-s", "HEAD:%s" % rel])
    rc2, pin_bytes, _ = sh(["git", "cat-file", "-s", "%s:%s" % (PINNED, rel)])
    rc3, gitlog, _ = sh(
        ["git", "log", "-1", "--format=%cI %h", "--", "skills/%s" % name]
    )
    rc4, gitlog_agents, _ = sh(
        ["git", "log", "-1", "--format=%cI %h", "--", ".agents/skills/%s" % name]
    )
    lic_files = []
    for k, v in r["found"].items():
        d = os.path.dirname(v["skill_md"])
        for f in os.listdir(d):
            if re.match(r"(?i)^(licen[cs]e|notice|copying)", f):
                lic_files.append(os.path.join(d, f).replace("\\", "/"))

    out_rows.append(
        {
            "registry_index": r["registry_index"],
            "prior_id": r["prior_id"],
            "skill_dir_name": name,
            "prior_record": r["prior_record"],
            "primary_path": (primary or "").replace("\\", "/"),
            "bytes": len(body),
            "lines": len(lines),
            "mtime_epoch": live["mtime_epoch"] if live else None,
            "frontmatter": fm,
            "copies": copies,
            "git_head_blob_bytes": head_bytes.strip() if rc == 0 else None,
            "git_pinned_blob_bytes": pin_bytes.strip() if rc2 == 0 else None,
            "git_last_commit_skills": gitlog.strip() or None,
            "git_last_commit_agents_skills": gitlog_agents.strip() or None,
            "licence_files_in_dir": sorted(set(lic_files))[:6],
            "headings": headings,
            "step_tokens": sorted(
                set(x.strip().lower() for x in STEP_RE.findall(body))
            )[:16],
            "roles": roles,
            "role_lists": role_lists,
            "tools": tools,
            "mcp_tools": mcps,
            "stop_rule_hits": hits(STOP_RE),
            "failure_hits": hits(FAIL_RE),
            "measurement_hits": hits(MEAS_RE, cap=6),
            "licence_hits": hits(LIC_RE, cap=6),
            "usage": {
                "executed_scripts_naming_it": len(usage[name]["scripts"]),
                "example_scripts": usage[name]["scripts"][:4],
                "run_records_naming_it": usage[name]["run_records"],
            },
        }
    )
    bodies.append(set(w.lower() for w in WORD.findall(body)))

# pairwise distinctness among the 32
for i, r in enumerate(out_rows):
    best, bj = None, 0.0
    for j in range(len(out_rows)):
        if i == j:
            continue
        a, b = bodies[i], bodies[j]
        if not a or not b:
            continue
        jac = len(a & b) / float(len(a | b))
        if jac > bj:
            bj, best = jac, j
    r["nearest_neighbour_in_slice"] = {
        "name": out_rows[best]["skill_dir_name"] if best is not None else None,
        "jaccard": round(bj, 4),
    }

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(
        {
            "usage_detector_control": {
                "scripts_scanned": 200,
                "known_present_token_agent(": ctrl_present,
                "known_absent_token": ctrl_absent,
            },
            "rows": out_rows,
        },
        fh,
        indent=1,
    )

print("candidates featured:", len(out_rows))
print(
    "usage detector control: 'agent(' found in %d/200 scripts ; bogus token in %d/200"
    % (ctrl_present, ctrl_absent)
)
print()
print(
    "%-3s %-42s %7s %5s %-22s %-9s %s"
    % (
        "idx",
        "name",
        "bytes",
        "hdgs",
        "nearest-in-slice",
        "jaccard",
        "usage(scripts/runs)",
    )
)
for r in out_rows:
    print(
        "%-3d %-42s %7d %5d %-22s %-9.3f %d/%d"
        % (
            r["registry_index"],
            r["skill_dir_name"],
            r["bytes"],
            len(r["headings"]),
            (r["nearest_neighbour_in_slice"]["name"] or "-")[:22],
            r["nearest_neighbour_in_slice"]["jaccard"],
            r["usage"]["executed_scripts_naming_it"],
            r["usage"]["run_records_naming_it"],
        )
    )
print("wrote", OUT)
