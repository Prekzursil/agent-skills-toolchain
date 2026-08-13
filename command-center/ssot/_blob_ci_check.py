"""Verify this lane's committed files are ruff-clean AS CI WILL SEE THEM.

A local `ruff format --check` runs against the WORKING TREE, which on this box is CRLF. CI
checks out the stored blob, which is LF. Ruff has been measured making different formatting
decisions on the two forms, so a local green can sit on top of a CI red. The rule is to check
the BLOB.

Two traps this deliberately avoids:

  1. `git archive` applies export-time EOL conversion and hands back CRLF on Windows -- the
     exact opposite of what is wanted. `git cat-file -p` returns the raw stored blob. Measured
     on this estate: archive 3,837 B / 100 CRLF vs cat-file 3,737 B / 0 CRLF for one file.
  2. A bare temp dir has no `ruff.toml`, so ruff falls back to its DEFAULT line length instead
     of the project's, and reports reformats on files CI would pass -- a false red in the very
     check meant to catch a false green. The config is copied in, and the repo-relative
     directory layout is mirrored so any path-scoped setting resolves the same way.

Control (both states): one extracted file is deliberately mangled and the checker must FIRE on
it. If the mangled file passes, the checker is not actually inspecting these files and its
silence about the rest is worthless.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
LANE_COMMITS = ["df6377ab", "3043d615", "a435ae7c", "33f3f2d3"]


def sh(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True, timeout=900, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    # Every python file this lane committed.
    paths: set[str] = set()
    for c in LANE_COMMITS:
        rc, out = sh(["git", "-C", str(REPO), "show", "--name-only", "--format=", c])
        for ln in out.split("\n"):
            ln = ln.strip()
            if ln.endswith(".py"):
                paths.add(ln)
    paths = {p for p in paths if (REPO / p).exists()}
    print(f"lane-committed .py files: {len(paths)}")
    if not paths:
        print("FAILED:blob-ci-check no files resolved -- detector suspect")
        return 2

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ssot_blob_"))
    try:
        crlf_seen = 0
        for p in sorted(paths):
            rc, _ = sh(["git", "-C", str(REPO), "cat-file", "-e", f"HEAD:{p}"])
            if rc != 0:
                continue
            raw = subprocess.run(
                ["git", "-C", str(REPO), "cat-file", "-p", f"HEAD:{p}"],
                capture_output=True,
                timeout=120,
            ).stdout
            crlf_seen += raw.count(b"\r\n")
            dest = tmp / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)

        # The config, without which ruff silently uses different defaults.
        shutil.copy2(REPO / "ruff.toml", tmp / "ruff.toml")
        print(f"extracted to {tmp}")
        print(
            f"CRLF bytes across all extracted blobs: {crlf_seen} "
            f"({'as expected for stored blobs' if crlf_seen == 0 else 'UNEXPECTED -- see trap 1'})"
        )

        rc_l, out_l = sh([sys.executable, "-m", "ruff", "check", "."], cwd=str(tmp))
        rc_f, out_f = sh(
            [sys.executable, "-m", "ruff", "format", "--check", "."], cwd=str(tmp)
        )
        print("\n-- ruff check (blob form) --")
        print(out_l.strip()[-600:] or "(no output)")
        print("\n-- ruff format --check (blob form) --")
        print(out_f.strip()[-600:] or "(no output)")

        clean = rc_l == 0 and rc_f == 0

        # ---- CONTROL: mangle one file and require the checker to FIRE ----
        victim = sorted(paths)[0]
        vpath = tmp / victim
        original = vpath.read_bytes()
        vpath.write_bytes(b"import  os,sys\nx   =    1\ndef  f( a ):\n  return    a\n")
        rc_c, out_c = sh(
            [sys.executable, "-m", "ruff", "format", "--check", "."], cwd=str(tmp)
        )
        fired = rc_c != 0
        print(f"\n-- CONTROL: mangled {victim} --")
        print(
            f"   checker {'FIRED' if fired else 'STAYED SILENT <-- CHECKER IS BLIND'}"
        )
        vpath.write_bytes(original)

        print()
        if not fired:
            print(
                "FAILED:blob-ci-check control did not fire; the clean result proves nothing"
            )
            return 3
        if clean:
            print(
                f"SUCCESS:blob-ci-check files={len(paths)} lint=0 format=0 (blob form, config present)"
            )
            return 0
        print("FAILED:blob-ci-check the committed blobs are NOT CI-clean")
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
