"""SSOT drift gate — fails when code the live MCP fleet EXECUTES has fallen behind `main`.

THE HAZARD THIS CLOSES. On this estate, editing and executing happen in two different
checkouts of one repo:

  ~/source/ast-integrate           holds `main`, is where all editing happens
  ~/source/agent-skills-toolchain  permanently detached (git forbids two checkouts of one
                                   branch), ~161 commits behind, and is the path that 8
                                   config fields point at -- 5 live MCP servers load their
                                   entry points from it

Nothing is broken while the two agree on the executed files. The failure mode is silent and
deferred: the next commit under `tools/mcp/**` lands on `main`, the running fleet keeps
executing the old bytes, and no test, gate or human notices because both checkouts are
"clean". This gate turns that latent divergence into a loud, mechanical failure.

WHAT IT MEASURES. For each directory the fleet actually loads from, the count of files that
differ between the executed checkout's HEAD and the reference (`origin/main` by default).
Non-zero => the running fleet is stale.

WHY IT CANNOT QUIETLY REPORT CLEAN. A differ that returns 0 for every input would report
"no drift" forever -- the exact shape of an inert control that passes and gets recorded as
diligence. So the gate runs a POSITIVE CONTROL on every invocation: the same differ, same
revision pair, over paths known to carry churn. If the control returns 0, the differ is not
working and the gate exits FAIL-CLOSED (exit 3) instead of reporting a clean fleet. The two
hypotheses -- "the fleet is current" vs "the differ is blind" -- produce different outputs by
construction.

Exit codes:  0 clean · 1 drift detected · 2 misconfigured · 3 detector broken (fail-closed)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

DEFAULT_EXECUTED = "C:/Users/Prekzursil/source/agent-skills-toolchain"

# The directories the live fleet loads entry points from, as resolved from the 8 field-level
# config references in SSOT-CLONE-INVENTORY.md §3 (receipt: command-center/ssot/exec-vs-edit.json).
# Deliberately a static list rather than a re-read of ~/.claude.json: those files are
# credential-bearing, and this gate never needs to open them.
EXECUTED_DIRS = [
    "tools/mcp/cloud-hub",
    "tools/mcp/qdx-rush-mcp",
    "tools/mcp/search-hub",
    "tools/mcp/social-hub",
    "tools/scholarly-access-mcp",
]

# Paths used only to prove the differ is alive. Chosen because they carry routine churn.
CONTROL_DIRS = ["command-center", "docs", "skills"]


def git(args: list[str], repo: str) -> tuple[int, str]:
    p = subprocess.run(
        ["git", "-C", repo] + args, capture_output=True, text=True, timeout=180
    )
    return p.returncode, (p.stdout or "")


def changed_count(
    repo: str, base: str, head: str, paths: list[str]
) -> tuple[int, list[str]]:
    rc, out = git(["diff", "--name-only", f"{base}..{head}", "--"] + paths, repo)
    if rc != 0:
        return -1, []
    files = [ln.strip() for ln in out.split("\n") if ln.strip()]
    return len(files), files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--executed",
        default=DEFAULT_EXECUTED,
        help="the checkout the live fleet loads code from",
    )
    ap.add_argument("--ref", default="origin/main", help="the SSOT reference revision")
    ap.add_argument("--json", dest="as_json", action="store_true")
    args = ap.parse_args()

    exe = args.executed
    if not pathlib.Path(exe).exists():
        # THREE OUTCOMES, not two -- the same distinction `r5_deploy_drift_gate.py` draws.
        # An absent checkout is not a failed comparison, it is an UNPERFORMABLE one, and
        # which answer is honest depends on WHY it is absent:
        #
        #   default path absent  -> the runner world. DEFAULT_EXECUTED is the hardcoded
        #       "C:/Users/Prekzursil/source/agent-skills-toolchain", which cannot exist on
        #       ubuntu-latest. Reporting NOT-CHECKED names that world and asserts nothing.
        #   explicit path absent -> the caller named a path and got it wrong. That is a
        #       real error and still fails closed at rc=2, so a typo cannot be laundered
        #       into a clean-looking NOT-CHECKED.
        #
        # WHY THIS MATTERS: measured 2026-08-14, this gate is invoked by NO workflow, and
        # the synthesis lane's ranked action #5 was to wire it into a push-triggered one.
        # Wired unchanged it would have exited 2 on every run -- `FAILED:ssot-drift-gate
        # executed checkout absent: C:/Users/...` -- and turned CI permanently red. The
        # hardcoded Windows absolute path is the same local-green/CI-red mechanism that
        # broke the hook-audit H2 control earlier in the same session.
        if exe == DEFAULT_EXECUTED:
            print(
                "SUCCESS:ssot-drift-gate NOT-CHECKED -- the executed checkout is ABSENT "
                f"({exe}); this is the runner world, and this run asserted NOTHING about "
                "whether the live fleet is executing stale bytes."
            )
            return 0
        print(f"FAILED:ssot-drift-gate executed checkout absent: {exe}")
        return 2

    rc, head = git(["rev-parse", "HEAD"], exe)
    if rc != 0:
        print(f"FAILED:ssot-drift-gate {exe} is not a git checkout")
        return 2
    head = head.strip()

    rc, ref_sha = git(["rev-parse", args.ref], exe)
    if rc != 0:
        print(
            f"FAILED:ssot-drift-gate cannot resolve {args.ref} in {exe} "
            f"(fetch first: git -C {exe} fetch origin)"
        )
        return 2
    ref_sha = ref_sha.strip()

    rc, out = git(["rev-list", "--left-right", "--count", f"{ref_sha}...{head}"], exe)
    behind, ahead = (out.split() + ["?", "?"])[:2] if rc == 0 else ("?", "?")

    # ---- POSITIVE CONTROL: prove the differ can see a real difference at this rev pair ----
    ctl_n, _ = changed_count(exe, ref_sha, head, CONTROL_DIRS)
    ctl_all, _ = changed_count(exe, ref_sha, head, ["."])

    print("=== SSOT drift gate ===")
    print(f"executed checkout : {exe}")
    print(f"  HEAD            : {head[:12]}")
    print(f"  {args.ref:15s} : {ref_sha[:12]}  (behind {behind} / ahead {ahead})")
    print(
        f"detector control  : {ctl_n} changed under {CONTROL_DIRS}, "
        f"{ctl_all} across the whole tree"
    )

    if head == ref_sha:
        print(
            "  control N/A: executed checkout is exactly at the reference, so a zero "
            "everywhere is the CORRECT answer, not a blind differ."
        )
    elif ctl_n <= 0 and ctl_all <= 0:
        print(
            "  CONTROL FAILED: the executed checkout is NOT at the reference "
            f"(behind {behind}) yet the differ reports 0 changes everywhere. "
            "The differ is blind -- refusing to certify the fleet as current."
        )
        print("FAILED:ssot-drift-gate detector-broken")
        return 3
    else:
        print(
            "  control PASS: the differ demonstrably sees changes at this revision pair, "
            "so a zero under the executed dirs is a measurement and not a silence."
        )

    # ---- THE ACTUAL CLAIM ----
    total = 0
    rows = []
    print(f"\nexecuted surface ({len(EXECUTED_DIRS)} dirs the live fleet loads from):")
    for d in EXECUTED_DIRS:
        n, files = changed_count(exe, ref_sha, head, [d])
        n = max(n, 0)
        total += n
        rows.append({"dir": d, "changed": n, "files": files[:20]})
        mark = "DRIFT" if n else "  ok "
        print(f"  [{mark}] {n:4d}  {d}")
        for f in files[:8]:
            print(f"            - {f}")

    payload = {
        "executed": exe,
        "executed_head": head,
        "ref": args.ref,
        "ref_sha": ref_sha,
        "behind": behind,
        "ahead": ahead,
        "control_changed_under_control_dirs": ctl_n,
        "control_changed_whole_tree": ctl_all,
        "executed_dirs": rows,
        "total_drift": total,
    }
    outp = pathlib.Path("command-center/ssot/drift-gate.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    with open(outp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2)
    if args.as_json:
        print(json.dumps(payload, indent=2))

    print()
    if total:
        print(
            f"{total} file(s) the live MCP fleet executes are STALE against {args.ref}."
        )
        print("The running servers are loading superseded bytes. Remediate by either:")
        print(
            f"  (a) advance the executed checkout:  git -C {exe} fetch origin && "
            f"git -C {exe} checkout {args.ref[7:] if args.ref.startswith('origin/') else args.ref}"
        )
        print(
            "      -- NOTE: git forbids two checkouts of one branch, so this lands DETACHED "
            "at the ref; that is expected and is how this checkout already operates."
        )
        # ASCII only: this line goes to CI logs and Windows consoles, where a non-ASCII
        # glyph mojibakes into noise that looks like a corrupted diagnostic.
        print(
            "  (b) repoint the 8 config fields (SSOT-CLONE-INVENTORY.md sec.3) at a checkout "
            "that tracks main."
        )
        print(
            "Then restart the affected MCP servers -- a running server does not reload from disk."
        )
        print(f"FAILED:ssot-drift-gate drift={total}")
        return 1

    print(
        f"0 files under the executed surface differ from {args.ref}: the live fleet is "
        "executing current bytes."
    )
    print(
        "Correctly scoped: this says nothing about the other "
        f"{max(int(behind) if behind.isdigit() else 0, 0)} commits the executed checkout is "
        "behind -- only that none of them touched the 5 executed directories. The hazard "
        "remains latent, not absent."
    )
    print(f"SUCCESS:ssot-drift-gate drift=0 behind={behind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
