import asyncio
import json
import uuid
import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path

URL = "http://127.0.0.1:8812/mcp"
PROJECT = str(Path.home() / "source" / "agent-skills-toolchain")
REPORT = Path(__file__).resolve().parents[1] / "reports" / "bus_proof.json"
DB = Path.home() / ".local/opt/mcp_agent_mail/storage.sqlite3"


def text_of(result) -> str:
    parts = []
    for c in getattr(result, "content", None) or []:
        t = getattr(c, "text", None)
        if t:
            parts.append(t)
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        parts.append(json.dumps(sc))
    return "\n".join(parts)


def parse(result):
    raw = text_of(result)
    try:
        return json.loads(raw), raw
    except Exception:
        return raw, raw


def extract_agent(reg):
    if isinstance(reg, dict):
        for name_k, tok_k in [
            ("name", "registration_token"),
            ("agent_name", "registration_token"),
            ("codename", "token"),
        ]:
            if reg.get(name_k) and reg.get(tok_k):
                return reg[name_k], reg[tok_k]
        for v in reg.values():
            if isinstance(v, dict):
                n, t = extract_agent(v)
                if n:
                    return n, t
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        n, t = extract_agent(item)
                        if n:
                            return n, t
    if isinstance(reg, str):
        m = re.search(r"([A-Z][a-z]+[A-Z][a-z]+)", reg)
        t = re.search(
            r"(?:registration_token|token)[\"'=\s:]+([A-Za-z0-9_\-]{8,})", reg
        )
        if m and t:
            return m.group(1), t.group(1)
        try:
            return extract_agent(json.loads(reg))
        except Exception:
            pass
    return None, None


async def call(session, name, args):
    r = await session.call_tool(name, args)
    if getattr(r, "isError", False):
        raise RuntimeError(f"tool_error {name}: {text_of(r)[:500]}")
    return parse(r)


async def main():
    from mcp.client.streamable_http import streamablehttp_client
    from mcp import ClientSession

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "url": URL,
        "project": PROJECT,
        "steps": [],
        "success": False,
    }
    marker = f"CRCP-P0-BUS-PROOF {uuid.uuid4().hex[:12]}"

    async with streamablehttp_client(
        URL, timeout=60.0, sse_read_timeout=120.0
    ) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            report["steps"].append({"step": "initialize", "ok": True})

            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            report["tools"] = tool_names
            report["steps"].append({"step": "list_tools", "count": len(tool_names)})

            data, _ = await call(session, "ensure_project", {"human_key": PROJECT})
            report["steps"].append(
                {"step": "ensure_project", "preview": str(data)[:300]}
            )

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
            by_prog = {}
            for name, tok, prog in rows:
                by_prog.setdefault(prog, (name, tok))

            if "claude-orchestrator" in by_prog and "codex-executor" in by_prog:
                c_name, c_tok = by_prog["claude-orchestrator"]
                x_name, x_tok = by_prog["codex-executor"]
                report["steps"].append(
                    {"step": "reuse_agents", "claude": c_name, "codex": x_name}
                )
            else:
                claude_reg, _ = await call(
                    session,
                    "register_agent",
                    {
                        "project_key": PROJECT,
                        "program": "claude-orchestrator",
                        "model": "claude-phase0-probe",
                    },
                )
                codex_reg, _ = await call(
                    session,
                    "register_agent",
                    {
                        "project_key": PROJECT,
                        "program": "codex-executor",
                        "model": "codex-phase0-probe",
                    },
                )
                report["steps"].append(
                    {"step": "register_claude", "preview": str(claude_reg)[:400]}
                )
                report["steps"].append(
                    {"step": "register_codex", "preview": str(codex_reg)[:400]}
                )
                c_name, c_tok = extract_agent(claude_reg)
                x_name, x_tok = extract_agent(codex_reg)

            report["agents"] = {
                "claude": c_name,
                "codex": x_name,
                "tokens": bool(c_tok and x_tok),
            }
            if not (c_name and c_tok and x_name and x_tok):
                report["error"] = "agent extract failed"
                REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print("FAILED:extract")
                print(json.dumps(report, indent=2)[:2000])
                return 2

            for tool, args in [
                (
                    "request_contact",
                    {
                        "project_key": PROJECT,
                        "from_agent": c_name,
                        "to_agent": x_name,
                        "registration_token": c_tok,
                    },
                ),
                (
                    "request_contact",
                    {
                        "project_key": PROJECT,
                        "from_agent": x_name,
                        "to_agent": c_name,
                        "registration_token": x_tok,
                    },
                ),
                (
                    "respond_contact",
                    {
                        "project_key": PROJECT,
                        "to_agent": x_name,
                        "from_agent": c_name,
                        "accept": True,
                        "registration_token": x_tok,
                    },
                ),
                (
                    "respond_contact",
                    {
                        "project_key": PROJECT,
                        "to_agent": c_name,
                        "from_agent": x_name,
                        "accept": True,
                        "registration_token": c_tok,
                    },
                ),
            ]:
                try:
                    d, _ = await call(session, tool, args)
                    report["steps"].append(
                        {"step": tool, "ok": True, "preview": str(d)[:160]}
                    )
                except Exception as e:
                    report["steps"].append(
                        {"step": tool, "ok": False, "error": str(e)[:200]}
                    )

            send1, _ = await call(
                session,
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

            inbox_x, _ = await call(
                session,
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
            send2, _ = await call(
                session,
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

            inbox_c, _ = await call(
                session,
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

            blob = (
                json.dumps(inbox_x, default=str)
                + json.dumps(inbox_c, default=str)
                + str(inbox_x)
                + str(inbox_c)
            )
            con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            n = con.execute(
                "select count(*) from messages where body_md like ?", (f"%{marker}%",)
            ).fetchone()[0]
            n2 = con.execute(
                "select count(*) from messages where body_md like ?", ("%REPLY_OK%",)
            ).fetchone()[0]
            con.close()
            report["sqlite_marker_msgs"] = n
            report["sqlite_reply_msgs"] = n2
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
                )
            },
            indent=2,
        )
    )
    print("SUCCESS:bus_proof" if report["success"] else "FAILED:bus_proof")
    return 0 if report["success"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as e:
        err = {"success": False, "error": repr(e)}
        REPORT.write_text(json.dumps(err, indent=2), encoding="utf-8")
        print(json.dumps(err, indent=2))
        print("FAILED:bus_exception")
        raise
