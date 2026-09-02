"""Live measurement for RES-0002: locate the 200→FAILED compare and session verdicts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from constants import FIXTURES, SESSION_TOOLS
from estate import census
from payloads import fetch_loopback, read_file_event, session_events
from runner import run_session, verdicts_by_tool
from scan import fixture_controls, live_scan, marker_line, rel_or_abs


def both_states_label(verdicts: dict[str, str]) -> str:
    v200 = verdicts.get("WebFetch")
    v404 = verdicts.get("WebFetch_404")
    if v200 == "FAILED" and v404 == "FAILED":
        return "FAILED-IN-BOTH"
    if v200 == "FAILED" and v404 in {"OK", "NOT-FIRED"}:
        return "INVERTED-EQ-200"
    if v200 in {"OK", "NOT-FIRED"} and v404 == "FAILED":
        return "VALID"
    if v200 in {"OK", "NOT-FIRED"} and v404 in {"OK", "NOT-FIRED"}:
        return "SILENT-OK-BOTH"
    return "OTHER"


def inversion_scope(verdicts: dict[str, str]) -> str:
    search = verdicts.get("WebSearch")
    read = verdicts.get("Read")
    fetch = verdicts.get("WebFetch")
    if fetch == "FAILED" and search != "FAILED" and read != "FAILED":
        return "WebFetch-specific"
    if fetch == "FAILED" and (search == "FAILED" or read == "FAILED"):
        return "general"
    if fetch != "FAILED":
        return "no-webfetch-failure"
    return "other"


def _compact_session(raw: dict[str, Any]) -> dict[str, Any]:
    verdicts = verdicts_by_tool(raw.get("results") or [])
    compact_rows = []
    for row in raw.get("results") or []:
        compact_rows.append(
            {
                "tool_name": row.get("tool_name"),
                "http_status": row.get("http_status"),
                "returncode": row.get("returncode"),
                "stdout_token": row.get("stdout_token"),
                "verdict": row.get("verdict"),
            }
        )
    return {
        "hook": raw.get("hook"),
        "ran": raw.get("ran"),
        "verdicts": verdicts,
        "both_states": both_states_label(verdicts),
        "scope": inversion_scope(verdicts),
        "results": compact_rows,
    }


def _live_hook_script(est: dict[str, Any]) -> Path | None:
    for item in est.get("hook_scripts") or []:
        path = Path(item.get("path") or "")
        if not path.is_file():
            continue
        name = (item.get("name") or "").lower()
        if "sentinel" in name or "post" in name:
            return path
    scripts = [Path(i["path"]) for i in (est.get("hook_scripts") or []) if i.get("path")]
    if len(scripts) == 1 and scripts[0].is_file():
        return scripts[0]
    return None


def scanner_both_states(controls: dict[str, Any]) -> dict[str, Any]:
    inv_status = controls["inverted_status_as_exit"]
    inv_eq = controls["inverted_eq_200"]
    correct = controls["correct_http"]
    noop = controls["noop"]
    fires_on_broken = (
        inv_status["regex_hit"]
        and inv_status["ast_hit"]
        and inv_eq["regex_hit"]
        and inv_eq["ast_hit"]
    )
    silent_on_good = (not correct["inversion_hit"]) and (not noop["inversion_hit"])
    return {
        "fires_on_broken": fires_on_broken,
        "silent_on_good": silent_on_good,
        "passed": fires_on_broken and silent_on_good,
        "broken_regex_and_ast": {
            "inverted_status_as_exit": {
                "regex": inv_status["regex_hit"],
                "ast": inv_status["ast_hit"],
            },
            "inverted_eq_200": {"regex": inv_eq["regex_hit"], "ast": inv_eq["ast_hit"]},
        },
        "good_silent": {
            "correct_http": not correct["inversion_hit"],
            "noop": not noop["inversion_hit"],
        },
    }


def measure() -> dict[str, Any]:
    est = census()
    http_pair = fetch_loopback()
    events = session_events(http_pair)
    read_event, read_meta = read_file_event()
    controls = fixture_controls()
    live = live_scan()
    live_script = _live_hook_script(est)

    sessions = {
        "live": _compact_session(run_session(live_script, events)),
        "inverted_status_as_exit": _compact_session(
            run_session(FIXTURES / "inverted_status_as_exit.py", events)
        ),
        "inverted_eq_200": _compact_session(
            run_session(FIXTURES / "inverted_eq_200.py", events)
        ),
        "correct_http": _compact_session(
            run_session(FIXTURES / "correct_http.py", events)
        ),
        "noop": _compact_session(run_session(FIXTURES / "noop.py", events)),
    }

    fixture_eq_line = marker_line(FIXTURES / "inverted_eq_200.py")
    fixture_exit_line = marker_line(FIXTURES / "inverted_status_as_exit.py")
    live_hits = live.get("inversion_hits") or []
    live_line = None
    if live_hits:
        first = live_hits[0]
        live_line = f"{first.get('path')}:{first.get('line')}"

    comparison = {
        "live_exists": bool(live_hits),
        "live_verdict": "FOUND" if live_hits else "REFUTED",
        "live_file_line": live_line,
        "live_hits": live_hits[:20],
        "explicit": (
            "REFUTED"
            if not live_hits
            else f"FOUND:{live_line}"
        ),
        "fixture_eq_200": {
            "path": rel_or_abs(FIXTURES / "inverted_eq_200.py"),
            "line": fixture_eq_line,
            "file_line": (
                f"{rel_or_abs(FIXTURES / 'inverted_eq_200.py')}:{fixture_eq_line}"
                if fixture_eq_line
                else None
            ),
            "role": "positive-control-not-live-hook",
        },
        "fixture_status_as_exit": {
            "path": rel_or_abs(FIXTURES / "inverted_status_as_exit.py"),
            "line": fixture_exit_line,
            "file_line": (
                f"{rel_or_abs(FIXTURES / 'inverted_status_as_exit.py')}:{fixture_exit_line}"
                if fixture_exit_line
                else None
            ),
            "role": "positive-control-not-live-hook",
        },
    }

    live_verdicts = sessions["live"]["verdicts"]
    reconstructed = sessions["inverted_status_as_exit"]["verdicts"]
    per_tool = {
        "WebSearch": {
            "live": live_verdicts.get("WebSearch"),
            "reconstructed_status_as_exit": reconstructed.get("WebSearch"),
            "reconstructed_eq_200": sessions["inverted_eq_200"]["verdicts"].get(
                "WebSearch"
            ),
            "correct_control": sessions["correct_http"]["verdicts"].get("WebSearch"),
        },
        "Read": {
            "live": live_verdicts.get("Read"),
            "reconstructed_status_as_exit": reconstructed.get("Read"),
            "reconstructed_eq_200": sessions["inverted_eq_200"]["verdicts"].get("Read"),
            "correct_control": sessions["correct_http"]["verdicts"].get("Read"),
        },
        "WebFetch": {
            "live": live_verdicts.get("WebFetch"),
            "reconstructed_status_as_exit": reconstructed.get("WebFetch"),
            "reconstructed_eq_200": sessions["inverted_eq_200"]["verdicts"].get(
                "WebFetch"
            ),
            "correct_control": sessions["correct_http"]["verdicts"].get("WebFetch"),
        },
        "WebFetch_404": {
            "live": live_verdicts.get("WebFetch_404"),
            "reconstructed_status_as_exit": reconstructed.get("WebFetch_404"),
            "reconstructed_eq_200": sessions["inverted_eq_200"]["verdicts"].get(
                "WebFetch_404"
            ),
            "correct_control": sessions["correct_http"]["verdicts"].get("WebFetch_404"),
        },
    }

    return {
        "session_tools": list(SESSION_TOOLS),
        "estate": {
            "platform": est["platform"],
            "claude_binary": est["claude_binary"],
            "eco_present": est["eco_present"],
            "register_md_present": est["register_md_present"],
            "hook_script_count": est["hook_script_count"],
            "live_post_tool_use_configured": est["live_post_tool_use_configured"],
            "live_tool_sentinel_present": est["live_tool_sentinel_present"],
            "hook_dirs_existing": [
                d["path"] for d in est["hook_dirs"] if d.get("exists")
            ],
            "eco_hits": est["eco_hits"],
            "settings": est["settings"],
            "post_tool_use_from_settings": est["post_tool_use_from_settings"],
        },
        "http_pair": {
            "ok_status": http_pair["ok_status"],
            "missing_status": http_pair["missing_status"],
            "ok_body_sha256": http_pair["ok_body_sha256"],
            "missing_body_sha256": http_pair["missing_body_sha256"],
            "ok_body_matches_fixture": http_pair["ok_body_matches_fixture"],
            "missing_body_matches_fixture": http_pair["missing_body_matches_fixture"],
        },
        "read_meta": read_meta,
        "read_event_tool": read_event.get("tool_name"),
        "live_scan": {
            "files_scanned": live["files_scanned"],
            "hit_count": live["hit_count"],
        },
        "scanner_controls": controls,
        "scanner_both_states": scanner_both_states(controls),
        "sessions": sessions,
        "verdicts_per_tool_type": per_tool,
        "comparison": comparison,
        "one_session": True,
    }


def expected_reconstructed() -> dict[str, Any]:
    return {
        "inverted_status_as_exit": {
            "WebSearch": "OK",
            "Read": "OK",
            "WebFetch": "FAILED",
            "WebFetch_404": "FAILED",
            "both_states": "FAILED-IN-BOTH",
            "scope": "WebFetch-specific",
        },
        "inverted_eq_200": {
            "WebSearch": "OK",
            "Read": "OK",
            "WebFetch": "FAILED",
            "WebFetch_404": "OK",
            "both_states": "INVERTED-EQ-200",
            "scope": "WebFetch-specific",
        },
        "correct_http": {
            "WebSearch": "OK",
            "Read": "OK",
            "WebFetch": "OK",
            "WebFetch_404": "FAILED",
            "both_states": "VALID",
            "scope": "no-webfetch-failure",
        },
    }
