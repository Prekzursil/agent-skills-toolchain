"""Stale-ref gate: remote branches with no open PR and no archive/rescue tag on the tip.

Audit Phase 4b (docs/RUNBOOK-2026-09-24-settle-and-harden.md). A branch other than
main/master is STALE when its tip commit is older than --max-age-hours, no open PR from
this repo has it as head, and no archive/* or rescue/* tag (peeled) names its tip. The
fix is a PR or a tag, never silence: an --allowlist line (branch<TAB>YYYY-MM-DD) only
defers it through that date (UTC). Exits 0 clean, 1 stale (0 if --dry-run), 2 error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
ATTEMPTS = 5
MAX_WAIT = 900.0  # seconds; a longer rate-limit wait fails instead of outliving the job
TABLE_HEAD = "| branch | last commit (UTC) | age | ahead of main |\n|---|---|---|---|"
FIX_HINT = (
    "\nFix: open a PR from the branch, or tag its tip: `git tag archive/<yyyy-mm>/"
    "<branch> origin/<branch>`, then push the tag. The allowlist only defers."
)


class CheckError(RuntimeError):
    """No verdict is possible: exit 2, never a clean 0 or a misleading 1."""


def _backoff(err: urllib.error.HTTPError, attempt: int, why: str) -> float | None:
    """Seconds to wait before retrying, or None when the error is final."""
    hdrs, limited = err.headers, err.code in (403, 429)
    if limited and (hdrs.get("Retry-After") or "").isdigit():  # secondary limit
        return float(hdrs["Retry-After"])
    if limited and hdrs.get("X-RateLimit-Remaining") == "0":  # primary limit
        return max(float(hdrs.get("X-RateLimit-Reset") or 0) - time.time(), 0) + 1.0
    if err.code == 429 or (limited and "rate limit" in why.lower()):
        return 60.0  # GitHub's advice when no header says how long to wait
    return 2.0**attempt if err.code >= 500 else None  # bare 403: a permission error


def _message(err: urllib.error.HTTPError) -> str:
    try:  # GitHub explains most failures in a JSON "message"
        return str(json.loads(err.read()).get("message", ""))
    except Exception:
        return str(err.reason)


def _get(url: str, token: str | None) -> tuple[object, object]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "stale-refs"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(ATTEMPTS):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as resp:
                return json.loads(resp.read()), resp.headers
        except urllib.error.HTTPError as err:
            why = f"HTTP {err.code} {_message(err)}"
            wait = _backoff(err, attempt, why)
        except (urllib.error.URLError, TimeoutError) as err:
            wait, why = 2.0**attempt, str(err)
        if wait is None or wait > MAX_WAIT or attempt == ATTEMPTS - 1:
            raise CheckError(f"GET {url}: {why.strip()}")
        print(f"retrying in {wait:.0f}s ({why.strip()}): {url}", file=sys.stderr)
        time.sleep(wait)
    raise CheckError(f"GET {url}: retries exhausted")


def _paged(url: str, token: str | None) -> list[dict]:
    # Follows Link rel="next" but re-applies its query to OUR /repos/{owner}/{name} URL:
    # GitHub writes the link as /repositories/{id}/..., which egress proxies may refuse.
    base, items = url.split("?")[0], []
    while url:
        data, headers = _get(url, token)
        if not isinstance(data, list):
            raise CheckError(f"GET {url}: expected a JSON list")
        items.extend(data)
        nxt = NEXT_LINK.search(headers.get("Link") or "")
        url = f"{base}?{urlsplit(nxt.group(1)).query}" if nxt else ""
    return items


def load_allowlist(path: str | None) -> dict[str, date]:
    """branch -> last day it is skipped. A malformed line fails instead of excusing."""
    allow: dict[str, date] = {}
    lines = Path(path).read_text(encoding="utf-8").splitlines() if path else []
    for num, line in enumerate(lines, 1):
        if line.strip() and not line.lstrip().startswith("#"):
            name, _, rest = line.partition("\t")
            stamp = rest.split("\t")[0].strip()  # text after a 2nd tab is a note
            if not name.strip() or not DATE_RE.fullmatch(stamp):
                raise CheckError(f"{path}:{num}: want branch<TAB>YYYY-MM-DD: {line!r}")
            allow[name.strip()] = date.fromisoformat(stamp)
    return allow


def find_stale(api, repo, token, max_age_hours, allow, now):
    """(branch, tip commit time, expired allowlist date or None) rows, oldest first."""
    root = f"{api}/repos/{repo}"
    branches = _paged(f"{root}/branches?per_page=100", token)
    pulls = _paged(f"{root}/pulls?state=open&per_page=100", token)
    with_pr = {  # a same-named branch on a fork does not excuse ours
        pr["head"]["ref"]
        for pr in pulls
        if (pr["head"].get("repo") or {}).get("id") == pr["base"]["repo"]["id"]
    }
    tagged, annotated = set(), []
    for prefix in ("archive", "rescue"):  # no trailing slash: proxies refuse it
        for ref in _paged(f"{root}/git/matching-refs/tags/{prefix}", token):
            if ref["ref"].startswith(f"refs/tags/{prefix}/"):
                obj = ref["object"]
                (annotated.append if obj["type"] == "tag" else tagged.add)(obj["sha"])
    stale = []
    for branch in branches:
        name, tip = branch["name"], branch["commit"]["sha"]
        if name in ("main", "master") or name in with_pr or tip in tagged:
            continue
        if (until := allow.get(name)) and now.date() <= until:
            continue
        stamp = _get(f"{root}/git/commits/{tip}", token)[0]["committer"]["date"]
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        if now - when <= timedelta(hours=max_age_hours):
            continue
        while annotated:  # peel lazily: only once some branch is otherwise stale
            obj = {"type": "tag", "sha": annotated.pop()}
            while obj["type"] == "tag":  # an annotated tag may name another tag
                obj = _get(f"{root}/git/tags/{obj['sha']}", token)[0]["object"]
            tagged.add(obj["sha"])
        if tip not in tagged:
            stale.append((name, when, until))
    return sorted(stale, key=lambda row: (row[1], row[0])), len(branches)


def _code(name: str) -> str:  # a code span: a branch name cannot ping or break rows
    fence = "`` " if "`" in name else "`"
    return f"{fence}{name}{fence[::-1]}".replace("|", "\\|")


def render(repo, stale, checked, max_age_hours, now) -> str:
    out = [
        f"## Stale refs: {repo}\n",
        f"**{len(stale)}** of {checked} branches are stale: tip commit older than "
        f"{max_age_hours:g}h, no open PR from the branch, no `archive/` or `rescue/` "
        f"tag on the tip (main/master excluded; checked {now:%Y-%m-%d %H:%M} UTC).\n",
    ]
    if stale:
        out.append(TABLE_HEAD)
        for name, when, until in stale:
            age, note = now - when, f" (allowlist expired {until})" if until else ""
            out.append(
                f"| {_code(name)}{note} | {when:%Y-%m-%d %H:%M} | "
                f"{age.days}d {age.seconds // 3600}h | unknown |"
            )
        out.append(FIX_HINT)
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--token", help="GitHub token (default: $GITHUB_TOKEN)")
    parser.add_argument("--max-age-hours", type=float, default=48.0)
    parser.add_argument("--allowlist", help="file of branch<TAB>YYYY-MM-DD lines")
    parser.add_argument("--out", help="also write the markdown report to this file")
    parser.add_argument("--dry-run", action="store_true", help="report, but exit 0")
    args = parser.parse_args(argv)
    if not REPO_RE.fullmatch(args.repo):
        parser.error(f"--repo must be owner/name, got {args.repo!r}")
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("warning: no token; unauthenticated calls are capped", file=sys.stderr)
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    now = datetime.now(timezone.utc)
    try:
        allow = load_allowlist(args.allowlist)
        rows, total = find_stale(api, args.repo, token, args.max_age_hours, allow, now)
    except Exception as err:  # 1 means "stale found", so a crash must not exit 1
        print(f"error: {type(err).__name__}: {err}", file=sys.stderr)
        return 2
    report = render(args.repo, rows, total, args.max_age_hours, now)
    sys.stdout.write(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 1 if rows and not args.dry_run else 0


if __name__ == "__main__":
    sys.exit(main())
