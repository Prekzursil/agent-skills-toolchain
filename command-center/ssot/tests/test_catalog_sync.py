"""Tests for command-center/ssot/catalog_sync.py (fake feeds, no network).

Every network call goes through the module-level ``catalog_sync.fetch`` callable,
which these tests replace with recorded fixtures under ``fixtures/catalog/``. The
only sockets opened here are the loopback ``http.server`` used to exercise the
DEFAULT ``fetch`` implementation itself.
"""

from __future__ import annotations

import hashlib
import io
import json
import socket
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

SSOT = Path(__file__).resolve().parents[1]
if str(SSOT) not in sys.path:
    sys.path.insert(0, str(SSOT))

import catalog_sync as cs  # noqa: E402

FIXTURES = SSOT / "fixtures" / "catalog"
REPO = SSOT.parents[1]
NOW = "2026-09-02T03:30:00+00:00"

FIXTURE_BY_FEED = {
    "models-dev": "models-dev.json",
    "openrouter": "openrouter.json",
    "hf-router": "hf-router.json",
    "mcp-registry": "mcp-registry.json",
}


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _registry(*, loopback_enabled: bool = True) -> dict[str, Any]:
    """A minimal models.json: two hosted rows plus the three loopback rows."""

    def endpoint(base_url: str, enabled: bool = True) -> dict[str, Any]:
        return {"enabled": enabled, "baseUrl": base_url, "kind": "x"}

    return {
        "schemaVersion": 1,
        "endpoints": {
            "hf-router": endpoint("https://router.huggingface.co/v1"),
            "openrouter": endpoint("https://openrouter.ai/api/v1"),
            "cursor-auth2api": endpoint("http://127.0.0.1:8317/v1", loopback_enabled),
            "ollama": endpoint("http://localhost:11434/v1", loopback_enabled),
            "lmstudio": endpoint("http://[::1]:1234/v1", loopback_enabled),
            "llamacpp": endpoint("http://127.0.0.1:8080/v1", False),
        },
    }


