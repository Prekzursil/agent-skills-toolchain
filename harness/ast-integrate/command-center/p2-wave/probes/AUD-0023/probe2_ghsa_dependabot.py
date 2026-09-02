#!/usr/bin/env python3
"""Probe 2: independent GHSA (npm bulk) + Dependabot attempt; falsify headline."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from snapshot import COMPLETION_SENTINEL, OUT, report_of  # noqa: E402
from sources import (  # noqa: E402
    CONTROL_ADVISORY,
    CONTROL_PACKAGE,
    CONTROL_VERSION,
    NPM_BULK,
    ghsa_ids_for_npm,
    npm_bulk_query,
    try_dependabot_alerts,
)

ART = REPO / OUT


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0023-probe2 {msg}")
    return 1


def main() -> int:
    bulk = npm_bulk_query({CONTROL_PACKAGE: [CONTROL_VERSION]})
    ghsa_ids = ghsa_ids_for_npm(CONTROL_PACKAGE, bulk)
    reported = CONTROL_ADVISORY in set(ghsa_ids)
    dependabot = try_dependabot_alerts()
    payload = {
        "probe": "probe2-ghsa-dependabot",
        "instrument": NPM_BULK,
        "dependabot": dependabot,
        "npm_ok": bool(bulk.get("ok")),
        "npm_http": bulk.get("http_status"),
        "control_advisory": CONTROL_ADVISORY,
        "ghsa_reported": reported,
        "ghsa_ids": ghsa_ids,
    }
    print(json.dumps(payload, sort_keys=True))
    if not bulk.get("ok"):
        return fail(f"npm bulk http={bulk.get('http_status')}")
    if not reported:
        return fail(f"{CONTROL_ADVISORY} absent from GHSA/npm bulk for lodash@4.17.20")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state={doc.get('state')}")
    if COMPLETION_SENTINEL not in text:
        return fail("completion sentinel absent")
    rep = report_of(doc)
    ctrl = rep.get("known_present_control") or doc.get("known_present_control") or {}
    if ctrl.get("ghsa_reported") is not True:
        return fail("artifact ghsa_reported is not true")
    if ctrl.get("both_sources_report") is not True:
        return fail("artifact both_sources_report is not true")
    if CONTROL_ADVISORY not in set(ctrl.get("ghsa_ids") or []):
        return fail("artifact missing control advisory in ghsa_ids")
    gh_src = ((rep.get("sources") or doc.get("sources") or {}).get("github_advisory")) or {}
    if gh_src.get("queried") is not True:
        return fail("sources.github_advisory.queried is not true")
    if gh_src.get("endpoint") != NPM_BULK:
        return fail("github advisory endpoint mismatch")
    headline = (rep.get("headline") or doc.get("headline") or {}).get(
        "production_packages_with_advisory"
    )
    live_prod = 0
    findings = rep.get("findings") or doc.get("findings") or []
    for finding in findings:
        if finding.get("scope") == "production" and (
            finding.get("osv_ids") or finding.get("ghsa_ids")
        ):
            live_prod += 1
    if headline != live_prod:
        return fail(
            f"headline production count {headline} != recount {live_prod}"
        )
    # Sibling fixtures must not be treated as the product closure.
    for finding in findings:
        lock = str(finding.get("lockfile") or "")
        if finding.get("scope") == "production" and "/p2-wave/probes/" in lock:
            if "/AUD-0023/" not in lock:
                return fail(f"sibling probe fixture in production findings: {lock}")
    decay = rep.get("decay") or doc.get("decay") or {}
    expires = decay.get("must_requery_after")
    queried = decay.get("query_timestamp")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not expires or expires <= queried or expires <= now:
        return fail("decay timestamp missing or already expired")
    print(
        "SUCCESS:AUD-0023-probe2 "
        f"ghsa_reported={reported} production_headline={headline} "
        f"dependabot={dependabot.get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
