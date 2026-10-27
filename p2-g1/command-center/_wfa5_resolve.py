"""build/wfa-5 : resolve prior-registry rows 129-160 (32 G-skill candidates) to REAL
provenance anchors on disk, and probe every location the prior archaeology named.

Reads only. Emits _wfa5_resolve.json.
"""

import json
import os
import subprocess

CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(REPO, "command-center", "_wfa5_resolve.json")
HOME = os.path.expanduser("~")

with open(
    os.path.join(CORPUS, "08-WORKFLOW-CANDIDATE-REGISTRY.json"), encoding="utf-8"
) as fh:
    prior = json.load(fh)["candidates"]
slice_rows = prior[128:160]
assert len(slice_rows) == 32, len(slice_rows)

roots = {
    "agents-live": os.path.join(HOME, ".agents", "skills"),
    "claude-live": os.path.join(HOME, ".claude", "skills"),
    "repo-skills": os.path.join(REPO, "skills"),
    "repo-agents-skills": os.path.join(REPO, ".agents", "skills"),
    "repo-skills-claude-only": os.path.join(REPO, "skills-claude-only"),
}
print("root existence:")
for k, v in roots.items():
    print("  %-24s %-70s %s" % (k, v, os.path.isdir(v)))

mirror = os.path.join(CORPUS, "main-mirror.git")
print("mirror present:", os.path.isdir(mirror))


def sh(args, cwd=None):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()[:200]
    except Exception as exc:  # noqa: BLE001
        return -1, "", str(exc)[:200]


rc, out, err = sh(
    ["git", "cat-file", "-t", "07f465f37d49710f7060dcc7b567d6c58213177b"], cwd=REPO
)
print("repo knows 07f465f3:", rc, out, err)
rc2, head, _ = sh(["git", "rev-parse", "HEAD"], cwd=REPO)
print("repo HEAD:", head)

rows = []
for idx, row in zip(range(129, 161), slice_rows):
    name = (
        str(row["provenance"]).split(":", 1)[1].strip()
        if ":" in str(row["provenance"])
        else row["name"]
    )
    found = {}
    for k, root in roots.items():
        if not os.path.isdir(root):
            continue
        d = os.path.join(root, name)
        sk = os.path.join(d, "SKILL.md")
        if os.path.isfile(sk):
            st = os.stat(sk)
            found[k] = {
                "skill_md": sk.replace("\\", "/"),
                "bytes": st.st_size,
                "mtime_epoch": st.st_mtime,
                "dir_entries": sorted(os.listdir(d))[:40],
            }
    rows.append(
        {
            "registry_index": idx,
            "prior_id": row["id"],
            "prior_name": row["name"],
            "skill_dir_name": name,
            "prior_record": row,
            "found": found,
        }
    )

miss = [r for r in rows if not r["found"]]
print("resolved on disk: %d/32   unresolved: %d" % (32 - len(miss), len(miss)))
for r in miss:
    print("  UNRESOLVED:", r["skill_dir_name"])

# DETECTOR CONTROL: a name that is known-present and a name that is known-absent
ctrl_present = os.path.isfile(
    os.path.join(roots["agents-live"], "workflow-authoring", "SKILL.md")
)
ctrl_absent = os.path.isfile(
    os.path.join(roots["agents-live"], "zzz-definitely-not-a-skill-9df3", "SKILL.md")
)
print(
    "detector control: known-present workflow-authoring =",
    ctrl_present,
    "| known-absent sentinel =",
    ctrl_absent,
)

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(
        {
            "roots": {
                k: {"path": v, "exists": os.path.isdir(v)} for k, v in roots.items()
            },
            "mirror_present": os.path.isdir(mirror),
            "repo_head": head,
            "repo_knows_07f465f3": {"rc": rc, "type": out, "err": err},
            "detector_control": {
                "known_present": ctrl_present,
                "known_absent": ctrl_absent,
            },
            "rows": rows,
        },
        fh,
        indent=1,
    )
print("wrote", OUT)
