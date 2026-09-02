"""Hand-built claim fixtures for TST-0022 named probes.

Live claim_gate.py names the second probe `verify_probe` (not verifier_probe)
and fingerprints the four axes in AXES.
"""
from __future__ import annotations

AXES = ("tool", "engine", "shell", "field")

SOURCE = {
    "tool": "python3",
    "engine": "cpython",
    "shell": "bash",
    "field": "sha256",
}
VERIFIER = {
    "tool": "python3",
    "engine": "cpython",
    "shell": "pwsh",
    "field": "sha256",
}


def hole_compare_first(source: object, verifier: object) -> bool:
    """Historical hole: compare fingerprints first.

    An absent/non-dict source normalises to four empty strings, which any
    non-empty verifier trivially differs from, so the pair is certified
    independent. The fixed gate must refuse this *before* comparing.
    """
    def key(probe: object) -> tuple[str, ...]:
        fields = probe if isinstance(probe, dict) else {}
        return tuple(" ".join(str(fields.get(axis) or "").lower().split()) for axis in AXES)

    return key(source) != key(verifier)


def _base(**extra):
    row = {
        "id": "FX-0",
        "text": "Fixture claim for the source-probe independence gate.",
        "verdict": "CONFIRMED",
        "scope": "command-center/p2-wave/probes/TST-0022",
        "band": "almost certain",
        "evidence": ["command-center/WORK-UNIT-CATALOG.json:76924"],
    }
    row.update(extra)
    return row


def absent_source_doc():
    return {
        "subject": "TST-0022 absent-source negative control",
        "claims": [
            _base(
                id="FX-ABSENT-SOURCE",
                text="CONFIRMED with a valid verifier and no source_probe.",
                verify_probe=dict(VERIFIER),
            )
        ],
    }


def same_probe_doc():
    return {
        "subject": "TST-0022 same-probe-rerun negative control",
        "claims": [
            _base(
                id="FX-SAME-PROBE",
                text="CONFIRMED that re-runs the producing probe as verifier.",
                source_probe=dict(SOURCE),
                verify_probe=dict(SOURCE),
            )
        ],
    }


def independent_doc():
    return {
        "subject": "TST-0022 independent-pair positive control",
        "claims": [
            _base(
                id="FX-INDEPENDENT",
                text="CONFIRMED with bash source and pwsh verifier (shell axis).",
                source_probe=dict(SOURCE),
                verify_probe=dict(VERIFIER),
            )
        ],
    }


def planted_registry():
    """Both-states census fixture: one missing source, one complete, one NOT-CHECKED."""
    return {
        "verdict_vocabulary": [
            "CONFIRMED",
            "REFUTED",
            "PARTIAL",
            "NOT-CHECKED",
            "BLOCKED",
        ],
        "claims": [
            _base(
                id="PLANT-MISSING",
                text="Planted CONFIRMED with no source_probe.",
                verify_probe=dict(VERIFIER),
            ),
            _base(
                id="PLANT-COMPLETE",
                text="Planted CONFIRMED with independent probes.",
                source_probe=dict(SOURCE),
                verify_probe=dict(VERIFIER),
            ),
            {
                "id": "PLANT-NOT-CHECKED",
                "text": "Not settled; must not count in the CONFIRMED missing tally.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "declare source_probe then re-run census",
            },
        ],
    }
