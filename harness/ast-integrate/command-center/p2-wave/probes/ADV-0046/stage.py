#!/usr/bin/env python3
"""Research / cross-vendor stage under test plus origin classification.

Builds a mixed-origin prompt the way this program's routing stages do
(program text + optional owner artifacts + optional public knowledge)
and ships it across HTTP, MCP stdio, and CLI subprocess to local
observers. Also exercises the in-process vendor adapters, which do not
open those transports.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "CNF-0158"))

import intercept as I  # noqa: E402

CANARY_ATTACHED = "CANARY-ADV-0046-OWNER-PRIVATE-b7e19c4d2a60f831"
CANARY_UNATTACHED = "CANARY-ADV-0046-UNATTACHED-aa11bb22cc33dd44"
PUBLIC_MARK = "RFC2119-MUST-PUBLIC-ADV0046"
PROGRAM_MARK = "PROGRAM-GENERATED-ADV0046-PROMPT-TEMPLATE"
OWNER_WORDS_MARK = "project Nightjar stays unpublished"
OWNER_SOURCE_MARK = "def owner_private_helper_adv0046"
OWNER_HOME = "/home/adv0046-owner/private-notes/ledger.md"
WORKTREE = "/opt/p2/ast-integrate"

ORIGIN_MARKERS: dict[str, tuple[str, ...]] = {
    "public_knowledge": (PUBLIC_MARK,),
    "program_generated": (PROGRAM_MARK, "unit_manifest.py --write"),
    "owner_private": (
        CANARY_ATTACHED,
        OWNER_WORDS_MARK,
        OWNER_SOURCE_MARK,
        OWNER_HOME,
        WORKTREE,
    ),
}


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def build_prompt(*, include_private: bool) -> str:
    parts = [
        load_fixture("program_generated.txt").rstrip(),
        "",
        "Worktree path (owner environment): " + WORKTREE,
        "",
        "Public knowledge excerpt:",
        load_fixture("public_knowledge.txt").rstrip(),
    ]
    if include_private:
        parts.extend(
            [
                "",
                "Owner-private artifact body:",
                load_fixture("owner_private.json").rstrip(),
                "",
                "Owner's own words:",
                load_fixture("owner_words.txt").rstrip(),
                "",
                "Owner source:",
                load_fixture("owner_source.py").rstrip(),
            ]
        )
    return "\n".join(parts) + "\n"


def classify_payload(text: str) -> dict[str, Any]:
    origins: dict[str, list[str]] = {}
    for origin, markers in ORIGIN_MARKERS.items():
        hits = [m for m in markers if m in text]
        if hits:
            origins[origin] = hits
    return {
        "origins": sorted(origins.keys()),
        "markers": origins,
        "has_attached_canary": CANARY_ATTACHED in text,
        "has_unattached_canary": CANARY_UNATTACHED in text,
        "bytes": len(text.encode("utf-8")),
    }


def _joined_captures(http_hits: list[dict], mcp: dict, cli: dict) -> str:
    bodies = [str(h.get("body") or "") for h in http_hits]
    bodies.append(str((mcp.get("child") or {}).get("stdin") or ""))
    bodies.append(str(mcp.get("parent_wrote") or ""))
    bodies.append(str((cli.get("child") or {}).get("prompt") or ""))
    bodies.append(str(cli.get("parent_argv_tail") or ""))
    return "\n".join(bodies)


def send_on_transports(prompt: str, tmp: Path) -> dict[str, Any]:
    observer = I.HttpObserver()
    counter = I.ConnectCounter()
    observer.start()
    counter.install()
    http_bytes = 0
    try:
        http_bytes = I.post_http(
            observer.endpoint,
            {
                "provider": "localhost-stand-in",
                "role": "research-query",
                "prompt": prompt,
            },
        )
        mcp = I.send_mcp_stdio(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "web_search",
                    "arguments": {"query": prompt},
                },
            },
            tmp / "mcp-capture.json",
        )
        cli = I.send_cli_subprocess(
            prompt, tmp / "cli-capture.json", workspace=WORKTREE
        )
        hits = observer.hits
        connects = counter.count
    finally:
        counter.remove()
        observer.stop()
    joined = _joined_captures(hits, mcp, cli)
    mcp_child = str((mcp.get("child") or {}).get("stdin") or "")
    cli_child = str((cli.get("child") or {}).get("prompt") or "")
    http_body = str(hits[0].get("body") or "") if hits else ""
    return {
        "http": {
            "hits": len(hits),
            "connects": connects,
            "bytes_sent": http_bytes,
            "body": http_body,
        },
        "mcp": {
            "exit_code": mcp.get("exit_code"),
            "parent_bytes": mcp.get("parent_bytes"),
            "child_bytes": (mcp.get("child") or {}).get("bytes"),
            "parent_matches_child": (mcp.get("parent_wrote") or "") == mcp_child,
            "stdin": mcp_child,
        },
        "cli": {
            "exit_code": cli.get("exit_code"),
            "parent_matches_child": (cli.get("parent_argv_tail") or "") == cli_child,
            "workspace": (cli.get("child") or {}).get("workspace"),
            "prompt": cli_child,
        },
        "joined": joined,
        "classification": classify_payload(joined),
    }


def inprocess_adapter_egress(prompt: str) -> dict[str, Any]:
    """CNF-0158 vendor_runtime: prompt stays in-process; no HTTP/MCP/CLI."""
    import vendor_runtime as VR  # noqa: WPS433 — optional live adapter

    observer = I.HttpObserver()
    counter = I.ConnectCounter()
    observer.start()
    counter.install()
    try:
        unit = {"id": "ADV-0046", "timeout_seconds": 30, "tool_permissions": ["Read"]}
        with tempfile.TemporaryDirectory(prefix="adv0046-adapter-") as td:
            out = Path(td) / "out.json"
            anthro = VR.AnthropicAdapter().dispatch(
                unit, prompt=prompt, prompt_by_file=True, output_path=out
            )
            openai = VR.OpenAIAdapter().dispatch(
                unit, prompt=prompt, prompt_by_file=True, output_path=out
            )
        hits = observer.hits
        connects = counter.count
    finally:
        counter.remove()
        observer.stop()
    return {
        "http_hits": len(hits),
        "socket_connects": connects,
        "anthropic_prompt_chars": anthro.prompt_chars,
        "openai_prompt_chars": openai.prompt_chars,
        "anthropic_transport": anthro.prompt_transport,
        "openai_transport": openai.prompt_transport,
        "canary_in_prompt": CANARY_ATTACHED in prompt,
        "egressed": len(hits) > 0 or connects > 0,
    }


def deliberate_canary_once() -> dict[str, Any]:
    """Control: send the attached canary once on every transport."""
    with tempfile.TemporaryDirectory(prefix="adv0046-ctrl-") as td:
        tmp = Path(td)
        report = send_on_transports(CANARY_ATTACHED, tmp)
    joined = report["joined"]
    return {
        "http_saw": CANARY_ATTACHED in report["http"]["body"],
        "mcp_saw": CANARY_ATTACHED in report["mcp"]["stdin"],
        "cli_saw": CANARY_ATTACHED in (report["cli"]["prompt"] or ""),
        "http_hits": report["http"]["hits"],
        "mcp_parent_matches_child": report["mcp"]["parent_matches_child"],
        "cli_parent_matches_child": report["cli"]["parent_matches_child"],
        "all_three": all(
            CANARY_ATTACHED in blob
            for blob in (
                report["http"]["body"],
                report["mcp"]["stdin"],
                report["cli"]["prompt"] or "",
            )
        ),
        "joined_has_unattached": CANARY_UNATTACHED in joined,
    }


def unattached_file_present() -> bool:
    return CANARY_UNATTACHED in load_fixture("owner_unattached.json")


def _line_of(text: str, needle: str) -> int:
    idx = text.find(needle)
    return text[:idx].count("\n") + 1 if idx >= 0 else 0


def census_live_tree() -> list[dict[str, Any]]:
    """Source-grounded sites that construct prompts or vendor argv."""
    rows = []
    cursor = REPO / "command-center" / "p2-wave" / "seed-stage" / "dispatch_cursor.py"
    text = cursor.read_text(encoding="utf-8")
    trunc = 'cmd.append(prompt.read_text(encoding="utf-8")[:12000])'
    full = 'cmd.append(prompt.read_text(encoding="utf-8"))\n'
    rows.append(
        {
            "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "line": _line_of(text, full) if full in text else _line_of(text, 'cmd.append(prompt.read_text(encoding="utf-8"))'),
            "snippet": 'cmd.append(prompt.read_text(encoding="utf-8"))',
            "rail": "cli-subprocess",
            "note": "launch_one embeds the full prompt in argv, including the worktree path from prompt_for.",
        }
    )
    if trunc in text:
        rows.append(
            {
                "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
                "line": _line_of(text, trunc),
                "snippet": trunc,
                "rail": "cli-subprocess",
                "note": "agent_cmd truncates the same prompt to 12000 characters before argv.",
            }
        )
    vr = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0158" / "vendor_runtime.py"
    vtext = vr.read_text(encoding="utf-8")
    vneedle = 'transport = "file" if prompt_by_file else "inline"'
    rows.append(
        {
            "path": "command-center/p2-wave/probes/CNF-0158/vendor_runtime.py",
            "line": vtext[: vtext.find(vneedle)].count("\n") + 1 if vneedle in vtext else 0,
            "snippet": vneedle,
            "rail": "in-process",
            "note": "Adapters record prompt_chars and write a local output file; they do not open HTTP/MCP/CLI.",
        }
    )
    return rows
