"""BUILD R1 -- would MY commit turn gate-lint-format red? Measured in a fresh clone.

_b6's positive control FAILED: the known provenance-locked `adv0022_probe2.py` did not match
any digest declared near its name, so that detector is INERT and its "no locks found" reading
cannot license reformatting 45 evidence scripts. Falling back to the byte-preserving route
the repo already uses for exactly this class (ruff.toml excludes
`command-center/casualty/probes` with a written "the bytes ARE the measurement" rationale):

  commit the 45 cited probes UNCHANGED + negate them in .gitignore + exclude them in ruff.toml

This script proves that candidate does not red the gate, and -- critically -- proves the
exclude is what is doing the work rather than the files happening to be clean.

  T1 CANDIDATE : clone HEAD, drop in the 45 files, patch .gitignore + ruff.toml -> expect GREEN
  T2 CONTROL   : identical, but WITHOUT the ruff.toml exclude          -> expect RED
                 If T2 is also green the files were already formatted and the exclude is
                 unnecessary; if T1 is red the candidate is not shippable. Either way the
                 pair distinguishes the two hypotheses, which a single green run cannot.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = "C:/Users/Prekzursil/source/ast-integrate"
PIN = ["uvx", "ruff@0.15.17"]
OUT = os.path.join(ROOT, "command-center/slop-report/_b7_candidate_gate.out.json")

EXCLUDE_LINE = '    "command-center/_*.py",\n'


def run(args, cwd):
    r = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout + r.stderr


def fmt_list(text):
    return sorted(
        line.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for line in text.splitlines()
        if "Would reformat:" in line
    )


def build(clone, cited, with_exclude: bool):
    """Drop the 45 files in and patch the two config files."""
    for n in cited:
        src = os.path.join(ROOT, "command-center", n)
        dst = os.path.join(clone, "command-center", n)
        with open(src, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
    # .gitignore negations (append; order matters -- a later negation wins)
    gi = os.path.join(clone, ".gitignore")
    with open(gi, "rb") as fh:
        data = fh.read()
    add = "".join(f"!command-center/{n}\n" for n in cited).encode("utf-8")
    with open(gi, "wb") as fh:
        fh.write(data + b"\n" + add)
    if with_exclude:
        rt = os.path.join(clone, "ruff.toml")
        with open(rt, "r", encoding="utf-8", newline="") as fh:
            txt = fh.read()
        assert "extend-exclude = [" in txt
        txt = txt.replace(
            "extend-exclude = [\n", "extend-exclude = [\n" + EXCLUDE_LINE, 1
        )
        with open(rt, "w", encoding="utf-8", newline="") as fh:
            fh.write(txt)


def measure(rev, cited, with_exclude):
    tmp = tempfile.mkdtemp(prefix="candgate_")
    clone = os.path.join(tmp, "repo")
    try:
        rc, t = run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--quiet",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                ROOT,
                clone,
            ],
            tmp,
        )
        if rc != 0:
            return {"clone_rc": rc, "err": t[-500:]}
        run(["git", "checkout", "--quiet", "--detach", rev], clone)
        build(clone, cited, with_exclude)
        # make them tracked so this mirrors the post-commit state
        run(["git", "add", "-f", "--", *[f"command-center/{n}" for n in cited]], clone)
        rc_l, t_l = run([*PIN, "check", ".", "--output-format=concise"], clone)
        rc_f, t_f = run([*PIN, "format", "--check", "."], clone)
        would = fmt_list(t_f)
        return {
            "with_exclude": with_exclude,
            "ruff_check_rc": rc_l,
            "ruff_check_tail": t_l.strip().splitlines()[-2:],
            "ruff_format_rc": rc_f,
            "n_would_reformat": len(would),
            "would_reformat_cc_probes": [
                p for p in would if p.startswith("command-center/_")
            ][:8],
            "would_reformat_other": [
                p for p in would if not p.startswith("command-center/_")
            ][:8],
            "green": rc_l == 0 and rc_f == 0,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    rev = subprocess.run(
        ["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    cited = json.load(
        open(
            os.path.join(ROOT, "command-center/slop-report/_b1_cited_probes.out.json"),
            encoding="utf-8",
        )
    )["cited_names"]

    out = {"rev": rev, "n_files": len(cited)}
    out["T1_candidate_with_exclude"] = measure(rev, cited, True)
    out["T2_control_without_exclude"] = measure(rev, cited, False)

    t1, t2 = out["T1_candidate_with_exclude"], out["T2_control_without_exclude"]
    checks = {
        "T1_candidate_is_green": bool(t1.get("green")),
        "T2_control_is_red": not t2.get("green", True),
        "states_distinguishable": bool(t1.get("green")) != bool(t2.get("green", True)),
    }
    out["checks"] = checks
    out["controls_verdict"] = "PASS" if all(checks.values()) else "FAIL"
    out["verdict"] = (
        "SHIPPABLE: commit-as-is + ruff exclude keeps gate-lint-format green"
        if checks["T1_candidate_is_green"]
        else "NOT SHIPPABLE"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
