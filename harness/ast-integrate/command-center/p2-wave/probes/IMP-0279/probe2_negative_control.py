#!/usr/bin/env python3
"""Probe 2: negative control — a genuinely diverse roster must report >1.

Starts from the catalog tests, not an author summary. If the detector always
emits 1 it is constant-firing; if it always emits seat-count it would have
already failed probe 1. Also checks mixed 6+2 -> 2, and that a one-field
delta (tools OR prompt OR context) actually splits a voice.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario  # noqa: E402

REPO = scenario.REPO
DUPES_PY = scenario.DUPES_PATH


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0279-probe2 {msg}")
    return 1


def main() -> int:
    if not DUPES_PY.is_file():
        return fail("module-absent")
    scenario.write_fixture_files()
    dupes = scenario.load_dupes()
    diverse = scenario.roster_diverse()
    mixed = scenario.roster_mixed()
    d_audit = dupes.audit_roster(diverse["seats"], diverse["outputs"])
    m_audit = dupes.audit_roster(mixed["seats"], mixed["outputs"])

    # One-field splits: each named fingerprint field must be able to mint a voice.
    base = scenario.clone_seat(1)
    splits = {}
    mutants = {
        "vendor": {**base, "seat_id": "m-vendor", "vendor": "openai"},
        "model": {**base, "seat_id": "m-model", "model": "haiku"},
        "system_prompt": {
            **base,
            "seat_id": "m-prompt",
            "system_prompt": base["system_prompt"] + "\nAlso refuse cost-only reasoning.",
        },
        "tools": {**base, "seat_id": "m-tools", "tools": ["web"]},
        "context": {**base, "seat_id": "m-context", "context": "a different brief"},
    }
    for field, mutant in mutants.items():
        pair = dupes.audit_roster([base, mutant])
        splits[field] = pair["effective_independence_count"]
        if pair["effective_independence_count"] != 2:
            return fail(f"field {field} did not split a voice: {pair['effective_independence_count']}")

    # Constant-1 detector would pass probe 1 and fail here.
    if d_audit["effective_independence_count"] <= 1:
        return fail(
            f"constant-firing detector: diverse roster independence="
            f"{d_audit['effective_independence_count']}"
        )
    if d_audit["effective_independence_count"] != 8:
        return fail(
            f"diverse independence={d_audit['effective_independence_count']} expected 8"
        )
    if d_audit["duplicate_cluster_count"] != 0:
        return fail(f"diverse roster flagged clones: {d_audit['flagged']}")
    if d_audit["similarity"]["mean_pairwise_jaccard"] >= dupes.LOW_SIMILARITY:
        return fail(
            f"diverse outputs collapsed mean="
            f"{d_audit['similarity']['mean_pairwise_jaccard']}"
        )
    if d_audit["corroboration"]["verdict"] != "CORROBORATED":
        return fail(f"diverse corroboration {d_audit['corroboration']}")

    if m_audit["effective_independence_count"] != 2:
        return fail(f"mixed 6+2 independence={m_audit['effective_independence_count']}")
    sizes = sorted(c["size"] for c in m_audit["flagged"])
    if sizes != [2, 6]:
        return fail(f"mixed flagged sizes {sizes}")
    if m_audit["corroboration"]["verdict"] != "CORROBORATED":
        return fail(f"mixed corroboration {m_audit['corroboration']}")

    # Adversarial: a naive seat-count "detector" would report 8 on eight copies.
    # The live module must not. Re-read eight copies here so this probe does not
    # trust probe 1's summary.
    cloned = scenario.roster_eight_copies()
    c_audit = dupes.audit_roster(cloned["seats"], cloned["outputs"])
    if c_audit["effective_independence_count"] == c_audit["seat_count"]:
        return fail("detector equals seat_count; labels were treated as voices")
    if c_audit["effective_independence_count"] != 1:
        return fail(f"re-measure eight copies independence={c_audit['effective_independence_count']}")

    # Adversarial: copying a seat dict and renaming it must not split.
    twin = copy.deepcopy(base)
    twin["seat_id"] = "renamed-twin"
    twin["name"] = "Totally Different Person"
    twin["role"] = "chief-skeptic"
    rename = dupes.audit_roster([base, twin])
    if rename["effective_independence_count"] != 1:
        return fail("renamed clone minted a second voice")

    import subprocess

    fixture = HERE / "fixtures" / "roster_diverse.json"
    proc = subprocess.run(
        [sys.executable, "-B", str(DUPES_PY), "--roster", str(fixture)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return fail(f"cli-exit {proc.returncode} {proc.stderr[-400:]}")
    cli = json.loads(proc.stdout)
    if int(cli.get("effective_independence_count") or 0) <= 1:
        return fail(f"cli diverse independence {cli.get('effective_independence_count')}")

    summary = {
        "diverse_independence": d_audit["effective_independence_count"],
        "diverse_mean_jaccard": d_audit["similarity"]["mean_pairwise_jaccard"],
        "mixed_independence": m_audit["effective_independence_count"],
        "mixed_within": m_audit["similarity"]["within_cluster_mean"],
        "mixed_across": m_audit["similarity"]["across_cluster_mean"],
        "one_field_splits": splits,
        "renamed_clone_independence": rename["effective_independence_count"],
        "cli_diverse_independence": cli.get("effective_independence_count"),
        "constant_fire_rejected": d_audit["effective_independence_count"] > 1,
        "seat_count_detector_rejected": c_audit["effective_independence_count"] != 8,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"diverse independence={d_audit['effective_independence_count']} "
        f"mean_jaccard={d_audit['similarity']['mean_pairwise_jaccard']} "
        f"mixed={m_audit['effective_independence_count']} "
        f"splits={splits}"
    )
    print("SUCCESS:IMP-0279-probe2 diverse roster reports >1; detector is not constant-firing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
