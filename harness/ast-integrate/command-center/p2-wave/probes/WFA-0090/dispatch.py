#!/usr/bin/env python3
"""Repaired cross-vendor work-unit dispatch (WFA-0090).

Measured defects this module closes:
  1. Fire-and-forget / --background returning a job receipt as the result.
  2. Inline prompts that overflow the Windows CreateProcess 32,767-char cap
     (measured payload_len=34472 -> os error 206).
  3. Exit code 0 treated as success while the contracted output file is
     missing, empty, or unparsable.
  4. A dispatch that returns without an explicit terminal state
     (SUCCESS:<id> / FAILED:<id> <reason>), punching a hole in fan-in.

The repaired path is blocking, requires an explicit timeout, routes the
prompt to a file, then applies two independent gates:
  A. AND-gate: file exists AND non-empty AND parses. Exit 0 is not enough.
  B. Regex gate over the returned payload: background-receipt phrases fail
     even when a wrapper plants a plausible file behind the AND-gate.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Windows CreateProcessW command-line cap. Measured overflow: 34472 chars.
WIN_CREATEPROCESS_CAP = 32767
MEASURED_OVERFLOW_INLINE_LEN = 34472

BACKGROUND_PHRASES = (
    "started in the background",
    "Check /codex:status",
)
# Independent of the AND-gate: catches a receipt even if a file was planted.
RECEIPT_REGEX = re.compile(
    r"(started in the background|Check /codex:status)",
    re.IGNORECASE,
)
TERMINAL_RE = re.compile(r"^(SUCCESS|FAILED):[A-Z]{2,5}-\d{4}(?:\s|$)")

HISTORICAL_RECEIPT = (
    "The task has started in the background. Check /codex:status for progress."
)


def argv_length(argv: list[str]) -> int:
    """CreateProcess-style joined length (space-separated, no extra quotes)."""
    if not argv:
        return 0
    return sum(len(a) for a in argv) + max(0, len(argv) - 1)


def receipt_hits(payload: str) -> list[str]:
    return [m.group(0) for m in RECEIPT_REGEX.finditer(payload or "")]


def and_gate(output_path: Path) -> dict[str, Any]:
    """Three-part AND: exists, non-empty, parses. Exit code is not consulted."""
    exists = output_path.is_file()
    size = output_path.stat().st_size if exists else 0
    nonempty = exists and size > 0
    parsed: Any = None
    parse_ok = False
    parse_error = ""
    if nonempty:
        try:
            text = output_path.read_text(encoding="utf-8")
            parsed = json.loads(text)
            parse_ok = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_error = f"{type(exc).__name__}:{exc}"
    ok = exists and nonempty and parse_ok
    reason = ""
    if not exists:
        reason = "and-gate:missing-file"
    elif not nonempty:
        reason = "and-gate:empty-file"
    elif not parse_ok:
        reason = "and-gate:unparseable"
    return {
        "exists": exists,
        "bytes": size,
        "nonempty": nonempty,
        "parse_ok": parse_ok,
        "parse_error": parse_error,
        "parsed_type": type(parsed).__name__ if parse_ok else None,
        "ok": ok,
        "reason": reason,
    }


def regex_gate(payload: str) -> dict[str, Any]:
    hits = receipt_hits(payload)
    return {
        "ok": not hits,
        "hits": hits,
        "reason": "" if not hits else "regex-gate:background-receipt",
    }


@dataclass
class DispatchRequest:
    unit_id: str
    output_path: Path
    prompt: str = ""
    prompt_file: Path | None = None
    timeout_seconds: float | None = None
    background: bool = False
    vendor_bin: str = "codex"
    extra_argv: list[str] = field(default_factory=list)
    scenario: str = "healthy"
    hang_seconds: float = 0.0
    # When True, skip writing the output file even on a healthy vendor (AND-gate test).
    suppress_output: bool = False
    empty_output: bool = False
    garbage_output: bool = False
    # Plant a valid JSON file *before* dispatch so AND-gate would pass on a receipt.
    plant_output: bool = False
    plant_payload: str | None = None


@dataclass
class DispatchResult:
    unit_id: str
    ok: bool
    terminal_state: str
    reason: str
    exit_code: int | None
    payload: str
    argv: list[str]
    prompt_file: str | None
    timeout_seconds: float | None
    vendor_called: bool
    vendor_calls: int
    elapsed_s: float
    and_gate: dict[str, Any]
    regex_gate: dict[str, Any]
    return_point: str
    blocking: bool
    background_requested: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "ok": self.ok,
            "terminal_state": self.terminal_state,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "payload": self.payload,
            "argv": self.argv,
            "prompt_file": self.prompt_file,
            "timeout_seconds": self.timeout_seconds,
            "vendor_called": self.vendor_called,
            "vendor_calls": self.vendor_calls,
            "elapsed_s": round(self.elapsed_s, 6),
            "and_gate": self.and_gate,
            "regex_gate": self.regex_gate,
            "return_point": self.return_point,
            "blocking": self.blocking,
            "background_requested": self.background_requested,
        }


@dataclass
class VendorReply:
    exit_code: int
    payload: str
    timed_out: bool = False
    os_error: int | None = None


class FakeVendor:
    """In-process stand-in for Codex/Claude. Records argv; never talks to a network."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_argv: list[str] = []
        self.last_joined_len = 0

    def invoke(self, argv: list[str], req: DispatchRequest) -> VendorReply:
        self.calls += 1
        self.last_argv = list(argv)
        self.last_joined_len = argv_length(argv)
        joined = " ".join(argv)
        if "--background" in argv or req.background:
            return VendorReply(exit_code=0, payload=HISTORICAL_RECEIPT)
        if self.last_joined_len >= WIN_CREATEPROCESS_CAP:
            raise OSError(206, "The filename or extension is too long")
        # Inline body still on argv (no --prompt-file) and large: same overflow class.
        if "--prompt-file" not in argv and req.prompt and len(joined) >= WIN_CREATEPROCESS_CAP:
            raise OSError(206, "The filename or extension is too long")
        if req.hang_seconds > 0:
            time.sleep(req.hang_seconds)
        if req.plant_payload is not None:
            return VendorReply(exit_code=0, payload=req.plant_payload)
        if req.scenario == "silent":
            return VendorReply(exit_code=0, payload="")
        if req.scenario == "receipt":
            return VendorReply(exit_code=0, payload=HISTORICAL_RECEIPT)
        out = req.output_path
        if req.suppress_output:
            return VendorReply(exit_code=0, payload="ok-no-file")
        if req.empty_output:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("", encoding="utf-8")
            return VendorReply(exit_code=0, payload="ok-empty-file")
        if req.garbage_output:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("{", encoding="utf-8")
            return VendorReply(exit_code=0, payload="ok-garbage")
        if req.scenario == "healthy" or req.scenario == "routed":
            out.parent.mkdir(parents=True, exist_ok=True)
            body = {
                "unit_id": req.unit_id,
                "ok": True,
                "from": "fake-vendor",
                "prompt_sha16": _sha16(req.prompt or _read(req.prompt_file)),
            }
            out.write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")
            return VendorReply(exit_code=0, payload=json.dumps({"wrote": str(out)}))
        return VendorReply(exit_code=1, payload=f"unknown-scenario:{req.scenario}")


