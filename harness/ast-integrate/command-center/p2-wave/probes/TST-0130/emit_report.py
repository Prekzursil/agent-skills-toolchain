#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0130.json (security_report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
from matrix import run_all  # noqa: E402

OUT = "command-center/receipts/TST-0130.json"
QUESTION = (
    "With an expired / wrong-CN certificate presented by the registry endpoint, "
    "does the client refuse the connection outright? PASS requires: no plaintext "
    "HTTP retry on any port, no `--insecure` equivalent reachable from config, "
    "and no silent substitution of a cached index for the refused fetch."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0130/probe1_tls_refuse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0130/probe2_insecure_parse.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    report = run_all()
    if not report["all_pass"]:
        print("FAILED:TST-0130 emit matrix not all_pass")
        print(json.dumps(
            {
                "tls_pass": report["tls_pass"],
                "parse_pass": report["parse_pass"],
                "audit_pass": report["audit_pass"],
                "tls_cases": {
                    k: {"pass": v["pass"], "problems": v.get("problems")}
                    for k, v in report["tls"]["cases"].items()
                },
                "parse_cases": {
                    k: {"pass": v["pass"], "problems": v.get("problems")}
                    for k, v in report["parse"]["cases"].items()
                },
                "audit": report["audit"],
            },
            indent=2,
            default=str,
        )[:4000])
        return 1

    tls = report["tls"]
    wrong = tls["cases"]["wrong_cn"]
    expired = tls["cases"]["expired"]
    valid = tls["cases"]["valid_both_states"]
    mutant = tls["cases"]["unverified_mutant_would_pass"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    client_rel = "tools/lib/registry_fetch.py"
    allow_rel = "tools/lib/net_allowlist.py"
    allow_js = "tools/lib/net-allowlist.mjs"
    client_sha, client_bytes = sha256_file(REPO / client_rel)

    claims = [
        {
            "id": "C1",
            "claim": (
                "Wrong-CN and expired certificates on the registry fixture are "
                "refused with classification tls-handshake-failure and a non-zero exit."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{client_rel}:_https_get",
        },
        {
            "id": "C2",
            "claim": (
                "A passive socket.create_connection capture records no second "
                "connection to an http:// scheme or port 80 after the refused handshake."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/TST-0130/capture.py",
        },
        {
            "id": "C3",
            "claim": (
                "The cached index is byte-for-byte unchanged and dest is not written "
                "when the handshake is refused (no silent cache substitution)."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{client_rel}:fetch_bytes",
        },
        {
            "id": "C4",
            "claim": (
                "Both-states: a valid certificate on the same fixture endpoint "
                "fetches the index with classification ok and exit 0."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/TST-0130/probe1_tls_refuse.py",
        },
        {
            "id": "C5",
            "claim": (
                "A config that sets insecure-TLS / --insecure / tls_verify=false is "
                "rejected at parse time before any socket is opened."
            ),
            "verdict": "CONFIRMED",
            "anchor": f"{allow_rel}:inspect_config_keys",
        },
    ]

    tests = [
        {
            "id": "TST0130-T1-WRONG-CN",
            "name": "Wrong-CN certificate is refused; dest unwritten; cache unchanged.",
            "result": "PASS",
            "classification": wrong["classification"],
            "exit_code": wrong["exit_code"],
            "capture": wrong["capture"],
        },
        {
            "id": "TST0130-T2-EXPIRED",
            "name": "Expired certificate is refused with the same classification.",
            "result": "PASS",
            "classification": expired["classification"],
            "exit_code": expired["exit_code"],
            "capture": expired["capture"],
        },
        {
            "id": "TST0130-T3-BOTH-STATES-VALID",
            "name": "Valid certificate on the same fixture endpoint fetches the index.",
            "result": "PASS",
            "classification": valid["classification"],
            "exit_code": valid["exit_code"],
        },
        {
            "id": "TST0130-T4-NO-PLAINTEXT-RETRY",
            "name": "Passive capture shows no port-80 / HTTP-trap connect after refuse.",
            "result": "PASS",
            "http_trap_hits": wrong["http_trap_hits"],
            "port80_bound": tls["port80_bound"],
        },
        {
            "id": "TST0130-T5-INSECURE-PARSE",
            "name": "insecure-TLS config keys are rejected at parse time.",
            "result": "PASS",
            "command": P2,
        },
        {
            "id": "TST0130-T6-UNVERIFIED-MUTANT",
            "name": "An unverified SSL context still connects to the wrong-CN fixture (detector control).",
            "result": "PASS",
            "mutant_ok": mutant["mutant_ok"],
        },
    ]

    evidence = [
        {
            "kind": "client-exit-classification",
            "signal": "a",
            "wrong_cn": {
                "classification": wrong["classification"],
                "exit_code": wrong["exit_code"],
                "error": wrong["error"],
            },
            "expired": {
                "classification": expired["classification"],
                "exit_code": expired["exit_code"],
                "error": expired["error"],
            },
        },
        {
            "kind": "passive-connection-capture",
            "signal": "b",
            "wrong_cn_attempts": wrong["capture"],
            "expired_attempts": expired["capture"],
            "http_trap_hits": wrong["http_trap_hits"],
            "port80_connects": False,
        },
        {
            "kind": "cache-bytes",
            "cache_sha_before": wrong["cache_sha_before"],
            "cache_sha_after": wrong["cache_sha_after"],
            "dest_exists_on_refuse": wrong["dest_exists"],
        },
        {
            "kind": "client-source",
            "path": client_rel,
            "sha256": client_sha,
            "bytes": client_bytes,
        },
    ]

    artifacts = [
        {"path": OUT, "role": "primary", "exists": True},
        {"path": client_rel, "role": "client", "exists": True},
        {"path": allow_rel, "role": "allowlist-python", "exists": True},
        {"path": allow_js, "role": "allowlist-js", "exists": True},
    ]

    doc = {
        "unit_id": "TST-0130",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0130",
        "report_kind": "security_report",
        "profile": "security-report-tls-no-downgrade",
        "phase": "10",
        "title": "TLS handshake failure must not downgrade to plaintext",
        "question": QUESTION,
        "answer": (
            "Yes. The live registry fetch client refuses expired and wrong-CN "
            "certificates outright (classification tls-handshake-failure, exit 11). "
            "A socket.create_connection capture records a single TCP connect to the "
            "TLS fixture port and zero connects to port 80 or the plaintext HTTP trap. "
            "The on-disk cached index is unchanged and dest is not written. A valid "
            "certificate on the same fixture endpoint succeeds (both-states). Config "
            "keys that would disable TLS verification are rejected at parse time. "
            "An unverified SSL mutant still connects to the wrong-CN fixture, so the "
            "refusal is verification rather than a dead server."
        ),
        "target_contract_pass": True,
        "completion_sentinel": "SUCCESS:TST-0130",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "client": {
            "path": client_rel,
            "sha256": client_sha,
            "bytes": client_bytes,
            "note": (
                "B07 registry HTTPS client was absent as a socket-opening fetch path "
                "(tools/marketplace/registry.py never opens a socket). This unit "
                "ships tools/lib/registry_fetch.py as the live index + package GET "
                "client under test, gated by tools/lib/net-allowlist.mjs / "
                "tools/lib/net_allowlist.py."
            ),
        },
        "claims": claims,
        "tests": tests,
        "evidence": evidence,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "tls-refuse-and-capture"},
            {"id": "probe2", "command": P2, "role": "insecure-parse-and-static-audit"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0130-probe2-insecure-parse-static-audit",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Probe 2 does not start TLS servers. It re-parses insecure configs "
                "and greps the client/allowlist sources for live CERT_NONE / "
                "unverified-context calls."
            ),
        },
        "artifacts": artifacts,
        "ts": now,
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0130")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
