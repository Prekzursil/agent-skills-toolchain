#!/usr/bin/env python3
"""CNL-0016 recruitment sampler: uniform and stratified, replay-safe seed.

The sampling frame is the ordered eligible catalog (lexicographic participant
id), not "all models" and not the ineligible tail. A replayed council reuses
the captured recruitment_seed plus the frame fingerprint; a fresh run mints
a new CSPRNG seed and therefore draws a different roster.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

DOMAIN_UNIFORM = b"CNL-0016|uniform"
DOMAIN_STRATUM_PREFIX = b"CNL-0016|stratum|"
DOMAIN_FRAME = b"CNL-0016|frame"

HERE = Path(__file__).resolve().parent
DEFAULT_POOL = HERE / "fixtures" / "pool.json"
DEFAULT_SPEC = HERE / "fixtures" / "draw_spec.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_seed_hex(text: str) -> bytes:
    raw = bytes.fromhex(text.strip())
    if len(raw) != 32:
        raise ValueError(f"recruitment_seed must be 32 bytes, got {len(raw)}")
    return raw


def mint_fresh_seed() -> bytes:
    # ANCHOR:fresh-run-mints-csprng-seed
    return os.urandom(32)


def eligible_frame(participants: list[dict]) -> list[dict]:
    # ANCHOR:frame-is-ordered-eligible-catalog
    frame = [p for p in participants if p.get("eligible") is True]
    frame.sort(key=lambda p: str(p["id"]))
    return frame


def stratum_of(person: dict, stratum_key: str) -> str:
    value = person.get(stratum_key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"participant {person.get('id')} missing stratum {stratum_key}")
    return value


def frame_fingerprint(frame: list[dict], stratum_key: str) -> str:
    payload = [
        {"id": p["id"], "stratum": stratum_of(p, stratum_key)} for p in frame
    ]
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hmac.new(DOMAIN_FRAME, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def hmac_block(key: bytes, counter: int) -> bytes:
    return hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()


def unbiased_index(key: bytes, n: int, counter: list[int]) -> int:
    if n <= 0:
        raise ValueError("n must be positive")
    # Rejection sampling on the first 8 bytes so modulo bias cannot freeze a seat.
    limit = (2**64 // n) * n
    while True:
        counter[0] += 1
        x = int.from_bytes(hmac_block(key, counter[0])[:8], "big")
        if x < limit:
            return x % n


def fisher_yates_take(ids: list[str], k: int, key: bytes) -> list[str]:
    # ANCHOR:hmac-fisher-yates
    if k < 0:
        raise ValueError("k must be >= 0")
    if k > len(ids):
        raise ValueError(f"cannot draw {k} from frame of {len(ids)}")
    buf = list(ids)
    counter = [0]
    for i in range(k):
        j = i + unbiased_index(key, len(buf) - i, counter)
        buf[i], buf[j] = buf[j], buf[i]
    return buf[:k]


def domain_key(seed: bytes, domain: bytes) -> bytes:
    return hmac.new(seed, domain, hashlib.sha256).digest()


def draw_uniform(frame: list[dict], k: int, seed: bytes) -> list[str]:
    ids = [p["id"] for p in frame]
    key = domain_key(seed, DOMAIN_UNIFORM)
    return fisher_yates_take(ids, k, key)


def draw_stratified(
    frame: list[dict],
    quotas: dict[str, int],
    seed: bytes,
    stratum_key: str,
) -> list[str]:
    # ANCHOR:stratum-domain-separation
    by_stratum: dict[str, list[str]] = {}
    for person in frame:
        by_stratum.setdefault(stratum_of(person, stratum_key), []).append(person["id"])
    roster: list[str] = []
    for stratum in sorted(quotas):
        want = int(quotas[stratum])
        pool_ids = by_stratum.get(stratum, [])
        if want > len(pool_ids):
            raise ValueError(
                f"stratum {stratum} quota {want} exceeds eligible {len(pool_ids)}"
            )
        child = domain_key(seed, DOMAIN_STRATUM_PREFIX + stratum.encode("utf-8"))
        roster.extend(fisher_yates_take(pool_ids, want, child))
    return roster


def assert_replay_frame(live_fp: str, recorded_fp: str | None) -> None:
    # ANCHOR:replay-refuses-frame-drift
    if recorded_fp is None:
        return
    if recorded_fp != live_fp:
        raise ValueError(
            f"frame fingerprint mismatch: recorded={recorded_fp} live={live_fp}"
        )


def run_draw(
    participants: list[dict],
    spec: dict,
    seed: bytes,
    mode: str,
    recorded_fp: str | None = None,
) -> dict[str, Any]:
    stratum_key = "vendor"
    frame = eligible_frame(participants)
    fp = frame_fingerprint(frame, stratum_key)
    assert_replay_frame(fp, recorded_fp)
    if mode == "uniform":
        roster = draw_uniform(frame, int(spec["uniform_k"]), seed)
    elif mode == "stratified":
        roster = draw_stratified(frame, spec["stratified_quotas"], seed, stratum_key)
    else:
        raise ValueError(f"unknown mode {mode}")
    return {
        "mode": mode,
        "recruitment_seed_hex": seed.hex(),
        "frame_ids": [p["id"] for p in frame],
        "frame_size": len(frame),
        "frame_fingerprint": fp,
        "roster": roster,
        "stratum_key": stratum_key,
    }


def frozen_roster(frame: list[dict], k: int, _seed: bytes) -> list[str]:
    """Negative-control sampler: ignores the seed (the frozen-sampler defect)."""
    return [p["id"] for p in frame][:k]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNL-0016 recruitment draw")
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--mode", choices=("uniform", "stratified"), required=True)
    parser.add_argument("--seed-hex", default="")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--recorded-fp", default="")
    args = parser.parse_args(argv)
    pool = load_json(args.pool)
    spec = load_json(args.spec)
    if args.fresh:
        seed = mint_fresh_seed()
    elif args.seed_hex:
        seed = parse_seed_hex(args.seed_hex)
    else:
        raise SystemExit("FAILED: provide --seed-hex or --fresh")
    recorded = args.recorded_fp or None
    result = run_draw(pool["participants"], spec, seed, args.mode, recorded)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
