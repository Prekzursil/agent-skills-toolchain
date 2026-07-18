#!/usr/bin/env python3
"""Regression suite for mine.py's HOOK TELEMETRY detector.

WHY THIS EXISTS
  mine.py reported `hooks: {}` across 10.62 GB / 1.56M lines and its own corpus marked the
  section DETECTOR_STATUS: BROKEN. The cause was NOT that hooks write no telemetry -- they
  write the richest telemetry in the corpus. The cause is a NESTING error:

      mine.py:309   hook = rec.get("hookName") or rec.get("hook_event_name")

  reads `hookName` at the TOP LEVEL of the record. The real field lives one level down, in
  a record of `type: "attachment"` under `rec["attachment"]["hookName"]`. The key name was
  already correct; only the path was wrong. scan() never inspects `type == "attachment"`
  at all (it branches on "assistant" / "user" only), so every hook fire was invisible.

  Measured on the live corpus 2026-07-18: 32,211 hook records in a 1,201-file sample.

EVERY FIXTURE BELOW IS A REAL SHAPE captured from ~/.claude/projects, not invented. The
seven `attachment.type` values are the complete observed set.

THE KNOWN-POSITIVE CONTROL IS MECHANICAL HERE, NOT REMEMBERED
  `test_control_detector_finds_known_present_hooks_in_live_corpus` runs the detector against
  the real corpus and fails if it finds nothing. That is INPUT-known-harness-defects.md's D2
  rule ("before reporting an absence, prove the detector can find a KNOWN-PRESENT item")
  turned into a test instead of a rule an agent has to remember to read.

RUN
  python -m pytest tools/harness-corpus/test_hook_telemetry.py -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent


def _load_mine():
    """Import the sibling mine.py by path (it is a script, not an installed module)."""
    spec = importlib.util.spec_from_file_location("mine_under_test", THIS / "mine.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mine_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


mine = _load_mine()


# --------------------------------------------------------------------------------------
# REAL record shapes, captured verbatim from ~/.claude/projects on 2026-07-18.
# Trimmed to the telemetry fields; nothing here is invented.
# --------------------------------------------------------------------------------------
def _attach(payload: dict) -> dict:
    """Wrap an attachment payload in its real transcript envelope."""
    return {
        "type": "attachment",
        "timestamp": "2026-07-18T12:00:00.000Z",
        "isSidechain": False,
        "userType": "external",
        "attachment": payload,
    }


HOOK_SUCCESS = _attach({
    "type": "hook_success",
    "hookName": "PreToolUse:Bash",
    "hookEvent": "PreToolUse",
    "toolUseID": "79d37b45-19b2-4372-9fe3-03ed7e1891c7",
    "content": "",
    "stdout": '{"hookSpecificOutput":{"hookEventName":"PreToolUse",'
              '"additionalContext":"goal re-injection"}}\r\n',
    "stderr": "",
    "exitCode": 0,
    "command": "Shared harness: PreToolUse",
    "durationMs": 469,
})

ASYNC_HOOK_RESPONSE = _attach({
    "type": "async_hook_response",
    "hookName": "Stop",
    "hookEvent": "Stop",
    "stdout": '{"hookSpecificOutput":{"hookEventName":"Stop"}}',
    "exitCode": 0,
})

HOOK_ADDITIONAL_CONTEXT = _attach({
    "type": "hook_additional_context",
    "hookName": "SessionStart",
    "hookEvent": "SessionStart",
})

HOOK_CANCELLED = _attach({
    "type": "hook_cancelled",
    "hookName": "PreToolUse:mcp__hublive__hub_backend_add",
    "hookEvent": "PreToolUse",
    "command": "Shared harness: PreToolUse",
    "durationMs": 5559,
})

# exitCode 127 = "command not found". This one never executed at all: the
# ${CLAUDE_PLUGIN_ROOT} placeholder was never expanded. A silently dead guard.
HOOK_NON_BLOCKING_ERROR = _attach({
    "type": "hook_non_blocking_error",
    "hookName": "PostToolUse:Write",
    "hookEvent": "PostToolUse",
    "command": "${CLAUDE_PLUGIN_ROOT}/scripts/validate-template.sh",
    "stderr": "Failed with non-blocking status code: No stderr output",
    "exitCode": 127,
    "durationMs": 31,
})

# The reason a block happened. Real shape: a dict whose "blockingError" key holds the
# check's own message. Without it a block is a bare count you cannot triage.
HOOK_BLOCKING_ERROR = _attach({
    "type": "hook_blocking_error",
    "hookName": "PostToolUse:Write",
    "hookEvent": "PostToolUse",
    "blockingError": {
        "blockingError": "[{'line': 30, 'message': \"Detected a dynamic value being used "
                         "with urllib.\", 'severity': 'WARNING'}]"
    },
})

HOOK_SYSTEM_MESSAGE = _attach({
    "type": "hook_system_message",
    "hookName": "Stop",
    "hookEvent": "Stop",
})

ALL_HOOK_RECORDS = [
    HOOK_SUCCESS,
    ASYNC_HOOK_RESPONSE,
    HOOK_ADDITIONAL_CONTEXT,
    HOOK_CANCELLED,
    HOOK_NON_BLOCKING_ERROR,
    HOOK_BLOCKING_ERROR,
    HOOK_SYSTEM_MESSAGE,
]

# Attachment records that are NOT hooks. These share the `type: "attachment"` envelope and
# are far more numerous than some hook types, so a detector that keys on the envelope alone
# over-counts. Guarding this is the use-vs-mention lesson (D1) applied to a new detector:
# match on the semantic role (carries hookName/hookEvent), never on the container.
NON_HOOK_ATTACHMENTS = [
    _attach({"type": "skill_listing", "content": "…"}),
    _attach({"type": "deferred_tools_delta", "tools": ["Read"]}),
    _attach({"type": "task_reminder", "content": "…"}),
    _attach({"type": "nested_memory", "path": "CLAUDE.md"}),
    _attach({"type": "file", "filename": "x.py"}),
]


def _write_jsonl(path: Path, records: list[dict]) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return str(path)


def _scan(path: str) -> "mine.Stats":
    st = mine.Stats()
    mine.scan(path, st, "session", 0)
    return st


# --------------------------------------------------------------------------------------
# THE PRIMARY FAILING TEST.
# Asserts on `Stats.hooks`, which ALREADY EXISTS on the unpatched miner and is always
# empty -- so a failure here proves detector BLINDNESS, not a missing attribute.
# --------------------------------------------------------------------------------------
def test_hook_fires_are_detected(tmp_path):
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    assert sum(st.hooks.values()) == 7, (
        f"expected 7 hook fires, detector saw {sum(st.hooks.values())} "
        f"-- hooks={dict(st.hooks)}"
    )
    assert st.hooks["PreToolUse:Bash"] == 1
    assert st.hooks["Stop"] == 2  # async_hook_response + hook_system_message
    assert st.hooks["PostToolUse:Write"] == 2  # non-blocking error + blocking error


def test_hook_event_is_recorded_separately_from_hook_name(tmp_path):
    """`hookName` is per-tool ("PreToolUse:Bash"); `hookEvent` is the bare lifecycle event.
    Rolling up by event answers "how much does PreToolUse cost me", which the per-tool
    name cannot."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    assert st.hook_events["PreToolUse"] == 2
    assert st.hook_events["PostToolUse"] == 2
    assert st.hook_events["Stop"] == 2
    assert st.hook_events["SessionStart"] == 1


