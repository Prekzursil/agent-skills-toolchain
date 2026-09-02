"""SYNTHESIS-REVIEW: cheap existence + sha + claim checks over E2E-WAVE-STATUS.md.

Read-only. Emits JSON to stdout.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "command-center", "E2E-WAVE-STATUS.md")

out = {"root": ROOT}


def run(args, cwd=ROOT):
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as e:  # noqa: BLE001
        return -1, "", repr(e)


with open(DOC, encoding="utf-8") as fh:
    doc = fh.read()

# ---- R2: every 8-hex sha cited in the doc resolves -------------------------
shas = sorted(set(re.findall(r"`([0-9a-f]{8})`", doc)))
sha_res = {}
for s in shas:
    rc, so, se = run(["git", "cat-file", "-t", s])
    sha_res[s] = {"rc": rc, "type": so, "err": se[:200]}
out["R2_shas"] = sha_res

# ---- R3: files named as shipped exist --------------------------------------
files = [
    "scripts/claude-science/cs_wiring_check.py",
    "command-center/casualty/casualty_guard.py",
    "command-center/casualty/integration_redproof.py",
    "tools/measure-guard/launchpath.py",
    "tools/measure-guard/unitgate.py",
    "tools/measure-guard/blobread.py",
    "tools/wf-timeout/wf_gate.py",
    "ci/tests/test_deploy_skills_daily.py",
    ".quality/charter_check.sh",
    "platform/schema/receipt.schema.json",
    "command-center/sources/REGISTER.md",
    "skills/workflow-authoring/scripts/workflow_lint.py",
    "skills/workflow-authoring/scripts/test_workflow_lint.py",
    ".agents/skills/workflow-authoring/scripts/workflow_lint.py",
    ".agents/skills/workflow-authoring/scripts/test_workflow_lint.py",
    "skills/workflow-authoring/SKILL.md",
    "command-center/p2-wave/_i3_blobfmt.py",
    "tools/monitorcore/_blob_ruff.py",
    "command-center/casualty/verify_ci_parity.py",
    "docs/workflow-sota/_int_blobcheck.py",
    "scripts/deploy-skills-daily.py",
    "ci/scripts/deploy-skills-daily.py",
    "scripts/sync-skills.ps1",
    ".gitleaks.toml",
    ".github/workflows/quality.yml",
    "workflow-authoring/templates/governed-run-orchestrator.md",
    "skills/workflow-authoring/templates/governed-run-orchestrator.md",
    "command-center/READY-UNITS.json",
    "tools/measure-guard/p13_emit_receipt.py",
]
fres = {}
for f in files:
    p = os.path.join(ROOT, f.replace("/", os.sep))
    rc, so, _ = run(["git", "ls-files", "--error-unmatch", f])
    fres[f] = {"exists": os.path.exists(p), "tracked": rc == 0,
               "size": os.path.getsize(p) if os.path.exists(p) else None}
out["R3_files"] = fres

# ---- receipt schema unit_id pattern ----------------------------------------
try:
    with open(os.path.join(ROOT, "platform", "schema", "receipt.schema.json"), encoding="utf-8") as fh:
        sch = json.load(fh)
    pat = sch.get("$defs", {}).get("unit_id", {}).get("pattern")
    out["unit_id_pattern"] = pat
    if pat:
        rx = re.compile(pat)
        out["unit_id_probe"] = {k: bool(rx.match(k)) for k in
                                ["BLD-0023", "ADV-0021", "R-M18", "R-M06", "R-I1", "WFA-0001"]}
except Exception as e:  # noqa: BLE001
    out["unit_id_pattern"] = f"ERR {e!r}"

# ---- deploy-skills-daily --target flag? ------------------------------------
cands = [p for p in ["scripts/deploy-skills-daily.py", "ci/scripts/deploy-skills-daily.py",
                     "tools/deploy-skills-daily.py"]
         if os.path.exists(os.path.join(ROOT, p.replace("/", os.sep)))]
out["deploy_tool_candidates"] = cands
rc, so, se = run(["git", "ls-files", "*deploy-skills-daily*"])
out["deploy_tool_tracked"] = so.splitlines()
for c in out["deploy_tool_tracked"]:
    p = os.path.join(ROOT, c.replace("/", os.sep))
    if os.path.exists(p):
        with open(p, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        out.setdefault("deploy_tool_flags", {})[c] = sorted(set(re.findall(r'add_argument\(\s*"(--[a-z0-9-]+)"', body)))

# ---- quality.yml gate names -------------------------------------------------
qp = os.path.join(ROOT, ".github", "workflows", "quality.yml")
if os.path.exists(qp):
    with open(qp, encoding="utf-8", errors="replace") as fh:
        q = fh.read()
    out["quality_job_ids"] = re.findall(r"^  ([a-z0-9][a-z0-9-]*):\s*$", q, re.M)
    for name in ["gate-p2-delivery", "gate-secrets", "gate-lint-format", "gate-skill-deploy-hop",
                 "casualty", "launchpath", "wf-timeout", "cs-wiring", "measure-guard", "suitefloor"]:
        out.setdefault("quality_mentions", {})[name] = q.count(name)
    out["quality_python_versions"] = sorted(set(re.findall(r"python-version:\s*['\"]?([0-9.]+)", q)))

# ---- charter -----------------------------------------------------------------
cp = os.path.join(ROOT, ".quality", "charter.json")
out["charter_exists"] = os.path.exists(cp)
if os.path.exists(cp):
    with open(cp, encoding="utf-8", errors="replace") as fh:
        try:
            cj = json.load(fh)
            out["charter_gates"] = list(cj.get("gates", cj).keys()) if isinstance(cj, dict) else None
        except Exception as e:  # noqa: BLE001
            out["charter_gates"] = f"ERR {e!r}"

# ---- workflow_lint word boundary fix present? --------------------------------
for f in ["skills/workflow-authoring/scripts/workflow_lint.py",
          ".agents/skills/workflow-authoring/scripts/workflow_lint.py"]:
    p = os.path.join(ROOT, f.replace("/", os.sep))
    if os.path.exists(p):
        with open(p, encoding="utf-8", errors="replace") as fh:
            b = fh.read()
        out.setdefault("mapsnull", {})[f] = {
            "has_wordboundary": r"\bnull\b" in b,
            "def_maps_nulls": "_maps_nulls" in b,
        }
# byte-identical twins?
import hashlib
for pair in [("skills/workflow-authoring/scripts/workflow_lint.py",
              ".agents/skills/workflow-authoring/scripts/workflow_lint.py"),
             ("skills/workflow-authoring/scripts/test_workflow_lint.py",
              ".agents/skills/workflow-authoring/scripts/test_workflow_lint.py")]:
    hs = []
    for f in pair:
        p = os.path.join(ROOT, f.replace("/", os.sep))
        hs.append(hashlib.sha256(open(p, "rb").read()).hexdigest()[:16] if os.path.exists(p) else None)
    out.setdefault("twins", {})[pair[0]] = {"a": hs[0], "b": hs[1], "identical": hs[0] == hs[1] and hs[0] is not None}

# ---- REGISTER.md section 9 ----------------------------------------------------
rp = os.path.join(ROOT, "command-center", "sources", "REGISTER.md")
if os.path.exists(rp):
    with open(rp, encoding="utf-8", errors="replace") as fh:
        rb = fh.read()
    out["register"] = {
        "has_sec9": bool(re.search(r"^##\s*9\.", rb, re.M)),
        "headings": re.findall(r"^##\s+(.{0,70})", rb, re.M),
        "bytes": len(rb),
    }

# ---- READY-UNITS reviewer_requirement -----------------------------------------
rup = os.path.join(ROOT, "command-center", "READY-UNITS.json")
if os.path.exists(rup):
    try:
        with open(rup, encoding="utf-8", errors="replace") as fh:
            ru = json.load(fh)
        units = ru if isinstance(ru, list) else ru.get("units", ru.get("ready", []))
        out["ready_units"] = {
            "type": type(ru).__name__,
            "n": len(units) if isinstance(units, list) else None,
            "with_reviewer_requirement": sum(
                1 for u in units if isinstance(u, dict) and u.get("reviewer_requirement")
            ) if isinstance(units, list) else None,
            "keys_sample": sorted(units[0].keys())[:20] if isinstance(units, list) and units and isinstance(units[0], dict) else None,
        }
    except Exception as e:  # noqa: BLE001
        out["ready_units"] = f"ERR {e!r}"

# ---- 21 tracked .py after 4573b603 ---------------------------------------------
rc, so, se = run(["git", "diff", "--name-only", "--diff-filter=AM", "4573b603..HEAD"])
py = [f for f in so.splitlines() if f.endswith(".py")]
out["py_since_4573b603"] = {"n": len(py), "files": py}

rc, so, se = run(["git", "rev-parse", "HEAD"])
out["HEAD"] = so
rc, so, se = run(["git", "log", "--oneline", "-8"])
out["log8"] = so.splitlines()

print(json.dumps(out, indent=1))
