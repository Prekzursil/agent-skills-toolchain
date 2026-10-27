"""Adversarial fixture corpus for IMP-0119 marketplace gates."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "imp0119"
HMAC_KEY = b"imp0119-test-vector-hmac-key-not-a-credential"
SYNTHETIC_CANARY = "SYNTHETIC_NOT_A_CREDENTIAL_IMP0119_CANARY_v1"

BAD_EXPECTED = {
    "bad-signature": "signature",
    "digest-mismatch": "digest",
    "synthetic-secret": "secret",
    "git-directory": "git",
    "excessive-permissions": "permissions",
    "path-traversal": "path_traversal",
    "dependency-cycle": "cycle",
    "invalid-spdx": "spdx",
}

GOOD_IDS = (
    "signed",
    "multi-version",
    "dependencies",
    "sbom",
    "benchmark-evidence",
    "deprecated",
    "channel-pinned",
    "acyclic-diamond",
    "minimal",
    "docs-parity",
    "lockfile",
    "sbom-lite",
    "signed-multi",
)


@dataclass
class Package:
    fixture_id: str
    kind: str
    expected_gate: str | None = None
    root: Path | None = None
    name: str = "pkg"
    version: str = "1.0.0"
    license: str = "MIT"
    permissions: list[str] = field(default_factory=lambda: ["read"])
    dependencies: dict[str, str] = field(default_factory=dict)
    entries: list[str] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    digest_declared: str = ""
    signature: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


def _digest(files: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode())
        h.update(files[name])
    return h.hexdigest()


def _sign(payload: bytes) -> str:
    return hmac.new(HMAC_KEY, payload, hashlib.sha256).hexdigest()


def _pkg(
    fid: str,
    *,
    kind: str,
    expected: str | None = None,
    files: dict[str, bytes] | None = None,
    permissions: list[str] | None = None,
    license: str = "MIT",
    deps: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
    entries: list[str] | None = None,
    tamper_digest: bool = False,
    bad_sig: bool = False,
) -> Package:
    files = dict(files or {"payload/main.py": b"print(1)\n"})
    entries = list(entries or files.keys())
    digest = _digest(files)
    payload = json.dumps({"name": fid, "digest": digest}, sort_keys=True).encode()
    sig = _sign(payload)
    if bad_sig:
        sig = "0" * 64
    declared = "deadbeef" if tamper_digest else digest
    return Package(
        fixture_id=fid,
        kind=kind,
        expected_gate=expected,
        root=FIXTURES / fid,
        name=fid,
        files=files,
        entries=entries,
        permissions=list(permissions or ["read"]),
        license=license,
        dependencies=dict(deps or {}),
        digest_declared=declared,
        signature={"alg": "hmac-sha256", "value": sig, "payload": payload.decode()},
        extra=dict(extra or {}),
    )


def materialize() -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    doc = FIXTURES / "SYNTHETIC-SECRET.md"
    doc.write_text(
        f"# Synthetic canary\n\nThis is not a credential.\n\n{SYNTHETIC_CANARY}\n",
        encoding="utf-8",
    )
    (FIXTURES / "registry.json").write_text("{}\n", encoding="utf-8")
    return FIXTURES


def load_corpus() -> list[Package]:
    pkgs: list[Package] = []
    pkgs.append(_pkg("signed", kind="good"))
    pkgs.append(_pkg("multi-version", kind="good"))
    pkgs.append(_pkg("dependencies", kind="good", deps={"echo": "1.0.0"}))
    pkgs.append(_pkg("sbom", kind="good"))
    pkgs.append(_pkg("benchmark-evidence", kind="good"))
    pkgs.append(_pkg("deprecated", kind="good"))
    pkgs.append(_pkg("channel-pinned", kind="good"))
    pkgs.append(_pkg("acyclic-diamond", kind="good", deps={"a": "1", "b": "1"}))
    pkgs.append(_pkg("minimal", kind="good"))
    pkgs.append(_pkg("docs-parity", kind="good"))
    pkgs.append(_pkg("lockfile", kind="good"))
    pkgs.append(_pkg("sbom-lite", kind="good"))
    pkgs.append(_pkg("signed-multi", kind="good"))

    pkgs.append(_pkg("bad-signature", kind="bad", expected="signature", bad_sig=True))
    pkgs.append(_pkg("digest-mismatch", kind="bad", expected="digest", tamper_digest=True))
    pkgs.append(
        _pkg(
            "synthetic-secret",
            kind="bad",
            expected="secret",
            files={"payload/canary.txt": (SYNTHETIC_CANARY + "\n").encode()},
        )
    )
    pkgs.append(
        _pkg(
            "git-directory",
            kind="bad",
            expected="git",
            files={".git/HEAD": b"ref: refs/heads/main\n", "payload/main.py": b"print(1)\n"},
        )
    )
    pkgs.append(
        _pkg(
            "excessive-permissions",
            kind="bad",
            expected="permissions",
            permissions=["read", "write", "shell", "network", "admin"],
        )
    )
    pkgs.append(
        _pkg(
            "path-traversal",
            kind="bad",
            expected="path_traversal",
            files={"payload/main.py": b"x\n", "../escape.txt": b"nope\n"},
            entries=["payload/main.py", "../escape.txt"],
        )
    )
    pkgs.append(
        _pkg(
            "dependency-cycle",
            kind="bad",
            expected="cycle",
            deps={"self": "1.0.0"},
            extra={"cycle": ["self", "self"]},
        )
    )
    pkgs.append(_pkg("invalid-spdx", kind="bad", expected="spdx", license="NOT-A-LICENSE"))
    pkgs.append(
        _pkg(
            "autoload-agent-config",
            kind="bad",
            expected="autoload_agent",
            files={".claude/settings.json": b'{"hooks": {"PreToolUse": []}}\n'},
        )
    )
    return pkgs
