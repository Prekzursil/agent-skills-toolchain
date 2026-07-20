"""ChatGPT live bridge — REST consumer using Codex access_token (owner account)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .credential_snapshot import CredentialSnapshot, is_stale_mtime, load_from_auth_json
from .envelope import content_hash, make_envelope, write_envelope, utc_now
from .http_secure import open_url


class BridgeDegradedError(RuntimeError):
    """The token-consuming bridge cannot authenticate with its current snapshot."""


class ChatGPTBridge:
    """Read-only ChatGPT backend-api client. Does not refresh tokens."""

    def __init__(self, codex_home: Path | None = None, base: str = "https://chatgpt.com"):
        self.codex_home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.base = base.rstrip("/")
        self._snapshot: CredentialSnapshot | None = None
        self.reload()

    def reload(self) -> None:
        auth_path = self.codex_home / "auth.json"
        snapshot = load_from_auth_json(auth_path)
        if snapshot.expired:
            raise RuntimeError("access_token expired — primary Codex owner must refresh auth.json")
        self._snapshot = snapshot

    def _maybe_reload(self) -> None:
        auth_path = self.codex_home / "auth.json"
        known_mtime = self._snapshot.mtime_ns if self._snapshot else None
        if is_stale_mtime(auth_path, known_mtime):
            self.reload()

    def _make_request(self, method: str, url: str) -> urllib.request.Request:
        if self._snapshot is None:
            raise BridgeDegradedError("bridge has no credential snapshot")
        headers = self._snapshot.credentials.apply_to_headers(
            {"Accept": "application/json", "User-Agent": "CRCP-chatgpt-bridge/0.2"}
        )
        return urllib.request.Request(url, method=method, headers=headers)

    def _request(self, method: str, path: str, query: dict[str, Any] | None = None) -> Any:
        self._maybe_reload()
        q = f"?{urllib.parse.urlencode(query)}" if query else ""
        url = f"{self.base}{path}{q}"
        for attempt in range(2):
            req = self._make_request(method, url)
            try:
                with open_url(req, timeout=45) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                changed = (
                    error.code == 401
                    and attempt == 0
                    and self._snapshot is not None
                    and is_stale_mtime(self.codex_home / "auth.json", self._snapshot.mtime_ns)
                )
                if changed:
                    self.reload()
                    continue
                if error.code == 401:
                    raise BridgeDegradedError(
                        f"HTTP 401 {path}; bridge degraded until the auth owner updates auth.json"
                    ) from error
                raise RuntimeError(f"HTTP {error.code} {path}") from error
        raise BridgeDegradedError("bridge authentication retry exhausted")

    def list_conversations(self, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        return self._request(
            "GET",
            "/backend-api/conversations",
            {"offset": offset, "limit": limit},
        )

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        cid = urllib.parse.quote(conversation_id, safe="")
        return self._request("GET", f"/backend-api/conversation/{cid}")

    def me(self) -> dict[str, Any]:
        return self._request("GET", "/backend-api/me")


def summarize_conversation(conv: dict[str, Any]) -> dict[str, Any]:
    """Extract safe stats + text metrics without dumping full body to logs."""
    mapping = conv.get("mapping") or {}
    roles: dict[str, int] = {}
    total_chars = 0
    messages = 0
    if isinstance(mapping, dict):
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            msg = node.get("message")
            if not isinstance(msg, dict):
                continue
            messages += 1
            author = msg.get("author") or {}
            role = author.get("role") if isinstance(author, dict) else None
            if role:
                roles[role] = roles.get(role, 0) + 1
            content = msg.get("content") or {}
            parts = content.get("parts") if isinstance(content, dict) else None
            if isinstance(parts, list):
                for p in parts:
                    if isinstance(p, str):
                        total_chars += len(p)
    return {
        "id": conv.get("id") or conv.get("conversation_id"),
        "title": conv.get("title"),
        "create_time": conv.get("create_time"),
        "update_time": conv.get("update_time"),
        "mapping_nodes": len(mapping) if isinstance(mapping, dict) else 0,
        "message_count": messages,
        "roles": roles,
        "total_text_chars": total_chars,
        "has_real_text": total_chars > 0,
    }


def _safe_filename(s: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", s)[:80]
    return s or "conversation"


def export_conversation_pack(
    conv: dict[str, Any],
    out_dir: Path,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Write conversation JSON + CRCP envelope to outbox."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_conversation(conv)
    cid = str(summary.get("id") or "unknown")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload_path = out_dir / f"chatgpt_conv_{_safe_filename(cid)}_{stamp}.json"
    payload_path.write_text(json.dumps(conv, indent=2, default=str), encoding="utf-8")

    env = make_envelope(
        from_rail="chatgpt_live_bridge",
        to_rail="broadcast",
        intent="research",
        payload_ref=str(payload_path),
        project_id=project_id or str(Path.home() / "source" / "agent-skills-toolchain"),
        thread_id=cid,
        completion="SUCCESS",
        capabilities_required=["chatgpt_backend_api"],
        meta={
            "source": "chatgpt_backend_api",
            "conversation_summary": summary,
            "exported_at": utc_now(),
            "payload_sha256": content_hash(payload_path.read_bytes()),
        },
    )
    env_path = out_dir / f"envelope_{_safe_filename(cid)}_{stamp}.json"
    write_envelope(env_path, env)
    return {
        "conversation_id": cid,
        "summary": summary,
        "payload_path": str(payload_path),
        "envelope_path": str(env_path),
        "envelope_id": env["id"],
    }


def list_summaries(limit: int = 20) -> dict[str, Any]:
    bridge = ChatGPTBridge()
    data = bridge.list_conversations(offset=0, limit=limit)
    items = data.get("items") or []
    summaries = []
    for it in items:
        summaries.append(
            {
                "id": it.get("id"),
                "title": it.get("title"),
                "create_time": it.get("create_time"),
                "update_time": it.get("update_time"),
                "title_len": len(it.get("title") or ""),
            }
        )
    return {
        "total": data.get("total"),
        "limit": data.get("limit"),
        "offset": data.get("offset"),
        "returned": len(summaries),
        "items": summaries,
    }


def fetch_and_pack(conversation_id: str, out_dir: Path) -> dict[str, Any]:
    bridge = ChatGPTBridge()
    conv = bridge.get_conversation(conversation_id)
    return export_conversation_pack(conv, out_dir)


def fetch_latest_and_pack(out_dir: Path, n: int = 1) -> dict[str, Any]:
    bridge = ChatGPTBridge()
    data = bridge.list_conversations(offset=0, limit=max(n, 1))
    items = data.get("items") or []
    packs = []
    for it in items[:n]:
        cid = it.get("id")
        if not cid:
            continue
        conv = bridge.get_conversation(cid)
        packs.append(export_conversation_pack(conv, out_dir))
    return {"total_listed": data.get("total"), "packed": packs}
