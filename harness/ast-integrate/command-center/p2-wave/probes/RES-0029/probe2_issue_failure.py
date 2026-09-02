#!/usr/bin/env python3
"""Probe 2: issue-tracker failure mode #10073; negative control #9889."""
from __future__ import annotations

import json
import re
import sys

sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))

from common import (  # noqa: E402
    HERE,
    ISSUE_CTRL_HTML,
    ISSUE_HTML,
    SENTINEL,
    UNIT,
    fetch,
    issue_title_from_html,
    load_artifact,
    sha256_bytes,
    slash_trigger_failure_title,
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    try:
        doc = load_artifact()
    except (OSError, json.JSONDecodeError) as exc:
        return fail(f"artifact {exc}")
    blob = json.dumps(doc)
    if SENTINEL not in blob:
        return fail("sentinel absent")
    if "issues/10073" not in blob:
        return fail("issue 10073 not cited")

    claim = next(
        (
            c
            for c in doc.get("claims") or []
            if c.get("claim_id") == "C-ISSUE-TRACKER-FAILURE-MODE"
        ),
        None,
    )
    if not isinstance(claim, dict):
        return fail("missing C-ISSUE-TRACKER-FAILURE-MODE")
    rails = [r for r in (claim.get("rails") or []) if isinstance(r, dict)]
    if len(rails) < 2:
        return fail("failure-mode claim lacks two rails")
    kinds = {r.get("kind") for r in rails}
    if "structured-api" not in kinds or "prose-source" not in kinds:
        return fail(f"rails kinds {kinds}")

    cap = HERE / "captures" / "issue10073.json"
    comments_path = HERE / "captures" / "issue10073.comments.json"
    if not cap.is_file() or not comments_path.is_file():
        return fail("captured issue JSON missing")
    issue = json.loads(cap.read_text(encoding="utf-8"))
    comments = json.loads(comments_path.read_text(encoding="utf-8"))
    title = str(issue.get("title") or "")
    if not slash_trigger_failure_title(title):
        return fail(f"captured title is not the slash-trigger bug: {title!r}")
    r1 = next(r for r in rails if r.get("rail") == "R1")
    if r1.get("sha256") != sha256_bytes(cap.read_bytes()):
        return fail("R1 sha256 mismatch vs captured issue JSON")

    bodies = "\n".join(str(c.get("body") or "") for c in comments)
    if "does not get triggered at all" not in bodies.lower():
        return fail("captured comments missing knowledge-type still-not-triggering")
    if "/design" not in (issue.get("body") or "") and "/design" not in bodies:
        return fail("captured issue missing /design trigger")

    live = fetch(ISSUE_HTML)
    if live["http_status"] != 200:
        return fail(f"live issue html http {live['http_status']}")
    live_title = issue_title_from_html(live["body"].decode("utf-8", "replace"))
    if not slash_trigger_failure_title(live_title):
        return fail(f"live HTML title mismatch {live_title!r}")

    ctrl = fetch(ISSUE_CTRL_HTML)
    if ctrl["http_status"] != 200:
        return fail(f"control issue html http {ctrl['http_status']}")
    ctrl_title = issue_title_from_html(ctrl["body"].decode("utf-8", "replace"))
    if slash_trigger_failure_title(ctrl_title):
        return fail(f"negative control #9889 incorrectly classified: {ctrl_title!r}")
    if "9889" not in ctrl_title and "repo" not in ctrl_title.lower():
        # Title should be the org-repo-trigger feature request, not the slash bug.
        if "not triggering" in ctrl_title.lower() and "/" in ctrl_title:
            return fail(f"control title collapsed into slash bug {ctrl_title!r}")

    print(
        json.dumps(
            {
                "probe": "probe2-issue-failure",
                "unit_id": UNIT,
                "pass": True,
                "issue": 10073,
                "title": title,
                "live_title": live_title,
                "negative_control_issue": 9889,
                "negative_control_title": ctrl_title,
                "knowledge_type_still_failed": True,
            }
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe2 issue-tracker failure mode #10073 "
        f"control=#9889 not-slash-bug"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
