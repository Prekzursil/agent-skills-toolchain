#!/usr/bin/env python3
"""Probe 2: frontmatter `model` field (not body grep) + use-vs-mention.

Independent of probe 1's path comparison. Tries to falsify the headline
opus-floor count by re-parsing the model field. A body-grep mutant that
flags the mention-only fixture is the bad detector this unit exists to
refuse. The planted frontmatter-sonnet fixture must be flagged; the
mention-only fixture must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drift as D  # noqa: E402

ART = REPO / D.OUT_REL
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0014-probe2 {msg}")
    return 1


def main() -> int:
    live = D.measure()
    uvm = live["use_vs_mention"]
    payload = {
        "probe": "probe2-frontmatter-model",
        "n_host_floor_violations": live["n_host_floor_violations"],
        "host_floor_violations": live["host_floor_violations"],
        "silent_on_mention": uvm["silent_on_mention"],
        "fires_on_frontmatter": uvm["fires_on_frontmatter"],
        "body_grep_flags_mention": uvm["body_grep_flags_mention"],
        "use_vs_mention_discriminates": uvm["use_vs_mention_discriminates"],
        "mention_model": uvm["mention_model"],
        "sonnet_model": uvm["sonnet_model"],
    }
    print(json.dumps(payload, sort_keys=True))

    if uvm["frontmatter_flags_mention"]:
        return fail("frontmatter detector flagged body-mention-only (use-vs-mention)")
    if not uvm["fires_on_frontmatter"]:
        return fail("frontmatter detector missed model: sonnet fixture")
    if not uvm["body_grep_flags_mention"]:
        return fail("mention fixture no longer contains sonnet; control is broken")
    if not uvm["use_vs_mention_discriminates"]:
        return fail("use-vs-mention did not discriminate both states")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable:{exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if D.SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("n_host_floor_violations") != live["n_host_floor_violations"]:
        return fail("artifact n_host_floor_violations drifted from live frontmatter parse")
    art_uvm = doc.get("use_vs_mention") or {}
    if art_uvm.get("silent_on_mention") is not True:
        return fail("artifact did not record silent_on_mention")
    if art_uvm.get("fires_on_frontmatter") is not True:
        return fail("artifact did not record fires_on_frontmatter")
    if art_uvm.get("frontmatter_flags_mention") is True:
        return fail("artifact flagged mention-only as a floor violation")
    orphans = list(doc.get("orphan_list") or [])
    if D.SONNET_REL not in orphans:
        return fail("artifact orphan_list omitted planted frontmatter-sonnet")
    if D.MENTION_REL in orphans:
        return fail("artifact orphan_list includes mention-only (body grep leak)")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("artifact reviewer.independent is not true")
    if str(rev.get("verdict") or "").upper() not in {"PASS", "PASSED"}:
        return fail("artifact reviewer.verdict is not PASS")

    print(
        f"frontmatter host_violations={live['n_host_floor_violations']} "
        f"silent_on_mention=True fires_on_sonnet=True body_grep_mention=True"
    )
    print("SUCCESS:AUD-0014-probe2 live frontmatter-model parse matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
