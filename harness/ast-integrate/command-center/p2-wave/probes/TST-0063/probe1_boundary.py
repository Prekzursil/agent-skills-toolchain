#!/usr/bin/env python3
"""Probe 1: boundary runs at limit-1, limit, limit+1 plus both transport states.

Named tests (catalog TST-0063):
  * test_payload_just_under_the_limit_succeeds_inline
  * test_payload_over_the_limit_switches_to_a_file_and_succeeds

Also records the 34472-char regression seed and proves host ARG_MAX is not
the detector (unguarded Linux spawn at the ceiling can succeed).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import cmdline_guard as cg  # noqa: E402

CEILING = cg.WINDOWS_CREATEPROCESS_CHAR_CEILING
VENDOR = [sys.executable, "-B", str(HERE / "vendor_cli.py")]


def fail(reason: str) -> int:
    print(f"FAILED:TST-0063-probe1 {reason}")
    return 1


def run_at(workdir: Path, target_chars: int, **kwargs):
    payload = cg.pad_payload_for_inline_chars(VENDOR, (), target_chars)
    got = cg.windows_cmdline_chars(list(VENDOR) + ["--prompt", payload])
    if got != target_chars:
        raise RuntimeError(f"pad missed target={target_chars} got={got}")
    return cg.spawn_guarded(VENDOR, payload, workdir=workdir, **kwargs), payload


def child_ok(spawn: cg.SpawnResult, payload: str, transport: str) -> bool:
    child = spawn.child or {}
    return (
        spawn.exit_code == 0
        and spawn.winerror is None
        and child.get("ok") is True
        and child.get("transport") == transport
        and child.get("payload_len") == len(payload)
        and child.get("payload_sha256") == cg.payload_digest(payload)
        and child.get("prompt_body_on_argv") is (transport == "inline")
    )


def test_payload_just_under_the_limit_succeeds_inline(root: Path) -> dict:
    spawn, payload = run_at(root / "under", CEILING - 1)
    ok = (
        spawn.marshal.transport == "inline"
        and spawn.marshal.switched is False
        and spawn.marshal.inline_chars == CEILING - 1
        and spawn.marshal.would_raise_206_if_inline is False
        and child_ok(spawn, payload, "inline")
    )
    return {
        "id": "test_payload_just_under_the_limit_succeeds_inline",
        "pass": ok,
        "result": spawn.as_dict(),
        "payload_chars": len(payload),
    }


def test_payload_over_the_limit_switches_to_a_file_and_succeeds(root: Path) -> dict:
    rows = {}
    all_ok = True
    for target in (CEILING, CEILING + 1):
        spawn, payload = run_at(root / f"over-{target}", target)
        ok = (
            spawn.marshal.transport == "prompt-file"
            and spawn.marshal.switched is True
            and spawn.marshal.inline_chars == target
            and spawn.marshal.would_raise_206_if_inline is True
            and spawn.marshal.windows_chars + 1 <= CEILING
            and "--prompt-file" in spawn.marshal.argv
            and child_ok(spawn, payload, "prompt-file")
        )
        all_ok = all_ok and ok
        rows[str(target)] = {
            "pass": ok,
            "result": spawn.as_dict(),
            "payload_chars": len(payload),
        }
    return {
        "id": "test_payload_over_the_limit_switches_to_a_file_and_succeeds",
        "pass": all_ok,
        "at_limit": rows[str(CEILING)],
        "at_limit_plus_1": rows[str(CEILING + 1)],
    }


def boundary_table(root: Path) -> dict:
    table = []
    ok = True
    for target, want_transport in (
        (CEILING - 1, "inline"),
        (CEILING, "prompt-file"),
        (CEILING + 1, "prompt-file"),
    ):
        spawn, payload = run_at(root / f"bound-{target}", target)
        row_ok = (
            spawn.marshal.transport == want_transport
            and spawn.marshal.inline_chars == target
            and child_ok(spawn, payload, want_transport)
        )
        ok = ok and row_ok
        table.append(
            {
                "assembled_chars": target,
                "offset_from_ceiling": target - CEILING,
                "want_transport": want_transport,
                "got_transport": spawn.marshal.transport,
                "switched": spawn.marshal.switched,
                "spawn_chars": spawn.marshal.windows_chars,
                "child_payload_len": (spawn.child or {}).get("payload_len"),
                "exit_code": spawn.exit_code,
                "pass": row_ok,
            }
        )
    return {"pass": ok, "rows": table}


def regression_seed_34472(root: Path) -> dict:
    payload = "R" * cg.INLINE_PAYLOAD_THAT_DIED
    spawn = cg.spawn_guarded(VENDOR, payload, workdir=root / "seed-34472")
    ok = (
        spawn.marshal.switched is True
        and spawn.marshal.transport == "prompt-file"
        and spawn.marshal.payload_chars == cg.INLINE_PAYLOAD_THAT_DIED
        and spawn.marshal.would_raise_206_if_inline is True
        and child_ok(spawn, payload, "prompt-file")
    )
    return {
        "id": "regression-seed-payload_len-34472",
        "pass": ok,
        "payload_chars": len(payload),
        "inline_chars": spawn.marshal.inline_chars,
        "transport": spawn.marshal.transport,
        "spawn_chars": spawn.marshal.windows_chars,
        "child": spawn.child,
        "exit_code": spawn.exit_code,
    }


def unguarded_206_and_linux_argmax_control(root: Path) -> dict:
    payload = cg.pad_payload_for_inline_chars(VENDOR, (), CEILING)
    gated = cg.spawn_guarded(
        VENDOR,
        payload,
        workdir=root / "force-inline-emulated",
        force_inline=True,
        emulate_createprocess=True,
    )
    linux = cg.naive_linux_spawn(
        VENDOR, payload, workdir=root / "naive-linux"
    )
    gated_ok = (
        gated.winerror == cg.WINERROR_FILENAME_EXCED_RANGE
        and gated.exit_code == cg.WINERROR_FILENAME_EXCED_RANGE
        and gated.child is None
        and gated.marshal.transport == "inline"
    )
    linux_ok = (
        linux.exit_code == 0
        and linux.winerror is None
        and (linux.child or {}).get("ok") is True
        and (linux.child or {}).get("payload_len") == len(payload)
    )
    return {
        "id": "unguarded-206-vs-linux-argmax",
        "pass": gated_ok and linux_ok,
        "emulated_createprocess_206": {
            "pass": gated_ok,
            "winerror": gated.winerror,
            "exit_code": gated.exit_code,
            "stderr": gated.stderr,
            "inline_chars": gated.marshal.inline_chars,
        },
        "naive_linux_spawn_succeeds_past_ceiling": {
            "pass": linux_ok,
            "exit_code": linux.exit_code,
            "host": linux.host,
            "note": (
                "Host ARG_MAX on Linux is not the Windows CreateProcess "
                "ceiling. A green spawn here must not be treated as PASS "
                "for the Windows guard."
            ),
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0063-p1-") as tmp:
        root = Path(tmp)
        under = test_payload_just_under_the_limit_succeeds_inline(root)
        over = test_payload_over_the_limit_switches_to_a_file_and_succeeds(root)
        bounds = boundary_table(root)
        seed = regression_seed_34472(root)
        control = unguarded_206_and_linux_argmax_control(root)

    ok = (
        under["pass"]
        and over["pass"]
        and bounds["pass"]
        and seed["pass"]
        and control["pass"]
    )
    payload = {
        "probe": "probe1-boundary-inline-and-switch",
        "unit_id": "TST-0063",
        "pass": ok,
        "ceiling": CEILING,
        "winerror_206": cg.WINERROR_FILENAME_EXCED_RANGE,
        "test_payload_just_under_the_limit_succeeds_inline": under,
        "test_payload_over_the_limit_switches_to_a_file_and_succeeds": over,
        "boundary_runs": bounds,
        "regression_seed_34472": seed,
        "platform_control": control,
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if not ok:
        return fail(
            "under-limit must stay inline; limit and limit+1 must switch "
            "to --prompt-file and succeed; 34472 seed must switch; "
            "unguarded path must raise 206 under the emulator"
        )
    print(
        "SUCCESS:TST-0063-probe1 boundary "
        f"limit-1={CEILING - 1} inline, "
        f"limit={CEILING} file, "
        f"limit+1={CEILING + 1} file"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
