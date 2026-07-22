"""ChatGPT sentinel chat-requirements: prepare + PoW (+ optional Turnstile hooks).

Owner-authorized write-path helper. PoW matches the reverse-engineered
shape used by the Desktop/Browser client (gAAAAAB + b64(JSON config) whose
sha3_512 hex starts with the server difficulty).

Turnstile still requires a real browser challenge response when required=true;
callers can pass a captured turnstile token or obtain one via CDP.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import threading
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .write_path import DEFAULT_UA, _browser_headers


def _positive_env_float(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
        return value if math.isfinite(value) and value > 0 else default
    except (TypeError, ValueError):
        return default


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


# 25s was too tight on desktop CPUs for current ChatGPT difficulty (measured fail).
# Override with CRCP_POW_DEADLINE_SECONDS when needed.
DEFAULT_POW_DEADLINE_SECONDS = _positive_env_float("CRCP_POW_DEADLINE_SECONDS", 120.0)
POW_MAX_CONCURRENT_SOLVES = _positive_env_int("CRCP_POW_MAX_CONCURRENT_SOLVES", 1)
_POW_SOLVE_SEMAPHORE = threading.BoundedSemaphore(POW_MAX_CONCURRENT_SOLVES)


def _parse_time_utc() -> str:
    now = datetime.now(timezone.utc)
    # Browser-style string (server is loose; keep readable)
    return (
        now.strftime("%a %b %d %Y %H:%M:%S") + " GMT+0000 (Coordinated Universal Time)"
    )


def build_pow_config(
    *,
    nonce: int = 0,
    user_agent: str = DEFAULT_UA,
    screen_w: int = 1920,
    screen_h: int = 1080,
) -> list[Any]:
    """Minimal config list that solves against current ChatGPT PoW (format A)."""
    return [
        screen_w,
        screen_h,
        1,
        nonce,
        user_agent,
        "https://chatgpt.com/",
        None,
        "en-US",
        None,
        0,
        "Google Inc.",
        "default",
        _parse_time_utc(),
        None,
        None,
        None,
        None,
    ]


def _pow_worker(args: tuple) -> dict[str, Any] | None:
    """Search a nonce range, stopping cooperatively at the shared deadline."""
    seed, difficulty, start, end, user_agent, modes, stop_event, deadline = args
    dlen = len(difficulty)
    config = build_pow_config(user_agent=user_agent)
    for n in range(start, end):
        # Avoid a monotonic clock syscall on every hash while keeping deadline
        # overshoot bounded to a small number of iterations.
        if stop_event.is_set() or (n & 0xFF) == 0 and time.monotonic() >= deadline:
            stop_event.set()
            return None
        config[3] = n
        raw = json.dumps(config, separators=(",", ":"), ensure_ascii=False)
        s = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        for tag in modes:
            payload = (seed + s) if tag == "seed+s" else s
            h = hashlib.sha3_512(payload.encode("utf-8")).hexdigest()
            if h.startswith(difficulty):
                return {
                    "token": "gAAAAAB" + s,
                    "nonce": n,
                    "hash_prefix": h[: dlen + 4],
                    "payload_mode": tag,
                    "difficulty": difficulty,
                    "seed": seed,
                }
    return None


def solve_proof_token(
    seed: str,
    difficulty: str,
    *,
    max_iter: int = 80_000_000,
    user_agent: str = DEFAULT_UA,
    workers: int | None = None,
    deadline_seconds: float | None = None,
) -> dict[str, Any]:
    """Find nonce so sha3_512(seed+b64(config) or b64(config)) starts with difficulty.

    Parallel chunked search. ``deadline_seconds`` includes time waiting for the
    process-wide solve slot. Set CRCP_POW_DEADLINE_SECONDS and
    CRCP_POW_MAX_CONCURRENT_SOLVES to configure process defaults.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    if max_iter <= 0:
        raise ValueError("max_iter must be positive")
    n_workers = workers or max(1, min(8, (os.cpu_count() or 4)))
    if n_workers <= 0:
        raise ValueError("workers must be positive")
    limit = (
        DEFAULT_POW_DEADLINE_SECONDS
        if deadline_seconds is None
        else float(deadline_seconds)
    )
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("deadline_seconds must be positive")

    started = time.monotonic()
    deadline = started + limit
    if not _POW_SOLVE_SEMAPHORE.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise TimeoutError(
            f"PoW deadline exceeded after {limit:g}s waiting for solve slot"
        )

    stop_event = threading.Event()
    timed_out = False
    try:
        # seed+s first (common); fall back to bare s if needed.
        modes_order = (("seed+s",), ("s",))
        chunk = max(200_000, max_iter // (n_workers * 16))
        with ThreadPoolExecutor(
            max_workers=n_workers, thread_name_prefix="crcp-pow"
        ) as pool:
            for modes in modes_order:
                start = 0
                while start < max_iter and not stop_event.is_set():
                    futures = []
                    for _ in range(n_workers):
                        if start >= max_iter:
                            break
                        end = min(start + chunk, max_iter)
                        args = (
                            seed,
                            difficulty,
                            start,
                            end,
                            user_agent,
                            modes,
                            stop_event,
                            deadline,
                        )
                        futures.append(pool.submit(_pow_worker, args))
                        start = end

                    pending = set(futures)
                    while pending and not stop_event.is_set():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            timed_out = True
                            stop_event.set()
                            break
                        done, pending = wait(
                            pending, timeout=remaining, return_when=FIRST_COMPLETED
                        )
                        if not done:
                            timed_out = True
                            stop_event.set()
                            break
                        for future in done:
                            hit = future.result()
                            if hit:
                                stop_event.set()
                                for other in pending:
                                    other.cancel()
                                hit["ms"] = int((time.monotonic() - started) * 1000)
                                hit["iterations"] = hit["nonce"] + 1
                                hit["workers"] = n_workers
                                return hit
                    if time.monotonic() >= deadline:
                        timed_out = True
                        stop_event.set()
                if timed_out:
                    break
    finally:
        stop_event.set()
        _POW_SOLVE_SEMAPHORE.release()

    if timed_out:
        raise TimeoutError(f"PoW deadline exceeded after {limit:g}s")
    raise RuntimeError(f"PoW not solved in {max_iter} iters (difficulty={difficulty})")


def sentinel_prepare(
    bridge,
    *,
    device_id: str | None = None,
    session_id: str | None = None,
    p: str = "",
    originator: str = "Codex Browser",
) -> dict[str, Any]:
    """POST /backend-api/sentinel/chat-requirements/prepare."""
    did = device_id or str(uuid.uuid4())
    sid = session_id or str(uuid.uuid4())
    url = f"{bridge.base}/backend-api/sentinel/chat-requirements/prepare"
    body = json.dumps({"p": p}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers=_browser_headers(
            bridge,
            device_id=did,
            session_id=sid,
            originator=originator,
        ),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    data["_device_id"] = did
    data["_session_id"] = sid
    return data


def acquire_sentinel_tokens(
    bridge,
    *,
    device_id: str | None = None,
    session_id: str | None = None,
    turnstile_token: str | None = None,
    originator: str = "Codex Browser",
    max_pow_iter: int = 80_000_000,
    pow_deadline_seconds: float | None = None,
    prepare_retries: int = 3,
) -> dict[str, Any]:
    """Prepare + solve PoW. Attach turnstile_token if provided/required.

    Retries prepare when PoW difficulty is too hard (fresh seed/difficulty).
    Paid path often accepts prepare+proof without Turnstile.
    """
    last_err: Exception | None = None
    for attempt in range(max(1, prepare_retries)):
        prep = sentinel_prepare(
            bridge,
            device_id=device_id,
            session_id=session_id,
            originator=originator,
        )
        pow_req = prep.get("proofofwork") or {}
        try:
            if not isinstance(pow_req, dict) or not pow_req.get("required"):
                proof: dict[str, Any] = {"token": None, "skipped": True}
            else:
                proof = solve_proof_token(
                    str(pow_req["seed"]),
                    str(pow_req["difficulty"]),
                    max_iter=max_pow_iter,
                    deadline_seconds=pow_deadline_seconds,
                )
            ts = prep.get("turnstile") or {}
            need_ts = bool(isinstance(ts, dict) and ts.get("required"))
            out = {
                "persona": prep.get("persona"),
                "prepare_token": prep.get("prepare_token"),
                "proof_token": proof.get("token"),
                "turnstile_token": turnstile_token,
                "turnstile_required": need_ts,
                "device_id": prep.get("_device_id"),
                "session_id": prep.get("_session_id"),
                "prepare_attempt": attempt + 1,
                "pow": {
                    k: proof.get(k)
                    for k in (
                        "nonce",
                        "iterations",
                        "ms",
                        "hash_prefix",
                        "payload_mode",
                        "difficulty",
                        "workers",
                    )
                    if proof.get(k) is not None
                },
                "so_required": bool((prep.get("so") or {}).get("required"))
                if isinstance(prep.get("so"), dict)
                else False,
                "raw_prepare_keys": sorted(prep.keys()),
            }
            # Paid path: turnstile flagged required but prepare+proof alone worked.
            if need_ts and not turnstile_token:
                out["turnstile_note"] = "required_flag_set_but_optional_for_paid"
            return out
        except TimeoutError as e:
            # A deadline is a hard stop, not a reason to launch another costly solve.
            last_err = e
            break
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(
        f"sentinel acquire failed after {prepare_retries} tries: {last_err}"
    )


def try_finalize(
    bridge,
    *,
    prepare_token: str,
    proof_token: str,
    turnstile_token: str,
    device_id: str,
    session_id: str,
    originator: str = "Codex Browser",
) -> dict[str, Any]:
    """Optional guest-style finalize → chat-requirements token (when endpoint accepts)."""
    url = f"{bridge.base}/backend-api/sentinel/chat-requirements/finalize"
    body = json.dumps(
        {
            "prepare_token": prepare_token,
            "proofofwork": proof_token,
            "turnstile": turnstile_token,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers=_browser_headers(
            bridge,
            device_id=device_id,
            session_id=session_id,
            originator=originator,
        ),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": resp.status, "body": data}
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status": e.code,
            "body_text": e.read().decode("utf-8", "replace")[:1500],
        }
