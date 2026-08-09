"""build/wfa-5 : targeted verification probes for the load-bearing claims in slice 129-160."""

import glob
import json
import os
import re
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
HOME = os.path.expanduser("~")
OUT = os.path.join(REPO, "command-center", "_wfa5_verify.json")
res = {}

# ---- P1. the two LIVE copies of design-studio-session differ: WHERE, exactly? ----
a = os.path.join(HOME, ".agents", "skills", "design-studio-session", "SKILL.md")
b = os.path.join(HOME, ".claude", "skills", "design-studio-session", "SKILL.md")
la = open(a, encoding="utf-8", errors="replace").read().splitlines()
lb = open(b, encoding="utf-8", errors="replace").read().splitlines()
diffs = []
for i in range(max(len(la), len(lb))):
    x = la[i] if i < len(la) else "<absent>"
    y = lb[i] if i < len(lb) else "<absent>"
    if x != y:
        diffs.append({"line": i + 1, "agents_vault": x[:300], "claude_vault": y[:300]})
res["P1_design_studio_session_live_diff"] = {
    "agents_path": a.replace("\\", "/"),
    "claude_path": b.replace("\\", "/"),
    "line_count": [len(la), len(lb)],
    "differing_lines": len(diffs),
    "first_diffs": diffs[:4],
}
print("P1 differing lines:", len(diffs))
for d in diffs[:3]:
    print("   L%d agents : %s" % (d["line"], d["agents_vault"][:160]))
    print("   L%d claude : %s" % (d["line"], d["claude_vault"][:160]))

# ---- P2. can the upstream terms for origin: ECC / oh-my-agent-check be established? ----
needles = {
    "ECC": r"\bECC\b",
    "oh-my-agent-check": r"oh-my-agent-check",
    "antbotlab": r"antbotlab",
    "standardagents/dmux": r"standardagents/dmux",
    "redminwang": r"redminwang",
}
hay = []
for pat in (
    os.path.join(REPO, "*.md"),
    os.path.join(REPO, "docs", "**", "*.md"),
    os.path.join(REPO, "LICENSE*"),
    os.path.join(REPO, "NOTICE*"),
    os.path.join(REPO, "skills", "*", "SKILL.md"),
    os.path.join(HOME, ".claude", "*.md"),
    os.path.join(HOME, ".agents", "*.md"),
):
    hay.extend(glob.glob(pat, recursive=True))
found = {k: [] for k in needles}
for p in hay:
    try:
        t = open(p, encoding="utf-8", errors="replace").read()
    except Exception:  # noqa: BLE001
        continue
    for k, rx in needles.items():
        for m in re.finditer(rx, t):
            ln = t[: m.start()].count("\n") + 1
            ctx = t.splitlines()[ln - 1][:200] if ln - 1 < len(t.splitlines()) else ""
            if len(found[k]) < 5:
                found[k].append({"path": p.replace("\\", "/"), "line": ln, "text": ctx})
res["P2_upstream_term_search"] = {
    "files_searched": len(hay),
    "hits": {k: len(v) for k, v in found.items()},
    "samples": found,
}
print("P2 files searched:", len(hay), "hits:", {k: len(v) for k, v in found.items()})

# ---- P3. licence-file detector control across the whole live vault ----
vault = os.path.join(HOME, ".agents", "skills")
lic_dirs = []
for d in sorted(os.listdir(vault)):
    dd = os.path.join(vault, d)
    if os.path.isdir(dd):
        for f in os.listdir(dd):
            if re.match(r"(?i)^(licen[cs]e|notice|copying)", f):
                lic_dirs.append(d)
                break
res["P3_licence_file_control"] = {
    "vault": vault.replace("\\", "/"),
    "skill_dirs": len(
        [d for d in os.listdir(vault) if os.path.isdir(os.path.join(vault, d))]
    ),
    "dirs_with_a_licence_file": len(lic_dirs),
    "which": lic_dirs[:20],
}
print(
    "P3 live vault skill dirs with a LICENSE/NOTICE file: %d of %d -> %s"
    % (len(lic_dirs), res["P3_licence_file_control"]["skill_dirs"], lic_dirs[:10])
)

# ---- P4. repo-only candidate 148: structure ----
p148 = os.path.join(REPO, "skills", "harness-module-authoring", "SKILL.md")
t148 = open(p148, encoding="utf-8", errors="replace").read()
l148 = t148.splitlines()
res["P4_harness_module_authoring"] = {
    "path": p148.replace("\\", "/"),
    "bytes": len(t148),
    "lines": len(l148),
    "headings": [
        {"line": i + 1, "text": ln.strip()[:110]}
        for i, ln in enumerate(l148)
        if re.match(r"^#{2,3}\s+\S", ln)
    ][:20],
    "deployed_live_agents": os.path.isfile(
        os.path.join(HOME, ".agents", "skills", "harness-module-authoring", "SKILL.md")
    ),
    "deployed_live_claude": os.path.isfile(
        os.path.join(HOME, ".claude", "skills", "harness-module-authoring", "SKILL.md")
    ),
}
print(
    "P4 harness-module-authoring: %d bytes, %d headings, deployed(agents)=%s deployed(claude)=%s"
    % (
        len(t148),
        len(res["P4_harness_module_authoring"]["headings"]),
        res["P4_harness_module_authoring"]["deployed_live_agents"],
        res["P4_harness_module_authoring"]["deployed_live_claude"],
    )
)

# ---- P5. deployment control: is a KNOWN-deployed skill seen as deployed? ----
res["P5_deployment_detector_control"] = {
    "known_deployed_workflow_authoring": os.path.isfile(
        os.path.join(HOME, ".agents", "skills", "workflow-authoring", "SKILL.md")
    ),
    "known_absent_sentinel": os.path.isfile(
        os.path.join(HOME, ".agents", "skills", "zzz-no-such-skill-4a1c", "SKILL.md")
    ),
}
print(
    "P5 control deployed=%s absent=%s"
    % (
        res["P5_deployment_detector_control"]["known_deployed_workflow_authoring"],
        res["P5_deployment_detector_control"]["known_absent_sentinel"],
    )
)


# ---- P6. usage-evidence cross-check with a DIFFERENT mechanism (git grep of the repo) ----
def gitgrep(term):
    r = subprocess.run(
        ["git", "grep", "-c", "--", term],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return len([x for x in (r.stdout or "").splitlines() if x.strip()])


res["P6_repo_reference_counts"] = {
    t: gitgrep(t)
    for t in [
        "deep-research",
        "handoff",
        "context-sandbox",
        "harness-module-authoring",
        "zzz-no-such-skill-4a1c",
    ]
}
print("P6 repo files referencing each name:", res["P6_repo_reference_counts"])

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=1)
print("wrote", OUT)
