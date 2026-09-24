"""Hermetic tests for ci/check_stale_refs.py (audit Phase 4b stale-ref gate).

A fake ``urlopen`` stands in for the GitHub REST API: every request is matched on its
path and query, an unexpected request fails the test, and nothing touches the network.
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check_stale_refs as csr  # noqa: E402

REPO = "octo/tool"
ROOT = f"/repos/{REPO}"
TOKEN = "t0ken"
NOW = datetime.now(timezone.utc)
FORK_ID, OUR_ID = 99, 1


def ago(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _headers(values: dict[str, str]) -> Message:
    msg = Message()
    for key, value in values.items():
        msg[key] = value
    return msg


class FakeResponse:
    def __init__(self, body: object, headers: dict[str, str]) -> None:
        self._raw, self.headers = json.dumps(body).encode(), _headers(headers)

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeGitHub:
    """Canned replies per path?query; a queued route serves its replies in order."""

    def __init__(self) -> None:
        self.routes: dict[str, list[tuple[int, object, dict[str, str]]]] = {}
        self.calls: list[str] = []

    def add(self, key: str, body: object, status: int = 200, **headers: str) -> None:
        clean = {k.replace("_", "-"): v for k, v in headers.items()}
        self.routes.setdefault(key, []).append((status, body, clean))

    def urlopen(self, request, timeout=None):
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        split = urlsplit(request.full_url)
        key = split.path + (f"?{split.query}" if split.query else "")
        self.calls.append(key)
        assert key in self.routes, f"unexpected GET {key}"
        queue = self.routes[key]
        status, body, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        if status >= 400:
            raw = io.BytesIO(json.dumps(body).encode())
            raise urllib.error.HTTPError(key, status, "err", _headers(headers), raw)
        return FakeResponse(body, headers)


def seed(gh, branches, pulls=(), archive=(), rescue=(), link=None) -> None:
    """``branches`` maps name -> (tip sha, committer date)."""
    listing = [{"name": n, "commit": {"sha": sha}} for n, (sha, _) in branches.items()]
    extra = {"Link": link} if link else {}
    gh.add(f"{ROOT}/branches?per_page=100", listing, **extra)
    for sha, when in branches.values():
        gh.add(f"{ROOT}/git/commits/{sha}", {"sha": sha, "committer": {"date": when}})
    gh.add(f"{ROOT}/pulls?state=open&per_page=100", list(pulls))
    gh.add(f"{ROOT}/git/matching-refs/tags/archive", list(archive))
    gh.add(f"{ROOT}/git/matching-refs/tags/rescue", list(rescue))


def pull(ref: str, head_repo_id: int = OUR_ID) -> dict:
    return {
        "head": {"ref": ref, "repo": {"id": head_repo_id}},
        "base": {"repo": {"id": OUR_ID}},
    }


def tag(name: str, sha: str, kind: str = "commit") -> dict:
    return {"ref": f"refs/tags/{name}", "object": {"type": kind, "sha": sha}}


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(csr.urllib.request, "urlopen", fake.urlopen)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    return fake


def run(capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str]:
    code = csr.main(["--repo", REPO, "--token", TOKEN, *extra])
    return code, capsys.readouterr().out


def test_fresh_branch_is_ignored(gh: FakeGitHub, capsys) -> None:
    seed(gh, {"main": ("m1", ago(900)), "feat/fresh": ("f1", ago(2))})
    code, out = run(capsys)
    assert code == 0
    assert "**0** of 2 branches are stale" in out and "feat/fresh" not in out
    assert f"{ROOT}/git/commits/m1" not in gh.calls, "main must never be judged"


def test_stale_branch_with_open_pr_is_ignored(gh: FakeGitHub, capsys) -> None:
    seed(gh, {"feat/pr": ("p1", ago(240))}, pulls=[pull("feat/pr")])
    code, out = run(capsys)
    assert code == 0 and "feat/pr" not in out


def test_stale_branch_with_rescue_tag_is_ignored(gh: FakeGitHub, capsys) -> None:
    seed(gh, {"wip/x": ("r1", ago(240))}, rescue=[tag("rescue/2026-09/wip-x", "r1")])
    code, out = run(capsys)
    assert code == 0 and "wip/x" not in out


def test_stale_branch_with_no_pr_or_tag_is_reported(gh, capsys, tmp_path) -> None:
    seed(
        gh,
        {"main": ("m1", ago(900)), "wip/orphan": ("o1", ago(240))},
        pulls=[pull("wip/orphan", head_repo_id=FORK_ID)],  # same name, from a fork
        archive=[tag("archive/2026-09/other", "zz"), tag("archived-x", "o1")],
    )
    report = tmp_path / "stale-refs.md"
    code, out = run(capsys, "--out", str(report))
    assert code == 1
    assert "**1** of 2 branches are stale" in out
    assert "| `wip/orphan` | " in out and " | 10d 0h | unknown |" in out
    assert report.read_text(encoding="utf-8") == out


def test_expired_allowlist_line_is_reported(gh, capsys, tmp_path) -> None:
    lapsed, deferred = NOW.date() - timedelta(days=30), NOW.date() + timedelta(days=30)
    allow = tmp_path / "allow.txt"
    allow.write_text(
        f"# header\n\nwip/lapsed\t{lapsed}\nwip/deferred\t{deferred}\tdecision-file\n",
        encoding="utf-8",
    )
    seed(gh, {"wip/lapsed": ("l1", ago(240)), "wip/deferred": ("d1", ago(240))})
    code, out = run(capsys, "--allowlist", str(allow))
    assert code == 1
    assert f"| `wip/lapsed` (allowlist expired {lapsed}) |" in out
    assert "wip/deferred" not in out


def test_annotated_archive_tag_is_peeled_to_the_tip(gh: FakeGitHub, capsys) -> None:
    seed(gh, {"old/lane": ("c1", ago(240))}, archive=[tag("archive/x", "t1", "tag")])
    gh.add(f"{ROOT}/git/tags/t1", {"object": {"type": "tag", "sha": "t2"}})
    gh.add(f"{ROOT}/git/tags/t2", {"object": {"type": "commit", "sha": "c1"}})
    code, out = run(capsys)
    assert code == 0 and "old/lane" not in out


def test_pagination_is_followed_and_rate_limit_waited_out(gh, capsys, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(csr.time, "sleep", sleeps.append)
    # GitHub writes the next link as /repositories/{id}/...; only /repos/ is served here.
    nxt = '<https://api.github.com/repositories/7/branches?per_page=100&page=2>; rel="next"'
    seed(gh, {"a/fresh": ("a1", ago(1))}, link=nxt)
    page2, reset = f"{ROOT}/branches?per_page=100&page=2", str(int(time.time()) + 5)
    limit = {"X_RateLimit_Remaining": "0", "X_RateLimit_Reset": reset}
    gh.add(page2, {"message": "API rate limit exceeded"}, status=403, **limit)
    gh.add(page2, [{"name": "b/stale", "commit": {"sha": "b1"}}])
    gh.add(f"{ROOT}/git/commits/b1", {"committer": {"date": ago(240)}})
    code, out = run(capsys)
    assert code == 1 and "| `b/stale` |" in out and "a/fresh" not in out
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 7
    assert "**1** of 2 branches" in out


def test_dry_run_never_fails_but_a_blind_check_does(gh, capsys, tmp_path) -> None:
    seed(gh, {"wip/orphan": ("o1", ago(240))})
    code, out = run(capsys, "--dry-run")
    assert code == 0 and "| `wip/orphan` |" in out
    bad = tmp_path / "allow.txt"
    bad.write_text("wip/orphan 2026-01-01\n", encoding="utf-8")  # space, not a tab
    assert csr.main(["--repo", REPO, "--token", TOKEN, "--allowlist", str(bad)]) == 2
    assert "want branch<TAB>YYYY-MM-DD" in capsys.readouterr().err
    gh.routes[f"{ROOT}/branches?per_page=100"] = [(404, {"message": "Not Found"}, {})]
    assert csr.main(["--repo", REPO, "--token", TOKEN, "--dry-run"]) == 2
    assert "HTTP 404 Not Found" in capsys.readouterr().err
