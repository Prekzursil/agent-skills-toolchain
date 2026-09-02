"""Both-states falsifiability scenario for ARC-0023.

Working local marketplace: install, upgrade, rollback, offline-from-export
succeed against a throwaway prefix. Broken marketplace (missing blob,
stripped signature) refuses. Public publish is BLOCKED under PR-ONLY.
Stopping condition 13 is UNSATISFIABLE-AS-WRITTEN. None of these steps
publish.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from market import FILES_V1, PKG, V1, V2, FixtureMarket, make_package, sha256_file

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "run"


def _reset(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_scenario() -> dict[str, Any]:
    root = _reset(FIX)
    working = FixtureMarket(root / "working-market")
    working.seed_working()
    prefix = _reset(root / "prefix")

    installed = working.install(PKG, V1, prefix)
    pin1 = working.pin(prefix, PKG)
    skill_v1 = (prefix / "packages" / PKG / "SKILL.md").read_text(encoding="utf-8")
    o_install = (
        installed.get("ok") is True
        and pin1 == V1
        and skill_v1 == FILES_V1["SKILL.md"]
    )

    upgraded = working.upgrade(PKG, prefix)
    pin2 = working.pin(prefix, PKG)
    skill_v2 = (prefix / "packages" / PKG / "SKILL.md").read_text(encoding="utf-8")
    o_upgrade = upgraded.get("ok") is True and pin2 == V2 and skill_v2 != skill_v1

    rolled = working.rollback(PKG, prefix)
    pin3 = working.pin(prefix, PKG)
    skill_v3 = (prefix / "packages" / PKG / "SKILL.md").read_text(encoding="utf-8")
    o_rollback = (
        rolled.get("ok") is True
        and pin3 == V1
        and skill_v3 == skill_v1
    )

    export_dir = working.export_to(root / "export")
    offline_prefix = _reset(root / "offline-prefix")
    offline_market = FixtureMarket(export_dir)
    offline = offline_market.install(PKG, V1, offline_prefix)
    o_offline = (
        offline.get("ok") is True
        and offline_market.pin(offline_prefix, PKG) == V1
    )

    broken = FixtureMarket(root / "broken-missing-blob")
    broken.seed_missing_blob(working)
    broken_prefix = _reset(root / "broken-prefix")
    missing = broken.install(PKG, V1, broken_prefix)
    o_missing = missing.get("ok") is not True and missing.get("refused") is True

    unsigned_root = root / "unsigned-market"
    if unsigned_root.exists():
        shutil.rmtree(unsigned_root)
    shutil.copytree(working.root, unsigned_root)
    unsigned_market = FixtureMarket(unsigned_root)
    blob = unsigned_root / f"blobs/{PKG}-{V1}.json"
    pkg = json.loads(blob.read_text(encoding="utf-8"))
    pkg["signature"] = "stripped"
    blob.write_text(json.dumps(pkg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    idx = unsigned_market.index()
    idx["packages"][PKG]["versions"][V1]["sha256"] = sha256_file(blob)
    (unsigned_root / "index.json").write_text(
        json.dumps(idx, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    unsigned_prefix = _reset(root / "unsigned-prefix")
    unsigned = unsigned_market.install(PKG, V1, unsigned_prefix)
    o_unsigned = (
        unsigned.get("ok") is not True
        and unsigned.get("refused") is True
        and unsigned.get("error") == "signature-verification-failed"
    )

    pub = working.publish_public(make_package(PKG, V1, FILES_V1))
    o_publish_blocked = (
        pub.get("ok") is False
        and pub.get("blocked") is True
        and pub.get("code") == "BLOCKED-PR-ONLY"
    )

    cond = working.canary_succeeds()
    o_cond13 = cond.get("verdict") == "UNSATISFIABLE-AS-WRITTEN" and cond.get("ok") is False

    pr = working.propose_pr(root / "pr-artifact", make_package(PKG, V1, FILES_V1))
    o_pr = pr.get("ok") is True and pr.get("index_unchanged") is True

    ids = []
    flags = {
        "O1-working-install-pin": o_install,
        "O2-working-upgrade-pin-changes": o_upgrade,
        "O3-working-rollback-restores": o_rollback,
        "O4-offline-install-from-export": o_offline,
        "O5-missing-blob-refuses": o_missing,
        "O6-unsigned-refuses": o_unsigned,
        "O7-publish-public-blocked-pr-only": o_publish_blocked,
        "O8-condition-13-unsatisfiable-as-written": o_cond13,
        "O9-propose-pr-index-unchanged": o_pr,
    }
    for key, fired in flags.items():
        if fired:
            ids.append(key)

    falsifiable = len(ids) >= 1
    # Distinguishes working from non-working without publishing: O1 vs O5.
    distinguishes = o_install and o_missing
    passed = (
        falsifiable
        and distinguishes
        and o_install
        and o_upgrade
        and o_rollback
        and o_offline
        and o_missing
        and o_unsigned
        and o_publish_blocked
        and o_cond13
        and o_pr
        and len(ids) == 9
    )
    return {
        "condition_13": cond,
        "distinguishes_working_from_broken_without_publish": distinguishes,
        "falsifiable_without_publish": falsifiable,
        "flags": flags,
        "observable_count": len(ids),
        "observable_ids": ids,
        "offline": {"ok": offline.get("ok"), "pin": offline_market.pin(offline_prefix, PKG)},
        "pass": passed,
        "prefix_pins": {"after_install": pin1, "after_rollback": pin3, "after_upgrade": pin2},
        "propose_pr": {
            "index_unchanged": pr.get("index_unchanged"),
            "ok": pr.get("ok"),
        },
        "publish_public": {
            "blocked": pub.get("blocked"),
            "code": pub.get("code"),
            "ok": pub.get("ok"),
        },
        "refused": {
            "missing_blob": {"error": missing.get("error"), "ok": missing.get("ok")},
            "unsigned": {"error": unsigned.get("error"), "ok": unsigned.get("ok")},
        },
        "working": {
            "install_ok": installed.get("ok"),
            "rollback_ok": rolled.get("ok"),
            "upgrade_ok": upgraded.get("ok"),
        },
    }


if __name__ == "__main__":
    import json as _json
    import sys as _sys

    _out = run_scenario()
    print(_json.dumps(_out, indent=2, sort_keys=True, default=str))
    _sys.exit(0 if _out.get("pass") else 1)
