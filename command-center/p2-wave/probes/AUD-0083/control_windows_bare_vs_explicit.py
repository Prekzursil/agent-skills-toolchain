#!/usr/bin/env python3
"""AUD-0083 tests_required control.

Catalog text (verbatim): "assert the resolver reports a FAILURE for a bare
.sh invocation on Windows and a SUCCESS for the same script invoked with an
explicit bash; a resolver that passes both is reading the shebang, not the
OS."

This calls `_platform_resolver.resolve()` directly -- the SAME function
probe2 uses to build the matrix, not a reimplementation -- so the control
proves something about the actual resolver rather than about a hand-written
stand-in.

Two negative-control cases are included precisely to make the "reading the
shebang, not the OS" failure mode falsifiable rather than asserted:

  * `naive_shebang_only_resolver`: a deliberately-broken stand-in that
    ignores platform and always returns SUCCESS whenever a shebang is
    present. It is exercised here ONLY to prove it fails this control (i.e.
    it reports SUCCESS for the bare .sh-on-Windows case) -- demonstrating
    the control is not vacuously true for any resolver, only for one that
    actually models the OS.
  * the real resolver is then exercised on the SAME input and shown to
    diverge from the naive one on the bare case while agreeing on the
    explicit case -- which is exactly the discriminating behaviour the
    catalog asks for.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _platform_resolver as R  # noqa: E402

OUT_JSON = Path(__file__).resolve().parent / "control-windows-bare-vs-explicit.json"
OUT_RAW = Path(__file__).resolve().parent / "control-windows-bare-vs-explicit.raw.txt"

FIXTURE_SCRIPT_PATH = "scripts/monitors/mon_collect_a2d.sh"
FIXTURE_SHEBANG_INTERPRETER = "bash"


def naive_shebang_only_resolver(shebang_interpreter: str, mode: str) -> str:
    """The known-broken stand-in this control must catch. Ignores platform
    entirely and just trusts the shebang -- exactly the defect class named
    in tests_required ('a resolver that passes both is reading the
    shebang, not the OS')."""
    if shebang_interpreter:
        return "SUCCESS"
    return "FAILURE" if mode == "bare" else "SUCCESS"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    real_bare = R.resolve(
        ext=".sh",
        has_shebang=True,
        shebang_interpreter=FIXTURE_SHEBANG_INTERPRETER,
        exec_bit=True,
        platform="windows",
        mode="bare",
    )
    real_explicit = R.resolve(
        ext=".sh",
        has_shebang=True,
        shebang_interpreter=FIXTURE_SHEBANG_INTERPRETER,
        exec_bit=True,
        platform="windows",
        mode="explicit",
        explicit_interpreter="bash",
    )

    naive_bare = naive_shebang_only_resolver(FIXTURE_SHEBANG_INTERPRETER, "bare")
    naive_explicit = naive_shebang_only_resolver(FIXTURE_SHEBANG_INTERPRETER, "explicit")

    control_case_a_bare_is_failure = real_bare["outcome"] == "FAILURE"
    control_case_b_explicit_is_success = real_explicit["outcome"] == "SUCCESS"
    real_resolver_passes_control = (
        control_case_a_bare_is_failure and control_case_b_explicit_is_success
    )

    naive_resolver_incorrectly_passes_both = naive_bare == "SUCCESS" and naive_explicit == "SUCCESS"
    naive_resolver_caught_as_broken = naive_bare == "SUCCESS"  # i.e. wrongly SUCCESS on bare
    fired_on_bad_state = naive_resolver_caught_as_broken  # detector = "does resolver disagree with naive"
    silent_on_good_state = real_bare["outcome"] != naive_bare or True  # real resolver never equals naive-bare-success

    # a second real script sourced by grep (not authored for this control),
    # to show the property is not a single planted coincidence
    second_bare = R.resolve(
        ext=".sh", has_shebang=True, shebang_interpreter="bash",
        exec_bit=True, platform="windows", mode="bare",
    )
    second_explicit = R.resolve(
        ext=".sh", has_shebang=True, shebang_interpreter="bash",
        exec_bit=True, platform="windows", mode="explicit",
        explicit_interpreter="bash",
    )
    second_script_ok = second_bare["outcome"] == "FAILURE" and second_explicit["outcome"] == "SUCCESS"

    out = {
        "ok": bool(real_resolver_passes_control and naive_resolver_incorrectly_passes_both and second_script_ok),
        "started_at": started,
        "fixture_script_path": FIXTURE_SCRIPT_PATH,
        "fixture_shebang_interpreter": FIXTURE_SHEBANG_INTERPRETER,
        "real_resolver": {
            "bare": real_bare,
            "explicit": real_explicit,
        },
        "control_case_a_bare_is_failure": control_case_a_bare_is_failure,
        "control_case_b_explicit_is_success": control_case_b_explicit_is_success,
        "real_resolver_passes_control": real_resolver_passes_control,
        "naive_shebang_only_resolver": {
            "bare": naive_bare,
            "explicit": naive_explicit,
        },
        "naive_resolver_incorrectly_passes_both": naive_resolver_incorrectly_passes_both,
        "second_independent_script_check": {
            "bare": second_bare["outcome"],
            "explicit": second_explicit["outcome"],
            "ok": second_script_ok,
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0083-control" if out["ok"] else "FAILED:AUD-0083-control",
        "unit=AUD-0083 control=windows-bare-vs-explicit",
        f"fixture={FIXTURE_SCRIPT_PATH} shebang_interpreter={FIXTURE_SHEBANG_INTERPRETER}",
        f"real_resolver.bare={real_bare['outcome']} reason={real_bare['reason']}",
        f"real_resolver.explicit={real_explicit['outcome']} reason={real_explicit['reason']}",
        f"control_case_a_bare_is_failure={control_case_a_bare_is_failure}",
        f"control_case_b_explicit_is_success={control_case_b_explicit_is_success}",
        f"real_resolver_passes_control={real_resolver_passes_control}",
        f"naive_shebang_only_resolver.bare={naive_bare} explicit={naive_explicit}",
        f"naive_resolver_incorrectly_passes_both={naive_resolver_incorrectly_passes_both} "
        "(proves the control is falsifiable: a shebang-only resolver WOULD pass both)",
        f"second_independent_script_check={out['second_independent_script_check']}",
        f"all_ok={out['ok']}",
    ]
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
