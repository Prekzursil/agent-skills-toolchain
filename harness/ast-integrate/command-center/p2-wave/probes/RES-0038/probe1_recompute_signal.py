#!/usr/bin/env python3
"""Probe 1: recompute client-verifiable signals; both-states mutants."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recompute as R  # noqa: E402

ART = REPO / "command-center/research/RES-0038.json"


def fail(why: str) -> int:
    print(f"FAILED:RES-0038-probe1 {why}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    got = R.from_captures()
    npm = got["npm_mcpName_ownership"]
    dns = got["dns_apex_mcp_txt"]
    gh = got["github_namespace_repo_owner_consistency"]
    allow = got["npm_registry_base_url_allowlist"]
    print(
        "capture_recompute "
        f"npm={npm.get('match')} dns={dns.get('match')} "
        f"gh={gh.get('match')} allow={allow.get('match')}"
    )
    if not npm.get("match"):
        return fail("npm-mcpName-mismatch-on-good-captures")
    if not dns.get("match"):
        return fail("dns-txt-mismatch-on-good-captures")
    if not gh.get("match"):
        return fail("github-owner-mismatch-on-good-captures")
    if not allow.get("match"):
        return fail("allowlist-mismatch-on-good-captures")

    server = R.load_json(R.CAP / "brave-server-detail.json")
    npm_doc = R.load_json(R.CAP / "brave-npm-2.1.3.json")
    evil = copy.deepcopy(npm_doc)
    evil["mcpName"] = "io.github.evil/forge"
    bad = R.npm_mcpname(server, evil)
    print(f"mutant_mcpName match={bad.get('match')} mcpName={bad.get('npm_mcpName')}")
    if bad.get("match"):
        return fail("mutant-mcpName-still-matched")

    live_pulse = R.live_dig_txt("pulsemcp.com")
    print(f"live_dns_pulsemcp rc={live_pulse.get('exit_code')} n={len(live_pulse.get('records') or [])}")
    if not live_pulse.get("ok"):
        return fail("live-dig-pulsemcp-failed")
    live_dns = R.dns_mcp_txt(
        live_pulse["records"],
        "pulsemcp.com",
        str((R.load_json(R.CAP / "pulsemcp-server-detail.json").get("server") or {}).get("name") or ""),
    )
    print(f"live_dns_match={live_dns.get('match')} parsed={live_dns.get('parsed')}")
    if not live_dns.get("match"):
        return fail("live-dns-vMCPv1-absent")
    captured_p = (dns.get("parsed") or [{}])[0].get("p")
    live_p = (live_dns.get("parsed") or [{}])[0].get("p")
    if captured_p and live_p and captured_p != live_p:
        print(f"WARN key-rotated captured_p={captured_p[:12]} live_p={live_p[:12]}")
        # still a live MCP TXT; rotation is allowed, match stays true

    live_ex = R.live_dig_txt("example.com")
    ex_dns = R.dns_mcp_txt(
        live_ex.get("records") or [],
        "example.com",
        "com.example/does-not-exist",
    )
    print(
        f"negative_dns_example.com match={ex_dns.get('match')} "
        f"mcp_txt={ex_dns.get('mcp_txt_present')} "
        f"domain_ok={ex_dns.get('domain_matches_namespace')}"
    )
    if not ex_dns.get("domain_matches_namespace"):
        return fail("example.com-namespace-not-recognized")
    if ex_dns.get("match") or ex_dns.get("mcp_txt_present"):
        return fail("example.com-unexpectedly-has-vMCPv1")

    rec = doc.get("recomputed_signal") or {}
    if rec.get("signal_id") != "npm_mcpName_ownership" or rec.get("outcome") != "MATCH":
        return fail("artifact-recomputed_signal-stale")
    if rec.get("computed_not_asserted") is not True:
        return fail("artifact-recomputed-asserted-not-computed")
    detail = rec.get("detail") or {}
    if detail.get("npm_mcpName") != npm.get("npm_mcpName"):
        return fail("artifact-detail-diverged-from-captures")

    print("SUCCESS:RES-0038-probe1 mcpName+dns recomputed both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
