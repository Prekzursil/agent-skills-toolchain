#!/usr/bin/env python3
"""Write TST-0188 + TST-0190 probe files (shell portability)."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "command-center" / "p2-wave" / "probes"

ECHO = r'''#!/usr/bin/env python3
"""Probe-local child: print the argv it received as JSON (exact strings)."""
from __future__ import annotations

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(json.dumps({"argv": sys.argv[1:]}))
'''

M190 = r'''#!/usr/bin/env python3
"""TST-0190 measured layer: bash-driven invocations of a native child, used to
observe MSYS path conversion of arguments with and without MSYS_NO_PATHCONV."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run_bash(script: str, timeout: int = 60) -> tuple[int, str]:
    p = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=timeout
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def child_argv(posix_style_arg: str, suppress: bool) -> tuple[int, str]:
    """Spawn the native argv-echo child from bash; suppress toggles the env prefix."""
    py = sys.executable.replace("\\", "/")
    echo = (HERE / "echo_args.py").as_posix()
    prefix = "MSYS_NO_PATHCONV=1 " if suppress else ""
    script = "%s%s %s %s" % (prefix, py, echo, posix_style_arg)
    return run_bash(script)
'''

P188_1 = r'''#!/usr/bin/env python3
"""TST-0188 probe1 -- static scan for caret-bearing revision arguments + live
hazard check under pwsh7 (both-states: the bare-caret form must demonstrably
produce a WRONG or errored dereference on this box).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.resolve().parents[4]
UNIT = "TST-0188"
RUN = HERE / ".run-p1"

# dispatch surfaces the unit names; documentation/rules/probe dirs are excluded
SURFACES = [
    "tools/lib/codex-invocation.mjs",
    "tools/lib/codex_invocation.py",
]
CARET_PATTERNS = [
    re.compile(r"\^[{^]"),      # ^{commit}-style suffixes
    re.compile(r"\bHEAD\^"),    # HEAD^ parent refs
    re.compile(r"~\^"),         # ~^ forms
]


def scan_surfaces():
    hits = []
    for rel in SURFACES:
        f = REPO / rel
        if not f.is_file():
            hits.append({"path": rel, "line": 0, "text": "<surface-absent>", "note": "scanned surface missing"})
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pat in CARET_PATTERNS:
                if pat.search(line):
                    hits.append({"path": rel, "line": i, "text": line.strip()[:160]})
    return hits


def make_tagged_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    def git(*args):
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "seed")
    git("tag", "v1.2.3")
    truth = subprocess.run(
        ["git", "rev-list", "-n", "1", "v1.2.3"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    ).stdout.strip()
    return truth


def run_pwsh(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", cmd],
        cwd=str(RUN), capture_output=True, text=True, timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    repo = RUN / "repo"
    truth = make_tagged_repo(repo)

    # correct form: single-quoted revision dereferences to the tagged commit
    rc_quoted, out_quoted = run_pwsh("git rev-parse --verify 'v1.2.3^{commit}'")
    quoted_ok = rc_quoted == 0 and truth in out_quoted

    # hazard form: BARE caret through PowerShell (^ is the PS escape char)
    rc_bare, out_bare = run_pwsh("git rev-parse --verify v1.2.3^{commit}")
    hazard_demonstrated = (rc_bare != 0) or (truth not in out_bare)

    hits = scan_surfaces()

    payload = {
        "probe": "probe1-static-and-hazard",
        "unit_id": UNIT,
        "pass": not hits and quoted_ok and hazard_demonstrated,
        "static_scan": {
            "surfaces": SURFACES,
            "caret_call_sites": hits,
            "zero_such_call_sites": not hits,
        },
        "live_check_pwsh7": {
            "tagged_commit_truth": truth,
            "quoted_form": {"rc": rc_quoted, "matches_truth": quoted_ok},
            "bare_caret_form": {
                "rc": rc_bare,
                "output_tail": out_bare[-200:],
                "wrong_or_errored": hazard_demonstrated,
            },
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 sites=0 quoted=ok hazard=demonstrated" % UNIT)
        return 0
    print("FAILED:%s-probe1 sites=%d quoted_ok=%s hazard=%s"
          % (UNIT, len(hits), quoted_ok, hazard_demonstrated))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P188_2 = r'''#!/usr/bin/env python3
"""TST-0188 probe2 -- second-shell cross-check: the same tag-to-commit dereference
run under Git Bash must agree with the pwsh7-quoted result and the ground truth;
any divergence is a finding (reviewer requirement: second Windows shell).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNIT = "TST-0188"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    RUN.mkdir(parents=True)
    repo = RUN / "repo"
    repo.mkdir(parents=True)

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "seed")
    git("tag", "v2.0.0")

    truth = git("rev-list", "-n", "1", "v2.0.0").stdout.strip()

    # pwsh7 lane (quoted caret form)
    p1 = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "git rev-parse --verify 'v2.0.0^{commit}'"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    pwsh_commit = (p1.stdout or "").strip().splitlines()[0] if p1.returncode == 0 and p1.stdout else None

    # Git Bash lane (bare caret is safe in POSIX shells; single-quoted also fine)
    p2 = subprocess.run(
        ["bash", "-c", "git rev-parse --verify 'v2.0.0^{commit}'"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    bash_commit = (p2.stdout or "").strip().splitlines()[0] if p2.returncode == 0 and p2.stdout else None

    no_divergence = truth == pwsh_commit == bash_commit

    payload = {
        "probe": "probe2-second-shell",
        "unit_id": UNIT,
        "pass": no_divergence and bool(truth),
        "ground_truth_rev_list": truth,
        "pwsh7_quoted_commit": pwsh_commit,
        "git_bash_quoted_commit": bash_commit,
        "divergence": None if no_divergence else {
            "truth": truth, "pwsh7": pwsh_commit, "bash": bash_commit,
        },
        "reviewer_note": "the independent reviewer re-runs this on BOTH shells and reports any divergence as a finding",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 truth==pwsh7==bash (%s)" % (UNIT, truth[:12]))
        return 0
    print("FAILED:%s-probe2 divergence truth=%s pwsh7=%s bash=%s"
          % (UNIT, truth[:12], pwsh_commit and pwsh_commit[:12], bash_commit and bash_commit[:12]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P190_1 = r'''#!/usr/bin/env python3
"""TST-0190 probe1 -- MSYS_NO_PATHCONV scoped to revision-ish arguments.

Both assertions in one probe:
  (a) WITH the variable applied (env-prefix scope), the POSIX-style argument
      survives INTACT into the native child's argv (suppression works), and
  (b) WITHOUT the variable, the same argument is CONVERTED by MSYS to a
      Windows path that the child actually resolves (normal conversion works).
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import msys_lane as ML  # noqa: E402

UNIT = "TST-0190"


def main() -> int:
    arg = "/c/Users/Prekzursil"

    rc_s, out_s = ML.child_argv(arg, suppress=True)
    kept = None
    try:
        kept = json.loads(out_s.splitlines()[-1])["argv"][0]
    except Exception:
        pass
    survives_intact = kept == arg

    rc_c, out_c = ML.child_argv(arg, suppress=False)
    conv = None
    try:
        conv = json.loads(out_c.splitlines()[-1])["argv"][0]
    except Exception:
        pass
    converted = conv is not None and conv.replace("/", "\\").lower().startswith("c:") and "users" in conv.lower()

    payload = {
        "probe": "probe1-scoped-suppression",
        "unit_id": UNIT,
        "pass": survives_intact and converted,
        "with_env_prefix": {"rc": rc_s, "child_argv0": kept, "survives_intact": survives_intact},
        "without_env_prefix": {"rc": rc_c, "child_argv0": conv, "msys_converted": converted},
        "measured_lane": "bash -c spawning a native python child (real MSYS conversion path)",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 suppressed_arg_intact=%s unsuppressed_converted=%s"
              % (UNIT, survives_intact, converted))
        return 0
    print("FAILED:%s-probe1 intact=%s converted=%s (%r / %r)"
          % (UNIT, survives_intact, converted, kept, conv))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P190_2 = r'''#!/usr/bin/env python3
"""TST-0190 probe2 -- both-states control (regression seed windows-shell.md:11):
with MSYS_NO_PATHCONV set GLOBALLY, the path-carrying command must demonstrably
FAIL to resolve its argument - proving the probe can see the inversion a global
suppression silently causes.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import msys_lane as ML  # noqa: E402

UNIT = "TST-0190"
PY = None


def exists_child_script(tmp: Path) -> str:
    s = tmp / "exists_child.py"
    s.write_text(
        "import json, os, sys\n"
        "p = sys.argv[1]\n"
        "sys.stdout.write(json.dumps({'path': p, 'exists': os.path.isdir(p)}))\n",
        encoding="utf-8",
    )
    return s.as_posix()


def main() -> int:
    import subprocess

    tmp = HERE / ".run-p2"
    tmp.mkdir(parents=True, exist_ok=True)
    child = exists_child_script(tmp)
    py = sys.executable.replace("\\", "/")
    arg = "/c/Users/Prekzursil"

    # GLOBAL suppression: the child receives the unconverted POSIX-style arg and
    # cannot resolve it as a Windows directory -> the command demonstrably fails
    p_global = subprocess.run(
        ["bash", "-c",
         "export MSYS_NO_PATHCONV=1; %s %s %s" % (py, child, arg)],
        capture_output=True, text=True, timeout=60,
    )
    out_g = (p_global.stdout or "").strip().splitlines()
    try:
        doc_g = json.loads(out_g[-1])
    except Exception:
        doc_g = {}
    global_fails_to_resolve = (doc_g.get("exists") is False)

    # scoped/absent: conversion happens, the child resolves the directory
    p_norm = subprocess.run(
        ["bash", "-c", "%s %s %s" % (py, child, arg)],
        capture_output=True, text=True, timeout=60,
    )
    out_n = (p_norm.stdout or "").strip().splitlines()
    try:
        doc_n = json.loads(out_n[-1])
    except Exception:
        doc_n = {}
    normal_resolves = (doc_n.get("exists") is True)

    payload = {
        "probe": "probe2-global-suppression-fails",
        "unit_id": UNIT,
        "pass": global_fails_to_resolve and normal_resolves,
        "global_suppression": {
            "child_seen_path": doc_g.get("path"),
            "resolved": doc_g.get("exists"),
            "demonstrably_fails": global_fails_to_resolve,
        },
        "normal_conversion": {
            "child_seen_path": doc_n.get("path"),
            "resolved": doc_n.get("exists"),
        },
        "regression_seed": "windows-shell.md:11 global suppression silently skipped a clone",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 global-fails=%s normal-resolves=%s"
              % (UNIT, global_fails_to_resolve, normal_resolves))
        return 0
    print("FAILED:%s-probe2 global_fails=%s normal=%s (%r %r)"
          % (UNIT, global_fails_to_resolve, normal_resolves, doc_g, doc_n))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

D188 = PROBES / "TST-0188"
D190 = PROBES / "TST-0190"
D188.mkdir(parents=True, exist_ok=True)
D190.mkdir(parents=True, exist_ok=True)
(D188 / "probe1_static_and_hazard.py").write_text(P188_1, encoding="utf-8", newline="\n")
(D188 / "probe2_second_shell.py").write_text(P188_2, encoding="utf-8", newline="\n")
(D190 / "echo_args.py").write_text(ECHO, encoding="utf-8", newline="\n")
(D190 / "msys_lane.py").write_text(M190, encoding="utf-8", newline="\n")
(D190 / "probe1_scoped_suppression.py").write_text(P190_1, encoding="utf-8", newline="\n")
(D190 / "probe2_global_suppression.py").write_text(P190_2, encoding="utf-8", newline="\n")
import ast

for f in [P188_1, P188_2, ECHO, M190, P190_1, P190_2]:
    ast.parse(f)
print("TST-0188 + TST-0190 written + syntax OK")
