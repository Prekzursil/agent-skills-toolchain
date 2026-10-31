"""What does `agent-self/bootstrap.ps1` (Copy-Item config/* -> ~/.claude -Force) do
to the ALWAYS-ON set and its token cost?

Simulates the merge-over-force copy in memory. Read-only; writes nothing.
"""

import glob
import os

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
LIVE = r"C:/Users/Prekzursil/.claude/rules"
SELF = r"C:/Users/Prekzursil/source/ast-integrate/agent-self/config/rules"
REPO = r"C:/Users/Prekzursil/source/ast-integrate/rules"


def load(root):
    d = {}
    for p in glob.glob(os.path.join(root, "**/*.md"), recursive=True):
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        with open(p, "rb") as fh:
            t = fh.read().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
        d[rel] = t
    return d


live, slf, repo = load(LIVE), load(SELF), load(REPO)


def alwayson(tree):
    return {k: len(ENC.encode(v)) for k, v in tree.items() if not v.startswith("---")}


before = alwayson(live)
after_tree = dict(live)
after_tree.update(slf)  # merge-over-force, no prune
after = alwayson(after_tree)

print(
    "BEFORE bootstrap: %d always-on rules, %d tok" % (len(before), sum(before.values()))
)
print(
    "AFTER  bootstrap: %d always-on rules, %d tok" % (len(after), sum(after.values()))
)
print("\nPROMOTED lazy -> always-on by the bootstrap:")
for k in sorted(set(after) - set(before)):
    print(
        "   + %-42s %d tok  (live had paths: frontmatter, agent-self copy does not)"
        % (k, after[k])
    )
print("DEMOTED always-on -> lazy:")
for k in sorted(set(before) - set(after)):
    print("   - %-42s %d tok" % (k, before[k]))
print("\nAlways-on files whose CONTENT the bootstrap would change:")
for k in sorted(set(before) & set(after)):
    if live.get(k) != after_tree.get(k):
        print("   ~ %-42s %d -> %d tok" % (k, before[k], after[k]))

print(
    "\n--- same simulation for `pwsh scripts/sync-rules.ps1` (repo rules/common/*.md -> live) ---"
)
after2 = dict(live)
for k, v in repo.items():
    # sync-rules.ps1 is NON-recursive: only rules/common/*.md
    if k.startswith("common/") and k.count("/") == 1:
        after2[k] = v
a2 = alwayson(after2)
print(
    "AFTER sync-rules: %d always-on rules, %d tok (delta %+d)"
    % (len(a2), sum(a2.values()), sum(a2.values()) - sum(before.values()))
)
print(
    "  content-changed always-on files: %d"
    % len([k for k in a2 if live.get(k) != after2.get(k)])
)
print("  files sync-rules.ps1 CANNOT reach (language dirs still divergent):")
for k in sorted(repo):
    if not (k.startswith("common/") and k.count("/") == 1):
        if k in live and live[k] != repo[k]:
            print("     %s" % k)
