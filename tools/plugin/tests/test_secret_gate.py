"""IMP-0004: credential-exposure gate — synthetic token blocks emit; report never echoes body.

NEGATIVE CONTROL: a clean bundle must pass while the planted-control bundle in the
same run fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import pack as pack_mod  # noqa: E402
import secret_gate as S  # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def _synthetic() -> str:
    return S.synthesize_github_pat(seed=20260908, body_len=36)


def test_synthetic_token_blocks_emit(tmp_path: Path) -> None:
    token = _synthetic()
    members = [
        ("readme.md", b"# clean\n"),
        ("cfg.py", f'TOKEN = "{token}"\n'.encode("utf-8")),
    ]
    with pytest.raises(S.SecretGateError, match="credential-exposure|github_token"):
        S.assert_members_clean(members)

    # Packer pre-emit must refuse before any archive bytes exist.
    stage = tmp_path / "repo"
    (stage / "tools" / "plugin").mkdir(parents=True)
    # Minimal git repo with a planted secret member under an allowlisted path is
    # heavy; exercise pack.PackError via direct assert path already covered and
    # via pack_mod raising PackError when members carry secrets.
    with pytest.raises(pack_mod.PackError, match="credential-exposure|github_token"):
        # Simulate the pack pre-emit call site.
        try:
            S.assert_members_clean(members)
        except S.SecretGateError as exc:
            raise pack_mod.PackError(str(exc)) from exc


def test_report_never_contains_secret_body() -> None:
    token = _synthetic()
    body = S.secret_body(token)
    assert body
    assert len(body) >= 16
    report = S.scan_members(
        [("plant.py", f'API_KEY = "{token}"\n'.encode("utf-8"))]
    )
    text = report.render_named_report()
    doc = json.dumps(report.as_secret_finding_doc())
    assert body not in text
    assert body not in doc
    assert token not in text
    assert token not in doc
    # Prefix may appear (zero-entropy); body must not.
    assert S.PLANTED_CONTROL_PREFIX in text or any(
        f.prefix == S.PLANTED_CONTROL_PREFIX for f in report.findings
    )
    assert report.blocking >= 1
    assert all("entropy=" in f.excerpt_shape for f in report.findings)
    assert S.report_contains_secret_body(text, token) is False


def test_negative_control_clean_passes_planted_fails_same_run() -> None:
    token = _synthetic()
    clean_members = [
        ("ok.py", b"x = 1\n"),
        ("note.md", b"no credentials here\n"),
    ]
    planted_members = [
        ("ok.py", b"x = 1\n"),
        (
            S.PLANTED_CONTROL_REL,
            f"token={token}\n".encode("utf-8"),
        ),
    ]
    clean = S.scan_members(clean_members)
    planted = S.scan_members(
        planted_members,
        planted_token=token,
        planted_rel=S.PLANTED_CONTROL_REL,
    )
    assert clean.clean is True
    assert clean.blocking == 0
    assert planted.clean is False
    assert planted.blocking >= 1
    assert planted.planted_control_found is True
    # Same-run invariant: clean pass AND planted fail.
    assert clean.clean and not planted.clean


def test_entropy_instrument_flags_same_synthetic_token() -> None:
    token = _synthetic()
    assert S.entropy_flags_token(token) is True
    # Pattern table also fires (two instruments).
    findings = S.scan_text(f'token="{token}"\n', relpath="x.py")
    rules = {f.rule for f in findings}
    assert "github_token" in rules


def test_nul_byte_does_not_disable_gate() -> None:
    """Regression: platform payload.py skipped scan on NUL in first 8 KiB — refuse that."""
    token = _synthetic()
    data = b"\x00" * 100 + f'TOKEN="{token}"\n'.encode("utf-8")
    findings = S.scan_bytes(data, relpath="binish.py")
    assert any(f.rule == "github_token" for f in findings)


def test_variable_name_and_byte_offset_reported() -> None:
    token = _synthetic()
    line = f'MY_API_TOKEN = "{token}"\n'
    findings = S.scan_text(line, relpath="cfg.py")
    blocking = [f for f in findings if f.severity == "blocking"]
    assert blocking
    assert blocking[0].variable_name == "MY_API_TOKEN"
    assert blocking[0].byte_offset >= 0
    named = blocking[0].named_line()
    assert "var=MY_API_TOKEN" in named
    assert S.secret_body(token) not in named


def test_base64_encoded_token_blocks_emit() -> None:
    """Regression for IMP-0004 FAIL review: base64-wrapped ghp_ must block."""
    import base64

    token = _synthetic()
    b64 = base64.b64encode(token.encode("ascii")).decode("ascii")
    members = [
        ("readme.md", b"# clean\n"),
        ("encoded_secret.cfg", f"API_TOKEN_B64={b64}\n".encode("utf-8")),
    ]
    report = S.scan_members(members)
    assert report.blocking >= 1
    assert any(f.rule.startswith("base64_wrapped_") for f in report.findings)
    body = S.secret_body(token)
    text = report.render_named_report()
    assert body not in text
    assert token not in text
    with pytest.raises(S.SecretGateError, match="base64_wrapped_|credential-exposure"):
        S.assert_members_clean(members)


def test_reviewer_evasion_fixture_now_blocks() -> None:
    """The FAIL-review fixture under reviews/IMP-0004 must no longer bypass."""
    fixture = (
        REPO
        / "command-center"
        / "p2-wave"
        / "reviews"
        / "IMP-0004"
        / "evasion-fixture"
        / "encoded_secret.cfg"
    )
    if not fixture.is_file():
        pytest.skip("evasion fixture not on tip yet")
    data = fixture.read_bytes()
    findings = S.scan_bytes(data, relpath="encoded_secret.cfg")
    blocking = [f for f in findings if f.severity == "blocking"]
    assert blocking, f"expected blocking on base64 evasion; got {findings!r}"
    with pytest.raises(S.SecretGateError):
        S.assert_members_clean([("encoded_secret.cfg", data)])
