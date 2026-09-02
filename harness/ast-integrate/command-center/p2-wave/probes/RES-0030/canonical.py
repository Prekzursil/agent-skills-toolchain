"""Live resolve of block/goose -> aaif-goose/goose (HTML + GitHub API)."""
from __future__ import annotations

import json
from typing import Any

from constants import (
    CANONICAL_API,
    CANONICAL_FULL_NAME,
    CANONICAL_HTML,
    OLD_API,
    OLD_HTML,
    REPO_NUMERIC_ID,
)
from fetchutil import fetch_chain, lineage


def _assert_html_redirect(rec: dict[str, Any]) -> None:
    chain = rec.get("chain") or []
    if len(chain) < 2:
        raise RuntimeError(f"html redirect chain too short: {chain}")
    hop0, hop1 = chain[0], chain[1]
    if hop0.get("status") != 301:
        raise RuntimeError(f"old html pointer was not 301: {hop0}")
    loc = str(hop0.get("location") or "")
    if "aaif-goose/goose" not in loc.replace("https://github.com/", ""):
        if loc.rstrip("/") != CANONICAL_HTML:
            raise RuntimeError(f"html 301 location not canonical: {loc}")
    if hop1.get("status") != 200:
        raise RuntimeError(f"canonical html not 200: {hop1}")
    if str(hop1.get("url") or "").rstrip("/") != CANONICAL_HTML:
        raise RuntimeError(f"canonical html hop url mismatch: {hop1.get('url')}")


def _assert_api_redirect(rec: dict[str, Any]) -> dict[str, Any]:
    chain = rec.get("chain") or []
    if len(chain) < 2:
        raise RuntimeError(f"api redirect chain too short: {chain}")
    hop0, hop1 = chain[0], chain[1]
    if hop0.get("status") != 301:
        raise RuntimeError(f"old api pointer was not 301: {hop0}")
    loc = str(hop0.get("location") or "")
    if str(REPO_NUMERIC_ID) not in loc:
        raise RuntimeError(f"api 301 did not target repo id {REPO_NUMERIC_ID}: {loc}")
    if hop1.get("status") != 200:
        raise RuntimeError(f"api final not 200: {hop1}")
    body = rec.get("body") or b""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"api final body unparseable: {exc}") from exc
    if payload.get("full_name") != CANONICAL_FULL_NAME:
        raise RuntimeError(f"api full_name={payload.get('full_name')}")
    if payload.get("id") != REPO_NUMERIC_ID:
        raise RuntimeError(f"api id={payload.get('id')}")
    html_url = str(payload.get("html_url") or "").rstrip("/")
    if html_url != CANONICAL_HTML:
        raise RuntimeError(f"api html_url={html_url}")
    return payload


def _assert_canonical_control(html: dict[str, Any], api: dict[str, Any]) -> None:
    hchain = html.get("chain") or []
    if not hchain or hchain[0].get("status") != 200:
        raise RuntimeError(f"canonical html control not 200: {hchain[:1]}")
    if hchain[0].get("location"):
        raise RuntimeError(f"canonical html unexpectedly redirected: {hchain[0]}")
    achain = api.get("chain") or []
    if not achain or achain[0].get("status") != 200:
        raise RuntimeError(f"canonical api control not 200: {achain[:1]}")
    body = api.get("body") or b""
    payload = json.loads(body.decode("utf-8"))
    if payload.get("full_name") != CANONICAL_FULL_NAME:
        raise RuntimeError(f"canonical api full_name={payload.get('full_name')}")


def resolve_canonical() -> dict[str, Any]:
    html_old = fetch_chain(OLD_HTML)
    _assert_html_redirect(html_old)
    api_old = fetch_chain(OLD_API)
    api_payload = _assert_api_redirect(api_old)
    html_new = fetch_chain(CANONICAL_HTML)
    api_new = fetch_chain(CANONICAL_API)
    _assert_canonical_control(html_new, api_new)

    html_chain = [
        {k: v for k, v in hop.items() if k != "sha256" or hop.get("status") == 301}
        for hop in html_old["chain"]
    ]
    # HTML 200 bodies churn; keep hop identity, drop volatile 200 sha.
    for hop in html_chain:
        if hop.get("status") == 200:
            hop.pop("sha256", None)
            hop["bytes_note"] = "html-200-body-volatile-not-hashed-as-evidence"

    api_chain = []
    for hop in api_old["chain"]:
        row = dict(hop)
        if hop.get("status") == 200:
            row.pop("sha256", None)
            row["bytes_note"] = "api-json-includes-live-counters-not-pinned"
        api_chain.append(row)

    return {
        "canonical_repo_url": CANONICAL_HTML,
        "canonical_api_url": CANONICAL_API,
        "canonical_full_name": CANONICAL_FULL_NAME,
        "repo_numeric_id": REPO_NUMERIC_ID,
        "old_html_pointer": OLD_HTML,
        "old_api_pointer": OLD_API,
        "html_redirect_chain": html_chain,
        "api_redirect_chain": api_chain,
        "html_fetched_at": html_old["fetched_at"],
        "api_fetched_at": api_old["fetched_at"],
        "api_final_status": api_old.get("final_status"),
        "clone_url": api_payload.get("clone_url"),
        "default_branch": api_payload.get("default_branch"),
        "control": {
            "canonical_html_status": (html_new.get("chain") or [{}])[0].get("status"),
            "canonical_html_no_location": not (html_new.get("chain") or [{}])[0].get("location"),
            "canonical_api_status": (api_new.get("chain") or [{}])[0].get("status"),
            "canonical_api_full_name": CANONICAL_FULL_NAME,
        },
        "source_lineage": [
            lineage(
                OLD_HTML,
                (html_old["chain"][0].get("status") if html_old["chain"] else None),
                html_old["chain"][0].get("sha256") if html_old["chain"] else None,
                html_old["fetched_at"],
                "html-redirect-probe",
            ),
            lineage(
                OLD_API,
                (api_old["chain"][0].get("status") if api_old["chain"] else None),
                api_old["chain"][0].get("sha256") if api_old["chain"] else None,
                api_old["fetched_at"],
                "github-api-structured",
            ),
            lineage(
                CANONICAL_HTML,
                (html_new["chain"][0].get("status") if html_new["chain"] else None),
                None,
                html_new["fetched_at"],
                "html-control-no-redirect",
            ),
        ],
    }
