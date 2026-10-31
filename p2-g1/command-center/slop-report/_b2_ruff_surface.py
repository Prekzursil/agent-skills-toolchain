"""BUILD R1 / step B2 -- what does the ruff gate ACTUALLY see, and what would my commit add?

Three states, measured with the CI pin (ruff 0.15.17) from the repo root so the committed
ruff.toml applies (a bare temp dir would default to line-length 88 and manufacture a false
red -- that exact trap is on record).

  S1 WORKTREE : `ruff check .` / `ruff format --check .` as run locally. Sees untracked,
                non-ignored files that a CI checkout does NOT contain.
  S2 CI-EQUIV : S1 restricted to TRACKED paths. This is what CI can actually fail on.
  S3 CANDIDATE: the 45 cited probe scripts I am about to un-ignore and commit. Explicit
                path args bypass .gitignore, which is precisely the post-commit condition.

Also a both-states control on the claim "gitignore is what hides command-center/_*.py from
the ruff gate": they must be ABSENT from S1 and PRESENT under --no-respect-gitignore.
"""

import json
import os
import re
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_b2_ruff_surface.out.json")


def run(args):
    r = subprocess.run(
        [*PIN, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout + r.stderr


def norm(p):
    return p.replace("\\", "/")


LINT_RE = re.compile(r"^(.+?):\d+:\d+: (\S+)")
FMT_RE = re.compile(r"^Would reformat: (.+)$")


def lint_files(text):
    """path -> list of rule codes"""
    d = {}
    for line in text.splitlines():
        m = LINT_RE.match(line.strip())
        if m:
            d.setdefault(norm(m.group(1)), []).append(m.group(2))
    return d


def fmt_files(text):
    return sorted(
        {
            norm(m.group(1))
            for m in (FMT_RE.match(x.strip()) for x in text.splitlines())
            if m
        }
    )


def main():
    tracked = set(
        subprocess.run(
            ["git", "-C", ROOT, "ls-files"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    )
    out = {"tracked_total": len(tracked)}

    # ---- S1 worktree ---------------------------------------------------------------------
    _, t = run(["check", ".", "--output-format=concise"])
    s1_lint = lint_files(t)
    _, t = run(["format", "--check", "."])
    s1_fmt = fmt_files(t)
    out["S1_worktree"] = {
        "lint_files": len(s1_lint),
        "lint_violations": sum(len(v) for v in s1_lint.values()),
        "fmt_files": len(s1_fmt),
    }

    # ---- S2 CI-equivalent: only tracked paths --------------------------------------------
    s2_lint = {p: v for p, v in s1_lint.items() if p in tracked}
    s2_fmt = [p for p in s1_fmt if p in tracked]
    out["S2_ci_equivalent"] = {
        "lint_files": len(s2_lint),
        "lint_violations": sum(len(v) for v in s2_lint.values()),
        "lint_detail": s2_lint,
        "fmt_files": len(s2_fmt),
        "fmt_detail": s2_fmt,
        "verdict": "CI-GREEN on ruff"
        if not s2_lint and not s2_fmt
        else "CI-RED on ruff",
    }
    out["S1_minus_S2_untracked_noise"] = {
        "lint_files": sorted(set(s1_lint) - tracked),
        "fmt_files": sorted(set(s1_fmt) - tracked),
    }

    # ---- S3 the commit candidates ---------------------------------------------------------
    cited = json.load(
        open(
            os.path.join(ROOT, "command-center/slop-report/_b1_cited_probes.out.json"),
            encoding="utf-8",
        )
    )["cited_names"]
    paths = [f"command-center/{n}" for n in cited]
    _, t = run(["check", *paths, "--output-format=concise"])
    c_lint = lint_files(t)
    _, t = run(["format", "--check", *paths])
    c_fmt = fmt_files(t)
    out["S3_candidates"] = {
        "n_candidates": len(paths),
        "lint_files": len(c_lint),
        "lint_violations": sum(len(v) for v in c_lint.values()),
        "lint_detail": c_lint,
        "fmt_files": len(c_fmt),
        "fmt_detail": c_fmt,
        "rule_histogram": {},
    }
    hist = {}
    for v in c_lint.values():
        for code in v:
            hist[code] = hist.get(code, 0) + 1
    out["S3_candidates"]["rule_histogram"] = dict(
        sorted(hist.items(), key=lambda kv: -kv[1])
    )

    # ---- CONTROL: is .gitignore what hides command-center/_*.py from `ruff check .`? -------
    hidden_in_s1 = sorted(p for p in s1_lint if p.startswith("command-center/_"))
    _, t = run(["check", ".", "--no-respect-gitignore", "--output-format=concise"])
    nog_lint = lint_files(t)
    shown_no_gitignore = sorted(p for p in nog_lint if p.startswith("command-center/_"))
    out["control_gitignore_hides_from_ruff"] = {
        "hypothesis": "gitignore, not ruff.toml, is why command-center/_*.py escape the gate",
        "cc_probe_lint_files_with_gitignore": len(hidden_in_s1),
        "cc_probe_lint_files_without_gitignore": len(shown_no_gitignore),
        "sample_without": shown_no_gitignore[:6],
        "checks": {
            "quiet_when_ignored": len(hidden_in_s1) == 0,
            "fires_when_not_ignored": len(shown_no_gitignore) > 0,
        },
    }
    c = out["control_gitignore_hides_from_ruff"]["checks"]
    out["control_gitignore_hides_from_ruff"]["verdict"] = (
        "PASS" if all(c.values()) else "FAIL"
    )

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1)[:6000])
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
