"""Three-way rules drift: repo rules/ vs agent-self/config/rules/ vs live ~/.claude/rules/.

Also totals always-on token cost per tree with tiktoken (declared as an ESTIMATE:
cl100k_base is OpenAI's tokenizer, not Anthropic's).
"""

import glob
import hashlib
import os

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")

TREES = {
    "repo": r"C:/Users/Prekzursil/source/ast-integrate/rules",
    "agent-self": r"C:/Users/Prekzursil/source/ast-integrate/agent-self/config/rules",
    "live": r"C:/Users/Prekzursil/.claude/rules",
}


def scan(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for p in sorted(glob.glob(os.path.join(root, "**/*.md"), recursive=True)):
        rel = os.path.relpath(p, root).replace("\\", "/")
        with open(p, "rb") as fh:
            raw = fh.read().replace(b"\r\n", b"\n")
        text = raw.decode("utf-8", errors="replace")
        out[rel] = {
            "sha": hashlib.sha256(raw).hexdigest(),
            "fm": text.startswith("---"),
            "tok": len(ENC.encode(text)),
            "bytes": len(raw),
        }
    return out


trees = {k: scan(v) for k, v in TREES.items()}

for k, v in trees.items():
    if not v:
        print("%-11s MISSING (%s)" % (k, TREES[k]))
        continue
    nofm = sorted(x for x in v if not v[x]["fm"])
    print(
        "%-11s files=%-4d  no-frontmatter=%-3d  ALWAYS-ON tok=%-6d  ALL tok=%d"
        % (
            k,
            len(v),
            len(nofm),
            sum(v[x]["tok"] for x in nofm),
            sum(v[x]["tok"] for x in v),
        )
    )
    print("            always-on set: %s" % [x.replace("common/", "") for x in nofm])

print("\n=== name-set differences ===")
keys = {k: set(v) for k, v in trees.items() if v}
allk = set().union(*keys.values())
for name in sorted(allk):
    present = [k for k in keys if name in keys[k]]
    if len(present) != len(keys):
        print("  %-46s present in %s" % (name, present))

print("\n=== content 3-way: files where the trees disagree ===")
common = set.intersection(*keys.values())
rows = []
for name in sorted(common):
    shas = {k: trees[k][name]["sha"][:8] for k in keys}
    if len(set(shas.values())) > 1:
        rows.append((name, shas, {k: trees[k][name]["bytes"] for k in keys}))
print("  disagreeing files: %d / %d" % (len(rows), len(common)))
for name, shas, by in rows:
    pat = "repo=%s self=%s live=%s" % (shas["repo"], shas["agent-self"], shas["live"])
    same = []
    if shas["repo"] == shas["agent-self"]:
        same.append("repo==self")
    if shas["repo"] == shas["live"]:
        same.append("repo==live")
    if shas["agent-self"] == shas["live"]:
        same.append("self==live")
    print(
        "  %-44s %s  bytes r=%d s=%d l=%d  %s"
        % (
            name,
            pat,
            by["repo"],
            by["agent-self"],
            by["live"],
            ",".join(same) or "ALL-3-DIFFER",
        )
    )
