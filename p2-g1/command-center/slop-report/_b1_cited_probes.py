"""BUILD R1 / step B1 -- re-derive the cited-probe set from scratch.

Independent of the grounding lane's numbers. Two questions:
  Q1: how many command-center/_*.py exist on disk, how many are TRACKED?
  Q2: which of them are NAMED INSIDE a TRACKED (committed) artifact?

Method: ONE `git grep -F -f <patterns> HEAD` pass over the committed tree (blobs, not the
worktree -- a sibling's uncommitted edit must not inflate the citation count).
Detector control (both states) lives in _b1_control.py.
"""

import json
import os
import re
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_b1_cited_probes.out.json")


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
    """name -> sorted list of tracked paths whose HEAD blob names it."""
    pfile = os.path.join(ROOT, "command-center/slop-report/_b1_patterns.txt")
    with open(pfile, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(names) + "\n")
    r = subprocess.run(
        ["git", "-C", ROOT, "grep", "-I", "-F", "-n", "-f", pfile, rev],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    os.unlink(pfile)
    # rc 1 == no matches, which is a legitimate answer (used by the control)
    if r.returncode not in (0, 1):
        raise SystemExit(f"git grep rc={r.returncode}: {r.stderr[:400]}")
    pat = re.compile(
        "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    )
    cites: dict[str, set[str]] = {n: set() for n in names}
    for line in r.stdout.splitlines():
        # format: <rev>:<path>:<lineno>:<content>
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        path, content = parts[1], parts[3]
        for m in pat.finditer(content):
            cites[m.group(0)].add(path)
    return {n: sorted(v) for n, v in cites.items()}


def main():
    out = {"rev": git_text("rev-parse", "HEAD").strip()}

    cc = os.path.join(ROOT, "command-center")
    on_disk = sorted(
        f
        for f in os.listdir(cc)
        if f.startswith("_")
        and f.endswith(".py")
        and os.path.isfile(os.path.join(cc, f))
    )
    out["on_disk_count"] = len(on_disk)
    out["on_disk_bytes"] = sum(os.path.getsize(os.path.join(cc, f)) for f in on_disk)

    tracked_all = set(git_text("ls-files").splitlines())
    out["tracked_total_repo"] = len(tracked_all)
    tracked_probes = sorted(f for f in on_disk if f"command-center/{f}" in tracked_all)
    out["tracked_probe_count"] = len(tracked_probes)
    out["tracked_probes"] = tracked_probes

    names = [f for f in on_disk if f not in set(tracked_probes)]
    out["untracked_probe_count"] = len(names)

    cites = citations(names)
    # A probe naming ITSELF inside its own untracked body cannot be a citer (untracked files
    # are not in HEAD), so every citer here is by construction a committed artifact.
    cited = {n: v for n, v in cites.items() if v}
    out["cited_count"] = len(cited)
    out["cited_bytes"] = sum(os.path.getsize(os.path.join(cc, n)) for n in cited)
    out["uncited_count"] = len(names) - len(cited)
    out["cited_names"] = sorted(cited)
    out["cited_detail"] = {
        n: {"n_citers": len(v), "citers": v[:8]}
        for n, v in sorted(cited.items(), key=lambda kv: -len(kv[1]))
    }
    out["top_cited"] = [
        [n, len(v)]
        for n, v in sorted(cited.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:10]
    ]

    r = subprocess.run(
        ["git", "-C", ROOT, "check-ignore", "-v", f"command-center/{names[0]}"],
        capture_output=True,
        text=True,
    )
    out["check_ignore_sample"] = r.stdout.strip()

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(
        json.dumps(
            {
                k: v
                for k, v in out.items()
                if k not in ("cited_detail", "cited_names", "tracked_probes")
            },
            indent=1,
        )
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
