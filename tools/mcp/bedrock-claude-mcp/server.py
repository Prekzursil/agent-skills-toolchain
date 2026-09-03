#!/usr/bin/env python3
"""bedrock-claude-mcp: minimal stdio MCP server exposing Amazon Bedrock Claude
models as chat tools. Backed by `aws bedrock-runtime converse` through the
operator's SSO credential chain (AWS_PROFILE); no secrets stored here.

Tools:
  claude_chat      - Claude Sonnet (configurable via BEDROCK_CLAUDE_MODEL)
  claude_haiku     - Claude Haiku, cheap/fast tier (BEDROCK_HAIKU_MODEL)
  bedrock_models   - list Claude models available in the region

Model IDs default to the EU cross-region prefixes (eu-central-1) with global
fallbacks; both overridable via environment.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

PROFILE = os.environ.get("AWS_PROFILE", "bolt-datascience")
REGION = os.environ.get("AWS_REGION", "eu-central-1")
CLAUDE_MODEL = os.environ.get(
    "BEDROCK_CLAUDE_MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1-0"
)
HAIKU_MODEL = os.environ.get(
    "BEDROCK_HAIKU_MODEL", "eu.anthropic.claude-haiku-4-5-20251001-v1-0"
)
TIMEOUT = int(os.environ.get("BEDROCK_MCP_TIMEOUT", "240"))

TOOLS = [
    {
        "name": "claude_chat",
        "description": "Chat with Claude Sonnet on Amazon Bedrock (operator SSO chain). "
        "Input: prompt (str), optional system (str), optional max_tokens (int).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "system": {"type": "string"},
                "max_tokens": {"type": "integer", "default": 4096},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "claude_haiku",
        "description": "Chat with Claude Haiku on Amazon Bedrock (fast/cheap tier).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "system": {"type": "string"},
                "max_tokens": {"type": "integer", "default": 2048},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "bedrock_models",
        "description": "List Claude/Anthropic foundation models available in the configured region.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"xox[bap]-[A-Za-z0-9-]{10,})"
)


def _redact(text: str) -> str:
    return SECRET_RE.sub("[REDACTED]", text)


def converse(model: str, prompt: str, system: str, max_tokens: int) -> str:
    messages = json.dumps([{"role": "user", "content": [{"text": prompt[:120_000]}]}])
    cmd = [
        "aws", "bedrock-runtime", "converse",
        "--profile", PROFILE, "--region", REGION, "--model-id", model,
        "--messages", messages,
        "--inference-config", json.dumps({"maxTokens": max_tokens, "temperature": 0.3}),
    ]
    if system:
        cmd += ["--system", json.dumps([{"text": system[:16_000]}])]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired:
        return "ERROR: bedrock call timed out"
    except OSError as exc:
        return f"ERROR: aws cli unavailable: {type(exc).__name__}"
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        return f"ERROR: aws exit {proc.returncode}: {_redact(detail[-1][:300] if detail else 'no output')}"
    try:
        data = json.loads(proc.stdout)
        return _redact(data["output"]["message"]["content"][0]["text"].strip())
    except (KeyError, IndexError, ValueError):
        return "ERROR: could not parse bedrock response"


def list_models() -> str:
    try:
        proc = subprocess.run(
            ["aws", "bedrock", "list-foundation-models",
             "--profile", PROFILE, "--region", REGION,
             "--by-provider", "anthropic", "--query",
             "modelSummaries[].[modelId,modelName] --output text"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return f"ERROR: {type(exc).__name__}"
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        return f"ERROR: aws exit {proc.returncode}: {detail[-1][:200] if detail else ''}"
    return (proc.stdout or "").strip()


def handle_tool_call(name: str, arguments: dict) -> str:
    if name == "claude_chat":
        return converse(
            CLAUDE_MODEL, str(arguments.get("prompt", "")),
            str(arguments.get("system", "")), int(arguments.get("max_tokens", 4096)),
        )
    if name == "claude_haiku":
        return converse(
            HAIKU_MODEL, str(arguments.get("prompt", "")),
            str(arguments.get("system", "")), int(arguments.get("max_tokens", 2048)),
        )
    if name == "bedrock_models":
        return list_models()
    return f"ERROR: unknown tool {name}"


def send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            continue
        method = request.get("method", "")
        request_id = request.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": request_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bedrock-claude-mcp", "version": "1.0.0"},
            }})
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = request.get("params", {})
            text = handle_tool_call(
                params.get("name", ""), params.get("arguments", {}) or {}
            )
            send({"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": text}],
                "isError": text.startswith("ERROR"),
            }})
        elif request_id is not None:
            send({"jsonrpc": "2.0", "id": request_id,
                  "error": {"code": -32601, "message": f"unknown method {method}"}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
