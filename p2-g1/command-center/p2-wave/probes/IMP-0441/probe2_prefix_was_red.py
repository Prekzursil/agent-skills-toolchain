#!/usr/bin/env python3
"""IMP-0441 probe2 (control): the pre-fix Windows run really was red.

Reproduces the pre-fix behaviour (hash RAW CRLF bytes against recorded LF
digests -> both gates' hash checks would fail) and proves the after-state
is not silence: LF-normalised hashes DO match the recorded digests. A
mutated .gitattributes missing one required rule must turn the --check
gate red (exit 1) - the mutation detector for the EOL policy itself."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EOL_PY = REPO / "tools" / "command-center" / "eol_policy.py"

spec = importlib.util.spec_from_file_location("imp0441_eol_policy", EOL_PY)
M = importlib.util.module_from_spec(spec)
sys.modules["imp0441_eol_policy"] = M
spec.loader.exec_module(M)


def fail(msg: str) -> int:
    print("FAILED:IMP-0441-probe2 " + str(msg))
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0441-probe2-"))
    lf_root = tmp / "lf" / "command-center"
    crlf_root = tmp / "crlf" / "command-center"
    M.build_min_command_center(lf_root)
    M.materialize_eol(lf_root, crlf_root, "crlf")

    # (a) pre-fix red: raw CRLF sha256 disagrees with recorded LF digests
    # for BOTH hashed artefacts (REACH-6 register + render STATUS.md).
    pre = M.prefix_raw_hash_red(crlf_root)
    if not pre["both_prefix_red"]:
        return fail(f"pre-fix state not red: {json.dumps(pre)[:300]}")
    # (b) after-state not silence: LF-normalised hashes DO match.
    if not pre["both_postfix_match"]:
        return fail(f"post-fix LF hashes do not match records: {json.dumps(pre)[:300]}")
    if pre["register_crlf_count"] <= 0:
        return fail("crlf fixture has no CRLF bytes - control vacuous")

    # (c) mutation: drop one required rule from a copy of .gitattributes
    #     -> the shipped --check gate must exit non-zero (mutation red).
    src = (REPO / ".gitattributes").read_text(encoding="utf-8")
    lines = [ln for ln in src.splitlines() if not ln.strip().startswith("*.ps1")]
    mutated = tmp / "gitattributes.mutated"
    mutated.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    mut = subprocess.run(
        [sys.executable, "-B", str(EOL_PY), "--check", "--gitattributes", str(mutated)],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if mut.returncode == 0:
        return fail("mutated .gitattributes (missing *.ps1) still passes --check - mutation undetected")
    # (d) the pristine file stays green on the same invocation path.
    ok = subprocess.run(
        [sys.executable, "-B", str(EOL_PY), "--check"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if ok.returncode != 0:
        return fail(f"pristine --check regressed to red: {ok.stdout} {ok.stderr}")

    print(json.dumps({
        "probe": "probe2-prefix-was-red",
        "unit_id": "IMP-0441",
        "register_crlf_bytes": pre["register_crlf_count"],
        "register_raw_sha256": pre["register_raw_sha256"],
        "register_recorded": pre["register_recorded"],
        "register_raw_matches": pre["register_raw_sha256"] == pre["register_recorded"],
        "register_lf_matches": pre["register_lf_sha256"] == pre["register_recorded"],
        "status_raw_matches": pre["status_raw_sha256"] == pre["status_recorded"],
        "status_lf_matches": pre["status_lf_sha256"] == pre["status_recorded"],
        "both_prefix_red": pre["both_prefix_red"],
        "both_postfix_match": pre["both_postfix_match"],
        "mutation_dropped_rule": "*.ps1",
        "mutation_exit": mut.returncode,
        "pristine_exit": ok.returncode,
    }, indent=2))
    print("SUCCESS:IMP-0441-probe2 prefix raw-hash control red, LF control green, mutation red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
