"""BUILD R2 / DoD4 -- the two frozen-evidence directories are untouched by this round.

  command-center/casualty/probes          (byte-identical to dead agents' scratch originals)
  command-center/p2-wave/probes/*/control (deliberately-broken detector fixtures)

For both, the BYTES are the measurement, so "untouched" must be shown, not asserted. Four
mechanically different signals:

  S1 no commit in this round's range touches either path   (git log <range> -- <paths>)
  S2 no tracked diff across the range                      (git diff --name-only)
  S3 nothing dirty in the worktree now                     (git status --porcelain)
  S4 every file still hashes, and the hasher is proven NON-CONSTANT

S4 matters because "all files hashed OK" is exactly what a hasher that returns a constant would
also print. The control mutates a COPY in a temp dir and requires the digest to change; if a
constant-returning hasher were in play, the mutated copy would hash the same and the control
fails. The originals are never opened for write.
"""

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = pathlib.Path(__file__).with_suffix(".out.json")
FROZEN = ["command-center/casualty/probes", "command-center/p2-wave/probes"]
BEFORE_REV = "61e69cf2"


def git(*args):
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def sha16_bytes(b):
    return hashlib.sha256(b).hexdigest()[:16]


def main():
    head = git("rev-parse", "HEAD").strip()
    res = {"range": f"{BEFORE_REV}..HEAD", "head": head, "dirs": {}}
    all_ok = True
    sample_bytes = None

    for d in FROZEN:
        touched_commits = [
            ln
            for ln in git(
                "log", "--format=%h", f"{BEFORE_REV}..HEAD", "--", d
            ).splitlines()
            if ln.strip()
        ]
        diffed = [
            ln
            for ln in git(
                "diff", "--name-only", BEFORE_REV, "HEAD", "--", d
            ).splitlines()
            if ln.strip()
        ]
        dirty = [
            ln
            for ln in git("status", "--porcelain", "--", d).splitlines()
            if ln.strip()
        ]
        files = sorted(p for p in (REPO / d).rglob("*") if p.is_file())
        digests = {}
        for p in files:
            raw = p.read_bytes()
            digests[str(p.relative_to(REPO)).replace("\\", "/")] = sha16_bytes(raw)
            if sample_bytes is None:
                sample_bytes = raw
        ok = not touched_commits and not diffed and not dirty and len(files) > 0
        all_ok = all_ok and ok
        res["dirs"][d] = {
            "S1_commits_touching": touched_commits,
            "S2_tracked_diff": diffed,
            "S3_worktree_dirty": dirty,
            "S4_n_files_hashed": len(files),
            "digests": digests,
            "untouched": ok,
        }

    # ---- hasher non-constant control (on a COPY, never the originals) ------
    tmp = tempfile.mkdtemp(prefix="r2_frozen_")
    try:
        victim = pathlib.Path(tmp) / "v.bin"
        victim.write_bytes(sample_bytes)
        stable = sha16_bytes(victim.read_bytes()) == sha16_bytes(sample_bytes)
        victim.write_bytes(sample_bytes + b"\n# mutated")
        mutated_differs = sha16_bytes(victim.read_bytes()) != sha16_bytes(sample_bytes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    res["hasher_control"] = {
        "stable_rehash_equal": stable,
        "mutated_copy_differs": mutated_differs,
        "pass": stable and mutated_differs,
        "note": "run on a temp copy; no frozen file was opened for write",
    }
    res["all_frozen_untouched"] = all_ok and res["hasher_control"]["pass"]
    res["verdict"] = (
        "UNTOUCHED" if res["all_frozen_untouched"] else "TOUCHED-OR-UNPROVEN"
    )

    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    summary = {k: v for k, v in res.items() if k not in ("dirs",)}
    summary["per_dir"] = {
        d: {"n": v["S4_n_files_hashed"], "untouched": v["untouched"]}
        for d, v in res["dirs"].items()
    }
    print(json.dumps(summary, indent=1))
    return 0 if res["all_frozen_untouched"] else 1


if __name__ == "__main__":
    sys.exit(main())
