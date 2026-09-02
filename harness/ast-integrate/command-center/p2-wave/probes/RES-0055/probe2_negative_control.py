#!/usr/bin/env python3
"""Named probe 2: N/A control and reviewer bypass of listed mitigations."""

from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[3] / "tools"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))
import common as C  # noqa: E402

from marketplace.install import marketplace_install  # noqa: E402
from marketplace.tests.support import (  # noqa: E402
    generate_publisher,
    good_request,
    sign_digest,
    write_deterministic_tar,
)
from marketplace.verify import GateFailure  # noqa: E402
from plugin.installer import install_from_handoff  # noqa: E402
from plugin.payloadutil import PAYLOAD_FILES, PROJECTION_MAP  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0055-probe2 {msg}")
    return 1


class RecordingInstaller:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def install_from_handoff(self, handoff, dest_home):
        self.calls.append((dict(handoff), Path(dest_home)))
        return install_from_handoff(handoff, dest_home)


def main() -> int:
    artifact_path = C.REPO / C.OUT_REL
    doc = json.loads(artifact_path.read_text(encoding="utf-8"))
    mmap = C.artifact_field(doc, "mechanism_map") or []
    na = [
        r
        for r in mmap
        if isinstance(r, dict) and r.get("applicability_verdict") == "not-applicable"
    ]
    if len(na) < 1:
        return fail("control: no not-applicable mechanism in artifact")
    na_ids = {str(r.get("mechanism_class")) for r in na}
    if "post-install-script" not in na_ids:
        return fail("post-install-script must be the honest N/A control")
    if "dependency-confusion" not in na_ids:
        return fail("dependency-confusion must also be N/A on this fetch path")

    spawn = C.installer_has_no_process_spawn()
    if spawn["imports_subprocess"] or spawn["calls_os_system"]:
        return fail(f"installer process-spawn leak {spawn}")
    if not spawn["extracts_with_data_filter"]:
        return fail("installer extract missing filter=data")
    if not spawn["copies_with_copy2"]:
        return fail("installer does not copy2 projected files")
    fetch_src = (C.REPO / "tools/marketplace/fetch.py").read_text(encoding="utf-8")
    if "unsupported or missing source" not in fetch_src:
        return fail("fetch.py missing explicit-source rejection")

    bypasses: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="res0055-p2-") as tmp:
        tmp_path = Path(tmp)
        dest = tmp_path / "home"
        cache = tmp_path / "cache"
        blob = tmp_path / "pkg.tar.gz"

        planted = dict(PAYLOAD_FILES)
        planted["package.json"] = (
            b'{"name":"demo","scripts":{"postinstall":'
            b'"python3 -c \\"open(\'SIDE_EFFECT\',\'w\').write(\'pwned\')\\""}}\n'
        )
        planted["scripts/postinstall.sh"] = b"#!/bin/sh\ntouch SIDE_EFFECT\n"
        projection = dict(PROJECTION_MAP)
        projection["package.json"] = "package.json"
        projection["scripts/postinstall.sh"] = "scripts/postinstall.sh"
        digest = write_deterministic_tar(blob, files=planted)
        private, pub = generate_publisher()
        sig = sign_digest(private, digest)
        rec = RecordingInstaller()
        result = marketplace_install(
            good_request(
                dest,
                cache,
                blob,
                digest,
                sig,
                pub,
                projection_map=projection,
                installer=rec,
            )
        )
        if not result.get("ok"):
            return fail("planted-lifecycle install did not succeed")
        live = dest / "plugins" / "demo"
        if not (live / "package.json").is_file():
            return fail("package.json was not projected; control would be vacuous")
        leaked = [
            p
            for p in (
                tmp_path / "SIDE_EFFECT",
                dest / "SIDE_EFFECT",
                live / "SIDE_EFFECT",
                C.REPO / "SIDE_EFFECT",
            )
            if p.is_file()
        ]
        if leaked:
            for p in leaked:
                p.unlink()
            return fail(f"postinstall side effect appeared: {leaked}")
        if not rec.calls:
            return fail("expected installer to be invoked after passing gates")
        bypasses.append(
            {
                "mitigation": "MIT-NO-LIFECYCLE-RUNNER",
                "attempt": "tarball with package.json scripts.postinstall plus shell script",
                "outcome": "SURVIVED",
                "detail": "files copied; SIDE_EFFECT not created; no subprocess in installer",
            }
        )

        rec2 = RecordingInstaller()
        mutated = tmp_path / "mutated.tar.gz"
        raw = blob.read_bytes()
        mutated.write_bytes(raw[:-1] + bytes([raw[-1] ^ 0x01]))
        try:
            marketplace_install(
                good_request(
                    dest / "digest-bypass",
                    cache / "digest-bypass",
                    mutated,
                    digest,
                    sig,
                    pub,
                    installer=rec2,
                    transaction_id="txn-digest-bypass",
                )
            )
            return fail("digest mismatch did not fail closed")
        except GateFailure as exc:
            if "digest" not in str(exc).lower() and "lockfile" not in str(exc).lower():
                return fail(f"unexpected GateFailure {exc}")
        if rec2.calls:
            return fail("installer ran after digest mismatch")
        bypasses.append(
            {
                "mitigation": "MIT-LOCKFILE-DIGEST",
                "attempt": "same lockfile digest, mutated blob bytes",
                "outcome": "SURVIVED",
                "detail": "GateFailure before installer",
            }
        )

        rec3 = RecordingInstaller()
        try:
            marketplace_install(
                good_request(
                    dest / "unsigned",
                    cache / "unsigned",
                    blob,
                    digest,
                    None,
                    pub,
                    installer=rec3,
                    transaction_id="txn-unsigned",
                )
            )
            return fail("unsigned package did not fail closed")
        except GateFailure as exc:
            if "unsigned" not in str(exc).lower() and "signature" not in str(exc).lower():
                return fail(f"unexpected unsigned failure {exc}")
        if rec3.calls:
            return fail("installer ran for unsigned package")
        bypasses.append(
            {
                "mitigation": "MIT-SIGNATURE-FAIL-CLOSED",
                "attempt": "signature=None",
                "outcome": "SURVIVED",
                "detail": "GateFailure unsigned fail closed",
            }
        )

        encoded = (
            b"# hello\n<!-- "
            + b"UkVTLTAwNTUtT0JGVVNDQVRJT04tTUFSS0VS"
            + b" -->\n"
        )
        hidden = base64.b64decode("UkVTLTAwNTUtT0JGVVNDQVRJT04tTUFSS0VS")
        if hidden != b"RES-0055-OBFUSCATION-MARKER":
            return fail("fixture encoding drift")
        if b"RES-0055-OBFUSCATION-MARKER" in encoded:
            return fail("marker should be encoded, not plaintext")
        bypasses.append(
            {
                "mitigation": "human-review-of-SKILL.md",
                "attempt": "base64 marker in HTML comment inside SKILL.md",
                "outcome": "NOT-EFFECTIVE",
                "detail": "Not listed as an effective mitigation.",
                "encoded_present": True,
            }
        )

    survived = [b for b in bypasses if b["outcome"] == "SURVIVED"]
    if len(survived) < 3:
        return fail("listed mitigations did not survive bypass attempts")
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-negative-control",
                "unit_id": C.UNIT,
                "not_applicable": sorted(na_ids),
                "installer_spawn": spawn,
                "bypasses": bypasses,
                "reviewer_id": "RES-0055-probe2-mitigation-bypass",
            }
        )
    )
    print(f"n/a={sorted(na_ids)} survived={len(survived)}")
    print("SUCCESS:RES-0055-probe2 negative-control and mitigation bypass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
