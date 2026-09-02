#!/usr/bin/env python3
"""Probe 1: measured eager vs lazy turn-zero token counts on the same index.

Live re-run of tools/router/lazy.py. Token counts come from TOKEN_RE over the
injected payload, not from a declared estimate. A LAZY body's unique marker
must be absent from the lazy turn-zero payload and present in the eager one.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
sys.path.insert(0, str(HERE))

from tools.router import lazy as L  # noqa: E402
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0369-probe1 {msg}")
    return 1


def main() -> int:
    if not S.LAZY_PY.is_file() or S.LAZY_PY.stat().st_size <= 0:
        return fail(f"module-absent {S.LAZY_PY.relative_to(S.REPO).as_posix()}")
    index_path = S.write_index()
    caps = S.capabilities()
    report = L.measure_turn_zero(caps, select_ids=[S.SELECT_ID])

    lazy_n = int(report["lazy_turn_zero_tokens"])
    eager_n = int(report["eager_turn_zero_tokens"])
    if lazy_n <= 0 or eager_n <= 0:
        return fail(f"non-positive token counts lazy={lazy_n} eager={eager_n}")
    if not report["lazy_cheaper"]:
        return fail(f"lazy {lazy_n} not cheaper than eager {eager_n}")
    if eager_n - lazy_n < 100:
        return fail(f"token delta too small to be a body-load gap: {eager_n - lazy_n}")
    if not report["lazy_bodies_equal_always_on"]:
        return fail(
            f"lazy turn-zero bodies {report['lazy_turn_zero_body_ids']} "
            f"!= always-on {report['always_on_ids']}"
        )
    if not report["eager_loaded_all_bodies"]:
        return fail(f"eager missed bodies {report['eager_turn_zero_body_ids']}")
    if report["accidental_eager_ids"]:
        return fail(f"accidental eager loads {report['accidental_eager_ids']}")
    if S.ALWAYS_ON_ID not in report["lazy_turn_zero_body_ids"]:
        return fail("always-on body missing from lazy turn-zero trace")
    if S.SELECT_ID in report["lazy_turn_zero_body_ids"]:
        return fail("lazy body loaded at turn zero without select")
    if S.SELECT_ID not in report["lazy_after_select_body_ids"]:
        return fail("select() did not load the requested body")
    if int(report["lazy_after_select_tokens"]) <= lazy_n:
        return fail("select() did not increase measured payload tokens")

    lazy_loader = L.GatewayLoader(caps, mode=L.MODE_LAZY)
    lazy_loader.turn_zero()
    eager_loader = L.GatewayLoader(caps, mode=L.MODE_EAGER)
    eager_loader.turn_zero()
    alpha_mark = S.unique_marker(S.SELECT_ID)
    gamma_mark = S.unique_marker(S.ALWAYS_ON_ID)
    if alpha_mark in lazy_loader.payload:
        return fail("lazy turn-zero payload contains a LAZY body's unique marker")
    if alpha_mark not in eager_loader.payload:
        return fail("eager turn-zero payload missing a LAZY body's unique marker")
    if gamma_mark not in lazy_loader.payload:
        return fail("lazy turn-zero payload missing ALWAYS-ON unique marker")
    # Estimate trap: a /4 guess of the lazy payload must not equal the measured count
    # for both modes (that would mean we published an estimate as a measurement).
    guess_lazy = len(lazy_loader.payload.encode("utf-8")) // 4
    guess_eager = len(eager_loader.payload.encode("utf-8")) // 4
    if guess_lazy == lazy_n and guess_eager == eager_n:
        return fail("token counts match len/4 estimates; instrument is not measuring tokens")

    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(S.LAZY_PY),
            "--index",
            str(index_path),
            "--compare",
            "--select",
            S.SELECT_ID,
        ],
        cwd=str(S.REPO),
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return fail(f"cli-exit {proc.returncode} {proc.stderr[-400:]}")
    cli = json.loads(proc.stdout)
    if int(cli.get("lazy_turn_zero_tokens") or 0) != lazy_n:
        return fail(f"cli lazy tokens {cli.get('lazy_turn_zero_tokens')} != live {lazy_n}")
    if int(cli.get("eager_turn_zero_tokens") or 0) != eager_n:
        return fail(f"cli eager tokens {cli.get('eager_turn_zero_tokens')} != live {eager_n}")

    summary = {
        "tokenizer_id": report["tokenizer_id"],
        "index_capability_count": report["index_capability_count"],
        "lazy_turn_zero_tokens": lazy_n,
        "eager_turn_zero_tokens": eager_n,
        "token_delta_eager_minus_lazy": report["token_delta_eager_minus_lazy"],
        "lazy_turn_zero_bytes": report["lazy_turn_zero_bytes"],
        "eager_turn_zero_bytes": report["eager_turn_zero_bytes"],
        "lazy_turn_zero_body_ids": report["lazy_turn_zero_body_ids"],
        "eager_turn_zero_body_ids": report["eager_turn_zero_body_ids"],
        "always_on_ids": report["always_on_ids"],
        "select_id": S.SELECT_ID,
        "lazy_after_select_tokens": report["lazy_after_select_tokens"],
        "cli_lazy_turn_zero_tokens": cli.get("lazy_turn_zero_tokens"),
        "len4_guess_rejected": True,
        "module_path": S.LAZY_PY.relative_to(S.REPO).as_posix(),
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"turn_zero lazy_tokens={lazy_n} eager_tokens={eager_n} "
        f"delta={report['token_delta_eager_minus_lazy']} "
        f"lazy_bodies={report['lazy_turn_zero_body_ids']}"
    )
    print("SUCCESS:IMP-0369-probe1 measured eager vs lazy turn-zero tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
