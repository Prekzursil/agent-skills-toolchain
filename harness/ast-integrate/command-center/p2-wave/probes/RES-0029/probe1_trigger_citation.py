#!/usr/bin/env python3
"""Probe 1: live re-fetch of match_trigger at file:line; dual rails; negative control."""
from __future__ import annotations

import json
import re
import sys

sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))

from common import (  # noqa: E402
    ART,
    DOCS_RAW,
    HERE,
    SENTINEL,
    SKILL_RAW,
    TRIGGER_RAW,
    UNIT,
    def_line,
    fetch,
    load_artifact,
    sha256_bytes,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def keyword_matches(keyword: str, message_lower: str) -> bool:
    keyword_lower = keyword.lower()
    if not keyword_lower:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])"
    return re.search(pattern, message_lower) is not None


def main() -> int:
    try:
        doc = load_artifact()
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"artifact {exc}")
    blob = json.dumps(doc)
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in blob:
        return fail("sentinel absent")

    skill = fetch(SKILL_RAW)
    trigger = fetch(TRIGGER_RAW)
    docs = fetch(DOCS_RAW)
    if skill["http_status"] != 200:
        return fail(f"skill.py http {skill['http_status']}")
    if trigger["http_status"] != 200:
        return fail(f"trigger.py http {trigger['http_status']}")
    if docs["http_status"] != 200:
        return fail(f"docs http {docs['http_status']}")

    skill_txt = skill["body"].decode("utf-8", "replace")
    trigger_txt = trigger["body"].decode("utf-8", "replace")
    docs_txt = docs["body"].decode("utf-8", "replace")
    mt = def_line(skill_txt, "def match_trigger(")
    kw = def_line(skill_txt, "def _keyword_matches(")
    if mt is None or kw is None:
        return fail("live skill.py missing match_trigger/_keyword_matches")
    if "class KeywordTrigger" not in trigger_txt or "class TaskTrigger" not in trigger_txt:
        return fail("live trigger.py missing KeywordTrigger/TaskTrigger")
    if "identical string matching logic" not in docs_txt:
        return fail("docs rail missing identical-string-matching sentence")
    if "class LLMRouterTrigger" in trigger_txt or "def llm_route_microagent" in skill_txt:
        return fail("negative control: unexpected LLM router in trigger path")

    cite = f"openhands-sdk/openhands/sdk/skills/skill.py:{mt}"
    if cite not in blob:
        return fail(f"artifact missing live file:line {cite}")

    trig_claim = next(
        (c for c in doc.get("claims") or [] if c.get("claim_id") == "C-TRIGGER-IS-KEYWORD-MATCH"),
        None,
    )
    if not isinstance(trig_claim, dict):
        return fail("missing C-TRIGGER-IS-KEYWORD-MATCH")
    rails = trig_claim.get("rails") or []
    kinds = {r.get("rail"): r.get("kind") for r in rails if isinstance(r, dict)}
    if kinds.get("R1") != "structured-api" or kinds.get("R2") != "prose-source":
        return fail(f"rails kinds {kinds}")
    for r in rails:
        if int(r.get("http_status") or 0) != 200:
            return fail(f"rail http {r}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(r.get("sha256") or "")):
            return fail("rail sha256")

    cap_api = HERE / "captures" / "skill.api.json"
    if not cap_api.is_file():
        return fail("captured Contents API JSON missing")
    api_sha = sha256_bytes(cap_api.read_bytes())
    r1 = next(r for r in rails if r.get("rail") == "R1")
    if r1.get("sha256") != api_sha:
        return fail("R1 sha256 does not match captured Contents API JSON")

    # Local replay of the cited matcher: git must not fire on github.
    if not keyword_matches("git", "please use git"):
        return fail("matcher control: git in 'please use git'")
    if keyword_matches("git", "see github actions"):
        return fail("negative control: git must not match github")
    if not keyword_matches("/design", "run /design now"):
        return fail("matcher control: /design")

    better = next(
        (c for c in doc.get("claims") or [] if c.get("claim_id") == "C-NOT-BETTER-THAN-KEYWORD"),
        None,
    )
    if not isinstance(better, dict):
        return fail("missing C-NOT-BETTER-THAN-KEYWORD")
    # The claim text says it is NOT a better router; do not allow an overclaim.
    if "not a better router than keyword matching" not in better.get("text", "").lower():
        return fail("overclaim: missing explicit not-better-than-keyword verdict")

    print(
        json.dumps(
            {
                "probe": "probe1-trigger-citation",
                "unit_id": UNIT,
                "pass": True,
                "match_trigger_line": mt,
                "keyword_matches_line": kw,
                "file_line": cite,
                "docs_identical_string_match": True,
                "git_does_not_match_github": True,
                "skill_live_sha256": skill["sha256"],
            }
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 trigger {cite} keyword-identity dual-rail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
