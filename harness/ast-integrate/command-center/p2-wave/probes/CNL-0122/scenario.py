"""Scripted four-seat council fixture for CNL-0122 pause/resume/replay."""
from __future__ import annotations

QUESTION = (
    "Does a council paused at an arbitrary round resume to a byte-identical "
    "transcript - and does perturbing exactly one captured seed change it, "
    "proving the replay is real rather than cached?"
)

ROSTER = ("architect", "skeptic", "pragmatist", "critic")
MAX_ROUNDS = 4
TOOLS = ("read_spec", "write_ballot")

# Per-seat, per-round base copy. Bytes still mix with sampling_seed in harness
# so a frozen script table cannot pass the perturbation control.
SCRIPTS = {
    "architect": (
        "Propose a typed snapshot covering seeds, roster order, clock, and log.",
        "Keep pause as a snapshot, not a deliberation event.",
        "Resume must continue the next round without rewriting prior seats.",
        "Stop after the declared round budget; do not invent extra speech.",
    ),
    "skeptic": (
        "Identical-seed replay can be a cached blob. Demand a seed kill.",
        "Wall-clock and PID must not leak into the transcript.",
        "A pause marker inside the transcript would make resume diverge.",
        "If any captured seed is decorative, the perturbation table exposes it.",
    ),
    "pragmatist": (
        "Serialize four seeds: sampling, tool-order, wall-clock, recruitment.",
        "Derive tool-call order from tool_order_seed, never filesystem order.",
        "Synthetic clock advances from wall_clock_seed only.",
        "Owner pause without mutation is resume; question change is restart.",
    ),
    "critic": (
        "Count events. A hash of a summary sentence is not a transcript.",
        "Recruitment seed must permute speaking order or it is not load-bearing.",
        "Two tools per seat so a swapped order is visible in the log.",
        "Negative control: a runtime that ignores the new seed must go red.",
    ),
}

DEFAULT_SEEDS = {
    "sampling_seed": 0xC1225A01,
    "tool_order_seed": 0xC1227001,
    "wall_clock_seed": 0xC122C10C,
    "recruitment_seed": 0xC1224E57,
}

PAUSE_ROUNDS = (1, 2, 3)
SEED_NAMES = (
    "sampling_seed",
    "tool_order_seed",
    "wall_clock_seed",
    "recruitment_seed",
)

SCENARIO_ID = "cnl-0122-pause-resume-replay"
SCENARIO_TITLE = "Pause at rounds 1-3, resume, replay, then kill one seed"
