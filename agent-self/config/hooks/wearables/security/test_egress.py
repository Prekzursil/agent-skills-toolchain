"""Tests for the fail-CLOSED egress guard (WU-0c).

NON-SYMMETRIC fixtures: the derived branch carries BOTH a DENY (no downgrade)
and an ALLOW (explicit downgrade) assertion so an inverted gate cannot pass.
"""

from wearables.security.egress import (
    EgressDecision,
    EgressRequest,
    egress_guard,
    scrub_secrets,
)

THIRD_PARTY = "gemini-2.5-flash"
THIRD_PARTY_ENDPOINT = "https://generativelanguage.googleapis.com/v1/models"
LOCAL_MODEL = "qwen2.5-3b"
LOCAL_ENDPOINT = "http://localhost:11434/v1"


def _req(**overrides):
    base = dict(
        model=THIRD_PARTY,
        endpoint=THIRD_PARTY_ENDPOINT,
        source_class="public_db",
        payload={"text": "baclofen Ki at GABA-B"},
        base_url=THIRD_PARTY_ENDPOINT,
        allow_derived_egress=False,
    )
    base.update(overrides)
    return EgressRequest(**base)


# --- allowlist / default-deny ---------------------------------------------


def test_public_db_to_third_party_is_allowed():
    decision = egress_guard(_req())
    assert isinstance(decision, EgressDecision)
    assert decision.allowed is True


def test_unknown_model_endpoint_pair_denied_by_default():
    decision = egress_guard(
        _req(model="unknown-model", endpoint="https://evil.example/x")
    )
    assert decision.allowed is False
    assert "allowlist" in decision.reason.lower()


# --- source_class gate -----------------------------------------------------


def test_unpublished_to_third_party_denied():
    decision = egress_guard(_req(source_class="unpublished"))
    assert decision.allowed is False
    assert "unpublished" in decision.reason.lower()


def test_derived_to_third_party_without_downgrade_denied():
    decision = egress_guard(_req(source_class="derived", allow_derived_egress=False))
    assert decision.allowed is False
    assert "derived" in decision.reason.lower()


def test_derived_to_third_party_with_downgrade_allowed():
    decision = egress_guard(_req(source_class="derived", allow_derived_egress=True))
    assert decision.allowed is True


def test_unpublished_with_downgrade_still_denied():
    # downgrade flag must NOT rescue unpublished
    decision = egress_guard(_req(source_class="unpublished", allow_derived_egress=True))
    assert decision.allowed is False


def test_unknown_source_class_denied():
    decision = egress_guard(_req(source_class="leaked"))
    assert decision.allowed is False


# --- local-LLM tier (loopback) ---------------------------------------------


def test_unpublished_to_loopback_local_allowed():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint=LOCAL_ENDPOINT,
            base_url=LOCAL_ENDPOINT,
            source_class="unpublished",
        )
    )
    assert decision.allowed is True


def test_loopback_127_allowed():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="http://127.0.0.1:11434/v1",
            base_url="http://127.0.0.1:11434/v1",
            source_class="unpublished",
        )
    )
    assert decision.allowed is True


def test_loopback_ipv6_allowed():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="http://[::1]:11434/v1",
            base_url="http://[::1]:11434/v1",
            source_class="unpublished",
        )
    )
    assert decision.allowed is True


def test_local_model_with_non_loopback_base_url_denied():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="http://169.254.169.254/latest/meta-data",
            base_url="http://169.254.169.254/latest/meta-data",
            source_class="unpublished",
        )
    )
    assert decision.allowed is False
    assert "loopback" in decision.reason.lower()


def test_local_model_public_host_base_url_denied():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="http://evil.example:11434/v1",
            base_url="http://evil.example:11434/v1",
            source_class="unpublished",
        )
    )
    assert decision.allowed is False


def test_local_model_empty_host_base_url_denied():
    # valid scheme but no host (e.g. "http:///v1") -> not loopback -> DENY
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="http:///v1",
            base_url="http:///v1",
            source_class="unpublished",
        )
    )
    assert decision.allowed is False
    assert "loopback" in decision.reason.lower()


def test_local_model_bad_scheme_base_url_denied():
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint="ftp://localhost:11434/v1",
            base_url="ftp://localhost:11434/v1",
            source_class="unpublished",
        )
    )
    assert decision.allowed is False


# --- secret scrub ----------------------------------------------------------


def test_secret_scrub_removes_google_key():
    out = scrub_secrets("call with GOOGLE_API_KEY=AIzaSyA-secret-value-123 here")
    assert "AIzaSyA-secret-value-123" not in out
    assert "[REDACTED]" in out


def test_secret_scrub_removes_hf_token():
    raw = "HF_TOKEN=hf_abcdefABCDEF0123456789 trailing"  # gitleaks:allow
    out = scrub_secrets(raw)
    assert "hf_abcdefABCDEF0123456789" not in out


def test_secret_scrub_removes_standalone_hf_token():
    # Regression (WU-0c): a bare hf_ token NOT preceded by HF_TOKEN= must be
    # scrubbed by whole-match replacement, not re-emitted via a capture group.
    out = scrub_secrets("leaked token hf_LEAKEDTOKEN1234567 in the body")
    assert "hf_LEAKEDTOKEN1234567" not in out
    assert "[REDACTED]" in out
    # belt-and-suspenders: assert-not-present in the scrubbed bytes
    assert b"hf_LEAKEDTOKEN1234567" not in out.encode("utf-8")


def test_secret_scrub_removes_authorization_bearer():
    out = scrub_secrets("Authorization: Bearer sk-verysecrettoken99")
    assert "sk-verysecrettoken99" not in out


def test_secret_scrub_removes_generic_key_param():
    out = scrub_secrets("https://api/x?key=topsecretvalue123&q=1")
    assert "topsecretvalue123" not in out


def test_secret_scrub_handles_non_string():
    assert scrub_secrets(12345) == "12345"


def test_egress_decision_payload_is_scrubbed_and_secret_absent():
    payload_text = "GOOGLE_API_KEY=AIzaSyVERYSECRET999 in body"  # gitleaks:allow
    decision = egress_guard(_req(payload={"text": payload_text}))
    assert decision.allowed is True
    blob = decision.scrubbed_payload
    assert "AIzaSyVERYSECRET999" not in blob
    # belt-and-suspenders: assert-not-present in the bytes
    assert b"AIzaSyVERYSECRET999" not in blob.encode("utf-8")


# --- fail-closed -----------------------------------------------------------


def test_malformed_request_denied_fail_closed():
    decision = egress_guard("not-an-egress-request")  # type: ignore[arg-type]
    assert decision.allowed is False
    assert (
        "fail-closed" in decision.reason.lower()
        or "malformed" in decision.reason.lower()
    )


def test_none_request_denied_fail_closed():
    decision = egress_guard(None)  # type: ignore[arg-type]
    assert decision.allowed is False


def test_internal_exception_denied_fail_closed(monkeypatch):
    # force an exception inside the guard's classification to prove fail-closed
    import wearables.security.egress as egress_mod

    def boom(*_a, **_k):
        raise RuntimeError("classifier exploded")

    monkeypatch.setattr(egress_mod, "_is_loopback", boom)
    decision = egress_guard(
        _req(
            model=LOCAL_MODEL,
            endpoint=LOCAL_ENDPOINT,
            base_url=LOCAL_ENDPOINT,
            source_class="unpublished",
        )
    )
    assert decision.allowed is False
    assert "fail-closed" in decision.reason.lower()
