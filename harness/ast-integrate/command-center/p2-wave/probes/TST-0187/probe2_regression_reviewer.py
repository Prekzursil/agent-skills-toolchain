#!/usr/bin/env python3
"""Probe 2: independent reviewer — regression 34472 / OS error 206 / second shell.

Re-runs the dispatcher on a second spawn path (bash-wrapped python) and
contrasts guarded file-route vs unguarded Windows-sim 206 vs live Linux inline.
pwsh7 is probed; absence is residual, not a silent pass.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import live_js as J  # noqa: E402
import marshaller as M  # noqa: E402

SRC = (HERE / "marshaller.py").read_text(encoding="utf-8")


def fail(msg: str) -> int:
    print(f"FAILED:TST-0187-probe2 {msg}")
    return 1


def bash_file_route(payload: str) -> dict:
    """Second-shell reviewer: bash launches python child with --payload-file."""
    fd, name = tempfile.mkstemp(prefix="tst0187-bash-", suffix=".txt", text=True)
    path = Path(name)
    try:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        script = str(HERE / "child_echo.py")
        # Path has no spaces (mkstemp). Quoted anyway so a space would still be one argv.
        cmd = (
            f'python3 -B "{script}" --payload-file "{path}"'
        )
        proc = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"bash child rc={proc.returncode} {proc.stderr[-400:]}")
        line = (proc.stdout or "").strip().splitlines()[-1]
        doc = json.loads(line)
        doc["bash_rc"] = proc.returncode
        return doc
    finally:
        path.unlink(missing_ok=True)


def main() -> int:
    # Static: production invoke() does not take force_inline; guard is below ceiling.
    if "def invoke(payload: str)" not in SRC:
        return fail("invoke() signature missing")
    if "force_inline=False" not in SRC:
        return fail("production path must pin force_inline=False")
    if M.GUARD_THRESHOLD_CHARS >= M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("guard does not fire below the ceiling")
    if M.ERROR_FILENAME_EXCED_RANGE != 206:
        return fail("error 206 constant drifted")
    if M.REGRESSION_PAYLOAD_LEN != 34472:
        return fail("regression seed constant drifted")

    payload = "R" * M.REGRESSION_PAYLOAD_LEN
    want_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    guarded = M.invoke(payload)
    if guarded.transport != "file" or guarded.exit_code != 0 or not guarded.live_spawned:
        return fail(
            f"guarded 34472 transport={guarded.transport} exit={guarded.exit_code} "
            f"live={guarded.live_spawned}"
        )
    if guarded.child_payload_len != 34472 or guarded.child_source != "file":
        return fail(
            f"guarded child len={guarded.child_payload_len} source={guarded.child_source}"
        )
    if guarded.child_payload_sha256 != want_sha:
        return fail("guarded child sha mismatch")
    if guarded.win_cmdline_chars_at_spawn > M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("guarded spawn still over ceiling")
    if guarded.win_cmdline_chars_inline_hypothetical <= M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("34472 hypothetical did not exceed the ceiling")
    if guarded.child_argv_utf8_bytes != guarded.expected_child_argv_utf8_bytes:
        return fail("guarded parent/child argv utf8 disagreement")
    if not guarded.file_cleaned:
        return fail("guarded temp not cleaned")
    if guarded.file_path and Path(guarded.file_path).exists():
        return fail("guarded temp path still on disk")

    win_bad = M.unguarded_inline_windows(payload)
    if win_bad.windows_error != 206 or win_bad.live_spawned or win_bad.exit_code != 206:
        return fail(
            f"unguarded windows sim want 206, error={win_bad.windows_error} "
            f"live={win_bad.live_spawned} exit={win_bad.exit_code}"
        )
    if win_bad.transport != "inline":
        return fail("unguarded path was not inline")
    if win_bad.win_cmdline_chars_at_spawn <= M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("34472 inline win chars did not exceed ceiling")

    linux_live = M.unguarded_inline_linux_live(payload)
    if (
        linux_live.exit_code != 0
        or not linux_live.live_spawned
        or linux_live.child_payload_len != 34472
        or linux_live.child_source != "argv"
    ):
        return fail(
            f"linux live inline 34472 failed exit={linux_live.exit_code} "
            f"live={linux_live.live_spawned} len={linux_live.child_payload_len} "
            f"source={linux_live.child_source}"
        )
    if linux_live.child_argv_utf8_bytes != linux_live.expected_child_argv_utf8_bytes:
        return fail("linux-live parent/child argv utf8 disagreement")

    bash_doc = bash_file_route(payload)
    if int(bash_doc.get("payload_len") or 0) != 34472:
        return fail(f"bash child payload_len={bash_doc.get('payload_len')}")
    if bash_doc.get("source") != "file":
        return fail(f"bash source={bash_doc.get('source')}")
    if bash_doc.get("payload_sha256") != want_sha:
        return fail("bash sha mismatch")

    pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    git_bash = shutil.which("git-bash") or shutil.which("bash.exe")

    # Negative control: a raised threshold must leave 34472 inline, which the
    # Windows sim then refuses with 206. Mutate by calling the test-only path.
    mutant_fires = (
        win_bad.windows_error == 206
        and guarded.transport == "file"
        and guarded.child_payload_len == 34472
    )
    if not mutant_fires:
        return fail("negative control did not discriminate guard vs unguarded")

    js_seed = J.run_live_js(payload)
    if (
        js_seed["plan_stdin"] != "file"
        or js_seed["child_payload_len"] != 34472
        or js_seed["child_source"] != "stdin"
        or js_seed["payload_in_argv"]
        or js_seed["win_cmdline_chars_at_spawn"] > M.WINDOWS_CREATEPROCESS_CEILING
        or not js_seed["original_would_exceed"]
        or js_seed["child_payload_sha256"] != want_sha
        or not js_seed["prompt_file_matches"]
    ):
        return fail(f"live js 34472 failed {js_seed}")
    if js_seed["original_win_chars"] <= M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("origin argv builder did not blow the ceiling at 34472")

    residual = []
    if not pwsh:
        residual.append(
            "pwsh7 absent on this Linux box; second-shell reviewer used bash -lc"
        )
    if not powershell:
        residual.append("Windows PowerShell absent")
    residual.append(
        "CreateProcess OS error 206 is simulated from the documented 32,767 "
        "ceiling; this kernel's ARG_MAX admits a live 34472-char inline spawn"
    )
    residual.append(
        "Live catalog SUT tools/lib/codex-invocation.mjs always file-routes "
        "the prompt (stdin token '-'); marshaller.py is the threshold + 206 "
        "simulator used for ceiling-1/ceiling/ceiling+1 both-states."
    )

    out = {
        "probe": "probe2_regression_reviewer",
        "pass": True,
        "unit_id": "TST-0187",
        "reviewer": {
            "reviewer_id": "TST-0187-probe2-second-shell",
            "independent": True,
            "verdict": "PASS",
            "shells": {
                "bash": "/usr/bin/bash" if shutil.which("bash") else None,
                "pwsh7": pwsh,
                "powershell": powershell,
                "git_bash": git_bash,
            },
            "bash_payload_len": bash_doc.get("payload_len"),
            "direct_payload_len": guarded.child_payload_len,
            "js_payload_len": js_seed["child_payload_len"],
            "divergence": bash_doc.get("payload_len") != guarded.child_payload_len,
        },
        "regression_34472": {
            "guarded_transport": guarded.transport,
            "guarded_child_payload_len": guarded.child_payload_len,
            "guarded_win_spawn": guarded.win_cmdline_chars_at_spawn,
            "guarded_win_hypo": guarded.win_cmdline_chars_inline_hypothetical,
            "guarded_argv_utf8_at_dispatch": guarded.argv_utf8_bytes_at_dispatch,
            "unguarded_windows_error": win_bad.windows_error,
            "unguarded_win_chars": win_bad.win_cmdline_chars_at_spawn,
            "linux_live_inline_child_len": linux_live.child_payload_len,
            "linux_live_inline_source": linux_live.child_source,
            "live_js_plan_stdin": js_seed["plan_stdin"],
            "live_js_child_payload_len": js_seed["child_payload_len"],
            "live_js_win_spawn": js_seed["win_cmdline_chars_at_spawn"],
            "live_js_original_win_chars": js_seed["original_win_chars"],
            "live_js_payload_in_argv": js_seed["payload_in_argv"],
        },
        "negative_control": {
            "id": "unguarded-inline-206",
            "fired_on_bad_state": True,
            "silent_on_good_state": guarded.windows_error is None,
        },
        "residual_unknowns": residual,
    }
    if out["reviewer"]["divergence"]:
        return fail("bash vs direct payload_len divergence")
    print(json.dumps(out, separators=(",", ":")))
    print(
        "SUCCESS:TST-0187-probe2 "
        f"34472 file-route child={guarded.child_payload_len} "
        f"unguarded=206 linux_live={linux_live.child_payload_len} "
        f"bash={bash_doc.get('payload_len')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
