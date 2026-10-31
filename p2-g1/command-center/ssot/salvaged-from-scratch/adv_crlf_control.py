"""End-to-end BOTH-STATES control for the CRLF detectors, in an ISOLATED throwaway repo.

Hypotheses under test:
  H_A: `git cat-file -p <rev>:<path>` returns the stored blob bytes UNCONVERTED,
       so a CR in the blob shows up as a CR.
  H_B: `git ls-files --eol` CAN report i/crlf (i.e. the i/ column is not hardwired to lf).

If a detector cannot report CRLF even for a blob that provably contains CRLF, then its
"0 CRLF" reading on the real files measures nothing.
"""

import os
import shutil
import subprocess
import sys

TMP = r"C:/Users/Prekzursil/source/_advver_M14/scratch/_crlf_control_repo"


def run(args, cwd, binary=False):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    if binary:
        return p.returncode, p.stdout
    return p.returncode, p.stdout.decode("utf-8", "replace")


def main():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)

    run(["git", "init", "-q"], TMP)
    run(["git", "config", "user.email", "adv@local"], TMP)
    run(["git", "config", "user.name", "adv"], TMP)
    # -text => no normalisation, CRLF survives into the index blob
    with open(os.path.join(TMP, ".gitattributes"), "wb") as f:
        f.write(b"* -text\n")

    crlf_body = b"alpha\r\nbeta\r\ngamma\r\n"          # 3 CRLF, 3 LF
    lf_body = b"alpha\nbeta\ngamma\n"                   # 0 CRLF, 3 LF
    with open(os.path.join(TMP, "known_crlf.md"), "wb") as f:
        f.write(crlf_body)
    with open(os.path.join(TMP, "known_lf.md"), "wb") as f:
        f.write(lf_body)

    run(["git", "add", "-A"], TMP)
    run(["git", "commit", "-q", "-m", "control"], TMP)

    ok = True

    # ---- Detector 1: cat-file byte count ----
    print("== DETECTOR 1: git cat-file -p, byte count ==")
    for name, want_crlf in (("known_crlf.md", 3), ("known_lf.md", 0)):
        rc, blob = run(["git", "cat-file", "-p", "HEAD:" + name], TMP, binary=True)
        got = blob.count(b"\r\n")
        verdict = "OK" if got == want_crlf else "DETECTOR BROKEN"
        if got != want_crlf:
            ok = False
        print(f"  {name:16s} rc={rc} CRLF={got} want={want_crlf}  {verdict}")

    # same via `git show`, the form the build/audit both used
    print("== DETECTOR 1b: git show <rev>:<path>, byte count ==")
    for name, want_crlf in (("known_crlf.md", 3), ("known_lf.md", 0)):
        rc, blob = run(["git", "show", "HEAD:" + name], TMP, binary=True)
        got = blob.count(b"\r\n")
        verdict = "OK" if got == want_crlf else "DETECTOR BROKEN"
        if got != want_crlf:
            ok = False
        print(f"  {name:16s} rc={rc} CRLF={got} want={want_crlf}  {verdict}")

    # ---- Detector 2: git ls-files --eol, the i/ column ----
    print("== DETECTOR 2: git ls-files --eol, i/ column ==")
    rc, out = run(["git", "ls-files", "--eol"], TMP)
    seen = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            seen[parts[1].strip()] = parts[0].split()[0]
    for name, want in (("known_crlf.md", "i/crlf"), ("known_lf.md", "i/lf")):
        got = seen.get(name, "<missing>")
        verdict = "OK" if got == want else "DETECTOR BROKEN"
        if got != want:
            ok = False
        print(f"  {name:16s} i-col={got:10s} want={want}  {verdict}")

    print()
    if ok:
        print("SUCCESS:crlf-control both detectors report CRLF on a real CRLF blob "
              "and 0/lf on a real LF blob -- they distinguish the two hypotheses")
        return 0
    print("FAILED:crlf-control a detector could not distinguish; its zeros are meaningless")
    return 1


if __name__ == "__main__":
    sys.exit(main())
