"""Unit tests for the HackTricks API client. No network: the HTTP layer is mocked, so these
burn zero RAG quota. Covers cache-hit (0 second HTTP), usage-guard refusal, key redaction on a
401 error path (stdout+stderr), missing-key error, and deterministic cache keys.
"""
import io
import json
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import htk_query as h  # noqa: E402


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("HACKTRICKS_API_KEY", "htk_secret_TESTKEY_do_not_leak")
    monkeypatch.setenv("HACKTRICKS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("HACKTRICKS_USAGE_FLOOR", "2")
    yield


def test_missing_key(monkeypatch):
    monkeypatch.delenv("HACKTRICKS_API_KEY", raising=False)
    monkeypatch.setattr(h, "_key_from_user_env", lambda: None)  # simulate no persisted user var
    with pytest.raises(h.HtkError):
        h.usage()


def test_rag_cache_hit(monkeypatch):
    calls = {"GET": 0, "POST": 0}

    def fake(method, path, body=None):
        calls[method] += 1
        if path.endswith("/usage"):
            return {"used": 0, "limit": 50, "remaining": 50}
        return {"results": [{"content": "x", "score": 1.0, "filename": "f.md"}],
                "query": body["query"], "usage": {"used": 1, "limit": 50}}

    monkeypatch.setattr(h, "_http_json", fake)
    r1, cached1 = h.rag("aws iam privilege escalation")
    assert cached1 is False and calls["POST"] == 1
    r2, cached2 = h.rag("aws iam privilege escalation")
    assert cached2 is True and calls["POST"] == 1  # served from cache, no 2nd POST
    assert r1 == r2


def test_usage_guard_refuses(monkeypatch):
    calls = {"POST": 0}

    def fake(method, path, body=None):
        if path.endswith("/usage"):
            return {"used": 49, "limit": 50, "remaining": 1}
        calls["POST"] += 1
        return {}

    monkeypatch.setattr(h, "_http_json", fake)
    with pytest.raises(h.HtkError):
        h.rag("a brand new uncached query")
    assert calls["POST"] == 0  # never spent


def test_key_redacted_on_http_error(monkeypatch):
    key = os.environ["HACKTRICKS_API_KEY"]

    def boom(req, timeout=0):
        body = io.BytesIO(b'{"error":"invalid key ' + key.encode() + b'"}')
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, body)

    monkeypatch.setattr(h.urllib.request, "urlopen", boom)
    with pytest.raises(h.HtkError) as exc:
        h.usage()
    assert key not in str(exc.value)
    assert "401" in str(exc.value)


def test_cache_key_deterministic_and_order_independent():
    a = h._cache_path("/api/v1/rag", {"query": "q", "max_results": 3})
    b = h._cache_path("/api/v1/rag", {"max_results": 3, "query": "q"})
    c = h._cache_path("/api/v1/rag", {"query": "other", "max_results": 3})
    assert a == b
    assert a != c


def test_rag_rejects_empty():
    with pytest.raises(h.HtkError):
        h.rag("   ")
