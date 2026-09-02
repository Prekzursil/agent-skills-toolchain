#!/usr/bin/env python3
"""Fetch two-rail evidence for RES-0163. No tokens printed."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "captures" / "raw"
INDEX = HERE / "captures" / "index.json"
UA = "ast-integrate-RES-0163-research/1.0 (+local-worktree; no-auth)"

RAILS = [
    {
        "id": "api-mcp-agent-mail",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/Dicklesworthstone/mcp_agent_mail",
        "accept": "application/vnd.github+json",
        "system": "mcp_agent_mail",
    },
    {
        "id": "prose-mcp-agent-mail-agents",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/Dicklesworthstone/"
            "mcp_agent_mail/main/AGENTS.md"
        ),
        "accept": "text/plain",
        "system": "mcp_agent_mail",
    },
    {
        "id": "prose-mcp-agent-mail-skill",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/Dicklesworthstone/"
            "mcp_agent_mail/main/SKILL.md"
        ),
        "accept": "text/plain",
        "system": "mcp_agent_mail",
    },
    {
        "id": "prose-mcp-agent-mail-guide",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/Dicklesworthstone/"
            "mcp_agent_mail/main/project_idea_and_guide.md"
        ),
        "accept": "text/plain",
        "system": "mcp_agent_mail",
    },
    {
        "id": "api-goose",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/block/goose",
        "accept": "application/vnd.github+json",
        "system": "goose",
    },
    {
        "id": "raw-goose-session-manager",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/block/goose/main/"
            "crates/goose/src/session/session_manager.rs"
        ),
        "accept": "text/plain",
        "system": "goose",
    },
    {
        "id": "raw-goose-session-cli",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/block/goose/main/"
            "crates/goose-cli/src/commands/session.rs"
        ),
        "accept": "text/plain",
        "system": "goose",
    },
    {
        "id": "api-openhands-sdk",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/OpenHands/software-agent-sdk",
        "accept": "application/vnd.github+json",
        "system": "openhands",
    },
    {
        "id": "raw-openhands-event-store",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
            "main/openhands-sdk/openhands/sdk/conversation/event_store.py"
        ),
        "accept": "text/plain",
        "system": "openhands",
    },
    {
        "id": "raw-openhands-conversation-lease",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
            "main/openhands-agent-server/openhands/agent_server/"
            "conversation_lease.py"
        ),
        "accept": "text/plain",
        "system": "openhands",
    },
    {
        "id": "raw-openhands-conversation-lease-alt",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/OpenHands/software-agent-sdk/"
            "main/openhands/agent_server/conversation_lease.py"
        ),
        "accept": "text/plain",
        "system": "openhands",
    },
    {
        "id": "api-git",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/git/git",
        "accept": "application/vnd.github+json",
        "system": "git_worktrees",
    },
    {
        "id": "prose-git-worktree-adoc",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/git-worktree.adoc"
        ),
        "accept": "text/plain",
        "system": "git_worktrees",
    },
    {
        "id": "raw-git-worktree-c",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/builtin/worktree.c"
        ),
        "accept": "text/plain",
        "system": "git_worktrees",
    },
    {
        "id": "api-emacs-mirror",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/emacs-mirror/emacs",
        "accept": "application/vnd.github+json",
        "system": "editor_lockfiles",
    },
    {
        "id": "raw-emacs-filelock-c",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/emacs-mirror/emacs/master/"
            "src/filelock.c"
        ),
        "accept": "text/plain",
        "system": "editor_lockfiles",
    },
    {
        "id": "prose-emacs-interlocking",
        "kind": "prose-source",
        "permalink": (
            "https://www.gnu.org/software/emacs/manual/html_node/emacs/"
            "Interlocking.html"
        ),
        "accept": "text/html",
        "system": "editor_lockfiles",
    },
    {
        "id": "prose-vim-recover",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/vim/vim/master/runtime/doc/"
            "recover.txt"
        ),
        "accept": "text/plain",
        "system": "editor_lockfiles",
    },
    {
        "id": "api-etcd",
        "kind": "structured-api",
        "permalink": "https://api.github.com/repos/etcd-io/etcd",
        "accept": "application/vnd.github+json",
        "system": "distributed_lock",
    },
    {
        "id": "prose-etcd-contrib-lock",
        "kind": "prose-source",
        "permalink": (
            "https://raw.githubusercontent.com/etcd-io/etcd/main/contrib/lock/"
            "README.md"
        ),
        "accept": "text/plain",
        "system": "distributed_lock",
    },
    {
        "id": "prose-kleppmann-locking",
        "kind": "prose-source",
        "permalink": (
            "https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-"
            "locking.html"
        ),
        "accept": "text/html",
        "system": "distributed_lock",
    },
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch(url: str, accept: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=45) as resp:
            body = resp.read()
            final = str(resp.geturl())
            return int(resp.status), body, final
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, url
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        msg = f"FETCH-ERROR:{type(exc).__name__}:{exc}".encode("utf-8")
        return 0, msg, url


def ext_for(kind: str, permalink: str) -> str:
    if "api.github.com" in permalink:
        return ".json"
    lower = permalink.lower()
    if lower.endswith(".md"):
        return ".md"
    if lower.endswith(".rs"):
        return ".rs"
    if lower.endswith(".py"):
        return ".py"
    if lower.endswith(".c"):
        return ".c"
    if lower.endswith(".adoc"):
        return ".adoc"
    if lower.endswith(".txt"):
        return ".txt"
    if kind == "structured-api":
        return ".json"
    return ".html"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    failures = []
    for spec in RAILS:
        status, body, final = fetch(spec["permalink"], spec["accept"])
        rel = f"captures/raw/{spec['id']}{ext_for(spec['kind'], spec['permalink'])}"
        path = HERE / rel
        path.write_bytes(body)
        digest = sha256_bytes(body)
        row = {
            "id": spec["id"],
            "kind": spec["kind"],
            "system": spec["system"],
            "permalink": spec["permalink"],
            "final_url": final,
            "http_status": status,
            "fetch_timestamp": ts,
            "sha256": digest,
            "bytes": len(body.replace(b"\r\n", b"\n")),
            "path": f"command-center/p2-wave/probes/RES-0163/{rel}",
        }
        rows.append(row)
        mark = "OK" if status == 200 and body else "FAIL"
        print(
            f"{mark} {status} {spec['id']} sha256={digest[:12]} bytes={len(body)}"
        )
        if status != 200 or not body:
            failures.append(spec["id"])
    INDEX.write_text(
        json.dumps(
            {
                "unit_id": "RES-0163",
                "fetched_at": ts,
                "user_agent": UA,
                "auth": "none",
                "rails": rows,
                "failed_ids": failures,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    needed = {
        "mcp_agent_mail": [
            "api-mcp-agent-mail",
            "prose-mcp-agent-mail-agents",
            "prose-mcp-agent-mail-skill",
        ],
        "goose": ["api-goose", "raw-goose-session-manager"],
        "openhands": ["api-openhands-sdk", "raw-openhands-event-store"],
        "git_worktrees": ["api-git", "prose-git-worktree-adoc", "raw-git-worktree-c"],
        "editor_lockfiles": ["raw-emacs-filelock-c", "prose-vim-recover"],
        "distributed_lock": ["api-etcd", "prose-etcd-contrib-lock"],
    }
    ok_ids = {r["id"] for r in rows if r["http_status"] == 200 and r["bytes"] > 0}
    missing = [
        name
        for name, ids in needed.items()
        if not any(i in ok_ids for i in ids)
        or sum(1 for i in ids if i in ok_ids) < 2
    ]
    # OpenHands lease file is optional alt; event store + API is enough if lease 404s.
    if "openhands" in missing:
        oh_ok = [i for i in ok_ids if i.startswith("raw-openhands") or i == "api-openhands-sdk"]
        if "api-openhands-sdk" in oh_ok and any(
            i.startswith("raw-openhands") for i in oh_ok
        ):
            missing = [m for m in missing if m != "openhands"]
    if missing:
        print(f"FAILED:capture missing groups {missing} failed={failures}")
        return 1
    print(f"SUCCESS:RES-0163-capture n={len(rows)} failed={failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
