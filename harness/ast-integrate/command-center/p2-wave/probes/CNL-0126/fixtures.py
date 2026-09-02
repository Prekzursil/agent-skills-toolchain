"""Closed capability fixtures for CNL-0126. Data only; no adapter calls."""
from __future__ import annotations

PARTIAL_WORK = (
    b"CNL-0126 partial council transcript\n"
    b"round=1 seat=anthropic:opus vote=continue\n"
    b"constraint: do not pretend full interchangeability; degrade loudly\n"
)

SPEC = {
    "id": "councilspec.fixture.cnl-0126",
    "assumed": {
        "tool_access": True,
        "context_length": 200000,
        "structured_output": True,
    },
}

CAPABLE = {
    "vendor_id": "anthropic",
    "model_id": "opus",
    "advertised": {
        "tool_access": True,
        "context_length": 200000,
        "structured_output": True,
    },
}

GAP_TOOL = {
    "vendor_id": "openai",
    "model_id": "codex-no-tools",
    "advertised": {
        "tool_access": False,
        "context_length": 200000,
        "structured_output": True,
    },
}

GAP_CONTEXT = {
    "vendor_id": "openai",
    "model_id": "small-window",
    "advertised": {
        "tool_access": True,
        "context_length": 8000,
        "structured_output": True,
    },
}

GAP_STRUCTURED = {
    "vendor_id": "openai",
    "model_id": "prose-only",
    "advertised": {
        "tool_access": True,
        "context_length": 200000,
        "structured_output": False,
    },
}

SUBSTITUTE = {
    "vendor_id": "anthropic",
    "model_id": "sonnet-as-opus",
    "advertised": {
        "tool_access": True,
        "context_length": 200000,
        "structured_output": True,
    },
}

GAP_SEATS = {
    "tool_access": GAP_TOOL,
    "context_length": GAP_CONTEXT,
    "structured_output": GAP_STRUCTURED,
}


def expected_gaps(assumed: dict, advertised: dict) -> list[str]:
    """Independent gap algebra. Probe 2 uses this; it does not call adapter.compute_gaps."""
    gaps: list[str] = []
    if assumed.get("tool_access") and not advertised.get("tool_access"):
        gaps.append("tool_access")
    if int(advertised.get("context_length") or 0) < int(assumed.get("context_length") or 0):
        gaps.append("context_length")
    if assumed.get("structured_output") and not advertised.get("structured_output"):
        gaps.append("structured_output")
    return gaps
