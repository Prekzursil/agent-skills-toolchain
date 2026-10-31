#!/usr/bin/env python3
"""Probe 2: tamper one index field (source) and re-resolve; audit digest capability."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0029-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if H.SENTINEL not in text or H.COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0029-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0029-probe2 self-declared {st}")
        return 1

    live = H.run_campaign()
    pred = live["predicates"]
    if not pred["control_private_only_selects_private"]:
        print("FAILED:ADV-0029-probe2 control did not select the private payload")
        return 1
    if not pred["schema_rejects_plugin_entry_digest"]:
        print("FAILED:ADV-0029-probe2 schema unexpectedly accepted plugin_entry sha256")
        return 1
    if not pred["honouring_digest_refuses_poison"]:
        print("FAILED:ADV-0029-probe2 honouring digest mutant did not refuse poison")
        return 1
    if not pred["detector_live"]:
        print("FAILED:ADV-0029-probe2 detector is not live")
        return 1

    t2 = live["targets"][1]
    if t2["verdict"] not in H.LEGAL:
        print("FAILED:ADV-0029-probe2 illegal verdict", t2)
        return 1
    art_targets = {
        t["id"]: t["verdict"] for t in doc.get("enumerated_targets") or []
    }
    live_targets = {t["id"]: t["verdict"] for t in live["targets"]}
    if art_targets != live_targets:
        print("FAILED:ADV-0029-probe2 target verdict mismatch", art_targets, live_targets)
        return 1

    schema = (live.get("production") or {}).get("schema") or {}
    if schema.get("integrity_or_origin_keys"):
        print("FAILED:ADV-0029-probe2 live schema unexpectedly has integrity fields")
        print(schema)
        return 1
    if schema.get("additional_properties") is not False:
        print("FAILED:ADV-0029-probe2 plugin_entry additionalProperties is not false")
        return 1
    if t2["fetched_sha256"] != live["payloads"]["poison_sha256"]:
        if t2["verdict"] == "CONFIRMED":
            print("FAILED:ADV-0029-probe2 CONFIRMED but fetched hash is not poison")
            return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or not reviewer.get("independent"):
        print("FAILED:ADV-0029-probe2 reviewer block", reviewer)
        return 1
    fp = H.fingerprints()
    if fp["source"] == fp["verifier"]:
        print("FAILED:ADV-0029-probe2 probe fingerprints identical")
        return 1

    plant = live.get("digest_field_plant") or {}
    summary = {
        "probe": "probe2-index-tamper",
        "unit_id": H.UNIT,
        "pass": True,
        "tampered_parse_ok": t2.get("tampered_parse_ok"),
        "fetched_sha256": t2.get("fetched_sha256"),
        "poison_sha256": live["payloads"]["poison_sha256"],
        "schema_integrity_keys": schema.get("integrity_or_origin_keys"),
        "schema_additional_properties": schema.get("additional_properties"),
        "digest_plant_rejected": plant.get("rejected"),
        "digest_plant_messages": plant.get("rejection_messages"),
        "honouring_digest_refused": pred["honouring_digest_refuses_poison"],
        "metadata_digest_ignored": pred["metadata_digest_ignored_by_installer"],
        "t2_index_poisoning": t2["verdict"],
        "source_fp": fp["source"][:16],
        "verifier_fp": fp["verifier"][:16],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "tamper_hash={0} poison={1} plant_rejected={2} t2={3}".format(
            t2.get("fetched_sha256"),
            live["payloads"]["poison_sha256"],
            plant.get("rejected"),
            t2["verdict"],
        )
    )
    print("SUCCESS:ADV-0029-probe2 tampered index source accepted; schema has no digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
