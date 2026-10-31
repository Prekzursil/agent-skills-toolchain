#!/usr/bin/env python3
"""Minimal OVH REST helper. No secrets printed."""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

ENDPOINTS = {
    "ovh-eu": "https://eu.api.ovh.com/1.0",
    "ovh-ca": "https://ca.api.ovh.com/1.0",
    "ovh-us": "https://api.us.ovhcloud.com/1.0",
}


def _cfg() -> tuple[str, str, str, str]:
    app = os.environ.get("OVH_APPLICATION_KEY") or ""
    secret = os.environ.get("OVH_APPLICATION_SECRET") or ""
    ck = os.environ.get("OVH_CONSUMER_KEY") or ""
    ep = os.environ.get("OVH_ENDPOINT") or "ovh-eu"
    if not (app and secret and ck):
        raise SystemExit("FAILED:ovh-creds-missing")
    return app, secret, ck, ep


def call(method: str, path: str, body: Any | None = None, endpoint: str | None = None) -> Any:
    app, secret, ck, ep_name = _cfg()
    if endpoint:
        ep_name = endpoint
    base = ENDPOINTS.get(ep_name, ep_name)
    url = base + path
    payload = "" if body is None else json.dumps(body, separators=(",", ":"))
    ts = str(int(time.time()) + 0)
    # server time
    try:
        with urllib.request.urlopen(base + "/auth/time", timeout=20) as r:
            ts = r.read().decode("utf-8").strip()
    except Exception:
        pass
    sig_src = "+".join([secret, ck, method.upper(), url, payload, ts])
    sig = "$1$" + hashlib.sha1(sig_src.encode("utf-8")).hexdigest()
    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8") if payload else None,
        method=method.upper(),
        headers={
            "X-Ovh-Application": app,
            "X-Ovh-Consumer": ck,
            "X-Ovh-Timestamp": ts,
            "X-Ovh-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"OVH {method} {path} HTTP {exc.code} {err}") from exc
