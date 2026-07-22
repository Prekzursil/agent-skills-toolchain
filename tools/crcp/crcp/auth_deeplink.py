"""Build and open the registered ChatGPT Desktop ``codex://`` protocol.

Deep links are navigation hints for the packaged desktop application.  They are
not an authentication transport and this module never adds OAuth credentials.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from typing import Any
from urllib.parse import quote, urlencode, urlsplit


CODEX_SCHEME = "codex"


def build_codex_deeplink(
    *,
    path: str = "",
    query: dict[str, Any] | None = None,
) -> str:
    """Return a ``codex://`` URL with a safely encoded path and query.

    ``path`` is treated as the portion following ``codex://``; leading slashes
    are ignored so both ``"open"`` and ``"/open"`` produce ``codex://open``.
    Sequence query values are expanded in the conventional ``doseq`` form.
    """

    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if query is not None and not isinstance(query, dict):
        raise TypeError("query must be a dict or None")

    normalized_path = path.lstrip("/")
    encoded_path = quote(normalized_path, safe="/:@-._~!$&'()*+,;=")
    url = f"{CODEX_SCHEME}://{encoded_path}"
    if query:
        url = f"{url}?{urlencode(query, doseq=True)}"
    return url


def _windows_shell_execute(url: str) -> None:
    """Open *url* through the Windows shell when ``os.startfile`` is absent."""

    result = ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
    if result <= 32:
        raise OSError("ShellExecuteW failed")


def open_deeplink(url: str) -> dict[str, Any]:
    """Ask the operating system to open a ``codex://`` URL.

    Launching is asynchronous.  ``ok`` therefore means the request was handed
    to the OS successfully, not that Desktop completed the requested action.
    Errors are reduced to exception class names so command details and URL
    query values cannot be copied into diagnostics.
    """

    if not isinstance(url, str) or not url:
        return {
            "ok": False,
            "url": url,
            "method": "validation",
            "error": "url must be a non-empty string",
        }

    try:
        parsed = urlsplit(url)
    except ValueError:
        return {
            "ok": False,
            "url": url,
            "method": "validation",
            "error": "invalid URL",
        }
    if parsed.scheme.lower() != CODEX_SCHEME:
        return {
            "ok": False,
            "url": url,
            "method": "validation",
            "error": "only codex:// deep links are supported",
        }

    method: str
    try:
        if os.name == "nt":
            startfile = getattr(os, "startfile", None)
            if callable(startfile):
                method = "os.startfile"
                startfile(url)
            else:
                method = "ShellExecuteW"
                _windows_shell_execute(url)
        elif sys.platform == "darwin":
            method = "open"
            subprocess.Popen(
                ["open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            method = "xdg-open"
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "method": method,
            "error": type(exc).__name__,
        }
    return {"ok": True, "url": url, "method": method}


def describe_protocol_registration() -> dict[str, Any]:
    """Describe the protocol facts measured on the Windows Desktop install."""

    return {
        "registered_scheme": "codex://",
        "registered_on": "Windows MSIX AppxManifest",
        "chatgpt_scheme_registered": False,
        "chatgpt_scheme": "chatgpt://",
        "opens_packaged_app": True,
        "carries_oauth_tokens": False,
        "authentication_transport": False,
        "limits": [
            "Only codex:// was observed as registered on the measured Windows install.",
            "Deep links open the packaged app but do not establish a web session.",
            "Deep links do not carry OAuth tokens.",
        ],
    }


def run_deeplink_cli(action: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch the programmatic ``status``, ``build``, and ``open`` actions."""

    normalized_action = str(action).strip().lower()
    if normalized_action == "status":
        return {"ok": True, "action": "status", **describe_protocol_registration()}
    if normalized_action == "build":
        try:
            url = build_codex_deeplink(
                path=kwargs.get("path", ""),
                query=kwargs.get("query"),
            )
        except (TypeError, ValueError) as exc:
            return {
                "ok": False,
                "action": "build",
                "error": str(exc),
            }
        return {"ok": True, "action": "build", "url": url, "method": "build"}
    if normalized_action == "open":
        url = kwargs.get("url")
        if url is None:
            return {
                "ok": False,
                "action": "open",
                "error": "url is required",
            }
        result = open_deeplink(url)
        result["action"] = "open"
        return result
    return {
        "ok": False,
        "action": normalized_action,
        "error": "action must be one of: status, build, open",
    }


__all__ = [
    "build_codex_deeplink",
    "describe_protocol_registration",
    "open_deeplink",
    "run_deeplink_cli",
]
