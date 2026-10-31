"""TST-0284 probe fixtures.

well_formed: the macOS-runner record shape the receipt records as accepted.
The three program records are reconstructed VERBATIM to the receipts
harvest rows (their source files are absent on this host); each must score
accepted=False with the receipt exact missing-field lists."""
from __future__ import annotations

WELL_FORMED = {
    "id": "well-formed-macos-runner",
    "claim_shown_unobtainable": (
        "A sub-100ms first-audio latency for the RVC voice changer on the "
        "RTX 4050 (4GB) hardware is unobtainable"
    ),
    "search_space_covered": (
        "RVC-13.x inference configs x chunk sizes 10-512ms x 3 GPU pipelines "
        "(default / no-compile / direct-ML) on the RTX 4050 4GB host"
    ),
    "methods_attempted": [
        "chunked streaming inference sweep (chunk 10-512ms) -> RTF 0.80 at 100ms chunk",
        "TorchScript compile + CUDA graphs -> no first-token gain at this chunk floor",
        "direct-ML / ONNX export -> higher first-audio latency than the torch lane",
    ],
    "resource_limit_reached": (
        "GPU memory ceiling on the 4GB 4050: sub-100ms chunks OOM or exceed "
        "the real-time factor budget; effort capped at the 40-sweep budget"
    ),
    "refuting_observation": (
        "A sub-100ms first-audio readout from the packaged RVC binary on the "
        "RTX 4050 host with the standard probe script and 16GB GPU memory headroom"
    ),
}

MISSING_REFUTING = {
    "id": "missing-refuting",
    "claim_shown_unobtainable": "claim A is unobtainable",
    "search_space_covered": "space S bounded",
    "methods_attempted": ["method m1 -> output o1"],
    "resource_limit_reached": "budget b reached",
}

EMPTY_REFUTING = dict(MISSING_REFUTING, id="empty-refuting", refuting_observation="   ")

CIRCULAR_UNOBSERVABLE = dict(
    MISSING_REFUTING,
    id="circular-unobservable",
    refuting_observation=
    "All future conceivable configurations of everything would need to be checked.",
)

OMNISCIENT = dict(
    MISSING_REFUTING,
    id="omniscient",
    refuting_observation="An infinite and omniscient sweep of everything.",
)

EQUALS_CLAIM = dict(
    MISSING_REFUTING,
    id="equals-claim",
    refuting_observation="This claim is impossible.",
)

# Receipt harvest rows: reconstructed verbatim to the recorded present/missing fields.
PROGRAM_RECORDS = [
    {
        "id": "IMP-0139-repair-loop-macos-proof",
        "claim_shown_unobtainable": "macOS repair-loop proof (recorded)",
        "search_space_covered": "recorded",
        "methods_attempted": [],
        "resource_limit_reached": "recorded",
        "refuting_observation": "recorded",
        "want_missing": ["methods_attempted"],
        "want_accepted": False,
    },
    {
        "id": "IMP-0311-hung-jury-binary-collapse",
        "claim_shown_unobtainable": "hung-jury binary collapse (recorded)",
        "search_space_covered": "recorded",
        "methods_attempted": [],
        "resource_limit_reached": "",
        "refuting_observation": "",
        "want_missing": ["methods_attempted", "resource_limit_reached", "refuting_observation"],
        "want_accepted": False,
    },
    {
        "id": "AUD-0084-claude-falsifier-unobtainable",
        "claim_shown_unobtainable": "claude falsifier unobtainable (recorded)",
        "search_space_covered": "",
        "methods_attempted": ["recorded"],
        "resource_limit_reached": "recorded",
        "refuting_observation": "recorded",
        "want_missing": ["search_space_covered"],
        "want_accepted": False,
    },
]
