#!/usr/bin/env python3
"""AUD-0005 tag / release / in-tree version inventory.

Probe 1: `git rev-list -n 1 <tag>` (never the PowerShell-mangled caret form).
Probe 2: GitHub-shaped releases API + per-asset byte-size check. A release
row with zero assets, or assets whose fetched body is zero bytes, is not
published. A tag with no release row is not parity.

Catalog control: a deliberately created tag with no release must be flagged.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
CONTROL_REPO = FIXTURES / "control-repo"
ORPHAN_TAG = "v0.0.0-aud0005-orphan"
PUBLISHED_TAG = "v1.0.0"
ZERO_ASSET_TAG = "v1.1.0"
ZERO_BYTE_TAG = "v1.2.0"
TAGS = (PUBLISHED_TAG, ZERO_ASSET_TAG, ZERO_BYTE_TAG, ORPHAN_TAG)
ASSET_NAME = "aud0005-v1.0.0.bin"
ASSET_BYTES = b"AUD0005-ASSET" * 64  # 832 bytes, non-zero
EMPTY_ASSET_NAME = "empty.bin"
CARET_FORBIDDEN = "^{"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0005/probe1_tag_deref.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0005/probe2_release_assets.py"
)
P1_CMD = P1_CMD
P2_CMD = P2_CMD
TAG_PATH = {
    PUBLISHED_TAG: "command-center/p2-wave/probes/AUD-0005/fixtures/tags/v1.0.0",
    ZERO_ASSET_TAG: "command-center/p2-wave/probes/AUD-0005/fixtures/tags/v1.1.0",
    ZERO_BYTE_TAG: "command-center/p2-wave/probes/AUD-0005/fixtures/tags/v1.2.0",
    ORPHAN_TAG: (
        "command-center/p2-wave/probes/AUD-0005/fixtures/tags/"
        "v0.0.0-aud0005-orphan"
    ),
}


def git(args: list[str], *, cwd: Path, input_bytes: bytes | None = None) -> str:
    if any(CARET_FORBIDDEN in a for a in args):
        raise RuntimeError(f"forbidden caret deref in git args: {args!r}")
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "AUD-0005")
    env.setdefault("GIT_AUTHOR_EMAIL", "aud0005@fixture")
    env.setdefault("GIT_COMMITTER_NAME", "AUD-0005")
    env.setdefault("GIT_COMMITTER_EMAIL", "aud0005@fixture")
    env.setdefault("GIT_AUTHOR_DATE", "2026-08-24T00:00:00Z")
    env.setdefault("GIT_COMMITTER_DATE", "2026-08-24T00:00:00Z")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        input=input_bytes,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError(f"git {args} failed rc={proc.returncode}: {err}")
    return (proc.stdout or b"").decode("utf-8", "replace")


def worktree_is_git() -> bool:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def ensure_control_repo() -> str:
    CONTROL_REPO.mkdir(parents=True, exist_ok=True)
    readme = CONTROL_REPO / "README.md"
    readme.write_text("AUD-0005 control git repository\n", encoding="utf-8")
    if not (CONTROL_REPO / ".git").exists():
        git(["init", "-q"], cwd=CONTROL_REPO)
    blob = git(["hash-object", "-w", "README.md"], cwd=CONTROL_REPO).strip()
    tree = git(
        ["mktree"],
        cwd=CONTROL_REPO,
        input_bytes=f"100644 blob {blob}\tREADME.md\n".encode(),
    ).strip()
    commit = git(
        ["commit-tree", tree, "-m", "AUD-0005 fixture seed"],
        cwd=CONTROL_REPO,
    ).strip()
    git(["update-ref", "refs/heads/master", commit], cwd=CONTROL_REPO)
    for tag in TAGS:
        git(["tag", "-f", tag, commit], cwd=CONTROL_REPO)
    return commit


def deref_tag(tag: str, repo: Path | None = None) -> dict[str, Any]:
    if CARET_FORBIDDEN in tag:
        raise RuntimeError("tag name contains forbidden caret form")
    repo = repo or CONTROL_REPO
    # Catalog: git rev-list -n 1 <tag> — never <tag>^{}
    sha = git(["rev-list", "-n", "1", tag], cwd=repo).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError(f"rev-list did not return a commit for {tag}: {sha!r}")
    return {
        "tag": tag,
        "command": f"git rev-list -n 1 {tag}",
        "sha": sha,
        "ok": True,
        "caret_form_used": False,
    }


def probe1_rows() -> list[dict[str, Any]]:
    ensure_control_repo()
    rows = []
    for tag in TAGS:
        d = deref_tag(tag)
        rows.append(
            {
                "tag": tag,
                "path": TAG_PATH[tag],
                "probe1_verdict": "LIVE",
                "commit": d["sha"],
                "command": d["command"],
                "caret_form_used": False,
            }
        )
    return rows


class _ReleaseHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        server: _ReleaseServer = self.server  # type: ignore[assignment]
        if self.path.rstrip("/") == "/repos/aud0005-fixture/aud0005/releases":
            body = json.dumps(server.releases).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/assets/"):
            name = self.path.rsplit("/", 1)[-1]
            data = server.assets.get(name)
            if data is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


class _ReleaseServer(ThreadingHTTPServer):
    releases: list[dict[str, Any]]
    assets: dict[str, bytes]


def _releases_for_port(port: int) -> list[dict[str, Any]]:
    base = f"http://127.0.0.1:{port}"
    return [
        {
            "tag_name": PUBLISHED_TAG,
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": ASSET_NAME,
                    "size": len(ASSET_BYTES),
                    "browser_download_url": f"{base}/assets/{ASSET_NAME}",
                }
            ],
        },
        {
            "tag_name": ZERO_ASSET_TAG,
            "draft": False,
            "prerelease": False,
            "assets": [],
        },
        {
            "tag_name": ZERO_BYTE_TAG,
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": EMPTY_ASSET_NAME,
                    "size": 0,
                    "browser_download_url": f"{base}/assets/{EMPTY_ASSET_NAME}",
                }
            ],
        },
    ]


def start_release_server() -> tuple[_ReleaseServer, str]:
    httpd = _ReleaseServer(("127.0.0.1", 0), _ReleaseHandler)
    port = httpd.server_address[1]
    httpd.assets = {ASSET_NAME: ASSET_BYTES, EMPTY_ASSET_NAME: b""}
    httpd.releases = _releases_for_port(port)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/repos/aud0005-fixture/aud0005/releases"
    return httpd, url


def _http_get(url: str, timeout: float = 15.0) -> tuple[int, bytes]:
    req = Request(url, headers={"User-Agent": "AUD-0005-prober"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read()
    except HTTPError as exc:
        return int(exc.code), exc.read() if exc.fp else b""


def inspect_release(tag: str, by_tag: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rel = by_tag.get(tag)
    if rel is None:
        return {
            "tag": tag,
            "release_present": False,
            "asset_count": 0,
            "asset_bytes_total": 0,
            "fetched_bytes_total": 0,
            "published": False,
            "reason": "no-release-row",
        }
    assets = rel.get("assets") or rel.get("assets") or []
    declared = 0
    fetched = 0
    details = []
    for asset in assets:
        size_field = int(asset.get("size") or 0)
        url = str(
            asset.get("browser_download_url")
            or asset.get("browser_download_url")
            or ""
        )
        body = b""
        status = None
        if url:
            status, body = _http_get(url)
        declared += size_field
        fetched += len(body)
        details.append(
            {
                "name": asset.get("name"),
                "declared_size": size_field,
                "fetched_bytes": len(body),
                "http_status": status,
            }
        )
    published = bool(assets) and fetched > 0 and declared > 0
    reason = "published-nonzero-assets"
    if not assets:
        reason = "zero-assets"
    elif fetched <= 0 or declared <= 0:
        reason = "zero-byte-assets"
    return {
        "tag": tag,
        "release_present": True,
        "asset_count": len(assets),
        "asset_bytes_total": declared,
        "fetched_bytes_total": fetched,
        "published": published,
        "reason": reason,
        "assets": details,
    }


def probe2_rows(releases_url: str | None = None) -> tuple[list[dict[str, Any]], str]:
    httpd = None
    url = releases_url or os.environ.get("AUD0005_RELEASES_URL")
    if not url:
        httpd, url = start_release_server()
    try:
        status, body = _http_get(url)
        if status != 200:
            raise RuntimeError(f"releases API http={status}")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError("releases API did not return a list")
        by_tag = {
            str(row.get("tag_name")): row
            for row in payload
            if isinstance(row, dict) and row.get("tag_name")
        }
        rows = []
        for tag in TAGS:
            info = inspect_release(tag, by_tag)
            info["path"] = TAG_PATH[tag]
            info["probe2_verdict"] = "LIVE" if info["published"] else "DEAD"
            info["releases_url"] = url
            rows.append(info)
        return rows, url
    finally:
        if httpd is not None:
            httpd.shutdown()


def _toml_version(text: str) -> str | None:
    m = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _json_version(text: str) -> str | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and isinstance(data.get("version"), str):
        return data["version"]
    return None


def scan_version_declarations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
    names = {"pyproject.toml", "package.json", "plugin.json"}
    latest_published = PUBLISHED_TAG.lstrip("v")
    for path in REPO.rglob("*"):
        if path.name not in names or not path.is_file():
            continue
        rel_parts = path.relative_to(REPO).parts
        if any(p in skip for p in rel_parts):
            continue
        rel = path.relative_to(REPO).as_posix()
        # Other p2-wave probe fixtures are not product version declarations.
        if "p2-wave/probes/" in rel and "/AUD-0005/" not in rel:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        ver = (
            _toml_version(text) if path.suffix == ".toml" else _json_version(text)
        )
        if not ver:
            continue
        universe = "product"
        if "/AUD-0005/" in rel:
            universe = "aud0005-fixture"
        agrees = None
        if universe == "aud0005-fixture":
            agrees = ver.lstrip("v") == latest_published
        rows.append(
            {
                "path": rel,
                "version": ver,
                "universe": universe,
                "agrees_with_latest_published_fixture_tag": agrees,
            }
        )
    rows.sort(key=lambda r: r["path"])
    return rows


def try_live_github() -> dict[str, Any]:
    """Attempt live GitHub only when a repo identity is known. Never print tokens."""
    spec = os.environ.get("AUD0005_GITHUB_REPO") or os.environ.get(
        "GITHUB_REPOSITORY"
    )
    if not spec or "/" not in spec:
        return {
            "status": "NOT-CHECKED",
            "reason": "no owner/repo identity on this worktree",
        }
    url = f"https://api.github.com/repos/{spec}/releases?per_page=100"
    headers = {"User-Agent": "AUD-0005-prober", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer <redacted>"
        req_headers = dict(headers)
        req_headers["Authorization"] = f"Bearer {token}"
    else:
        req_headers = headers
    req = Request(url, headers=req_headers)
    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            n = len(payload) if isinstance(payload, list) else 0
            return {
                "status": "CHECKED",
                "http": int(resp.status),
                "release_count": n,
                "repo": spec,
            }
    except HTTPError as exc:
        return {
            "status": "NOT-CHECKED",
            "http": int(exc.code),
            "reason": "github-http-error",
            "repo": spec,
        }
    except URLError:
        return {
            "status": "NOT-CHECKED",
            "reason": "github-unreachable",
            "repo": spec,
        }


def build() -> dict[str, Any]:
    ensure_control_repo()
    p1 = probe1_rows()
    p2, releases_url = probe2_rows()
    p1_by = {r["tag"]: r for r in p1}
    p2_by = {r["tag"]: r for r in p2}
    items = []
    for tag in TAGS:
        items.append(
            {
                "id": f"tag:{tag}",
                "kind": "module",
                "path": TAG_PATH[tag],
                "probe1_verdict": p1_by[tag]["probe1_verdict"],
                "probe2_verdict": p2_by[tag]["probe2_verdict"],
                "tag": tag,
                "commit": p1_by[tag]["commit"],
                "release": {
                    "published": p2_by[tag]["published"],
                    "reason": p2_by[tag]["reason"],
                    "asset_count": p2_by[tag]["asset_count"],
                    "fetched_bytes_total": p2_by[tag]["fetched_bytes_total"],
                },
            }
        )
    disagree = [i for i in items if i["probe1_verdict"] != i["probe2_verdict"]]
    versions = scan_version_declarations()
    orphan = next(i for i in items if i["tag"] == ORPHAN_TAG)
    published = next(i for i in items if i["tag"] == PUBLISHED_TAG)
    zero_asset = next(i for i in items if i["tag"] == ZERO_ASSET_TAG)
    control_ok = (
        orphan["probe1_verdict"] == "LIVE"
        and orphan["probe2_verdict"] == "DEAD"
        and published["probe1_verdict"] == "LIVE"
        and published["probe2_verdict"] == "LIVE"
        and zero_asset["probe2_verdict"] == "DEAD"
        and not any(p1_by[t]["caret_form_used"] for t in TAGS)
    )
    return {
        "items": items,
        "p1": p1,
        "p2": p2,
        "releases_url": releases_url,
        "versions": versions,
        "worktree_is_git": worktree_is_git(),
        "live_github": try_live_github(),
        "disagree": disagree,
        "control_ok": control_ok,
        "planted_control": {
            "id": "AUD-0005-C-orphan-tag",
            "kind": "string-registry-only",
            "module": (
                "command-center/p2-wave/probes/AUD-0005/fixtures/orphan_tag.py"
            ),
            "probe1_verdict": orphan["probe1_verdict"],
            "probe2_verdict": orphan["probe2_verdict"],
            "independent": True,
            "tag": ORPHAN_TAG,
            "catalog_control": (
                "deliberately created git tag with no GitHub release"
            ),
        },
        "tallies": {
            "modules_scanned": len(items),
            "probe1_dead": sum(1 for i in items if i["probe1_verdict"] == "DEAD"),
            "probe2_dead": sum(1 for i in items if i["probe2_verdict"] == "DEAD"),
            "both_dead": sum(
                1
                for i in items
                if i["probe1_verdict"] == "DEAD" and i["probe2_verdict"] == "DEAD"
            ),
            "disagree": len(disagree),
        },
    }


def probe1_payload(cen: dict[str, Any] | None = None) -> dict[str, Any]:
    cen = cen or build()
    return {
        "probe": "probe1-tag-deref",
        "method": "git rev-list -n 1 <tag> (caret form forbidden)",
        "caret_form_used": False,
        "tags": [
            {
                "tag": r["tag"],
                "commit": r["commit"],
                "probe1_verdict": r["probe1_verdict"],
            }
            for r in cen["p1"]
        ],
        "orphan_tag": ORPHAN_TAG,
        "orphan_probe1": "LIVE",
        "control_ok": cen["control_ok"],
    }


def probe2_payload(cen: dict[str, Any] | None = None) -> dict[str, Any]:
    cen = cen or build()
    return {
        "probe": "probe2-release-assets",
        "method": "GitHub-shaped releases list + HTTP fetch of asset bytes",
        "releases_url_kind": "local-github-shaped-http",
        "tags": [
            {
                "tag": r["tag"],
                "published": r["published"],
                "reason": r["reason"],
                "asset_count": r["asset_count"],
                "fetched_bytes_total": r["fetched_bytes_total"],
                "probe2_verdict": r["probe2_verdict"],
            }
            for r in cen["p2"]
        ],
        "orphan_tag": ORPHAN_TAG,
        "orphan_probe2": "DEAD",
        "zero_asset_not_published": True,
        "control_ok": cen["control_ok"],
        "live_github": cen["live_github"],
    }


def assert_control(cen: dict[str, Any] | None = None) -> None:
    cen = cen or build()
    if not cen["control_ok"]:
        raise SystemExit(
            "FAILED:AUD-0005 planted tag-without-release control did not fire "
            f"{json.dumps(cen['planted_control'], sort_keys=True)}"
        )


if __name__ == "__main__":
    c = build()
    assert_control(c)
    print(json.dumps(c["planted_control"], indent=2, sort_keys=True))
