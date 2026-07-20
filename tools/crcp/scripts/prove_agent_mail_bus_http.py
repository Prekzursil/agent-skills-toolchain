"""Prove agent-mail bus via raw JSON-RPC HTTP (no streamablehttp_client hang)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import urllib.request

URL = "http://127.0.0.1:8812/mcp"
PROJECT = str(Path.home() / "source" / "agent-skills-toolchain")
REPORT = Path(__file__).resolve().parents[1] / "reports" / "bus_proof.json"
DB = Path.home() / ".local/opt/mcp_agent_mail/storage.sqlite3"


class Rpc:
    def __init__(self, url: str):
        self.url = url
        self.session_id: str | None = None
        self._id = 0

    def call(self, method: str, params: dict | None = None, is_notification: bool = False):
        self._id += 1
        payload: dict = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            payload["id"] = self._id
        if params is not None:
            payload["params"] = params
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
            if sid:
                self.session_id = sid
            body = resp.read().decode("utf-8", "replace")
            # handle SSE-ish responses: lines starting with data:
            if body.lstrip().startswith("event:") or "\ndata:" in body or body.startswith("data:"):
                chunks = []
                for line in body.splitlines():
                    if line.startswith("data:"):
                        chunks.append(line[5:].strip())
                body = "\n".join(chunks) if chunks else body
            if is_notification or not body.strip():
                return None
            # may be multiple json objects
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                # take first json line
                for line in body.splitlines():
                    line = line.strip()
                    if line.startswith("{"):
                        return json.loads(line)
                raise


def tool_result_text(rpc_result: dict) -> str:
    if not rpc_result:
        return ""
    if "error" in rpc_result:
        raise RuntimeError(json.dumps(rpc_result["error"])[:500])
    result = rpc_result.get("result") or {}
    parts = []
    for c in result.get("content") or []:
        if isinstance(c, dict) and c.get("text"):
            parts.append(c["text"])
    if result.get("structuredContent") is not None:
        parts.append(json.dumps(result["structuredContent"]))
    return "\n".join(parts)


def parse_tool(rpc_result: dict):
    raw = tool_result_text(rpc_result)
    try:
        return json.loads(raw), raw
    except Exception:
        return raw, raw


def extract_agent(reg):
    if isinstance(reg, dict):
        for nk, tk in [("name", "registration_token"), ("agent_name", "registration_token")]:
            if reg.get(nk) and reg.get(tk):
                return reg[nk], reg[tk]
        for v in reg.values():
            if isinstance(v, dict):
                n, t = extract_agent(v)
                if n:
                    return n, t
    if isinstance(reg, str):
        import re

        m = re.search(r"([A-Z][a-z]+[A-Z][a-z]+)", reg)
        t = re.search(r"(?:registration_token|token)[\"'=\s:]+([A-Za-z0-9_\-]{8,})", reg)
        if m and t:
            return m.group(1), t.group(1)
    return None, None


def main() -> int:
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "url": URL,
        "project": PROJECT,
        "transport": "jsonrpc-http",
        "steps": [],
        "success": False,
    }
    marker = f"CRCP-P0-BUS-PROOF {uuid.uuid4().hex[:12]}"
    rpc = Rpc(URL)

    init = rpc.call(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "crcp-bus-proof", "version": "0.1"},
        },
    )
    report["steps"].append({"step": "initialize", "ok": True, "session": rpc.session_id, "server": (init or {}).get("result", {}).get("serverInfo")})
    rpc.call("notifications/initialized", {}, is_notification=True)

    tools = rpc.call("tools/list", {})
    tool_names = [t.get("name") for t in ((tools or {}).get("result") or {}).get("tools") or []]
    report["tools"] = tool_names
    report["steps"].append({"step": "tools/list", "count": len(tool_names)})

    def tool(name: str, arguments: dict):
        res = rpc.call("tools/call", {"name": name, "arguments": arguments})
        return parse_tool(res)

    data, _ = tool("ensure_project", {"human_key": PROJECT})
    report["steps"].append({"step": "ensure_project", "preview": str(data)[:300]})

    # reuse agents if present
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        """
        select a.name, a.registration_token, a.program
        from agents a join projects p on p.id=a.project_id
        where p.human_key=? and a.retired_at is null
          and a.program in ('claude-orchestrator','codex-executor')
        order by a.id desc
        """,
        (PROJECT,),
    ).fetchall()
    con.close()
    by = {}
    for name, tok, prog in rows:
        by.setdefault(prog, (name, tok))

    if "claude-orchestrator" in by and "codex-executor" in by:
        c_name, c_tok = by["claude-orchestrator"]
        x_name, x_tok = by["codex-executor"]
        report["steps"].append({"step": "reuse_agents", "claude": c_name, "codex": x_name})
    else:
        claude_reg, _ = tool(
            "register_agent",
            {"project_key": PROJECT, "program": "claude-orchestrator", "model": "claude-phase0-probe"},
        )
        codex_reg, _ = tool(
            "register_agent",
            {"project_key": PROJECT, "program": "codex-executor", "model": "codex-phase0-probe"},
        )
        report["steps"].append({"step": "register_claude", "preview": str(claude_reg)[:400]})
        report["steps"].append({"step": "register_codex", "preview": str(codex_reg)[:400]})
        c_name, c_tok = extract_agent(claude_reg)
        x_name, x_tok = extract_agent(codex_reg)

    report["agents"] = {"claude": c_name, "codex": x_name, "tokens": bool(c_tok and x_tok)}
    if not (c_name and c_tok and x_name and x_tok):
        report["error"] = "agent extract failed"
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("FAILED:extract")
        print(json.dumps(report, indent=2)[:2000])
        return 2

    for name, args in [
        ("request_contact", {"project_key": PROJECT, "from_agent": c_name, "to_agent": x_name, "registration_token": c_tok}),
        ("request_contact", {"project_key": PROJECT, "from_agent": x_name, "to_agent": c_name, "registration_token": x_tok}),
        ("respond_contact", {"project_key": PROJECT, "to_agent": x_name, "from_agent": c_name, "accept": True, "registration_token": x_tok}),
        ("respond_contact", {"project_key": PROJECT, "to_agent": c_name, "from_agent": x_name, "accept": True, "registration_token": c_tok}),
    ]:
        try:
            d, _ = tool(name, args)
            report["steps"].append({"step": name, "ok": True, "preview": str(d)[:160]})
        except Exception as e:
            report["steps"].append({"step": name, "ok": False, "error": str(e)[:240]})

    send1, _ = tool(
        "send_message",
        {
            "project_key": PROJECT,
            "sender_name": c_name,
            "sender_token": c_tok,
            "to": [x_name],
            "subject": "CRCP Phase0 bus proof",
            "body_md": marker,
        },
    )
    report["steps"].append({"step": "send_c_to_x", "preview": str(send1)[:200]})

    inbox_x, _ = tool(
        "fetch_inbox",
        {
            "project_key": PROJECT,
            "agent_name": x_name,
            "registration_token": x_tok,
            "include_bodies": True,
            "limit": 20,
        },
    )
    report["steps"].append({"step": "inbox_x", "preview": str(inbox_x)[:400]})

    reply = marker + " | REPLY_OK"
    send2, _ = tool(
        "send_message",
        {
            "project_key": PROJECT,
            "sender_name": x_name,
            "sender_token": x_tok,
            "to": [c_name],
            "subject": "CRCP Phase0 bus proof REPLY",
            "body_md": reply,
        },
    )
    report["steps"].append({"step": "send_x_to_c", "preview": str(send2)[:200]})

    inbox_c, _ = tool(
        "fetch_inbox",
        {
            "project_key": PROJECT,
            "agent_name": c_name,
            "registration_token": c_tok,
            "include_bodies": True,
            "limit": 20,
        },
    )
    report["steps"].append({"step": "inbox_c", "preview": str(inbox_c)[:400]})

    blob = json.dumps(inbox_x, default=str) + json.dumps(inbox_c, default=str) + str(inbox_x) + str(inbox_c)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    n = con.execute("select count(*) from messages where body_md like ?", (f"%{marker}%",)).fetchone()[0]
    n2 = con.execute("select count(*) from messages where body_md like ?", ("%REPLY_OK%",)).fetchone()[0]
    recent = con.execute(
        "select id, subject, substr(body_md,1,80) from messages order by id desc limit 5"
    ).fetchall()
    con.close()
    report["sqlite_marker_msgs"] = n
    report["sqlite_reply_msgs"] = n2
    report["recent_messages"] = [{"id": r[0], "subject": r[1], "body": r[2]} for r in recent]
    report["got_forward"] = marker in blob or n >= 1
    report["got_reply"] = ("REPLY_OK" in blob) or n2 >= 1
    report["success"] = bool(report["got_forward"] and report["got_reply"])
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report.get(k)
                for k in (
                    "success",
                    "got_forward",
                    "got_reply",
                    "agents",
                    "sqlite_marker_msgs",
                    "sqlite_reply_msgs",
                    "tools",
                    "recent_messages",
                )
            },
            indent=2,
        )
    )
    print("SUCCESS:bus_proof" if report["success"] else "FAILED:bus_proof")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
