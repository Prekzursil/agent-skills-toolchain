#!/usr/bin/env python3
"""TST-0221 probe A: live mkt health-check names the revoked coordinate.

Signal (a): after an upstream revocation of hello-skill@1.0.0, the health check
flags hello-skill@1.0.0 WITHOUT any manual refresh, and does NOT flag
hello-skill@1.1.0 installed in a second site. Both-states control: the same
site checks CLEAN before the revocation. Exact-set oracle: exit 0 only when
the flags equal exactly {hello-skill@1.0.0}; the oracle is red-capable - the
same comparison with the revoked coordinate omitted exits 1.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "marketplace"))

from mkt import fixture, install as inst_mod, moderation  # noqa: E402

WORK = HERE / "fixtures" / "health"


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    built = fixture.build(WORK)
    registry_root = Path(built["registry_root"])
    policy = fixture.trust_policy()
    secret, _ = fixture.keys_for("pub:registry-root")  # list must be co-signed by an active registry-maintainer key

    site_a = WORK / "site-a"
    site_b = WORK / "site-b"
    inst_a = inst_mod.Installer(registry_root, site_a, policy)
    inst_b = inst_mod.Installer(registry_root, site_b, policy)
    inst_a.install("hello-skill", "=1.0.0")
    inst_b.install("hello-skill", "=1.1.0")

    health_pre = inst_a.health_check()
    pre_clean = health_pre["code"] == "CLEAN" and health_pre["flags"] == []

    moderation.revoke(
        registry_root,
        scope={"kind": "version", "name": "hello-skill", "version": "1.0.0"},
        reason="probe A upstream revocation (TST-0221)",
        severity="critical",
        authority="pub:registry-root",
        maintainer_secret_hex=secret,
    )

    # NO manual refresh: the same Installer object re-reads the registry.
    health_post_a = inst_a.health_check()
    health_post_b = inst_b.health_check()
    flags_a = [f["package"] for f in health_post_a["flags"]]
    flags_b = [f["package"] for f in health_post_b["flags"]]

    def exact_set_oracle(flags: list[str]) -> bool:
        return sorted(flags) == ["hello-skill@1.0.0"]

    oracle_green = exact_set_oracle(flags_a)
    oracle_red_when_omitted = not exact_set_oracle([f for f in flags_a if f != "hello-skill@1.0.0"]) and flags_a != []

    checks = {
        "both_states_control_nonrevoked_not_flagged": pre_clean is True,
        "health_output_names_revoked_coordinate": flags_a == ["hello-skill@1.0.0"],
        "other_version_not_flagged": "hello-skill@1.1.0" not in flags_a and flags_b == [],
        "no_manual_refresh_needed": health_post_a["revocations_considered"] >= 1,
        "exact_set_oracle_green": oracle_green is True,
        "exact_set_oracle_red_capable": oracle_red_when_omitted is True,
    }
    out = {
        "probe": "probe_a_health",
        "unit": "TST-0221",
        "pre_revocation": {"code": health_pre["code"], "flags": health_pre["flags"]},
        "post_revocation_site_a": {"code": health_post_a["code"], "flags": flags_a},
        "post_revocation_site_b": {"code": health_post_b["code"], "flags": flags_b},
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe-a-health-check.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(WORK, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
