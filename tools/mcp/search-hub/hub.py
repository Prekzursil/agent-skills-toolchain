#!/usr/bin/env python3
"""search-hub -- a LAZY search multiplexer with rotation + keyless fallback.

Fronts Exa, Tavily, Firecrawl, and SearXNG STDIO search MCP servers behind ONE
registration while keeping every tool under its ORIGINAL name. The three keyed
providers get transparent API-key rotation; keyless SearXNG is the last-resort
search surface and never enters cooldown. ``initialize``/``tools/list`` are
answered from committed per-provider caches WITHOUT spawning anything (the
low-RAM, idle-cheap win). A keyed ``tools/call`` is routed to the ACTIVE key's
lazily-spawned child; if that child returns a hard-exhaustion error, the hub
cools that key, rotates to the next non-cooled key (lazily spawning ITS child)
and retries the SAME call once -- usually ~1 child per provider, low RAM.

Unlike cloud-hub (one child per backend, forwarded asynchronously), the search
rotator forwards a ``tools/call`` SYNCHRONOUSLY: it must inspect the child's
response to classify exhaustion-vs-rate before deciding whether to rotate. The
child's JSON-RPC reply is then relayed to the client VERBATIM (stdio purity).

Modes::

    python hub.py                      # runtime stdio MCP (what ~/.mcp.json runs)
    python hub.py --refresh [ids...]   # (re)generate tool caches by enumerating
    python hub.py --print-plan         # print the merged plan (tool counts)

Rotation/usage/cooldown live in ``rotation.py`` + ``usage.py``; provider specs +
the error classifier live in ``providers.py``; the multi-key store + the six
``<prefix>_account_*`` tools reuse the shared ``_shared/accounts.py``.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
# accounts.py is shared with cloud-hub/social-hub, one level up in _shared.
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "_shared"))

import accounts  # noqa: E402
import adapters  # noqa: E402
import onions  # noqa: E402
import providers  # noqa: E402
import rotation  # noqa: E402
import usage  # noqa: E402

HUB_VERSION = "0.1.0"
CACHE_DIR = os.path.join(_HERE, "caches")
# The gitignored per-user key store (may hold literal secrets -> never committed).
ACCOUNTS_PATH = os.path.join(_HERE, "accounts.json")
INIT_ID = "_hub_init"
ENUM_TIMEOUT = 45.0  # seconds to wait for a provider's initialize/tools-list
SPAWN_TIMEOUT = 30.0  # seconds to wait for a lazy child to initialize
CALL_TIMEOUT = float(os.environ.get("SEARCH_HUB_CALL_TIMEOUT_S", "180"))


def _spawn(cmd: tuple[str, ...], env: dict[str, str]) -> subprocess.Popen:
    """Spawn an MCP child with UTF-8 pipes (Windows defaults to cp1252)."""
    return subprocess.Popen(
        list(cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _reader(proc: subprocess.Popen, q: "queue.Queue[str | None]") -> None:
    """Pump one child's stdout into a queue; enqueue None on EOF."""
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            q.put(line)
    finally:
        q.put(None)


