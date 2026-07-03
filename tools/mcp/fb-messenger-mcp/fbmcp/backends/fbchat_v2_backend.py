"""Default T4 E2EE backend: wraps the pip `fbchat-v2` library (v2.1.6+).

fbchat-v2 (MIT, Python) spawns a compiled mautrix/meta Go bridge (AGPL-3.0)
via its internal `_BridgeProcess` and speaks stdio JSON-RPC to it. It handles
Messenger's Labyrinth E2EE for personal 1:1 DMs, authenticated with the same
facebook.com cookies (c_user/xs/datr/fr).

Mapping to the real v2.1.6 API (verified against the installed package):
  * auth   fbchat_v2.dataGetHome("<raw cookie header>")  -> dataFB
  * list   fbchat_v2._features._thread._all_thread_data.func(dataFB) -> {"dataGet": ...}
           (dataAllThread lists GROUPS only; DMs are parsed out of dataGet)
  * send   api(dataFB=dataFB).connect(enable_e2ee=True); api.send(chat_jid, text)
           -> {"success": 1, "payload": {...}} | {"error": 1, "payload": {...}}
  * react  api.bridge.call("sendE2EEReaction", {chatJid, messageId, senderJid, emoji})
  * read   listeningE2EEEvent(dataFB) live listener (NO history/backfill RPC exists)

fbchat-v2's calls are synchronous/blocking, so every one runs in a worker
thread via asyncio.to_thread to keep the MCP event loop responsive.

NOTE (honesty): send is param-verified against the real API but runtime-
untested here (needs live FB cookies + the Go bridge binary). It reports
sent=True ONLY when the bridge returns {"success": 1}.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
import time
from typing import Any, Iterator, Optional

from ._cookies import cookie_header, missing_e2ee_cookies

DEFAULT_JID_SUFFIX = "@s.whatsapp.net"  # per fbchat-v2 api.send() DM docstring

# Proxy env vars every egress path in this backend honors:
#   * Python `requests` (dataGetHome / _all_thread_data): default Session has
#     trust_env=True and these calls pass NO proxies=, so HTTP(S)_PROXY/ALL_PROXY
#     from the environment are used.
#   * the mautrix/meta Go bridge subprocess: fbchat-v2's _BridgeProcess spawns it
#     via subprocess.Popen WITHOUT env=, so it inherits os.environ at spawn time,
#     and Go's http.ProxyFromEnvironment reads HTTP(S)_PROXY.
# fbchat-v2 exposes no proxy/session parameter anywhere (verified against 2.1.6),
# so routing FB_DM_PROXY through these env vars for the duration of each call is
# the only scoped way to proxy both paths without a permanent global proxy.
_PROXY_ENV_KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY")

# Serializes the os.environ mutation so two concurrent DM calls cannot interleave
# their save/restore and leak the proxy into the parent process. Only ever
# acquired from asyncio.to_thread worker threads, so it never blocks the event
# loop (a threading.Lock held across an await would).
_PROXY_ENV_LOCK = threading.Lock()


class FbchatV2Backend:
    """E2EE 1:1 DM backend built on fbchat-v2 + the mautrix/meta Go bridge."""

    def __init__(
        self,
        cookies_path: str,
        proxy: Optional[str] = None,
        jid_suffix: Optional[str] = None,
        binary_path: Optional[str] = None,
    ) -> None:
        self.cookies_path = cookies_path
        self.proxy = proxy
        self.jid_suffix = jid_suffix or os.environ.get(
            "FB_DM_JID_SUFFIX", DEFAULT_JID_SUFFIX
        )
        self.binary_path = binary_path or os.environ.get("FBCHAT_E2EE_BIN") or None
        self._dataFB: Optional[dict] = None

    # -- library access (lazy) -------------------------------------------- #
    @staticmethod
    def _lib():
        """Import the exact fbchat-v2 symbols we call (raises if absent)."""
        import fbchat_v2
        from fbchat_v2._features._thread._all_thread_data import func as list_func
        from fbchat_v2._messaging._listening_e2ee import listeningE2EEEvent
        from fbchat_v2._messaging._send_e2ee import api as SendApi

        return fbchat_v2.dataGetHome, list_func, SendApi, listeningE2EEEvent

    def _to_jid(self, thread_id: str) -> str:
        """Full JID pass-through; bare numeric id gets the DM suffix appended."""
        s = str(thread_id)
        return s if "@" in s else f"{s}{self.jid_suffix}"

    async def _data_fb(self) -> dict:
        if self._dataFB is None:
            data_get_home, *_ = self._lib()
            header = cookie_header(self.cookies_path)

            def _call() -> dict:
                with self._proxy_env():  # proxy the dataGetHome requests.get
                    return data_get_home(header)

            self._dataFB = await asyncio.to_thread(_call)
        return self._dataFB

    def _new_sender(self, SendApi, data_fb):
        """Construct a standalone sender, tolerating older kwarg sets."""
        try:
            return SendApi(
                dataFB=data_fb, e2ee_memory_only=True, binary_path=self.binary_path
            )
        except TypeError:
            return SendApi(dataFB=data_fb)

    @contextlib.contextmanager
    def _proxy_env(self) -> Iterator[None]:
        """Route FB_DM_PROXY through the wrapped egress, and ONLY that egress.

        Sets HTTP(S)_PROXY/ALL_PROXY for the duration of the wrapped call so both
        the Python `requests` calls and the inherited Go-bridge subprocess send
        their traffic through the proxy, then restores the previous environment
        EXACTLY (absent vars removed, prior values put back). The parent process
        is therefore never left with a global proxy, so no other tool's traffic
        is affected.

        When ``self.proxy`` is falsy this is a no-op: egress stays direct, exactly
        as before FB_DM_PROXY was wired in.

        MUST be entered from within an asyncio.to_thread worker (the module lock
        would block the event loop otherwise).
        """
        if not self.proxy:
            yield
            return
        with _PROXY_ENV_LOCK:
            saved = {key: os.environ.get(key) for key in _PROXY_ENV_KEYS}
            try:
                for key in _PROXY_ENV_KEYS:
                    os.environ[key] = self.proxy
                yield
            finally:
                for key, prior in saved.items():
                    if prior is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = prior

    # -- interface -------------------------------------------------------- #
    async def status(self) -> dict:
        missing = missing_e2ee_cookies(self.cookies_path)
        lib_ok = True
        bin_ok = True
        reason = ""
        try:
            self._lib()
        except Exception as exc:  # library not installed
            lib_ok = False
            reason = f"fbchat-v2 not importable: {exc!r}"
        if lib_ok:
            try:
                from fbchat_v2._messaging._listening_e2ee import _resolve_binary

                await asyncio.to_thread(_resolve_binary)
            except Exception as exc:  # bridge binary missing / not downloaded
                bin_ok = False
                reason = reason or f"go bridge binary not resolved: {exc!r}"
        ready = not missing and lib_ok and bin_ok
        if missing and not reason:
            reason = f"missing required cookies: {missing}"
        return {
            "ready": ready,
            "missing_cookies": missing,
            "lib_installed": lib_ok,
            "bridge_binary_found": bin_ok,
            "jid_suffix": self.jid_suffix,
            "proxy_set": bool(self.proxy),
            "reason": reason or "ok",
        }

    async def list_threads(self, limit: int = 20) -> Any:
        _, list_func, *_ = self._lib()
        data_fb = await self._data_fb()

        def _call() -> dict:
            with self._proxy_env():  # proxy the _all_thread_data requests.post
                return list_func(data_fb)

        result = await asyncio.to_thread(_call)
        return self._parse_dms(result, limit)

    def _parse_dms(self, result: dict, limit: int) -> dict:
        raw = result.get("dataGet") if isinstance(result, dict) else None
        try:
            nodes = json.loads(raw)["o0"]["data"]["viewer"]["message_threads"]["nodes"]
        except Exception as exc:
            return {
                "error": f"could not parse DM thread list: {exc!r}",
                "group_threads": (result or {}).get("dataAllThread"),
            }
        dms = []
        for node in nodes:
            tk = node.get("thread_key") or {}
            other = tk.get("other_user_id")
            if tk.get("thread_fbid") is None and other:
                dms.append(
                    {
                        "other_user_id": other,
                        "name": node.get("name"),
                        "thread_jid": self._to_jid(other),
                    }
                )
            if len(dms) >= limit:
                break
        return {
            "dms": dms,
            "count": len(dms),
            "note": "1:1 E2EE DM threads (group threads excluded).",
        }

    async def send(self, thread_id: str, text: str) -> Any:
        _, _, SendApi, _ = self._lib()
        data_fb = await self._data_fb()
        jid = self._to_jid(thread_id)

        def _do():
            with self._proxy_env():  # bridge subprocess inherits proxy at Popen
                sender = self._new_sender(SendApi, data_fb)
                sender.connect(enable_e2ee=True)
                try:
                    return sender.send(jid, text)
                finally:
                    sender.close()

        return await asyncio.to_thread(_do)

    async def react(
        self,
        thread_id: str,
        message_id: str,
        emoji: str,
        author_id: Optional[str] = None,
    ) -> Any:
        _, _, SendApi, _ = self._lib()
        data_fb = await self._data_fb()
        chat_jid = self._to_jid(thread_id)
        sender_jid = self._to_jid(author_id or thread_id)

        def _do():
            with self._proxy_env():  # bridge subprocess inherits proxy at Popen
                sender = self._new_sender(SendApi, data_fb)
                sender.connect(enable_e2ee=True)
                try:
                    return sender.bridge.call(
                        "sendE2EEReaction",
                        {
                            "chatJid": chat_jid,
                            "messageId": message_id,
                            "senderJid": sender_jid,
                            "emoji": emoji,
                        },
                    )
                finally:
                    sender.close()

        return await asyncio.to_thread(_do)

    async def read_thread(
        self, thread_id: str, limit: int = 20, listen_seconds: Optional[float] = None
    ) -> Any:
        _, _, _, Listener = self._lib()
        data_fb = await self._data_fb()
        secs = (
            listen_seconds
            if listen_seconds is not None
            else float(os.environ.get("FB_DM_LISTEN_SECONDS", "20"))
        )
        want = str(thread_id).split("@")[0]

        def _do():
            events: list = []
            with self._proxy_env():  # listener-init requests + bridge Popen
                try:
                    listener = Listener(data_fb, binary_path=self.binary_path)
                except TypeError:
                    listener = Listener(data_fb)

                @listener.on_message
                def _handler(evt):  # pragma: no cover - runtime callback
                    if evt.get("type") == "e2eeMessage":
                        data = evt.get("data", {})
                        if str(data.get("chatJid", "")).split("@")[0] == want:
                            events.append(data)

                thread = threading.Thread(target=listener.connect_mqtt, daemon=True)
                thread.start()
                time.sleep(secs)
                try:
                    listener.stop()
                except Exception:
                    pass  # nosec B110 - best-effort listener stop during teardown
            return events[:limit]

        events = await asyncio.to_thread(_do)
        return {
            "messages": events,
            "count": len(events),
            "note": (
                f"LIVE capture only: the fbchat-v2 bridge has no history/backfill "
                f"RPC. Only messages received during the {secs:g}s listen window "
                f"are returned."
            ),
        }
