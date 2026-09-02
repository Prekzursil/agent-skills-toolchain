#!/usr/bin/env python3
"""Shared fetch/hash helpers for RES-0029. No API keys. No git writes."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0029"
ART_REL = "command-center/research/RES-0029.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0029 in the receipt AND the trigger implementation "
    "cited at file:line plus one issue-tracker-sourced failure mode"
)
UA = "ast-integrate-RES-0029-probe (+research; no auth)"
SDK_COMMIT = "25cc8e56a4d029f4f879bdfead1cd21c11d6483d"
DOCS_COMMIT = "80930beab613ebebbc01a63fb83f95fed366c9b5"
SKILL_RAW = (
    "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/skills/skill.py"
)
SKILL_PERMALINK = (
    "https://github.com/OpenHands/software-agent-sdk/blob/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/skills/skill.py"
)
TRIGGER_RAW = (
    "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/skills/trigger.py"
)
TRIGGER_PERMALINK = (
    "https://github.com/OpenHands/software-agent-sdk/blob/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/skills/trigger.py"
)
AGENT_RAW = (
    "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/agent/agent.py"
)
AGENT_PERMALINK = (
    "https://github.com/OpenHands/software-agent-sdk/blob/"
    f"{SDK_COMMIT}/openhands-sdk/openhands/sdk/agent/agent.py"
)
DOCKER_RAW = (
    "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
    f"{SDK_COMMIT}/openhands-workspace/openhands/workspace/docker/workspace.py"
)
DOCKER_PERMALINK = (
    "https://github.com/OpenHands/software-agent-sdk/blob/"
    f"{SDK_COMMIT}/openhands-workspace/openhands/workspace/docker/workspace.py"
)
README_RAW = (
    "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
    f"{SDK_COMMIT}/README.md"
)
SKILL_API = (
    "https://api.github.com/repos/OpenHands/software-agent-sdk/contents/"
    "openhands-sdk/openhands/sdk/skills/skill.py"
)
DOCKER_API = (
    "https://api.github.com/repos/OpenHands/software-agent-sdk/contents/"
    "openhands-workspace/openhands/workspace/docker/workspace.py"
)
DOCS_RAW = (
    "https://raw.githubusercontent.com/OpenHands/docs/"
    f"{DOCS_COMMIT}/sdk/arch/skill.mdx"
)
DOCS_PERMALINK = (
    "https://github.com/OpenHands/docs/blob/"
    f"{DOCS_COMMIT}/sdk/arch/skill.mdx"
)
ISSUE_HTML = "https://github.com/OpenHands/OpenHands/issues/10073"
ISSUE_API = "https://api.github.com/repos/OpenHands/OpenHands/issues/10073"
ISSUE_CTRL_HTML = "https://github.com/OpenHands/OpenHands/issues/9889"
OLD_ORG = "https://github.com/All-Hands-AI/OpenHands"
NEW_ORG = "https://github.com/OpenHands/OpenHands"
SKILL_API = (
    "https://api.github.com/repos/OpenHands/software-agent-sdk/contents/"
    "openhands-sdk/openhands/sdk/skills/skill.py"
)
DOCKER_API = (
    "https://api.github.com/repos/OpenHands/software-agent-sdk/contents/"
    "openhands-workspace/openhands/workspace/docker/workspace.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def fetch(url: str, timeout: int = 40) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {
                "url": url,
                "final_url": getattr(resp, "geturl", lambda: url)(),
                "http_status": int(getattr(resp, "status", 200) or 200),
                "body": body,
                "sha256": sha256_bytes(body),
                "bytes": len(body),
                "fetch_timestamp": utc_now(),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "url": url,
            "final_url": url,
            "http_status": int(exc.code),
            "body": body,
            "sha256": sha256_bytes(body),
            "bytes": len(body),
            "fetch_timestamp": utc_now(),
            "error": str(exc),
        }


def def_line(src: str, needle: str) -> int | None:
    for i, line in enumerate(src.splitlines(), 1):
        if needle in line:
            return i
    return None


def load_artifact() -> dict:
    if not ART.is_file() or ART.stat().st_size <= 0:
        raise FileNotFoundError(ART_REL)
    return json.loads(ART.read_text(encoding="utf-8"))


def slash_trigger_failure_title(title: str) -> bool:
    t = (title or "").lower()
    return "microagents with / not triggering" in t or "/ not triggering" in t


def issue_title_from_html(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else ""
