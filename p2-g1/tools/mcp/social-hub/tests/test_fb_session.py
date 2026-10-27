#!/usr/bin/env python3
"""Tests for fb_session: whoami interpretation, redaction, paths, export/verify.

No live Facebook: the MCP round-trip and the Node exporter are both mocked. The
end-to-end auth chain against a real (expired) session is exercised separately.
"""

from __future__ import annotations

import fb_session as S


# ---- whoami interpretation (the security-sensitive core) ------------------ #
def test_interpret_whoami_authenticated():
    resp = {
        "result": {"content": [{"type": "text", "text": '{"uid": "123", "name": "X"}'}]}
    }
    v = S._interpret_whoami(resp)
    assert v["authenticated"] is True and v["name_present"] is True


def test_interpret_whoami_uid_zero_is_not_authed():
    resp = {
        "result": {"content": [{"type": "text", "text": '{"uid": "0", "name": ""}'}]}
    }
    v = S._interpret_whoami(resp)
    assert v["authenticated"] is False and v["name_present"] is False


def test_interpret_whoami_is_error():
    resp = {
        "result": {
            "isError": True,
            "content": [{"type": "text", "text": "AuthError: boom"}],
        }
    }
    v = S._interpret_whoami(resp)
    assert v["authenticated"] is False
    assert v["detail"] == "AuthError: boom"


def test_interpret_whoami_bad_json():
    resp = {"result": {"content": [{"type": "text", "text": "not json"}]}}
    v = S._interpret_whoami(resp)
    assert v["authenticated"] is False


def test_interpret_whoami_never_leaks_value():
    # A real uid/name must not appear in the verdict; only booleans + a class.
    resp = {
        "result": {
            "content": [{"type": "text", "text": '{"uid": "999", "name": "Secret"}'}]
        }
    }
    v = S._interpret_whoami(resp)
    assert "999" not in v["detail"] and "Secret" not in v["detail"]


def test_first_text_empty():
    assert S._first_text({}) == ""
    assert S._first_text({"content": [{"type": "image"}]}) == ""


def test_redact_first_line_only():
    assert S._redact("line one\nline two") == "line one"
    assert S._redact("") == ""
    assert len(S._redact("x" * 500)) == 200


# ---- default cookies path ------------------------------------------------- #
def test_default_cookies_path_env_override(monkeypatch):
    monkeypatch.setenv("FB_COOKIES_PATH", "/custom/cookies.json")
    assert S.default_cookies_path() == "/custom/cookies.json"


def test_default_cookies_path_falls_back_to_slot(monkeypatch):
    monkeypatch.delenv("FB_COOKIES_PATH", raising=False)
    path = S.default_cookies_path()
    assert path.endswith("cookies.json")


# ---- verify_whoami (mocked backend) --------------------------------------- #
def test_verify_whoami_missing_file(tmp_path):
    v = S.verify_whoami(str(tmp_path / "nope.json"))
    assert v["authenticated"] is False and "does not exist" in v["detail"]


def test_verify_whoami_calls_backend(monkeypatch, tmp_path):
    cookies = tmp_path / "cookies.json"
    cookies.write_text("[]", encoding="utf-8")
    captured = {}

    def fake_mcp(cmd, env):
        captured["cmd"] = cmd
        captured["path"] = env.get("FB_COOKIES_PATH")
        return {"authenticated": True, "name_present": True, "detail": "ok"}

    monkeypatch.setattr(S, "_mcp_whoami", fake_mcp)
    v = S.verify_whoami(str(cookies))
    assert v["authenticated"] is True
    assert captured["path"] == str(cookies)  # the written file is what gets verified


# ---- run_export (mocked node) --------------------------------------------- #
def _fake_completed(returncode, stdout, stderr=""):
    class R:
        pass

    r = R()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_run_export_success(monkeypatch):
    monkeypatch.setattr(
        S.subprocess,
        "run",
        lambda *a, **k: _fake_completed(
            0, "progress\nSUCCESS:fb-session 9 cookies -> x\n"
        ),
    )
    ok, marker = S.run_export("out.json")
    assert ok is True and marker.startswith("SUCCESS:fb-session")


def test_run_export_failure_marker(monkeypatch):
    monkeypatch.setattr(
        S.subprocess,
        "run",
        lambda *a, **k: _fake_completed(1, "FAILED:fb-session login not detected\n"),
    )
    ok, marker = S.run_export("out.json")
    assert ok is False and "login not detected" in marker


def test_run_export_node_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(S.subprocess, "run", boom)
    ok, marker = S.run_export("out.json")
    assert ok is False and "node not on PATH" in marker


def test_run_export_timeout(monkeypatch):
    def boom(*a, **k):
        raise S.subprocess.TimeoutExpired(cmd="node", timeout=1)

    monkeypatch.setattr(S.subprocess, "run", boom)
    ok, marker = S.run_export("out.json")
    assert ok is False and "timed out" in marker


def test_run_export_passes_profile_and_headless(monkeypatch):
    seen = {}

    def capture(argv, **k):
        seen["argv"] = argv
        return _fake_completed(0, "SUCCESS:fb-session 1 cookies -> x\n")

    monkeypatch.setattr(S.subprocess, "run", capture)
    S.run_export("out.json", profile="/p", headless=True)
    assert "--profile" in seen["argv"] and "--headless" in seen["argv"]


# ---- main() --------------------------------------------------------------- #
def test_main_verify_only_authenticated(monkeypatch, capsys):
    monkeypatch.setattr(
        S,
        "verify_whoami",
        lambda p: {"authenticated": True, "name_present": True, "detail": "ok"},
    )
    rc = S.main(["--verify-only", "--out", "x.json"])
    assert rc == 0 and "SUCCESS:fb-session authenticated" in capsys.readouterr().out


def test_main_verify_only_not_authed(monkeypatch, capsys):
    monkeypatch.setattr(
        S,
        "verify_whoami",
        lambda p: {"authenticated": False, "name_present": False, "detail": "expired"},
    )
    rc = S.main(["--verify-only", "--out", "x.json"])
    assert rc == 1 and "NOT authenticated" in capsys.readouterr().out


def test_main_export_then_verify(monkeypatch, capsys):
    monkeypatch.setattr(
        S, "run_export", lambda *a, **k: (True, "SUCCESS:fb-session 9 -> x")
    )
    monkeypatch.setattr(
        S,
        "verify_whoami",
        lambda p: {"authenticated": True, "name_present": True, "detail": "ok"},
    )
    rc = S.main(["--out", "x.json"])
    assert rc == 0


def test_main_export_fails_short_circuits(monkeypatch, capsys):
    monkeypatch.setattr(
        S, "run_export", lambda *a, **k: (False, "FAILED:fb-session nope")
    )
    called = {"verify": False}

    def should_not_run(p):
        called["verify"] = True
        return {}

    monkeypatch.setattr(S, "verify_whoami", should_not_run)
    rc = S.main(["--out", "x.json"])
    assert rc == 1 and called["verify"] is False