class FakeFetch:
    """Recorded-fixture transport. ``responses`` maps url -> (status, headers, body)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.responses: dict[str, Any] = {}
        for feed in cs.FEEDS:
            self.serve_fixture(feed.url, FIXTURE_BY_FEED[feed.name])

    def serve_fixture(self, url: str, fixture: str, **headers: str) -> None:
        body = (FIXTURES / fixture).read_bytes()
        self.responses[url] = (200, headers, body)

    def serve(self, url: str, status: int, body: bytes = b"", **headers: str) -> None:
        self.responses[url] = (status, headers, body)

    def raise_for(self, url: str, exc: Exception) -> None:
        self.responses[url] = exc

    def __call__(
        self, url: str, headers: dict[str, str], timeout: float = 10.0
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append((url, dict(headers)))
        entry = self.responses.get(url)
        if entry is None:
            raise ConnectionRefusedError(f"no fixture for {url}")
        if isinstance(entry, Exception):
            raise entry
        return entry


@pytest.fixture()
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeFetch:
    transport = FakeFetch()
    monkeypatch.setattr(cs, "fetch", transport)
    return transport


@pytest.fixture()
def registry_path(tmp_path: Path) -> Path:
    path = tmp_path / "models.json"
    path.write_text(json.dumps(_registry()), encoding="utf-8")
    return path


def _run(root: Path, registry: Path, *extra: str) -> tuple[int, str]:
    buf = io.StringIO()
    argv = ["--root", str(root), "--registry", str(registry), *extra]
    with redirect_stdout(buf):
        rc = cs.main(argv)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# Normalisation / golden
# ---------------------------------------------------------------------------
def test_fake_feeds_produce_the_golden_index(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    for name in ("cursor-auth2api", "ollama", "lmstudio"):
        url = cs.loopback_url(_registry()["endpoints"][name]["baseUrl"])
        fake.serve_fixture(url, "loopback-models.json")
    root = tmp_path / "catalog"

    summary = cs.run(root, registry_path, now=NOW)

    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    expected = _load("expected-index.json")
    assert index["models"] == expected["models"]
    assert index["counts"] == expected["counts"]
    assert index["hosts"] == expected["hosts"]
    assert index["generated_at"] == NOW
    assert set(index["feeds"]) == set(FIXTURE_BY_FEED) | {
        "cursor-auth2api",
        "ollama",
        "lmstudio",
    }
    assert all(v["source_status"] == "ok" for v in index["feeds"].values())
    assert summary["counts"]["ok"] == 7
    # per-feed files carry the normalised shape
    feed_file = json.loads((root / "openrouter.json").read_text(encoding="utf-8"))
    assert set(feed_file) == {
        "feed",
        "url",
        "fetched_at",
        "source_status",
        "hosts",
        "models",
    }
    assert feed_file["fetched_at"] == NOW
    # the row schema is closed
    allowed = set(cs.MODEL_KEYS) | {"feed"}
    assert all(set(row) <= allowed for row in index["models"])
    # first-ever run: everything is new, nothing vanished
    diff = json.loads((root / "last-diff.json").read_text(encoding="utf-8"))
    assert len(diff["new_models"]) == len(index["models"])
    assert diff["vanished_models"] == []


def test_llamacpp_disabled_row_is_not_a_feed() -> None:
    feeds = cs.loopback_feeds(_registry())
    assert [f.name for f in feeds] == ["cursor-auth2api", "ollama", "lmstudio"]
    assert all(f.optional for f in feeds)
    assert feeds[2].url == "http://[::1]:1234/v1/models"


def test_hosted_rows_and_junk_rows_are_skipped_by_loopback_feeds() -> None:
    registry = {
        "endpoints": {
            "hosted": {"enabled": True, "baseUrl": "https://x.example/v1"},
            "junk": "not-a-dict",
            "nourl": {"enabled": True},
            "badhost": {"enabled": True, "baseUrl": "http://"},
        }
    }
    assert cs.loopback_feeds(registry) == []
    assert cs.loopback_feeds({}) == []


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://models.dev/api.json", True),
        ("http://127.0.0.1:8317/v1/models", True),
        ("http://localhost:11434/v1/models", True),
        ("http://[::1]:1234/v1/models", True),
        ("http://evil.example/v1/models", False),
        ("ftp://models.dev/api.json", False),
        ("http://", False),
        ("http://[::1", False),
    ],
)
def test_validate_url(url: str, ok: bool) -> None:
    if ok:
        cs.validate_url(url)
    else:
        with pytest.raises(cs.CatalogSyncError):
            cs.validate_url(url)


def test_host_of_tolerates_malformed_urls() -> None:
    assert cs.host_of("http://[::1") is None
    assert cs.host_of("http://[::1]:1234/v1") == "::1"
    assert not cs.is_loopback("http://[::1")


def test_atomic_write_cleans_up_its_temp_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(cs.os, "replace", boom)
    target = tmp_path / "out.json"
    with pytest.raises(OSError):
        cs.atomic_write_json(target, {"a": 1})
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_conditional_headers_only_forward_string_validators() -> None:
    assert cs._conditional_headers(None) == {}
    assert cs._conditional_headers({"etag": None, "last_modified": 3}) == {}
    assert cs._conditional_headers({"etag": '"e"'}) == {"If-None-Match": '"e"'}
    assert cs._conditional_headers({"last_modified": "Mon"}) == {
        "If-Modified-Since": "Mon"
    }


def _parsed(
    parser: cs.Parser, payload: Any
) -> tuple[list[dict[str, Any] | None], list[str]]:
    """Parser output pushed through ``normalise_row`` -- the shape that reaches disk."""
    rows, hosts = parser(payload)
    return [cs.normalise_row(row) for row in rows], hosts


def test_parsers_tolerate_missing_and_malformed_entries() -> None:
    models, hosts = _parsed(
        cs.parse_models_dev,
        {
            "p": {
                "api": "https://api.p.example/v1",
                "models": {"m": {"limit": {}, "cost": {}}, "junk": 3},
            },
            "q": "not-a-provider",
            "r": {"models": {}},
        },
    )
    assert models == [{"id": "m", "provider": "p", "supports_tools": False}]
    assert hosts == ["api.p.example"]

    models, hosts = _parsed(
        cs.parse_openrouter, {"data": [{"id": "a/b"}, 4, {"name": "x"}, {"id": "solo"}]}
    )
    assert models == [{"id": "a/b", "provider": "a"}, {"id": "solo"}]
    assert hosts == ["openrouter.ai"]
    assert _parsed(cs.parse_openrouter, {"data": "nope"}) == ([], ["openrouter.ai"])

    models, hosts = _parsed(
        cs.parse_hf_router,
        {"data": [{"id": "o/m", "providers": [{"provider": "x"}, "junk"]}, {"id": 5}]},
    )
    assert models == [{"id": "o/m", "provider": "x"}]
    assert hosts == ["router.huggingface.co"]
    assert _parsed(cs.parse_hf_router, {"data": [{"id": "solo"}]}) == (
        [{"id": "solo"}],
        ["router.huggingface.co"],
    )

    models, hosts = _parsed(
        cs.parse_mcp_registry,
        {"servers": [{"server": {"name": "n"}}, {"server": 1}, "junk", {}]},
    )
    assert models == [{"id": "n"}]
    assert hosts == ["registry.modelcontextprotocol.io"]

    models, hosts = _parsed(
        cs.parse_openai_models, {"data": [{"id": "x", "owned_by": "o"}, {}]}
    )
    assert models == [{"id": "x", "provider": "o"}]
    assert hosts == []


@pytest.mark.parametrize(
    "parser, payload",
    [
        (cs.parse_models_dev, []),
        (cs.parse_openrouter, [1, 2]),
        (cs.parse_hf_router, "x"),
        (cs.parse_mcp_registry, 7),
        (cs.parse_openai_models, None),
    ],
)
def test_parsers_reject_non_object_payloads(parser: cs.Parser, payload: Any) -> None:
    with pytest.raises(cs.CatalogSyncError):
        parser(payload)


def test_normalise_row_coerces_types_and_drops_unknown_keys() -> None:
    row = cs.normalise_row(
        {
            "id": "m",
            "context": "4096",
            "pricing": {"input": "0.5", "output": None, "junk": "x"},
            "status": " live ",
            "expiration_date": "2026-09-20T00:00:00Z",
            "supports_tools": 1,
            "version": 3,
            "unknown": True,
        }
    )
    assert row == {
        "id": "m",
        "context": 4096,
        "pricing": {"input": 0.5},
        "status": "live",
        "expiration_date": "2026-09-20",
        "supports_tools": True,
        "version": "3",
    }
    assert cs.normalise_row({"id": "m", "context": "lots", "pricing": "free"}) == {
        "id": "m"
    }
    assert cs.normalise_row({"id": ""}) is None
    assert cs.normalise_row("junk") is None


# ---------------------------------------------------------------------------
# Diff: the product
# ---------------------------------------------------------------------------
def _index(rows: list[dict[str, Any]], hosts: list[str]) -> dict[str, Any]:
    return {"models": rows, "hosts": hosts}


def test_diff_detects_every_event_kind() -> None:
    previous = _index(
        [
            {"feed": "openrouter", "id": "stays", "provider": "p"},
            {"feed": "openrouter", "id": "gone", "provider": "p"},
            {
                "feed": "mcp-registry",
                "id": "srv",
                "version": "1.0.0",
                "status": "active",
            },
            {"feed": "hf-router", "id": "m", "provider": "q", "status": "live"},
        ],
        ["openrouter.ai", "api-inference.huggingface.co"],
    )
    current = _index(
        [
            {"feed": "openrouter", "id": "stays", "provider": "p"},
            {
                "feed": "openrouter",
                "id": "fresh",
                "provider": "p",
                "expiration_date": "2026-09-20",
            },
            {
                "feed": "openrouter",
                "id": "far",
                "provider": "p",
                "expiration_date": "2027-01-01",
            },
            {
                "feed": "openrouter",
                "id": "bad",
                "provider": "p",
                "expiration_date": "soon",
            },
            {
                "feed": "mcp-registry",
                "id": "srv",
                "version": "1.1.0",
                "status": "deprecated",
            },
            {"feed": "hf-router", "id": "m", "provider": "q", "status": "error"},
        ],
        ["openrouter.ai"],
    )

    diff = cs.diff_index(previous, current, now=NOW)

    assert [r["id"] for r in diff["new_models"]] == ["bad", "far", "fresh"]
    assert [r["id"] for r in diff["vanished_models"]] == ["gone"]
    assert [r["id"] for r in diff["expired"]] == ["fresh"]
    assert [(r["id"], r["status"]) for r in diff["status_not_live"]] == [
        ("m", "error"),
        ("srv", "deprecated"),
    ]
    assert diff["version_moves"] == [
        {"feed": "mcp-registry", "id": "srv", "from": "1.0.0", "to": "1.1.0"}
    ]
    assert diff["decommissioned_hosts"] == ["api-inference.huggingface.co"]
    assert diff["generated_at"] == NOW
    assert diff["counts"] == {
        "new_models": 3,
        "vanished_models": 1,
        "expired": 1,
        "status_not_live": 2,
        "version_moves": 1,
        "decommissioned_hosts": 1,
    }


def test_diff_against_nothing_is_all_new() -> None:
    current = _index([{"feed": "f", "id": "a"}], ["h"])
    diff = cs.diff_index(None, current, now=NOW)
    assert [r["id"] for r in diff["new_models"]] == ["a"]
    assert diff["decommissioned_hosts"] == []
    assert cs.diff_index(None, {"models": []}, now=NOW)["counts"]["new_models"] == 0


def test_expiring_within_window_boundaries() -> None:
    assert cs.expiring_within({"expiration_date": "2026-10-02"}, NOW, days=30)
    assert not cs.expiring_within({"expiration_date": "2026-10-03"}, NOW, days=30)
    assert cs.expiring_within({"expiration_date": "2020-01-01"}, NOW, days=30)
    assert not cs.expiring_within({"id": "no-date"}, NOW, days=30)
    assert not cs.expiring_within({"expiration_date": "garbage"}, NOW, days=30)


def test_report_rendering_lists_each_kind_and_truncates() -> None:
    rows = [{"feed": "f", "id": f"m{i}", "provider": "p"} for i in range(12)]
    previous = _index([], ["api-inference.huggingface.co"])
    diff = cs.diff_index(previous, _index(rows, []), now=NOW)
    text = cs.render_report(
        diff, {"feeds": {"f": {"source_status": "ok", "count": 12}}}
    )
    assert "new_models: 12" in text
    assert "... 2 more" in text
    assert "vanished_models: 0" in text
    assert "f: ok (12 models)" in text
    assert "decommissioned_hosts: 1\n  - api-inference.huggingface.co" in text


# ---------------------------------------------------------------------------
# Cache, last-known-good, unreachable
# ---------------------------------------------------------------------------
def test_etag_roundtrip_304_leaves_file_byte_identical(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    url = cs.FEEDS[0].url
    fake.serve_fixture(url, "models-dev.json", ETag='"v1"', **{"Last-Modified": "Mon"})
    root = tmp_path / "catalog"

    cs.run(root, registry_path, feed_names=["models-dev"], now=NOW)
    first = (root / "models-dev.json").read_bytes()
    cache = json.loads((root / ".cache" / "models-dev.headers.json").read_text())
    assert cache == {"url": url, "etag": '"v1"', "last_modified": "Mon"}

    fake.serve(url, 304)
    summary = cs.run(
        root, registry_path, feed_names=["models-dev"], now="2026-09-03T03:30:00+00:00"
    )

    sent = fake.calls[-1][1]
    assert sent["If-None-Match"] == '"v1"'
    assert sent["If-Modified-Since"] == "Mon"
    assert (root / "models-dev.json").read_bytes() == first
    assert summary["feeds"]["models-dev"]["source_status"] == "unchanged"
    assert summary["counts"]["ok"] == 1
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert index["feeds"]["models-dev"]["source_status"] == "unchanged"
    assert index["counts"]["total"] == 4


def test_304_without_a_cached_body_is_stale(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    fake.serve(cs.FEEDS[0].url, 304)
    summary = cs.run(
        tmp_path / "catalog", registry_path, feed_names=["models-dev"], now=NOW
    )
    feed = summary["feeds"]["models-dev"]
    assert feed["source_status"] == "stale"
    assert "304" in feed["error"]
    assert feed["count"] == 0


@pytest.mark.parametrize(
    "failure",
    [
        ("status", 500),
        ("status", 429),
        ("body", b"{not json"),
        ("body", b"[1, 2, 3]"),
        ("exc", TimeoutError("timed out")),
        ("exc", OSError("connection reset")),
    ],
)
def test_last_known_good_survives_failures(
    fake: FakeFetch, tmp_path: Path, registry_path: Path, failure: tuple[str, Any]
) -> None:
    url = cs.FEEDS[1].url  # openrouter
    root = tmp_path / "catalog"
    cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    good = json.loads((root / "openrouter.json").read_text(encoding="utf-8"))

    kind, value = failure
    if kind == "status":
        fake.serve(url, value, b"upstream sad")
    elif kind == "body":
        fake.serve(url, 200, value)
    else:
        fake.raise_for(url, value)
    later = "2026-09-03T03:30:00+00:00"
    summary = cs.run(root, registry_path, feed_names=["openrouter"], now=later)

    stale = json.loads((root / "openrouter.json").read_text(encoding="utf-8"))
    assert stale["source_status"] == "stale"
    assert stale["models"] == good["models"]
    assert stale["hosts"] == good["hosts"]
    assert stale["fetched_at"] == NOW  # the last GOOD fetch, not this run
    assert stale["error"]
    assert "upstream sad" not in stale["error"]
    assert summary["counts"] == {
        "feeds": 1,
        "ok": 0,
        "stale": 1,
        "unreachable": 0,
        "new": 0,
        "vanished": 0,
    }


def test_failure_with_no_last_known_good_yields_an_empty_stale_feed(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    fake.serve(cs.FEEDS[2].url, 503)
    root = tmp_path / "catalog"
    summary = cs.run(root, registry_path, feed_names=["hf-router"], now=NOW)
    feed = json.loads((root / "hf-router.json").read_text(encoding="utf-8"))
    assert feed["source_status"] == "stale"
    assert feed["models"] == []
    assert feed["fetched_at"] is None
    assert summary["counts"]["stale"] == 1


def test_a_previous_stale_file_stays_last_known_good_without_recording_stale_as_good(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    url = cs.FEEDS[1].url
    root = tmp_path / "catalog"
    cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    fake.serve(url, 500)
    cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    fake.serve(url, 500)
    cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    stale = json.loads((root / "openrouter.json").read_text(encoding="utf-8"))
    assert stale["source_status"] == "stale"
    assert len(stale["models"]) == 4


def test_corrupt_last_known_good_is_treated_as_absent(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "catalog"
    root.mkdir()
    (root / "openrouter.json").write_text("{broken", encoding="utf-8")
    (root / ".cache").mkdir()
    (root / ".cache" / "openrouter.headers.json").write_text(
        "{broken", encoding="utf-8"
    )
    fake.serve(cs.FEEDS[1].url, 500)
    summary = cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    assert summary["feeds"]["openrouter"]["count"] == 0
    assert summary["feeds"]["openrouter"]["source_status"] == "stale"


def test_loopback_unreachable_is_recorded_not_failed(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "catalog"
    fake.serve_fixture("http://127.0.0.1:8317/v1/models", "loopback-models.json")
    fake.raise_for("http://localhost:11434/v1/models", ConnectionRefusedError())
    fake.serve("http://[::1]:1234/v1/models", 502)

    rc, out = _run(root, registry_path)

    assert rc == 0
    line = out.strip().splitlines()[-1]
    assert line == (
        "SUCCESS:catalog-sync feeds=7 ok=5 stale=0 unreachable=2 new=18 vanished=0"
    )
    ollama = json.loads((root / "ollama.json").read_text(encoding="utf-8"))
    assert ollama["source_status"] == "unreachable"
    assert ollama["models"] == []
    lms = json.loads((root / "lmstudio.json").read_text(encoding="utf-8"))
    assert lms["source_status"] == "unreachable"


def test_loopback_unreachable_keeps_its_last_known_good_models(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "catalog"
    url = "http://127.0.0.1:8317/v1/models"
    fake.serve_fixture(url, "loopback-models.json")
    cs.run(root, registry_path, feed_names=["cursor-auth2api"], now=NOW)
    fake.raise_for(url, ConnectionRefusedError())
    summary = cs.run(root, registry_path, feed_names=["cursor-auth2api"], now=NOW)
    feed = json.loads((root / "cursor-auth2api.json").read_text(encoding="utf-8"))
    assert feed["source_status"] == "unreachable"
    assert len(feed["models"]) == 3
    assert summary["counts"]["unreachable"] == 1
    assert summary["counts"]["vanished"] == 0


def test_unselected_feeds_keep_contributing_their_stored_file(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "catalog"
    cs.run(root, registry_path, feed_names=["openrouter"], now=NOW)
    later = "2026-09-03T03:30:00+00:00"
    summary = cs.run(root, registry_path, feed_names=["mcp-registry"], now=later)

    assert summary["counts"] == {
        "feeds": 1,
        "ok": 1,
        "stale": 0,
        "unreachable": 0,
        "new": 3,
        "vanished": 0,
    }
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    assert index["counts"]["by_feed"] == {"mcp-registry": 3, "openrouter": 4}
    assert index["feeds"]["openrouter"] == {
        "source_status": "ok",
        "fetched_at": NOW,
        "count": 4,
    }
    assert set(summary["feeds"]) == {"mcp-registry"}
    assert [c[0] for c in fake.calls[1:]] == [cs.FEEDS[3].url]


def test_stored_result_carries_a_previous_error_and_defaults(tmp_path: Path) -> None:
    feed = cs.FEEDS[1]
    root = tmp_path / "catalog"
    assert cs._stored_result(feed, root) is None
    root.mkdir()
    (root / f"{feed.name}.json").write_text(
        json.dumps({"models": [{"id": "m"}], "error": "http 500"}), encoding="utf-8"
    )
    stored = cs._stored_result(feed, root)
    assert stored is not None
    assert (stored.url, stored.status, stored.error) == (feed.url, "stale", "http 500")
    assert stored.hosts == [] and stored.fetched_at is None


def test_offline_never_touches_the_network(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "catalog"
    cs.run(root, registry_path, feed_names=["openrouter", "mcp-registry"], now=NOW)
    before = fake.calls[:]
    rc, out = _run(
        root, registry_path, "--offline", "--feeds", "openrouter,mcp-registry"
    )
    assert rc == 0
    assert fake.calls == before
    assert "stale=2" in out
    feed = json.loads((root / "openrouter.json").read_text(encoding="utf-8"))
    assert feed["source_status"] == "stale"
    assert feed["error"] == "offline"
    assert len(feed["models"]) == 4


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def test_cli_never_writes_the_two_registries(fake: FakeFetch, tmp_path: Path) -> None:
    agents = REPO / ".agents" / "agents.json"
    models = REPO / ".agents" / "models.json"
    before = (
        hashlib.sha256(agents.read_bytes()).hexdigest(),
        hashlib.sha256(models.read_bytes()).hexdigest(),
    )
    rc, out = _run(tmp_path / "catalog", models)
    after = (
        hashlib.sha256(agents.read_bytes()).hexdigest(),
        hashlib.sha256(models.read_bytes()).hexdigest(),
    )
    assert rc == 0
    assert before == after
    assert "SUCCESS:catalog-sync feeds=7" in out
    assert (
        "unreachable=3" in out
    )  # the real loopback rows have no fixture -> unreachable


def test_cli_json_output_is_machine_readable(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    rc, out = _run(
        tmp_path / "catalog", registry_path, "--json", "--feeds", "openrouter"
    )
    assert rc == 0
    lines = out.strip().splitlines()
    payload = json.loads("\n".join(lines[:-1]))
    assert payload["counts"]["feeds"] == 1
    assert payload["diff"]["counts"]["new_models"] == 4
    assert lines[-1].startswith("SUCCESS:catalog-sync ")


def test_cli_prints_the_diff_report_by_default(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    rc, out = _run(tmp_path / "catalog", registry_path, "--feeds", "openrouter")
    assert rc == 0
    assert "catalog-sync diff" in out
    assert "expired: 1" in out
    assert "example/legacy-chat-v1" in out


@pytest.mark.parametrize(
    "argv, needle",
    [
        (["--registry", "/nonexistent/models.json"], "registry"),
        (["--feeds", "nope"], "unknown feed"),
    ],
)
def test_cli_misuse_exits_2_with_a_failed_line(
    fake: FakeFetch, tmp_path: Path, registry_path: Path, argv: list[str], needle: str
) -> None:
    full = ["--root", str(tmp_path / "catalog")]
    if "--registry" not in argv:
        full += ["--registry", str(registry_path)]
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cs.main(full + argv)
    assert rc == 2
    line = buf.getvalue().strip().splitlines()[-1]
    assert line.startswith("FAILED:catalog-sync ")
    assert needle in line


@pytest.mark.parametrize("text", ["nope", "[1, 2]"])
def test_cli_rejects_a_registry_that_is_not_a_json_object(
    fake: FakeFetch, tmp_path: Path, text: str
) -> None:
    bad = tmp_path / "models.json"
    bad.write_text(text, encoding="utf-8")
    rc, out = _run(tmp_path / "catalog", bad)
    assert rc == 2
    assert "FAILED:catalog-sync" in out


def test_cli_reports_a_bug_as_failed_exit_2(
    tmp_path: Path, registry_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(cs, "run", broken)
    rc, out = _run(tmp_path / "catalog", registry_path)
    assert rc == 2
    assert out.strip() == "FAILED:catalog-sync RuntimeError: unexpected"


def test_cli_root_that_is_a_file_is_misuse(
    fake: FakeFetch, tmp_path: Path, registry_path: Path
) -> None:
    root = tmp_path / "file-not-dir"
    root.write_text("x", encoding="utf-8")
    rc, out = _run(root, registry_path, "--feeds", "openrouter")
    assert rc == 2
    assert "FAILED:catalog-sync" in out


def test_defaults_point_inside_the_repo() -> None:
    assert cs.DEFAULT_ROOT == REPO / "state" / "catalog"
    assert cs.DEFAULT_REGISTRY == REPO / ".agents" / "models.json"
    assert [f.name for f in cs.FEEDS] == list(FIXTURE_BY_FEED)


def test_feed_urls_are_the_documented_ones() -> None:
    urls = {f.name: f.url for f in cs.FEEDS}
    assert urls["models-dev"] == "https://models.dev/api.json"
    assert urls["openrouter"] == "https://openrouter.ai/api/v1/models"
    assert urls["hf-router"] == "https://router.huggingface.co/v1/models"
    assert urls["mcp-registry"] == (
        "https://registry.modelcontextprotocol.io/v0.1/servers?version=latest"
    )


def test_run_rejects_an_unsafe_feed_url(tmp_path: Path, registry_path: Path) -> None:
    bad = cs.Feed("bad", "http://evil.example/models", cs.parse_openai_models, True)
    with pytest.raises(cs.CatalogSyncError):
        cs.sync_feed(bad, tmp_path / "catalog", now=NOW)


def test_main_without_argv_uses_sys_argv(
    fake: FakeFetch,
    tmp_path: Path,
    registry_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "catalog_sync.py",
            "--root",
            str(tmp_path / "catalog"),
            "--registry",
            str(registry_path),
            "--feeds",
            "mcp-registry",
        ],
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cs.main()
    assert rc == 0
    assert "feeds=1" in buf.getvalue()


# ---------------------------------------------------------------------------
# The default transport (loopback http.server; the only sockets in this file)
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/ok":
            body = b'{"data": []}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("ETag", '"abc"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/cached":
            self.send_response(304)
            self.end_headers()
        else:
            body = b"nope"
            self.send_response(500)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


@pytest.fixture()
def local_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_default_fetch_returns_status_headers_body(local_server: str) -> None:
    status, headers, body = cs.fetch(f"{local_server}/ok", {}, timeout=5.0)
    assert status == 200
    assert headers["ETag"] == '"abc"'
    assert body == b'{"data": []}'

    status, headers, body = cs.fetch(
        f"{local_server}/cached", {"If-None-Match": '"abc"'}, timeout=5.0
    )
    assert status == 304
    assert body == b""

    status, _headers, body = cs.fetch(f"{local_server}/boom", {}, timeout=5.0)
    assert status == 500
    assert body == b"nope"


def test_default_fetch_raises_when_nothing_listens() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(OSError):
        cs.fetch(f"http://127.0.0.1:{port}/v1/models", {}, timeout=1.0)
