#!/usr/bin/env python3
"""Probe 2: a bare .sh invocation is reproduced as a Windows failure.

Control: Linux execve of the same marker.sh succeeds via shebang. Explicit
`bash marker.sh` succeeds. Windows cmd.exe PATHEXT model returns the exact
'not recognized' error and must NOT succeed. A resolver that passed both the
bare Windows case and the shebang/explicit cases is reading #!, not the OS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0068.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0068-probe2 {msg}")
    return 1


def main() -> int:
    live = E.run_all()
    control = live["windows_linux_control"]
    tests = live["tests"]
    win = control["windows_bare_sh"]
    linux = control["linux_shebang_exec"]
    explicit = control["explicit_bash"]

    if win.get("ok"):
        return fail("Windows bare .sh succeeded (shebang cheat)")
    if int(win.get("returncode") or 0) != E.CMD_NOT_RECOGNIZED_EXIT:
        return fail(
            f"Windows returncode={win.get('returncode')} want {E.CMD_NOT_RECOGNIZED_EXIT}"
        )
    stderr = win.get("stderr") or ""
    if "not recognized" not in stderr.lower():
        return fail(f"Windows stderr missing 'not recognized': {stderr!r}")
    if win.get("read_shebang"):
        return fail("Windows model claims it read the shebang")

    if not linux.get("ok"):
        return fail(
            f"Linux shebang exec failed rc={linux.get('returncode')} "
            f"stderr={linux.get('stderr')!r} stdout={linux.get('stdout')!r}"
        )
    if not linux.get("read_shebang"):
        return fail("Linux control did not go through execve shebang")

    if not explicit.get("ok"):
        return fail(
            f"explicit bash failed rc={explicit.get('returncode')} "
            f"stderr={explicit.get('stderr')!r}"
        )
    if explicit.get("read_shebang"):
        return fail("explicit interpreter path claimed shebang-read")

    if control.get("shebang_cheat_detected"):
        return fail("shebang cheat: Windows ok and Linux shebang ok")
    if not control.get("discriminates"):
        return fail("control does not discriminate Windows-fail vs Linux-shebang-success")

    if not tests["test_bare_sh_invocation_is_reproduced_as_a_failure_on_windows"]:
        return fail("live Windows-failure test is false")

    for row in live["live_invocations"]:
        if row.get("route") != "windows-bare":
            continue
        if row.get("ok"):
            return fail(f"estate {row.get('id')} Windows-bare unexpectedly ok")
        if "not recognized" not in (row.get("stderr") or "").lower():
            return fail(f"estate {row.get('id')} missing not-recognized stderr")

    print(
        f"windows rc={win.get('returncode')} ok={win.get('ok')} "
        f"pathext_hit={win.get('pathext_hit')} read_shebang={win.get('read_shebang')}"
    )
    print(f"windows stderr={stderr.strip()!r}")
    print(
        f"linux_shebang rc={linux.get('returncode')} ok={linux.get('ok')} "
        f"stdout={(linux.get('stdout') or '').strip()!r}"
    )
    print(
        f"explicit_bash rc={explicit.get('returncode')} ok={explicit.get('ok')} "
        f"stdout={(explicit.get('stdout') or '').strip()!r}"
    )

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:TST-0068" not in text:
            return fail("artifact sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        rec_tests = {
            t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)
        }
        row = rec_tests.get(
            "test_bare_sh_invocation_is_reproduced_as_a_failure_on_windows"
        )
        if not row or row.get("result") != "PASS":
            return fail("artifact missing PASS for Windows bare-.sh test")
        rec_ctrl = doc.get("windows_linux_control") or {}
        rec_win = rec_ctrl.get("windows_bare_sh") or {}
        if rec_win.get("ok") is True:
            return fail("artifact records Windows bare .sh as ok")
        if "not recognized" not in str(rec_win.get("stderr") or "").lower():
            return fail("artifact Windows stderr missing 'not recognized'")

    print("SUCCESS:TST-0068-probe2 bare .sh reproduced as Windows not-recognized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
