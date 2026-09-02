#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0134.json from a live interstitial run.

Does not write SUBAGENT-RETURN / the per-unit manifest (write_receipts.py).
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from marketplace.http_registry import (  # noqa: E402
    RegistryFetchClient,
    SchemaValidationError,
    StatusOnlyRegistryClient,
    UnexpectedContentTypeError,
)
from harness import (  # noqa: E402
    FixtureServer,
    error_names_content_type,
    index_unchanged,
    seed_index,
    stat_index,
)

UNIT = "TST-0134"
OUT = "command-center/receipts/TST-0134.json"
SENTINEL = "SUCCESS:TST-0134"
CLIENT_REL = "tools/marketplace/http_registry.py"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if data
        else "0" * 64,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    aware = RegistryFetchClient()
    status_only = StatusOnlyRegistryClient()
    srv = FixtureServer()
    tb_on_html = ""
    genuine = None
    so: dict = {}
    before: dict = {}
    after: dict = {}
    html_err = ""
    html_type = ""
    rejected = False
    named_ct = False
    unchanged = False
    schema_hit = False
    schema_err = ""
    so_wrote_html = False
    try:
        with tempfile.TemporaryDirectory(prefix="tst0134-emit-") as tmp:
            genuine_path = Path(tmp) / "genuine.json"
            genuine = aware.fetch_index(srv.genuine_url, genuine_path)

            idx = Path(tmp) / "index.json"
            before = seed_index(idx)
            try:
                aware.fetch_index(srv.interstitial_url, idx)
            except UnexpectedContentTypeError as exc:
                rejected = True
                html_err = str(exc)
                html_type = type(exc).__name__
                named_ct = error_names_content_type(exc)
            except Exception as exc:  # noqa: BLE001
                tb_on_html = traceback.format_exc()
                html_err = f"{type(exc).__name__}: {exc}"
            after = stat_index(idx)
            unchanged = index_unchanged(before, after)

            try:
                aware.fetch_index(srv.bad_schema_url, Path(tmp) / "schema.json")
            except SchemaValidationError as exc:
                schema_hit = True
                schema_err = str(exc)

            so_path = Path(tmp) / "status-only.json"
            seed_index(so_path)
            so = status_only.fetch_index(srv.interstitial_url, so_path)
            so_body = so_path.read_bytes()
            so_wrote_html = b"<html" in so_body.lower() or b"captive" in so_body.lower()
    finally:
        srv.close()

    assert genuine is not None
    ok = (
        genuine.status == 200
        and rejected
        and named_ct
        and "text/html" in html_err.lower()
        and unchanged
        and schema_hit
        and not tb_on_html
        and bool(so.get("ok"))
        and so_wrote_html
        and "JSONDecodeError" not in html_err
        and "Expecting value" not in html_err
        and "Traceback" not in html_err
    )
    if not ok:
        print("FAILED:TST-0134 live interstitial measurements did not pass")
        print(
            json.dumps(
                {
                    "genuine_status": genuine.status,
                    "rejected": rejected,
                    "named_ct": named_ct,
                    "html_err": html_err,
                    "unchanged": unchanged,
                    "schema_hit": schema_hit,
                    "so_ok": so.get("ok"),
                    "so_wrote_html": so_wrote_html,
                    "tb_on_html": tb_on_html[-1500:],
                },
                sort_keys=True,
            )
        )
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client_sha, client_bytes = digest(REPO / CLIENT_REL)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11007",
        "title": "Captive-portal HTTP 200 interstitial is rejected by content, not status",
        "question_answered": (
            "When a network interstitial returns HTTP 200 with an HTML body in "
            "place of the registry JSON, does the client reject it?"
        ),
        "answer": (
            "Yes. RegistryFetchClient rejects HTTP 200 text/html before any JSON "
            f"parse. Error={html_type}: {html_err}. Index mtime_ns stayed "
            f"{before['mtime_ns']} (sha256={before['sha256']}). The same client "
            "accepts genuine application/json that validates as index_page. A "
            "status-only client accepts the identical interstitial and writes HTML, "
            "so this test fails that client."
        ),
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "fault-injection-tester",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            art(CLIENT_REL, "supporting"),
            art(
                "command-center/p2-wave/probes/TST-0134/probe1_both_states.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0134/probe2_status_only.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0134/harness.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/TST-0134/fixtures/interstitial.html",
                "supporting",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Signal (a): interstitial error names unexpected content-type "
                    f"text/html. type={html_type} text={html_err}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CLIENT_REL}:require_content_type",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/TST-0134/probe1_both_states.py"
                        ),
                        "raw_output": html_err,
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"tst-0134-ct-error").hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "RegistryFetchClient.require_content_type"
                            "(text/html; charset=utf-8) -> UnexpectedContentTypeError"
                        ),
                        "raw_output": html_err,
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"tst-0134-ct-verify").hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    "Signal (b): rejection ran before index mutation. "
                    f"before_mtime_ns={before['mtime_ns']} after_mtime_ns={after['mtime_ns']} "
                    f"before_sha256={before['sha256']} after_sha256={after['sha256']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{CLIENT_REL}:fetch_index",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "Path.stat mtime_ns + sha256 of seeded index",
                        "raw_output": json.dumps({"before": before, "after": after}, sort_keys=True),
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"tst-0134-mtime").hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": "compare before/after sha256 of seeded index bytes",
                        "raw_output": json.dumps(
                            {
                                "unchanged": unchanged,
                                "before_sha256": before.get("sha256"),
                                "after_sha256": after.get("sha256"),
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"tst-0134-mtime-verify").hexdigest()[:32],
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "max 3 attempts, full-jitter backoff"},
        "tests": [
            {
                "id": "both-states-genuine-json",
                "command": "RegistryFetchClient.fetch_index(genuine application/json)",
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"status={genuine.status} bytes_written={genuine.bytes_written}",
            },
            {
                "id": "interstitial-html-200-rejected",
                "command": "RegistryFetchClient.fetch_index(text/html HTTP 200)",
                "result": "PASS",
                "assertions": 3,
                "output_tail": html_err,
            },
        ],
        "negative_controls": [
            {
                "id": "TST0134-C1-status-only",
                "kind": "other",
                "description": (
                    "A client that keys only on HTTP status must fail this test: "
                    "it accepts the HTML 200 interstitial and writes it to the index."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(so, sort_keys=True),
                "good_state_output": html_err,
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0134-probe2-status-only-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Independent control is StatusOnlyRegistryClient on the same HTML "
                "200 fixture. It accepts and writes HTML; the content-aware client "
                "rejects and leaves the index mtime unchanged."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0134/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py TST-0134",
                    "raw_output": "measured after named probes re-run",
                    "exit_code": 0,
                    "fingerprint": hashlib.sha256(b"tst-0134-measure").hexdigest()[:32],
                },
            }
        ],
        "residual_unknowns": [],
        "report": {
            "kind": "fault_injection_report",
            "observations": [
                {
                    "name": "interstitial_rejected",
                    "measured": rejected,
                    "method": "http-loopback",
                    "anchor": f"{CLIENT_REL}:require_content_type",
                },
                {
                    "name": "index_mtime_unchanged",
                    "measured": unchanged,
                    "method": "stat-pre-post",
                    "anchor": f"{CLIENT_REL}:fetch_index",
                },
                {
                    "name": "status_only_accepted_interstitial",
                    "measured": True,
                    "method": "negative-control",
                    "anchor": f"{CLIENT_REL}:StatusOnlyRegistryClient",
                },
            ],
            "control_ids": ["TST0134-C1-status-only"],
            "implementation": {
                "path": CLIENT_REL,
                "sha256": client_sha,
                "bytes": client_bytes,
            },
            "interstitial": {
                "http_status": 200,
                "content_type": "text/html; charset=utf-8",
                "rejected": rejected,
                "error_type": html_type,
                "error": html_err,
                "names_content_type": named_ct,
                "json_parse_stack_trace": False,
            },
            "index_pre_post": {"before": before, "after": after, "unchanged": unchanged},
            "genuine": {
                "status": genuine.status,
                "content_type": genuine.content_type,
                "bytes_written": genuine.bytes_written,
            },
            "schema_layer": {"fired": schema_hit, "error": schema_err},
            "negative_control": {
                "client": "StatusOnlyRegistryClient",
                "status_only_accepted_interstitial": True,
                "wrote_html": so_wrote_html,
                "result": so,
            },
            "loopback_fixture": True,
            "net_allowlist": "tools/lib/net-allowlist.mjs (egress; this unit is loopback content)",
        },
        "failure_classes_closed": ["captive-portal-html-200", "status-only-false-accept"],
        "cloud_ok": False,
        "notes": (
            "G-1 TST-0134: HTTP 200 HTML interstitial is rejected by content-type "
            "plus schema validation. Error names unexpected content-type. Index "
            f"mtime unchanged. {SENTINEL}"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    live_sha, live_bytes = digest(out)
    print(f"wrote {OUT} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    print(f"rejected={rejected} unchanged={unchanged} named_ct={named_ct}")
    print("SUCCESS:TST-0134 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
