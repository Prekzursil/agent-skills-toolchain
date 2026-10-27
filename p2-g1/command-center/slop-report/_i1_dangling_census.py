"""INTEGRATE / step I1 -- how many DANGLING citations exist right now?

A dangling citation = a TRACKED artifact names a script that exists on this disk but is
NOT tracked by git. The citation resolves for the author and resolves to nothing in a
clone. That is the defect the SLOP lane fixed 45 instances of; this probe asks whether
the class is currently at zero, which decides whether a CI gate for it can be green.

Two scopes measured, because the answer decides the gate's reach:
  ROOT      command-center/_*.py            (the SLOP round-1 population)
  RECURSIVE command-center/**/_*.py         (every underscore script under the tree)

Detector control lives in _i1_control (same file, --control): a name known to be cited
must FIRE and a name that exists nowhere must stay QUIET, and the two must differ.
"""

import json
import os
import re
import subprocess
import sys
import uuid

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_i1_dangling_census.out.json")


def git_text(*args, check=True):
    r = subprocess.run(
        ["git", "-C", ROOT, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and r.returncode != 0:
        raise SystemExit(f"git {args} rc={r.returncode}: {r.stderr[:400]}")
    return r.stdout


def citations(names, rev="HEAD"):
    """basename -> sorted tracked paths whose HEAD blob contains it. {} for empty input."""
    if not names:
        return {}
    pfile = os.path.join(
        ROOT, f"command-center/slop-report/_i1_pat_{uuid.uuid4().hex}.txt"
    )
    with open(pfile, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(names) + "\n")
    try:
        r = subprocess.run(
            ["git", "-C", ROOT, "grep", "-I", "-F", "-n", "-f", pfile, rev],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        os.unlink(pfile)
    if r.returncode not in (0, 1):
        raise SystemExit(f"git grep rc={r.returncode}: {r.stderr[:400]}")
    pat = re.compile(
        "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    )
    cites: dict[str, set[str]] = {n: set() for n in names}
    for line in r.stdout.splitlines():
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        path, content = parts[1], parts[3]
        for m in pat.finditer(content):
            cites[m.group(0)].add(path)
    return {n: sorted(v) for n, v in cites.items()}


def scan(recursive):
    cc = os.path.join(ROOT, "command-center")
    found = []
    if recursive:
        for dirpath, dirnames, filenames in os.walk(cc):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for f in filenames:
                if f.startswith("_") and f.endswith(".py"):
                    rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(
                        "\\", "/"
                    )
                    found.append((f, rel))
    else:
        for f in sorted(os.listdir(cc)):
            if (
                f.startswith("_")
                and f.endswith(".py")
                and os.path.isfile(os.path.join(cc, f))
            ):
                found.append((f, f"command-center/{f}"))
    return found


def main():
    out = {"rev": git_text("rev-parse", "HEAD").strip()}
    tracked_all = set(git_text("ls-files").splitlines())

    for label, recursive in (("root", False), ("recursive", True)):
        found = scan(recursive)
        untracked = [(b, rel) for b, rel in found if rel not in tracked_all]
        # A basename can appear at >1 path; collapse to the basename the grep uses.
        names = sorted({b for b, _ in untracked})
        cites = citations(names)
        dangling = {n: v for n, v in cites.items() if v}
        out[label] = {
            "on_disk": len(found),
            "tracked": len(found) - len(untracked),
            "untracked": len(untracked),
            "untracked_distinct_basenames": len(names),
            "dangling_count": len(dangling),
            "dangling": {n: v[:6] for n, v in sorted(dangling.items())},
        }

    # ---- detector control, both states -------------------------------------------------
    # POSITIVE: a basename that is TRACKED and known-cited must produce >=1 citer.
    # NEGATIVE: a runtime-random name that exists nowhere must produce 0.
    pos_name = "_b1_cited_probes.py"
    neg_name = f"_zz_absent_{uuid.uuid4().hex}.py"
    ctl = citations([pos_name, neg_name])
    pos_hits, neg_hits = len(ctl.get(pos_name, [])), len(ctl.get(neg_name, []))
    out["control"] = {
        "positive_name": pos_name,
        "positive_hits": pos_hits,
        "negative_hits": neg_hits,
        "positive_fires": pos_hits >= 1,
        "negative_quiet": neg_hits == 0,
        "states_distinguishable": pos_hits >= 1 and neg_hits == 0,
    }
    out["control_pass"] = out["control"]["states_distinguishable"]

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True)[:4000])
    print(f"\nwrote {OUT}")
    return 0 if out["control_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
