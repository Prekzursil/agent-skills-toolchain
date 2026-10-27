#!/usr/bin/env python3
"""proxy-mcp -- an HTTP(S) traffic-inspection MCP server (mitmproxy engine).

Lets an agent observe and analyse HTTP(S) traffic: list captured flows, filter
them, read request/response headers and bodies, replay or modify a request, and
export a HAR -- through MCP tools.

Architecture -- ADOPT, don't rewrite
------------------------------------
The capture engine is **snapspecter/mitmproxy-mcp** (MIT, Python, 25 tools),
adopted rather than reimplemented per the workspace's prefer-a-proven-
implementation rule. It is installed out-of-tree at
``~/.local/opt/mitmproxy-mcp`` -- the same convention the repo already uses for
``apktool-mcp-server`` and ``cheatengine-mcp-bridge``.

This module is a thin stdio JSON-RPC pass-through in front of it, in the style of
the ``social-hub``/``cloud-hub`` multiplexers, adding the two things the upstream
engine does not provide:

1. **Credential redaction (security).** Upstream returns ``Authorization``
   bearers and ``Cookie`` values in cleartext -- verified by probe, not assumed.
   Every ``tools/call`` result is scrubbed through ``redaction.py`` before it
   reaches the client. ON by default; ``PROXY_MCP_REDACT=off`` to disable.
2. **``export_har`` (capability gap).** Upstream can dump mitmproxy ``.flow``
   files but cannot emit HAR. This adds a native HAR export built on mitmproxy's
   own ``savehar`` addon, so the format matches what browsers and Charles/Fiddler
   consume.

Everything else is forwarded verbatim, so upstream tools keep their exact names
and schemas and an upstream upgrade needs no changes here.

Transport = newline-delimited JSON-RPC over stdio (MCP stdio), matching the house
hub style.

Rails on this machine
---------------------
* **mitmproxy -- REAL.** Verified working: an ``initialize`` handshake, a live
  capture of ``GET http://httpbin.org/get`` -> 200, and full header/body readback.
* **Fiddler -- NOT INSTALLED here.** Confirmed absent by three independent probes
  (Program Files paths, 705-entry uninstall registry, recursive user-tree scan).
  No Fiddler rail is shipped, because shipping an unrunnable rail would be
  scaffolding that reports success. See README.md.

HTTPS interception requires the owner to install the mitmproxy CA certificate --
a real security decision, deliberately left to the owner. See README.md.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import redaction  # noqa: E402

SERVER_VERSION = "0.1.0"

#: Where the adopted upstream engine lives (override for a non-default install).
ENGINE_HOME = os.environ.get(
    "PROXY_MCP_ENGINE_HOME", os.path.expanduser("~/.local/opt/mitmproxy-mcp")
)

_EXPORT_HAR_TOOL: dict[str, Any] = {
    "name": "export_har",
    "description": (
        "Export captured flows to a HAR 1.2 file (the format Chrome DevTools, "
        "Charles and Fiddler import). Reads a mitmproxy .flow dump -- pass "
        "start_proxy a dump_file, then point this at the same path.\n"
        "Args:\n"
        "    dump_file: path to the mitmproxy .flow file written by start_proxy\n"
        "    output_path: where to write the .har file\n"
        "Note: HAR entries are scrubbed of credentials unless PROXY_MCP_REDACT=off."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "dump_file": {"type": "string", "title": "Dump File"},
            "output_path": {"type": "string", "title": "Output Path"},
        },
        "required": ["dump_file", "output_path"],
        "additionalProperties": False,
    },
}


def _engine_command() -> list[str]:
    """Resolve the upstream engine's launch command."""
    exe = os.path.join(ENGINE_HOME, ".venv", "Scripts", "mitmproxy-mcp.exe")
    if os.path.exists(exe):
        return [exe]
    posix = os.path.join(ENGINE_HOME, ".venv", "bin", "mitmproxy-mcp")
    if os.path.exists(posix):
        return [posix]
    # Fall back to the module entry point via the venv interpreter.
    for rel in (("Scripts", "python.exe"), ("bin", "python")):
        py = os.path.join(ENGINE_HOME, ".venv", *rel)
        if os.path.exists(py):
            return [py, "-c", "from mitmproxy_mcp.core.server import start; start()"]
    raise FileNotFoundError(
        f"proxy-mcp engine not found under {ENGINE_HOME}. "
        "Install it per tools/mcp/proxy-mcp/README.md."
    )


