"""A5 cloud-batch auth: runtime injection, never bundled auth files.

A5-RUNTIME-INJECT-NO-BUNDLE: the image and the harvest bundle may list the
*names* of required environment variables. Values arrive from a host-side
broker at process start. A missing name is a named error, not an empty string.
Auth files are refused at pack time.
"""
from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from scrubber import AUTH_FILENAMES, Finding, assert_clean, scan_mapping

REQUIRED_ENV_MANIFEST = "required-env.json"


class AuthBundleRefused(Exception):
    pass


class MissingRuntimeSecret(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"A5-RUNTIME-INJECT-NO-BUNDLE missing required env {name}")


@dataclass
class PackResult:
    ok: bool
    members: list[str]
    blob: bytes = b""
    findings: list[Finding] = field(default_factory=list)
    reason: str = ""


def required_env_document(names: list[str]) -> bytes:
    body = {
        "contract": "A5-RUNTIME-INJECT-NO-BUNDLE",
        "required_env_names": list(names),
        "values_in_image": False,
        "broker": "host-side-workload-identity-or-secret-broker",
    }
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _member_forbidden(name: str) -> bool:
    base = Path(name.replace("\\", "/")).name
    return base in AUTH_FILENAMES


def pack_image(files: dict[str, bytes]) -> PackResult:
    """Fail-closed packer: auth filenames and secret-shaped bytes refuse the image."""
    members = sorted(files)
    forbidden = [m for m in members if _member_forbidden(m)]
    if forbidden:
        return PackResult(
            ok=False,
            members=members,
            reason="auth-filename:" + ",".join(forbidden),
        )
    findings = scan_mapping(files, artifact_class="harvest-bundle")
    if findings:
        return PackResult(
            ok=False,
            members=members,
            findings=findings,
            reason="scrub-gate:"
            + ",".join(f"{f.rule_id}@{f.path}" for f in findings),
        )
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name in members:
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    return PackResult(ok=True, members=members, blob=buf.getvalue())


def inject_runtime(required_names: list[str], broker: dict[str, str]) -> dict[str, str]:
    """Copy values from the broker. Never persist them. Missing name is loud."""
    injected: dict[str, str] = {}
    for name in required_names:
        if name not in broker or broker[name] == "":
            raise MissingRuntimeSecret(name)
        injected[name] = broker[name]
    return injected


def harvest_from_image(blob: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(blob), mode="r") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            out[member.name] = extracted.read() if extracted is not None else b""
    assert_clean(out, artifact_class="harvest-bundle")
    return out
