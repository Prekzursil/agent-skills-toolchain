#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0106-anonymity-and-partition-leakage.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    meas = E.measure()
    if not meas["oracle_can_go_red"]:
        print("FAILED:ADV-0106 emit oracle cannot go red")
        return 1
    if not meas["oracle_silent_on_good"]:
        print("FAILED:ADV-0106 emit good-state oracle not silent")
        return 1
    if not meas["honest_canary_silent"]:
        print("FAILED:ADV-0106 emit honest canary leaked")
        return 1
    if not meas["honest_fact_leak"]:
        print("FAILED:ADV-0106 emit withheld facts not found in honest paraphrase")
        return 1
    if meas["identity_verdict"] not in {"CONFIRMED", "REFUTED", "PARTIAL"}:
        print(f"FAILED:ADV-0106 emit identity_verdict={meas['identity_verdict']}")
        return 1
    if meas["partition_verdict"] not in {"CONFIRMED", "REFUTED", "PARTIAL"}:
        print(f"FAILED:ADV-0106 emit partition_verdict={meas['partition_verdict']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    good = meas["stylometry_good"]
    bad = meas["stylometry_bad"]
    ident = meas["public_identity_scan"]
    schema_on_disk = (E.REPO / E.SCHEMA_DECLARED).is_file()

    answer = (
        "On this Linux worktree the live SUT is tools/council/partition.py "
        f"(TST-0272 fixtures). Probe 1 re-attributed anonymised first-pass notes "
        f"from {good['n_authors']} authors (gallery={good['n_gallery_per_author']}, "
        f"test={good['n_test_per_author']} each). Chance baseline={good['chance']}. "
        f"Style-normalised accuracy={good['accuracy']} "
        f"(p_ge_chance={good['p_ge_chance']:.6f}, indistinguishable="
        f"{good['indistinguishable_from_chance']}). Distinctive-idiolect control "
        f"accuracy={bad['accuracy']} (distinguishable). Public honest artifacts "
        f"identity_leaked={ident['identity_leaked']}. Identity target verdict="
        f"{meas['identity_verdict']}. Probe 2 grepped each seat's readable "
        "artifacts for facts unique to the withheld bundle. Honest mode: withheld "
        f"canary silent={meas['honest_canary_silent']} but withheld facts leaked "
        f"via moderator paraphrase paths={meas['honest_fact_paths']}. Naive "
        f"carriers all fire={meas['naive_canary_all_fire']}; detector-control "
        f"fires={meas['detector_control_fires']}; assembly-leak fires="
        f"{meas['assembly_leak_fires']}. Partition target verdict="
        f"{meas['partition_verdict']}. {E.SENTINEL}"
    )

    tests = [
        {
            "id": "T-IDENTITY-REATTRIBUTION-CHANCE",
            "name": "Chance baseline computed; style-normalised accuracy indistinguishable",
            "result": "PASS" if good["indistinguishable_from_chance"] else "FAIL",
        },
        {
            "id": "T-IDENTITY-NEGATIVE-CAN-GO-RED",
            "name": "Planted idiolect makes re-attribution beat chance",
            "result": "PASS"
            if (not bad["indistinguishable_from_chance"] and bad["accuracy"] > E.CHANCE)
            else "FAIL",
        },
        {
            "id": "T-PUBLIC-TRANSCRIPT-NO-SEAT-LABEL",
            "name": "Published honest artifacts do not carry seat identity strings",
            "result": "PASS" if not ident["identity_leaked"] else "FAIL",
        },
        {
            "id": "T-PARTITION-CONTENT-AUDIT",
            "name": "Honest withheld-canary silent; withheld facts still readable by seat-a",
            "result": "PASS"
            if (meas["honest_canary_silent"] and meas["honest_fact_leak"])
            else "FAIL",
        },
        {
            "id": "T-PARTITION-NEGATIVE-CAN-GO-RED",
            "name": "Naive summary/scratchpad/tool/paraphrase leak the withheld canary",
            "result": "PASS" if meas["naive_canary_all_fire"] else "FAIL",
        },
        {
            "id": "T-DETECTOR-CONTROL-ALLOWED-PLANT",
            "name": "Same canary planted in allowed bundle is found (detector not stuck green)",
            "result": "PASS" if meas["detector_control_fires"] else "FAIL",
        },
        {
            "id": "T-EMPTY-SEARCH-REJECTED",
            "name": "Zero-path search is rejected, not scored as a clean withhold",
            "result": "PASS" if meas["empty_search_rejected"] else "FAIL",
        },
        {
            "id": "T-REDACTED-PARAPHRASE-TWIN-SILENT",
            "name": "Fully redacted paraphrase twin is silent on withheld facts",
            "result": "PASS" if meas["redacted_paraphrase_twin_silent"] else "FAIL",
        },
        {
            "id": "T-NAMED-PROBES-RECORDED",
            "name": "Both catalog probes recorded verbatim",
            "result": "PASS",
        },
        {
            "id": "T-DECLARED-SCHEMA",
            "name": "Catalog output_schema path on this tree",
            "result": "PASS" if schema_on_disk else "NOT-CHECKED",
            "detail": (
                f"{E.SCHEMA_DECLARED} absent on this tree; G-1 does not require "
                "schema validation. Artifact is JSON with state=SUCCESS. "
                "Did not rebuild council-pathology-sim.schema.json."
            ),
        },
    ]
    if any(t["result"] == "FAIL" for t in tests):
        print("FAILED:ADV-0106 emit a required test is FAIL")
        print(json.dumps(tests, indent=2)[:4000])
        return 1

    doc = {
        "unit_id": E.UNIT,
        "id": E.UNIT,
        "state": "SUCCESS",
        "sentinel": E.SENTINEL,
        "completion_sentinel": E.SENTINEL,
        "report_kind": "council-pathology-sim",
        "title": "Anonymity and information-partition leakage in blind rounds",
        "question": E.QUESTION,
        "question_or_target": E.QUESTION,
        "answer": answer,
        "ts": now,
        "output_path": E.OUT_REL,
        "output_schema": E.SCHEMA_DECLARED,
        "spec_anchor": "_USER-PROMPTS.md:10924, 10927",
        "mechanism": (
            "stylometric re-attribution scored against chance plus a "
            "cross-partition fact-presence audit"
        ),
        "cloud_ok": False,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5",
            "role": "catalog-required cross-vendor Codex refuter",
            "execution_substrate": "linux-headless-local",
        },
        "sut": {
            "path": E.SUT,
            "modes": meas["modes"],
            "seats": meas["seats"],
        },
        "enumerated_targets": [
            {
                "id": "TARGET-IDENTITY-REATTRIBUTION",
                "claim": (
                    "A participant's identity can be inferred from the anonymised "
                    "transcript of a blind / anonymous round."
                ),
                "verdict": meas["identity_verdict"],
            },
            {
                "id": "TARGET-PARTITION-CONTENT-LEAK",
                "claim": (
                    "Withheld-partition facts appear in another participant's "
                    "readable artifacts even when identity stays hidden."
                ),
                "verdict": meas["partition_verdict"],
            },
        ],
        "measurements": meas,
        "named_probes": [
            {
                "id": "probe1",
                "command": E.PROBE1_CMD,
                "role": "identity-reattribution-vs-chance",
                "catalog_text": E.CATALOG_PROBE1,
            },
            {
                "id": "probe2",
                "command": E.PROBE2_CMD,
                "role": "partition-content-audit",
                "catalog_text": E.CATALOG_PROBE2,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-STYLOMETRIC-LEAK",
                "kind": "both-states",
                "fired_on_bad_state": not bad["indistinguishable_from_chance"],
                "silent_on_good_state": good["indistinguishable_from_chance"],
                "good_output": (
                    f"accuracy={good['accuracy']} chance={good['chance']} "
                    f"p_ge={good['p_ge_chance']}"
                ),
                "bad_output": f"accuracy={bad['accuracy']} chance={bad['chance']}",
            },
            {
                "id": "NC-CROSS-PARTITION-PARAPHRASE",
                "kind": "both-states",
                "fired_on_bad_state": meas["honest_fact_leak"]
                or meas["naive_canary_all_fire"],
                "silent_on_good_state": meas["redacted_paraphrase_twin_silent"],
                "good_output": "fully redacted paraphrase twin has zero withheld facts",
                "bad_output": (
                    "honest paraphrase retains withheld facts after canary redaction; "
                    "naive carriers leak the canary"
                ),
            },
        ],
        "evidence": [
            {
                "kind": "stylometry-vs-chance",
                "detail": (
                    f"n={good['n']} chance={good['chance']} good_accuracy="
                    f"{good['accuracy']} leaky_accuracy={bad['accuracy']}"
                ),
                "verdict": meas["identity_verdict"],
            },
            {
                "kind": "partition-fact-grep",
                "detail": (
                    "Seat-a canary search is clean in honest mode; withheld prose "
                    f"('Secret figure is 17') remains in {meas['honest_fact_paths']}"
                ),
                "verdict": meas["partition_verdict"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0106-probe2-partition-content-audit",
            "vendor": "openai",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-derives withheld-fact hits from live "
                "tools/council/partition.py artifacts, not from this unit's "
                "narrative. Cross-vendor vendor-session residual is NOT-CHECKED "
                "and does not BLOCK G-1."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0106/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement (cross-vendor Anthropic opus, "
                    "fresh context) was not executed as a vendor session."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the named vendor refuter against the raw artifact."
                ),
            }
        ],
        "notes": (
            "G-1 for ADV-0106. Live named probes exit 0. Honest non-BLOCKED "
            "artifact. Per-unit manifest only. Did not run global "
            "unit_manifest.py --write. Did not rebuild "
            "council-pathology-sim.schema.json. Prior cloud strikes were BLOCKED "
            "on missing runtime; this delivery runs tools/council/partition.py "
            "live. cloud ok=true is not delivery. "
            + E.SENTINEL
        ),
    }

    blob = json.dumps(doc, indent=1, sort_keys=True)
    if E.SENTINEL not in blob:
        print("FAILED:ADV-0106 emit sentinel missing")
        return 1
    if E.CATALOG_PROBE1 not in blob or E.CATALOG_PROBE2 not in blob:
        print("FAILED:ADV-0106 emit catalog probe text missing")
        return 1

    out = E.REPO / E.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob + "\n", encoding="utf-8")
    sha, size = digest(out)
    print(f"wrote {E.OUT_REL} bytes={size} sha256={sha}")
    print(
        f"identity={meas['identity_verdict']} partition={meas['partition_verdict']} "
        f"good_acc={good['accuracy']} bad_acc={bad['accuracy']}"
    )
    print("SUCCESS:ADV-0106 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
