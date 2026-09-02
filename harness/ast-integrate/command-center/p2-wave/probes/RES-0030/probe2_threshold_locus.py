#!/usr/bin/env python3
"""Named probe 2: failure-threshold locus + configurable-vs-hardcoded control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    CONFIG_KEY,
    CONFIG_READ_LINE,
    CONSTRUCTOR_DEFAULT_LINE,
    DEFAULT_FAILURE_THRESHOLD,
    DEFAULT_THRESHOLD_LINE,
    INIT_REL,
    LEAD_WORKER_REL,
    OUTPUT_REL,
    REPO,
    SENTINEL,
    SWITCH_LOG_LINE,
    TRIGGER_LINE,
    UNIT_ID,
)
from threshold import extract_threshold  # noqa: E402

ART = REPO / OUTPUT_REL


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0030-probe2 {msg}")
    return 1


def main() -> int:
    live = extract_threshold()
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")

    thr = doc.get("escalation_threshold") or {}
    if thr.get("default") != DEFAULT_FAILURE_THRESHOLD:
        return _fail(f"default {thr.get('default')}")
    if thr.get("configurable") is not True:
        return _fail("threshold not recorded as configurable")
    if thr.get("config_key") != CONFIG_KEY:
        return _fail(f"config_key {thr.get('config_key')}")

    want_loci = {
        f"{INIT_REL}:{DEFAULT_THRESHOLD_LINE}",
        f"{INIT_REL}:{CONFIG_READ_LINE}",
        f"{LEAD_WORKER_REL}:{CONSTRUCTOR_DEFAULT_LINE}",
        f"{LEAD_WORKER_REL}:{TRIGGER_LINE}",
    }
    blob = json.dumps(doc)
    missing = [locus for locus in want_loci if locus not in blob]
    if missing:
        return _fail(f"locus-absent {missing}")
    if f"{LEAD_WORKER_REL}:{SWITCH_LOG_LINE}" not in blob:
        return _fail("switch-log locus absent")

    if live["configurable"] is not True:
        return _fail("live parse says not configurable")
    if live["direction"] != "worker-to-lead-fallback":
        return _fail(f"direction {live['direction']}")
    if live["catalog_framing_lead_to_worker_via_failure_threshold"] != "REFUTED":
        return _fail("catalog framing not refuted")
    if live["mutant_config_key_stripped_still_configurable"]:
        return _fail("both-states mutant still configurable")
    if not live["main_lead_worker_absent"]:
        return _fail(f"main still has lead_worker.rs status={live['main_lead_worker_http_status']}")

    # Artifact must not cite "beats retry" as measured fact.
    beats = None
    for claim in doc.get("claims") or []:
        cid = str(claim.get("id") or "")
        statement = str(claim.get("claim") or claim.get("canonical_mechanism") or "")
        if "beats" in statement.lower() or cid in {"C5", "RES-0030-C5"} or "retrying the same worker" in statement.lower():
            beats = claim
            break
    if beats is None:
        return _fail("beats-retry claim row missing")
    verdict = str(beats.get("verdict") or beats.get("status") or "").upper()
    tier = str(beats.get("evidence_tier") or "")
    if verdict not in {"REFUTED", "NOT-CHECKED"}:
        return _fail(f"beats-retry overclaimed verdict={verdict}")
    if verdict != "REFUTED" and tier not in {"E3", "E4"}:
        return _fail(f"beats-retry must be REFUTED or E3/E4, got {verdict}/{tier}")

    # Directional claim in artifact.
    framing = str(thr.get("direction") or "")
    if "worker-to-lead" not in framing:
        return _fail(f"artifact direction {framing}")

    recipes = doc.get("recipes") or {}
    if not recipes.get("retry_is_distinct_from_lead_worker"):
        return _fail("recipes retry not distinguished from lead/worker")

    out = {
        "probe": "probe2-threshold-locus",
        "unit_id": UNIT_ID,
        "pass": True,
        "default_threshold": live["default_threshold"],
        "configurable": True,
        "config_key": CONFIG_KEY,
        "loci": live["loci"],
        "direction": live["direction"],
        "main_absent": live["main_lead_worker_absent"],
        "mutant_rejected": True,
        "beats_retry_verdict": verdict,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"threshold={live['default_threshold']} configurable=True "
        f"locus={live['loci']['trigger']} direction={live['direction']}"
    )
    print(f"SUCCESS:{UNIT_ID}-probe2 escalation threshold at file:line")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
