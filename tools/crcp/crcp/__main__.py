"""CLI: python -m crcp <command> ..."""

from __future__ import annotations

import argparse
import base64
import hashlib
import inspect
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import __version__
from .auth import full_auth_status
from .bridge import fetch_and_pack, fetch_latest_and_pack, list_summaries
from .bus import DEFAULT_PROJECT
from .health import full_health, health_table, write_wfmon_snippet
from .inbox import scan_inbox, watch_inbox
from .live_bridge import run_live_bridge
from .publish import publish_file, publish_outbox
from .token_watch import watch_auth_json
from .wfmon_export import build_wfmon_report


class AuthCliConfigError(RuntimeError):
    """A missing module, incompatible API, or invalid auth CLI setting."""


_SECRET_KEYS = {
    "access_token",
    "authorization",
    "client_secret",
    "code",
    "code_verifier",
    "cookie",
    "cookie_value",
    "encrypted_value",
    "id_token",
    "jwt",
    "refresh_token",
    "session_token",
    "token",
    "value",
    "verifier",
}


def _crcp_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _redact(data: Any) -> Any:
    """Recursively remove credential values before terminal output."""
    if isinstance(data, dict):
        clean: dict[str, Any] = {}
        for key, value in data.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SECRET_KEYS or normalized.endswith("_token"):
                clean[str(key)] = "[REDACTED]"
            elif normalized in {"url", "authorize_url"} and isinstance(value, str):
                clean[str(key)] = _redact_url(value)
            else:
                clean[str(key)] = _redact(value)
        return clean
    if isinstance(data, (list, tuple)):
        return [_redact(item) for item in data]
    if isinstance(data, bytes):
        return {"type": "bytes", "length": len(data)}
    return data


def _redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            normalized = key.lower().replace("-", "_")
            if normalized in _SECRET_KEYS or normalized.endswith("_token"):
                value = "[REDACTED]"
            query.append((key, value))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
    except ValueError:
        return "[INVALID URL]"


def _print_json(data: object) -> None:
    print(json.dumps(_redact(data), indent=2, default=str))


def _livez() -> dict[str, object]:
    return {"live": True, "status": "LIVE"}


def _health_with_probes() -> dict[str, Any]:
    report = full_health()
    operational = build_wfmon_report(report, root=_crcp_root())
    report["livez"] = _livez()
    report["readyz"] = operational["readyz"]
    return report


def _auth_import(module: str, *names: str) -> tuple[Any, ...]:
    try:
        imported = __import__(f"{__package__}.{module}", fromlist=list(names))
        return tuple(getattr(imported, name) for name in names)
    except (ImportError, AttributeError) as exc:
        raise AuthCliConfigError(
            f"auth integration unavailable: {module} must provide {', '.join(names)}"
        ) from exc


