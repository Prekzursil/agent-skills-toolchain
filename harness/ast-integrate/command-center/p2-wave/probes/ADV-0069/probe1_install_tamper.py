#!/usr/bin/env python3
"""Probe 1: install from tampered mirror and tampered bundle; record hashes.

Live client under test: tools/marketplace/blob_store.py (IMP-0121).
Production offline import (IMP-0109) is measured as absent, not invented.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dist import (  # noqa: E402
    PKG_NAME,
    PKG_VERSION,
    build_pristine_bundle,
    build_pristine_mirror,
    install_from_mirror,
    production_surfaces,
    tamper_bundle_payload,
    tamper_mirror_payload,
    verify_bundle_envelope_only,
    verify_bundle_recompute,
)


def main() -> int:
    surfaces = production_surfaces()
    with tempfile.TemporaryDirectory(prefix="adv0069-p1-") as td:
        tmp = Path(td)
        mirror = tmp / "mirror"
        mirror.mkdir()
        built = build_pristine_mirror(mirror)
        pristine_m = install_from_mirror(mirror, "pristine")
        tamper_m = tamper_mirror_payload(Path(built["store_root"]))
        tampered_m = install_from_mirror(mirror, "tampered")

        bundle = tmp / "bundle"
        bundle.mkdir()
        built_b = build_pristine_bundle(bundle)
        pristine_env = verify_bundle_envelope_only(bundle, "pristine")
        pristine_re = verify_bundle_recompute(bundle, "pristine")
        tamper_b = tamper_bundle_payload(bundle)
        tampered_env = verify_bundle_envelope_only(bundle, "tampered")
        tampered_re = verify_bundle_recompute(bundle, "tampered")

    prod_importer = surfaces["any_named_offline_or_mirror_module"]
    mirror_detects = (
        pristine_m.all_pass
        and tampered_m.detected
        and not tampered_m.all_pass
        and tampered_m.declared_digest != tampered_m.observed_digest
        and tampered_m.blobstore_error is not None
    )
    envelope_misses_payload_tamper = (
        pristine_env.detected is False
        and tampered_env.detected is False
        and tampered_env.declared_digest != tampered_env.observed_digest
    )
    recompute_catches = (
        pristine_re.all_pass
        and tampered_re.detected
        and tampered_re.declared_digest != tampered_re.observed_digest
    )
    both_states = bool(pristine_m.all_pass and tampered_m.detected)
    wrong_gate_silent_on_good = not pristine_env.detected and (
        pristine_env.declared_digest == pristine_env.observed_digest
    )
    wrong_gate_misses_bad = (not tampered_env.detected) and envelope_misses_payload_tamper

    out = {
        "probe": "probe1_install_tamper",
        "package": {"name": PKG_NAME, "version": PKG_VERSION},
        "production_surfaces": surfaces,
        "production_offline_importer_present": prod_importer,
        "mirror": {
            "pristine": pristine_m.as_dict(),
            "tamper": tamper_m,
            "tampered": tampered_m.as_dict(),
            "tamper_detected_by_live_BlobStore_get": mirror_detects,
        },
        "bundle": {
            "built": {
                "digest": built_b["digest"],
                "envelope_sha256": built_b["envelope_sha256"],
                "manifest_keys": built_b["manifest_keys"],
                "has_digest_field": built_b["has_digest_field"],
            },
            "tamper": tamper_b,
            "pristine_envelope_only": pristine_env.as_dict(),
            "pristine_recompute": pristine_re.as_dict(),
            "tampered_envelope_only": tampered_env.as_dict(),
            "tampered_recompute": tampered_re.as_dict(),
            "production_client_detected_tamper": False,
            "fixture_recompute_detected_tamper": recompute_catches,
            "envelope_only_missed_payload_tamper": envelope_misses_payload_tamper,
        },
        "controls": {
            "NC-PRODUCTION-BOTH-STATES": {
                "silent_on_good_state": pristine_m.all_pass,
                "fired_on_bad_state": tampered_m.detected,
                "ok": both_states,
            },
            "NC-WRONG-GATE-MATCHER": {
                "silent_on_good_state": wrong_gate_silent_on_good,
                "fired_on_bad_state": wrong_gate_misses_bad,
                "note": (
                    "The wrong gate (envelope-only) staying green on a "
                    "payload tamper is the mutant going red relative to "
                    "the recompute detector."
                ),
                "ok": wrong_gate_silent_on_good and wrong_gate_misses_bad and recompute_catches,
            },
        },
        "artifact_hash_evidence": {
            "mirror_declared": tampered_m.declared_digest,
            "mirror_observed_after_tamper": tampered_m.observed_digest,
            "bundle_declared": tampered_re.declared_digest,
            "bundle_observed_after_tamper": tampered_re.observed_digest,
        },
    }
    text = json.dumps(out, indent=2, sort_keys=True)
    print(text)
    ok = (
        both_states
        and recompute_catches
        and envelope_misses_payload_tamper
        and not prod_importer
        and built["payload_sha256"] == built["digest"]
    )
    if not ok:
        print("FAILED:ADV-0069-probe1 measurement invariants broken", file=sys.stderr)
        return 1
    print(
        "SUCCESS:ADV-0069-probe1 tampered-mirror detected by BlobStore.get; "
        "tampered-bundle missed by envelope-only and by absent production importer; "
        "payload-recompute fixture detector fired; hashes recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
