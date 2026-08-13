"""Was README.md ever CRLF on the ancestry path, and did 7aa86f16 normalise it?

The BUILD says: sibling commit 7aa86f16 "rewrote that file to LF between the two rounds".
The AUDIT says: that causal attribution is wrong; 7aa86f16 is a content repair, and
README.md is i/lf on both sides of it.
A third possibility: a real LF-normalisation happened, at some OTHER commit.
"""

import subprocess

REPO = r"C:/Users/Prekzursil/source/ast-integrate"


def sh(args, binary=False):
    p = subprocess.run(args, cwd=REPO, capture_output=True)
    return p.returncode, (p.stdout if binary else p.stdout.decode("utf-8", "replace"))


def crlf_at(rev, path):
    rc, b = sh(["git", "cat-file", "-p", f"{rev}:{path}"], binary=True)
    if rc != 0:
        return None
    return b.count(b"\r\n"), b.count(b"\n")


# walk the FIRST-PARENT ancestry of the lane commit only -- not --all
rc, out = sh(["git", "log", "--first-parent", "--format=%H %ad %s", "--date=short",
              "673cd180", "--", "README.md"])
rows = [ln for ln in out.splitlines() if ln.strip()]
print(f"README.md touched by {len(rows)} commits on the first-parent ancestry of 673cd180\n")
prev = None
for ln in rows:
    h = ln.split()[0]
    res = crlf_at(h, "README.md")
    if res is None:
        continue
    crlf, lf = res
    mark = ""
    if prev is not None and prev != crlf:
        mark = f"   <== TRANSITION {crlf} (child) vs {prev} (its child-side neighbour)"
    print(f"  {h[:8]}  CRLF={crlf:>4}  lines={lf:>4}  {ln[41:100]}{mark}")
    prev = crlf

print("\n--- the commit the BUILD blames: 7aa86f16 ---")
rc, out = sh(["git", "show", "--stat", "--format=%H%n%ad%n%s", "--date=short", "7aa86f16"])
print(out[:700])
for side, rev in (("parent 7aa86f16^", "7aa86f16^"), ("commit 7aa86f16", "7aa86f16")):
    res = crlf_at(rev, "README.md")
    print(f"  {side:20s} README.md CRLF={res[0]} lines={res[1]}" if res else f"  {side} absent")

print("\n--- is 7aa86f16 even an ancestor of the lane commit? ---")
rc, _ = sh(["git", "merge-base", "--is-ancestor", "7aa86f16", "673cd180"])
print(f"  ancestor of 673cd180: {'YES' if rc == 0 else 'NO'}")
rc2, _ = sh(["git", "merge-base", "--is-ancestor", "7aa86f16", "630bb8af"])
print(f"  ancestor of 630bb8af (round 2): {'YES' if rc2 == 0 else 'NO'}")
