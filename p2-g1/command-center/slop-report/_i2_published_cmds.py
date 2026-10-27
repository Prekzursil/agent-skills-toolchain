"""INTEGRATE / step I2 -- count the FIELD, not the document.

I1 refuted the obvious gate. A bare `git grep` for an untracked script's basename reports
103-158 "dangling citations", but 157 of the citers are the SLOP lane's OWN census outputs
(`_slop_measure*.out.json`), whose entire job is to ENUMERATE untracked filenames. A census
that lists a file is measuring it, not depending on it. Gating on that would fire on the
measurement instead of the defect -- the use-vs-mention failure this repo has already paid
for.

The field that IS a dependency: a committed artifact that publishes a RUNNABLE COMMAND.
`python <path>` in a tracked document is a promise -- "run this and you get the result".
If <path> is not tracked, the promise is unkeepable in any clone. A JSON array element
"_foo.py" never matches `python <path>`, so the census noise disappears by construction.

This probe measures the landscape across corpus scopes before a gate is written to it.
"""

import json
import os
import re
import subprocess
import sys

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
OUT = os.path.join(ROOT, "command-center/slop-report/_i2_published_cmds.out.json")

# `python foo/bar.py`, `python3 -u foo/bar.py`, optionally inside backticks. The path must
# contain a slash: a bare `foo.py` cannot be resolved against the repo root unambiguously.
CMD = re.compile(
    r"\bpython3?(?:\.exe)?\s+(?:-[A-Za-z]\s+)*([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.py)"
)


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


def blob(path):
    r = subprocess.run(
        ["git", "-C", ROOT, "cat-file", "-p", f"HEAD:{path}"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def main():
    tracked = set(git_text("ls-files").splitlines())
    rev = git_text("rev-parse", "HEAD").strip()

    scopes = {
        "md_all": lambda p: p.endswith(".md"),
        "md_cc_docs": lambda p: (
            p.endswith(".md")
            and (p.startswith("command-center/") or p.startswith("docs/"))
        ),
        "text_cc_docs": lambda p: (
            p.rsplit(".", 1)[-1] in ("md", "txt", "json", "yml", "yaml")
            and (p.startswith("command-center/") or p.startswith("docs/"))
        ),
        "py_cc": lambda p: p.endswith(".py") and p.startswith("command-center/"),
    }

    out = {"rev": rev, "tracked_total": len(tracked), "scopes": {}}
    for label, pred in scopes.items():
        corpus = sorted(p for p in tracked if pred(p))
        hits = []  # (citer, lineno, path)
        for p in corpus:
            for i, line in enumerate(blob(p).splitlines(), 1):
                for m in CMD.finditer(line):
                    hits.append((p, i, m.group(1)))
        targets = {}
        for citer, ln, tgt in hits:
            targets.setdefault(tgt, []).append(f"{citer}:{ln}")
        untracked_t = {t: v for t, v in targets.items() if t not in tracked}
        missing_disk = {
            t: v
            for t, v in untracked_t.items()
            if not os.path.isfile(os.path.join(ROOT, t))
        }
        out["scopes"][label] = {
            "corpus_files": len(corpus),
            "commands_found": len(hits),
            "distinct_targets": len(targets),
            "untracked_targets": len(untracked_t),
            "untracked_and_absent_on_disk": len(missing_disk),
            "violations": {t: v[:4] for t, v in sorted(untracked_t.items())},
        }

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    for label, s in out["scopes"].items():
        print(
            f"{label:14s} corpus={s['corpus_files']:5d} cmds={s['commands_found']:5d} "
            f"targets={s['distinct_targets']:4d} UNTRACKED={s['untracked_targets']:3d} "
            f"(absent on disk {s['untracked_and_absent_on_disk']})"
        )
    print()
    for label in ("md_all", "text_cc_docs"):
        v = out["scopes"][label]["violations"]
        if v:
            print(f"-- {label} violations --")
            for t, where in sorted(v.items()):
                print(f"   {t}   <- {where}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
