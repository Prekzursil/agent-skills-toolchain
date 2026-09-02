#!/usr/bin/env python3
"""Probe 2: sequential install census (IMP-0126 signal 2).

Installs the first package into a throwaway HOME, then attempts the
conflicting second package. The guard must refuse and name both
claimants; a post-refuse census must be byte-identical to the pre-attempt
census. The counterfactual (guard off, case-insensitive placement) must
overwrite the first package's file — proving the conflict is real, not
theoretical.

NEGATIVE CONTROL in the same run: two disjoint packages both install.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.fixtures import (  # noqa: E402
    ALPHA_UNIQUE,
    CONFLICT_LIVE_REL,
    GAMMA_HOOK,
    GAMMA_SKILL,
    PKG_ALPHA,
    PKG_BETA_CASEFOLD,
    PKG_DELTA_EXACT,
    PKG_GAMMA_DISJOINT,
)
from marketplace.install import InstallRefused, Ledger, census, install  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0126.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0126-probe2 {msg}")
    return 1


def main() -> int:
    alpha_readme = PKG_ALPHA["payload"]["skills/shared/README.md"]
    beta_readme = PKG_BETA_CASEFOLD["payload"]["skills/shared/readme.md"]
    delta_readme = PKG_DELTA_EXACT["payload"]["skills/shared/README.md"]
    alpha_sha = _sha(alpha_readme)
    beta_sha = _sha(beta_readme)
    delta_sha = _sha(delta_readme)
    if alpha_sha == beta_sha or alpha_sha == delta_sha:
        return _fail("fixture bytes are not distinct; overwrite would be invisible")

    with tempfile.TemporaryDirectory(prefix="imp0126-p2-guard-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        before = census(home)
        if before.get(CONFLICT_LIVE_REL) != alpha_sha:
            return _fail("alpha live file sha mismatch after first install")
        try:
            install(
                PKG_BETA_CASEFOLD["id"],
                PKG_BETA_CASEFOLD["payload"],
                home,
                ledger,
                guard=True,
            )
        except InstallRefused as exc:
            named = {n for c in exc.conflicts for n in c.named_packages()}
            refuse_text = str(exc)
            if named != {PKG_ALPHA["id"], PKG_BETA_CASEFOLD["id"]}:
                return _fail(f"guard named={named}")
            if PKG_ALPHA["id"] not in refuse_text or PKG_BETA_CASEFOLD["id"] not in refuse_text:
                return _fail(f"refuse text missing claimant: {refuse_text}")
            print(f"guard_refused named={sorted(named)}")
            print(f"  {refuse_text}")
        else:
            return _fail("casefold pair was not refused")
        after_refuse = census(home)
        if after_refuse != before:
            return _fail("census mutated after refused install")
        if PKG_BETA_CASEFOLD["id"] in ledger.package_ids():
            return _fail("refused package recorded in ledger")

        try:
            install(
                PKG_DELTA_EXACT["id"],
                PKG_DELTA_EXACT["payload"],
                home,
                ledger,
                guard=True,
            )
        except InstallRefused as exc:
            named_d = {n for c in exc.conflicts for n in c.named_packages()}
            if PKG_ALPHA["id"] not in named_d or PKG_DELTA_EXACT["id"] not in named_d:
                return _fail(f"exact pair named={named_d}")
            print(f"exact_pair_refused named={sorted(named_d)}")
        else:
            return _fail("exact conflicting pair was not refused")
        if census(home) != before:
            return _fail("census mutated after exact-pair refuse")

    with tempfile.TemporaryDirectory(prefix="imp0126-p2-overwrite-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        pre = census(home)
        result = install(
            PKG_BETA_CASEFOLD["id"],
            PKG_BETA_CASEFOLD["payload"],
            home,
            ledger,
            guard=False,
            case_insensitive=True,
        )
        post = census(home)
        if CONFLICT_LIVE_REL not in result.overwritten_live_rels:
            return _fail(f"counterfactual did not overwrite {CONFLICT_LIVE_REL}")
        if post.get(CONFLICT_LIVE_REL) != beta_sha:
            return _fail(
                f"counterfactual sha={post.get(CONFLICT_LIVE_REL)} want={beta_sha}"
            )
        if post[CONFLICT_LIVE_REL] == pre[CONFLICT_LIVE_REL]:
            return _fail("counterfactual census shows no overwrite")
        if post.get(ALPHA_UNIQUE) != pre.get(ALPHA_UNIQUE):
            return _fail("counterfactual mutated a non-conflicting alpha file")
        print(
            f"counterfactual overwritten={list(result.overwritten_live_rels)} "
            f"sha {pre[CONFLICT_LIVE_REL][:12]} -> {post[CONFLICT_LIVE_REL][:12]}"
        )

    with tempfile.TemporaryDirectory(prefix="imp0126-p2-disjoint-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        install(
            PKG_GAMMA_DISJOINT["id"],
            PKG_GAMMA_DISJOINT["payload"],
            home,
            ledger,
            guard=True,
        )
        snap = census(home)
        if ALPHA_UNIQUE not in snap or GAMMA_SKILL not in snap or GAMMA_HOOK not in snap:
            return _fail(f"disjoint census missing files {sorted(snap)}")
        if snap[ALPHA_UNIQUE] != _sha(PKG_ALPHA["payload"]["skills/alpha/SKILL.md"]):
            return _fail("alpha unique file corrupted in disjoint install")
        if snap[GAMMA_SKILL] != _sha(PKG_GAMMA_DISJOINT["payload"]["skills/gamma/SKILL.md"]):
            return _fail("gamma file sha mismatch")
        if set(ledger.package_ids()) != {PKG_ALPHA["id"], PKG_GAMMA_DISJOINT["id"]}:
            return _fail(f"disjoint ledger={ledger.package_ids()}")
        print("negative_control disjoint_install_ok=True")

    if not ART.is_file():
        return _fail("receipt missing")
    blob = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0126" not in blob:
        return _fail("sentinel absent")

    print(
        json.dumps(
            {
                "probe": "probe2-sequential-census",
                "unit_id": "IMP-0126",
                "guard_refused": True,
                "census_unchanged_after_refuse": True,
                "counterfactual_overwrote": True,
                "disjoint_negative_control": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0126-probe2 sequential install census and overwrite counterfactual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