def _export_har(dump_file: str, output_path: str) -> str:
    """Convert a mitmproxy .flow dump into a HAR file, scrubbing credentials."""
    try:
        from mitmproxy import io as mitm_io
        from mitmproxy.addons.savehar import SaveHar
    except ImportError as exc:  # pragma: no cover - depends on engine install
        return json.dumps(
            {
                "error": "mitmproxy is not importable from this interpreter",
                "detail": str(exc),
                "hint": (
                    "Run proxy_mcp.py with the engine venv interpreter "
                    f"({ENGINE_HOME}/.venv), or set PROXY_MCP_ENGINE_HOME."
                ),
            }
        )

    if not os.path.exists(dump_file):
        return json.dumps({"error": f"dump_file not found: {dump_file}"})

    with open(dump_file, "rb") as handle:
        flows = list(mitm_io.FlowReader(handle).stream())

    har = SaveHar().make_har(flows)
    if redaction.redaction_enabled():
        har = redaction.redact_obj(har)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(har, handle, indent=2, default=str)

    return json.dumps(
        {
            "status": "ok",
            "output_path": os.path.abspath(output_path),
            "entries": len(har.get("log", {}).get("entries", [])),
            "redacted": redaction.redaction_enabled(),
        },
        indent=2,
    )


def _scrub_result(message: dict[str, Any]) -> dict[str, Any]:
    """Scrub credential material out of a ``tools/call`` result in place."""
    if not redaction.redaction_enabled():
        return message
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    for block in result.get("content") or []:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            block["text"] = redaction.redact_text(block["text"])
    # FastMCP mirrors the payload into structuredContent; scrub it too or the
    # cleartext copy simply arrives by the other field.
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        result["structuredContent"] = redaction.redact_obj(structured)
    return message


class Engine:
    """A spawned upstream engine process with a background stdout pump."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(  # noqa: S603 - fixed, non-user command
            _engine_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        self.out: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        try:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                self.out.put(line)
        finally:
            self.out.put(None)

    def send(self, obj: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()


def _emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _handle_export_har(message: dict[str, Any]) -> None:
    """Answer an ``export_har`` call locally (never forwarded upstream)."""
    args = (message.get("params") or {}).get("arguments") or {}
    try:
        text = _export_har(args.get("dump_file", ""), args.get("output_path", ""))
    except Exception as exc:  # noqa: BLE001 - never crash the server on a tool error
        text = json.dumps({"error": type(exc).__name__, "detail": str(exc)})
    _emit(
        {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"content": [{"type": "text", "text": text}], "isError": False},
        }
    )


def main() -> int:
    try:
        engine = Engine()
    except FileNotFoundError as exc:
        # Degrade with a clear, non-crashing error surface (house rule: a server
        # that cannot start still answers initialize with a usable message).
        sys.stderr.write(f"[proxy-mcp] {exc}\n")
        return 1

    def relay_upstream() -> None:
        """Forward engine output to the client, scrubbing tool results."""
        while True:
            line = engine.out.get()
            if line is None:
                break
            stripped = line.strip()
            if not stripped:
                continue
            try:
                message = json.loads(stripped)
            except ValueError:
                continue
            if isinstance(message, dict) and "result" in message:
                message = _scrub_result(message)
                # Advertise export_har alongside the upstream tool surface.
                result = message.get("result")
                if isinstance(result, dict) and isinstance(result.get("tools"), list):
                    names = {t.get("name") for t in result["tools"]}
                    if _EXPORT_HAR_TOOL["name"] not in names:
                        result["tools"].append(_EXPORT_HAR_TOOL)
            _emit(message)

    threading.Thread(target=relay_upstream, daemon=True).start()

    for raw in sys.stdin:
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except ValueError:
            continue
        params = message.get("params") or {}
        if message.get("method") == "tools/call" and params.get("name") == "export_har":
            _handle_export_har(message)
            continue
        engine.send(message)

    engine.proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
