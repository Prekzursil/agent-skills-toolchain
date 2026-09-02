"""Generate self-contained replication packages from the P0/P1 census."""
from __future__ import annotations

import shutil
from pathlib import Path

from common import PACKAGES, dump_json
from extract import write_input
import toolchain as T
import verify_claim as V


def one_command(claim_id: str) -> str:
    rel_pkg = f"command-center/p2-wave/probes/CNF-0182/packages/{claim_id}"
    return (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0182/run_one.py "
        f"--package {rel_pkg}"
    )


def build_one(claim: dict, dest_root: Path | None = None) -> dict:
    cid = str(claim["claim_id"])
    pkg_dir = (dest_root or PACKAGES) / cid
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    pkg_dir.mkdir(parents=True)
    inp = write_input(pkg_dir, claim)
    pin_mm = T.pin_major_minor()
    pkg = {
        "package_id": f"pkg-{cid}",
        "claim_id": cid,
        "severity": claim["severity"],
        "statement": claim["statement"],
        "check_type": claim["check_type"],
        "expect": claim["expect"],
        "confirmation_record": claim.get("confirmation_record") or "NOT-CHECKED",
        "pinned_toolchain": [
            {
                "tool": "python3",
                "version": pin_mm,
                "invoke": "python3 --version",
            }
        ],
        "inputs": [inp],
        "commands": [one_command(cid)],
        "expected_outputs": [
            {
                "id": "verdict",
                "path": "expected/verdict.json",
                "normalizer": "json-stable",
            }
        ],
        "normalizers": ["json-stable", "timestamp", "abs-path"],
        "pass_criterion": "exit_code==0 and normalized actual.holds==true and bytes match expected/verdict.json",
        "one_command": one_command(cid),
        "credentials": {
            "bundled": False,
            "runtime_inject": list(claim.get("runtime_inject") or []),
        },
    }
    verdict = V.evaluate(pkg, pkg_dir)
    if not verdict.get("holds"):
        raise RuntimeError(f"{cid} does not hold at authoring: {verdict}")
    dump_json(pkg_dir / "expected" / "verdict.json", verdict)
    dump_json(pkg_dir / "PACKAGE.json", pkg)
    return pkg


def generate(claims: list[dict]) -> list[dict]:
    staging = PACKAGES.parent / "_packages_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    packages = []
    try:
        for claim in claims:
            if not claim.get("check_type"):
                raise RuntimeError(
                    f"claim {claim.get('claim_id')} lacks check_type; cannot emit a runnable package"
                )
            packages.append(build_one(claim, dest_root=staging))
        if PACKAGES.exists():
            shutil.rmtree(PACKAGES)
        staging.rename(PACKAGES)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return packages
