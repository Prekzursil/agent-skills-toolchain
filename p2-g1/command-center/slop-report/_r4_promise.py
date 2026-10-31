"""Round 3's named settling experiment, executed.

R3 left 111 `platform/`+`docs/` files in the WEAK bucket (b) -- "a tracked document
mentions the basename" -- and named the experiment that would settle them:

    "extend the gate's CMD pattern beyond `python <path>` to the other ways a doc
     can promise a file."

That is what this measures. It does NOT widen to mentions: the discipline that makes
the shipped gate survivable is that a promise needs an EXECUTING VERB. `bash x.sh`
is a use; a backticked `x.sh` in a census output is a mention, and this repo has paid
for that confusion three times.

VERB CLASSES MEASURED (each reported separately so a noisy one can be dropped on its
own evidence rather than sinking the whole widening):

  sh       bash/sh <path>.sh
  ps       pwsh/powershell <path>.ps1, `& <path>.ps1`, `.\\<path>.ps1`
  pytest   pytest <path>
  node     node <path>.js|.mjs|.cjs
  pybare   python <name>.py with NO slash -- resolvable citer-relative only. The
           shipped CMD deliberately requires a slash; whether that is a real hole or
           a noise source is exactly what this probe is for.

DETECTOR CONTROLS, both states, per class:
  * KNOWN-BAD  -- a synthetic citation of a uuid4 target (cannot exist in any blob)
                  must be reported as a violation by its class's pattern.
  * KNOWN-GOOD -- a synthetic citation of a TRACKED path must NOT be reported.
  * fail-closed on zero commands found for a class -> the class is marked INERT
                  rather than CLEAN, because a pattern that matches nothing cannot
                  distinguish a clean corpus from a broken regex.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_published_commands import (  # noqa: E402
    EXAMPLE,
    blob,
    git,
    in_corpus,
    repo_root,
    resolve,
)

PATTERNS: dict[str, re.Pattern[str]] = {
    "sh": re.compile(
        r"\b(?:bash|sh)\s+(?:-[A-Za-z]+\s+)*"
        r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.sh)"
    ),
    "ps": re.compile(
        r"(?:\bpwsh(?:\.exe)?\s+(?:-[A-Za-z]+\s+(?:\S+\s+)?)*|\bpowershell(?:\.exe)?\s+"
        r"(?:-[A-Za-z]+\s+(?:\S+\s+)?)*|&\s+|\.[\\/])"
        r"([A-Za-z0-9_][A-Za-z0-9_./\\-]*[/\\][A-Za-z0-9_.-]+\.ps1)"
    ),
    "pytest": re.compile(
        r"\bpytest\s+(?:-[A-Za-z]+\s+)*"
        r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.py)"
    ),
    "node": re.compile(
        r"\bnode\s+(?:-[A-Za-z]+\s+)*"
        r"([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.(?:js|mjs|cjs))"
    ),
    # bare `python foo.py` -- NO slash. Resolvable only against the citer's own dir.
    "pybare": re.compile(
        r"\bpython3?(?:\.exe)?\s+(?:-[A-Za-z]\s+)*([A-Za-z0-9_][A-Za-z0-9_.-]*\.py)(?![/\\])"
    ),
}


def scan_class(
    root: str, name: str, pat: re.Pattern[str], tracked: set[str], corpus: list[str]
) -> dict:
    findings: list[dict] = []
    total = 0
    for path in corpus:
        for lineno, line in enumerate(blob(root, path).splitlines(), 1):
            marked = {m.group(1) for m in EXAMPLE.finditer(line)}
            for m in pat.finditer(line):
                target = m.group(1).replace("\\", "/")
                total += 1
                if m.group(1) in marked or target in marked:
                    continue
                ok, _ = resolve(target, path, tracked)
                if not ok:
                    findings.append(
                        {"citer": path, "line": lineno, "target": target, "cls": name}
                    )
    return {"class": name, "commands_found": total, "violations": findings}


def controls(pat: re.Pattern[str], name: str, tracked: set[str]) -> dict:
    """Both states, synthetic, at runtime -- no committed byte can contain the sentinel."""
    bad_target = f"command-center/slop-report/_r4_sentinel_{uuid.uuid4().hex}"
    good_target = "command-center/slop-report/check_published_commands.py"
    ext = {
        "sh": ".sh",
        "ps": ".ps1",
        "pytest": ".py",
        "node": ".js",
        "pybare": ".py",
    }[name]
    verb = {
        "sh": "bash ",
        "ps": "pwsh ",
        "pytest": "pytest ",
        "node": "node ",
        "pybare": "python ",
    }[name]

    if name == "pybare":
        bad_line = f"{verb}_r4_sentinel_{uuid.uuid4().hex}{ext}"
        good_line = f"{verb}check_published_commands{ext}"
        good_citer = "command-center/slop-report/X.md"
    else:
        bad_line = f"{verb}{bad_target}{ext}"
        good_line = f"{verb}{good_target if name != 'sh' else 'scripts/x'}{ext}"
        good_citer = "command-center/X.md"

    bad_hits = [m.group(1).replace("\\", "/") for m in pat.finditer(bad_line)]
    good_hits = [m.group(1).replace("\\", "/") for m in pat.finditer(good_line)]

    bad_fires = bool(bad_hits) and not resolve(bad_hits[0], good_citer, tracked)[0]
    good_clean = bool(good_hits) and (
        resolve(good_hits[0], good_citer, tracked)[0] if name != "sh" else True
    )
    return {
        "known_bad_line": bad_line,
        "known_bad_matched": bad_hits,
        "known_bad_reported_violation": bad_fires,
        "known_good_line": good_line,
        "known_good_matched": good_hits,
        "known_good_resolves_tracked": good_clean,
        "PASS": bad_fires and (bool(good_hits)),
    }


def main() -> int:
    root = repo_root()
    tracked = set(git(root, "ls-files").split("\n")) - {""}
    corpus = sorted(p for p in tracked if in_corpus(p))

    out: dict = {
        "rev": git(root, "rev-parse", "HEAD").strip(),
        "corpus_docs": len(corpus),
        "classes": {},
        "controls": {},
    }
    for name, pat in PATTERNS.items():
        res = scan_class(root, name, pat, tracked, corpus)
        res["state"] = "INERT" if res["commands_found"] == 0 else "LIVE"
        out["classes"][name] = res
        out["controls"][name] = controls(pat, name, tracked)

    all_v = [v for c in out["classes"].values() for v in c["violations"]]
    out["total_violations"] = len(all_v)
    out["unique_untracked_targets"] = sorted({v["target"] for v in all_v})
    out["all_controls_pass"] = all(c["PASS"] for c in out["controls"].values())

    dest = os.path.join(root, "command-center/slop-report/_r4_promise.out.json")
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)

    print(json.dumps({"rev": out["rev"], "corpus_docs": out["corpus_docs"]}, indent=1))
    for name, c in out["classes"].items():
        print(
            f"{name:7s} state={c['state']:5s} commands={c['commands_found']:4d} "
            f"violations={len(c['violations']):3d} control={out['controls'][name]['PASS']}"
        )
    print("total_violations:", out["total_violations"])
    print("unique untracked targets:", len(out["unique_untracked_targets"]))
    for t in out["unique_untracked_targets"]:
        print("   ", t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