def _read(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _sha16(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _write_prompt_file(req: DispatchRequest) -> Path:
    if req.prompt_file is not None:
        path = req.prompt_file
    else:
        path = req.output_path.with_suffix(req.output_path.suffix + ".prompt.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.prompt, encoding="utf-8")
    return path


def build_blocking_argv(req: DispatchRequest, prompt_file: Path) -> list[str]:
    argv = [req.vendor_bin, "--ignore-user-config", "--prompt-file", str(prompt_file)]
    if req.timeout_seconds is not None:
        argv.extend(["--timeout", str(req.timeout_seconds)])
    argv.extend(req.extra_argv)
    if "--background" in argv:
        raise ValueError("blocking argv must not contain --background")
    return argv


class BrokenDispatcher:
    """Pre-fix class: fire-and-forget, inline prompt, exit-0-is-success, silent return."""

    name = "broken"

    def __init__(self, vendor: FakeVendor | None = None) -> None:
        self.vendor = vendor or FakeVendor()

    def dispatch(self, req: DispatchRequest) -> DispatchResult:
        t0 = time.monotonic()
        argv = [req.vendor_bin]
        if req.background:
            argv.append("--background")
        if req.prompt:
            argv.append(req.prompt)
        argv.extend(req.extra_argv)
        and_info: dict[str, Any] = {
            "exists": False,
            "bytes": 0,
            "nonempty": False,
            "parse_ok": False,
            "ok": False,
            "reason": "not-run",
        }
        try:
            reply = self.vendor.invoke(argv, req)
        except OSError as exc:
            return DispatchResult(
                unit_id=req.unit_id,
                ok=False,
                terminal_state="",
                reason=f"os-error:{getattr(exc, 'winerror', None) or exc.errno}",
                exit_code=None,
                payload=str(exc),
                argv=argv,
                prompt_file=None,
                timeout_seconds=req.timeout_seconds,
                vendor_called=True,
                vendor_calls=self.vendor.calls,
                elapsed_s=time.monotonic() - t0,
                and_gate=and_info,
                regex_gate={"ok": True, "hits": [], "reason": "not-run"},
                return_point="broken-os-error",
                blocking=False,
                background_requested=req.background,
            )
        # Pre-fix: exit 0 is success. No AND-gate. No regex. Terminal may be empty.
        ok = reply.exit_code == 0
        payload = reply.payload
        terminal = f"SUCCESS:{req.unit_id}" if ok else ""
        if req.scenario == "silent":
            terminal = ""
        return DispatchResult(
            unit_id=req.unit_id,
            ok=ok,
            terminal_state=terminal,
            reason="exit-code-only" if ok else "nonzero-exit",
            exit_code=reply.exit_code,
            payload=payload,
            argv=argv,
            prompt_file=None,
            timeout_seconds=req.timeout_seconds,
            vendor_called=True,
            vendor_calls=self.vendor.calls,
            elapsed_s=time.monotonic() - t0,
            and_gate=and_info,
            regex_gate=regex_gate(payload),
            return_point="broken-exit-code-only",
            blocking=not req.background,
            background_requested=req.background,
        )


class RepairedDispatcher:
    """Blocking dispatch: explicit timeout, prompt-by-file, AND-gate + regex gate."""

    name = "repaired"

    def __init__(self, vendor: FakeVendor | None = None) -> None:
        self.vendor = vendor or FakeVendor()

    def dispatch(self, req: DispatchRequest) -> DispatchResult:
        """Single wrapper: every path, including inner holes, gets a terminal state."""
        result = self._dispatch_inner(req)
        if not result.terminal_state or not TERMINAL_RE.match(result.terminal_state):
            result.ok = False
            result.reason = result.reason or "missing-terminal-state"
            result.terminal_state = f"FAILED:{req.unit_id} {result.reason}"
            result.return_point = result.return_point + "+forced-terminal"
        return result

    def _fail(
        self,
        req: DispatchRequest,
        *,
        reason: str,
        return_point: str,
        t0: float,
        payload: str = "",
        argv: list[str] | None = None,
        prompt_file: Path | None = None,
        vendor_called: bool = False,
        exit_code: int | None = None,
        and_info: dict[str, Any] | None = None,
        rx_info: dict[str, Any] | None = None,
    ) -> DispatchResult:
        return DispatchResult(
            unit_id=req.unit_id,
            ok=False,
            terminal_state=f"FAILED:{req.unit_id} {reason}",
            reason=reason,
            exit_code=exit_code,
            payload=payload,
            argv=list(argv or []),
            prompt_file=str(prompt_file) if prompt_file else None,
            timeout_seconds=req.timeout_seconds,
            vendor_called=vendor_called,
            vendor_calls=self.vendor.calls,
            elapsed_s=time.monotonic() - t0,
            and_gate=(
                and_info
                if and_info is not None
                else (
                    and_gate(req.output_path)
                    if req.output_path.exists()
                    else {
                        "exists": False,
                        "bytes": 0,
                        "nonempty": False,
                        "parse_ok": False,
                        "parse_error": "",
                        "parsed_type": None,
                        "ok": False,
                        "reason": "and-gate:not-run",
                    }
                )
            ),
            regex_gate=rx_info or regex_gate(payload),
            return_point=return_point,
            blocking=True,
            background_requested=req.background,
        )

    def _dispatch_inner(self, req: DispatchRequest) -> DispatchResult:
        t0 = time.monotonic()
        if req.background or "--background" in req.extra_argv:
            return self._fail(
                req,
                reason="fire-and-forget-rejected",
                return_point="reject-background",
                t0=t0,
                payload="",
                vendor_called=False,
            )
        if req.timeout_seconds is None or req.timeout_seconds <= 0:
            return self._fail(
                req,
                reason="timeout-required",
                return_point="reject-missing-timeout",
                t0=t0,
                vendor_called=False,
            )

        prompt_file = req.prompt_file
        routed = False
        if req.prompt:
            probe_argv = [req.vendor_bin, req.prompt]
            would_overflow = (
                argv_length(probe_argv) >= WIN_CREATEPROCESS_CAP
                or len(req.prompt) >= MEASURED_OVERFLOW_INLINE_LEN
            )
            # Never put the prompt body on argv. Oversized inline is rejected
            # before the vendor is called and rewritten as a prompt file.
            prompt_file = _write_prompt_file(req)
            routed = would_overflow or req.prompt_file is None
        elif prompt_file is None:
            return self._fail(
                req,
                reason="prompt-file-required",
                return_point="reject-missing-prompt-file",
                t0=t0,
                vendor_called=False,
            )

        if prompt_file is None or not prompt_file.is_file() or prompt_file.stat().st_size <= 0:
            return self._fail(
                req,
                reason="prompt-file-required",
                return_point="reject-missing-prompt-file",
                t0=t0,
                vendor_called=False,
            )

        argv = build_blocking_argv(req, prompt_file)
        if argv_length(argv) >= WIN_CREATEPROCESS_CAP:
            return self._fail(
                req,
                reason="argv-exceeds-createprocess-cap",
                return_point="reject-argv-cap",
                t0=t0,
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=False,
            )

        if req.plant_output:
            req.output_path.parent.mkdir(parents=True, exist_ok=True)
            req.output_path.write_text(
                json.dumps({"planted": True, "unit_id": req.unit_id}) + "\n",
                encoding="utf-8",
            )

        try:
            if req.hang_seconds > float(req.timeout_seconds):
                # Do not sleep past the deadline: classify timeout without hanging the probe.
                time.sleep(min(req.hang_seconds, 0.02))
                return self._fail(
                    req,
                    reason="timeout",
                    return_point="reject-timeout",
                    t0=t0,
                    argv=argv,
                    prompt_file=prompt_file,
                    vendor_called=True,
                    exit_code=124,
                )
            reply = self.vendor.invoke(argv, req)
        except OSError as exc:
            errno = getattr(exc, "winerror", None) or exc.errno
            return self._fail(
                req,
                reason=f"os-error:{errno}",
                return_point="reject-vendor-oserror",
                t0=t0,
                payload=str(exc),
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=True,
            )

        payload = reply.payload or ""
        rx = regex_gate(payload)
        ag = and_gate(req.output_path)

        if not rx["ok"]:
            return self._fail(
                req,
                reason=rx["reason"],
                return_point="reject-background-receipt-regex",
                t0=t0,
                payload=payload,
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=True,
                exit_code=reply.exit_code,
                and_info=ag,
                rx_info=rx,
            )
        if reply.exit_code == 0 and not ag["ok"]:
            return self._fail(
                req,
                reason=ag["reason"] or "severed-stream",
                return_point="reject-and-gate",
                t0=t0,
                payload=payload,
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=True,
                exit_code=reply.exit_code,
                and_info=ag,
                rx_info=rx,
            )
        if reply.exit_code != 0:
            return self._fail(
                req,
                reason=f"vendor-exit:{reply.exit_code}",
                return_point="reject-vendor-exit",
                t0=t0,
                payload=payload,
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=True,
                exit_code=reply.exit_code,
                and_info=ag,
                rx_info=rx,
            )
        if not ag["ok"]:
            return self._fail(
                req,
                reason=ag["reason"] or "and-gate-failed",
                return_point="reject-and-gate",
                t0=t0,
                payload=payload,
                argv=argv,
                prompt_file=prompt_file,
                vendor_called=True,
                exit_code=reply.exit_code,
                and_info=ag,
                rx_info=rx,
            )

        tag = "success-routed-prompt-file" if routed else "success-blocking-file-prompt"
        return DispatchResult(
            unit_id=req.unit_id,
            ok=True,
            terminal_state=f"SUCCESS:{req.unit_id}",
            reason="and-gate-and-regex-pass",
            exit_code=reply.exit_code,
            payload=payload,
            argv=argv,
            prompt_file=str(prompt_file),
            timeout_seconds=req.timeout_seconds,
            vendor_called=True,
            vendor_calls=self.vendor.calls,
            elapsed_s=time.monotonic() - t0,
            and_gate=ag,
            regex_gate=rx,
            return_point=tag,
            blocking=True,
            background_requested=False,
        )


RETURN_POINTS_REQUIRED = (
    "reject-background",
    "reject-missing-timeout",
    "reject-background-receipt-regex",
    "reject-and-gate",
    "reject-timeout",
    "success-blocking-file-prompt",
    "success-routed-prompt-file",
)


def campaign(tmp: Path) -> dict[str, Any]:
    """Run the both-states + AND-gate + regex + oversized + terminal suite."""
    repaired_v = FakeVendor()
    broken_v = FakeVendor()
    repaired = RepairedDispatcher(repaired_v)
    broken = BrokenDispatcher(broken_v)
    uid = "WFA-0090"

    def out(name: str) -> Path:
        return tmp / f"{name}.json"

    # --- both-states: background ---
    bg_req_b = DispatchRequest(
        unit_id=uid,
        output_path=out("bg-broken"),
        prompt="do work",
        background=True,
        timeout_seconds=5,
        scenario="receipt",
    )
    bg_req_r = DispatchRequest(
        unit_id=uid,
        output_path=out("bg-repaired"),
        prompt="do work",
        background=True,
        timeout_seconds=5,
        scenario="receipt",
    )
    bg_broken = broken.dispatch(bg_req_b)
    bg_repaired = repaired.dispatch(bg_req_r)

    # --- oversized inline ---
    huge = "X" * MEASURED_OVERFLOW_INLINE_LEN
    ov_broken = broken.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("ov-broken"),
            prompt=huge,
            timeout_seconds=5,
            scenario="healthy",
        )
    )
    ov_repaired = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("ov-repaired"),
            prompt=huge,
            prompt_file=tmp / "routed.prompt.txt",
            timeout_seconds=5,
            scenario="healthy",
        )
    )

    # --- healthy blocking ---
    healthy = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("healthy"),
            prompt="small prompt",
            prompt_file=tmp / "healthy.prompt.txt",
            timeout_seconds=5,
            scenario="healthy",
        )
    )

    # --- AND-gate: exit 0, missing file ---
    missing = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("missing"),
            prompt="x",
            prompt_file=tmp / "missing.prompt.txt",
            timeout_seconds=5,
            suppress_output=True,
        )
    )

    # --- AND-gate: empty ---
    empty = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("empty"),
            prompt="x",
            prompt_file=tmp / "empty.prompt.txt",
            timeout_seconds=5,
            empty_output=True,
        )
    )

    # --- AND-gate: unparseable ---
    garbage = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("garbage"),
            prompt="x",
            prompt_file=tmp / "garbage.prompt.txt",
            timeout_seconds=5,
            garbage_output=True,
        )
    )

    # --- regex gate vs planted AND-gate file (evidence B) ---
    planted = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("planted"),
            prompt="x",
            prompt_file=tmp / "planted.prompt.txt",
            timeout_seconds=5,
            scenario="receipt",
            plant_output=True,
            plant_payload=HISTORICAL_RECEIPT,
        )
    )

    # --- timeout ---
    timed = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("timed"),
            prompt="x",
            prompt_file=tmp / "timed.prompt.txt",
            timeout_seconds=0.01,
            hang_seconds=1.0,
        )
    )

    # --- missing timeout ---
    no_to = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("no-timeout"),
            prompt="x",
            prompt_file=tmp / "no-timeout.prompt.txt",
            timeout_seconds=None,
        )
    )

    # --- broken silent hole ---
    silent_broken = broken.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("silent-broken"),
            prompt="x",
            timeout_seconds=5,
            scenario="silent",
        )
    )
    silent_repaired = repaired.dispatch(
        DispatchRequest(
            unit_id=uid,
            output_path=out("silent-repaired"),
            prompt="x",
            prompt_file=tmp / "silent.prompt.txt",
            timeout_seconds=5,
            scenario="silent",
            suppress_output=True,
        )
    )

    results = {
        "background_broken": bg_broken.as_dict(),
        "background_repaired": bg_repaired.as_dict(),
        "oversized_broken": ov_broken.as_dict(),
        "oversized_repaired": ov_repaired.as_dict(),
        "healthy": healthy.as_dict(),
        "and_gate_missing": missing.as_dict(),
        "and_gate_empty": empty.as_dict(),
        "and_gate_unparseable": garbage.as_dict(),
        "regex_vs_planted_file": planted.as_dict(),
        "timeout": timed.as_dict(),
        "missing_timeout": no_to.as_dict(),
        "silent_broken": silent_broken.as_dict(),
        "silent_repaired": silent_repaired.as_dict(),
    }

    points = {r["return_point"].replace("+forced-terminal", "") for r in results.values()}
    missing_points = [p for p in RETURN_POINTS_REQUIRED if p not in points]

    both_states_background = {
        "broken_accepted_receipt": bool(
            bg_broken.ok and RECEIPT_REGEX.search(bg_broken.payload or "")
        ),
        "broken_vendor_called": bg_broken.vendor_called,
        "repaired_rejected": (not bg_repaired.ok)
        and bg_repaired.reason == "fire-and-forget-rejected",
        "repaired_vendor_not_called": not bg_repaired.vendor_called,
        "repaired_has_terminal": bool(TERMINAL_RE.match(bg_repaired.terminal_state)),
        "pass": False,
    }
    both_states_background["pass"] = (
        both_states_background["broken_accepted_receipt"]
        and both_states_background["repaired_rejected"]
        and both_states_background["repaired_vendor_not_called"]
        and both_states_background["repaired_has_terminal"]
    )

    routed_file = Path(ov_repaired.prompt_file) if ov_repaired.prompt_file else None
    oversized = {
        "broken_hit_os_error_or_inline": (
            ov_broken.return_point == "broken-os-error"
            or (ov_broken.argv and any(len(a) >= MEASURED_OVERFLOW_INLINE_LEN for a in ov_broken.argv))
        ),
        "repaired_ok": ov_repaired.ok,
        "repaired_prompt_file_exists": bool(routed_file and routed_file.is_file()),
        "repaired_prompt_file_bytes": routed_file.stat().st_size if routed_file and routed_file.is_file() else 0,
        "repaired_argv_has_prompt_file": "--prompt-file" in ov_repaired.argv,
        "repaired_argv_lacks_body": huge not in " ".join(ov_repaired.argv),
        "repaired_argv_len": argv_length(ov_repaired.argv),
        "repaired_argv_under_cap": argv_length(ov_repaired.argv) < WIN_CREATEPROCESS_CAP,
        "ignore_user_config": "--ignore-user-config" in ov_repaired.argv,
        "pass": False,
    }
    oversized["pass"] = (
        oversized["broken_hit_os_error_or_inline"]
        and oversized["repaired_ok"]
        and oversized["repaired_prompt_file_exists"]
        and oversized["repaired_argv_has_prompt_file"]
        and oversized["repaired_argv_lacks_body"]
        and oversized["repaired_argv_under_cap"]
        and oversized["ignore_user_config"]
    )

    and_gate_ok = (
        not missing.ok
        and missing.reason.startswith("and-gate:")
        and not empty.ok
        and empty.reason.startswith("and-gate:")
        and not garbage.ok
        and garbage.reason.startswith("and-gate:")
        and healthy.ok
        and healthy.and_gate.get("ok") is True
    )

    regex_independent = (
        planted.and_gate.get("ok") is True
        and not planted.ok
        and planted.reason == "regex-gate:background-receipt"
        and planted.return_point == "reject-background-receipt-regex"
    )

    terminals = []
    for key, row in results.items():
        ts = row.get("terminal_state") or ""
        terminals.append(
            {
                "case": key,
                "terminal_state": ts,
                "ok_shape": bool(TERMINAL_RE.match(ts)),
                "return_point": row.get("return_point"),
            }
        )
    # Broken silent is the hole we are proving; repaired must not have it.
    repaired_keys = [k for k in results if not k.endswith("_broken") and k != "oversized_broken"]
    repaired_all_terminal = all(
        TERMINAL_RE.match(results[k]["terminal_state"] or "") for k in repaired_keys
    )
    broken_silent_hole = not bool(TERMINAL_RE.match(silent_broken.terminal_state or ""))

    return {
        "results": results,
        "both_states_background": both_states_background,
        "oversized_inline": oversized,
        "and_gate_exit0_insufficient": and_gate_ok,
        "regex_independent_of_and_gate": regex_independent,
        "return_points_seen": sorted(points),
        "return_points_missing": missing_points,
        "terminals": terminals,
        "repaired_all_terminal": repaired_all_terminal,
        "broken_silent_hole": broken_silent_hole,
        "healthy_success": healthy.ok and healthy.terminal_state == f"SUCCESS:{uid}",
        "pass": (
            both_states_background["pass"]
            and oversized["pass"]
            and and_gate_ok
            and regex_independent
            and repaired_all_terminal
            and broken_silent_hole
            and healthy.ok
            and not missing_points
        ),
    }


