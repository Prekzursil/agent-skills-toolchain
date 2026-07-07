#!/usr/bin/env python3
"""Shared helpers for the Modal MCP wrapper (CLI path + SDK path).

Split out of ``server.py`` so the CLI tools (``server.py``) and the SDK sandbox/
function tools (``sandbox.py``) share ONE implementation of: the ``modal`` CLI
runner, a lazy ``modal`` SDK gate, per-invocation credential rotation, a
stdio-purity guard, destructive-op gating, and a LOCAL cost estimator.

Rotation is **per-invocation**: an optional ``profile`` (a.k.a. ``account``)
resolves a fresh ``modal.Client`` (SDK) or a per-call env overlay (CLI) on EACH
call; no shared/global "active profile" flag is ever mutated. This matches the
hub's kill+respawn account model for the ambient account while letting a single
call target a *different* account without disturbing concurrent calls
(concurrency-safety -- parallel calls must not contaminate each other).

Stdio purity: this backend speaks newline-delimited JSON-RPC over stdout, so any
library chatter (Modal progress bars / image-build logs) MUST NOT reach stdout.
``quiet()`` redirects ``sys.stdout`` to ``sys.stderr`` (which the hub routes to
DEVNULL) around every SDK/CLI import and call.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
import threading

_CLI_TIMEOUT = 900  # seconds; volume put/get + image builds can be slow
_LOG_TIMEOUT = 30  # seconds; bounded window for streaming log commands
_MAX_OUT = 8000  # cap captured stdout so a huge log can't bloat a JSON reply
_NO_CLI = (
    "modal CLI not found; `pip install modal` and set "
    "MODAL_TOKEN_ID + MODAL_TOKEN_SECRET (or ~/.modal.toml)"
)
_NO_SDK = (
    "modal SDK not available; `pip install modal` and set "
    "MODAL_TOKEN_ID + MODAL_TOKEN_SECRET (or ~/.modal.toml)"
)

# Whole-string ``${NAME}`` refs are resolved by the account layer, not here; a
# per-call profile instead reads MODAL_TOKEN_ID_<SLUG> from the live env.
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


# --------------------------------------------------------------------------- #
# JSON result helpers (every tool returns a JSON string, matching the 6 CLI    #
# tools' existing shape).                                                      #
# --------------------------------------------------------------------------- #
def dumps(obj) -> str:
    """Serialize a result object to a compact, unicode-preserving JSON string."""
    import json  # noqa: PLC0415  (stdlib, cheap; kept local for symmetry)

    return json.dumps(obj, ensure_ascii=False)


def ok(**fields) -> str:
    """A success result: ``{"ok": true, ...}`` as JSON."""
    return dumps({"ok": True, **fields})


def fail(error: str, **fields) -> str:
    """A failure result: ``{"ok": false, "error": ...}`` as JSON."""
    return dumps({"ok": False, "error": error, **fields})


# --------------------------------------------------------------------------- #
# Per-invocation credential rotation.                                          #
# --------------------------------------------------------------------------- #
def _slug(name: str) -> str:
    """``team`` -> ``TEAM``; ``ca-oauth2`` -> ``CA_OAUTH2`` (env-var suffix)."""
    return _NON_ALNUM.sub("_", name).upper()


def _read_toml_profile(profile: str, toml_path: str | None) -> dict | None:
    """Return the ``[profile]`` table from ``~/.modal.toml`` (or None)."""
    path = toml_path or os.path.join(os.path.expanduser("~"), ".modal.toml")
    try:
        import tomllib  # noqa: PLC0415  (py3.11+; lazy so import is cheap)

        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError, ModuleNotFoundError):
        return None
    prof = data.get(profile)
    return prof if isinstance(prof, dict) else None


def resolve_profile(
    profile: str,
    environ: "os._Environ[str] | dict[str, str] | None" = None,
    toml_path: str | None = None,
) -> tuple[str, str, str]:
    """Resolve a named profile to ``(token_id, token_secret, environment)``.

    Sources, in order:

    1. Env vars ``MODAL_TOKEN_ID_<SLUG>`` / ``MODAL_TOKEN_SECRET_<SLUG>`` (and
       optional ``MODAL_ENVIRONMENT_<SLUG>``) -- the same env the hub already
       injects for ``md`` accounts (``accounts.json`` uses ``${...}`` refs like
       ``MODAL_TOKEN_ID_TEAM``), so a per-call ``profile="team"`` reuses them.
    2. A ``[profile]`` section in ``~/.modal.toml`` (Modal's native profiles):
       ``token_id`` / ``token_secret`` / optional ``environment``.

    Raises ``KeyError`` with an actionable message if neither yields both tokens.
    """
    env = os.environ if environ is None else environ
    slug = _slug(profile)
    tid = env.get(f"MODAL_TOKEN_ID_{slug}")
    tsecret = env.get(f"MODAL_TOKEN_SECRET_{slug}")
    environment = env.get(f"MODAL_ENVIRONMENT_{slug}", "")
    if tid and tsecret:
        return tid, tsecret, environment
    prof = _read_toml_profile(profile, toml_path)
    if prof and prof.get("token_id") and prof.get("token_secret"):
        return (
            str(prof["token_id"]),
            str(prof["token_secret"]),
            str(prof.get("environment") or environment or ""),
        )
    raise KeyError(
        f"profile {profile!r}: set MODAL_TOKEN_ID_{slug} + "
        f"MODAL_TOKEN_SECRET_{slug} (e.g. via accounts.json) or add a "
        f"[{profile}] section with token_id/token_secret to ~/.modal.toml"
    )


def rotation_env(
    base: dict[str, str], profile: str = "", environment: str = ""
) -> dict[str, str]:
    """Return a COPY of ``base`` with per-call rotation overlaid (never mutates).

    A ``profile`` sets ``MODAL_TOKEN_ID``/``MODAL_TOKEN_SECRET`` (which the modal
    CLI honours over any ``~/.modal.toml`` active profile) and drops a stale
    ``MODAL_PROFILE`` so the resolved token wins. An explicit ``environment``
    (else the profile's) sets ``MODAL_ENVIRONMENT`` (the modal CLI's ``--env``).
    Raises ``KeyError`` (via :func:`resolve_profile`) if the profile is unknown.
    """
    out = dict(base)
    if profile:
        tid, tsecret, prof_env = resolve_profile(profile, environ=base)
        out["MODAL_TOKEN_ID"] = tid
        out["MODAL_TOKEN_SECRET"] = tsecret
        out.pop("MODAL_PROFILE", None)
        if prof_env and not environment:
            out["MODAL_ENVIRONMENT"] = prof_env
    if environment:
        out["MODAL_ENVIRONMENT"] = environment
    return out


# --------------------------------------------------------------------------- #
# CLI path.                                                                    #
# --------------------------------------------------------------------------- #
def run_cli(
    *args: str,
    profile: str = "",
    environment: str = "",
    timeout: int = _CLI_TIMEOUT,
) -> dict:
    """Invoke the ``modal`` CLI, capturing output. Never raises.

    ``profile``/``environment`` apply per-call credential rotation via a private
    env overlay (see :func:`rotation_env`) -- the global process env is untouched.
    """
    exe = shutil.which("modal")
    if not exe:
        return {"ok": False, "error": _NO_CLI}
    try:
        env = rotation_env(dict(os.environ), profile, environment)
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        proc = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"modal {' '.join(args)} failed: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip()[:_MAX_OUT],
        "stderr": (proc.stderr or "").strip()[:2000],
    }


def run_cli_stream(
    *args: str,
    profile: str = "",
    environment: str = "",
    timeout: int = _LOG_TIMEOUT,
) -> dict:
    """Run a *streaming* CLI command (``app logs``/``container logs``) bounded.

    Modal's log commands follow the stream indefinitely, so a background reader
    collects lines until ``timeout`` elapses, then the child is terminated and
    the captured window returned (``truncated`` flags an unfinished stream).
    """
    exe = shutil.which("modal")
    if not exe:
        return {"ok": False, "error": _NO_CLI}
    try:
        env = rotation_env(dict(os.environ), profile, environment)
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        proc = subprocess.Popen(
            [exe, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except OSError as exc:
        return {"ok": False, "error": f"modal {' '.join(args)} failed: {exc}"}
    lines: list[str] = []

    def _pump() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                lines.append(line.rstrip("\n"))
        except (OSError, ValueError):
            pass

    reader = threading.Thread(target=_pump, daemon=True)
    reader.start()
    reader.join(timeout)
    truncated = reader.is_alive()
    try:
        proc.terminate()
    except OSError:
        pass
    return {
        "ok": True,
        "output": "\n".join(lines)[:_MAX_OUT],
        "truncated": truncated,
        "timeout_s": timeout,
    }


# --------------------------------------------------------------------------- #
# SDK path.                                                                    #
# --------------------------------------------------------------------------- #
def quiet() -> "contextlib.AbstractContextManager[object]":
    """Context manager redirecting library stdout to stderr (stdio purity).

    Wrap every ``modal`` import and SDK call so Modal's progress output / build
    logs never corrupt this server's stdout JSON-RPC stream. The hub routes this
    child's stderr to DEVNULL, so the redirected bytes are simply discarded.
    """
    return contextlib.redirect_stdout(sys.stderr)


_SDK: dict[str, object] = {}


def load_sdk() -> "tuple[object | None, str | None]":
    """Import ``modal`` lazily (stdout-guarded, cached); return ``(mod, err)``.

    Enumeration (``tools/list``) never calls a tool, so ``modal`` is imported
    only on first real SDK call -- keeping listing credential-free and fast.
    """
    if "mod" in _SDK:
        return _SDK["mod"], _SDK["err"]  # type: ignore[return-value]
    try:
        with quiet():
            import modal  # noqa: PLC0415  (lazy on purpose)

        _SDK["mod"], _SDK["err"] = modal, None
    except Exception as exc:  # noqa: BLE001  (surface any import failure as text)
        _SDK["mod"], _SDK["err"] = None, f"{_NO_SDK} ({exc})"
    return _SDK["mod"], _SDK["err"]  # type: ignore[return-value]


def sdk_ctx(
    modal, profile: str = "", environment: str = ""
) -> "tuple[object | None, str | None]":
    """Resolve ``(client, environment_name)`` for one SDK call.

    A ``profile`` builds a fresh per-call ``modal.Client.from_credentials(...)``
    (threaded through ``client=`` on ``Sandbox.create``/``from_id``/``list``,
    ``App.lookup``, ``Function.from_name`` ...); with no profile the ambient
    account (the env the hub injected) is used and ``client`` is ``None``. The
    environment name is the explicit arg, else the profile's, else the ambient
    ``MODAL_ENVIRONMENT``. Raises ``KeyError`` if a named profile is unknown.
    """
    if profile:
        tid, tsecret, prof_env = resolve_profile(profile)
        with quiet():
            client = modal.Client.from_credentials(tid, tsecret)
        return client, (environment or prof_env or None)
    return None, (environment or os.environ.get("MODAL_ENVIRONMENT") or None)


# --------------------------------------------------------------------------- #
# Destructive-op gating.                                                       #
# --------------------------------------------------------------------------- #
def guard_destructive(
    action: str, target: str, confirm: bool, dry_run: bool
) -> str | None:
    """Return a JSON short-circuit for a destructive op, or ``None`` to proceed.

    ``dry_run`` always previews (nothing changes). Otherwise ``confirm`` must be
    ``True`` -- a missing confirm returns an actionable error instead of acting.
    """
    if dry_run:
        return dumps(
            {
                "ok": True,
                "dry_run": True,
                "would": action,
                "target": target,
                "note": "dry_run: nothing changed; re-call with confirm=true "
                "to execute",
            }
        )
    if not confirm:
        return fail(
            f"{action} on {target!r} is destructive/irreversible (and may be "
            f"billable); re-call with confirm=true (or dry_run=true to preview)",
            needs_confirm=True,
            action=action,
            target=target,
        )
    return None


# --------------------------------------------------------------------------- #
# LOCAL cost estimation (Modal exposes NO public billing API).                 #
# --------------------------------------------------------------------------- #
# Per-second USD list price -- source: modal.com/pricing, as of PRICING_AS_OF.
PRICING_AS_OF = "2026-07-07"
GPU_USD_PER_SEC = {
    "b200": 0.001736,
    "h200": 0.001261,
    "h100": 0.001097,
    "rtx-pro-6000": 0.000842,
    "a100-80gb": 0.000694,
    "a100-40gb": 0.000583,
    "l40s": 0.000542,
    "a10": 0.000306,
    "l4": 0.000222,
    "t4": 0.000164,
}
GPU_ALIASES = {
    "a100": "a100-80gb",
    "a100-80g": "a100-80gb",
    "a100-40g": "a100-40gb",
    "a10g": "a10",
    "rtxpro6000": "rtx-pro-6000",
    "rtx-pro-6000-blackwell": "rtx-pro-6000",
    "h100i": "h100",
}
# CPU + memory are billed at a higher rate on the Sandbox/Notebook tier than on
# the Function tier; the caller picks which via ``tier``.
CPU_USD_PER_CORE_SEC = {"standard": 0.0000131, "sandbox": 0.00003942}
MEM_USD_PER_GIB_SEC = {"standard": 0.00000222, "sandbox": 0.00000672}


def _normalize_gpu(gpu: str) -> tuple[str, int]:
    """``"A100:2"`` -> ``("a100-80gb", 2)``; ``"t4"`` -> ``("t4", 1)``."""
    text = gpu.strip().lower()
    count = 1
    if ":" in text:
        text, _, raw = text.partition(":")
        count = int(raw) if raw.isdigit() and int(raw) > 0 else 1
    text = text.replace("_", "-").replace(" ", "-")
    return GPU_ALIASES.get(text, text), count


def estimate_cost(
    seconds: float,
    gpu: str = "",
    gpu_count: int = 1,
    cpu_cores: float = 0.125,
    memory_gib: float = 0.0,
    tier: str = "sandbox",
) -> dict:
    """LOCAL cost estimate from GPU/CPU/memory-seconds. Never bills anything."""
    tier = tier if tier in CPU_USD_PER_CORE_SEC else "sandbox"
    breakdown: dict[str, dict] = {}
    total = 0.0
    if gpu:
        gpu_norm, parsed = _normalize_gpu(gpu)
        rate = GPU_USD_PER_SEC.get(gpu_norm)
        if rate is None:
            return {
                "ok": False,
                "error": f"unknown gpu {gpu!r}",
                "known_gpus": sorted(GPU_USD_PER_SEC),
            }
        count = parsed if ":" in gpu else max(int(gpu_count), 1)
        cost = rate * count * seconds
        breakdown["gpu"] = {
            "type": gpu_norm,
            "count": count,
            "usd_per_sec": rate,
            "usd": round(cost, 6),
        }
        total += cost
    if cpu_cores:
        rate = CPU_USD_PER_CORE_SEC[tier]
        cost = rate * cpu_cores * seconds
        breakdown["cpu"] = {
            "cores": cpu_cores,
            "usd_per_core_sec": rate,
            "usd": round(cost, 6),
        }
        total += cost
    if memory_gib:
        rate = MEM_USD_PER_GIB_SEC[tier]
        cost = rate * memory_gib * seconds
        breakdown["memory"] = {
            "gib": memory_gib,
            "usd_per_gib_sec": rate,
            "usd": round(cost, 6),
        }
        total += cost
    return {
        "ok": True,
        "tier": tier,
        "seconds": seconds,
        "breakdown": breakdown,
        "total_usd": round(total, 6),
        "total_usd_per_hour": round(total / seconds * 3600, 6) if seconds else 0.0,
        "pricing_as_of": PRICING_AS_OF,
        "note": "LOCAL estimate (list price from modal.com/pricing); Modal "
        "exposes NO public billing API -- verify current rates + your usage "
        "in the Modal dashboard.",
    }
