#!/usr/bin/env python3
"""Probe 1: onion class stays OFF by default; default path runs without it.

Both-states: absent opt-in vs planted owner opt-in. Never-list actions fail closed.
No live onion connection in either state.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import legal_review as LR  # noqa: E402
import onion_gate as OG  # noqa: E402
import sweep as S  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/wfa/WFA-0028-sweep-niche-archival.json"
ONION_URL = "http://wfa0028researchexample.onion/orchestration-index"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0028-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "WFA-0028":
        return fail("unit_id")
    if "SUCCESS:WFA-0028" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    saved_opt = os.environ.pop("WFA0028_OWNER_OPT_IN", None)
    saved_env = os.environ.pop("WFA0028_ONION", None)
    try:
        off = OG.onion_class_enabled()
        if off["enabled"]:
            return fail("default-enabled")
        cls_off = OG.classify_url(ONION_URL, enabled=False)
        if cls_off["action"] != "skip-class-off":
            return fail(f"default-did-not-skip {cls_off}")

        os.environ["WFA0028_ONION"] = "1"
        env_only = OG.onion_class_enabled()
        if env_only["enabled"]:
            return fail("env-alone-enabled-onion")

        with tempfile.TemporaryDirectory(prefix="wfa0028-optin-") as tmp:
            planted = Path(tmp) / "onion-source-class-opt-in.json"
            planted.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "unit_id": "WFA-0028",
                        "owner": "probe1-planted-owner",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            os.environ["WFA0028_OWNER_OPT_IN"] = str(planted)
            os.environ.pop("WFA0028_ONION", None)
            on = OG.onion_class_enabled()
            if not on["enabled"]:
                return fail(f"opt-in-did-not-enable {on}")
            cls_on = OG.classify_url(ONION_URL, enabled=True)
            if cls_on["action"] == "allow-read":
                return fail("opt-in-must-not-live-fetch")
            if "onion" not in cls_on["class"]:
                return fail("opt-in-lost-onion-label")
    finally:
        if saved_opt is None:
            os.environ.pop("WFA0028_OWNER_OPT_IN", None)
        else:
            os.environ["WFA0028_OWNER_OPT_IN"] = saved_opt
        if saved_env is None:
            os.environ.pop("WFA0028_ONION", None)
        else:
            os.environ["WFA0028_ONION"] = saved_env

    default_run = S.run(onion_enabled=False)
    if default_run["onion_gate"]["enabled"]:
        return fail("sweep-default-onion-on")
    if not default_run["onion_skipped"]:
        return fail("queued-onion-not-reported")
    if any(x.get("action") == "allow-read" for x in default_run["onion_skipped"]):
        return fail("onion-was-fetched")
    if default_run["counts"]["findings"] < 1:
        return fail("default-path-produced-no-findings")
    if not default_run["legal_review"]["pass"]:
        return fail("legal-review-failed-on-default")

    artifact_onion = doc.get("onion_source_class") or doc.get("onion_gate") or {}
    if artifact_onion.get("enabled") is True:
        return fail("artifact-claims-onion-on")

    never = LR.refuse_if_action("purchase")
    if never["pass"] or never["verdict"] != "FAIL-CLOSED":
        return fail(f"never-list-silent {never}")
    hits = never.get("never_list_hits") or []
    if "purchase" not in hits and "transaction" not in hits:
        return fail(f"never-list-missed-purchase {never}")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-onion-default-off",
                "unit_id": "WFA-0028",
                "default_enabled": False,
                "env_alone_insufficient": True,
                "opt_in_enables_class": True,
                "opt_in_still_no_live_fetch": True,
                "default_findings": default_run["counts"]["findings"],
                "onion_skipped": len(default_run["onion_skipped"]),
                "never_list_fail_closed": True,
            }
        )
    )
    print("SUCCESS:WFA-0028-probe1 onion class default-off and default path runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
