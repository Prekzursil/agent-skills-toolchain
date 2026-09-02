"""HTTP resolver that records every redirect hop (never silent follow)."""
from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from mappings import INVALID_URL

USER_AGENT = "RES-0042-mcp-census/1.0 (research snapshot; +local-worktree)"
TIMEOUT = 8
MAX_HOPS = 8
_API_CACHE: dict[str, dict] = {}
_RESOLVE_CACHE: dict[str, dict] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_http_url(url: str) -> bool:
    return isinstance(url, str) and url.lower().startswith(("http://", "https://"))


def is_planted_invalid(url: str) -> bool:
    if not isinstance(url, str):
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    return host.endswith(".invalid") or url == INVALID_URL


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoFollow)


def _request(url: str, method: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        method=method,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        },
    )


def _one_hop(url: str, method: str = "HEAD") -> dict[str, Any]:
    """Fetch one hop without following redirects. HEAD may 405; retry GET."""
    opener = _opener()
    try:
        try:
            with opener.open(_request(url, method), timeout=TIMEOUT) as resp:
                return {
                    "url": url,
                    "status": int(getattr(resp, "status", None) or resp.getcode() or 0),
                    "location": resp.headers.get("Location") or resp.headers.get("location"),
                    "final": False,
                    "error": None,
                }
        except urllib.error.HTTPError as exc:
            loc = exc.headers.get("Location") if exc.headers else None
            return {
                "url": url,
                "status": int(exc.code or 0),
                "location": loc,
                "final": exc.code not in {301, 302, 303, 307, 308},
                "error": None if loc or exc.code else str(exc.reason),
            }
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return {
            "url": url,
            "status": 0,
            "location": None,
            "final": True,
            "error": f"URLError:{type(reason).__name__}:{reason}",
        }
    except (TimeoutError, socket.timeout, ssl.SSLError, ValueError, OSError) as exc:
        return {
            "url": url,
            "status": 0,
            "location": None,
            "final": True,
            "error": f"{type(exc).__name__}:{exc}",
        }


def _join(base: str, loc: str) -> str:
    return urllib.parse.urljoin(base, loc)


def resolve_url(url: str, *, method: str = "HEAD") -> dict[str, Any]:
    """Resolve url, recording the redirect chain. Never skip. Never silent-follow."""
    cache_key = f"{method}:{url}"
    if cache_key in _RESOLVE_CACHE:
        return dict(_RESOLVE_CACHE[cache_key])
    fetched_at = now_iso()
    if not is_http_url(url):
        return {
            "declared_url": url,
            "final_url": url if url else "UNMAPPED",
            "http_status": 0,
            "redirect_chain": [],
            "resolvable": False,
            "status": "UNRESOLVABLE" if url not in {"", "UNMAPPED"} else "UNMAPPED",
            "error": "not-an-http-url",
            "skipped": False,
            "snapshot_timestamp": fetched_at,
        }
    chain: list[dict[str, Any]] = []
    current = url
    seen: set[str] = set()
    for _ in range(MAX_HOPS):
        if current in seen:
            chain.append(
                {
                    "url": current,
                    "status": 0,
                    "location": None,
                    "final": True,
                    "error": "redirect-loop",
                }
            )
            break
        seen.add(current)
        hop = _one_hop(current, method=method)
        if method == "HEAD" and hop.get("status") in {0, 403, 405, 429, 501} and not hop.get("location"):
            hop = _one_hop(current, method="GET")
        chain.append(hop)
        loc = hop.get("location")
        code = int(hop.get("status") or 0)
        if loc and code in {301, 302, 303, 307, 308}:
            current = _join(current, str(loc))
            continue
        break
    last = chain[-1] if chain else {}
    last_status = int(last.get("status") or 0)
    last_err = last.get("error")
    # Final URL is the last hop we actually requested, not a silent target.
    final_url = str(last.get("url") or url)
    if last.get("location") and last_status in {301, 302, 303, 307, 308}:
        # Chain exhausted while still redirecting: record destination, keep 3xx.
        final_url = _join(final_url, str(last["location"]))
    resolvable = last_status > 0 and last_err not in {"redirect-loop"} and not str(last_err or "").startswith(
        ("URLError", "TimeoutError", "SSLError")
    )
    status_token = "RESOLVED" if last_status and last_status < 400 else (
        "UNRESOLVABLE" if last_status == 0 else "HTTP-ERROR"
    )
    if last_status in {301, 302, 303, 307, 308}:
        status_token = "REDIRECT-RECORDED"
    out = {
        "declared_url": url,
        "final_url": final_url,
        "http_status": last_status,
        "redirect_chain": chain,
        "resolvable": bool(resolvable and last_status != 0),
        "status": status_token if last_status != 0 else "UNRESOLVABLE",
        "error": last_err,
        "skipped": False,
        "snapshot_timestamp": fetched_at,
        "redirected": any(
            int(h.get("status") or 0) in {301, 302, 303, 307, 308} for h in chain
        ),
    }
    _RESOLVE_CACHE[cache_key] = out
    return dict(out)


