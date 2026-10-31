#!/usr/bin/env python3
"""IMP-0008 probe1: synthetic below-floor negotiation + fail-closed controls.

Rebuilt 2026-10-26 (shard-6 wave-4 resume): the original probe was lost with
the mid-flight host death; this re-derivation anchors on the same receipt.

Signal 1 (evidence_requirement): negotiate()'s verdict for a synthetic
below-floor client version, with the refusal message naming the exact
required version, and preflight_install writing no destination payload.

Negative control: an unparsable version string must FAIL CLOSED (refuse),
never default to compatible. A fail-open mutant must diverge on that input
and stay identical on parseable inputs.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from client_negotiate import load_manifest, negotiate, preflight_install  # noqa: E402


def main() -> int:
    manifest = load_manifest(REPO / ".claude-plugin" / "plugin.json")
    floor = str(manifest.get("min_client_version"))
    facts: dict = {
        "unit_id": "IMP-0008",
        "probe": "probe1-below-floor",
        "manifest_source": ".claude-plugin/plugin.json",
        "manifest_top_level_min_client_version_present": "min_client_version" in json.loads(
            (REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        ),
        "manifest_compatibility_block": json.loads(
            (REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        ).get("compatibility"),
        "floor": floor,
        "supported_clients": manifest.get("supported_clients"),
    }
    checks: list[dict] = []

    def chk(name: str, ok: bool) -> bool:
        checks.append({"check": name, "ok": bool(ok)})
        return bool(ok)

    # Below-floor synthetic.
    below = negotiate(manifest, "claude-code", "0.0.1")
    chk("below_floor_refused", (not below.allowed) and below.reason == "below-floor")
    chk("refusal_names_exact_required_version", floor in below.message and "0.0.1" in below.message)

    # At-floor and above-floor allowed; prerelease parses at its release tuple.
    at = negotiate(manifest, "claude-code", "1.0.0")
    above = negotiate(manifest, "claude-code", "2.1.310")
    pre = negotiate(manifest, "claude-code", "1.0.0-rc.1")
    chk("at_floor_allowed", at.allowed and at.reason == "ok")
    chk("above_floor_allowed", above.allowed)
    chk("prerelease_parses_at_release_tuple", pre.parsed_version == "1.0.0" and pre.allowed)

    # Unparsable must fail closed.
    unparsable = negotiate(manifest, "claude-code", "not-a-version-at-all")
    chk("unparsable_fail_closed", (not unparsable.allowed) and unparsable.reason == "unparsable-version")
    chk("unparsable_refusal_names_floor", floor in unparsable.message)

    # Refused install writes no destination payload.
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "dest"
        res = preflight_install(dest, manifest, "claude-code", "0.0.1", write=True)
        chk("refused_install_writes_nothing", (not res["allowed"]) and (not res["installed"]) and (not dest.exists()))
        ok_dest = Path(td) / "ok-dest"
        res_ok = preflight_install(ok_dest, manifest, "claude-code", "2.0.0", write=True)
        chk("allowed_install_writes_payload", res_ok["allowed"] and res_ok["installed"] and ok_dest.is_dir())

    # Negative control: a fail-open mutant negotiate (identical to production
    # except unparsable -> allowed) must DIVERGE on the unparsable input and
    # AGREE with production on every parseable input (silent on good state).
    def mutant_negotiate(manifest_, client_id, offered):
        n = negotiate(manifest_, client_id, offered)
        if n.reason == "unparsable-version":
            return dataclasses.replace(n, allowed=True, reason="mutant-fail-open")
        return n

    m_unparsable = mutant_negotiate(manifest, "claude-code", "not-a-version-at-all")
    m_below = mutant_negotiate(manifest, "claude-code", "0.0.1")
    m_at = mutant_negotiate(manifest, "claude-code", "1.0.0")
    chk("mutant_diverges_on_unparsable_fired", m_unparsable.allowed != unparsable.allowed)
    chk("mutant_agrees_parseable_silent", m_below.allowed == below.allowed and m_at.allowed == at.allowed)

    facts["negotiations"] = {
        "below_floor_0.0.1": {"allowed": below.allowed, "reason": below.reason, "message": below.message},
        "at_floor_1.0.0": {"allowed": at.allowed, "reason": at.reason},
        "above_floor_2.1.310": {"allowed": above.allowed, "reason": above.reason},
        "prerelease_1.0.0-rc.1": {"allowed": pre.allowed, "parsed": pre.parsed_version},
        "unparsable": {"allowed": unparsable.allowed, "reason": unparsable.reason, "message": unparsable.message},
    }
    facts["checks"] = checks
    facts["all_ok"] = all(c["ok"] for c in checks)
    print(json.dumps(facts, indent=1))
    if not facts["all_ok"]:
        print("FAILED:IMP-0008-probe1 below-floor or fail-closed control failed")
        return 1
    print("SUCCESS:IMP-0008-probe1 below-floor refused; message names required version; fail-closed holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
