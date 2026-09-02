"""Both-states control per adapter guard, against reproductions.

For each of the four named estate classes: a broken fixture must make the
guard fire (FAILED:<id> <reason>); a healthy fixture must stay silent
(SUCCESS:<id>). A use-vs-mention body that discusses background work must
not trip the fire-and-forget flag guard.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from adapter import (
    CONSERVATIVE_INLINE_THRESHOLD,
    ESTATE_OVERFLOW_PAYLOAD,
    MINI_OUTPUT_SCHEMA,
    WIN_CREATEPROCESS_CAP,
    assembled_utf16,
    dispatch,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "WU-0001"

HEALTHY_BODY = {
    "unit_id": UID,
    "state": "SUCCESS",
    "sentinel": f"SUCCESS:{UID}",
}


def _healthy(**overrides: Any) -> dict:
    req: dict[str, Any] = {
        "unit_id": UID,
        "transport": "inline",
        "prompt": "short healthy prompt",
        "background": False,
        "wait": True,
        "mcp_tools_active": True,
        "output_schema": MINI_OUTPUT_SCHEMA,
        "body": dict(HEALTHY_BODY),
    }
    req.update(overrides)
    return req


def _ok(result: dict) -> bool:
    return (
        result.get("ok") is True
        and result.get("marker") == f"SUCCESS:{UID}"
        and str(result.get("marker") or "").startswith("SUCCESS:")
    )


def _fired(result: dict, token: str) -> bool:
    marker = str(result.get("marker") or "")
    reason = str(result.get("reason") or "")
    return (
        result.get("ok") is False
        and marker.startswith(f"FAILED:{UID} ")
        and token in reason
        and token in marker
    )


def _guard_background() -> dict:
    bad = dispatch(_healthy(background=True))
    flag = dispatch(_healthy(extra_argv=["--background"]))
    good = dispatch(_healthy())
    mention = dispatch(
        _healthy(
            body={
                **HEALTHY_BODY,
                "notes": (
                    "This result discusses a started in the background job as "
                    "subject matter; it is not a job receipt."
                ),
            }
        )
    )
    return {
        "fired_on_bad": _fired(bad, "fire-and-forget"),
        "fired_on_flag": _fired(flag, "fire-and-forget"),
        "silent_on_good": _ok(good),
        "silent_on_mention": _ok(mention),
        "bad_marker": bad.get("marker"),
        "good_marker": good.get("marker"),
        "mention_marker": mention.get("marker"),
    }


def _guard_win_arg() -> dict:
    oversized = "x" * ESTATE_OVERFLOW_PAYLOAD
    bad = dispatch(_healthy(prompt=oversized, transport="inline"))
    n_bad = assembled_utf16(_healthy(prompt=oversized, transport="inline"))
    good_file = dispatch(
        _healthy(
            prompt=oversized,
            transport="prompt-file",
            prompt_file="command-center/p2-wave/probes/ARC-0040/prompt.wu-0001.txt",
        )
    )
    n_file = assembled_utf16(
        _healthy(
            prompt=oversized,
            transport="prompt-file",
            prompt_file="command-center/p2-wave/probes/ARC-0040/prompt.wu-0001.txt",
        )
    )
    good_short = dispatch(_healthy())
    mid = "y" * (CONSERVATIVE_INLINE_THRESHOLD + 100)
    conservative = dispatch(_healthy(prompt=mid, transport="inline"))
    return {
        "fired_on_bad": _fired(bad, "win-arg-limit"),
        "fired_on_conservative": _fired(conservative, "win-arg-limit"),
        "silent_on_prompt_file": _ok(good_file),
        "silent_on_short_inline": _ok(good_short),
        "estate_payload_len": ESTATE_OVERFLOW_PAYLOAD,
        "assembled_inline_utf16": n_bad,
        "assembled_prompt_file_utf16": n_file,
        "inline_exceeds_cap": n_bad > WIN_CREATEPROCESS_CAP,
        "prompt_file_under_cap": n_file <= WIN_CREATEPROCESS_CAP,
        "linux_createprocess_206_reproduced": False,
        "bad_marker": bad.get("marker"),
        "good_marker": good_file.get("marker"),
    }


def _guard_progress() -> dict:
    bad_obj = dispatch(_healthy(body={"type": "PROGRESS", "pct": 40}))
    ndjson = "\n".join(
        [
            '{"type":"PROGRESS","pct":10}',
            '{"type":"PROGRESS","pct":90}',
        ]
    )
    bad_nd = dispatch(_healthy(body=ndjson))
    missing = dispatch(_healthy(body=None))
    good = dispatch(_healthy())
    return {
        "fired_on_bad": _fired(bad_obj, "severed-stream")
        and "progress-only" in str(bad_obj.get("reason")),
        "fired_on_ndjson": _fired(bad_nd, "severed-stream"),
        "fired_on_missing": _fired(missing, "severed-stream"),
        "silent_on_good": _ok(good),
        "bad_marker": bad_obj.get("marker"),
        "good_marker": good.get("marker"),
    }


def _guard_schema_mcp() -> dict:
    invalid = {"unit_id": UID, "note": "not a typed result"}
    bad_mcp = dispatch(
        _healthy(mcp_tools_active=True, body=invalid)
    )
    bad_off = dispatch(
        _healthy(mcp_tools_active=False, body=invalid)
    )
    good_mcp = dispatch(_healthy(mcp_tools_active=True))
    good_off = dispatch(_healthy(mcp_tools_active=False))
    return {
        "fired_on_bad_mcp_active": _fired(bad_mcp, "schema-invalid")
        and "mcp-active" in str(bad_mcp.get("reason")),
        "fired_on_bad_mcp_off": _fired(bad_off, "schema-invalid"),
        "silent_on_good_mcp_active": _ok(good_mcp),
        "silent_on_good_mcp_off": _ok(good_off),
        "mcp_does_not_bypass_schema": _fired(bad_mcp, "schema-invalid"),
        "bad_marker": bad_mcp.get("marker"),
        "good_marker": good_mcp.get("marker"),
    }


def both_states() -> dict:
    bg = _guard_background()
    arg = _guard_win_arg()
    prog = _guard_progress()
    sch = _guard_schema_mcp()
    checks = {
        "background.fired_on_bad": bg["fired_on_bad"],
        "background.fired_on_flag": bg["fired_on_flag"],
        "background.silent_on_good": bg["silent_on_good"],
        "background.silent_on_mention": bg["silent_on_mention"],
        "win_arg_limit.fired_on_bad": arg["fired_on_bad"],
        "win_arg_limit.fired_on_conservative": arg["fired_on_conservative"],
        "win_arg_limit.silent_on_prompt_file": arg["silent_on_prompt_file"],
        "win_arg_limit.silent_on_short_inline": arg["silent_on_short_inline"],
        "win_arg_limit.inline_exceeds_cap": arg["inline_exceeds_cap"],
        "win_arg_limit.prompt_file_under_cap": arg["prompt_file_under_cap"],
        "progress.fired_on_bad": prog["fired_on_bad"],
        "progress.fired_on_ndjson": prog["fired_on_ndjson"],
        "progress.fired_on_missing": prog["fired_on_missing"],
        "progress.silent_on_good": prog["silent_on_good"],
        "schema_mcp.fired_on_bad_mcp_active": sch["fired_on_bad_mcp_active"],
        "schema_mcp.fired_on_bad_mcp_off": sch["fired_on_bad_mcp_off"],
        "schema_mcp.silent_on_good_mcp_active": sch["silent_on_good_mcp_active"],
        "schema_mcp.silent_on_good_mcp_off": sch["silent_on_good_mcp_off"],
        "schema_mcp.mcp_does_not_bypass_schema": sch["mcp_does_not_bypass_schema"],
    }
    failed = [k for k, v in checks.items() if not v]
    a6 = REPO / "command-center/phase3/A6/DESIGN.json"
    user_prompts = REPO / "_USER-PROMPTS.md"
    return {
        "pass": not failed,
        "failed": failed,
        "checks": checks,
        "guards": {
            "background": bg,
            "win_arg_limit": arg,
            "progress_stream": prog,
            "schema_mcp": sch,
        },
        "estate": {
            "measured_payload_len": ESTATE_OVERFLOW_PAYLOAD,
            "win_createprocess_cap": WIN_CREATEPROCESS_CAP,
            "conservative_inline_threshold": CONSERVATIVE_INLINE_THRESHOLD,
            "linux_createprocess_206_reproduced": False,
            "a6_design_present": a6.is_file(),
            "user_prompts_47_present": user_prompts.is_file(),
        },
    }
