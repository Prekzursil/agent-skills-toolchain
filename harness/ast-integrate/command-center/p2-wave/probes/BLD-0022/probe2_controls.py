#!/usr/bin/env python3
"""Named probe 2: known OWNER-EXPLICIT (PR-ONLY) and AGENT-ASSUMED controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import corpus as CORP  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0022.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0022-probe2 {msg}")
    return 1


def main() -> int:
    utts = CORP.load_fixture_utterances()
    pr = C.classify("PR-ONLY", utts)
    if pr.classification != C.OWNER_EXPLICIT:
        return fail(f"PR-ONLY fixture -> {pr.classification}")
    if "Release mode is PR-ONLY." not in (pr.owner_quote or ""):
        return fail(f"PR-ONLY quote {pr.owner_quote!r}")
    if "owner-release.md" not in (pr.owner_quote_anchor or ""):
        return fail(f"PR-ONLY anchor {pr.owner_quote_anchor}")

    assumed = C.classify("Z-00", utts)
    if assumed.classification != C.AGENT_ASSUMED:
        return fail(f"Z-00 fixture -> {assumed.classification}")
    if assumed.routed_to_owner is not True:
        return fail("Z-00 not routed to owner")

    # Drop the owner-release utterance: PR-ONLY must leave OWNER-EXPLICIT.
    no_owner = [u for u in utts if "owner-release.md" not in u.path]
    pr_bad = C.classify("PR-ONLY", no_owner)
    if pr_bad.classification == C.OWNER_EXPLICIT:
        return fail("PR-ONLY stayed EXPLICIT with owner file removed")

    if ART.is_file() and ART.stat().st_size > 0:
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:BLD-0022" not in text:
            return fail("sentinel-absent")
        controls = {
            str(r.get("id")): r for r in (doc.get("control_classifications") or [])
        }
        fx = controls.get("CTRL-PR-ONLY-FIXTURE")
        if not fx or fx.get("classification") != C.OWNER_EXPLICIT:
            return fail("artifact missing OWNER-EXPLICIT PR-ONLY fixture control")
        live = controls.get("CTRL-PR-ONLY-LIVE")
        if not live:
            return fail("artifact missing live PR-ONLY control")
        if live.get("classification") == C.OWNER_EXPLICIT:
            quote = live.get("owner_quote")
            if not quote:
                return fail("live PR-ONLY claimed EXPLICIT without owner quote")
        z = controls.get("CTRL-Z-00-AGENT-ASSUMED")
        if not z or z.get("classification") != C.AGENT_ASSUMED:
            return fail("artifact missing AGENT-ASSUMED Z-00 control")
        if z.get("routed_to_owner") is not True:
            return fail("Z-00 control not routed")
        for row in doc.get("selected_options") or []:
            if row.get("classification") == C.OWNER_EXPLICIT:
                if not row.get("owner_quote") or not row.get("owner_quote_anchor"):
                    return fail(f"live {row.get('id')} EXPLICIT without quote")
            if row.get("classification") == C.AGENT_ASSUMED:
                if row.get("routed_to_owner") is not True:
                    return fail(f"live {row.get('id')} AGENT-ASSUMED not routed")
        reviewer = doc.get("reviewer") or {}
        if reviewer.get("independent") is not True:
            return fail("reviewer not independent")
        if reviewer.get("input_was_quotes_only") is not True:
            return fail("reviewer did not restrict input to quotes")
        if int(reviewer.get("rescored_count") or 0) < 5:
            return fail("reviewer rescored fewer than 5")
        if reviewer.get("verdict") != "PASS":
            return fail("reviewer verdict not PASS")

    out = {
        "probe": "probe2-pr-only-and-agent-assumed",
        "unit_id": "BLD-0022",
        "pr_only_fixture": pr.classification,
        "z00_fixture": assumed.classification,
        "pr_only_without_owner_file": pr_bad.classification,
        "fired_on_bad": pr_bad.classification != C.OWNER_EXPLICIT,
        "silent_on_good": pr.classification == C.OWNER_EXPLICIT,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:BLD-0022-probe2 PR-ONLY explicit and AGENT-ASSUMED controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