def test_blocking_error_is_counted_as_a_block(tmp_path):
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    assert st.hook_blocks["PostToolUse:Write"] == 1, dict(st.hook_blocks)
    assert sum(st.hook_blocks.values()) == 1


def test_nonzero_exit_is_counted_as_a_failure(tmp_path):
    """exit 127 on `${CLAUDE_PLUGIN_ROOT}/...` is a hook that never ran. Invisible before
    this patch; it is the whole reason hook telemetry is worth extracting."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    assert st.hook_errors["PostToolUse:Write"] == 2  # 127 non-blocking + blocking error
    assert st.hook_exit_codes[127] == 1


def test_hook_latency_is_recorded(tmp_path):
    """Hooks sit on the critical path of every tool call, so their latency is a first-class
    harness cost. A 107-second hook was observed live."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    assert st.hook_durations["PreToolUse:Bash"] == [469]
    assert 5559 in st.hook_durations["PreToolUse:mcp__hublive__hub_backend_add"]


def test_failing_hook_command_is_captured_for_diagnosis(tmp_path):
    """Counting a failure is useless without the command that failed -- that string is what
    identifies the unexpanded ${CLAUDE_PLUGIN_ROOT} placeholder."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    cmds = st.hook_failure_commands["PostToolUse:Write"]
    assert any("CLAUDE_PLUGIN_ROOT" in c for c in cmds), cmds


def test_block_reason_is_captured(tmp_path):
    """A block count with no reason cannot be triaged. Distinguishing a TRUE positive from
    the D1 use-vs-mention false-positive class requires the check's own message."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS))
    reasons = st.hook_block_reasons["PostToolUse:Write"]
    assert reasons, "block recorded with no reason -- untriageable"
    assert "urllib" in reasons[0]


