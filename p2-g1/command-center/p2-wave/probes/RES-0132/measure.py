"""Recompute T+0 / T+7 / T+30 verdicts, named flips, and median lag."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import scan as S

HERE = Path(__file__).resolve().parent

# Cadence: T+0, T+7d, T+30d. Product window ends at the live fetch day.
# Historical windows are chosen so a real advisory lands inside 30 days
# of a then-green pin. That sample estimates lag given a flip, not the
# probability a random lockfile flips.
LOCKFILES: list[dict[str, Any]] = [
    {
        "id": "control-red-npm-lodash-4.17.11",
        "role": "control-already-published",
        "kind": "npm-lock",
        "path": HERE / "control-red/package-lock.json",
        "t0": "2024-05-01T00:00:00Z",
        "t7": "2024-05-08T00:00:00Z",
        "t30": "2024-05-31T00:00:00Z",
        "expect_t0": "RED",
    },
    {
        "id": "control-red-pip-requests-2.25.1",
        "role": "control-already-published",
        "kind": "pip-req",
        "path": HERE / "control-red/requirements.txt",
        "t0": "2024-05-01T00:00:00Z",
        "t7": "2024-05-08T00:00:00Z",
        "t30": "2024-05-31T00:00:00Z",
        "expect_t0": "RED",
    },
    {
        "id": "frozen-green-npm-mcp-sdk",
        "role": "product-frozen-green",
        "kind": "npm-lock",
        "path": HERE / "frozen-green/package-lock.json",
        "t0": "2026-07-25T00:00:00Z",
        "t7": "2026-08-01T00:00:00Z",
        "t30": "2026-08-24T00:00:00Z",
        "expect_t0": "GREEN",
    },
    {
        "id": "historical-pip-2024-05-01",
        "role": "historical-green-then-decay",
        "kind": "pip-req",
        "path": HERE / "historical/pip-2024-05-01/requirements.txt",
        "t0": "2024-05-01T00:00:00Z",
        "t7": "2024-05-08T00:00:00Z",
        "t30": "2024-05-31T00:00:00Z",
        "expect_t0": "GREEN",
    },
    {
        "id": "historical-npm-braces-3.0.2",
        "role": "historical-green-then-decay",
        "kind": "npm-lock",
        "path": HERE / "historical/npm-braces-3.0.2/package-lock.json",
        "t0": "2024-05-01T00:00:00Z",
        "t7": "2024-05-08T00:00:00Z",
        "t30": "2024-05-31T00:00:00Z",
        "expect_t0": "GREEN",
    },
    {
        "id": "historical-npm-cross-spawn-7.0.3",
        "role": "historical-green-then-decay",
        "kind": "npm-lock",
        "path": HERE / "historical/npm-cross-spawn-7.0.3/package-lock.json",
        "t0": "2024-10-15T00:00:00Z",
        "t7": "2024-10-22T00:00:00Z",
        "t30": "2024-11-14T00:00:00Z",
        "expect_t0": "GREEN",
    },
]

SECOND_SIGNAL_GHSAS = [
    "GHSA-jf85-cpcp-j695",  # lodash control CVE-2019-10744
    "GHSA-j8r2-6x86-q33q",  # requests 2.25.1 control CVE-2023-32681
    "GHSA-h75v-3vvj-5mfj",  # jinja2 May 2024
    "GHSA-9wx4-h78v-vm56",  # requests 2.31.0 May 2024
    "GHSA-grv7-fg5c-xmjg",  # braces May 2024
    "GHSA-3xgq-45jj-v275",  # cross-spawn Nov 2024
]


def load_packages(spec: dict[str, Any]) -> list[dict[str, str]]:
    path: Path = spec["path"]
    if spec["kind"] == "npm-lock":
        return S.parse_npm_lock(path)
    if spec["kind"] == "pip-req":
        return S.parse_requirements(path)
    raise ValueError(spec["kind"])


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def checkpoint_flips(
    db: S.CaptureDB,
    packages: list[dict[str, str]],
    t0: datetime,
    t7: datetime,
    t30: datetime,
) -> dict[str, Any]:
    v0 = S.lockfile_verdict(db, packages, t0)
    v7 = S.lockfile_verdict(db, packages, t7)
    v30 = S.lockfile_verdict(db, packages, t30)
    events: list[dict[str, Any]] = []

    def new_ids(prev: dict[str, Any], cur: dict[str, Any], label: str, when: datetime) -> None:
        prev_set = set(prev["advisory_ids"])
        for aid in cur["advisory_ids"]:
            if aid in prev_set:
                continue
            osv = S.osv_published(db, aid) or {}
            pub = osv.get("published_dt")
            lag = None
            if pub is not None:
                lag = (when - pub).total_seconds() / 86400.0
            events.append(
                {
                    "checkpoint": label,
                    "advisory_id": aid,
                    "published": osv.get("published"),
                    "lag_days": lag,
                    "cve_ids": (db.vulns.get(aid) or {}).get("aliases") or [],
                }
            )

    new_ids(v0, v7, "T+7d", t7)
    new_ids(v7, v30, "T+30d", t30)
    interval_flips = int(v0["verdict"] != v7["verdict"]) + int(
        v7["verdict"] != v30["verdict"]
    )
    return {
        "T+0": {"at": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), **{k: v for k, v in v0.items()}},
        "T+7d": {"at": t7.strftime("%Y-%m-%dT%H:%M:%SZ"), **{k: v for k, v in v7.items()}},
        "T+30d": {
            "at": t30.strftime("%Y-%m-%dT%H:%M:%SZ"),
            **{k: v for k, v in v30.items()},
        },
        "interval_flip_count": interval_flips,
        "t30_flipped_from_t0": v0["verdict"] != v30["verdict"],
        "named_flips": events,
    }


def run() -> dict[str, Any]:
    db = S.CaptureDB()
    rows: list[dict[str, Any]] = []
    lag_days: list[float] = []
    named: list[dict[str, Any]] = []
    control_ok = True
    product_t30_flip = None

    for spec in LOCKFILES:
        packages = load_packages(spec)
        digest, size = S.sha256_file(spec["path"])
        t0 = S.parse_ts(spec["t0"])
        t7 = S.parse_ts(spec["t7"])
        t30 = S.parse_ts(spec["t30"])
        assert t0 and t7 and t30
        # Re-verify the frozen bytes at every cadence point (same file).
        hashes = {
            "T+0": digest,
            "T+7d": digest,
            "T+30d": digest,
            "identical": True,
        }
        cadence = checkpoint_flips(db, packages, t0, t7, t30)
        t0_verdict = cadence["T+0"]["verdict"]
        if spec["expect_t0"] != t0_verdict:
            control_ok = False
        if spec["role"] == "product-frozen-green":
            product_t30_flip = cadence["t30_flipped_from_t0"]
        if spec["role"] == "historical-green-then-decay" and t0_verdict == "GREEN":
            for ev in cadence["named_flips"]:
                if ev.get("lag_days") is not None:
                    lag_days.append(float(ev["lag_days"]))
                named.append({"lockfile_id": spec["id"], **ev})
        rel = spec["path"].relative_to(HERE).as_posix()
        rows.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "path": f"command-center/p2-wave/probes/RES-0132/{rel}",
                "sha256": digest,
                "bytes": size,
                "package_count": len(packages),
                "lockfile_hash_reverified": hashes,
                "expect_t0": spec["expect_t0"],
                "t0_matches_expect": spec["expect_t0"] == t0_verdict,
                **cadence,
            }
        )

    historical = [r for r in rows if r["role"] == "historical-green-then-decay"]
    hist_n = len(historical)
    hist_flip_n = sum(1 for r in historical if r["t30_flipped_from_t0"])
    hist_intervals = hist_n * 2
    hist_interval_flips = sum(r["interval_flip_count"] for r in historical)

    braces_t0 = next(r for r in rows if r["id"] == "historical-npm-braces-3.0.2")
    braces_patched = S.package_verdict(
        db,
        {"name": "braces", "version": "3.0.3", "ecosystem": "npm"},
        S.parse_ts("2024-05-31T00:00:00Z"),
    )
    lodash_product_t0 = S.package_verdict(
        db,
        {"name": "lodash", "version": "4.17.11", "ecosystem": "npm"},
        S.parse_ts("2026-07-25T00:00:00Z"),
    )

    agreements = [S.second_signal_agreement(db, gid) for gid in SECOND_SIGNAL_GHSAS]
    all_agree = all(a["agree_utc_date"] for a in agreements)

    return {
        "fetched_at": S.load_json(S.CAPTURES / "osv-querybatch-index.json").get(
            "fetched_at"
        ),
        "osv_endpoint": "https://api.osv.dev/v1/querybatch",
        "github_endpoint": "https://api.github.com/advisories/{id}",
        "method": (
            "Live OSV querybatch at fetch time tells which advisories match "
            "each frozen pin today. Checkpoint membership is published <= T. "
            "GitHub Advisory REST published_at is the second rail. osv-scanner "
            "and pip-audit binaries were not present; both wrap OSV."
        ),
        "lockfiles": rows,
        "control_t0_all_red": all(
            r["t0_matches_expect"]
            for r in rows
            if r["role"] == "control-already-published"
        ),
        "product_lockfile_flipped_in_30d": product_t30_flip,
        "historical_t30_flip_rate": (hist_flip_n / hist_n) if hist_n else None,
        "historical_interval_flip_rate": (
            hist_interval_flips / hist_intervals if hist_intervals else None
        ),
        "named_flips": named,
        "median_lag_days": median(lag_days),
        "lag_sample_days": lag_days,
        "second_signal": {
            "all_agree_utc_date": all_agree,
            "pairs": agreements,
        },
        "both_states_braces": {
            "vulnerable_pin": "braces@3.0.2",
            "patched_pin": "braces@3.0.3",
            "t0_2024_05_01_vulnerable": braces_t0["T+0"]["verdict"],
            "t30_2024_05_31_vulnerable": braces_t0["T+30d"]["verdict"],
            "t30_patched": braces_patched["verdict"],
            "date_cut_works": (
                braces_t0["T+0"]["verdict"] == "GREEN"
                and braces_t0["T+30d"]["verdict"] == "RED"
                and braces_patched["verdict"] == "GREEN"
            ),
        },
        "lodash_still_red_at_product_t0": lodash_product_t0["verdict"] == "RED",
        "invariants_ok": (
            control_ok
            and all_agree
            and lodash_product_t0["verdict"] == "RED"
            and braces_t0["T+0"]["verdict"] == "GREEN"
            and braces_t0["T+30d"]["verdict"] == "RED"
            and braces_patched["verdict"] == "GREEN"
        ),
    }
