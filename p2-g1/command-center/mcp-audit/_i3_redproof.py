#!/usr/bin/env python3
"""RED-PROOF for the mcp-audit CI wiring: the gate must go RED when the work rots.

A workflow never observed to fail is indistinguishable from a no-op, and this repository has
shipped that shape.  This takes a THROWAWAY FULL CLONE with the integration committed into
it, injects one realistic defect at a time, COMMITS it (the gate reads committed blobs, so a
working-tree edit would prove nothing), and requires:

  * BASELINE -- unmutated, ``ci_gate.py`` exits 0.  Without it the injections prove nothing.
  * EACH INJECTION -- ``ci_gate.py`` exits non-zero, AND the injection is confirmed to have
    changed the tree.  An injection that silently no-ops would score as "gate red" off some
    unrelated cause -- the effectiveness-control failure a sibling lane measured.
  * PRE-EXISTING CI -- measured by SIGNAL DELTA, where the signal is ``(exit code, hash of
    output)``.  Exit code alone is not enough: ``ruff format --check`` is ALREADY red on this
    tree from concurrent lanes, so an rc-only test would score it "unchanged" for every
    injection and mistake a permanently-red gate for a blind one.  A gate is credited with
    catching an injection only if its signal MOVED.
  * A LIVENESS CONTROL PER PRE-EXISTING GATE -- "unchanged" only means BLIND if that gate can
    be observed moving at all here.  An offline ``uvx``, a missing ``bash`` or a crashing
    script produces the identical signal in both states and would be scored blind on every
    row.  Each entry therefore gets a defect it MUST see; any that never moves is reported
    UNPROVEN, and the run fails rather than publishing an unmeasured blindness claim.
    (Measured: the first version of this script used ``uvx ruff@0.15.17`` and scored rc=2 in
    both states -- WSL had no DNS, so the tool never ran.  It is now the ambient ``ruff``,
    verified at exactly the pinned 0.15.17, with the version recorded in the report.)

Run on Linux, inside the throwaway clone::

    python3 command-center/mcp-audit/_i3_redproof.py --json OUT.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
LANE = "command-center/mcp-audit"
DISP = REPO / LANE / "disposition.json"
GATE = REPO / LANE / "ci_gate.py"
PINNED_RUFF = "0.15.17"


def sh(argv: list[str]) -> tuple[int, str]:
    p = subprocess.run(argv, cwd=REPO, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def signal(argv: list[str]) -> str:
    """(exit code, hash of output) -- what a maintainer would SEE from this gate."""
    rc, out = sh(argv)
    return (
        f"rc={rc}/out={hashlib.sha256(out.encode('utf-8', 'replace')).hexdigest()[:12]}"
    )


def ruff_cmd() -> list[str]:
    """The pinned ruff, ambient if its version matches, else via uvx."""
    exe = shutil.which("ruff")
    if exe:
        v = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout
        if PINNED_RUFF in v:
            return [exe]
    return ["uvx", f"ruff@{PINNED_RUFF}"]


RUFF = ruff_cmd()
# The pre-existing CI steps that could plausibly read a change under command-center/mcp-audit
# and are hermetic enough to run here.  SCOPE, stated because a wider claim would be false:
# the other ~21 quality.yml steps (types, per-package coverage, node, opengrep, gitleaks, osv)
# were NOT run.  None of them evaluates the SEMANTICS of a JSON measurement artifact, but that
# is reasoning, not measurement, and is labelled as such.
PREEXISTING: dict[str, list[str]] = {
    "quality/ruff-check": [*RUFF, "check", "."],
    "quality/ruff-format": [*RUFF, "format", "--check", "."],
    "quality/charter": ["bash", ".quality/charter_check.sh"],
    "p2next-rail-count": [sys.executable, "command-center/p2-next/rail_count_gate.py"],
}


def gate_rc(rev: str = "HEAD") -> tuple[int, str]:
    rc, out = sh([sys.executable, f"{LANE}/ci_gate.py", "--rev", rev])
    lines = [ln for ln in out.splitlines() if ln.startswith(("SUCCESS:", "FAILED:"))]
    return rc, (lines[-1][:150] if lines else out.strip().splitlines()[-1][:150])


def load_disp() -> dict:
    return json.loads(DISP.read_text(encoding="utf-8"))


def save_disp(d: dict) -> None:
    DISP.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------- the injections
def inj_a_drop_mounted_server() -> str:
    d = load_disp()
    d["rows"] = [r for r in d["rows"] if r["name"] != "cloud-hub"]
    save_disp(d)
    return f"dropped the 'cloud-hub' row (23 -> {len(d['rows'])})"


def inj_b_handedit_a_number() -> str:
    """Not hypothetical: tools/mcpapply/mcpapply/impact.py still says `cloud-hub -- 409
    tools` while the sweep measured 424 twice.  This is that rot applied to the artifact."""
    d = load_disp()
    for r in d["rows"]:
        if r["name"] == "cloud-hub":
            was, r["tool_count"] = r["tool_count"], 409
            save_disp(d)
            return f"cloud-hub tool_count {was} -> 409 (the stale impact.py value)"
    raise AssertionError("cloud-hub row not found")


def inj_c_irreversible_disposition() -> str:
    d = load_disp()
    for r in d["rows"]:
        if r["disposition"] == "DISABLE":
            r["disposition"] = "REMOVE"
            save_disp(d)
            return f"{r['name']}: DISABLE -> REMOVE"
    raise AssertionError("no DISABLE row")


def inj_d_ungated_new_gate() -> str:
    (REPO / LANE / "_zz_new_probe.py").write_text(
        '"""A new probe a future round adds and forgets to wire."""\n\n\n'
        "def main() -> int:\n"
        '    print("SUCCESS:zz-new-probe")\n'
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n",
        encoding="utf-8",
        newline="\n",
    )
    return "added _zz_new_probe.py (ruff-clean, so lint cannot see it)"


def inj_e_both_states_anchor_rots() -> str:
    src = GATE.read_text(encoding="utf-8")
    assert src.count('"630bb8af"') == 1, "anchor not found exactly once"
    GATE.write_text(src.replace('"630bb8af"', '"HEAD"'), encoding="utf-8", newline="\n")
    return "ci_gate CI_PLAN both-states anchor 630bb8af -> HEAD"


INJECTIONS = [
    ("INJ-A a mounted server vanishes from the inventory", inj_a_drop_mounted_server),
    (
        "INJ-B a measured number is hand-edited to a stale value",
        inj_b_handedit_a_number,
    ),
    (
        "INJ-C a recommendation becomes irreversible (REMOVE)",
        inj_c_irreversible_disposition,
    ),
    ("INJ-D a new gate file lands unwired", inj_d_ungated_new_gate),
    (
        "INJ-E the both-states anchor is re-pointed at HEAD",
        inj_e_both_states_anchor_rots,
    ),
]


# ------------------------------------------------- liveness controls for the blind-set
def live_ruff_check() -> str:
    (REPO / LANE / "_zz_syntax.py").write_text(
        "x=(1,\n", encoding="utf-8", newline="\n"
    )
    return "a python file that does not parse"


def live_ruff_format() -> str:
    (REPO / LANE / "_zz_fmt.py").write_text("x  =  1\n", encoding="utf-8", newline="\n")
    return "a python file with non-canonical spacing"


def live_charter() -> str:
    p = REPO / ".github/workflows/quality.yml"
    body = p.read_text(encoding="utf-8")
    p.write_text(
        body.replace("name: quality", "name: quality\n# gate-bogus-unclaimed-slug", 1),
        encoding="utf-8",
        newline="\n",
    )
    return "a gate-<slug> marker in quality.yml with no charter slug"


def live_rail_count() -> str:
    p = REPO / "command-center/CROSS-VENDOR-RAIL-STATUS.md"
    body = p.read_text(encoding="utf-8")
    p.write_text(body.replace("42", "43", 1), encoding="utf-8", newline="\n")
    return "the rail number in the owning doc rotated 42 -> 43"


LIVENESS = {
    "quality/ruff-check": live_ruff_check,
    "quality/ruff-format": live_ruff_format,
    "quality/charter": live_charter,
    "p2next-rail-count": live_rail_count,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    if sh(["git", "rev-parse", "--is-inside-work-tree"])[1].strip() != "true":
        print("FAILED:i-redproof not a git work tree")
        return 1
    base = sh(["git", "rev-parse", "HEAD"])[1].strip()
    print(
        f"== throwaway clone {REPO}  base {base[:12]}  {sys.platform}  ruff={' '.join(RUFF)} =="
    )

    def reset() -> None:
        sh(["git", "reset", "--hard", "--quiet", base])
        sh(["git", "clean", "-fdq"])

    def commit(msg: str) -> None:
        sh(["git", "add", "-A"])
        sh(
            [
                "git",
                "-c",
                "user.email=rp@local",
                "-c",
                "user.name=rp",
                "commit",
                "-q",
                "-m",
                msg,
            ]
        )

    reset()
    rc0, m0 = gate_rc()
    print(f"  BASELINE ci_gate rc={rc0}  {m0}")
    if rc0 != 0:
        print(
            "FAILED:i-redproof baseline already red -- injections would prove nothing"
        )
        return 1
    pre = {k: signal(v) for k, v in PREEXISTING.items()}
    for k, v in pre.items():
        print(f"  BASELINE pre-existing {k:22} {v}")

    bad: list[str] = []
    report: list[dict] = []
    for label, fn in INJECTIONS:
        reset()
        what = fn()
        changed = bool(sh(["git", "status", "--porcelain"])[1].strip())
        commit(f"redproof: {label}")
        rc, marker = gate_rc()
        post = {k: signal(v) for k, v in PREEXISTING.items()}
        caught = [k for k in PREEXISTING if post[k] != pre[k]]
        blind = [k for k in PREEXISTING if post[k] == pre[k]]
        ok = changed and rc != 0
        report.append(
            {
                "injection": label,
                "what": what,
                "injection_changed_tree": changed,
                "ci_gate_rc": rc,
                "ci_gate_marker": marker,
                "preexisting_caught": caught,
                "preexisting_blind": blind,
                "ok": ok,
            }
        )
        print(f"  {'ok ' if ok else 'BAD'} {label}\n        {what}")
        print(f"        effectiveness control (tree changed): {changed}")
        print(f"        ci_gate rc={rc}  {marker[:118]}")
        print(f"        pre-existing: caught={caught or '-none-'}  blind={blind}")
        if not ok:
            bad.append(label)

    print(
        "  -- liveness controls: can each pre-existing gate be observed MOVING here? --"
    )
    liveness: dict[str, dict] = {}
    for name, mk in LIVENESS.items():
        reset()
        what = mk()
        commit(f"redproof liveness: {name}")
        now = signal(PREEXISTING[name])
        moved = now != pre[name]
        liveness[name] = {
            "defect": what,
            "baseline": pre[name],
            "after": now,
            "moved": moved,
        }
        print(
            f"  {'ok ' if moved else 'BAD'} {name:22} {pre[name]} -> {now}  moved={moved}"
        )
        print(f"        injected: {what}")
        if not moved:
            bad.append(f"liveness/{name}")

    reset()
    rc_end, _ = gate_rc()
    print(f"  RESTORED ci_gate rc={rc_end} (must be 0)")
    if rc_end != 0:
        bad.append("restore")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                {
                    "base": base,
                    "ruff": RUFF,
                    "baseline_rc": rc0,
                    "preexisting_baseline": pre,
                    "injections": report,
                    "liveness_controls": liveness,
                    "restored_rc": rc_end,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if bad:
        print(f"FAILED:i-redproof {bad}")
        return 1
    print(
        f"SUCCESS:i-redproof {len(INJECTIONS)}/{len(INJECTIONS)} injections turn the gate RED, "
        f"{len(LIVENESS)}/{len(LIVENESS)} blind-set liveness controls fired"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
