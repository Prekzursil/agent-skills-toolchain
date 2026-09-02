#!/usr/bin/env python3
"""One-shot network harvest for RES-0131. Probes never import or run this."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
SRC = CAP / "sources"
PKG = CAP / "packages"
UA = "ast-integrate-RES-0131/1.0 (research harvest)"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
REPO_REL = "command-center/p2-wave/probes/RES-0131"

SOURCES = [
    {
        "id": "npms-quality-js",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/npms-io/npms-analyzer/master/lib/analyze/evaluate/quality.js",
    },
    {
        "id": "npms-score-js",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/npms-io/npms-analyzer/master/lib/scoring/score.js",
    },
    {
        "id": "npms-popularity-js",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/npms-io/npms-analyzer/master/lib/analyze/evaluate/popularity.js",
    },
    {
        "id": "npms-maintenance-js",
        "kind": "api",
        "url": "https://raw.githubusercontent.com/npms-io/npms-analyzer/master/lib/analyze/evaluate/maintenance.js",
    },
    {
        "id": "npms-architecture-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/npms-io/npms-analyzer/master/docs/architecture.md",
    },
    {
        "id": "npm-registry-api-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/npm/registry/main/docs/REGISTRY-API.md",
    },
    {
        "id": "scorecard-checks-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/ossf/scorecard/main/docs/checks.md",
    },
    {
        "id": "scorecard-readme-md",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/ossf/scorecard/main/README.md",
    },
    {
        "id": "packagist-apidoc-html",
        "kind": "prose",
        "url": "https://packagist.org/apidoc",
    },
    {
        "id": "packagist-issue-1368",
        "kind": "prose",
        "url": "https://api.github.com/repos/composer/packagist/issues/1368",
    },
    {
        "id": "packagist-monolog-json",
        "kind": "api",
        "url": "https://packagist.org/packages/monolog/monolog.json",
    },
    {
        "id": "silverstripe-moduleratings-readme",
        "kind": "prose",
        "url": "https://raw.githubusercontent.com/silverstripe/silverstripe-moduleratings/master/README.md",
    },
]

SEED_NAMES = [
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
    "pad",
    "flatten",
    "is-number",
    "kind-of",
    "arrify",
    "decamelize",
    "camelcase",
    "color-name",
    "escape-string-regexp",
    "path-is-absolute",
    "fs.realpath",
    "graceful-fs",
]

SEARCHES = [
    "express",
    "left-pad",
    "is-odd",
    "hello-world",
    "test-package",
    "keywords:cli",
    "keywords:util",
    "deprecated",
]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str, timeout: int = 45) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(), str(resp.headers.get("Content-Type") or "")
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return int(exc.code), body, ""


def save_source(item: dict) -> dict:
    SRC.mkdir(parents=True, exist_ok=True)
    status, body, ctype = fetch(item["url"])
    path = SRC / f"{item['id']}.bin"
    path.write_bytes(body)
    rec = {
        "id": item["id"],
        "kind": item["kind"],
        "permalink": item["url"],
        "requested_url": item["url"],
        "fetched_at": NOW,
        "http_status": status,
        "sha256": digest(body),
        "bytes": len(body),
        "content_type": ctype,
        "capture_path": f"{REPO_REL}/captures/sources/{item['id']}.bin",
        "snippet": body.decode("utf-8", errors="replace")[:240],
    }
    print(f"source {item['id']} status={status} bytes={len(body)}")
    return rec


def npm_search(text: str, size: int = 40) -> list[dict]:
    q = urllib.parse.quote(text)
    url = f"https://registry.npmjs.org/-/v1/search?text={q}&size={size}"
    status, body, _ = fetch(url)
    if status != 200:
        print(f"search fail {text} status={status}")
        return []
    doc = json.loads(body.decode("utf-8"))
    out: list[dict] = []
    for obj in doc.get("objects") or []:
        pkg = obj.get("package") or {}
        score = obj.get("score") or {}
        detail = score.get("detail") or {}
        name = pkg.get("name")
        if not name or "/" in str(name):
            continue
        out.append(
            {
                "name": name,
                "version": pkg.get("version"),
                "npm_search_final": score.get("final"),
                "npm_search_quality": detail.get("quality"),
                "npm_search_popularity": detail.get("popularity"),
                "npm_search_maintenance": detail.get("maintenance"),
                "search_query": text,
                "search_url": url,
            }
        )
    return out


def packument(name: str) -> dict:
    status, body, _ = fetch(
        f"https://registry.npmjs.org/{urllib.parse.quote(name)}"
    )
    if status != 200:
        raise RuntimeError(f"packument {name} status={status}")
    return json.loads(body.decode("utf-8"))


def extract_features(tar_bytes: bytes) -> dict:
    names: list[str] = []
    pkg: dict = {}
    readme_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            rel = member.name.split("/", 1)[-1]
            names.append(rel)
            low = rel.lower()
            base = low.split("/")[-1]
            if rel == "package.json":
                fh = tf.extractfile(member)
                if fh is not None:
                    pkg = json.loads(fh.read().decode("utf-8", errors="replace"))
            if base.startswith("readme"):
                readme_bytes += int(member.size or 0)
    low_names = [n.lower() for n in names]
    bases = [n.split("/")[-1] for n in low_names]
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    deps = pkg.get("dependencies") if isinstance(pkg.get("dependencies"), dict) else {}
    unlocked = 0
    for ver in deps.values():
        s = str(ver).strip()
        if s in {"*", "latest", ">=0.0.0", ">0.0.0"}:
            unlocked += 1
    license_field = pkg.get("license")
    has_license_field = bool(license_field) and str(license_field).strip() not in {
        "",
        "UNLICENSED",
        "UNLICENCED",
    }
    has_license_file = any(
        b.startswith("license") or b.startswith("licence") or b == "copying"
        for b in bases
    )
    has_changelog = any(
        b.startswith("changelog") or b.startswith("changes") or b.startswith("history")
        for b in bases
    )
    linter_needles = (
        "eslint",
        "prettier",
        "jshint",
        "jscs",
        "standard",
        "biome",
        "xo.config",
    )
    has_linter = any(any(x in n for x in linter_needles) for n in low_names)
    if isinstance(pkg.get("eslintConfig"), dict) or pkg.get("prettier"):
        has_linter = True
    if any(k in scripts for k in ("lint", "eslint", "prettier")):
        has_linter = True
    test_cmd = str(scripts.get("test") or "").strip()
    has_test_script = bool(test_cmd) and "no test specified" not in test_cmd.lower()
    has_test_files = any(
        part in {"test", "tests", "__tests__", "spec"}
        for n in low_names
        for part in n.split("/")[:-1]
    ) or any(".test." in b or ".spec." in b for b in bases)
    has_npmignore = any(b == ".npmignore" for b in bases)
    has_files_field = isinstance(pkg.get("files"), list) and bool(pkg.get("files"))
    has_security = any(b.startswith("security") for b in bases)
    has_lock = any(
        b
        in {
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        }
        for b in bases
    )
    binary_hits = [
        n
        for n in names
        if n.lower().endswith((".exe", ".dll", ".so", ".dylib", ".a"))
    ]
    return {
        "file_count": len(names),
        "readme_bytes": readme_bytes,
        "has_license_field": has_license_field,
        "has_license_file": has_license_file,
        "has_changelog": has_changelog,
        "has_linter": has_linter,
        "has_npmignore": has_npmignore,
        "has_files_field": has_files_field,
        "has_test_script": has_test_script,
        "has_test_files": has_test_files,
        "has_security_md": has_security,
        "has_lockfile": has_lock,
        "binary_artifact_count": len(binary_hits),
        "unlocked_dep_count": unlocked,
        "deprecated_in_manifest": bool(pkg.get("deprecated")),
        "license": license_field
        if isinstance(license_field, str)
        else json.dumps(license_field)
        if license_field
        else None,
        "scripts_keys": sorted(scripts),
        "repository": pkg.get("repository"),
        "sample_files": sorted(names)[:80],
    }


def offline_components(feat: dict) -> dict[str, float]:
    return {
        "has_license": 1.0
        if feat["has_license_field"] or feat["has_license_file"]
        else 0.0,
        "readme_norm": min(float(feat["readme_bytes"]) / 400.0, 1.0),
        "has_changelog": 1.0 if feat["has_changelog"] else 0.0,
        "has_linter": 1.0 if feat["has_linter"] else 0.0,
        "has_ignore_or_files": 1.0
        if feat["has_npmignore"] or feat["has_files_field"]
        else 0.0,
        "has_test_script": 1.0 if feat["has_test_script"] else 0.0,
        "has_test_files": 1.0 if feat["has_test_files"] else 0.0,
        "not_deprecated": 0.0 if feat["deprecated_in_manifest"] else 1.0,
        "has_security_md": 1.0 if feat["has_security_md"] else 0.0,
        "no_binary_artifacts": 1.0 if feat["binary_artifact_count"] == 0 else 0.0,
        "has_lockfile": 1.0 if feat["has_lockfile"] else 0.0,
        "no_unlocked_deps": 1.0 if feat["unlocked_dep_count"] == 0 else 0.0,
    }


def offline_score(feat: dict) -> float:
    parts = offline_components(feat)
    return sum(parts.values()) / float(len(parts))


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


def harvest_package(name: str, search_row: dict | None) -> dict | None:
    try:
        doc = packument(name)
    except Exception as exc:
        print(f"skip packument {name}: {exc}")
        return None
    latest = (doc.get("dist-tags") or {}).get("latest")
    versions = doc.get("versions") or {}
    ver = versions.get(latest) or {}
    dist = ver.get("dist") or {}
    tarball = dist.get("tarball")
    if not tarball:
        print(f"skip no tarball {name}")
        return None
    status, tar_bytes, _ = fetch(str(tarball), timeout=60)
    if status != 200 or len(tar_bytes) < 40:
        print(f"skip tarball {name} status={status} bytes={len(tar_bytes)}")
        return None
    if len(tar_bytes) > 8_000_000:
        print(f"skip huge tarball {name} bytes={len(tar_bytes)}")
        return None
    feat = extract_features(tar_bytes)
    repo = github_repo(
        feat.get("repository") or ver.get("repository") or doc.get("repository")
    )
    scorecard = None
    if repo:
        sc_url = f"https://api.securityscorecards.dev/projects/github.com/{repo}"
        sc_status, sc_body, _ = fetch(sc_url, timeout=30)
        if sc_status == 200:
            try:
                sc = json.loads(sc_body.decode("utf-8"))
                checks = [
                    {
                        "name": c.get("name"),
                        "score": c.get("score"),
                        "reason": (c.get("reason") or "")[:180],
                    }
                    for c in (sc.get("checks") or [])
                ]
                scorecard = {
                    "repo": repo,
                    "score": sc.get("score"),
                    "date": sc.get("date"),
                    "url": sc_url,
                    "http_status": sc_status,
                    "sha256": digest(sc_body),
                    "checks": checks,
                }
            except json.JSONDecodeError:
                scorecard = None
    npms = None
    npms_url = f"https://api.npms.io/v2/package/{urllib.parse.quote(name)}"
    ns, nb, _ = fetch(npms_url, timeout=30)
    if ns == 200:
        try:
            nd = json.loads(nb.decode("utf-8"))
            sc = (nd.get("score") or {}).get("detail") or {}
            npms = {
                "url": npms_url,
                "http_status": ns,
                "sha256": digest(nb),
                "final": (nd.get("score") or {}).get("final"),
                "quality": sc.get("quality"),
                "popularity": sc.get("popularity"),
                "maintenance": sc.get("maintenance"),
            }
        except json.JSONDecodeError:
            npms = None
    rec = {
        "name": name,
        "version": latest,
        "ecosystem": "npm",
        "tarball_url": tarball,
        "tarball_sha256": digest(tar_bytes),
        "tarball_bytes": len(tar_bytes),
        "integrity": dist.get("integrity"),
        "shasum": dist.get("shasum"),
        "fetched_at": NOW,
        "features": feat,
        "offline_components": offline_components(feat),
        "offline_score": offline_score(feat),
        "npm_search": search_row or {},
        "npms": npms,
        "scorecard": scorecard,
        "github_repo": repo,
        "online_quality": (search_row or {}).get("npm_search_quality"),
        "online_final": (search_row or {}).get("npm_search_final"),
        "online_score_source": "npm-search",
    }
    if npms and isinstance(npms.get("quality"), (int, float)):
        rec["online_quality"] = npms["quality"]
        rec["online_final"] = npms["final"]
        rec["online_score_source"] = "npms.io"
    return rec


def pick_thirty(candidates: list[dict]) -> list[str]:
    scored = [
        c
        for c in candidates
        if isinstance(c.get("npm_search_quality"), (int, float))
    ]
    scored.sort(key=lambda c: float(c["npm_search_quality"]))
    if len(scored) < 30:
        names: list[str] = []
        seen: set[str] = set()
        for c in scored + candidates:
            if c["name"] in seen:
                continue
            seen.add(c["name"])
            names.append(c["name"])
            if len(names) >= 45:
                break
        return names
    n = len(scored)
    picks: list[str] = []
    seen: set[str] = set()
    bands = [
        scored[: max(1, n // 3)],
        scored[n // 3 : 2 * n // 3],
        scored[2 * n // 3 :],
    ]
    for band in bands:
        step = max(1, len(band) // 10)
        i = 0
        taken = 0
        while taken < 10 and i < len(band) * 3:
            row = band[(i * step) % len(band)]
            i += 1
            if row["name"] in seen:
                continue
            seen.add(row["name"])
            picks.append(row["name"])
            taken += 1
    return picks


def main() -> int:
    SRC.mkdir(parents=True, exist_ok=True)
    PKG.mkdir(parents=True, exist_ok=True)
    sources = [save_source(item) for item in SOURCES]
    (CAP / "sources-index.json").write_text(
        json.dumps({"fetched_at": NOW, "rails": sources}, indent=2) + "\n",
        encoding="utf-8",
    )

    by_name: dict[str, dict] = {}
    for query in SEARCHES:
        for row in npm_search(query, size=40):
            by_name.setdefault(row["name"], row)
        time.sleep(0.15)
    for name in SEED_NAMES:
        if name in by_name:
            continue
        rows = npm_search(name, size=1)
        if rows and rows[0]["name"] == name:
            by_name[name] = rows[0]
        else:
            by_name[name] = {"name": name}
        time.sleep(0.08)

    picks = pick_thirty(list(by_name.values()))
    print("picks", picks)

    harvested: list[dict] = []
    for name in picks:
        rec = harvest_package(name, by_name.get(name))
        if rec is None or rec.get("online_quality") is None:
            print(f"skip incomplete {name}")
            continue
        path = PKG / f"{name}.json"
        path.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        harvested.append(rec)
        print(
            f"pkg {name} off={rec['offline_score']:.3f} "
            f"q={float(rec['online_quality']):.3f} src={rec['online_score_source']}"
        )
        if len(harvested) >= 30:
            break
        time.sleep(0.08)

    if len(harvested) < 30:
        extra = [n for n in SEED_NAMES if n not in {r["name"] for r in harvested}]
        for name in extra:
            rec = harvest_package(name, by_name.get(name) or {"name": name})
            if rec is None or rec.get("online_quality") is None:
                continue
            path = PKG / f"{name}.json"
            path.write_text(
                json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            harvested.append(rec)
            print(
                f"pkg {name} off={rec['offline_score']:.3f} "
                f"q={float(rec['online_quality']):.3f} src={rec['online_score_source']}"
            )
            if len(harvested) >= 30:
                break
            time.sleep(0.08)

    if len(harvested) < 30:
        print(f"FAILED harvest only {len(harvested)}")
        return 1
    harvested = harvested[:30]
    sample = {
        "fetched_at": NOW,
        "n": len(harvested),
        "packages": [
            {
                "name": r["name"],
                "version": r["version"],
                "offline_score": r["offline_score"],
                "online_quality": r["online_quality"],
                "online_final": r["online_final"],
                "online_score_source": r["online_score_source"],
                "tarball_sha256": r["tarball_sha256"],
                "capture": f"{REPO_REL}/captures/packages/{r['name']}.json",
            }
            for r in harvested
        ],
    }
    (CAP / "sample.json").write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS harvested {len(harvested)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
