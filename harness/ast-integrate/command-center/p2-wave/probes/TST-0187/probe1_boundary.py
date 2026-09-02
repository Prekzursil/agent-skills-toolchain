#!/usr/bin/env python3
"""Probe 1: ceiling-1 / ceiling / ceiling+1 boundary + 10x file route.

Signal (a): measured Windows cmdline chars and argv UTF-8 bytes at dispatch.
Signal (b): child process received payload size (and sha256).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import live_js as J  # noqa: E402
import marshaller as M  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0187-probe1 {msg}")
    return 1


def check_live_ok(r: M.DispatchResult, want_len: int, want_transport: str, tag: str) -> str | None:
    if r.exit_code != 0:
        return f"{tag} exit={r.exit_code}"
    if not r.live_spawned:
        return f"{tag} not live-spawned"
    if r.transport != want_transport:
        return f"{tag} transport={r.transport} want={want_transport}"
    if r.child_payload_len != want_len:
        return f"{tag} child_payload_len={r.child_payload_len} want={want_len}"
    if r.child_payload_sha256 != r.payload_sha256:
        return f"{tag} payload sha mismatch"
    if r.child_argv_utf8_bytes != r.expected_child_argv_utf8_bytes:
        return (
            f"{tag} child argv utf8 {r.child_argv_utf8_bytes} "
            f"!= parent-expected {r.expected_child_argv_utf8_bytes}"
        )
    if r.win_cmdline_chars_at_spawn > M.WINDOWS_CREATEPROCESS_CEILING:
        return f"{tag} spawn still over ceiling ({r.win_cmdline_chars_at_spawn})"
    if not r.file_cleaned:
        return f"{tag} temp file not cleaned"
    return None


def main() -> int:
    rows: list[dict] = []

    p_under = M.payload_for_inline_win_chars(M.GUARD_THRESHOLD_CHARS - 1)
    p_at = M.payload_for_inline_win_chars(M.GUARD_THRESHOLD_CHARS)
    r_under = M.invoke(p_under)
    r_at = M.invoke(p_at)
    err = check_live_ok(r_under, len(p_under), "inline", "guard-1")
    if err:
        return fail(err)
    if r_under.child_source != "argv":
        return fail(f"guard-1 source={r_under.child_source} want=argv")
    if r_under.win_cmdline_chars_inline_hypothetical >= M.GUARD_THRESHOLD_CHARS:
        return fail("guard-1 hypothetical already at threshold")
    err = check_live_ok(r_at, len(p_at), "file", "guard")
    if err:
        return fail(err)
    if r_at.child_source != "file":
        return fail(f"guard source={r_at.child_source} want=file")
    if r_at.win_cmdline_chars_at_spawn >= M.GUARD_THRESHOLD_CHARS:
        return fail("file-route spawn argv still over guard threshold")
    rows.append(
        {
            "id": "guard-threshold-both-states",
            "under_len": len(p_under),
            "at_len": len(p_at),
            "under_transport": r_under.transport,
            "at_transport": r_at.transport,
            "under_win_hypo": r_under.win_cmdline_chars_inline_hypothetical,
            "at_win_hypo": r_at.win_cmdline_chars_inline_hypothetical,
            "at_win_spawn": r_at.win_cmdline_chars_at_spawn,
            "guard_threshold": M.GUARD_THRESHOLD_CHARS,
            "ceiling": M.WINDOWS_CREATEPROCESS_CEILING,
        }
    )

    # Catalog: boundary at ceiling-1, ceiling, ceiling+1 characters.
    # MSDN 32,767 includes the NUL, so win_cmdline_chars==32767 is the last
    # legal slot; 32768+ is OS error 206. The guard file-routes all three.
    boundary = []
    for delta, label in ((-1, "ceiling-1"), (0, "ceiling"), (1, "ceiling+1")):
        target = M.WINDOWS_CREATEPROCESS_CEILING + delta
        payload = M.payload_for_inline_win_chars(target)
        r = M.invoke(payload)
        err = check_live_ok(r, len(payload), "file", label)
        if err:
            return fail(err)
        if r.child_source != "file":
            return fail(f"{label} source={r.child_source} want=file")
        if r.win_cmdline_chars_inline_hypothetical != target:
            return fail(
                f"{label} hypo={r.win_cmdline_chars_inline_hypothetical} want={target}"
            )
        bad = M.unguarded_inline_windows(payload)
        over = target > M.WINDOWS_CREATEPROCESS_CEILING
        if over:
            if bad.windows_error != M.ERROR_FILENAME_EXCED_RANGE or bad.live_spawned:
                return fail(
                    f"{label} unguarded want 206, error={bad.windows_error} "
                    f"live={bad.live_spawned}"
                )
        elif bad.windows_error is not None:
            return fail(
                f"{label} unguarded should still be legal, error={bad.windows_error}"
            )
        boundary.append(
            {
                "label": label,
                "target_win_chars": target,
                "payload_len": len(payload),
                "transport": r.transport,
                "win_spawn": r.win_cmdline_chars_at_spawn,
                "win_hypo": r.win_cmdline_chars_inline_hypothetical,
                "child_payload_len": r.child_payload_len,
                "argv_utf8_at_dispatch": r.argv_utf8_bytes_at_dispatch,
                "unguarded_windows_error": bad.windows_error,
                "unguarded_live_spawned": bad.live_spawned,
            }
        )
    if boundary[0]["unguarded_windows_error"] is not None:
        return fail("ceiling-1 unguarded must remain legal under MSDN NUL-inclusive cap")
    if boundary[1]["target_win_chars"] != M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("ceiling row misaligned")
    if boundary[1]["unguarded_windows_error"] is not None:
        return fail("ceiling unguarded equals the NUL-inclusive max and must stay legal")
    if boundary[2]["unguarded_windows_error"] != M.ERROR_FILENAME_EXCED_RANGE:
        return fail("ceiling+1 unguarded must be OS error 206")
    rows.append({"id": "createprocess-boundary", "cases": boundary})

    ten = "C" * M.TEN_X_CEILING
    r10 = M.invoke(ten)
    err = check_live_ok(r10, M.TEN_X_CEILING, "file", "10x")
    if err:
        return fail(err)
    if r10.child_source != "file":
        return fail(f"10x source={r10.child_source}")
    if r10.win_cmdline_chars_inline_hypothetical <= M.WINDOWS_CREATEPROCESS_CEILING:
        return fail("10x hypothetical did not exceed ceiling")
    bad10 = M.unguarded_inline_windows(ten)
    if bad10.windows_error != M.ERROR_FILENAME_EXCED_RANGE or bad10.live_spawned:
        return fail("10x unguarded did not 206")
    rows.append(
        {
            "id": "ten-x-file-route",
            "payload_len": M.TEN_X_CEILING,
            "child_payload_len": r10.child_payload_len,
            "transport": r10.transport,
            "win_spawn": r10.win_cmdline_chars_at_spawn,
            "win_hypo": r10.win_cmdline_chars_inline_hypothetical,
            "argv_utf8_at_dispatch": r10.argv_utf8_bytes_at_dispatch,
            "child_argv_utf8": r10.child_argv_utf8_bytes,
        }
    )

    if not (M.GUARD_THRESHOLD_CHARS < M.WINDOWS_CREATEPROCESS_CEILING):
        return fail("guard threshold is not below the ceiling")

    static = J.mjs_static()
    if not all(
        [
            static["has_create_plan"],
            static["has_prompt_from_stdin"],
            static["never_push_prompt"],
            static["pushes_stdin_token"],
            static["writes_prompt_file"],
            static["stdin_token_dash"],
        ]
    ):
        return fail(f"live mjs static {static}")

    js_boundary = []
    for delta, label in ((-1, "ceiling-1"), (0, "ceiling"), (1, "ceiling+1")):
        target = M.WINDOWS_CREATEPROCESS_CEILING + delta
        payload = M.payload_for_inline_win_chars(target)
        js = J.run_live_js(payload)
        if js["plan_stdin"] != "file":
            return fail(f"js {label} stdin={js['plan_stdin']}")
        if js["payload_in_argv"]:
            return fail(f"js {label} payload leaked into argv")
        if js["child_source"] != "stdin" or js["child_payload_len"] != len(payload):
            return fail(
                f"js {label} child source={js['child_source']} "
                f"len={js['child_payload_len']}"
            )
        if js["child_payload_sha256"] != js["payload_sha256"]:
            return fail(f"js {label} child sha mismatch")
        if js["win_cmdline_chars_at_spawn"] > M.WINDOWS_CREATEPROCESS_CEILING:
            return fail(
                f"js {label} spawn still over ceiling "
                f"({js['win_cmdline_chars_at_spawn']})"
            )
        if js["win_cmdline_chars_at_spawn"] >= M.GUARD_THRESHOLD_CHARS:
            return fail("js file-route spawn argv still over guard threshold")
        js_boundary.append(
            {
                "label": label,
                "target_win_chars": target,
                "payload_len": len(payload),
                "plan_stdin": js["plan_stdin"],
                "win_spawn": js["win_cmdline_chars_at_spawn"],
                "original_win_chars": js["original_win_chars"],
                "child_payload_len": js["child_payload_len"],
                "argv_utf8_at_dispatch": js["argv_utf8_bytes"],
                "payload_in_argv": js["payload_in_argv"],
            }
        )
    rows.append({"id": "live-js-createprocess-boundary", "cases": js_boundary})

    js10 = J.run_live_js("C" * M.TEN_X_CEILING)
    if (
        js10["plan_stdin"] != "file"
        or js10["child_payload_len"] != M.TEN_X_CEILING
        or js10["payload_in_argv"]
        or js10["win_cmdline_chars_at_spawn"] > M.WINDOWS_CREATEPROCESS_CEILING
        or not js10["original_would_exceed"]
        or not js10["prompt_file_matches"]
    ):
        return fail("js 10x failed " + json.dumps({k: js10[k] for k in (
            "plan_stdin",
            "child_payload_len",
            "payload_in_argv",
            "win_cmdline_chars_at_spawn",
            "original_would_exceed",
            "prompt_file_matches",
        )}))
    rows.append(
        {
            "id": "live-js-ten-x-file-route",
            "payload_len": M.TEN_X_CEILING,
            "child_payload_len": js10["child_payload_len"],
            "plan_stdin": js10["plan_stdin"],
            "win_spawn": js10["win_cmdline_chars_at_spawn"],
            "original_win_chars": js10["original_win_chars"],
            "argv_utf8_at_dispatch": js10["argv_utf8_bytes"],
        }
    )

    out = {
        "probe": "probe1_boundary",
        "pass": True,
        "unit_id": "TST-0187",
        "rows": rows,
        "live_mjs_static": static,
        "signals": {
            "a": "win_cmdline_chars_at_spawn + argv_utf8_bytes_at_dispatch",
            "b": "child_payload_len from live child_echo.py",
        },
    }
    print(json.dumps(out, separators=(",", ":")))
    print(
        "SUCCESS:TST-0187-probe1 "
        f"guard {M.GUARD_THRESHOLD_CHARS}<{M.WINDOWS_CREATEPROCESS_CEILING} "
        f"boundary file-routed 10x child={r10.child_payload_len}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
