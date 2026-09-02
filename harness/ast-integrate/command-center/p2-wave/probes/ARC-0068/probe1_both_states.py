#!/usr/bin/env python3
"""Probe 1: both-states digest-only FAIL / full-artifact PASS.

Also proves a judge attestation without citations is not evidence.
Live A1/A2 DESIGN.json rows must match the artifact when those files exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402

ART = REPO / "command-center/phase3/FULL-READ-GATE.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0068-probe1 {msg}")
    return 1


def main() -> int:
    if not G.FIXTURE_DOSSIER.is_file():
        return fail("fixture-dossier-absent")
    digest = G.admit_paths(G.FIXTURE_DIGEST, G.FIXTURE_DOSSIER)
    full = G.admit_paths(G.FIXTURE_FULL, G.FIXTURE_DOSSIER)
    assertion = G.admit_paths(G.FIXTURE_ASSERT, G.FIXTURE_DOSSIER)
    print(
        "fixture digest={0} {1} full={2} {3} assertion={4} {5}".format(
            digest["verdict"],
            digest["coverage"]["coverage_fraction"],
            full["verdict"],
            full["coverage"]["coverage_fraction"],
            assertion["verdict"],
            assertion["failing_condition_id"],
        )
    )
    if digest["verdict"] != "FAIL":
        return fail("digest-only-did-not-fail")
    if digest["failing_condition_id"] != G.FR_COVERAGE:
        return fail(f"digest-failing={digest['failing_condition_id']}")
    if digest["coverage"]["cited_distinct"] != 0:
        return fail("digest-matched-a-dossier-section")
    if full["verdict"] != "PASS":
        return fail("full-artifact-did-not-pass")
    if full["coverage"]["cited_distinct"] != full["coverage"]["sections_present"]:
        return fail("full-card-did-not-cite-every-derived-section")
    if assertion["verdict"] != "FAIL":
        return fail("attestation-only-did-not-fail")
    if assertion["failing_condition_id"] != G.FR_NO_CITATIONS:
        return fail("attestation-must-fail-as-no-citations")
    if assertion["coverage"]["judge_attested_full_read"] is not True:
        return fail("assertion-fixture-lost-attestation-flag")

    live = G.live_dossier_states(REPO)
    for row in live:
        print(
            "live {0} present={1} ok={2}".format(
                row["path"],
                row["present"],
                (row.get("both_states") or {}).get("ok"),
            )
        )
        if not row["present"]:
            continue
        both = row["both_states"]
        if not both or not both["ok"]:
            return fail(f"live-both-states {row['path']}")
        if both["digest_verdict"] != "FAIL" or both["full_verdict"] != "PASS":
            return fail(f"live-verdicts {row['path']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("FULL-READ-GATE.json missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0068" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    stored = doc.get("both_states") or {}
    if stored.get("fixture_digest_verdict") != "FAIL":
        return fail("artifact-digest-verdict-drift")
    if stored.get("fixture_full_verdict") != "PASS":
        return fail("artifact-full-verdict-drift")
    if stored.get("fixture_digest_coverage") != digest["coverage"]["coverage_fraction"]:
        return fail("artifact-digest-coverage-drift")
    if stored.get("fixture_full_coverage") != full["coverage"]["coverage_fraction"]:
        return fail("artifact-full-coverage-drift")
    live_art = {r["path"]: r for r in (doc.get("live_dossiers") or []) if isinstance(r, dict)}
    for row in live:
        art_row = live_art.get(row["path"])
        if art_row is None:
            return fail(f"artifact-missing-live-row {row['path']}")
        if bool(art_row.get("present")) != bool(row["present"]):
            return fail(f"artifact-present-drift {row['path']}")
        if row["present"]:
            art_both = art_row.get("both_states") or {}
            if art_both.get("digest_coverage_fraction") != row["both_states"]["digest_coverage_fraction"]:
                return fail(f"artifact-live-digest-drift {row['path']}")
            if art_both.get("full_coverage_fraction") != row["both_states"]["full_coverage_fraction"]:
                return fail(f"artifact-live-full-drift {row['path']}")
    print("both_states=True attestation_ignored=True live_ok=True")
    print("SUCCESS:ARC-0068-probe1 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