def naive_skip_invalid(urls: list[str]) -> list[str]:
    """Mutant: drop planted-invalid / .invalid hosts instead of reporting them."""
    return [u for u in urls if is_http_url(u) and not is_planted_invalid(u)]


def github_owner_repo(url: str) -> tuple[str, str] | None:
    if not is_http_url(url):
        return None
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if owner.lower() in {"orgs", "users", "settings"}:
        return None
    return owner, repo


def github_api_json(path: str) -> dict[str, Any]:
    if path in _API_CACHE:
        return dict(_API_CACHE[path])
    url = "https://api.github.com" + path
    fetched_at = now_iso()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url,
        method="GET",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", None) or resp.getcode() or 0)
            try:
                body = json.loads(raw.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                body = None
            out = {
                "ok": True,
                "http_status": status,
                "json": body,
                "snapshot_timestamp": fetched_at,
                "url": url,
                "error": None,
                "sha256_len": len(raw),
            }
            _API_CACHE[path] = out
            return dict(out)
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read() or b""
        except Exception:
            raw = b""
        body = None
        try:
            body = json.loads(raw.decode("utf-8", errors="replace")) if raw else None
        except json.JSONDecodeError:
            body = None
        out = {
            "ok": False,
            "http_status": int(exc.code or 0),
            "json": body,
            "snapshot_timestamp": fetched_at,
            "url": url,
            "error": f"HTTPError:{exc.code}",
            "sha256_len": len(raw),
        }
        _API_CACHE[path] = out
        return dict(out)
    except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, OSError) as exc:
        out = {
            "ok": False,
            "http_status": 0,
            "json": None,
            "snapshot_timestamp": fetched_at,
            "url": url,
            "error": f"{type(exc).__name__}:{exc}",
            "sha256_len": 0,
        }
        _API_CACHE[path] = out
        return dict(out)


def fetch_github_meta(owner: str, repo: str) -> dict[str, Any]:
    repo_doc = github_api_json(f"/repos/{owner}/{repo}")
    rel_doc = github_api_json(f"/repos/{owner}/{repo}/releases/latest")
    info = repo_doc.get("json") if isinstance(repo_doc.get("json"), dict) else {}
    rel = rel_doc.get("json") if isinstance(rel_doc.get("json"), dict) else {}
    last_release = None
    release_tag = None
    sha = None
    sha_doc: dict[str, Any] = {}
    if rel_doc.get("http_status") == 200 and rel:
        last_release = rel.get("published_at") or rel.get("created_at")
        release_tag = rel.get("tag_name")
        sha = rel.get("target_commitish")
    elif rel_doc.get("http_status") == 404:
        last_release = "NO-GITHUB-RELEASE"
        sha_doc = github_api_json(f"/repos/{owner}/{repo}/commits?per_page=1")
        commits = sha_doc.get("json") if isinstance(sha_doc.get("json"), list) else []
        if commits and isinstance(commits[0], dict):
            sha = commits[0].get("sha")
    else:
        last_release = "UNAVAILABLE"
    archived = bool(info.get("archived")) if info else None
    return {
        "owner": owner,
        "repo": repo,
        "archived": archived,
        "pushed_at": (info or {}).get("pushed_at"),
        "default_branch": (info or {}).get("default_branch"),
        "html_url": (info or {}).get("html_url"),
        "full_name": (info or {}).get("full_name"),
        "last_release_date": last_release or "UNAVAILABLE",
        "release_tag": release_tag,
        "commit_sha": sha,
        "api_repo_status": repo_doc.get("http_status"),
        "api_release_status": rel_doc.get("http_status"),
        "api_commits_status": sha_doc.get("http_status"),
        "snapshot_timestamp": repo_doc.get("snapshot_timestamp") or now_iso(),
        "rails": {
            "api_repo": repo_doc.get("url"),
            "api_release": rel_doc.get("url"),
            "api_commits": sha_doc.get("url"),
        },
    }
