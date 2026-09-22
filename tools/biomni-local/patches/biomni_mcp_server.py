#!/usr/bin/env python3
"""biomni_mcp_server — standalone MCP server exposing Biomni A1 as coarse tools.

WHY THIS EXISTS: gradio 5.50.0's native MCP mount (GRADIO_MCP_SERVER / launch(
mcp_server=True)) never engages on this build — no banner, no /gradio_api/mcp
transport, POST 404 (measured 2026-09-20). This server bypasses gradio entirely:
FastMCP (fastmcp 4.0.5, installed in biomni_e1) + the same A1 construction the
web app uses. Serves streamable HTTP on :7870.

Tools: biomni_task / biomni_tool_search / biomni_status (same contracts as the
gradio app attempted).
"""

import os
from pathlib import Path

# HOME-independent anchors: under the Claude Science MCP sandbox, HOME is remapped
# to a per-connector workspace, so derive paths from this file's location instead.
_BIOMNI_DIR = Path(__file__).resolve().parent          # .../Biomni
_HOME_ROOT = Path("/home/prekzursil")                  # canonical user root
os.chdir(_BIOMNI_DIR)
from dotenv import load_dotenv

load_dotenv()

from fastmcp import FastMCP

mcp = FastMCP("biomni")

_agent = None


def agent():
    global _agent
    if _agent is None:
        from biomni.agent import A1

        _agent = A1(
            path=str(_HOME_ROOT / "biomni-data"),
            llm=os.environ.get("BIOMNI_LLM", "glm-5.3-flash"),
            source="Custom",
            base_url=os.environ["BIOMNI_CUSTOM_BASE_URL"],
            api_key=os.environ["BIOMNI_CUSTOM_API_KEY"],
        )
        # Estate MCP injection (2026-09-22): WSL-native stdio servers only; the
        # config lives beside this file. Fail-open: injection must never break A1.
        try:
            _agent.add_mcp(str(_BIOMNI_DIR / "mcp_inject.yaml"))
        except Exception as _e:  # noqa: BLE001
            print(f"WARNING: MCP injection skipped: {type(_e).__name__}: {_e}")
    return _agent


def _last_answer(a) -> str:
    msgs = getattr(a, "main_history_copy", None) or []
    for m in reversed(msgs):
        if m.get("role") == "assistant" and m.get("content") not in (
            "Executor is working on it 👉",
            "",
        ):
            return str(m["content"])
    return "(no final answer produced)"


@mcp.tool
def biomni_task(prompt: str) -> str:
    """Run a full Biomni A1 research/analysis task; returns the final report.

    The agent plans, retrieves tools/data from the 14 GB lake, executes
    (Python/R/CLI). Long tasks can take minutes.
    """
    a = agent()
    out = a.go(prompt)
    # go() returns (history_list, solution_str); solution is authoritative.
    if isinstance(out, tuple) and len(out) >= 2 and isinstance(out[1], str) and out[1].strip():
        sol = out[1].strip()
        return sol.removeprefix("<solution>").removesuffix("</solution>").strip()
    return _last_answer(a)


@mcp.tool
def biomni_tool_search(query: str) -> str:
    """Search the Biomni tool catalogue by substring; up to 40 matches."""
    a = agent()
    try:
        tools = a.tool_registry.list_tools()
    except Exception as e:
        return f"tool registry error: {type(e).__name__}: {e}"
    q = query.lower()
    names = [t if isinstance(t, str) else str(t.get("name", t)) for t in tools]
    hits = [n for n in names if q in n.lower()] or names
    return "\n".join(f"{i + 1}. {h}" for i, h in enumerate(hits[:40])) or "(empty registry)"


@mcp.tool
def biomni_status() -> str:
    """Biomni stack status: lake path, tool count, model, endpoints."""
    a = agent()
    try:
        n = len(a.tool_registry.list_tools())
    except Exception:
        n = -1
    return (
        f"lake={_HOME_ROOT / 'biomni-data'} tools={n} "
        f"llm={os.environ.get('BIOMNI_LLM', 'glm-5.3-flash')} "
        f"web_ui=http://127.0.0.1:7860 mcp=http://127.0.0.1:7870/mcp"
    )


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=7870)
