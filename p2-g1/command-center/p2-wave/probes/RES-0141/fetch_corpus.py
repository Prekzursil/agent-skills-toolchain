#!/usr/bin/env python3
"""Fetch 100+ real GitHub release notes and freeze captures with lineage.

Does not import labels.py or detector.py. Re-runnable; skips captures that
already exist unless --refresh is passed.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import CAPTURES, CORPUS, dump_json, sha256_bytes  # noqa: E402
from contract import N_NOTES  # noqa: E402

UA = "ast-integrate-RES-0141-research (+https://github.com/)"
CTX = ssl.create_default_context()

# Repos with public GitHub Releases that typically carry changelog bodies.
REPOS: list[tuple[str, str]] = [
    ("pallets", "flask"),
    ("pallets", "click"),
    ("pallets", "werkzeug"),
    ("pallets", "jinja"),
    ("encode", "httpx"),
    ("encode", "starlette"),
    ("encode", "uvicorn"),
    ("pydantic", "pydantic"),
    ("fastapi", "fastapi"),
    ("pytest-dev", "pytest"),
    ("psf", "black"),
    ("urllib3", "urllib3"),
    ("redis", "redis-py"),
    ("sqlalchemy", "sqlalchemy"),
    ("aio-libs", "aiohttp"),
    ("python-poetry", "poetry"),
    ("Textualize", "rich"),
    ("tiangolo", "typer"),
    ("pypa", "pip"),
    ("celery", "celery"),
    ("vitejs", "vite"),
    ("facebook", "react"),
    ("pallets", "markupsafe"),
    ("pallets", "itsdangerous"),
]

METHODOLOGY = [
    {
        "id": "semver-spec",
        "url": "https://semver.org/",
        "role": "semver-major-definition",
    },
    {
        "id": "conventional-commits",
        "url": "https://www.conventionalcommits.org/en/v1.0.0/",
        "role": "breaking-change-footer-definition",
    },
    {
        "id": "keep-a-changelog",
        "url": "https://keepachangelog.com/en/1.1.0/",
        "role": "changelog-structure-definition",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, accept: str = "application/vnd.github+json") -> tuple[int, bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
        },
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=45) as resp:
            raw = resp.read()
            final = str(resp.geturl())
            status = int(resp.status)
            return status, raw, final, ""
    except urllib.error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        return int(exc.code), raw, url, f"HTTPError:{exc.code}"
    except urllib.error.URLError as exc:
        return 0, b"", url, f"URLError:{exc.reason}"


def save_capture(stem: str, url: str, status: int, raw: bytes, final: str) -> dict:
    CAPTURES.mkdir(parents=True, exist_ok=True)
    body_path = CAPTURES / f"{stem}.body"
    meta_path = CAPTURES / f"{stem}.meta.json"
    body_path.write_bytes(raw)
    meta = {
        "id": stem,
        "requested_url": url,
        "resolved_url": final,
        "http_status": status,
        "fetched_at": now_iso(),
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "body_path": str(body_path.relative_to(HERE.parent.parent.parent.parent).as_posix())
        if False
        else f"command-center/p2-wave/probes/RES-0141/captures/{stem}.body",
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def fetch_releases(owner: str, repo: str, per_page: int = 20) -> tuple[dict, list]:
    stem = f"github-{owner}-{repo}-releases"
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/releases"
        f"?per_page={per_page}&page=1"
    )
    meta_path = CAPTURES / f"{stem}.meta.json"
    body_path = CAPTURES / f"{stem}.body"
    if meta_path.is_file() and body_path.is_file() and not REFRESH:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        data = json.loads(body_path.read_text(encoding="utf-8"))
        return meta, data if isinstance(data, list) else []
    status, raw, final, err = http_get(url)
    meta = save_capture(stem, url, status, raw, final)
    if err:
        meta["error"] = err
        (CAPTURES / f"{stem}.meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = []
    if not isinstance(data, list):
        data = []
    return meta, data


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    text = (tag or "").strip()
    text = re.sub(r"^[^\d]*", "", text)
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        m = re.match(r"^(\d+)\.(\d+)$", text)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2)), 0
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def usable_body(body: str) -> bool:
    text = (body or "").strip()
    if len(text) < 40:
        return False
    # skip almost-empty "See CHANGELOG" stubs
    if len(text) < 80 and "changelog" in text.lower() and "http" in text.lower():
        return False
    return True


REFRESH = False


def fetch_methodology() -> list[dict]:
    rows = []
    for spec in METHODOLOGY:
        stem = spec["id"]
        meta_path = CAPTURES / f"{stem}.meta.json"
        body_path = CAPTURES / f"{stem}.body"
        if meta_path.is_file() and body_path.is_file() and not REFRESH:
            rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
            continue
        status, raw, final, err = http_get(spec["url"], accept="text/html")
        meta = save_capture(stem, spec["url"], status, raw, final)
        meta["role"] = spec["role"]
        if err:
            meta["error"] = err
        (CAPTURES / f"{stem}.meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        rows.append(meta)
        time.sleep(0.3)
    return rows


def main() -> int:
    global REFRESH
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    REFRESH = bool(args.refresh)

    methodology = fetch_methodology()
    notes: list[dict] = []
    repo_meta: list[dict] = []

    for owner, repo in REPOS:
        meta, releases = fetch_releases(owner, repo)
        repo_meta.append(
            {
                "owner": owner,
                "repo": repo,
                "http_status": meta.get("http_status"),
                "n_api_rows": len(releases),
                "capture_id": meta.get("id"),
                "sha256": meta.get("sha256"),
                "resolved_url": meta.get("resolved_url"),
                "fetched_at": meta.get("fetched_at"),
            }
        )
        print(
            f"repo {owner}/{repo} status={meta.get('http_status')} "
            f"n={len(releases)} sha={str(meta.get('sha256') or '')[:12]}"
        )
        parsed: list[tuple[tuple[int, int, int] | None, dict]] = []
        for rel in releases:
            if not isinstance(rel, dict):
                continue
            if rel.get("draft"):
                continue
            tag = str(rel.get("tag_name") or "")
            body = str(rel.get("body") or "")
            parsed.append((parse_semver(tag), rel))

        # previous tag = next row in GitHub's newest-first list that parses
        for i, (ver, rel) in enumerate(parsed):
            if rel.get("prerelease"):
                continue
            body = str(rel.get("body") or "")
            if not usable_body(body):
                continue
            prev_ver = None
            prev_tag = None
            for j in range(i + 1, len(parsed)):
                pv, prel = parsed[j]
                if prel.get("prerelease"):
                    continue
                if pv is not None:
                    prev_ver = pv
                    prev_tag = str(prel.get("tag_name") or "")
                    break
            tag = str(rel.get("tag_name") or "")
            note_id = f"{owner}-{repo}-{tag}".replace("/", "_")
            notes.append(
                {
                    "id": note_id,
                    "owner": owner,
                    "repo": repo,
                    "tag": tag,
                    "name": rel.get("name") or tag,
                    "html_url": rel.get("html_url"),
                    "api_url": rel.get("url"),
                    "published_at": rel.get("published_at"),
                    "prerelease": bool(rel.get("prerelease")),
                    "semver": list(ver) if ver else None,
                    "previous_tag": prev_tag,
                    "previous_semver": list(prev_ver) if prev_ver else None,
                    "body": body,
                    "body_sha256": sha256_bytes(body.encode("utf-8")),
                    "capture_id": meta.get("id"),
                    "source_lineage": {
                        "resolved_url": rel.get("html_url") or meta.get("resolved_url"),
                        "api_url": rel.get("url") or meta.get("requested_url"),
                        "fetch_timestamp": meta.get("fetched_at"),
                        "http_status": meta.get("http_status"),
                        "sha256_fetched_bytes": meta.get("sha256"),
                        "sha256_note_body": sha256_bytes(body.encode("utf-8")),
                        "capture_path": f"command-center/p2-wave/probes/RES-0141/captures/{meta.get('id')}.body",
                    },
                }
            )
        time.sleep(0.25)

    # Prefer a mix: keep all majors, fill with minors/patches, cap at N_NOTES
    # Selection is structural (semver), not detector-based.
    majors = []
    others = []
    for n in notes:
        cur = n.get("semver")
        prev = n.get("previous_semver")
        if (
            isinstance(cur, list)
            and isinstance(prev, list)
            and len(cur) >= 1
            and len(prev) >= 1
            and int(cur[0]) > int(prev[0])
        ):
            majors.append(n)
        else:
            others.append(n)

    selected: list[dict] = []
    seen = set()
    for n in majors + others:
        if n["id"] in seen:
            continue
        seen.add(n["id"])
        selected.append(n)
        if len(selected) >= N_NOTES:
            break

    corpus = {
        "unit_id": "RES-0141",
        "n_requested": N_NOTES,
        "n_selected": len(selected),
        "n_candidates": len(notes),
        "n_majors_available": len(majors),
        "selection_rule": (
            "GitHub Releases with body>=40 chars; skip draft/prerelease; "
            "prefer semver-major bumps vs previous parsed tag, then fill "
            "with remaining notes in API order. Selection does not read "
            "detector.py or labels.py."
        ),
        "methodology_captures": methodology,
        "repo_captures": repo_meta,
        "notes": selected,
    }
    dump_json(CORPUS, corpus)
    print(
        f"wrote {CORPUS} n_selected={len(selected)} "
        f"candidates={len(notes)} majors={len(majors)}"
    )
    if len(selected) < N_NOTES:
        print(f"FAILED:fetch need {N_NOTES} notes, got {len(selected)}")
        return 1
    print("SUCCESS:RES-0141-fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