def _invoke(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Invoke an evolving sibling API, rejecting unsupported explicit options."""
    signature = inspect.signature(function)
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    unsupported = [
        key
        for key, value in kwargs.items()
        if value is not None and key not in signature.parameters
    ]
    if unsupported and not accepts_kwargs:
        raise AuthCliConfigError(
            f"installed {function.__module__}.{function.__name__} does not support: "
            + ", ".join(sorted(unsupported))
        )
    passed = (
        kwargs
        if accepts_kwargs
        else {
            key: value for key, value in kwargs.items() if key in signature.parameters
        }
    )
    return function(*args, **passed)


def _invoke_with_user_data(
    function: Callable[..., Any],
    module: Any,
    user_data: Path | None,
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Bridge older mirror APIs while keeping the profile override scoped."""
    if user_data is None or "user_data" in inspect.signature(function).parameters:
        return _invoke(function, *args, user_data=user_data, **kwargs)
    default_path = getattr(module, "default_user_data_dir", None)
    if not callable(default_path):
        raise AuthCliConfigError(
            f"installed {function.__module__}.{function.__name__} cannot honor --user-data"
        )
    module.default_user_data_dir = lambda: user_data
    try:
        return _invoke(function, *args, **kwargs)
    finally:
        module.default_user_data_dir = default_path


def _exit_for(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    if (
        result.get("ok") is False
        or result.get("success") is False
        or result.get("error")
    ):
        return 1
    if str(result.get("status", "")).lower() in {
        "error",
        "failed",
        "failure",
        "soft_fail",
    }:
        return 1
    return 0


def _emit(result: Any) -> int:
    _print_json(result if result is not None else {"ok": True})
    return _exit_for(result)


def _parse_query(items: list[str]) -> dict[str, str]:
    query: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise AuthCliConfigError("invalid --query item; expected KEY=VAL")
        key, value = item.split("=", 1)
        if not key:
            raise AuthCliConfigError("--query key cannot be empty")
        query[key] = value
    return query


def cmd_auth_mirror(args: argparse.Namespace) -> int:
    inventory, export = _auth_import(
        "auth_mirror", "run_mirror_inventory", "run_mirror_export"
    )
    module = sys.modules.get(f"{__package__}.auth_mirror")
    user_data = Path(args.user_data).expanduser() if args.user_data else None
    if args.export:
        result = _invoke_with_user_data(
            export,
            module,
            user_data,
            Path(args.export).expanduser(),
            decrypt=args.decrypt,
        )
    else:
        if args.decrypt:
            raise AuthCliConfigError("--decrypt requires --export DIR")
        result = _invoke_with_user_data(inventory, module, user_data)
    return _emit(result)


def cmd_auth_deeplink_build(args: argparse.Namespace) -> int:
    (build,) = _auth_import("auth_deeplink", "build_codex_deeplink")
    url = build(path=args.path, query=_parse_query(args.query))
    return _emit({"ok": True, "url": url})


def cmd_auth_deeplink_open(args: argparse.Namespace) -> int:
    (open_link,) = _auth_import("auth_deeplink", "open_deeplink")
    return _emit(open_link(args.url))


def cmd_auth_deeplink_status(_args: argparse.Namespace) -> int:
    (run_cli,) = _auth_import("auth_deeplink", "run_deeplink_cli")
    return _emit(run_cli("status"))


def _redirect_uri(value: str | None) -> str:
    redirect = value or os.environ.get("CRCP_OAUTH_REDIRECT_URI")
    if not redirect:
        try:
            from .auth_sso import DEFAULT_REDIRECT_URI as _default_redirect
        except Exception:  # pragma: no cover - module optional during partial apply
            _default_redirect = "http://127.0.0.1:1455/auth/callback"
        redirect = _default_redirect
    return redirect


def cmd_auth_sso_login(args: argparse.Namespace) -> int:
    (login,) = _auth_import("auth_sso", "run_sso_login")
    kwargs: dict[str, Any] = {
        "open_browser": not args.print_url,
        "print_url": args.print_url,
        "timeout_s": args.timeout,
    }
    if args.redirect_uri is not None:
        kwargs["redirect_uri"] = args.redirect_uri
    verifier = os.environ.get("CRCP_OAUTH_CODE_VERIFIER")
    if verifier:
        kwargs["code_verifier"] = verifier
    if args.code is not None:
        kwargs["code"] = args.code
        if not verifier:
            raise AuthCliConfigError(
                "--code requires CRCP_OAUTH_CODE_VERIFIER from the matching PKCE request"
            )
    return _emit(_invoke(login, **kwargs))


def cmd_auth_sso_authorize_url(args: argparse.Namespace) -> int:
    module_name = "auth_sso"
    (build,) = _auth_import(module_name, "build_authorize_url")
    module = sys.modules.get(f"{__package__}.{module_name}")
    client_id = os.environ.get(
        "CRCP_OAUTH_CLIENT_ID",
        getattr(module, "DEFAULT_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann"),
    )
    scopes = getattr(module, "DEFAULT_SCOPES", "openid profile email offline_access")
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    url = build(
        _redirect_uri(args.redirect_uri),
        client_id=client_id,
        scopes=scopes,
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_challenge=challenge,
    )
    return _emit(
        {
            "ok": True,
            "authorize_url": url,
            "note": "URL preview only; use `auth sso login --print-url` for a completable PKCE flow.",
        }
    )


def cmd_auth_broker(args: argparse.Namespace) -> int:
    """Browser broker: Desktop cookies+Bearer, or phone-store NextAuth apply."""
    out = _crcp_root() / "reports" / "auth_broker_last.json"

    def _persist(result: Any) -> None:
        try:
            safe = json.loads(json.dumps(result, default=str))
            out.write_text(json.dumps(safe, indent=2), encoding="utf-8")
            print(f"# wrote {out}", file=sys.stderr)
        except Exception:
            pass

    if getattr(args, "desktop_cdp_inventory", False):
        (inventory,) = _auth_import("auth_broker", "run_desktop_cdp_inventory")
        result = inventory(port=args.port)
        _persist(result)
        return _emit(result)

    if getattr(args, "phone_status", False):
        (status_fn,) = _auth_import("auth_broker", "phone_store_status")
        result = status_fn()
        _persist(result)
        return _emit(result)

    if getattr(args, "from_phone_store", False) or getattr(
        args, "phone_extract", False
    ):
        (run_phone,) = _auth_import("auth_broker", "run_from_phone_store")
        phone_browser = getattr(args, "phone_browser", None) or "chrome"
        # Default phone-store port is 9340 unless user overrode --port from desktop default
        port = args.port
        if port in (9333, 9222) and not getattr(args, "port_explicit", False):
            port = 9340
        # If user passed --port, argparse always sets it; detect "explicit" via env or always honor --port
        # Honor args.port always when provided; use 9340 when still at desktop default 9333.
        if args.port == 9333:
            port = 9340
        else:
            port = args.port
        result = _invoke(
            run_phone,
            browser=phone_browser,
            port=port,
            extract_first=bool(getattr(args, "phone_extract", False)),
        )
        _persist(result)
        return _emit(result)

    (run_broker,) = _auth_import("auth_broker", "run_broker")
    kwargs: dict[str, Any] = {
        "port": args.port,
        "start_url": args.url,
        "attach_only": args.attach,
        "skip_cookies": args.no_cookies,
        "skip_bearer": args.no_bearer,
        "keep_open": not args.close,
    }
    if args.profile:
        kwargs["profile_dir"] = Path(args.profile).expanduser()
    if args.desktop_user_data:
        kwargs["desktop_user_data"] = Path(args.desktop_user_data).expanduser()
    if args.browser:
        kwargs["browser_path"] = args.browser
    result = _invoke(run_broker, **kwargs)
    _persist(result)
    return _emit(result)


def cmd_auth_status(_args: argparse.Namespace) -> int:
    report = full_auth_status()
    _print_json(report)
    out = _crcp_root() / "reports" / "auth_status_live.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"# wrote {out}", file=sys.stderr)
    return 0 if report.get("overall") == "GREEN" else 1


def cmd_health(args: argparse.Namespace) -> int:
    report = _health_with_probes()
    if args.json:
        _print_json(report)
    else:
        print(health_table(report))
        _print_json({"livez": report["livez"], "readyz": report["readyz"]})
        if args.verbose:
            _print_json({k: v for k, v in report["rails"].items()})
    out = _crcp_root() / "reports" / "health_live.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    snippet = _crcp_root() / "reports" / "wfmon_crcp_health.json"
    write_wfmon_snippet(report, snippet)
    print(f"# wrote {out}", file=sys.stderr)
    print(f"# wrote {snippet}", file=sys.stderr)
    return 0 if report.get("overall") == "GREEN" else 1


def cmd_livez(_args: argparse.Namespace) -> int:
    _print_json(_livez())
    return 0


def cmd_readyz(_args: argparse.Namespace) -> int:
    readyz = _health_with_probes()["readyz"]
    _print_json(readyz)
    return 0 if readyz.get("ready") else 1


def cmd_chatgpt_list(args: argparse.Namespace) -> int:
    _print_json(list_summaries(limit=args.limit))
    return 0


def cmd_chatgpt_fetch(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else _crcp_root() / "outbox"
    result = (
        fetch_and_pack(args.id, out_dir)
        if args.id
        else fetch_latest_and_pack(out_dir, n=args.latest)
    )
    _print_json(result)
    return 0


def cmd_chatgpt_live(args: argparse.Namespace) -> int:
    result = run_live_bridge(
        poll_interval=args.poll_interval,
        auto_publish=not args.no_publish,
        once=args.once,
        http_port=args.http_port,
        enable_http=not args.no_http,
    )
    if args.once:
        _print_json(result)
    return 0 if not (result.get("errors") if isinstance(result, dict) else None) else 1


def cmd_chatgpt_send(args: argparse.Namespace) -> int:
    from .write_path import send_message

    result = send_message(
        args.text,
        conversation_id=args.conversation_id,
        model=args.model,
        new_conversation=args.new,
        auto_sentinel=not args.no_sentinel,
    )
    _print_json(result)
    out = _crcp_root() / "reports" / "chatgpt_send_last.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"# wrote {out}", file=sys.stderr)
    return 0 if result.get("success") else 1


def cmd_auth_watch(args: argparse.Namespace) -> int:
    result = watch_auth_json(interval_sec=args.interval, once=args.once)
    if args.once:
        _print_json(result)
    return 0


def cmd_bus_register_grok(args: argparse.Namespace) -> int:
    from .bus import (
        AgentMailRpc,
        DEFAULT_DB,
        ensure_contact,
        load_or_register_bridge_agent,
        tool_call,
    )
    import sqlite3
    import uuid

    project = args.project or DEFAULT_PROJECT
    rpc = AgentMailRpc()
    rpc.initialize()
    tool_call(rpc, "ensure_project", {"human_key": project})
    grok_name, grok_tok = load_or_register_bridge_agent(
        rpc, project, program="grok-node", model="grok-build"
    )
    con = sqlite3.connect(f"file:{DEFAULT_DB}?mode=ro", uri=True)
    rows = con.execute(
        "select a.name, a.registration_token, a.program from agents a join projects p on p.id=a.project_id "
        "where p.human_key=? and a.retired_at is null order by a.id desc",
        (project,),
    ).fetchall()
    con.close()
    by_prog: dict[str, tuple[str, str]] = {}
    for name, token, program in rows:
        by_prog.setdefault(program, (name, token))
    for program, model in (
        ("claude-orchestrator", "claude"),
        ("codex-executor", "codex"),
    ):
        if program not in by_prog:
            by_prog[program] = load_or_register_bridge_agent(
                rpc, project, program=program, model=model
            )
    by_prog["grok-node"] = (grok_name, grok_tok)
    c_name, c_tok = by_prog["claude-orchestrator"]
    x_name, x_tok = by_prog["codex-executor"]
    g_name, g_tok = by_prog["grok-node"]
    for a, at, b, bt in (
        (g_name, g_tok, c_name, c_tok),
        (g_name, g_tok, x_name, x_tok),
        (c_name, c_tok, g_name, g_tok),
        (x_name, x_tok, g_name, g_tok),
    ):
        ensure_contact(rpc, project, a, at, b, bt)
    marker = f"CRCP-P3-GROK-3WAY {uuid.uuid4().hex[:12]}"
    tool_call(
        rpc,
        "send_message",
        {
            "project_key": project,
            "sender_name": g_name,
            "sender_token": g_tok,
            "to": [c_name, x_name],
            "subject": "CRCP Phase3 Grok three-way",
            "body_md": marker,
        },
    )
    inboxes = []
    for name, token in ((c_name, c_tok), (x_name, x_tok)):
        inboxes.append(
            tool_call(
                rpc,
                "fetch_inbox",
                {
                    "project_key": project,
                    "agent_name": name,
                    "registration_token": token,
                    "include_bodies": True,
                    "limit": 10,
                },
            )
        )
    got_c = marker in json.dumps(inboxes[0], default=str)
    got_x = marker in json.dumps(inboxes[1], default=str)
    report = {
        "success": got_c and got_x,
        "marker": marker,
        "agents": {"grok": g_name, "claude": c_name, "codex": x_name},
        "got_on_claude": got_c,
        "got_on_codex": got_x,
    }
    out = _crcp_root() / "reports" / "bus_three_way_proof.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_json(report)
    print(f"# wrote {out}", file=sys.stderr)
    return 0 if report["success"] else 1


def cmd_inbox_scan(args: argparse.Namespace) -> int:
    root = _crcp_root()
    inbox = Path(args.dir) if args.dir else root / "inbox" / "chatgpt"
    outbox = Path(args.out) if args.out else root / "outbox"
    result = (
        watch_inbox(inbox, outbox=outbox, interval_sec=args.interval, once=False)
        if args.watch
        else scan_inbox(inbox, outbox=outbox)
    )
    _print_json(result)
    return 0 if result.get("failed", 0) == 0 else 1


def cmd_publish(args: argparse.Namespace) -> int:
    root = _crcp_root()
    project = args.project or DEFAULT_PROJECT
    if args.file:
        result = publish_file(Path(args.file), project=project)
        _print_json(result)
        return 0
    result = publish_outbox(
        Path(args.out) if args.out else root / "outbox",
        project=project,
        limit=args.limit,
        force=args.force,
    )
    _print_json(result)
    return (
        0
        if not [item for item in result.get("results") or [] if not item.get("ok")]
        else 1
    )


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"crcp {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crcp",
        description="Cross-Rail Control Plane CLI (Phase 1–2)",
        epilog=(
            "Operational tools: python -m crcp.reconcile {scan,requeue,dead-letter}; "
            "durable SQLite spool API: crcp.spool.EventSpool."
        ),
    )
    parser.add_argument("--version", action="store_true", help="print version")
    sub = parser.add_subparsers(dest="command")
    version = sub.add_parser("version", help="print version")
    version.set_defaults(func=cmd_version)

    auth = sub.add_parser("auth", help="auth vault and session commands")
    auth_sub = auth.add_subparsers(dest="auth_cmd")
    status = auth_sub.add_parser("status", help="multi-rail auth status (no secrets)")
    status.set_defaults(func=cmd_auth_status)
    watch = auth_sub.add_parser("watch", help="watch auth.json mtime (no secrets)")
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--once", action="store_true")
    watch.set_defaults(func=cmd_auth_watch)
    mirror = auth_sub.add_parser("mirror", help="inventory or export Desktop cookies")
    mirror.add_argument(
        "--user-data", metavar="PATH", help="Desktop Chromium user-data directory"
    )
    mirror.add_argument(
        "--json",
        action="store_true",
        help="JSON output (the default; retained for scripts)",
    )
    mirror.add_argument("--export", metavar="DIR", help="export directory")
    mirror.add_argument(
        "--decrypt",
        action="store_true",
        help="explicitly permit local Windows decryption for export",
    )
    mirror.set_defaults(func=cmd_auth_mirror)
    deeplink = auth_sub.add_parser(
        "deeplink", help="build, open, or describe codex:// links"
    )
    deeplink_sub = deeplink.add_subparsers(dest="deeplink_cmd")
    deep_build = deeplink_sub.add_parser("build", help="build a codex:// URL")
    deep_build.add_argument("--path", default="", help="deeplink path")
    deep_build.add_argument(
        "--query",
        action="append",
        default=[],
        metavar="KEY=VAL",
        help="query item; repeatable",
    )
    deep_build.set_defaults(func=cmd_auth_deeplink_build)
    deep_open = deeplink_sub.add_parser("open", help="open a codex:// URL")
    deep_open.add_argument("url")
    deep_open.set_defaults(func=cmd_auth_deeplink_open)
    deep_status = deeplink_sub.add_parser(
        "status", help="describe protocol registration"
    )
    deep_status.set_defaults(func=cmd_auth_deeplink_status)
    sso = auth_sub.add_parser("sso", help="PKCE public-client SSO")
    sso_sub = sso.add_subparsers(dest="sso_cmd")
    login = sso_sub.add_parser("login", help="run or continue the PKCE login flow")
    login.add_argument("--redirect-uri", metavar="URI")
    login.add_argument(
        "--print-url",
        action="store_true",
        help="do not open a browser; return authorization URL",
    )
    login.add_argument(
        "--code", help="authorization code for an offline continuation (never echoed)"
    )
    login.add_argument("--timeout", type=int, default=300, metavar="N")
    login.set_defaults(func=cmd_auth_sso_login)
    authorize = sso_sub.add_parser(
        "authorize-url", help="build a metadata-safe authorization URL preview"
    )
    authorize.add_argument("--redirect-uri", metavar="URI")
    authorize.set_defaults(func=cmd_auth_sso_authorize_url)

    broker = auth_sub.add_parser(
        "broker",
        help="browser profile broker: Desktop cookies+Bearer, or phone-store NextAuth",
    )
    broker.add_argument(
        "--port",
        type=int,
        default=9333,
        help="CDP port (desktop default 9333; phone-store default 9340)",
    )
    broker.add_argument(
        "--profile",
        help="dedicated Chromium user-data-dir (default ~/.crcp/browser-broker-profile)",
    )
    broker.add_argument(
        "--url", default="https://chatgpt.com/", help="start URL after inject"
    )
    broker.add_argument(
        "--desktop-user-data", help="Desktop Electron userData path for cookie decrypt"
    )
    broker.add_argument(
        "--browser", help="path to chrome.exe / msedge.exe (Desktop mode)"
    )
    broker.add_argument(
        "--attach",
        action="store_true",
        help="do not launch; attach to existing CDP port",
    )
    broker.add_argument(
        "--no-cookies", action="store_true", help="skip Desktop cookie injection"
    )
    broker.add_argument(
        "--no-bearer", action="store_true", help="skip Bearer header injection"
    )
    broker.add_argument(
        "--close",
        action="store_true",
        help="hint that profile may be closed (default keeps open)",
    )
    broker.add_argument(
        "--desktop-cdp-inventory",
        action="store_true",
        help="inventory cookies on an already-running CDP (e.g. Desktop on 9222)",
    )
    broker.add_argument(
        "--from-phone-store",
        action="store_true",
        help="apply phone-extracted NextAuth cookies (durable isolated profile; WEB_SESSION path)",
    )
    broker.add_argument(
        "--phone-status",
        action="store_true",
        help="show phone cookie store status (no secret values)",
    )
    broker.add_argument(
        "--phone-extract",
        action="store_true",
        help="re-extract from phone via ADB first, then apply (implies --from-phone-store)",
    )
    broker.add_argument(
        "--phone-browser",
        choices=("chrome", "edge"),
        default="chrome",
        help="browser kind for phone-store apply (default chrome)",
    )
    broker.set_defaults(func=cmd_auth_broker)

    health = sub.add_parser("health", help="unified health probe")
    health.add_argument("--json", action="store_true")
    health.add_argument("-v", "--verbose", action="store_true")
    health.set_defaults(func=cmd_health)
    livez = sub.add_parser("livez", help="local process liveness probe (JSON)")
    livez.set_defaults(func=cmd_livez)
    readyz = sub.add_parser("readyz", help="operational readiness probe (JSON)")
    readyz.set_defaults(func=cmd_readyz)

    chatgpt = sub.add_parser("chatgpt", help="ChatGPT live bridge")
    chatgpt_sub = chatgpt.add_subparsers(dest="chatgpt_cmd")
    listing = chatgpt_sub.add_parser("list", help="list conversations")
    listing.add_argument("--limit", type=int, default=20)
    listing.set_defaults(func=cmd_chatgpt_list)
    fetch = chatgpt_sub.add_parser(
        "fetch", help="fetch conversation(s) into outbox envelopes"
    )
    fetch.add_argument("--id", help="conversation id")
    fetch.add_argument(
        "--latest", type=int, default=1, help="fetch N most recent if --id omitted"
    )
    fetch.add_argument("--out", help="outbox directory")
    fetch.set_defaults(func=cmd_chatgpt_fetch)
    live = chatgpt_sub.add_parser("live", help="persistent polling bridge + HTTP :8820")
    live.add_argument("--poll-interval", type=float, default=60.0)
    live.add_argument("--once", action="store_true", help="single poll cycle then exit")
    live.add_argument(
        "--no-publish", action="store_true", help="do not auto-publish to agent-mail"
    )
    live.add_argument("--http-port", type=int, default=8820)
    live.add_argument("--no-http", action="store_true")
    live.set_defaults(func=cmd_chatgpt_live)
    send = chatgpt_sub.add_parser(
        "send", help="send a message (prepare + PoW sentinel)"
    )
    send.add_argument("text", help="user message text")
    send.add_argument("--conversation-id", help="continue existing conversation")
    send.add_argument("--model", help="model slug (default from conversation/init)")
    send.add_argument("--new", action="store_true", help="force new conversation")
    send.add_argument(
        "--no-sentinel", action="store_true", help="skip auto prepare+PoW"
    )
    send.set_defaults(func=cmd_chatgpt_send)

    bus = sub.add_parser("bus", help="agent-mail bus utilities")
    bus_sub = bus.add_subparsers(dest="bus_cmd")
    grok = bus_sub.add_parser(
        "register-grok", help="register Grok node + three-way proof"
    )
    grok.add_argument("--project", help="agent-mail project key")
    grok.set_defaults(func=cmd_bus_register_grok)
    inbox = sub.add_parser("inbox", help="drop-folder ingest for ChatGPT exports")
    inbox_sub = inbox.add_subparsers(dest="inbox_cmd")
    scan = inbox_sub.add_parser("scan", help="scan inbox once (or --watch)")
    scan.add_argument("--dir", help="inbox directory (default inbox/chatgpt)")
    scan.add_argument("--out", help="outbox directory")
    scan.add_argument("--watch", action="store_true", help="poll until Ctrl+C")
    scan.add_argument("--interval", type=float, default=5.0, help="watch poll seconds")
    scan.set_defaults(func=cmd_inbox_scan)
    publish = sub.add_parser("publish", help="publish outbox envelopes to agent-mail")
    publish.add_argument("--out", help="outbox directory")
    publish.add_argument("--file", help="single envelope JSON path")
    publish.add_argument("--limit", type=int, default=20)
    publish.add_argument(
        "--force", action="store_true", help="re-publish already-sent envelopes"
    )
    publish.add_argument("--project", help="agent-mail project key")
    publish.set_defaults(func=cmd_publish)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv or argv in (["--version"], ["-V"]):
        return cmd_version(argparse.Namespace())
    try:
        args = parser.parse_args(argv)
        if getattr(args, "version", False) and not getattr(args, "command", None):
            return cmd_version(args)
        function = getattr(args, "func", None)
        if not function:
            parser.print_help()
            return 2
        return int(function(args))
    except AuthCliConfigError as exc:
        _print_json({"ok": False, "error": {"kind": "config", "message": str(exc)}})
        return 2
    except Exception as exc:
        # Default stays fail-closed: suppress the message. An exception may opt in
        # via `crcp_safe_message = True` when its text is constructed to be
        # secret-free (see auth_broker.CredentialScopeError). Without this, a
        # credential-egress REFUSAL is indistinguishable from a browser fault and
        # gets misdiagnosed instead of acted on.
        safe = bool(getattr(exc, "crcp_safe_message", False))
        _print_json(
            {
                "ok": False,
                "error": {
                    "kind": "credential_scope" if safe else "runtime",
                    "type": type(exc).__name__,
                    "message": str(exc)
                    if safe
                    else "auth command failed; details suppressed to protect credentials",
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