def _drain_until(q: "queue.Queue[str | None]", want_id, deadline: float) -> dict:
    """Read queued lines until a JSON-RPC message with id==want_id appears.

    Non-matching JSON messages (e.g. server notifications) are dropped. Raises
    TimeoutError past ``deadline`` or EOFError if the child exits first.
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("deadline exceeded")
        try:
            line = q.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError("deadline exceeded") from exc
        if line is None:
            raise EOFError("child exited")
        s = line.strip()
        if not s.startswith("{"):
            continue
        try:
            msg = json.loads(s)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg


# --------------------------------------------------------------------------- #
# routing plan (built from committed caches, no spawning)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Route:
    """Resolution of one exposed tool name back to its owning provider."""

    platform: str
    original_name: str


def load_cache(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def tools_of(cache: dict | None) -> list[dict]:
    if not cache:
        return []
    tools = (cache.get("tools") or {}).get("tools")
    return tools if isinstance(tools, list) else []


def build_routes(
    specs: list[providers.ProviderSpec], cache_dir: str
) -> tuple[list[dict], dict[str, Route], dict[str, str]]:
    """Merge the committed caches into (advertised tools, routing, degraded).

    Provider tool names are already namespaced (``*_exa`` / ``tavily_*`` /
    ``firecrawl_*``) so cross-provider collisions are not expected; a collision
    is still handled defensively with a ``<prefix>_`` on the second owner.
    """
    tools: list[dict] = []
    routes: dict[str, Route] = {}
    degraded: dict[str, str] = {}
    for spec in specs:
        cached = tools_of(load_cache(os.path.join(cache_dir, spec.cache)))
        if not cached:
            degraded[spec.platform] = "no cached tool list (run --refresh)"
        for tool in cached:
            name = tool.get("name")
            if not isinstance(name, str) or not name:
                continue
            exposed = f"{spec.prefix}_{name}" if name in routes else name
            routes[exposed] = Route(spec.platform, name)
            merged = dict(tool)
            merged["name"] = exposed
            tools.append(merged)
    return tools, routes, degraded


# --------------------------------------------------------------------------- #
# per-(provider, key) lazily-spawned child
# --------------------------------------------------------------------------- #
class ProviderKeyChild:
    """One search server bound to a key (or keyless sentinel), lazily spawned."""

    def __init__(
        self, spec: providers.ProviderSpec, key_name: str, env_resolver
    ) -> None:
        self.spec = spec
        self.key_name = key_name
        self._env_resolver = env_resolver  # callable() -> resolved env for THIS key
        self.proc: subprocess.Popen | None = None
        self.q: "queue.Queue[str | None]" = queue.Queue()
        self.started = False
        self.ok = False
        self.error = ""

    def _spawn_env(self) -> dict[str, str]:
        env = dict(os.environ)
        for name, value in self.spec.env_defaults:
            env.setdefault(name, value)
        try:
            env.update(self._env_resolver() or {})
        except (KeyError, ValueError, TypeError):
            pass  # a malformed account must never block a spawn
        return env

    def _alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def ensure_started(self) -> bool:
        """Spawn + initialize the child once; cached readiness thereafter."""
        if self.started:
            return self.ok and self._alive()
        self.started = True
        try:
            self.proc = _spawn(self.spec.cmd, self._spawn_env())
        except OSError as exc:
            self.error = f"spawn failed: {exc}"
            return False
        threading.Thread(target=_reader, args=(self.proc, self.q), daemon=True).start()
        self._send(
            {
                "jsonrpc": "2.0",
                "id": INIT_ID,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "search-hub", "version": HUB_VERSION},
                },
            }
        )
        try:
            _drain_until(self.q, INIT_ID, time.monotonic() + SPAWN_TIMEOUT)
        except (TimeoutError, EOFError) as exc:
            self.error = f"initialize failed: {exc}"
            self._terminate()
            return False
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.ok = True
        return True

    def call(self, request: dict) -> dict:
        """Synchronously forward a tools/call and return the child's response."""
        if not self.ensure_started():
            return self._error_response(request, f"unavailable: {self.error}")
        if not self._send(request):
            return self._error_response(request, f"write failed: {self.error}")
        try:
            return _drain_until(
                self.q, request.get("id"), time.monotonic() + CALL_TIMEOUT
            )
        except (TimeoutError, EOFError) as exc:
            self.error = str(exc)
            return self._error_response(request, f"no response: {exc}")

    def _send(self, obj: dict) -> bool:
        try:
            self.proc.stdin.write(json.dumps(obj) + "\n")  # type: ignore[union-attr]
            self.proc.stdin.flush()  # type: ignore[union-attr]
            return True
        except (OSError, ValueError, AttributeError) as exc:
            self.error = f"write failed: {exc}"
            return False

    def _error_response(self, request: dict, detail: str) -> dict:
        binding = "keyless backend" if self.spec.keyless else f"key '{self.key_name}'"
        text = f"[search-hub] {self.spec.label} {binding} {detail}"
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"content": [{"type": "text", "text": text}], "isError": True},
        }

    def _terminate(self) -> None:
        try:
            if self.proc is not None:
                self.proc.terminate()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# the multiplexing server
