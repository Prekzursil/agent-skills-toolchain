"""Execute the two actionable buckets, with the controls that make them checkable.

BUCKET (b) -- `platform/` evidence that exists on ONE disk and is promised by
committed documents. 14 files are cited as `python <path>` by tracked reports.
They are committed BYTE-UNCHANGED; the one lint error blocking that (an F841 in
`_p12_refute_predicate.py`, already recorded in
`published-commands-baseline.json` as the reason the file stayed uncommitted) is
silenced by a per-file ignore in `ruff.toml` rather than by editing evidence.

  Control A -- narrowness. The SAME F841 shape at a different path must still be
  flagged, otherwise the ignore went global and the gate stopped measuring.
  Control B -- both states on the real target: `ruff check` over the 14 was rc 1
  (F841) before the ruff.toml edit and must be rc 0 after.

BUCKET (d) -- `$null`, a 0-byte file at the repo root created by running a
PowerShell `2>$null` redirect under a shell that does not expand it. Deleted.
Nothing can be lost from a 0-byte file, so the deletion needs no reference scan
to be safe; what it does need is proof it did not disturb anything else, so the
tracked-file dirty set is captured before and after and must be unchanged.

Run:  python command-center/slop-report/_r3_apply.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")
RUFF = ["uvx", "ruff@0.15.17"]
DOLLAR_NULL = REPO / "$null"

CITED = [
    "platform/architecture/_mkt_measure.py",
    "platform/architecture/_mkt_measure2.py",
    "platform/architecture/_mkt_measure3.py",
    "platform/architecture/_mkt_measure4.py",
    "platform/architecture/_mkt_measure5.py",
    "platform/architecture/_mkt_measure6.py",
    "platform/architecture/_mkt_measure7.py",
    "platform/architecture/_secfirst_probe_denydefault.py",
    "platform/architecture/_secfirst_selfaudit.py",
    "platform/architecture/_uxpf_consumption.py",
    "platform/lib/_d1_mutation_proof.py",
    "platform/lib/_p12_refute_predicate.py",
    "platform/lib/_predicate_twin_differential.py",
    "platform/lib/workflows/_verify_bp3.py",
]

F841_SOURCE = "def f():\n    unused = 1\n    return 2\n"


def run(args: list[str], cwd: Path = REPO) -> tuple[int, str]:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, shell=False)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def tracked_dirty() -> set[str]:
    rc, out = run(["git", "status", "--porcelain", "-uno"])
    return {ln[3:] for ln in out.splitlines() if ln[3:]}


def main() -> int:
    result: dict[str, object] = {}
    result["rev_at_start"] = run(["git", "rev-parse", "HEAD"])[1]

    # ---- bucket (b) preflight -------------------------------------------
    result["cited_exist"] = {p: (REPO / p).is_file() for p in CITED}
    rc_untracked, untracked_out = run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *CITED]
    )
    result["cited_untracked_now"] = sorted(
        p for p in untracked_out.splitlines() if p.strip()
    )

    rc_check, check_out = run([*RUFF, "check", *CITED])
    rc_fmt, fmt_out = run([*RUFF, "format", "--check", *CITED])
    result["ruff_check"] = {"rc": rc_check, "tail": check_out[-300:]}
    result["ruff_format_check"] = {"rc": rc_fmt, "tail": fmt_out[-300:]}

    # Control A: the ignore must be path-scoped, not global.
    with tempfile.TemporaryDirectory(prefix="r3-f841-") as raw:
        probe = Path(raw) / "elsewhere_same_shape.py"
        probe.write_text(F841_SOURCE, encoding="utf-8")
        rc_a, out_a = run([*RUFF, "check", "--select", "F841", str(probe)], cwd=REPO)
    result["control_a_same_shape_elsewhere_still_flagged"] = {
        "rc": rc_a,
        "fires": rc_a != 0 and "F841" in out_a,
    }

    # Control B: the same rule on the ignored file must be silent NOW; the rc 1
    # BEFORE the ruff.toml edit is this session's other state and is recorded in
    # SLOP-BUILD-R3.md rather than re-measured here (the edit is already made).
    rc_b, _ = run([*RUFF, "check", "--select", "F841", CITED[11]])
    result["control_b_ignored_file_silent_now"] = {"rc": rc_b, "silent": rc_b == 0}

    # ---- bucket (d): delete $null ---------------------------------------
    before = tracked_dirty()
    dn: dict[str, object] = {"existed": DOLLAR_NULL.is_file()}
    if dn["existed"]:
        dn["bytes"] = DOLLAR_NULL.stat().st_size
        rc_ign, _ = run(["git", "check-ignore", "-q", "$null"])
        dn["was_gitignored"] = rc_ign == 0
        rc_tr, tr = run(["git", "ls-files", "--", "$null"])
        dn["was_tracked"] = bool(tr.strip())
        if dn["bytes"] == 0 and not dn["was_tracked"]:
            DOLLAR_NULL.unlink()
            dn["deleted"] = True
        else:
            dn["deleted"] = False
            dn["refused_because"] = "not 0 bytes, or tracked -- not an unambiguous (d)"
    dn["absent_after"] = not DOLLAR_NULL.exists()
    after = tracked_dirty()
    dn["tracked_dirty_set_unchanged"] = before == after
    dn["tracked_dirty_delta"] = sorted(before ^ after)
    result["dollar_null"] = dn

    checks = {
        "all_cited_exist": all(result["cited_exist"].values()),
        "ruff_check_green": rc_check == 0,
        "ruff_format_green": rc_fmt == 0,
        "control_a_fires": bool(
            result["control_a_same_shape_elsewhere_still_flagged"]["fires"]
        ),
        "control_b_silent": bool(result["control_b_ignored_file_silent_now"]["silent"]),
        "dollar_null_gone": bool(dn["absent_after"]),
        "no_collateral": bool(dn["tracked_dirty_set_unchanged"]),
    }
    result["checks"] = checks
    result["all_pass"] = all(checks.values())
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")

    for k, v in checks.items():
        print(f"  {'ok ' if v else 'BAD'} {k}: {v}")
    print(f"$null: {dn}")
    if not result["all_pass"]:
        print("FAILED:r3-apply a check did not pass")
        return 1
    print(f"SUCCESS:r3-apply -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