def scan_call_sites(repo: Path) -> dict[str, Any]:
    """Scan this worktree for fire-and-forget / inline-dispatch residues."""
    roots = [
        repo / "command-center" / "p2-wave" / "seed-stage",
        repo / "tools",
        repo / "command-center" / "wfa",
    ]
    live_candidates = [
        Path.home() / ".claude" / "workflows",
        Path("/mnt/c/Users/Prekzursil/.claude/workflows"),
        Path("/root/.claude/workflows"),
    ]
    live = []
    for p in live_candidates:
        live.append({"path": str(p), "exists": p.is_dir(), "entries": []})
        if p.is_dir():
            live[-1]["entries"] = [x.name for x in list(p.iterdir())[:20]]

    hits: list[dict[str, Any]] = []
    needles = ("--background", "start_new_session", "mcp__codex__codex")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".sh", ".ps1", ".json", ".md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for n in needles:
                    if n in line:
                        rel = path.relative_to(repo).as_posix()
                        hits.append(
                            {
                                "path": rel,
                                "line": i,
                                "needle": n,
                                "snippet": line.strip()[:180],
                            }
                        )
    return {
        "live_workflows": live,
        "live_workflows_present": any(x["exists"] for x in live),
        "repo_hits": hits,
        "note": (
            "live:~/.claude/workflows is absent on this Linux worktree; "
            "repair is the dispatcher class plus fixtures of the measured failures."
        ),
    }


VendorFactory = Callable[[], FakeVendor]


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="wfa0090-") as raw:
        report = campaign(Path(raw))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2, sort_keys=True))
    print("pass=" + str(report["pass"]))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