# --------------------------------------------------------------------------- #
class SearchHub:
    """One stdin loop; N providers, each with per-key lazy children + rotation."""

    def __init__(
        self,
        specs: list[providers.ProviderSpec],
        emit=None,
        store: "accounts.AccountStore | None" = None,
        rotator: "rotation.Rotator | None" = None,
        environ=None,
        self_hosted: "list[adapters.SelfHostedAdapter] | None" = None,
    ) -> None:
        self.specs = specs
        self.by_platform = {s.platform: s for s in specs}
        self.keyed_specs = [s for s in specs if not s.keyless]
        self.environ = environ if environ is not None else os.environ
        self._out_lock = threading.Lock()
        self._emit = emit or self._emit_stdout
        self.store = store or accounts.AccountStore(
            ACCOUNTS_PATH,
            [_account_policy(s) for s in self.keyed_specs],
            environ=self.environ,
        )
        rotation.seed_backup_keys(self.store, self.keyed_specs, self.environ)
        self.rotator = rotator or rotation.Rotator.from_specs(
            self.keyed_specs, self.store, environ=self.environ
        )
        self.tools, self.routes, self.degraded = build_routes(specs, CACHE_DIR)
        self.account_tools, self.account_routes = self._account_surface(specs)
        # Self-hosted, key-free lane: in-process HTTP adapters (no child spawned,
        # no new import beyond urllib). Their tools/list surface is committed too.
        self.adapters = (
            self_hosted
            if self_hosted is not None
            else adapters.default_adapters(self.environ)
        )
        self.adapter_routes = {
            name: ad for ad in self.adapters for name in ad.tool_names()
        }
        self.adapter_tools = [d for ad in self.adapters for d in ad.tool_defs()]
        # Onion lane (Ahmia + VormWeb indexes via SearXNG): works by default, ASKS
        # before searching, ENABLE_ONIONS=0 is a hard kill switch (§ onions.py).
        self.onions_kill_switched = onions.is_kill_switched(self.environ)
        self._children: dict[tuple[str, str], ProviderKeyChild] = {}
        self.all_tools = (
            self.tools + self.adapter_tools + self.account_tools + [_usage_tool_def()]
        )

    # ---- advertised surface --------------------------------------------
    def _account_surface(self, specs):
        tools: list[dict] = []
        routes: dict[str, tuple[str, str]] = {}
        for spec in specs:
            if spec.keyless:
                continue
            for tool in accounts.account_tool_defs(
                spec.prefix, spec.platform, "env", spec.label
            ):
                tools.append(tool)
                op = tool["name"].rsplit("_account_", 1)[1]
                routes[tool["name"]] = (spec.platform, op)
        return tools, routes

    # ---- child management ----------------------------------------------
    def _child(self, platform: str, key_name: str) -> ProviderKeyChild:
        key = (platform, key_name)
        child = self._children.get(key)
        if child is None:
            spec = self.by_platform[platform]

            def env_resolver() -> dict[str, str]:
                if spec.keyless:
                    return {
                        name: self.environ.get(name, default)
                        for name, default in spec.env_defaults
                    }
                return self.store.env_for(platform, key_name)

            child = ProviderKeyChild(spec, key_name, env_resolver)
            self._children[key] = child
        return child

    # ---- emit / reply helpers ------------------------------------------
    def _emit_stdout(self, raw_json_line: str) -> None:
        with self._out_lock:
            sys.stdout.write(raw_json_line + "\n")
            sys.stdout.flush()

    def _reply(self, mid, result: dict) -> None:
        self._emit(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}))

    def _error(self, mid, code: int, message: str) -> None:
        self._emit(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": code, "message": message},
                }
            )
        )

    def _tool_result(self, mid, payload: dict, is_error: bool = False) -> None:
        self._reply(
            mid,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, ensure_ascii=False, indent=2),
                    }
                ],
                "isError": is_error,
            },
        )

    def _initialize_result(self, params: dict) -> dict:
        pv = (params or {}).get("protocolVersion") or "2024-11-05"
        return {
            "protocolVersion": pv,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "search-hub", "version": HUB_VERSION},
        }

    # ---- dispatch -------------------------------------------------------
    def dispatch(self, msg: dict) -> None:
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            self._reply(mid, self._initialize_result(msg.get("params") or {}))
        elif method == "tools/list":
            self._reply(mid, {"tools": self.all_tools})
        elif method == "tools/call":
            self.handle_call(msg, mid)
        elif method == "ping":
            self._reply(mid, {})
        elif method in ("resources/list", "resources/templates/list", "prompts/list"):
            self._reply(mid, _empty_listing(method))
        elif method is not None and method.startswith("notifications/"):
            return
        elif mid is not None:
            self._error(mid, -32601, f"Method not found: {method}")

    def handle_call(self, msg: dict, mid) -> None:
        name = (msg.get("params") or {}).get("name")
        if not isinstance(name, str):
            self._error(mid, -32602, "tools/call requires a string 'name'")
            return
        if name == "search_usage":
            self._handle_usage(msg, mid)
        elif name in self.account_routes:
            self._handle_account(msg, mid, name)
        elif name in self.adapter_routes:
            self._handle_adapter(msg, mid, name)
        elif name in self.routes:
            self._handle_provider(msg, mid, name)
        else:
            self._error(mid, -32602, f"Unknown tool: {name!r}")

    def _handle_provider(self, msg: dict, mid, name: str) -> None:
        """Route a provider tool through the rotator (active key, rotate-retry)."""
        route = self.routes[name]
        onion_mode = None
        if route.platform == "searxng":
            args = (msg.get("params") or {}).get("arguments") or {}
            action, payload = onions.onion_decision(name, args, self.environ)
            if action in (onions.FORBID, onions.KILLED):
                # Refuse at the hub -- no child spawned, no query forwarded.
                self._tool_result(mid, {"envelope": payload}, is_error=True)
                return
            if action == onions.ASK:
                # Ask-before-searching: a confirmation request, NOT an error.
                self._tool_result(mid, payload, is_error=False)
                return
            if action == onions.RUN:
                # Confirmed onion search: forward the mode-applied (index-only) args
                # and tag the response so onion hits are clearly differentiated.
                onion_args, onion_mode = payload
                params = dict(msg.get("params") or {})
                params["arguments"] = onion_args
                msg = {**msg, "params": params}

        def forward(key_name: str, request: dict) -> dict:
            req = dict(request)
            params = dict(req.get("params") or {})
            params["name"] = route.original_name
            req["params"] = params
            return self._child(route.platform, key_name).call(req)

        spec = self.by_platform[route.platform]
        if spec.keyless:
            # No account lookup or classifier: this child is always eligible and
            # can never be cooled by keyed-provider exhaustion state.
            response = forward("keyless", msg)
        else:
            response = self.rotator.route_call(route.platform, msg, forward)
        if onion_mode is not None:
            # `msg` was rebound above with the pinned onion args; they name the
            # index engine(s) that answered, so the lane tag can say which.
            response = onions.tag_onion_response(
                response, onion_mode, (msg.get("params") or {}).get("arguments")
            )
        response.setdefault("jsonrpc", "2.0")
        response["id"] = mid
        self._emit(json.dumps(response, ensure_ascii=False))

    def _handle_adapter(self, msg: dict, mid, name: str) -> None:
        """Serve a self-hosted tool over HTTP, in-process (no child spawned).

        The adapter always attempts the real backend and returns a truthful
        ``isError`` result when it is unreachable -- it never fabricates hits, so
        the keyless self-hosted lane is safe-inert exactly like SearXNG.
        """
        ad = self.adapter_routes[name]
        args = (msg.get("params") or {}).get("arguments") or {}
        result = ad.handle_call(name, args)
        self._reply(mid, result)

    def _handle_account(self, msg: dict, mid, name: str) -> None:
        """Serve a ``<prefix>_account_*`` tool via the store (never forwarded)."""
        platform, op = self.account_routes[name]
        args = (msg.get("params") or {}).get("arguments") or {}
        result = self.store.handle(platform, op, args)
        if result.get("ok") and result.get("respawn"):
            active = result.get("active")
            if isinstance(active, str):
                # Deliberate manual switch/cycle: un-cool the chosen key so the
                # user's explicit choice wins over an earlier auto-cooldown.
                self.rotator.clear_cooldown(platform, active)
            result["note"] = (
                "active key set; the next call routes to this key (its child is "
                "spawned lazily). Auto-rotation still applies if it later exhausts."
            )
        self._tool_result(mid, result, is_error=not result.get("ok", False))

    def _handle_usage(self, msg: dict, mid) -> None:
        """On-demand per-key usage + rotation health for one or all providers.

        Also reports the self-hosted lane's capability lattice. ``probe=true``
        performs ONE health GET per self-hosted backend to upgrade the reported
        state from config-declared to live-``probed`` / ``absent``.
        """
        args = (msg.get("params") or {}).get("arguments") or {}
        want = args.get("provider") or ""
        probe = bool(args.get("probe"))
        report = {"providers": [], "self_hosted": []}
        for spec in self.specs:
            if want and want != spec.platform:
                continue
            report["providers"].append(self._usage_for_provider(spec))
        for ad in self.adapters:
            if want and want != ad.platform:
                continue
            report["self_hosted"].append(ad.capabilities(probe=probe))
        self._tool_result(mid, report)

    def _usage_for_provider(self, spec: providers.ProviderSpec) -> dict:
        if spec.keyless:
            return {
                "provider": spec.platform,
                "label": spec.label,
                "usage_api": "none (keyless; never cooled)",
                "keys": [],
            }
        keys = []
        health = {h["name"]: h for h in self.rotator.health_snapshot(spec.platform)}
        for name in self.rotator.key_names(spec.platform):
            key_value = self.rotator.key_value(spec.platform, name)
            report = usage.usage_for(
                spec.usage_kind, key_value, name, self.rotator.getter
            )
            report["health"] = health.get(name, {})
            keys.append(report)
        return {
            "provider": spec.platform,
            "label": spec.label,
            "usage_api": spec.usage_url or "none (error-driven)",
            "keys": keys,
        }

    def run(self) -> int:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw.startswith("{"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            self.dispatch(msg)
        return 0


def _account_policy(spec: providers.ProviderSpec) -> accounts.AccountPolicy:
    """The env-mode multi-key policy for a keyed provider."""
    return accounts.AccountPolicy(
        platform=spec.platform, mode="env", seed_env=(spec.key_env,), label=spec.label
    )


def _usage_tool_def() -> dict:
    return {
        "name": "search_usage",
        "description": (
            "On-demand per-key usage + rotation health for the search providers "
            "(Exa/Tavily/Firecrawl/SearXNG), plus the self-hosted lane's capability "
            "lattice. Reports each stored key's label, remaining credits/allowance "
            "(Firecrawl remainingCredits; Tavily plan+paygo headroom), and cooldown "
            "state. Exa reports 'error-driven (no balance API)'; SearXNG reports "
            "keyless and never cooled. The self-hosted section reports each tool's "
            "state (native|probed|declared|emulated|absent). Pass "
            "provider='exa'|'tavily'|'firecrawl'|'searxng'|'selfhosted' to narrow, or "
            "omit for all; probe=true does ONE health GET per self-hosted backend. "
            "Read-only; does not spawn a search child."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "description": (
                        "exa | tavily | firecrawl | searxng | selfhosted; empty = all"
                    ),
                },
                "probe": {
                    "type": "boolean",
                    "description": (
                        "self-hosted only: perform one live health GET to upgrade "
                        "state from declared to probed/absent (default false)"
                    ),
                },
            },
        },
    }


