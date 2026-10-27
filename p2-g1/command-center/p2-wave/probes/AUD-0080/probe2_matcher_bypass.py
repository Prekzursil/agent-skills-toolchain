#!/usr/bin/env python3
"""Named probe 2: matcher receipt for allow-listed commands vs hook intent.

Mechanically independent of probe 1: re-reads allow rules to construct commands,
then tests matchers. Config read is the model; this matcher test is the receipt.

Includes the use-vs-mention control: PAYLOAD quoting rm -rf with a benign VERB
must not be flagged by the verb-aware gate; the naive payload-body grep must
flag both recorded false positives so the control is non-vacuous.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    construct_and_test_hooks,
    evaluate_use_vs_mention,
    extract_permissions,
    fixture_hooks,
    hook_fires,
    live_and_repo_hooks,
    live_permission_scopes,
    load_json,
    mention_vs_hooks,
    merge_allow_deny,
    naive_payload_guard,
    verb_aware_rm_gate,
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0080-probe2 {msg}")
    return 1


def main() -> int:
    control = evaluate_use_vs_mention()
    if not control["pass"]:
        return fail(
            "use-vs-mention control failed: "
            f"naive_mentions={control['naive_flags_mentions']} "
            f"verb_mentions={control['verb_aware_flags_mentions']} "
            f"verb_uses={control['verb_aware_flags_uses']}"
        )
    if len(control["naive_flags_mentions"]) != 2:
        return fail("naive payload-body guard did not flag both recorded false positives")
    if control["verb_aware_flags_mentions"]:
        return fail("verb-aware gate flagged a mention (payload-body defect)")

    hooks = fixture_hooks()
    if len(hooks) < 3:
        return fail(f"expected >=3 fixture hooks, got {len(hooks)}")

    settings = HERE / "fixtures" / "hooks" / "settings.json"
    allow, _deny = extract_permissions(load_json(settings))
    tests = construct_and_test_hooks(hooks, allow)
    by_id = {
        (t["hook"].get("handler_id"), t["hook"].get("event")): t for t in tests
    }
    rm_gate = next(
        (t for t in tests if t["hook"].get("handler_id") == "intent-gate-rm"),
        None,
    )
    wrong = next(
        (t for t in tests if t["hook"].get("handler_id") == "wrong-field-tool-name"),
        None,
    )
    naive = next(
        (t for t in tests if t["hook"].get("handler_id") == "naive-grep-rm.sh"),
        None,
    )
    if rm_gate is None or wrong is None or naive is None:
        return fail(f"missing fixture hook rows: {list(by_id)}")
    if rm_gate["classification"] != "CAUGHT":
        return fail(f"intent-gate-rm should catch allow-listed rm, got {rm_gate}")
    if wrong["classification"] != "BYPASS":
        return fail(
            "wrong-field matcher ^rm against tool_name Bash must miss allow-listed "
            f"rm -rf; got {wrong['classification']}"
        )
    if naive["classification"] != "CAUGHT":
        return fail(
            "cursor naive matcher should fire on constructed rm -rf intent command; "
            f"got {naive['classification']}"
        )

    mentions = mention_vs_hooks(hooks)
    echo_on_if = [
        m
        for m in mentions
        if m["case_id"] == "fp-echo-quotes-rm" and m["hook_id"] == "intent-gate-rm"
    ]
    grep_on_if = [
        m
        for m in mentions
        if m["case_id"] == "fp-grep-needle-rm" and m["hook_id"] == "intent-gate-rm"
    ]
    echo_on_naive = [
        m
        for m in mentions
        if m["case_id"] == "fp-echo-quotes-rm" and m["hook_id"] == "naive-grep-rm.sh"
    ]
    grep_on_naive = [
        m
        for m in mentions
        if m["case_id"] == "fp-grep-needle-rm" and m["hook_id"] == "naive-grep-rm.sh"
    ]
    if not echo_on_if or echo_on_if[0]["class"] != "SILENT-ON-MENTION":
        return fail(f"if-rule Bash(rm *) must not catch echo-quoted rm: {echo_on_if}")
    if not grep_on_if or grep_on_if[0]["class"] != "SILENT-ON-MENTION":
        return fail(f"if-rule Bash(rm *) must not catch grep needle: {grep_on_if}")
    if not echo_on_naive or echo_on_naive[0]["class"] != "FALSE-POSITIVE":
        return fail(f"naive payload matcher must FP on echo quotes: {echo_on_naive}")
    if not grep_on_naive or grep_on_naive[0]["class"] != "FALSE-POSITIVE":
        return fail(f"naive payload matcher must FP on grep needle: {grep_on_naive}")

    find_cmd = "find /tmp -delete"
    find_vs_rm_hook = hook_fires(
        {
            "event": "PreToolUse",
            "matcher": "Bash",
            "if_rule": "Bash(rm *)",
            "handler_id": "intent-gate-rm",
            "family": "claude-or-plugin",
        },
        "Bash",
        find_cmd,
    )
    if find_vs_rm_hook["fires"]:
        return fail("Bash(rm *) if-rule must not treat find -delete as rm")
    if "Bash(find *)" not in allow:
        return fail("fixture allow missing Bash(find *) for intent-bypass sample")

    live_hooks = live_and_repo_hooks()
    live_scopes = live_permission_scopes()
    live_allow = merge_allow_deny(live_scopes)["effective_allow"]
    live_tests = construct_and_test_hooks(
        [h for h in live_hooks if h.get("scope") != "repo-plugin-fixture-cnf0146"],
        live_allow,
    )
    plugin_tests = construct_and_test_hooks(
        [h for h in live_hooks if h.get("scope") == "repo-plugin-fixture-cnf0146"],
        live_allow or ["Shell(ls)"],
    )

    payload = {
        "probe": "probe2-matcher-bypass",
        "unit_id": "AUD-0080",
        "pass": True,
        "use_vs_mention": control,
        "fixture_hook_tests": tests,
        "mention_vs_hooks": mentions,
        "intent_bypass_find_vs_rm_if": {
            "command": find_cmd,
            "allow_rule": "Bash(find *)",
            "hook_if": "Bash(rm *)",
            "fires": find_vs_rm_hook["fires"],
            "classification": "BYPASS",
            "note": (
                "Allow-listed find -delete matches the destructive intent of the "
                "rm gate but the matcher/if does not catch it."
            ),
        },
        "live_hook_count": len(
            [h for h in live_hooks if not str(h.get("scope") or "").startswith("repo-")]
        ),
        "repo_plugin_hook_count": len(
            [h for h in live_hooks if h.get("scope") == "repo-plugin-fixture-cnf0146"]
        ),
        "live_effective_allow": live_allow,
        "live_matcher_tests": live_tests,
        "plugin_fixture_matcher_tests": plugin_tests,
        "naive_payload_guard_echo": naive_payload_guard('echo "rm -rf /"'),
        "verb_aware_echo": verb_aware_rm_gate('echo "rm -rf /"'),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        "use_vs_mention=PASS naive_fp=2 verb_fp=0 "
        f"rm_gate={rm_gate['classification']} "
        f"wrong_field={wrong['classification']} "
        f"live_hooks={payload['live_hook_count']}"
    )
    print("SUCCESS:AUD-0080-probe2 matcher receipt and use-vs-mention control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
