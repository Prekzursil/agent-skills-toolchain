"""Execute the lawful public examination for RES-0119 and persist captures."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from policy import (
    ALLOWED_HOSTS,
    CLEAR_WEB_TARGETS,
    NEVER_LIST,
    PROGRAM_TOPIC_NEEDLES,
    SKIP_DIR_NAMES,
    USER_AGENT,
    host_allowed,
    looks_like_optin,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURE_DIR = HERE / "captures"
ONION_RE = re.compile(rb"[a-z2-7]{56}\.onion", re.I)
AUTH_HEADER_RE = re.compile(r"^www-authenticate$", re.I)
PAYMENT_STATUS = {402, 451}


class AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not host_allowed(newurl):
            raise urllib.error.URLError(f"redirect-off-allowlist:{newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def which_bin(name: str) -> str | None:
    return shutil.which(name)


def port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_owner_optin(root: Path) -> list[str]:
    hits: list[str] = []
    search_root = root / "command-center"
    if not search_root.is_dir():
        return hits
    for dirpath, dirnames, filenames in os.walk(search_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if looks_like_optin(path):
                hits.append(path.relative_to(root).as_posix())
    return sorted(hits)


def environment_probe(root: Path) -> dict[str, Any]:
    bins = {name: which_bin(name) for name in ("tor", "torsocks", "torify")}
    socks = {
        "9050": port_open("127.0.0.1", 9050),
        "9150": port_open("127.0.0.1", 9150),
    }
    optin = scan_owner_optin(root)
    client_present = any(bins.values()) or any(socks.values())
    blocked = []
    if not client_present:
        blocked.append("tor-client-absent")
    if not optin:
        blocked.append("owner-opt-in-absent")
    return {
        "measured_at": utc_now(),
        "binaries": bins,
        "local_socks_listeners": socks,
        "tor_client_present": client_present,
        "owner_optin_paths": optin,
        "owner_optin_present": bool(optin),
        "onion_fetch_permitted": False,
        "onion_fetch_blocked_because": blocked,
    }


def _headers_dict(headers: Any) -> dict[str, str]:
    return {str(k): str(v) for k, v in headers.items()}


def fetch_allowlisted(url: str, dest_stem: str) -> dict[str, Any]:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    t0 = time.time()
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        AllowlistRedirectHandler,
        urllib.request.HTTPSHandler(context=ctx),
    )
    entry: dict[str, Any] = {
        "url": url,
        "method": "GET",
        "started_at": started,
        "class": "clear-web",
        "allowlisted": True,
        "auth_required": False,
        "payment_required": False,
        "attempted": True,
        "completed": False,
        "skipped": False,
        "never_list_actions": {item: "not-attempted" for item in NEVER_LIST},
    }
    try:
        with opener.open(req, timeout=25) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            final = resp.geturl()
            raw_headers = _headers_dict(resp.headers)
            body = resp.read(400000)
        if not host_allowed(final):
            raise RuntimeError(f"final-url-off-allowlist:{final}")
        header_blob = (
            "\n".join(f"{k}: {v}" for k, v in sorted(raw_headers.items())) + "\n"
        ).encode("utf-8")
        body_path = CAPTURE_DIR / f"{dest_stem}.body"
        head_path = CAPTURE_DIR / f"{dest_stem}.headers"
        body_path.write_bytes(body)
        head_path.write_bytes(header_blob)
        www_auth = any(AUTH_HEADER_RE.match(k) for k in raw_headers)
        entry.update(
            {
                "completed": True,
                "http_status": status,
                "final_url": final,
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "header_sha256": sha256_bytes(header_blob),
                "capture_body": body_path.relative_to(REPO).as_posix(),
                "capture_headers": head_path.relative_to(REPO).as_posix(),
                "elapsed_ms": int((time.time() - t0) * 1000),
                "ended_at": utc_now(),
                "auth_required": status in {401, 407} or www_auth,
                "payment_required": status in PAYMENT_STATUS,
                "www_authenticate": www_auth,
                "host": (urlparse(final).hostname or "").lower(),
            }
        )
        return entry
    except Exception as exc:
        entry.update(
            {
                "completed": False,
                "http_status": 0,
                "error_type": type(exc).__name__,
                "error": str(exc)[:400],
                "elapsed_ms": int((time.time() - t0) * 1000),
                "ended_at": utc_now(),
            }
        )
        return entry


def topic_hits(body: bytes) -> list[str]:
    text = body.decode("utf-8", "replace").lower()
    return [n for n in PROGRAM_TOPIC_NEEDLES if n in text]


def published_onions(body: bytes) -> list[str]:
    found = sorted({m.decode("ascii").lower() for m in ONION_RE.findall(body)})
    return found[:20]


def catalog_topic_census(root: Path) -> dict[str, Any]:
    catalog = json.loads(
        (root / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    units = catalog.get("work_units") or []
    res = [u for u in units if str(u.get("id") or "").startswith("RES-")]
    needles = (
        "orchestr",
        "agent",
        "prompt",
        "mcp",
        "workflow",
        "council",
        "deliberat",
    )
    topicish = []
    onionish = []
    for u in res:
        blob = f"{u.get('title') or ''} {u.get('question_or_target') or ''}".lower()
        if any(n in blob for n in needles):
            topicish.append(u.get("id"))
        if "onion" in blob or " tor" in blob or blob.startswith("tor"):
            onionish.append(u.get("id"))
    this = next((u for u in units if u.get("id") == "RES-0119"), {})
    return {
        "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
        "res_unit_count": len(res),
        "program_topic_res_count": len(topicish),
        "program_topic_res_ids_head": topicish[:12],
        "onion_or_tor_res_ids": onionish,
        "this_unit_title": this.get("title"),
        "this_unit_owner_approval_required": this.get("owner_approval_required"),
        "this_unit_question": this.get("question_or_target"),
    }


def skipped_onion_attempt(env: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": None,
        "method": "GET",
        "class": "onion",
        "allowlisted": False,
        "attempted": False,
        "completed": False,
        "skipped": True,
        "skip_reasons": list(env.get("onion_fetch_blocked_because") or []),
        "auth_required": False,
        "payment_required": False,
        "http_status": None,
        "note": (
            "No onion-circuit fetch was issued. Owner opt-in for the "
            "controversial source class is unanswered on disk, and no Tor "
            "client is present. The research question is answered with an "
            "explicit null rather than by opening a circuit."
        ),
        "started_at": utc_now(),
        "ended_at": utc_now(),
        "never_list_actions": {item: "not-attempted" for item in NEVER_LIST},
    }


def run_sweep(root: Path | None = None) -> dict[str, Any]:
    root = root or REPO
    env = environment_probe(root)
    census = catalog_topic_census(root)
    egress: list[dict[str, Any]] = []
    captures: list[dict[str, Any]] = []
    for target in CLEAR_WEB_TARGETS:
        row = fetch_allowlisted(target["url"], target["id"])
        row["target_id"] = target["id"]
        row["kind"] = target["kind"]
        row["rail"] = target["rail"]
        egress.append(row)
        if row.get("completed") and row.get("capture_body"):
            body = (root / row["capture_body"]).read_bytes()
            captures.append(
                {
                    "id": target["id"],
                    "kind": target["kind"],
                    "rail": target["rail"],
                    "permalink": row.get("final_url") or target["url"],
                    "requested_url": target["url"],
                    "fetch_timestamp": row.get("ended_at"),
                    "http_status": row.get("http_status"),
                    "sha256": row.get("sha256"),
                    "bytes": row.get("bytes"),
                    "path": row.get("capture_body"),
                    "headers_path": row.get("capture_headers"),
                    "program_topic_hits": topic_hits(body),
                    "published_onion_addresses": published_onions(body),
                    "why": target["why"],
                    "host_allowed": host_allowed(
                        row.get("final_url") or target["url"]
                    ),
                }
            )
    egress.append(skipped_onion_attempt(env))
    topic_hit_total = sum(len(c.get("program_topic_hits") or []) for c in captures)
    completed = [
        e for e in egress if e.get("class") == "clear-web" and e.get("completed")
    ]
    auth_or_pay = [
        e for e in egress if e.get("auth_required") or e.get("payment_required")
    ]
    return {
        "environment": env,
        "catalog_census": census,
        "egress_log": egress,
        "captures": captures,
        "clear_web_completed": len(completed),
        "onion_fetches_completed": 0,
        "program_topic_hits_in_captures": topic_hit_total,
        "auth_or_payment_hits": auth_or_pay,
        "allowed_hosts": sorted(ALLOWED_HOSTS),
        "never_list": list(NEVER_LIST),
    }


if __name__ == "__main__":
    result = run_sweep()
    print(
        json.dumps(
            {
                "clear_web_completed": result["clear_web_completed"],
                "onion_fetches_completed": result["onion_fetches_completed"],
                "program_topic_hits_in_captures": result[
                    "program_topic_hits_in_captures"
                ],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0119-sweep")
