#!/usr/bin/env python3
"""Reusable multi-account credential store + cycling for MCP hub multiplexers.

A cswap-style layer (like ``claude-swap`` for Claude accounts, ``modal profile``,
or multiple ``gcloud config configurations``) generalized across N platforms so a
lazy MCP hub can hold SEVERAL named accounts per backend, switch the active one,
and CYCLE (rotate) through them.

Two account modes:

* ``env``  -- an account is a bundle of environment variables (literal values or
  ``${ENV}`` references). Used for key-based backends (RunPod, Kaggle, Modal,
  Lightning, rclone). The on-disk store is the source of truth; the hub injects
  the active account's env when it spawns that backend.
* ``cli``  -- an account maps to the platform CLI's own profile mechanism (Azure
  subscriptions, gcloud configurations). ``list``/``switch``/``add``/``remove``
  delegate to the CLI (the CLI is the source of truth); no env is injected.

Seeding: if an ``env`` platform has no stored accounts but its registration env
vars are all present, an in-memory ``default`` account is synthesized from
``${ENV}`` references. It is never persisted -- literal secrets only reach the
on-disk store when the user explicitly adds them.

The on-disk store (``accounts.json``) is GITIGNORED and written with restrictive
permissions; it may legitimately hold literal secrets, so it must never be
committed.

Design notes for reuse: this module depends only on the stdlib and a small
``AccountPolicy`` passed in per platform -- no coupling to any backend registry,
so both cloud-hub and social-hub can share it. The CLI ``runner`` is injectable
so the cli-profile path is unit-testable without a real ``az``/``gcloud``.

Switching or cycling accounts to evade a platform's per-account free-tier or
rate limits may violate that platform's Terms of Service; this tooling is
ordinary account management for the user's OWN accounts.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

# A whole-string ``${NAME}`` reference (accounts.json may reference env vars
# instead of embedding literal secrets).
_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")

ACCOUNT_OPS = ("list", "current", "add", "remove", "switch", "cycle")

# (rc, stdout, stderr)
Runner = Callable[[tuple[str, ...]], "tuple[int, str, str]"]


@dataclass(frozen=True)
class CliProfileSpec:
    """How to drive a platform CLI's own profile mechanism (cli mode).

    ``activate_cmd``/``add_cmd``/``remove_cmd`` may contain the literal token
    ``{name}`` which is substituted with the requested account name. ``list_cmd``
    must emit one profile name per line; ``current_cmd`` must emit the active
    name on the first non-empty line.
    """

    list_cmd: tuple[str, ...]
    current_cmd: tuple[str, ...]
    activate_cmd: tuple[str, ...]
    add_cmd: tuple[str, ...] | None = None
    remove_cmd: tuple[str, ...] | None = None
    add_hint: str = ""
    remove_hint: str = ""


@dataclass(frozen=True)
class AccountPolicy:
    """Per-platform account policy handed to the store by the hub."""

    platform: str
    mode: str  # "env" | "cli"
    seed_env: tuple[str, ...] = ()
    cli: CliProfileSpec | None = None
    label: str = ""


def _default_runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
    """Run a CLI command, returning (rc, stdout, stderr). Never raises.

    ``argv[0]`` is resolved via ``shutil.which`` so PATHEXT shims (``az.CMD``,
    ``gcloud.CMD`` on Windows) are found and executed with their explicit
    extension -- a bare ``az`` would otherwise miss the ``.CMD`` under
    ``CreateProcess``.
    """
    if not argv:
        return 127, "", "empty command"
    exe = shutil.which(argv[0]) or argv[0]
    try:
        proc = subprocess.run([exe, *argv[1:]], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        return 127, "", str(exc)


def resolve_env(env: Mapping[str, str], environ: Mapping[str, str]) -> dict[str, str]:
    """Resolve a stored env bundle: ``${NAME}`` -> environ[NAME], else literal."""
    out: dict[str, str] = {}
    for key, val in env.items():
        if isinstance(val, str):
            match = _REF.match(val)
            out[key] = environ.get(match.group(1), "") if match else val
    return out


def account_tool_defs(prefix: str, platform: str, mode: str,
                      label: str = "") -> list[dict]:
    """The six synthetic account-management tool schemas for one backend.

    Names are ``<prefix>_account_<op>`` so they never collide across backends
    (prefixes are unique) and are always safe to prefix (they are hub-native).
    """
    who = label or platform
    string = {"type": "string"}
    name_arg = {"type": "object", "properties": {"name": string},
                "required": ["name"]}
    add_props: dict = {"name": string}
    if mode == "env":
        add_props["env"] = {"type": "object",
                            "description": "Env vars for this account; values "
                                           "may be literals or ${ENV} refs.",
                            "additionalProperties": {"type": "string"}}
        add_required = ["name", "env"]
    else:
        add_required = ["name"]
    empty = {"type": "object", "properties": {}}
    tip = (f" Manages the user's OWN {who} accounts "
           f"({'env-var profiles' if mode == 'env' else 'CLI profiles'}).")
    return [
        {"name": f"{prefix}_account_list",
         "description": f"List the configured {who} accounts and which is active."
                        + tip,
         "inputSchema": empty},
        {"name": f"{prefix}_account_current",
         "description": f"Show the currently active {who} account." + tip,
         "inputSchema": empty},
        {"name": f"{prefix}_account_add",
         "description": f"Add a named {who} account." + tip,
         "inputSchema": {"type": "object", "properties": add_props,
                         "required": add_required}},
        {"name": f"{prefix}_account_remove",
         "description": f"Remove a named {who} account." + tip,
         "inputSchema": name_arg},
        {"name": f"{prefix}_account_switch",
         "description": f"Switch the active {who} account by name; the hub "
                        f"kills+respawns the backend so new creds take effect."
                        + tip,
         "inputSchema": name_arg},
        {"name": f"{prefix}_account_cycle",
         "description": f"Rotate to the NEXT {who} account (round-robin); the "
                        f"hub kills+respawns the backend." + tip,
         "inputSchema": empty},
    ]


class AccountStore:
    """A multi-platform, multi-account credential store with cycling.

    ``env``-mode accounts live in the JSON store; ``cli``-mode operations
    delegate to an (injectable) ``runner`` so they can be unit-tested.
    """

    def __init__(self, path: str, policies: Iterable[AccountPolicy],
                 environ: Mapping[str, str] | None = None,
                 runner: Runner | None = None) -> None:
        self.path = path
        self.policies: dict[str, AccountPolicy] = {p.platform: p for p in policies}
        self.environ = environ if environ is not None else os.environ
        self.runner = runner or _default_runner
        self._data: dict[str, dict] = self._load()

    # ---- persistence -----------------------------------------------------
    def _load(self) -> dict[str, dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _persist(self) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
        try:  # best-effort lockdown (Windows honours the read-only bit only)
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    # ---- env-mode helpers ------------------------------------------------
    def _seed_record(self, pol: AccountPolicy) -> dict | None:
        """Synthesize an in-memory ``default`` record from registration env."""
        if pol.seed_env and all(n in self.environ for n in pol.seed_env):
            return {"active": "default",
                    "accounts": [{"name": "default",
                                  "env": {n: f"${{{n}}}" for n in pol.seed_env}}]}
        return None

    def _view(self, pol: AccountPolicy) -> dict:
        """Read-only env-mode view: stored record, else a seeded default."""
        rec = self._data.get(pol.platform)
        if rec and rec.get("accounts"):
            return rec
        return self._seed_record(pol) or {"active": None, "accounts": []}

    def _materialize(self, pol: AccountPolicy) -> dict:
        """Ensure a writable stored record exists (copying any seed in)."""
        rec = self._data.get(pol.platform)
        if not rec or not rec.get("accounts"):
            seed = self._seed_record(pol)
            rec = {"active": seed["active"],
                   "accounts": [dict(a) for a in seed["accounts"]]} if seed \
                else {"active": None, "accounts": []}
            self._data[pol.platform] = rec
        return rec

    def active_env(self, platform: str) -> dict[str, str]:
        """Resolved env for the active account (env mode); {} otherwise."""
        pol = self.policies.get(platform)
        if pol is None or pol.mode != "env":
            return {}
        rec = self._view(pol)
        active = rec.get("active")
        for acct in rec.get("accounts", []):
            if acct.get("name") == active:
                return resolve_env(acct.get("env", {}), self.environ)
        return {}

    # ---- cli-mode helpers ------------------------------------------------
    @staticmethod
    def _lines(out: str) -> list[str]:
        return [ln.strip() for ln in out.splitlines() if ln.strip()]

    def _cli_names(self, cli: CliProfileSpec) -> tuple[list[str], str]:
        _rc, out, _err = self.runner(cli.list_cmd)
        _rc2, cur, _err2 = self.runner(cli.current_cmd)
        return self._lines(out), (self._lines(cur)[0] if self._lines(cur) else "")

    @staticmethod
    def _fill(cmd: tuple[str, ...], name: str) -> tuple[str, ...]:
        return tuple(part.replace("{name}", name) for part in cmd)

    # ---- operations ------------------------------------------------------
    def handle(self, platform: str, op: str, arguments: Mapping | None) -> dict:
        """Dispatch one account operation; always returns a result dict."""
        pol = self.policies.get(platform)
        if pol is None:
            return _err(platform, op, f"unknown platform {platform!r}")
        fn = getattr(self, f"_op_{op}", None)
        if fn is None:
            return _err(platform, op, f"unknown account op {op!r}")
        try:
            return fn(pol, dict(arguments or {}))
        except _AccountError as exc:
            return _err(platform, op, str(exc))

    def _op_list(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            names, active = self._cli_names(_require_cli(pol))
            return _ok(pol, "list", accounts=names, active=active, source="cli")
        rec = self._view(pol)
        return _ok(pol, "list",
                   accounts=[a.get("name") for a in rec.get("accounts", [])],
                   active=rec.get("active"), source="store")

    def _op_current(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            _rc, out, _err = self.runner(_require_cli(pol).current_cmd)
            lines = self._lines(out)
            return _ok(pol, "current", active=(lines[0] if lines else None),
                       source="cli")
        rec = self._view(pol)
        active = rec.get("active")
        keys = next((sorted(a.get("env", {}))
                     for a in rec.get("accounts", []) if a.get("name") == active),
                    [])
        return _ok(pol, "current", active=active, env_keys=keys, source="store")

    def _op_add(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            if not cli.add_cmd:
                raise _AccountError(
                    f"add is not supported for {pol.platform}; {cli.add_hint}")
            rc, out, err = self.runner(self._fill(cli.add_cmd, name))
            return _cli_result(pol, "add", rc, out, err, name=name)
        env = args.get("env")
        if not isinstance(env, dict) or not env:
            raise _AccountError("'env' must be a non-empty object of str->str")
        rec = self._materialize(pol)
        if any(a.get("name") == name for a in rec["accounts"]):
            raise _AccountError(f"account {name!r} already exists")
        rec["accounts"].append({"name": name,
                                "env": {str(k): str(v) for k, v in env.items()}})
        if not rec.get("active"):
            rec["active"] = name
        self._persist()
        return _ok(pol, "add", added=name, active=rec["active"])

    def _op_remove(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            if not cli.remove_cmd:
                raise _AccountError(
                    f"remove is not supported for {pol.platform}; {cli.remove_hint}")
            rc, out, err = self.runner(self._fill(cli.remove_cmd, name))
            return _cli_result(pol, "remove", rc, out, err, name=name)
        rec = self._materialize(pol)
        keep = [a for a in rec["accounts"] if a.get("name") != name]
        if len(keep) == len(rec["accounts"]):
            raise _AccountError(f"no such account {name!r}")
        rec["accounts"] = keep
        if rec.get("active") == name:
            rec["active"] = keep[0]["name"] if keep else None
        self._persist()
        return _ok(pol, "remove", removed=name, active=rec.get("active"))

    def _op_switch(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            rc, out, err = self.runner(self._fill(cli.activate_cmd, name))
            res = _cli_result(pol, "switch", rc, out, err, active=name)
            res["respawn"] = res["ok"]
            return res
        rec = self._materialize(pol)
        if not any(a.get("name") == name for a in rec["accounts"]):
            raise _AccountError(f"no such account {name!r}")
        rec["active"] = name
        self._persist()
        return _ok(pol, "switch", active=name, respawn=True)

    def _op_cycle(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            cli = _require_cli(pol)
            names, active = self._cli_names(cli)
            nxt = _next_name(names, active)
            rc, out, err = self.runner(self._fill(cli.activate_cmd, nxt))
            res = _cli_result(pol, "cycle", rc, out, err, active=nxt,
                              previous=active)
            res["respawn"] = res["ok"]
            return res
        rec = self._materialize(pol)
        names = [a.get("name") for a in rec["accounts"]]
        nxt = _next_name(names, rec.get("active"))
        rec["active"] = nxt
        self._persist()
        return _ok(pol, "cycle", active=nxt, respawn=True)


class _AccountError(Exception):
    """A user-facing account-operation failure (surfaced as a tool error)."""


def _need_name(args: dict) -> str:
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _AccountError("'name' is required")
    return name.strip()


def _require_cli(pol: AccountPolicy) -> CliProfileSpec:
    if pol.cli is None:
        raise _AccountError(f"{pol.platform} has no CLI profile spec")
    return pol.cli


def _next_name(names: list[str], active: str | None) -> str:
    if not names:
        raise _AccountError("no accounts to cycle through")
    try:
        idx = names.index(active) if active in names else -1
    except ValueError:
        idx = -1
    return names[(idx + 1) % len(names)]


def _ok(pol: AccountPolicy, op: str, **extra) -> dict:
    return {"ok": True, "platform": pol.platform, "mode": pol.mode,
            "op": op, **extra}


def _err(platform: str, op: str, message: str) -> dict:
    return {"ok": False, "platform": platform, "op": op, "error": message}


def _cli_result(pol: AccountPolicy, op: str, rc: int, out: str, err: str,
                **extra) -> dict:
    res = _ok(pol, op, **extra) if rc == 0 else _err(pol.platform, op,
                                                     (err or out).strip()
                                                     or f"CLI exited {rc}")
    res["source"] = "cli"
    if out.strip():
        res["stdout"] = out.strip()[:2000]
    return res
