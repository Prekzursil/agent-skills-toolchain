"""ChatGPT write path — POST conversation with captured Desktop/Web body schema.

Capture evidence (2026-07-20, chrome-devtools guest send, 200 SSE):
  POST /backend-anon/f/conversation  (auth: /backend-api/f/conversation)
  Headers: openai-sentinel-*, x-conduit-token, oai-device-id, browser UA
  Body: parent_message_id=client-created-root, model=auto, modern fields

Token-consumer for auth (no refresh). Owner-authorized only.
Sentinel/Turnstile/PoW must be supplied (browser capture or solver); bare
Bearer alone yields 403 Unusual activity.
"""

from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.request
from typing import Any, Iterator

from .bridge import ChatGPTBridge
from .envelope import utc_now
from .http_secure import open_url
from .sse_contract import COMPLETE, UNCERTAIN_ACCEPTED, classify_sse

# Captured production client strings (non-secret; rotate as web app updates).
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
DEFAULT_CLIENT_VERSION = "prod-fb4a8a2a751dfec391053cfd7b01c52699ccf78c"
DEFAULT_CLIENT_BUILD = "8370486"

# Prefer /f/conversation (conduit fanout path) over legacy /conversation.
CONVERSATION_PATH = "/backend-api/f/conversation"
PREPARE_PATH = "/backend-api/f/conversation/prepare"
INIT_PATH = "/backend-api/conversation/init"


def _browser_headers(
    bridge: ChatGPTBridge,
    *,
    accept: str = "application/json",
    device_id: str | None = None,
    session_id: str | None = None,
    sentinel_chat_token: str | None = None,
    sentinel_prepare_token: str | None = None,
    sentinel_proof_token: str | None = None,
    sentinel_turnstile_token: str | None = None,
    conduit_token: str | None = None,
    turn_trace_id: str | None = None,
    originator: str = "Codex Browser",
) -> dict[str, str]:
    """Build headers matching Fiddler Desktop/Browser captures.

    Auth paid path (session 250): openai-sentinel-chat-requirements-prepare-token
    + proof + turnstile. Guest web used finalize token under
    openai-sentinel-chat-requirements-token.
    """
    bridge._maybe_reload()
    if getattr(bridge, "_snapshot", None) is None:
        raise RuntimeError("bridge has no credential snapshot")
    did = device_id or str(uuid.uuid4())
    sid = session_id or str(uuid.uuid4())
    h: dict[str, str] = bridge._snapshot.credentials.apply_to_headers(
        {
            "Content-Type": "application/json",
            "Accept": accept,
            "User-Agent": DEFAULT_UA,
            "OAI-Language": "en-US",
            "oai-language": "en-US",
            # Desktop chat uses oai-did; web also sends oai-device-id.
            "oai-did": did,
            "oai-device-id": did,
            "oai-session-id": sid,
            "oai-client-version": DEFAULT_CLIENT_VERSION,
            "oai-client-build-number": DEFAULT_CLIENT_BUILD,
            "Origin": "https://chatgpt.com",
            "Referer": "https://chatgpt.com/",
            # Chat send: Codex Browser; wham/*: Codex Desktop (Fiddler 2026-07-20).
            "originator": originator,
        }
    )
    # Duplicate account header casing used by some web clients.
    if h.get("ChatGPT-Account-Id"):
        h["chatgpt-account-id"] = h["ChatGPT-Account-Id"]
    # Paid Desktop/Browser: prepare-token header (no finalize).
    if sentinel_prepare_token:
        h["openai-sentinel-chat-requirements-prepare-token"] = sentinel_prepare_token
    # Guest web finalize token (alternate).
    if sentinel_chat_token:
        h["openai-sentinel-chat-requirements-token"] = sentinel_chat_token
    if sentinel_proof_token:
        h["openai-sentinel-proof-token"] = sentinel_proof_token
    if sentinel_turnstile_token:
        h["openai-sentinel-turnstile-token"] = sentinel_turnstile_token
    if conduit_token:
        h["x-conduit-token"] = conduit_token
    if turn_trace_id:
        h["x-oai-turn-trace-id"] = turn_trace_id
    return h


