#!/usr/bin/env python3
"""GLM delivery agent — runs ON the GitHub runner, powered by the owner's two
Z.AI coding-plan keys (ZAI_API_KEY_A/B secrets; failover built in).

A minimal OpenAI-compatible tool-calling loop: system prompt = the committed
agent contract; tools = bash / read / write / list; each tool result feeds the
next turn; budget-bounded; on quota exhaustion (429/quota text) it switches to
the OTHER plan key and retries; both dead -> exit 1 with the partial report.

usage: python glm_agent.py --contract command-center/p2-loop/agent_contract.md \
                            --budget-min 270 [--model glm-4.6]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = os.environ.get(
    "ZAI_ENDPOINT", "https://api.z.ai/api/coding/paas/v4/chat/completions"
)
ROOT = Path(__file__).resolve().parents[2]
EXHAUST_MARKERS = ("insufficient", "quota", "exceeded", "balance", "rate limit")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the repo root (read-only git allowed; git WRITE commands are forbidden by the contract)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a repo-relative file (first 400 lines)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a repo-relative file (full content, LF)",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List a repo-relative directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


class Client:
    def __init__(self) -> None:
        # AGENT_API_KEY/AGENT_ENDPOINT = generic single-key backend (e.g. the
        # free OpenRouter GLM tier); otherwise the dual Z.AI plan keys.
        if os.environ.get("AGENT_API_KEY"):
            self.keys = [os.environ["AGENT_API_KEY"]]
        else:
            self.keys = [
                os.environ[n]
                for n in ("ZAI_API_KEY_A", "ZAI_API_KEY_B")
                if os.environ.get(n)
            ]
        if not self.keys:
            raise SystemExit("FAILED:glm-agent no ZAI_API_KEY_A/B or AGENT_API_KEY in env")
        self.active = 0
        self.endpoint = os.environ.get(
            "AGENT_ENDPOINT", ENDPOINT
        )

    def chat(self, messages: list[dict], model: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": messages, "tools": TOOLS, "stream": False}
        ).encode()
        # free single-key tiers (OpenRouter :free) 429 on transient upstream
        # saturation, not quota death — be patient with those
        max_attempts = len(self.keys) * 2 if len(self.keys) > 1 else 12
        for attempt in range(max_attempts):
            req = urllib.request.Request(
                self.endpoint,
                data=body,
                headers={
                    "Authorization": f"Bearer {self.keys[self.active]}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.loads(r.read())
            except TimeoutError:
                # deep-reasoning turns can exceed a single socket read window;
                # the request is idempotent — back off and resend
                wait = 15 + attempt * 10
                print(f"[read-timeout] long generation; retry in {wait}s (attempt {attempt + 1})", flush=True)
                time.sleep(wait)
                continue
            except ConnectionError as e:
                print(f"[conn-error] {type(e).__name__}; retry in 10s", flush=True)
                time.sleep(10)
                continue
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:500]
                except Exception:
                    pass
                if e.code == 429 or any(m in detail.lower() for m in EXHAUST_MARKERS):
                    if len(self.keys) == 1:
                        wait = min(20 + attempt * 15, 120)
                        print(f"[free-tier 429] transient upstream saturation; retry in {wait}s (attempt {attempt + 1})", flush=True)
                        time.sleep(wait)
                        continue
                    prev = self.active
                    self.active = (self.active + 1) % len(self.keys)
                    print(f"[failover] key#{prev} exhausted -> key#{self.active}", flush=True)
                    continue
                print(f"[api-error] HTTP {e.code}: {detail}", flush=True)
                if e.code == 400 and attempt + 1 < len(self.keys) * 2:
                    # transient plan-endpoint 400s observed; one retry on the
                    # same key, then the other, before giving up
                    time.sleep(3)
                    continue
                raise
        raise SystemExit("FAILED:glm-agent all plan keys exhausted")


def tool_call(name: str, args: dict) -> str:
    if name == "bash":
        p = subprocess.run(
            ["bash", "-lc", args["command"]], cwd=ROOT, capture_output=True, text=True, timeout=600
        )
        out = (p.stdout + p.stderr)[-6000:]
        return f"exit={p.returncode}\n{out}"
    if name == "read_file":
        p = ROOT / args["path"]
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:400]
            return "\n".join(lines)
        except Exception as e:
            return f"ERROR: {e}"
    if name == "write_file":
        p = ROOT / args["path"]
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8", newline="\n")
            return f"wrote {len(args['content'])} chars to {args['path']}"
        except Exception as e:
            return f"ERROR: {e}"
    if name == "list_dir":
        p = ROOT / args["path"]
        try:
            return "\n".join(sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())[:300])
        except Exception as e:
            return f"ERROR: {e}"
    return f"ERROR: unknown tool {name}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", default="command-center/p2-loop/agent_contract.md")
    ap.add_argument("--budget-min", type=int, default=270)
    ap.add_argument("--model", default=os.environ.get("GLM_MODEL", "glm-4.6"))
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    a = ap.parse_args()

    client = Client()
    contract = (ROOT / a.contract).read_text(encoding="utf-8")
    goal = subprocess.run(
        [sys.executable, "command-center/p2-loop/p2_goal.py"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    shard_note = ""
    if a.shards > 1:
        cat = json.loads(
            (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
        )
        unbuilt = sorted(u["id"] for u in cat["work_units"])
        mine = [uid for i, uid in enumerate(unbuilt) if i % a.shards == a.shard]
        shard_note = (
            "\n\n## SHARD ASSIGNMENT (shard %d of %d)\n"
            "You MUST only deliver/review units from this list (%d units):\n%s\n"
            "Units outside this list belong to sibling shards; do not touch them."
            % (a.shard, a.shards, len(mine), ", ".join(mine[:400]))
        )
    messages = [
        {
            "role": "system",
            "content": contract
            + shard_note
            + "\n\n## Goal function output right now\n```json\n"
            + goal
            + "\n```\nWork within this repo root. Use tools; end with your structured report.",
        },
        # a lone system message is rejected by the plan endpoint (error 1214)
        {"role": "user", "content": "Begin work per the contract now."},
    ]
    deadline = time.time() + a.budget_min * 60
    turns = 0
    while time.time() < deadline:
        turns += 1
        resp = client.chat(messages, a.model)
        msg = resp.get("choices", [{}])[0].get("message", {})
        content = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
        if content:
            print(f"[turn {turns}] {content[:500]}", flush=True)
        if not calls:
            print("[agent] final message (no tool calls) — contract work concluded", flush=True)
            print(content, flush=True)
            return 0
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for c in calls:
            fn = c["function"]["name"]
            args = json.loads(c["function"].get("arguments") or "{}")
            print(f"[tool] {fn} {str(args)[:120]}", flush=True)
            result = tool_call(fn, args)
            messages.append(
                {"role": "tool", "tool_call_id": c["id"], "content": result[-8000:]}
            )
    print(f"FAILED:glm-agent budget exhausted after {turns} turns; partial tree retained", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