def test_non_hook_attachments_are_not_counted(tmp_path):
    """No false positives: skill_listing / task_reminder / file share the attachment
    envelope but are not hooks."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", NON_HOOK_ATTACHMENTS))
    assert sum(st.hooks.values()) == 0, dict(st.hooks)
    assert sum(st.hook_errors.values()) == 0


def test_mixed_stream_counts_only_hooks(tmp_path):
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", ALL_HOOK_RECORDS + NON_HOOK_ATTACHMENTS))
    assert sum(st.hooks.values()) == 7


def test_malformed_attachment_does_not_crash(tmp_path):
    """FAIL-SOFT is a stated design constraint of mine.py; a 10 GB corpus contains junk."""
    junk = [
        {"type": "attachment", "attachment": None},
        {"type": "attachment", "attachment": "a string"},
        {"type": "attachment", "attachment": {"type": "hook_success"}},  # no hookName
        {"type": "attachment"},
        {"type": "attachment", "attachment": {"hookName": 12345, "exitCode": "x"}},
    ]
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", junk))
    assert sum(st.hooks.values()) == 0


def test_legacy_toplevel_hookname_still_works(tmp_path):
    """The original top-level probe stays wired so a future/other record shape that really
    does carry hookName at the root is not newly dropped."""
    st = _scan(_write_jsonl(tmp_path / "t.jsonl", [
        {"type": "system", "hookName": "LegacyShape", "timestamp": "2026-07-18T00:00:00Z"},
    ]))
    assert st.hooks["LegacyShape"] == 1


# --------------------------------------------------------------------------------------
# MECHANICAL KNOWN-POSITIVE CONTROL (INPUT-known-harness-defects.md D2 made executable).
# --------------------------------------------------------------------------------------
LIVE_CORPUS = Path(os.path.expanduser("~/.claude/projects"))

# The skip below is PORTABILITY ONLY (CI has no ~/.claude/projects). It is deliberately NOT
# the only thing guarding detector validity, because a skip that silently disappears is the
# very failure mode this control exists to catch: if the corpus were renamed, a bare skipif
# would quietly stop checking and nobody would notice.
#
# Two independent mitigations:
#   1. `test_mixed_stream_counts_only_hooks` proves the detector finds planted hooks among
#      realistic non-hook noise. It uses a fixture, so it can NEVER skip.
#   2. Set PR3_REQUIRE_LIVE_CORPUS=1 to turn the skip into a hard failure on any box that is
#      supposed to have the corpus (i.e. the owner's machine, or a harness-regression job).
_REQUIRE_LIVE = os.environ.get("PR3_REQUIRE_LIVE_CORPUS") == "1"


def test_live_corpus_is_present_when_required():
    """Fails loudly if the live corpus is required but missing, so the control below cannot
    silently stop running."""
    if not _REQUIRE_LIVE:
        pytest.skip("PR3_REQUIRE_LIVE_CORPUS not set; live-corpus control is optional here")
    assert LIVE_CORPUS.is_dir(), (
        f"PR3_REQUIRE_LIVE_CORPUS=1 but {LIVE_CORPUS} is absent -- the known-positive control "
        f"would have silently skipped, leaving the detector unguarded."
    )


@pytest.mark.skipif(
    not LIVE_CORPUS.is_dir() and not _REQUIRE_LIVE,
    reason="live corpus not present (portability skip; set PR3_REQUIRE_LIVE_CORPUS=1 to enforce)",
)
def test_control_detector_finds_known_present_hooks_in_live_corpus():
    """Prove the detector finds a KNOWN-PRESENT item before any absence is ever reported.

    Hooks demonstrably fire on this box (a SubagentStart hook injected context into the very
    turn that wrote this file). If this test finds zero, the detector is broken again --
    which is precisely the failure mode that produced `DETECTOR_STATUS: BROKEN`.
    """
    st = mine.Stats()
    scanned = 0
    for dirpath, _dirs, files in os.walk(LIVE_CORPUS):
        for f in files:
            if not f.endswith(".jsonl"):
                continue
            p = os.path.join(dirpath, f)
            try:
                if os.path.getsize(p) > 40 * 1024 * 1024:
                    continue
            except OSError:
                continue
            mine.scan(p, st, "session", 0)
            scanned += 1
            if sum(st.hooks.values()) >= 50:
                break
        if sum(st.hooks.values()) >= 50:
            break
    assert scanned > 0, "no transcripts scanned -- the control itself is invalid"
    assert sum(st.hooks.values()) >= 50, (
        f"KNOWN-POSITIVE CONTROL FAILED: scanned {scanned} live transcripts and found "
        f"{sum(st.hooks.values())} hook fires. Hooks are known to fire on this box, so a "
        f"zero/low count means the DETECTOR is broken, not that hooks are idle."
    )
    assert st.hook_events, "hook fires found but no hookEvent rollup -- partial extraction"