def conversation_init(bridge: ChatGPTBridge) -> dict[str, Any]:
    url = f"{bridge.base}{INIT_PATH}"
    data = json.dumps(
        {
            "requested_default_model": None,
            "conversation_id": None,
            "timezone_offset_min": -180,
            "conversation_origin": None,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=_browser_headers(bridge),
        method="POST",
    )
    with open_url(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def conversation_prepare(
    bridge: ChatGPTBridge,
    *,
    parent_message_id: str = "client-created-root",
    conversation_id: str | None = None,
    model: str = "auto",
    conduit_token: str | None = None,
    turn_trace_id: str | None = None,
    device_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """POST /f/conversation/prepare → conduit_token for x-conduit-token header."""
    body: dict[str, Any] = {
        "action": "next",
        "parent_message_id": parent_message_id,
        "model": model,
        "client_prepare_state": "none",
        "client_prepare_dispatch": "immediate",
        "client_prepare_source": "context_change",
        "timezone_offset_min": -180,
        "timezone": "Europe/Bucharest",
        "history_and_training_disabled": False,
        "conversation_mode": {"kind": "primary_assistant"},
        "system_hints": [],
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {
            "app_name": "chatgpt.com",
            "has_web_push_capabilities": True,
            "web_push_notification_permission": "default",
        },
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    url = f"{bridge.base}{PREPARE_PATH}"
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw,
        headers=_browser_headers(
            bridge,
            conduit_token=conduit_token,
            turn_trace_id=turn_trace_id,
            device_id=device_id,
            session_id=session_id,
        ),
        method="POST",
    )
    try:
        with open_url(req, timeout=30) as resp:
            return {
                "ok": True,
                "status": resp.status,
                "body": json.loads(resp.read().decode("utf-8")),
            }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status": e.code,
            "body_text": e.read().decode("utf-8", "replace")[:2000],
        }


# Work-mode handoff tool stub from Desktop auth capture (session 250).
_HANDOFF_SIGNATURE: dict[str, Any] = {
    "name": "handoff",
    "type": "kwargs",
    "description": (
        "Redirect the user's request from ChatGPT to Work mode when Work mode "
        "is the better execution environment."
    ),
    "params": [
        {
            "name": "prompt",
            "required": True,
            "type": {
                "type": "string",
                "description": "A brief instruction describing what Work mode should do for the user.",
            },
        },
        {
            "name": "reason",
            "required": True,
            "type": {
                "type": "string",
                "description": "A short user-facing reason why continuing in Work mode would help.",
            },
        },
    ],
}


def build_next_body(
    *,
    text: str,
    parent_message_id: str | None = None,
    model: str = "gpt-5-5",
    conversation_id: str | None = None,
    message_id: str | None = None,
    style: str = "desktop_auth",
    history_and_training_disabled: bool = False,
) -> dict[str, Any]:
    """Body shapes from live 200 captures.

    style=desktop_auth: Fiddler session 250 (lean auth first turn).
    style=guest_web: earlier guest chatgpt.com capture (richer fields + parent root).
    """
    mid = message_id or str(uuid.uuid4())
    now = time.time()

    if style == "desktop_auth":
        body: dict[str, Any] = {
            "action": "next",
            "local_function_signatures": [_HANDOFF_SIGNATURE],
            "messages": [
                {
                    "id": mid,
                    "author": {"role": "user", "name": None, "metadata": {}},
                    "create_time": now,
                    "update_time": None,
                    "content": {"content_type": "text", "parts": [text]},
                    "status": "finished_successfully",
                    "end_turn": None,
                    "weight": 1,
                    "metadata": {},
                    "recipient": "all",
                    "channel": None,
                }
            ],
            "model": model,
            "supported_encodings": ["v1"],
            "timezone": "Europe/Bucharest",
            "timezone_offset_min": -180,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        if parent_message_id:
            body["parent_message_id"] = parent_message_id
        return body

    # guest_web / full client shape
    body = {
        "action": "next",
        "messages": [
            {
                "id": mid,
                "author": {"role": "user"},
                "create_time": now,
                "content": {"content_type": "text", "parts": [text]},
                "metadata": {
                    "selected_github_repos": [],
                    "selected_all_github_repos": False,
                    "serialization_metadata": {"custom_symbol_offsets": []},
                },
            }
        ],
        "parent_message_id": parent_message_id or "client-created-root",
        "model": model,
        "client_prepare_state": "none",
        "timezone_offset_min": -180,
        "timezone": "Europe/Bucharest",
        "history_and_training_disabled": history_and_training_disabled,
        "conversation_mode": {"kind": "primary_assistant"},
        "enable_message_followups": True,
        "system_hints": [],
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "client_contextual_info": {
            "is_dark_mode": True,
            "time_since_loaded": 100,
            "page_height": 900,
            "page_width": 1200,
            "pixel_ratio": 1,
            "screen_height": 1080,
            "screen_width": 1920,
            "app_name": "chatgpt.com",
            "has_web_push_capabilities": True,
            "web_push_notification_permission": "default",
        },
        "paragen_cot_summary_display_override": "allow",
        "force_parallel_switch": "auto",
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    return body


def post_conversation(
    bridge: ChatGPTBridge,
    body: dict[str, Any],
    *,
    stream: bool = True,
    path: str = CONVERSATION_PATH,
    device_id: str | None = None,
    session_id: str | None = None,
    sentinel_chat_token: str | None = None,
    sentinel_prepare_token: str | None = None,
    sentinel_proof_token: str | None = None,
    sentinel_turnstile_token: str | None = None,
    conduit_token: str | None = None,
    turn_trace_id: str | None = None,
    originator: str = "Codex Browser",
) -> dict[str, Any]:
    """POST conversation. Prefer Accept: text/event-stream for real chat."""
    url = f"{bridge.base}{path}"
    accept = "text/event-stream" if stream else "application/json"
    raw = json.dumps(body).encode("utf-8")
    headers = _browser_headers(
        bridge,
        accept=accept,
        device_id=device_id,
        session_id=session_id,
        sentinel_chat_token=sentinel_chat_token,
        sentinel_prepare_token=sentinel_prepare_token,
        sentinel_proof_token=sentinel_proof_token,
        sentinel_turnstile_token=sentinel_turnstile_token,
        conduit_token=conduit_token,
        turn_trace_id=turn_trace_id,
        originator=originator,
    )
    # Match live capture routing headers.
    headers["x-openai-target-path"] = path
    headers["x-openai-target-route"] = path
    req = urllib.request.Request(url, data=raw, headers=headers, method="POST")
    try:
        with open_url(req, timeout=120) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            text = data.decode("utf-8", "replace")
            terminal = classify_sse(resp.status, text)
            status = (
                "SUCCESS"
                if terminal == COMPLETE
                else UNCERTAIN_ACCEPTED
                if terminal == UNCERTAIN_ACCEPTED
                else "FAILED"
            )
            return {
                "ok": status == "SUCCESS",
                "status": status,
                "http_ok": 200 <= resp.status < 300,
                "status_code": resp.status,
                "content_type": content_type,
                "body_len": len(data),
                "body_text": text[:8000],
                "parsed_events": list(_parse_sse(text))
                if "event-stream" in content_type
                or text.startswith("data:")
                or "event:" in text[:200]
                else None,
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")
        return {
            "ok": False,
            "status": "FAILED",
            "http_ok": False,
            "status_code": e.code,
            "body_text": err_body[:2000],
        }


def _parse_sse(text: str) -> Iterator[dict[str, Any]]:
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            yield {"done": payload == "[DONE]"}
            continue
        try:
            yield json.loads(payload)
        except Exception:
            yield {"raw": payload[:200]}


def send_message(
    text: str,
    *,
    conversation_id: str | None = None,
    model: str | None = None,
    new_conversation: bool = False,
    sentinel_chat_token: str | None = None,
    sentinel_prepare_token: str | None = None,
    sentinel_proof_token: str | None = None,
    sentinel_turnstile_token: str | None = None,
    conduit_token: str | None = None,
    style: str = "desktop_auth",
    auto_sentinel: bool = True,
) -> dict[str, Any]:
    """High-level send using Desktop auth schema + local PoW.

    By default acquires prepare_token + solves proofofwork (sha3_512).
    Paid accounts accept prepare+proof without Turnstile (proven 2026-07-20).
    Pass explicit tokens to skip auto acquisition.
    """
    bridge = ChatGPTBridge()
    device_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    turn_trace_id = str(uuid.uuid4())
    report: dict[str, Any] = {
        "at": utc_now(),
        "text_len": len(text),
        "new_conversation": new_conversation,
        "endpoint": CONVERSATION_PATH,
        "style": style,
        "capture_ref": "reports/write_path_desktop_auth_capture_2026-07-20.md",
        "sentinel_prepare_present": bool(sentinel_prepare_token),
        "sentinel_finalize_present": bool(sentinel_chat_token),
        "auto_sentinel": auto_sentinel,
    }

    try:
        init = conversation_init(bridge)
        report["init"] = {
            "type": init.get("type"),
            "default_model_slug": init.get("default_model_slug"),
        }
        model = model or init.get("default_model_slug") or "gpt-5-5"
    except Exception as e:
        report["init_error"] = str(e)[:300]
        model = model or "gpt-5-5"

    parent_id: str | None = None
    conv_id = conversation_id

    if not new_conversation:
        if not conv_id:
            items = bridge.list_conversations(0, 1).get("items") or []
            if items:
                conv_id = items[0].get("id")
        if conv_id:
            conv = bridge.get_conversation(conv_id)
            parent_id = conv.get("current_node")
            conv_id = conv.get("conversation_id") or conv.get("id") or conv_id
            report["parent_message_id"] = parent_id
            report["conversation_id"] = conv_id
            report["title"] = conv.get("title")
        else:
            new_conversation = True
            report["new_conversation"] = True

    if new_conversation:
        # Auth Desktop first turn: omit conversation_id + parent (server assigns).
        conv_id = None
        parent_id = None if style == "desktop_auth" else "client-created-root"
        report["mode"] = (
            "desktop_auth_first_turn"
            if style == "desktop_auth"
            else "client-created-root"
        )
        report["parent_message_id"] = parent_id

    body = build_next_body(
        text=text,
        parent_message_id=parent_id,
        model=model or "gpt-5-5",
        conversation_id=conv_id,
        style=style,
    )
    report["request_body_keys"] = sorted(body.keys())
    report["model"] = model

    # Sentinel last: prepare+PoW immediately before POST (tokens are short-lived;
    # earlier conduit/init chatter can invalidate them — proved 2026-07-20).
    if auto_sentinel and not (sentinel_prepare_token and sentinel_proof_token):
        try:
            from .sentinel import acquire_sentinel_tokens

            acq = acquire_sentinel_tokens(
                bridge,
                device_id=device_id,
                session_id=session_id,
                turnstile_token=sentinel_turnstile_token,
                originator="Codex Browser",
            )
            report["sentinel"] = {
                "persona": acq.get("persona"),
                "pow": acq.get("pow"),
                "turnstile_required": acq.get("turnstile_required"),
            }
            device_id = acq.get("device_id") or device_id
            session_id = acq.get("session_id") or session_id
            sentinel_prepare_token = sentinel_prepare_token or acq.get("prepare_token")
            sentinel_proof_token = sentinel_proof_token or acq.get("proof_token")
            if acq.get("turnstile_token") and not sentinel_turnstile_token:
                sentinel_turnstile_token = acq.get("turnstile_token")
            report["sentinel_prepare_present"] = bool(sentinel_prepare_token)
            report["sentinel_proof_present"] = bool(sentinel_proof_token)
        except Exception as e:
            report["sentinel_error"] = f"{type(e).__name__}: {e}"[:400]
            report["success"] = False
            report["blocker"] = "sentinel_pow_failed"
            return report

    if auto_sentinel and not (sentinel_prepare_token and sentinel_proof_token):
        report["success"] = False
        report["blocker"] = "sentinel_tokens_missing"
        return report

    # Conduit is optional; Desktop capture often posted without a request x-conduit-token.
    report["has_conduit"] = bool(conduit_token)

    result = post_conversation(
        bridge,
        body,
        stream=True,
        device_id=device_id,
        session_id=session_id,
        sentinel_chat_token=sentinel_chat_token,
        sentinel_prepare_token=sentinel_prepare_token,
        sentinel_proof_token=sentinel_proof_token,
        sentinel_turnstile_token=sentinel_turnstile_token,
        conduit_token=conduit_token,
        turn_trace_id=turn_trace_id,
        originator="Codex Browser",
    )
    report["stream_attempt"] = {
        "ok": result.get("ok"),
        "status": result.get("status"),
        "http_ok": result.get("http_ok"),
        "status_code": result.get("status_code"),
        "content_type": result.get("content_type"),
        "body_prefix": (result.get("body_text") or "")[:500],
        "event_count": len(result.get("parsed_events") or [])
        if result.get("parsed_events") is not None
        else None,
    }
    report["ok"] = bool(result.get("ok"))
    report["status"] = result.get("status")
    report["http_ok"] = bool(result.get("http_ok"))
    report["status_code"] = result.get("status_code")

    if result.get("ok"):
        report["success"] = True
        report["response"] = {
            "status": result.get("status"),
            "http_ok": result.get("http_ok"),
            "status_code": result.get("status_code"),
            "body_prefix": (result.get("body_text") or "")[:800],
            "events_sample": (result.get("parsed_events") or [])[:5],
        }
    elif not result.get("http_ok"):
        # Legacy path fallback for diagnosis.
        legacy = post_conversation(
            bridge,
            body,
            stream=True,
            path="/backend-api/conversation",
            device_id=device_id,
            session_id=session_id,
            sentinel_chat_token=sentinel_chat_token,
            sentinel_prepare_token=sentinel_prepare_token,
            sentinel_proof_token=sentinel_proof_token,
            sentinel_turnstile_token=sentinel_turnstile_token,
            conduit_token=conduit_token,
            turn_trace_id=turn_trace_id,
            originator="Codex Browser",
        )
        report["legacy_conversation_path"] = {
            "ok": legacy.get("ok"),
            "status": legacy.get("status"),
            "http_ok": legacy.get("http_ok"),
            "status_code": legacy.get("status_code"),
            "body_prefix": (legacy.get("body_text") or "")[:400],
        }
        report["ok"] = bool(legacy.get("ok"))
        report["status"] = legacy.get("status")
        report["http_ok"] = bool(legacy.get("http_ok"))
        report["status_code"] = legacy.get("status_code")
        if legacy.get("ok"):
            report["success"] = True
            report["success_path"] = "/backend-api/conversation"
        else:
            report["success"] = False
            report["blocker"] = (
                "bot_defense_sentinel"
                if "Unusual activity" in (result.get("body_text") or "")
                else "http_error"
            )
            report["next"] = (
                "PoW/prepare failed or blocked. Re-run with auto_sentinel=True "
                "(default) or pass capture tokens; Turnstile only if paid path rejects."
            )
    else:
        # A 2xx response can still be explicitly failed or lack terminal
        # evidence.  Do not retry on the legacy path: the turn may have been
        # accepted and a second POST could duplicate the user's message.
        report["success"] = False
        report["blocker"] = (
            "sse_terminal_error"
            if result.get("status") == "FAILED"
            else "sse_terminal_uncertain"
        )

    return report
