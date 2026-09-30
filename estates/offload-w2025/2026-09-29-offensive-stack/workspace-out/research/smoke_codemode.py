"""Smoke test: code-mode sandbox via run_in_codemode (subprocess + Job Object on win32)."""
import asyncio
from nodriver_proxy_mcp.codemode.tools import run_in_codemode

script = """
import sys, platform
print("python:", sys.version.split()[0], "| platform:", platform.platform())
# resource-limit sanity: this side of the sandbox is visible
print("hello from sandbox")
"""

out = asyncio.run(run_in_codemode(script, timeout=60))
print(out)
