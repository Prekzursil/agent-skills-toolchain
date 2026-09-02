"""Deterministic two-cluster roster for IMP-0331 probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.topology.committee import Participant  # noqa: E402

QUESTION = "Adopt policy X: expand enforcement authority?"
CAUCUS_SIZE = 4
N_STANDING = 3
AFFINITY_SEED_ID = "hawk-5"
RANDOM_SEED = 20260824
BASELINE_SEED = 7


def two_cluster_roster() -> tuple[Participant, ...]:
    """Six hawks near +0.8 and six doves near -0.8.

    Affinity around hawk-5 therefore stays inside one cluster. A mixed
    random draw of four spans both clusters and has large spread.
    """
    hawks = tuple(
        Participant(
            id=f"hawk-{i}",
            position=round(0.70 + i * 0.03, 2),
            tags=("hawk",),
        )
        for i in range(6)
    )
    doves = tuple(
        Participant(
            id=f"dove-{i}",
            position=round(-0.70 - i * 0.03, 2),
            tags=("dove",),
        )
        for i in range(6)
    )
    return hawks + doves
