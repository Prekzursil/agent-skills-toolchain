#!/usr/bin/env python3
"""linkedin-mcp MCP server -- self-serve LinkedIn (personal developer app) over stdio.

Thin FastMCP wrappers over ``linkedin_core`` (which holds every bit of the REST
logic and is unit-testable with no token and no network). Scoped to LinkedIn's
Open Permissions surface only -- Sign In with LinkedIn (OpenID Connect) and Share
on LinkedIn -- because those are the ONLY products a personal app can enable
without LinkedIn partner review. See README.md and SETUP.md.

Credentials are read from the environment at call time and NEVER inlined here:
    LINKEDIN_ACCESS_TOKEN / LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET / LINKEDIN_REDIRECT_URI

Run: ``python server.py`` (stdio MCP; what ~/.mcp.json launches).
A missing token yields a clean, actionable error from every tool -- never a
stack trace -- so the server always starts and lists its tools.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import linkedin_core as core  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("linkedin")


def _guard(fn, *args, **kwargs) -> dict:
    """Run a core call, converting a LinkedInError into a structured result.

    Guarantees every tool returns a dict (never raises) so a missing token or a
    bad argument surfaces as an actionable message, not an MCP transport error.
    """
    try:
        return fn(*args, **kwargs)
    except core.LinkedInError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def linkedin_auth_status() -> dict:
    """Report which LinkedIn credentials are configured and probe the token.

    Safe to call with NOTHING set up -- it names exactly which environment
    variable is missing and how to obtain it, plus (when client id/secret are
    present) a live introspection of the token's scopes and expiry. Start here.
    Needs: nothing (works empty); introspection needs CLIENT_ID + CLIENT_SECRET.
    """
    return _guard(core.auth_status)


@mcp.tool()
def linkedin_whoami() -> dict:
    """Return the authenticated member's profile and Person URN via OIDC userinfo.

    The Person URN is what the posting tools use as the author, so callers rarely
    need it directly -- the post tools resolve it automatically.
    Product: Sign In with LinkedIn using OpenID Connect. Scopes: openid, profile
    (email optional). Endpoint: GET /v2/userinfo.
    """
    return _guard(core.whoami)


@mcp.tool()
def linkedin_post_text(text: str, visibility: str = "PUBLIC", author: str = "") -> dict:
    """Publish a text-only post to the authenticated member's LinkedIn feed.

    ``visibility`` is PUBLIC (anyone) or CONNECTIONS (1st-degree only). ``author``
    is an optional ``urn:li:person:...`` override; if omitted it is resolved via
    userinfo. Returns the new post URN + feed URL on success.
    Product: Share on LinkedIn. Scope: w_member_social. Endpoint: POST /v2/ugcPosts.
    """
    return _guard(core.post_text, text, visibility, author)


@mcp.tool()
def linkedin_post_article(
    text: str,
    url: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
    author: str = "",
) -> dict:
    """Publish a post that shares an external article/URL with commentary.

    ``url`` is the link to share; ``title``/``description`` are optional link
    card overrides. Returns the new post URN + feed URL on success.
    Product: Share on LinkedIn. Scope: w_member_social. Endpoint: POST /v2/ugcPosts.
    """
    return _guard(core.post_article, text, url, title, description, visibility, author)


@mcp.tool()
def linkedin_post_image(
    text: str,
    image_path: str,
    title: str = "",
    description: str = "",
    visibility: str = "PUBLIC",
    author: str = "",
) -> dict:
    """Publish a post with a local image attached (register -> upload -> share).

    ``image_path`` is a path readable by the server process. Runs the 3-step
    LinkedIn media flow (registerUpload -> binary upload -> ugcPost). Returns the
    new post URN + feed URL on success.
    Product: Share on LinkedIn. Scope: w_member_social. Endpoints: POST
    /v2/assets?action=registerUpload, the returned uploadUrl, POST /v2/ugcPosts.
    """
    return _guard(
        core.post_image, text, image_path, title, description, visibility, author
    )


@mcp.tool()
def linkedin_delete_post(post_urn: str) -> dict:
    """Delete a post you authored, by its URN (urn:li:ugcPost:... or urn:li:share:...).

    Product: Share on LinkedIn. Scope: w_member_social. Endpoint: DELETE
    /v2/ugcPosts/{urn-encoded post_urn}.
    """
    return _guard(core.delete_post, post_urn)


@mcp.tool()
def linkedin_comment(post_urn: str, text: str, author: str = "") -> dict:
    """Comment on a post/share/activity URN as the authenticated member.

    GATED (expected 403 on a self-serve app): the member socialActions surface
    requires the PARTNER-ONLY w_member_social_feed scope -- independently
    reproduced 403 in two live reports (soleur #799, claude-code #60046). Shipped
    for honest matrix coverage; returns LinkedIn's real 403 with the missing
    scope named, never a crash. Endpoint: POST /v2/socialActions/{post_urn}/comments.
    """
    return _guard(core.comment, post_urn, text, author)


@mcp.tool()
def linkedin_react(post_urn: str, author: str = "") -> dict:
    """Like a post/share/activity URN as the authenticated member.

    GATED (expected 403 on a self-serve app; same w_member_social_feed gate as
    linkedin_comment). Shipped for honest matrix coverage; returns LinkedIn's
    real 403 with the missing scope named. Endpoint: POST
    /v2/socialActions/{post_urn}/likes.
    """
    return _guard(core.react, post_urn, author)


@mcp.tool()
def linkedin_authorization_url(
    scopes: str = core.DEFAULT_SCOPES, redirect_uri: str = "", state: str = ""
) -> dict:
    """Build the 3-legged OAuth authorization URL to open in a browser (no network).

    Rejects any non-self-serve scope up front. Only needed if you are NOT using
    the portal token generator. ``redirect_uri`` defaults to
    LINKEDIN_REDIRECT_URI and must match a URL on the app's Auth tab.
    Needs: LINKEDIN_CLIENT_ID (+ a redirect URL).
    """
    return _guard(core.build_authorization_url, scopes, redirect_uri, state)


@mcp.tool()
def linkedin_exchange_code(code: str, redirect_uri: str = "") -> dict:
    """Exchange a 3-legged authorization code for a 60-day member access token.

    Returns the access token (and refresh token, if your app has programmatic
    refresh) so you can store it as LINKEDIN_ACCESS_TOKEN. Auth codes expire 30
    minutes after issue. Needs: LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET (+
    the same redirect URL used to get the code).
    """
    return _guard(core.exchange_code, code, redirect_uri)


@mcp.tool()
def linkedin_token_status(token: str = "") -> dict:
    """Introspect a token (defaults to LINKEDIN_ACCESS_TOKEN): active, scopes, expiry.

    Use to check whether your token is still valid, what scopes it carries, and
    when it expires. Needs: LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET (+ a
    token, either the argument or LINKEDIN_ACCESS_TOKEN).
    Endpoint: POST /oauth/v2/introspectToken.
    """
    return _guard(core.token_status, token)


def main() -> None:  # pragma: no cover -- module entrypoint
    mcp.run()


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    main()
