#!/usr/bin/env python3
"""Shared IMP-0279 fixtures: cloned roster, diverse roster, mixed roster.

First-round texts are independently authored, not derived from fingerprints.
That keeps output-similarity corroboration from being circular.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DUPES_PATH = REPO / "tools" / "council" / "integrity" / "dupes.py"
FIXTURES = HERE / "fixtures"

CLONE_PROMPT = (
    "You are a cost-focused reviewer. Recommend the cheapest option that "
    "meets the stated functional bar. Do not invent requirements."
)
CLONE_CONTEXT = {
    "brief": "Choose between option-A (hosted, $12k/yr) and option-B (self-host, $4k/yr).",
    "constraints": ["must keep existing API", "no new vendors this quarter"],
}
CLONE_TOOLS = [{"name": "read"}, {"name": "grep"}, {"name": "glob"}]
CLONE_OUTPUT = (
    "I recommend option-B. It meets the existing-API constraint at one third "
    "the annual cost of option-A, and it introduces no new vendor. Residual: "
    "self-host ops load is not quantified in the brief."
)

DIVERSE: list[dict[str, Any]] = [
    {
        "seat_id": "legal",
        "vendor": "anthropic",
        "model": "opus",
        "system_prompt": "You are counsel. Flag license and liability risk first.",
        "tools": ["read", "cite"],
        "context": "contract clause 12 indemnification plus GPL-2.0 notice",
        "output": (
            "Do not ship until clause 12 indemnification is rewritten; the GPL-2.0 "
            "notice on the bundled parser creates copyleft exposure for customers."
        ),
    },
    {
        "seat_id": "perf",
        "vendor": "openai",
        "model": "gpt-4.1",
        "system_prompt": "You are a performance engineer. Argue from measured latency.",
        "tools": ["shell", "benchmark"],
        "context": "p99 latency budget 40ms; current mean 12ms on 8 vCPU",
        "output": (
            "The prototype already sits at 12ms mean; keep the in-process cache. "
            "A remote sidecar would blow the 40ms p99 budget on a cold miss."
        ),
    },
    {
        "seat_id": "ethics",
        "vendor": "google",
        "model": "gemini-pro",
        "system_prompt": "You are an ethics reviewer. Surface who is harmed if we are wrong.",
        "tools": ["web", "notes"],
        "context": "decision affects unpaid beta users in a medical-adjacent workflow",
        "output": (
            "Beta users in a medical-adjacent workflow cannot be the blast radius. "
            "Ship a kill switch and an explicit non-diagnostic disclaimer before any expand."
        ),
    },
    {
        "seat_id": "security",
        "vendor": "anthropic",
        "model": "sonnet",
        "system_prompt": "You are an application-security reviewer. Demand an exploit story.",
        "tools": [],
        "context": "SSRF via URL field on import; no allowlist today",
        "output": (
            "The import URL field is SSRF-complete. Refuse merge until an allowlist "
            "and network egress deny-by-default are in the same patch as the feature."
        ),
    },
    {
        "seat_id": "cost",
        "vendor": "mistral",
        "model": "large",
        "system_prompt": "You are a finance partner. Convert every design choice to run-rate.",
        "tools": ["python", "sheet"],
        "context": "run-rate cap $6k/month including inference",
        "output": (
            "At current token mix the hosted path crosses $6k/month by week six. "
            "Cap daily completions or move summarisation off the frontier model."
        ),
    },
    {
        "seat_id": "ux",
        "vendor": "meta",
        "model": "llama-3-70b",
        "system_prompt": "You are a product designer. Argue from the first-run empty state.",
        "tools": ["search", "figma"],
        "context": "first-run is a blank canvas; 70% of trials abandon before a second save",
        "output": (
            "The blank canvas is the abandonment. A five-item starter template on "
            "first run is the intervention; another settings panel will not move the 70%."
        ),
    },
    {
        "seat_id": "ops",
        "vendor": "cohere",
        "model": "command-r",
        "system_prompt": "You are an SRE. Refuse designs that cannot page a human.",
        "tools": ["logs", "pager"],
        "context": "on-call is two people covering four regions",
        "output": (
            "Two people cannot page four regions for a new stateful service. "
            "Keep it stateless or add an explicit follow-the-sun rotation before launch."
        ),
    },
    {
        "seat_id": "privacy",
        "vendor": "amazon",
        "model": "titan-text",
        "system_prompt": "You are a privacy engineer. Trace every identifier to a retention clock.",
        "tools": ["deploy", "dlp"],
        "context": "transcripts currently retained 400 days; policy max is 30",
        "output": (
            "Transcripts at 400 days violate the 30-day policy. Default retention "
            "must drop to 30 with a named legal-hold exception, or the panel is void."
        ),
    },
]


def load_dupes():
    spec = importlib.util.spec_from_file_location("council_integrity_dupes", DUPES_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {DUPES_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def clone_seat(index: int, *, tools: Any | None = None) -> dict[str, Any]:
    return {
        "seat_id": f"clone-{index:02d}",
        "name": f"Participant {index}",
        "role": f"reviewer-{index}",
        "vendor": "Anthropic",
        "model": "Opus",
        "system_prompt": CLONE_PROMPT,
        "tools": list(CLONE_TOOLS if tools is None else tools),
        "context": dict(CLONE_CONTEXT),
    }


def roster_eight_copies() -> dict[str, Any]:
    seats = [clone_seat(i) for i in range(1, 9)]
    # Tool-order permutation on even seats: still one voice if tools are a set.
    seats[1]["tools"] = list(reversed(CLONE_TOOLS))
    seats[3]["tools"] = [CLONE_TOOLS[2], CLONE_TOOLS[0], CLONE_TOOLS[1]]
    outputs = {seat["seat_id"]: CLONE_OUTPUT for seat in seats}
    return {
        "id": "eight-copies-one-config",
        "seats": seats,
        "outputs": outputs,
        "expected_independence": 1,
    }


def roster_diverse() -> dict[str, Any]:
    seats = []
    outputs = {}
    for row in DIVERSE:
        seat = {k: v for k, v in row.items() if k != "output"}
        seats.append(seat)
        outputs[seat["seat_id"]] = row["output"]
    return {
        "id": "eight-distinct-configs",
        "seats": seats,
        "outputs": outputs,
        "expected_independence": 8,
    }


def roster_mixed() -> dict[str, Any]:
    """Six clones of voice A plus two clones of voice B -> independence 2."""
    voice_a = [clone_seat(i) for i in range(1, 7)]
    voice_b = []
    for i in range(1, 3):
        voice_b.append(
            {
                "seat_id": f"alt-{i:02d}",
                "name": f"Alt {i}",
                "vendor": "openai",
                "model": "gpt-4.1",
                "system_prompt": DIVERSE[1]["system_prompt"],
                "tools": DIVERSE[1]["tools"],
                "context": DIVERSE[1]["context"],
            }
        )
    seats = voice_a + voice_b
    outputs = {s["seat_id"]: CLONE_OUTPUT for s in voice_a}
    outputs.update({s["seat_id"]: DIVERSE[1]["output"] for s in voice_b})
    return {
        "id": "six-plus-two",
        "seats": seats,
        "outputs": outputs,
        "expected_independence": 2,
    }


def roster_labels_only() -> dict[str, Any]:
    """Eight empty configs with distinct names: still one voice."""
    seats = [
        {
            "seat_id": f"label-{i}",
            "name": f"Voice {i}",
            "role": f"role-{i}",
            "vendor": "",
            "model": "",
            "system_prompt": "",
            "tools": [],
            "context": "",
        }
        for i in range(1, 9)
    ]
    outputs = {s["seat_id"]: "undifferentiated empty-config reply" for s in seats}
    return {
        "id": "labels-are-not-voices",
        "seats": seats,
        "outputs": outputs,
        "expected_independence": 1,
    }


def write_fixture_files() -> list[Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, doc in (
        ("roster_eight_copies.json", roster_eight_copies()),
        ("roster_diverse.json", roster_diverse()),
        ("roster_mixed.json", roster_mixed()),
        ("roster_labels_only.json", roster_labels_only()),
    ):
        path = FIXTURES / name
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write_fixture_files():
        print(path)
