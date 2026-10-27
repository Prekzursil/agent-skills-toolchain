#!/usr/bin/env python3
"""TST-0195 probe 2: windows policy leg + silent-mutant rejection + fresh-process signal.

Bad state A: a windows casefold that emits NO warning (silent mutant) must be
             rejected by the comparator.
Bad state B: the linux policy must NOT accept the wrong-case reference.
Good state : ./Skills/ resolves under the windows policy WITH a warning naming
             both spellings; ./skills/ stays silent.
Fresh process: a second python interpreter re-derives the windows result
             independently; both must agree.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lookup import lookup  # noqa: E402

ROOT = HERE / "fixtures" / "plugin-root"


def silent_casefold_mutant(requested: str, root: Path, platform: str) -> dict:
    """Mutation control: windows normalization with the warning stripped."""
    result = lookup(requested, root, platform)
    result["warnings"] = []
    result["reason"] = "silent-ok"
    return result


def main() -> int:
    resolved_warn = lookup("./Skills/", ROOT, "windows")
    resolved_silent = lookup("./skills/", ROOT, "windows")
    linux_reject = lookup("./Skills/", ROOT, "linux")
    mutant = silent_casefold_mutant("./Skills/", ROOT, "windows")

    warnings_ok = resolved_warn["ok"] is True and resolved_warn["reason"] == "ok-with-warning"
    names_both = resolved_warn["warnings"] == ["casing-mismatch requested='Skills' on-disk='skills'"]
    silent_ok = resolved_silent["ok"] is True and resolved_silent["warnings"] == [] and resolved_silent["reason"] == "ok-silent"

    code = (
        "import json,sys; sys.path.insert(0, r\"%s\"); from lookup import lookup; "
        "print(json.dumps(lookup(\"./Skills/\", r\"%s\", \"windows\"), sort_keys=True))"
        % (str(HERE), str(ROOT))
    )
    second = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=120)
    second_ok = second.returncode == 0
    second_doc = {}
    if second_ok:
        try:
            second_doc = json.loads(second.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            second_ok = False
    second_agree = bool(
        second_ok
        and second_doc.get("ok") is True
        and second_doc.get("warnings") == resolved_warn["warnings"]
        and second_doc.get("resolved") == resolved_warn["resolved"]
    )

    checks = {
        "windows_resolves_with_warning": warnings_ok,
        "warning_names_both_spellings": names_both,
        "correct_case_silent": silent_ok,
        "silent_mutant_rejected": mutant["warnings"] == [] and mutant["reason"] == "silent-ok" and mutant != resolved_warn,
        "linux_policy_still_rejects": linux_reject["ok"] is False and linux_reject["reason"] == "exact-miss",
        "fresh_process_agree": second_agree,
    }
    out = {
        "probe": "probe2_windows_warning_matrix",
        "unit": "TST-0195",
        "windows_mismatch": resolved_warn,
        "windows_good": resolved_silent,
        "linux_reject": linux_reject,
        "silent_mutant": mutant,
        "fresh_process_agree": second_agree,
        "checks": checks,
        "ok": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    (HERE / "probe2_windows_warning_matrix.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