def _empty_listing(method: str) -> dict:
    return {
        "resources/list": {"resources": []},
        "resources/templates/list": {"resourceTemplates": []},
        "prompts/list": {"prompts": []},
    }[method]


# --------------------------------------------------------------------------- #
# cache refresh / plan CLI (not part of the runtime stdio path)
# --------------------------------------------------------------------------- #
def refresh_provider(spec: providers.ProviderSpec, timeout: float = ENUM_TIMEOUT):
    """Spawn a provider once, capture tools/list, and write its committed cache."""
    env = dict(os.environ)
    for name, value in spec.env_defaults:
        env.setdefault(name, value)
    if spec.key_env:
        env.setdefault(spec.key_env, os.environ.get(spec.key_env, "REFRESH_DUMMY"))
    try:
        proc = _spawn(spec.cmd, env)
    except OSError as exc:
        return False, 0, f"spawn failed: {exc}"
    q: "queue.Queue[str | None]" = queue.Queue()
    threading.Thread(target=_reader, args=(proc, q), daemon=True).start()
    try:
        _write(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "search-hub-refresh",
                        "version": HUB_VERSION,
                    },
                },
            },
        )
        deadline = time.monotonic() + timeout
        init = _drain_until(q, 1, deadline)
        _write(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _write(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = _drain_until(q, 2, deadline)
    except (TimeoutError, EOFError, OSError) as exc:
        _safe_terminate(proc)
        return False, 0, f"enumerate failed: {exc}"
    _safe_terminate(proc)
    tool_list = (tools.get("result") or {}).get("tools", [])
    payload = {"initialize": init.get("result"), "tools": tools.get("result")}
    with open(os.path.join(CACHE_DIR, spec.cache), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return True, len(tool_list), f"cached {len(tool_list)} tools -> {spec.cache}"


def _write(proc: subprocess.Popen, obj: dict) -> None:
    proc.stdin.write(json.dumps(obj) + "\n")  # type: ignore[union-attr]
    proc.stdin.flush()  # type: ignore[union-attr]


def _safe_terminate(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        pass


def _cmd_refresh(which: list[str]) -> int:
    specs = providers.default_providers()
    if which:
        specs = [s for s in specs if s.platform in which]
    rc = 0
    for spec in specs:
        ok, _n, msg = refresh_provider(spec)
        print(
            f"[refresh] {'OK  ' if ok else 'SKIP'} {spec.platform}: {msg}",
            file=sys.stderr,
        )
        if not ok:
            rc = 1
    return rc


def _cmd_print_plan() -> int:
    specs = providers.default_providers()
    tools, routes, degraded = build_routes(specs, CACHE_DIR)
    account_tool_count = sum(not s.keyless for s in specs) * len(accounts.ACCOUNT_OPS)
    per_provider: dict[str, int] = {s.platform: 0 for s in specs}
    for route in routes.values():
        per_provider[route.platform] += 1
    self_hosted = adapters.default_adapters(os.environ)
    adapter_tools = [d for ad in self_hosted for d in ad.tool_defs()]
    for ad in self_hosted:
        per_provider[ad.platform] = len(ad.tool_names())
    summary = {
        "provider_tools": len(tools),
        "self_hosted_tools": len(adapter_tools),
        "account_tools": account_tool_count,
        "usage_tools": 1,
        "total_exposed": len(tools) + len(adapter_tools) + account_tool_count + 1,
        "per_provider": per_provider,
        "degraded": degraded,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if argv and argv[0] == "--refresh":
        return _cmd_refresh(argv[1:])
    if argv and argv[0] == "--print-plan":
        return _cmd_print_plan()
    return SearchHub(providers.default_providers()).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
