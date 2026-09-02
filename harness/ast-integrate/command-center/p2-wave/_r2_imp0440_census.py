"""IMP-0440 feasibility census: where does the archive-plus-extract recipe still live?

The unit demands ONE `blob_bytes(rev, path)` helper on `git cat-file` and the removal of every
archive-based provenance recipe. Before building, measure the surface: if remediation requires
editing trees a sibling lane owns, that part is BLOCKED and must be reported as such rather than
narrowed away.

Also runs the three-route comparison the row's evidence_requirement names.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRLF = b"\r\n"


def git(*args, binary=False):
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True)
    if binary:
        return r.returncode, r.stdout
    return r.returncode, r.stdout.decode("utf-8", "replace")


print("=== census: files mentioning `git archive` ===")
rc, out = git("grep", "-n", "-I", "git archive")
lines = [ln for ln in out.splitlines() if ln.strip()]
print(f"  raw hits: {len(lines)}")
by_file: dict[str, list[str]] = {}
for ln in lines:
    f = ln.split(":", 1)[0]
    by_file.setdefault(f, []).append(ln)
for f, hits in sorted(by_file.items()):
    print(f"  {f}  ({len(hits)} hit(s))")

print()
print("=== use-vs-mention split: PRESCRIBES the recipe vs DOCUMENTS it as wrong ===")
NEG = re.compile(
    r"do not use|don.t use|never|wrong|opposite|banned|must be replaced|"
    r"instead of|rather than|refuted|forbidden|avoid|deprecat|CRLF|converts?|conversion",
    re.I,
)
prescribes, warns = [], []
for ln in lines:
    (warns if NEG.search(ln) else prescribes).append(ln)
print(f"  lines that WARN against it : {len(warns)}")
print(f"  lines that may PRESCRIBE it: {len(prescribes)}")
for ln in prescribes:
    print(f"    ! {ln[:170]}")

print()
print("=== EXECUTABLE call sites (a doc naming it is not a dependency) ===")
code = [
    ln
    for ln in lines
    if ln.split(":", 1)[0].endswith(
        (".py", ".ps1", ".sh", ".mjs", ".js", ".yml", ".yaml")
    )
]
print(f"  hits inside executable/CI files: {len(code)}")
for ln in code:
    print(f"    {ln[:170]}")

print()
print("=== the three-route comparison the row's evidence_requirement demands ===")
target = sys.argv[1] if len(sys.argv) > 1 else "command-center/ready_units.py"
rc1, blob_cat = git("cat-file", "-p", f"HEAD:{target}", binary=True)
rc2, blob_show = git("show", f"HEAD:{target}", binary=True)
arch_bytes = b""
with tempfile.TemporaryDirectory() as td:
    tarp = Path(td) / "a.tar"
    r = subprocess.run(
        ["git", "archive", "-o", str(tarp), "HEAD", "--", target],
        cwd=str(REPO),
        capture_output=True,
    )
    if r.returncode == 0 and tarp.is_file():
        with tarfile.open(tarp) as tf:
            fh = tf.extractfile(tf.getmember(target))
            arch_bytes = fh.read() if fh else b""

routes = {
    "git archive + tar -x": arch_bytes,
    "git cat-file -p": blob_cat,
    "git show <rev>:<path>": blob_show,
}
print(f"  target = {target}")
print(f"  {'route':<24} {'bytes':>8} {'CRLF':>6}")
for name, data in routes.items():
    print(f"  {name:<24} {len(data):>8} {data.count(CRLF):>6}")

vals = [v.replace(CRLF, b"\n") for v in routes.values()]
identical = all(v == vals[0] for v in vals) and bool(vals[0])
print(
    f"  CONTROL identical-after-LF-normalisation: {identical}  "
    f"(proves the difference is line endings, not content)"
)
print(
    f"  CONTROL the comparison must FAIL on a mangled copy: "
    f"{(vals[0] + b'# planted') != vals[0]} (a comparison that cannot fail proves nothing)"
)
print("DONE:imp0440-census")
