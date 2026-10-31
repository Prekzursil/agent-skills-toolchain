#!/usr/bin/env python3
"""Refill the 30-package sample using npms.io scores only (no npm-search 1.0 junk)."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from local_score import extract_features, offline_components, offline_score  # noqa: E402

PKG = HERE / "captures" / "packages"
UA = "ast-integrate-RES-0131/1.0 (research harvest)"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
REPO_REL = "command-center/p2-wave/probes/RES-0131"

CURATED = [
    "lodash",
    "express",
    "react",
    "commander",
    "debug",
    "chalk",
    "semver",
    "minimist",
    "glob",
    "ms",
    "mkdirp",
    "rimraf",
    "yargs",
    "axios",
    "eslint",
    "prettier",
    "mocha",
    "wrap-ansi",
    "type-fest",
    "left-pad",
    "is-odd",
    "is-even",
    "isarray",
    "object-assign",
    "once",
    "wrappy",
    "concat-map",
    "balanced-match",
    "xtend",
    "inflight",
    "flatten",
    "pad",
    "is-number",
    "kind-of",
    "arrify",
    "color-name",
    "escape-string-regexp",
    "path-is-absolute",
    "graceful-fs",
    "figures",
    "peertube-plugin-hello-world",
    "reft-pad",
    "magic-renamer",
]


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(resp.status), resp.read()


def sha256(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def github_repo(repository) -> str | None:
    if isinstance(repository, dict):
        url = str(repository.get("url") or "")
    else:
        url = str(repository or "")
    url = url.replace("git+", "").replace("git://", "https://")
    url = url.replace("github.com:", "github.com/")
    if "github.com/" not in url:
        return None
    tail = url.split("github.com/", 1)[1]
    if tail.endswith(".git"):
        tail = tail[:-4]
    parts = [p for p in tail.split("/") if p]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def harvest_one(name: str) -> dict | None:
    try:
        status, body = fetch(f"https://registry.npmjs.org/{urllib.parse.quote(name)}")
    except Exception as exc:
        print(f"packument fail {name}: {exc}")
        return None
    if status != 200:
        print(f"packument {name} status={status}")
        return None
    doc = json.loads(body.decode("utf-8"))
    latest = (doc.get("dist-tags") or {}).get("latest")
    ver = (doc.get("versions") or {}).get(latest) or {}
    dist = ver.get("dist") or {}
    tarball = dist.get("tarball")
    if not tarball:
        return None
    time.sleep(0.25)
    try:
        ts, tb = fetch(str(tarball), timeout=60)
    except Exception as exc:
        print(f"tarball fail {name}: {exc}")
        return None
    if ts != 200 or len(tb) < 40 or len(tb) > 8_000_000:
        print(f"tarball skip {name} status={ts} bytes={len(tb)}")
        return None
    feat = extract_features(tb)
    time.sleep(0.2)
    npms = None
    npms_url = f"https://api.npms.io/v2/package/{urllib.parse.quote(name)}"
    try:
        ns, nb = fetch(npms_url)
        if ns == 200:
            nd = json.loads(nb.decode("utf-8"))
            sc = (nd.get("score") or {}).get("detail") or {}
            if isinstance(sc.get("quality"), (int, float)):
                npms = {
                    "url": npms_url,
                    "http_status": ns,
                    "sha256": sha256(nb),
                    "final": (nd.get("score") or {}).get("final"),
                    "quality": sc.get("quality"),
                    "popularity": sc.get("popularity"),
                    "maintenance": sc.get("maintenance"),
                }
    except Exception as exc:
        print(f"npms fail {name}: {exc}")
    if npms is None:
        print(f"skip no npms {name}")
        return None
    repo = github_repo(
        feat.get("repository") or ver.get("repository") or doc.get("repository")
    )
    scorecard = None
    if repo:
        sc_url = f"https://api.securityscorecards.dev/projects/github.com/{repo}"
        try:
            ss, sb = fetch(sc_url, timeout=30)
            if ss == 200:
                scd = json.loads(sb.decode("utf-8"))
                scorecard = {
                    "repo": repo,
                    "score": scd.get("score"),
                    "date": scd.get("date"),
                    "url": sc_url,
                    "http_status": ss,
                    "sha256": sha256(sb),
                    "checks": [
                        {
                            "name": c.get("name"),
                            "score": c.get("score"),
                            "reason": (c.get("reason") or "")[:180],
                        }
                        for c in (scd.get("checks") or [])
                    ],
                }
        except Exception as exc:
            print(f"scorecard skip {name}: {exc}")
        time.sleep(0.15)
    rec = {
        "name": name,
        "version": latest,
        "ecosystem": "npm",
        "tarball_url": tarball,
        "tarball_sha256": sha256(tb),
        "tarball_bytes": len(tb),
        "integrity": dist.get("integrity"),
        "shasum": dist.get("shasum"),
        "fetched_at": NOW,
        "features": feat,
        "offline_components": offline_components(feat),
        "offline_score": offline_score(feat),
        "npms": npms,
        "scorecard": scorecard,
        "github_repo": repo,
        "online_quality": npms["quality"],
        "online_final": npms["final"],
        "online_score_source": "npms.io",
    }
    return rec


def pick_thirty(rows: list[dict]) -> list[dict]:
    rows = sorted(rows, key=lambda r: float(r["online_quality"]))
    if len(rows) <= 30:
        return rows
    n = len(rows)
    picks: list[dict] = []
    seen: set[str] = set()
    bands = [rows[: n // 3], rows[n // 3 : 2 * n // 3], rows[2 * n // 3 :]]
    for band in bands:
        step = max(1, len(band) // 10)
        i = 0
        taken = 0
        while taken < 10 and i < len(band) * 4:
            row = band[(i * step) % len(band)]
            i += 1
            if row["name"] in seen:
                continue
            seen.add(row["name"])
            picks.append(row)
            taken += 1
    return picks[:30]


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    harvested: list[dict] = []
    for name in CURATED:
        rec = harvest_one(name)
        if rec is None:
            continue
        harvested.append(rec)
        print(
            f"pkg {name} off={rec['offline_score']:.3f} "
            f"q={float(rec['online_quality']):.3f} final={float(rec['online_final']):.3f}"
        )
        time.sleep(0.2)
    if len(harvested) < 30:
        print(f"FAILED only {len(harvested)}")
        return 1
    chosen = pick_thirty(harvested)
    # wipe previous junk captures
    for old in PKG.glob("*.json"):
        old.unlink()
    for rec in chosen:
        (PKG / f"{rec['name']}.json").write_text(
            json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    sample = {
        "fetched_at": NOW,
        "n": len(chosen),
        "online_score_source": "npms.io",
        "packages": [
            {
                "name": r["name"],
                "version": r["version"],
                "offline_score": r["offline_score"],
                "online_quality": r["online_quality"],
                "online_final": r["online_final"],
                "online_score_source": "npms.io",
                "tarball_sha256": r["tarball_sha256"],
                "capture": f"{REPO_REL}/captures/packages/{r['name']}.json",
            }
            for r in chosen
        ],
    }
    (HERE / "captures" / "sample.json").write_text(
        json.dumps(sample, indent=2) + "\n", encoding="utf-8"
    )
    qs = [float(r["online_quality"]) for r in chosen]
    print(
        f"SUCCESS n={len(chosen)} quality min={min(qs):.3f} max={max(qs):.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
