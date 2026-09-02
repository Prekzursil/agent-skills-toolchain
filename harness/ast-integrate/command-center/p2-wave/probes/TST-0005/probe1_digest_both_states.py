#!/usr/bin/env python3
"""Probe 1: both-states for a plausible digest vs a real artifact.

test_digest_without_artifact_rejected
test_digest_with_artifact_accepted

A hand-written convincing sha256 prose is independently well-formed, then
fed to admit() against an absent contracted path. Fan-in must REJECT without
parsing the digest. The same digest shape against a live file whose sha256
matches must ACCEPT after existence-then-parse.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from fan_in.barrier import admit, digest_well_formed  # noqa: E402
import fixtures as F  # noqa: E402

RAW = HERE / "probe1-digest-both-states.raw.json"


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0005-probe1 {msg}")
    return 1


def matching_digest(path: Path, rel: str) -> str:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return (
        f"SUCCESS:present-control\n"
        f"path: {rel}\n"
        f"sha256: {digest}\n"
        f"bytes: {len(raw)}\n"
    )


def main() -> int:
    prose = F.load_convincing_digest()
    if not digest_well_formed(prose):
        return _fail("hand-written convincing digest is not well-formed")
    if "sha256:" not in prose.lower():
        return _fail("hand-written digest missing sha256 token")

    absent_root = REPO
    absent_rel = F.ABSENT_PATH
    if (absent_root / absent_rel).exists():
        return _fail(f"absent-oracle path unexpectedly exists: {absent_rel}")

    rejected = admit(absent_root, [absent_rel], prose)
    print(
        f"without_artifact status={rejected['status']} reason={rejected['reason_id']} "
        f"parsed={rejected['digest_parsed']} phases={rejected['phases']}"
    )
    if rejected["admitted"] or rejected["status"] != "REJECT":
        return _fail(f"convincing digest for absent path was admitted: {rejected}")
    if rejected["reason_id"] != "absent-artifact":
        return _fail(f"expected absent-artifact, got {rejected['reason_id']}")
    if rejected["digest_parsed"]:
        return _fail("digest was parsed although the artifact is absent")
    if rejected["phases"] != ["existence_check"]:
        return _fail(f"absent path phases {rejected['phases']} are not existence-only")
    if absent_rel not in rejected["message"]:
        return _fail("reject message did not name the absent path")

    with tempfile.TemporaryDirectory(prefix="tst0005-present-") as tmp:
        root = Path(tmp)
        rel = "command-center/receipts/TST-0005-present-control.json"
        live = root / rel
        live.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"unit_id": "TST-0005", "control": "present"}, indent=2) + "\n"
        live.write_text(body, encoding="utf-8")
        digest = matching_digest(live, rel)
        if not digest_well_formed(digest):
            return _fail("present-control digest is not well-formed")
        accepted = admit(root, [rel], digest)
        print(
            f"with_artifact status={accepted['status']} reason={accepted['reason_id']} "
            f"parsed={accepted['digest_parsed']} phases={accepted['phases']}"
        )
        if not accepted["admitted"] or accepted["status"] != "ACCEPT":
            return _fail(f"matching digest with live artifact was rejected: {accepted}")
        if not accepted["digest_parsed"]:
            return _fail("present artifact did not reach digest parse")
        if accepted["phases"] != ["existence_check", "digest_parse"]:
            return _fail(f"present phases {accepted['phases']}")
        live_sha = hashlib.sha256(live.read_bytes()).hexdigest()
        if accepted["live_sha256"] != live_sha or accepted["digest_sha256"] != live_sha:
            return _fail("accepted sha256 does not match live bytes")

        # Same well-formed prose, still-present file, but hash does not match:
        # existence passed, parse ran, mismatch is not an absent-path accept.
        mismatch = admit(root, [rel], prose)
        if mismatch["admitted"] or mismatch["reason_id"] != "digest-mismatch":
            return _fail(f"present+wrong-digest should mismatch, got {mismatch}")
        if not mismatch["digest_parsed"]:
            return _fail("mismatch path must parse after existence succeeds")

    doc = {
        "absent_path": absent_rel,
        "digest_without_artifact_rejected": True,
        "digest_with_artifact_accepted": True,
        "hand_written_digest_well_formed": True,
        "absent_digest_parsed": False,
        "present_digest_parsed": True,
        "pass": True,
        "probe": "probe1-digest-both-states",
        "unit_id": "TST-0005",
        "without_artifact": {
            "reason_id": rejected["reason_id"],
            "status": rejected["status"],
            "digest_parsed": rejected["digest_parsed"],
            "phases": rejected["phases"],
        },
        "with_artifact": {
            "reason_id": accepted["reason_id"],
            "status": accepted["status"],
            "digest_parsed": accepted["digest_parsed"],
            "phases": accepted["phases"],
        },
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("both-states reject-absent/accept-present")
    print("SUCCESS:TST-0005-probe1 digest both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
