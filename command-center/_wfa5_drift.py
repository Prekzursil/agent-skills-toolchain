"""build/wfa-5 : measure live-vs-repo drift for the 32 slice candidates the RIGHT way.

EOL trap (rules/common/windows-shell.md 8b): a working-tree file is CRLF, the stored blob
is LF, so a raw byte compare manufactures phantom drift. Every comparison here is made on
LF-normalised bytes AND the raw byte counts are reported alongside, so the reader can see
which differences are content and which are line endings.

Committed bytes are read with `git cat-file -p` (never `git archive`, which returns CRLF
on this box).
"""

import hashlib
import json
import os
import subprocess

REPO = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(REPO, "command-center", "_wfa5_drift.json")
FEAT = os.path.join(REPO, "command-center", "_wfa5_skillfeat.json")
PINNED = "07f465f37d49710f7060dcc7b567d6c58213177b"

with open(FEAT, encoding="utf-8") as fh:
    rows = json.load(fh)["rows"]


def blob(rev_path):
    r = subprocess.run(
        ["git", "cat-file", "-p", rev_path], cwd=REPO, capture_output=True, timeout=120
    )
    return r.stdout if r.returncode == 0 else None


def norm(b):
    return b.replace(b"\r\n", b"\n") if b is not None else None


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16] if b is not None else None


res = []
for r in rows:
    name = r["skill_dir_name"]
    copies = r["copies"]
    live_p = (copies.get("agents-live") or {}).get("path")
    claude_p = (copies.get("claude-live") or {}).get("path")
    live_b = None
    if live_p and os.path.isfile(live_p):
        with open(live_p, "rb") as fh:
            live_b = fh.read()
    claude_b = None
    if claude_p and os.path.isfile(claude_p):
        with open(claude_p, "rb") as fh:
            claude_b = fh.read()
    head_b = blob("HEAD:skills/%s/SKILL.md" % name)
    head_agents_b = blob("HEAD:.agents/skills/%s/SKILL.md" % name)
    pin_b = blob("%s:skills/%s/SKILL.md" % (PINNED, name))
    pin_agents_b = blob("%s:.agents/skills/%s/SKILL.md" % (PINNED, name))

    variants = {
        "live_agents": live_b,
        "live_claude": claude_b,
        "repo_HEAD_skills": head_b,
        "repo_HEAD_agents_skills": head_agents_b,
        "pinned_skills": pin_b,
        "pinned_agents_skills": pin_agents_b,
    }
    digests = {k: sha(norm(v)) for k, v in variants.items()}
    raw_bytes = {k: (len(v) if v is not None else None) for k, v in variants.items()}
    present = {k: v for k, v in digests.items() if v}
    distinct = sorted(set(present.values()))
    ref = (
        digests.get("live_agents")
        or digests.get("live_claude")
        or digests.get("repo_HEAD_skills")
        or digests.get("repo_HEAD_agents_skills")
    )
    res.append(
        {
            "registry_index": r["registry_index"],
            "name": name,
            "copies_present": sorted(present),
            "digests_lf_normalised": digests,
            "raw_byte_counts": raw_bytes,
            "distinct_content_versions": len(distinct),
            "all_copies_identical_after_lf_norm": len(distinct) == 1,
            "reference_digest": ref,
        }
    )

ident = sum(1 for x in res if x["all_copies_identical_after_lf_norm"])
multi = [x for x in res if x["distinct_content_versions"] > 1]
print("candidates measured                     :", len(res))
print("all copies identical after LF-normalise :", ident)
print("candidates with >1 distinct content ver  :", len(multi))
for x in multi:
    print(
        "   drift: %-40s versions=%d copies=%s"
        % (x["name"], x["distinct_content_versions"], ",".join(x["copies_present"]))
    )
print(
    "candidates with NO repo copy at HEAD     :",
    sum(
        1
        for x in res
        if not x["digests_lf_normalised"]["repo_HEAD_skills"]
        and not x["digests_lf_normalised"]["repo_HEAD_agents_skills"]
    ),
)

# DETECTOR CONTROL: the comparator must FIRE on a known-different pair and stay silent on
# a known-identical pair.
a = b"line one\r\nline two\r\n"
b_ = b"line one\nline two\n"
c = b"line one\nline THREE\n"
print("control identical-after-norm (CRLF vs LF):", sha(norm(a)) == sha(norm(b_)))
print("control differs (real content change)    :", sha(norm(b_)) != sha(norm(c)))

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(
        {
            "eol_control": {
                "crlf_vs_lf_same_after_norm": sha(norm(a)) == sha(norm(b_)),
                "real_change_detected": sha(norm(b_)) != sha(norm(c)),
            },
            "rows": res,
        },
        fh,
        indent=1,
    )
print("wrote", OUT)
