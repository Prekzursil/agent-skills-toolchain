#!/usr/bin/env python3
"""Fetch official plugin-manifest schemas and docs into captures/ (dual rails)."""
from __future__ import annotations

import hashlib
import json
import random
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAP = HERE / "captures"
UA = {
    "User-Agent": "ast-integrate-RES-0129-research/1.0",
    "Accept": "*/*",
}

# kind: json-schema | ts-source | rs-source | md-spec | docs-prose | json-example
SOURCES: tuple[tuple[str, str, str, str, bool], ...] = (
    (
        "claude-code",
        "schema-schemastore",
        "json-schema",
        "https://json.schemastore.org/claude-code-plugin-manifest.json",
        True,
    ),
    (
        "claude-code",
        "schema-github",
        "json-schema",
        "https://raw.githubusercontent.com/SchemaStore/schemastore/master/src/schemas/json/claude-code-plugin-manifest.json",
        True,
    ),
    (
        "claude-code",
        "docs-plugins-reference",
        "docs-prose",
        "https://code.claude.com/docs/en/plugins-reference.md",
        False,
    ),
    (
        "claude-code",
        "repo-manifest-reference",
        "md-spec",
        "https://raw.githubusercontent.com/anthropics/claude-code/main/plugins/plugin-dev/skills/plugin-structure/references/manifest-reference.md",
        True,
    ),
    (
        "codex-cli",
        "manifest-rs",
        "rs-source",
        "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core-plugins/src/manifest.rs",
        True,
    ),
    (
        "codex-cli",
        "plugin-json-spec",
        "md-spec",
        "https://raw.githubusercontent.com/openai/codex/main/codex-rs/skills/src/assets/samples/plugin-creator/references/plugin-json-spec.md",
        True,
    ),
    (
        "codex-cli",
        "docs-build",
        "docs-prose",
        "https://developers.openai.com/codex/plugins/build",
        False,
    ),
    (
        "gemini-cli",
        "extension-ts",
        "ts-source",
        "https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/cli/src/config/extension.ts",
        True,
    ),
    (
        "gemini-cli",
        "docs-reference-md",
        "md-spec",
        "https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/extensions/reference.md",
        True,
    ),
    (
        "gemini-cli",
        "docs-prose",
        "docs-prose",
        "https://geminicli.com/docs/extensions/reference/",
        False,
    ),
    (
        "cursor",
        "docs-reference",
        "md-spec",
        "https://cursor.com/docs/reference/plugins.md",
        True,
    ),
    (
        "cursor",
        "docs-plugins",
        "docs-prose",
        "https://cursor.com/docs/plugins.md",
        False,
    ),
    (
        "cursor",
        "template-plugin-json",
        "json-example",
        "https://raw.githubusercontent.com/cursor/plugin-template/main/plugins/starter-advanced/.cursor-plugin/plugin.json",
        False,
    ),
    (
        "continue-dev",
        "config-yaml-schema-ts",
        "ts-source",
        "https://raw.githubusercontent.com/continuedev/continue/main/packages/config-yaml/src/schemas/index.ts",
        True,
    ),
    (
        "continue-dev",
        "docs-reference",
        "docs-prose",
        "https://docs.continue.dev/reference",
        False,
    ),
    (
        "copilot-extensions",
        "cli-plugin-reference",
        "md-spec",
        "https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference",
        True,
    ),
    (
        "copilot-extensions",
        "docs-creating",
        "docs-prose",
        "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/plugins-creating",
        False,
    ),
    (
        "copilot-extensions",
        "docs-md-github",
        "md-spec",
        "https://raw.githubusercontent.com/github/docs/main/content/copilot/reference/copilot-cli-reference/cli-plugin-reference.md",
        True,
    ),
)


def fetch(url: str) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=40) as resp:
                body = resp.read()
                return {
                    "url": url,
                    "final_url": resp.geturl(),
                    "http_status": int(getattr(resp, "status", None) or resp.getcode()),
                    "fetched_at": fetched_at,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "content_type": resp.headers.get("Content-Type"),
                    "body": body,
                    "ok": True,
                }
        except urllib.error.HTTPError as exc:
            body = exc.read() if hasattr(exc, "read") else b""
            status = int(exc.code)
            if status in {429, 502, 503, 529} and attempt < 4:
                time.sleep((0.4 * (2**attempt)) + random.random() * 0.3)
                fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                last_err = exc
                continue
            return {
                "url": url,
                "final_url": url,
                "http_status": status,
                "fetched_at": fetched_at,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest() if body else None,
                "content_type": None,
                "body": body,
                "ok": False,
                "error": f"HTTPError {status}",
            }
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < 4:
                time.sleep((0.4 * (2**attempt)) + random.random() * 0.3)
                fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                continue
            return {
                "url": url,
                "final_url": url,
                "http_status": 0,
                "fetched_at": fetched_at,
                "bytes": 0,
                "sha256": None,
                "content_type": None,
                "body": b"",
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return {
        "url": url,
        "final_url": url,
        "http_status": 0,
        "fetched_at": fetched_at,
        "bytes": 0,
        "sha256": None,
        "content_type": None,
        "body": b"",
        "ok": False,
        "error": str(last_err),
    }


def main() -> int:
    CAP.mkdir(parents=True, exist_ok=True)
    index: dict = {
        "unit_id": "RES-0129",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [],
    }
    ok_n = 0
    for client, sid, kind, url, complete in SOURCES:
        rec = fetch(url)
        fname = f"{client}__{sid}"
        suffix = ".json" if kind in {"json-schema", "json-example"} else ".body"
        path = CAP / f"{fname}{suffix}"
        meta = {k: rec[k] for k in rec if k != "body"}
        meta.update(
            {
                "client": client,
                "source_id": sid,
                "kind": kind,
                "complete_field_list": complete,
                "capture_path": (
                    "command-center/p2-wave/probes/RES-0129/captures/" + path.name
                ),
            }
        )
        path.write_bytes(rec.get("body") or b"")
        (CAP / f"{fname}.meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        index["sources"].append(meta)
        mark = "OK" if rec.get("ok") and rec.get("http_status") == 200 else "FAIL"
        if mark == "OK":
            ok_n += 1
        print(f"{mark} {client}/{sid} status={rec.get('http_status')} bytes={rec.get('bytes')}")
        time.sleep(0.15)
    (CAP / "_index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"captured_ok={ok_n}/{len(SOURCES)}")
    by_client: dict[str, list[dict]] = {}
    for src in index["sources"]:
        by_client.setdefault(src["client"], []).append(src)
    missing = []
    for client, rows in by_client.items():
        structured = [
            r
            for r in rows
            if r.get("ok")
            and r.get("http_status") == 200
            and r.get("kind") in {"json-schema", "ts-source", "rs-source", "md-spec"}
            and r.get("complete_field_list")
        ]
        prose = [
            r
            for r in rows
            if r.get("ok")
            and r.get("http_status") == 200
            and r.get("kind") in {"docs-prose", "md-spec"}
        ]
        if not structured:
            missing.append(f"{client}:no-complete-structured")
        if not prose:
            missing.append(f"{client}:no-prose")
    if missing:
        print("FAILED:capture dual-rail gaps " + ",".join(missing))
        return 1
    print("SUCCESS:RES-0129-capture dual rails present for all six clients")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
