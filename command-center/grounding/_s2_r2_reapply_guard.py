"""ROUND 2 / R6b: re-apply the main-guard repair with the FIXED tool.

The first application used the repo's `_fix_main_guard.py` as-is.  The executable
both-states probe then reported the junction invocation STILL silent -- the repair
had not repaired.  Root cause: `needs_import()` was called on the ALREADY-PATCHED
text, where `OLD` no longer exists, so `split(OLD)` returned the whole document and
the NEW block's own `realpathSync` token made the check answer "already imported".
The import was never inserted; the guard's `catch` swallowed the ReferenceError and
fell back to exactly the broken lexical compare.

This script rewinds the two .mjs files to their HEAD bytes and re-runs the corrected
tool, so what lands on disk is the TOOL's output, not a hand edit.

Byte discipline: the rewind reads `git show HEAD:<path>`, which returns the stored
blob (LF).  `git checkout --` would apply the repo's EOL conversion and could hand
back CRLF, turning an 11-line change into a whole-file diff.  Everything here is
read_bytes/write_bytes for the same reason the tool itself is.

Controls:
  * both trees must be byte-identical at HEAD before, and byte-identical after.
  * the post-condition (guard references realpathSync => file imports it) must hold.
  * the executable both-states probe is re-run separately; THAT is the proof.
"""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
TREES = ["skills/ui-audit", ".agents/skills/ui-audit"]
TARGET = "dead_button_crawl.mjs"
TOOL = "_fix_main_guard.py"


def blob(relpath):
    out = subprocess.run(["git", "show", "HEAD:%s" % relpath], cwd=str(REPO),
                         capture_output=True)
    if out.returncode != 0:
        raise SystemExit("cannot read HEAD blob for %s: %s"
                         % (relpath, out.stderr.decode("utf-8", "replace")[:200]))
    return out.stdout


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def main():
    print("=== 0. the two trees must agree at HEAD before anything is written ===")
    for name in (TARGET, TOOL):
        hs = {t: sha(blob("%s/%s" % (t, name))) for t in TREES}
        same = len(set(hs.values())) == 1
        print("  %-24s %s  identical=%s" % (name, list(hs.values()), same))
        if not same:
            print("  REFUSED: trees diverge at HEAD for %s -- not a mechanical re-apply" % name)
            return 1

    print()
    print("=== 1. propagate the FIXED tool to the second tree (dual-write) ===")
    src = REPO / TREES[0] / TOOL
    fixed = src.read_bytes()
    dst = REPO / TREES[1] / TOOL
    if dst.read_bytes() != fixed:
        dst.write_bytes(fixed)
        print("  wrote %s (%d bytes)" % (dst, len(fixed)))
    else:
        print("  %s already identical" % dst)
    print("  tool sha now: %s / %s"
          % (sha(src.read_bytes()), sha(dst.read_bytes())))

    print()
    print("=== 2. rewind the target to HEAD bytes (LF preserved, no git checkout) ===")
    for t in TREES:
        p = REPO / t / TARGET
        b = blob("%s/%s" % (t, TARGET))
        p.write_bytes(b)
        print("  %-30s restored %d bytes  crlf=%d" % (t, len(b), b.count(b"\r\n")))

    print()
    print("=== 3. run the CORRECTED tool in each tree ===")
    rc = 0
    for t in TREES:
        r = subprocess.run([sys.executable, str(REPO / t / TOOL)],
                           capture_output=True, text=True)
        rc |= r.returncode
        head = [x for x in r.stdout.splitlines() if not x.startswith("  skipped")]
        print("  %-30s exit=%d  %s" % (t, r.returncode, " | ".join(head)))
    if rc:
        print("  FAILED: the tool reported a non-zero exit")
        return 1

    print()
    print("=== 4. post-conditions ===")
    ok = True
    hashes = []
    for t in TREES:
        p = REPO / t / TARGET
        with io.open(p, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        has_import = "import { realpathSync } from 'node:fs';" in text
        has_guard = "__isMain(process.argv[1], __filename)" in text
        no_old = "resolve(process.argv[1]) === resolve(__filename)" not in text
        crlf = text.count("\r\n")
        hashes.append(sha(p.read_bytes()))
        print("  %-30s import=%-5s __isMain=%-5s old-guard-gone=%-5s crlf=%d"
              % (t, has_import, has_guard, no_old, crlf))
        ok &= has_import and has_guard and no_old and crlf == 0
    print("  both trees byte-identical:", len(set(hashes)) == 1)
    ok &= len(set(hashes)) == 1
    print()
    print("%s:s2-r2-reapply-guard" % ("SUCCESS" if ok else "FAILED"))
    return 0 if ok else 1


sys.exit(main())
