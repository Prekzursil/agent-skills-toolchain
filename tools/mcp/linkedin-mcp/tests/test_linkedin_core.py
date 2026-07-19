#!/usr/bin/env python3
"""Unit tests for linkedin_core -- no token, no network (injected fake requester).

The single ``request_json`` seam is replaced by ``FakeRequester`` so every code
path (success, 401, 403-gated, network error, validation) is exercised offline.
"""

from __future__ import annotations

import linkedin_core as core
import pytest

TOKEN_ENV = {
    "LINKEDIN_ACCESS_TOKEN": "tok",
    "LINKEDIN_CLIENT_ID": "cid",
    "LINKEDIN_CLIENT_SECRET": "sec",
    "LINKEDIN_REDIRECT_URI": "https://example.com/cb",
}


class FakeRequester:
    """Records calls and returns queued ``(status, body, headers)`` triples."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers=None, body=None, timeout=core.TIMEOUT):
        self.calls.append(
            {"method": method, "url": url, "headers": headers or {}, "body": body}
        )
        if self._responses:
            return self._responses.pop(0)
        return 200, {}, {}


def _userinfo_ok():
    return 200, {"sub": "ABC123", "name": "Jane Dev"}, {}


def _created(urn="urn:li:ugcPost:999"):
    return 201, {}, {"X-RestLi-Id": urn}


# --- credentials ------------------------------------------------------------- #
def test_access_token_missing_raises_actionable():
    with pytest.raises(core.LinkedInError) as exc:
        core.access_token({})
    assert "LINKEDIN_ACCESS_TOKEN" in str(exc.value)
    assert "SETUP.md" in str(exc.value)


def test_access_token_present():
    assert core.access_token({"LINKEDIN_ACCESS_TOKEN": " tok "}) == "tok"


def test_client_id_and_secret_missing():
    with pytest.raises(core.LinkedInError):
        core.client_id({})
    with pytest.raises(core.LinkedInError):
        core.client_secret({})


def test_credential_presence_reports_booleans_only():
    present = core.credential_presence({"LINKEDIN_ACCESS_TOKEN": "x"})
    assert present["LINKEDIN_ACCESS_TOKEN"] is True
    assert present["LINKEDIN_CLIENT_ID"] is False
    # values never leak -- only booleans
    assert all(isinstance(v, bool) for v in present.values())


# --- validation helpers ------------------------------------------------------ #
@pytest.mark.parametrize("bad", ["", "   ", None, 123])
def test_text_rejects_empty_and_nonstring(bad):
    with pytest.raises(core.LinkedInError):
        core._text(bad, "text", 100)


def test_text_rejects_nul_and_overlong():
    with pytest.raises(core.LinkedInError):
        core._text("a\x00b", "text", 100)
    with pytest.raises(core.LinkedInError):
        core._text("x" * 101, "text", 100)


def test_visibility_validation():
    assert core._visibility("PUBLIC") == "PUBLIC"
    assert core._visibility("CONNECTIONS") == "CONNECTIONS"
    with pytest.raises(core.LinkedInError):
        core._visibility("PRIVATE")


@pytest.mark.parametrize("bad", ["", "ftp://x", "not-a-url", 5])
def test_https_url_rejects_bad(bad):
    with pytest.raises(core.LinkedInError):
        core._https_url(bad, "url")


def test_urn_validation_and_type_constraint():
    assert core._urn("urn:li:person:X", "author", ("person",)) == "urn:li:person:X"
    with pytest.raises(core.LinkedInError):
        core._urn("not-a-urn", "author")
    with pytest.raises(core.LinkedInError):
        core._urn("urn:li:x", "author")  # too few parts
    with pytest.raises(core.LinkedInError):
        core._urn("urn:li:organization:5", "author", ("person",))  # wrong type


def test_person_urn_and_encode():
    assert core.person_urn("ABC") == "urn:li:person:ABC"
    with pytest.raises(core.LinkedInError):
        core.person_urn("")
    assert core.encode_urn("urn:li:ugcPost:1") == "urn%3Ali%3AugcPost%3A1"


# --- request_json seam ------------------------------------------------------- #
def test_request_json_network_error_returns_zero(monkeypatch):
    def boom(*a, **k):
        raise OSError("no net")

    monkeypatch.setattr(core.urllib.request, "urlopen", boom)
    status, body, headers = core.request_json("GET", "https://x")
    assert status == 0
    assert "failed" in body["error"]


def test_request_json_decodes_json_and_headers(monkeypatch):
    class Resp:
        status = 200
        headers = {"X-RestLi-Id": "urn:li:ugcPost:7"}

        def read(self):
            return b'{"hello": "world"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(core.urllib.request, "urlopen", lambda *a, **k: Resp())
    status, body, headers = core.request_json("GET", "https://x")
    assert status == 200
    assert body == {"hello": "world"}
    assert headers["X-RestLi-Id"] == "urn:li:ugcPost:7"


def test_request_json_http_error(monkeypatch):
    import io

    def raise_http(*a, **k):
        raise core.urllib.error.HTTPError(
            "https://x", 403, "Forbidden", {}, io.BytesIO(b'{"message":"no"}')
        )

    monkeypatch.setattr(core.urllib.request, "urlopen", raise_http)
    status, body, _ = core.request_json("GET", "https://x")
    assert status == 403
    assert body["message"] == "no"


def test_decode_empty_and_nonjson():
    assert core._decode(b"") == {}
    assert core._decode(b"plain text") == "plain text"


# --- whoami ------------------------------------------------------------------ #
def test_whoami_success():
    fake = FakeRequester(_userinfo_ok())
    out = core.whoami(TOKEN_ENV, fake)
    assert out["ok"] is True
    assert out["person_urn"] == "urn:li:person:ABC123"
    assert out["name"] == "Jane Dev"
    assert fake.calls[0]["url"] == core.USERINFO_URL
    assert fake.calls[0]["headers"]["X-Restli-Protocol-Version"] == "2.0.0"


def test_whoami_401_is_structured_not_raised():
    fake = FakeRequester((401, {"message": "Empty oauth2_access_token"}, {}))
    out = core.whoami(TOKEN_ENV, fake)
    assert out["ok"] is False
    assert out["status"] == 401
    assert "60 days" in out["hint"]


def test_whoami_missing_token_raises():
    with pytest.raises(core.LinkedInError):
        core.whoami({}, FakeRequester())


# --- post_text --------------------------------------------------------------- #
def test_post_text_resolves_author_and_posts():
    fake = FakeRequester(_userinfo_ok(), _created("urn:li:ugcPost:555"))
    out = core.post_text("Hello!", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["post_urn"] == "urn:li:ugcPost:555"
    assert out["url"].endswith("urn:li:ugcPost:555/")
    # 2 calls: userinfo then ugcPosts
    assert fake.calls[1]["url"] == core.UGC_POSTS_URL
    body = fake.calls[1]["body"]
    assert body["author"] == "urn:li:person:ABC123"
    assert body["lifecycleState"] == "PUBLISHED"
    sc = body["specificContent"]["com.linkedin.ugc.ShareContent"]
    assert sc["shareCommentary"]["text"] == "Hello!"
    assert sc["shareMediaCategory"] == "NONE"


def test_post_text_with_explicit_author_skips_userinfo():
    fake = FakeRequester(_created())
    out = core.post_text(
        "Hi", author="urn:li:person:ZZZ", environ=TOKEN_ENV, requester=fake
    )
    assert out["ok"] is True
    assert len(fake.calls) == 1  # no userinfo lookup
    assert fake.calls[0]["body"]["author"] == "urn:li:person:ZZZ"


def test_post_text_author_validation_raises():
    with pytest.raises(core.LinkedInError):
        core.post_text(
            "Hi",
            author="urn:li:organization:5",
            environ=TOKEN_ENV,
            requester=FakeRequester(),
        )


def test_post_text_propagates_userinfo_failure():
    fake = FakeRequester((401, {"message": "bad"}, {}))
    out = core.post_text("Hi", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
    assert out["status"] == 401
    assert len(fake.calls) == 1  # never reached ugcPosts


def test_post_text_non201_is_failure():
    fake = FakeRequester(_userinfo_ok(), (422, {"message": "bad content"}, {}))
    out = core.post_text("Hi", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
    assert out["status"] == 422


def test_post_text_bad_visibility():
    with pytest.raises(core.LinkedInError):
        core.post_text(
            "Hi", visibility="SECRET", environ=TOKEN_ENV, requester=FakeRequester()
        )


# --- post_article ------------------------------------------------------------ #
def test_post_article_builds_article_media():
    fake = FakeRequester(_userinfo_ok(), _created())
    out = core.post_article(
        "read this",
        "https://blog.example.com/x",
        title="Title",
        description="Desc",
        environ=TOKEN_ENV,
        requester=fake,
    )
    assert out["ok"] is True
    sc = fake.calls[1]["body"]["specificContent"]["com.linkedin.ugc.ShareContent"]
    assert sc["shareMediaCategory"] == "ARTICLE"
    assert sc["media"][0]["originalUrl"] == "https://blog.example.com/x"
    assert sc["media"][0]["title"]["text"] == "Title"
    assert sc["media"][0]["description"]["text"] == "Desc"


def test_post_article_rejects_bad_url():
    with pytest.raises(core.LinkedInError):
        core.post_article(
            "x", "not-a-url", environ=TOKEN_ENV, requester=FakeRequester()
        )


# --- post_image -------------------------------------------------------------- #
def _register_ok(url="https://up.example/put", asset="urn:li:digitalmediaAsset:AA"):
    return (
        200,
        {
            "value": {
                "uploadMechanism": {
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {
                        "uploadUrl": url
                    }
                },
                "asset": asset,
            }
        },
        {},
    )


def test_post_image_full_flow():
    fake = FakeRequester(
        _userinfo_ok(),  # author
        _register_ok(),  # registerUpload
        (201, {}, {}),  # binary PUT
        _created("urn:li:ugcPost:IMG"),  # ugcPost
    )
    out = core.post_image(
        "with pic",
        "ignored.png",
        environ=TOKEN_ENV,
        requester=fake,
        opener=lambda p: b"\x89PNG\r\n",
    )
    assert out["ok"] is True
    assert out["post_urn"] == "urn:li:ugcPost:IMG"
    assert out["asset"] == "urn:li:digitalmediaAsset:AA"
    # 4 calls in order
    assert fake.calls[1]["url"] == core.REGISTER_UPLOAD_URL
    assert fake.calls[2]["url"] == "https://up.example/put"
    assert fake.calls[2]["body"] == b"\x89PNG\r\n"
    sc = fake.calls[3]["body"]["specificContent"]["com.linkedin.ugc.ShareContent"]
    assert sc["shareMediaCategory"] == "IMAGE"
    assert sc["media"][0]["media"] == "urn:li:digitalmediaAsset:AA"


def test_post_image_retries_put_as_post_on_405():
    fake = FakeRequester(
        _userinfo_ok(),
        _register_ok(),
        (405, {"message": "method"}, {}),  # PUT rejected
        (201, {}, {}),  # POST retry ok
        _created(),
    )
    out = core.post_image(
        "pic", "x.png", environ=TOKEN_ENV, requester=fake, opener=lambda p: b"data"
    )
    assert out["ok"] is True
    assert fake.calls[2]["method"] == "PUT"
    assert fake.calls[3]["method"] == "POST"


def test_post_image_upload_failure_surfaces():
    fake = FakeRequester(
        _userinfo_ok(),
        _register_ok(),
        (500, {"message": "boom"}, {}),
        (500, {"message": "boom"}, {}),
    )
    out = core.post_image(
        "pic", "x.png", environ=TOKEN_ENV, requester=fake, opener=lambda p: b"d"
    )
    assert out["ok"] is False
    assert out["status"] == 500


def test_post_image_register_failure_surfaces():
    fake = FakeRequester(_userinfo_ok(), (403, {"message": "no"}, {}))
    out = core.post_image(
        "pic", "x.png", environ=TOKEN_ENV, requester=fake, opener=lambda p: b"d"
    )
    assert out["ok"] is False
    assert out["status"] == 403


def test_post_image_empty_file_raises():
    with pytest.raises(core.LinkedInError):
        core.post_image(
            "pic",
            "x.png",
            environ=TOKEN_ENV,
            requester=FakeRequester(),
            opener=lambda p: b"",
        )


def test_post_image_unreadable_file_raises():
    def boom(_):
        raise OSError("nope")

    with pytest.raises(core.LinkedInError):
        core.post_image(
            "pic", "x.png", environ=TOKEN_ENV, requester=FakeRequester(), opener=boom
        )


def test_register_upload_missing_fields():
    fake = FakeRequester((200, {"value": {}}, {}))
    slot, failure = core.register_upload(
        "urn:li:person:X", environ=TOKEN_ENV, requester=fake
    )
    assert slot == {}
    assert failure["ok"] is False


def test_read_binary_reads_file(tmp_path):
    p = tmp_path / "b.bin"
    p.write_bytes(b"xyz")
    assert core._read_binary(str(p)) == b"xyz"


# --- delete ------------------------------------------------------------------ #
def test_delete_post_success():
    fake = FakeRequester((204, {}, {}))
    out = core.delete_post("urn:li:ugcPost:1", TOKEN_ENV, fake)
    assert out["ok"] is True
    assert fake.calls[0]["method"] == "DELETE"
    assert "urn%3Ali%3AugcPost%3A1" in fake.calls[0]["url"]


def test_delete_post_rejects_non_post_urn():
    with pytest.raises(core.LinkedInError):
        core.delete_post("urn:li:person:1", TOKEN_ENV, FakeRequester())


def test_delete_post_failure():
    fake = FakeRequester((404, {"message": "gone"}, {}))
    out = core.delete_post("urn:li:ugcPost:1", TOKEN_ENV, fake)
    assert out["ok"] is False
    assert out["status"] == 404


# --- comment / react (gated) ------------------------------------------------- #
def test_comment_gated_403_names_scope():
    fake = FakeRequester(_userinfo_ok(), (403, {"message": "denied"}, {}))
    out = core.comment("urn:li:ugcPost:1", "hi", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
    assert out["status"] == 403
    assert "w_member_social_feed" in out["hint"]
    assert "PARTNER-GATED" in out["hint"]


def test_comment_success_shape_when_permitted():
    fake = FakeRequester(
        _userinfo_ok(),
        (
            201,
            {"commentUrn": "urn:li:comment:(urn:li:ugcPost:1,9)"},
            {"X-RestLi-Id": "9"},
        ),
    )
    out = core.comment("urn:li:ugcPost:1", "hi", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["comment_urn"] == "urn:li:comment:(urn:li:ugcPost:1,9)"
    assert out["comment_id"] == "9"


def test_react_gated_403_names_scope():
    fake = FakeRequester(_userinfo_ok(), (403, {"message": "denied"}, {}))
    out = core.react("urn:li:ugcPost:1", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
    assert "w_member_social_feed" in out["hint"]


def test_react_success_when_permitted():
    fake = FakeRequester(
        _userinfo_ok(),
        (201, {"id": "urn:li:like:(urn:li:person:ABC123,urn:li:ugcPost:1)"}, {}),
    )
    out = core.react("urn:li:ugcPost:1", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["like_id"].startswith("urn:li:like:")


# --- OAuth flow -------------------------------------------------------------- #
def test_build_authorization_url_defaults():
    out = core.build_authorization_url(environ=TOKEN_ENV)
    assert out["ok"] is True
    assert out["authorization_url"].startswith(core.AUTHORIZATION_URL + "?")
    assert "response_type=code" in out["authorization_url"]
    assert "scope=openid+profile+email+w_member_social" in out["authorization_url"]


def test_build_authorization_url_rejects_gated_scope():
    with pytest.raises(core.LinkedInError) as exc:
        core.build_authorization_url(
            scopes="openid r_organization_social", environ=TOKEN_ENV
        )
    assert "r_organization_social" in str(exc.value)
    assert "partner approval" in str(exc.value)


def test_build_authorization_url_requires_redirect():
    with pytest.raises(core.LinkedInError):
        core.build_authorization_url(environ={"LINKEDIN_CLIENT_ID": "c"})


def test_build_authorization_url_with_state():
    out = core.build_authorization_url(state="xyz", environ=TOKEN_ENV)
    assert "state=xyz" in out["authorization_url"]


def test_build_authorization_url_empty_scopes():
    with pytest.raises(core.LinkedInError):
        core.build_authorization_url(scopes="   ", environ=TOKEN_ENV)


def test_exchange_code_success():
    fake = FakeRequester(
        (
            200,
            {"access_token": "AT", "expires_in": 5184000, "scope": "w_member_social"},
            {},
        )
    )
    out = core.exchange_code("thecode", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["access_token"] == "AT"
    assert out["expires_in_days"] == 60.0
    body = fake.calls[0]["body"]
    assert "grant_type=authorization_code" in body
    assert "code=thecode" in body


def test_exchange_code_requires_redirect():
    with pytest.raises(core.LinkedInError):
        core.exchange_code(
            "c", environ={"LINKEDIN_CLIENT_ID": "c", "LINKEDIN_CLIENT_SECRET": "s"}
        )


def test_exchange_code_failure():
    fake = FakeRequester((400, {"message": "bad code"}, {}))
    out = core.exchange_code("c", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
    assert out["status"] == 400


# --- token introspection ----------------------------------------------------- #
def test_token_status_active():
    fake = FakeRequester(
        (
            200,
            {
                "active": True,
                "status": "active",
                "scope": "openid,profile,w_member_social",
                "expires_at": 123,
                "auth_type": "3L",
            },
            {},
        )
    )
    out = core.token_status(environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["active"] is True
    assert out["can_post"] is True
    assert out["can_identify"] is True
    assert "w_member_social" in out["scopes"]


def test_token_status_explicit_token():
    fake = FakeRequester((200, {"active": False, "status": "expired"}, {}))
    out = core.token_status(token="sometoken", environ=TOKEN_ENV, requester=fake)
    assert out["active"] is False
    assert "token=sometoken" in fake.calls[0]["body"]


def test_token_status_failure():
    fake = FakeRequester((401, {"message": "bad secret"}, {}))
    out = core.token_status(environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False


# --- auth_status ------------------------------------------------------------- #
def test_auth_status_nothing_configured():
    out = core.auth_status({}, FakeRequester())
    assert out["ok"] is False
    assert "LINKEDIN_ACCESS_TOKEN" in out["error"]
    assert out["credentials_present"]["LINKEDIN_ACCESS_TOKEN"] is False


def test_auth_status_token_only_cannot_introspect():
    out = core.auth_status({"LINKEDIN_ACCESS_TOKEN": "t"}, FakeRequester())
    assert out["ok"] is True
    assert out["token"]["ok"] is False
    assert "CLIENT_ID" in out["token"]["error"]


def test_auth_status_full_probes_token():
    fake = FakeRequester(
        (200, {"active": True, "status": "active", "scope": "w_member_social"}, {})
    )
    out = core.auth_status(TOKEN_ENV, fake)
    assert out["ok"] is True
    assert out["token"]["ok"] is True
    assert out["token"]["can_post"] is True


def test_auth_status_reports_missing_redirect():
    env = {
        "LINKEDIN_ACCESS_TOKEN": "t",
        "LINKEDIN_CLIENT_ID": "c",
        "LINKEDIN_CLIENT_SECRET": "s",
    }
    fake = FakeRequester((200, {"active": True}, {}))
    out = core.auth_status(env, fake)
    assert "LINKEDIN_REDIRECT_URI" in out["missing"]


# --- request_json body encoding + _fail hint matrix -------------------------- #
def test_request_json_encodes_each_body_type(monkeypatch):
    captured = {}

    class Resp:
        status = 200
        headers = {}

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["data"] = req.data
        return Resp()

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)

    core.request_json("POST", "https://x", body=b"rawbytes")
    assert captured["data"] == b"rawbytes"
    core.request_json("POST", "https://x", body="rawstr")
    assert captured["data"] == b"rawstr"
    core.request_json("POST", "https://x", body={"k": "v"})
    assert captured["data"] == b'{"k": "v"}'
    core.request_json("GET", "https://x", body=None)
    assert captured["data"] is None


@pytest.mark.parametrize(
    "status,needle",
    [
        (0, "network error"),
        (401, "60 days"),
        (403, "Products tab"),
        (429, "150 member requests"),
        (500, "failed with HTTP 500"),
    ],
)
def test_fail_hint_matrix(status, needle):
    out = core._fail(status, {"message": ""}, "do a thing")
    assert out["ok"] is False
    assert out["status"] == status
    blob = out["hint"] or out["error"]
    assert needle in blob


def test_fail_gated_scope_hint_wins():
    out = core._fail(
        403, {"message": "no"}, "comment", gated_scope="w_member_social_feed"
    )
    assert "w_member_social_feed" in out["hint"]
    assert "PARTNER-GATED" in out["hint"]


def test_fail_parses_string_payload():
    out = core._fail(500, "raw upstream text", "act")
    assert "raw upstream text" in out["error"]


def test_fail_reads_service_error_code():
    out = core._fail(403, {"message": "x", "serviceErrorCode": 100}, "act")
    assert out["serviceErrorCode"] == 100


# --- optional-field omission paths ------------------------------------------- #
def test_post_article_without_title_or_description():
    fake = FakeRequester(_userinfo_ok(), _created())
    out = core.post_article("x", "https://y.com", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    media = fake.calls[1]["body"]["specificContent"]["com.linkedin.ugc.ShareContent"][
        "media"
    ][0]
    assert "title" not in media
    assert "description" not in media


def test_post_image_without_optional_fields_and_put_ok():
    fake = FakeRequester(_userinfo_ok(), _register_ok(), (200, {}, {}), _created())
    out = core.post_image(
        "x", "i.png", environ=TOKEN_ENV, requester=fake, opener=lambda p: b"d"
    )
    assert out["ok"] is True
    assert fake.calls[2]["method"] == "PUT"  # no retry needed


def test_comment_uses_header_id_when_no_comment_urn():
    fake = FakeRequester(_userinfo_ok(), (201, {}, {"X-RestLi-Id": "77"}))
    out = core.comment("urn:li:ugcPost:1", "hi", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is True
    assert out["comment_id"] == "77"
    assert out["comment_urn"] is None


def test_created_post_without_header():
    # A 201 with no X-RestLi-Id still returns ok with post_urn None.
    fake = FakeRequester(_created(urn=""))
    out = core.post_text(
        "hi", author="urn:li:person:X", environ=TOKEN_ENV, requester=fake
    )
    assert out["ok"] is True
    assert out["post_urn"] is None
    assert "url" not in out


def test_token_status_missing_token_raises():
    with pytest.raises(core.LinkedInError):
        core.token_status(
            environ={"LINKEDIN_CLIENT_ID": "c", "LINKEDIN_CLIENT_SECRET": "s"}
        )


def test_exchange_code_non_dict_payload_is_failure():
    fake = FakeRequester((200, "not-json", {}))
    out = core.exchange_code("c", environ=TOKEN_ENV, requester=fake)
    assert out["ok"] is False
