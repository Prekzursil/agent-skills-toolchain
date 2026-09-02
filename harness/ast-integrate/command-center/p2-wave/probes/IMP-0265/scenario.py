"""IMP-0265 probe fixtures: 12-seat roster, duplicate pair, diverse pair."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY_PATH = REPO / "tools" / "council" / "participants" / "registry.py"
RECEIPT_PATH = REPO / "command-center" / "receipts" / "IMP-0265.json"


def load_registry():
    name = "imp0265_council_registry"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REGISTRY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {REGISTRY_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _seat(
    participant_id: str,
    display_name: str,
    vendor: str,
    model: str,
    prompt: str,
    expertise: list[str],
    pointer: str | None,
    tools: list[str],
) -> dict[str, Any]:
    return {
        "participant_id": participant_id,
        "display_name": display_name,
        "vendor": vendor,
        "model": model,
        "prompt": prompt,
        "declared_expertise": expertise,
        "calibration_history_pointer": pointer,
        "tool_grants": tools,
    }


# Distinct voices. Seat 10 clones seat 0's vendor+model+prompt+tools.
_UNIQUE: list[dict[str, Any]] = [
    _seat(
        "seat-00-architect",
        "Architect",
        "anthropic",
        "claude-opus-4",
        "You are the systems architect. Prefer explicit contracts over slogans.",
        ["architecture", "contracts"],
        "calibration://history/architect",
        ["Read", "Grep", "Glob"],
    ),
    _seat(
        "seat-01-skeptic",
        "Skeptic",
        "openai",
        "gpt-4o",
        "You attack hidden assumptions. Demand a failing fixture before a claim.",
        ["adversarial-review"],
        "calibration://history/skeptic",
        ["Read", "Bash"],
    ),
    _seat(
        "seat-02-pragmatist",
        "Pragmatist",
        "google",
        "gemini-1.5-pro",
        "You ship the smallest change that satisfies the measured contract.",
        ["delivery"],
        "calibration://history/pragmatist",
        ["Read", "Edit", "Write"],
    ),
    _seat(
        "seat-03-critic",
        "Critic",
        "anthropic",
        "claude-sonnet-4",
        "You score residual risk. Silence is not a pass.",
        ["risk"],
        "calibration://history/critic",
        ["Read"],
    ),
    _seat(
        "seat-04-legal",
        "Legal",
        "openai",
        "gpt-4o",
        "You are counsel. Flag license, privacy, and authority gaps.",
        ["legal"],
        "calibration://history/legal",
        ["Read", "Grep"],
    ),
    _seat(
        "seat-05-security",
        "Security",
        "anthropic",
        "claude-opus-4",
        "You are the security reviewer. Secrets, authz, and injection first.",
        ["security"],
        "calibration://history/security",
        ["Read", "Grep", "Glob"],
    ),
    _seat(
        "seat-06-data",
        "Data",
        "google",
        "gemini-1.5-flash",
        "You own schema and measurement hygiene. Numbers need a denominator.",
        ["data", "measurement"],
        "calibration://history/data",
        ["Read", "Bash"],
    ),
    _seat(
        "seat-07-ops",
        "Ops",
        "anthropic",
        "claude-haiku-4",
        "You own runtime cost, timeouts, and rollback.",
        ["operations"],
        "calibration://history/ops",
        ["Bash"],
    ),
    _seat(
        "seat-08-product",
        "Product",
        "openai",
        "o1",
        "You own user-visible outcomes and refusal to gold-plate.",
        ["product"],
        "calibration://history/product",
        ["Read", "Write"],
    ),
    _seat(
        "seat-09-research",
        "Research",
        "deepseek",
        "deepseek-v3",
        "You cite prior art and refuse unsourced novelty claims.",
        ["research"],
        "calibration://history/research",
        ["Read", "Grep"],
    ),
    _seat(
        "seat-11-quant",
        "Quant",
        "xai",
        "grok-4",
        "You recompute every reported figure from the fixture, not the narrative.",
        ["quant"],
        "calibration://history/quant",
        ["Read", "Bash"],
    ),
]


CLONE_OF = "seat-00-architect"
CLONE_ID = "seat-10-architect-clone"


def clone_fields() -> dict[str, Any]:
    src = next(s for s in _UNIQUE if s["participant_id"] == CLONE_OF)
    return _seat(
        CLONE_ID,
        "Architect-Alt",
        src["vendor"],
        src["model"],
        src["prompt"],
        ["security", "claimed-not-demonstrated"],
        "calibration://history/architect-alt",
        list(src["tool_grants"]),
    )


def twelve_seat_specs() -> list[dict[str, Any]]:
    """12-seat roster: 11 unique configs plus one planted duplicate of seat-00."""
    specs = list(_UNIQUE)
    specs.insert(10, clone_fields())
    if len(specs) != 12:
        raise RuntimeError(f"twelve-seat fixture size {len(specs)}")
    return specs


def fill(reg, specs: list[dict[str, Any]]):
    for spec in specs:
        reg.register(**spec)
    return reg


def twelve_seat_registry():
    R = load_registry()
    return fill(R.ParticipantRegistry(), twelve_seat_specs())


def duplicate_pair_registry():
    """Negative-control roster: the same configuration seated twice."""
    R = load_registry()
    src = next(s for s in _UNIQUE if s["participant_id"] == CLONE_OF)
    reg = R.ParticipantRegistry()
    reg.register(**src)
    clone = clone_fields()
    clone["tool_grants"] = list(reversed(list(src["tool_grants"]))) + [src["tool_grants"][0]]
    reg.register(**clone)
    return reg


def diverse_pair_registry():
    """Clean control: two different prompts/tools must not collide."""
    R = load_registry()
    reg = R.ParticipantRegistry()
    fill(reg, _UNIQUE[:2])
    return reg


def same_model_different_prompt_registry():
    """Architect vs Security share vendor+model but not prompt — two voices."""
    R = load_registry()
    reg = R.ParticipantRegistry()
    a = next(s for s in _UNIQUE if s["participant_id"] == "seat-00-architect")
    b = next(s for s in _UNIQUE if s["participant_id"] == "seat-05-security")
    fill(reg, [a, b])
    return reg
