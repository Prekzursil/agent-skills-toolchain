#!/usr/bin/env python3
"""Probe 1: plant .git and a canary credential; both excluded and the build fails loudly.

Both-states: the same packer accepts the clean candidate stage (positive control).
Silent omission of either plant is a detector failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import packer as P  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0080.json"
CEILING = 5 * 1024 * 1024


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0080-probe1 {msg}")
    return 1


def pack_clean(stage: Path) -> dict:
    P.stage_candidate(stage, REPO)
    return P.pack_stage(
        stage,
        list(P.CANDIDATE_GLOBS),
        CEILING,
        package_id="a2-typed-registry-pack",
        repo_root=REPO,
    )


def pack_planted(stage: Path) -> dict:
    P.stage_candidate(stage, REPO)
    git = stage / ".git" / "config"
    git.parent.mkdir(parents=True, exist_ok=True)
    git.write_text("[core]\n\trepositoryformatversion = 0\n", encoding="utf-8")
    cred = stage / "secrets" / "planted.credentials"
    cred.parent.mkdir(parents=True, exist_ok=True)
    cred.write_text(
        "CANARY_CREDENTIAL_ARC0080=planted-not-a-real-secret\n",
        encoding="utf-8",
    )
    return P.pack_stage(
        stage,
        list(P.CANDIDATE_GLOBS),
        CEILING,
        package_id="a2-typed-registry-pack",
        repo_root=REPO,
    )


def main() -> int:
    if not ART.is_file():
        return _fail("contract missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0080" not in text:
        return _fail("sentinel absent from contract")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="arc0080-p1-clean-") as td:
        clean = pack_clean(Path(td))
    clean.pop("_zip_bytes", None)
    print(
        f"clean verdict={clean['verdict']} members={clean['integrity']['member_count']} "
        f"failures={len(clean['failures'])}"
    )
    if clean["verdict"] != "accept" or clean["failures"]:
        return _fail(f"positive control rejected: {clean.get('failures')}")
    if clean["integrity"]["member_count"] != len(P.CANDIDATE_PATHS):
        return _fail("clean member count != candidate file count")
    if not clean["reproducibility"]["repeat_digest_agrees"]:
        return _fail("clean repeat digest disagrees")

    with tempfile.TemporaryDirectory(prefix="arc0080-p1-bad-") as td:
        planted = pack_planted(Path(td))
    zip_bytes = planted.pop("_zip_bytes", None)
    print(
        f"planted verdict={planted['verdict']} members={planted['integrity']['member_count']} "
        f"failures={len(planted['failures'])} zip={zip_bytes is not None}"
    )
    if planted["verdict"] != "reject":
        return _fail("planted stage was accepted — silent omit or missing gate")
    if zip_bytes is not None:
        return _fail("reject still emitted an archive")

    fail_paths = {f.get("path") for f in planted["failures"]}
    fail_classes = {f.get("class") for f in planted["failures"]}
    print(f"fail_paths={sorted(fail_paths)}")
    print(f"fail_classes={sorted(c for c in fail_classes if c)}")
    if ".git/config" not in fail_paths:
        return _fail("planted .git/config not named in failures")
    if "secrets/planted.credentials" not in fail_paths:
        return _fail("planted canary credential not named in failures")
    if "git" not in fail_classes:
        return _fail("git exclusion class did not fire")
    if "credentials" not in fail_classes:
        return _fail("credentials exclusion class did not fire")

    member_paths = {m["path"] for m in planted["members"]}
    if ".git/config" in member_paths or "secrets/planted.credentials" in member_paths:
        return _fail("planted path present in members — not excluded")

    print("both_states clean=accept planted=reject")
    print("SUCCESS:ARC-0080-probe1 exclusion control .git+credential fail-loud")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
