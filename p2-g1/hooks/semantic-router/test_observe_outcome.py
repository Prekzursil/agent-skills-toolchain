#!/usr/bin/env python3
"""N07 regression: the router must credit VERIFIED outcomes, not bare invocations.

Measured at 27fb388 before ``observe.explicitly_failed`` existed: with
``mcp:claude_ai_Tavily`` pending as a suggestion, a PostToolUse envelope whose
``tool_response`` was ``{"isError": true, "content": [{"type": "text", "text": "not
connected"}]}`` still produced ``{"suggested": 1, "used": 1}``, and
``success.boost(key, succ, alpha=0.4)`` returned ``+0.133333`` -- so an endpoint that had
just answered "not connected" was ranked UP for the rest of the session.

Both directions are asserted, because a one-directional test cannot tell an outcome gate
from a blanket disarm (which would be the worse failure -- the success signal silently
stops learning anything):
  * an explicit failure earns NO credit and NO boost;
  * an ordinary success still earns credit and a positive boost;
  * a payload with no ``tool_response`` at all still credits (older hosts / the
    conservative default).

The durable store is redirected into ``tmp_path``, so this suite never writes
``hooks/semantic-router/success.json`` or the shared temp session dir.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MCP_TOOL = "mcp__claude_ai_Tavily__tavily_search"
KEY = "mcp:claude_ai_Tavily"
ALPHA = 0.4


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Wired:
    """``success`` + ``observe`` loaded with the durable store pointed at a tmp dir.

    ``observe.main`` does ``import success`` (its own ``sys.path.insert`` puts this dir
    first), so the redirected module is published under the bare name ``success`` for the
    duration of the test and the previous binding is restored afterwards -- six hook dirs
    share flat module names in this tree, so leaving one behind is a real hazard.
    """

    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self._prev = None
        self._had_prev = False

    def __enter__(self):
        self.success = _load("success", "success.py")
        self.success.SUCCESS_JSON = self.tmp_path / "success.json"
        session_dir = self.tmp_path / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)
        self.success._session_dir = lambda: session_dir
        self._had_prev = "success" in sys.modules
        self._prev = sys.modules.get("success")
        sys.modules["success"] = self.success
        self.observe = _load("observe_under_test", "observe.py")
        return self

    def __exit__(self, *_exc):
        if self._had_prev:
            sys.modules["success"] = self._prev
        else:
            sys.modules.pop("success", None)
        return False

    def feed(self, payload: dict) -> int:
        original = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            return self.observe.main()
        finally:
            sys.stdin = original

    def row(self, key: str) -> dict:
        return self.success.load_success().get(key) or {}


def _envelope(tool_response) -> dict:
    payload = {
        "session_id": "s1",
        "hook_event_name": "PostToolUse",
        "tool_name": MCP_TOOL,
        "tool_input": {"query": "anything"},
    }
    if tool_response is not None:
        payload["tool_response"] = tool_response
    return payload


def test_an_explicitly_failed_mcp_call_earns_no_routing_credit(tmp_path):
    with _Wired(tmp_path) as w:
        w.success.record_suggested([KEY], "s1")
        assert w.row(KEY) == {"suggested": 1, "used": 0}, (
            "fixture must start un-credited"
        )

        rc = w.feed(
            _envelope(
                {
                    "isError": True,
                    "content": [{"type": "text", "text": "not connected"}],
                }
            )
        )
        assert rc == 0, "the observer must stay fail-open / inject-nothing"
        assert w.row(KEY) == {"suggested": 1, "used": 0}, (
            "an isError=true response must not increment `used`"
        )
        assert w.success.boost(KEY, w.success.load_success(), ALPHA) == 0.0, (
            "a failed endpoint must receive no positive ranking nudge"
        )


def test_a_successful_mcp_call_is_still_credited(tmp_path):
    """Non-disarm control: without this the gate above could pass by crediting nothing."""
    with _Wired(tmp_path) as w:
        w.success.record_suggested([KEY], "s1")
        assert (
            w.feed(_envelope({"content": [{"type": "text", "text": "3 results"}]})) == 0
        )
        assert w.row(KEY) == {"suggested": 1, "used": 1}
        assert w.success.boost(KEY, w.success.load_success(), ALPHA) > 0.0


def test_a_response_free_envelope_keeps_the_previous_behaviour(tmp_path):
    """Conservative default: an absent/unknown outcome must not stop crediting."""
    with _Wired(tmp_path) as w:
        w.success.record_suggested([KEY], "s1")
        assert w.feed(_envelope(None)) == 0
        assert w.row(KEY) == {"suggested": 1, "used": 1}


def test_explicitly_failed_recognises_the_documented_markers(tmp_path):
    with _Wired(tmp_path) as w:
        failed = w.observe.explicitly_failed
        for shape in (
            {"isError": True},
            {"is_error": True},
            {"success": False},
            {"ok": False},
            {"interrupted": True},
            {"status": "failed"},
            {"error": "boom"},
            {"result": {"isError": True}},
        ):
            assert failed(shape) is True, shape
        for shape in (
            None,
            "",
            "3 results",
            [],
            {"content": []},
            {"isError": False},
            {"error": ""},
            {"error": False},
            {"status": "ok"},
        ):
            assert failed(shape) is False, shape


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
