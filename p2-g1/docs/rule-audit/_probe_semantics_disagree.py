"""Which rule files have OPPOSITE load semantics across the three trees?"""

import glob
import os

TREES = [
    ("repo", r"C:/Users/Prekzursil/source/ast-integrate/rules"),
    ("self", r"C:/Users/Prekzursil/source/ast-integrate/agent-self/config/rules"),
    ("live", r"C:/Users/Prekzursil/.claude/rules"),
]

names = set()
for _, root in TREES:
    for p in glob.glob(os.path.join(root, "**/*.md"), recursive=True):
        names.add(os.path.relpath(p, root).replace(os.sep, "/"))

print("%-44s %-7s %-7s %-7s" % ("file", "repo", "self", "live"))
disagree = 0
for name in sorted(names):
    row = []
    for _, root in TREES:
        p = os.path.join(root, name)
        if not os.path.isfile(p):
            row.append("ABSENT")
            continue
        with open(p, "rb") as fh:
            text = fh.read().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")
        row.append("LAZY" if text.startswith("---") else "ALWAYS")
    if len(set(row)) > 1:
        disagree += 1
        print("%-44s %-7s %-7s %-7s  <<< DISAGREE" % (name, row[0], row[1], row[2]))
print(
    "\ntotal files: %d ; semantics disagree across trees: %d" % (len(names), disagree)
)
