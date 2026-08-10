"""The TEST FIXTURE MARKETPLACE: a deterministic, reproducible registry builder.

WHY A BUILDER AND NOT A COMMITTED REGISTRY
    Three reasons, each measured rather than aesthetic.

    1. **Digests must never be committed.** git stores LF, Windows checks out CRLF, so a
       committed ``payload_digest`` would be right on one platform and wrong on the other.
       The fixture registry is therefore generated into a caller-supplied root, and every
       digest is computed and compared inside one run on one filesystem.
    2. **Signatures must never carry committed secret key material.** Fixture keys are
       DERIVED from public labels (``sha256("mkt-fixture:publisher-alpha")``), so the repo
       contains no key bytes at all -- only the label that reproduces them. These are
       test keys for a local fixture and are not credentials of this estate.
    3. **The adversarial packages must not be committed.** ``secret-leaker`` exists to prove
       the payload scanner fires; committing a credential-shaped string to satisfy a test
       would trip the repo's own secret gates and would be exactly the wrong lesson. It is
       synthesised at build time, from an obviously-fake literal, and only ever lives in a
       temp root.

WHAT IT BUILDS
    Seven packages -- four publishable, three that MUST be refused -- one mirror, one
    collection, a revocation list, an advisory list, and a governance policy. The
    negative cases are as much of the fixture as the positive ones: a fixture marketplace
    in which everything publishes cannot demonstrate that anything is enforced.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from . import publish as publish_mod
from . import registry as reg
from . import schemas
from .canon import read_json, write_json
from .crypto import generate_keypair, key_id
from .publish import sign_index

MARKETPLACE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_SRC = MARKETPLACE_ROOT / "fixture"
REGISTRY_ID = "reg:fixture-local"
T0 = "2026-08-10T09:00:00Z"

#: Fixture identities. The SEED LABEL is committed; the key bytes are derived, never stored.
IDENTITIES: dict[str, dict[str, str]] = {
    "pub:registry-root": {
        "label": "mkt-fixture:registry-root",
        "role": "registry-maintainer",
        "name": "Fixture Registry Root",
    },
    "pub:alpha-tools": {
        "label": "mkt-fixture:alpha-tools",
        "role": "publisher",
        "name": "Alpha Tools",
    },
    "pub:beta-labs": {
        "label": "mkt-fixture:beta-labs",
        "role": "publisher",
        "name": "Beta Labs",
    },
    "pub:moderation-board": {
        "label": "mkt-fixture:moderation-board",
        "role": "moderator",
        "name": "Fixture Moderation Board",
    },
    "pub:security-response": {
        "label": "mkt-fixture:security-response",
        "role": "security-response",
        "name": "Fixture Security Response",
    },
}


def keys_for(publisher_id: str) -> tuple[str, str]:
    """``(secret_hex, public_key)`` derived deterministically from the committed label."""
    label = IDENTITIES[publisher_id]["label"]
    return generate_keypair(hashlib.sha256(label.encode("utf-8")).digest())


def publisher_documents(*, now: str = T0) -> list[dict[str, Any]]:
    docs = []
    for pid, meta in sorted(IDENTITIES.items()):
        _, public = keys_for(pid)
        doc = {
            "id": pid,
            "display_name": meta["name"],
            "contact": f"{pid.removeprefix('pub:')}@fixture.invalid",
            "registered_at": now,
            "role": meta["role"],
            "keys": [
                {
                    "key_id": key_id(public),
                    "public_key": public,
                    "status": "active",
                    "valid_from": now,
                }
            ],
        }
        schemas.validate("publisher", doc)
        docs.append(doc)
    return docs


def trust_policy(*, strict: bool = True) -> dict[str, Any]:
    """The consumer trust policy for the fixture. Fail-closed on every absence."""
    doc = read_json(FIXTURE_SRC / "trust-policy.json")
    _, root_pub = keys_for("pub:registry-root")
    doc["registry_maintainer_keys"] = [root_pub]
    doc["trusted_publishers"] = [
        {"publisher": pid, "public_key": keys_for(pid)[1]}
        for pid in sorted(IDENTITIES)
        if IDENTITIES[pid]["role"] == "publisher"
    ]
    doc["trusted_publishers"].append(
        {"publisher": "pub:registry-root", "public_key": root_pub}
    )
    if not strict:
        doc["on_missing"]["revocation_list"] = "warn"
        doc["on_missing"]["advisory_list"] = "warn"
    schemas.validate("trust-policy", doc)
    return doc


def governance_policy() -> dict[str, Any]:
    """The real marketplace governance policy -- the fixture does not get a softer one.

    It lives beside ``GOVERNANCE.md`` at the marketplace root (not under ``fixture/``)
    because ``prose_document`` is a non-traversing relative path by schema: a governance
    policy that had to point at ``../`` to find the document it governs would be a
    governance policy that could point anywhere.
    """
    doc = read_json(MARKETPLACE_ROOT / "governance-policy.json")
    schemas.validate("governance-policy", doc)
    return doc


# --------------------------------------------------------------------------- #
# adversarial packages -- synthesised, never committed
# --------------------------------------------------------------------------- #

#: An obviously-fake token. Split at build time so the literal never appears whole in the
#: repo, and prefixed `AKIA`-style only in shape, not in value.
_FAKE_TOKEN = "sk-" + "FIXTURE" + ("0" * 8) + "NOTAREALKEY" + ("1" * 8)


def _write_adversarial(root: Path) -> None:
    """Synthesise the three packages that MUST be refused."""
    # 1. excessive permissions -- the malicious-package test
    evil = root / "evil-overreach-1.0.0"
    (evil / "payload").mkdir(parents=True, exist_ok=True)
    (evil / "payload" / "README.md").write_text(
        "# evil-overreach\n\nA fixture package that asks for the whole machine. It must be REFUSED\n"
        "by the linter and again by the installer.\n",
        encoding="utf-8",
        newline="\n",
    )
    (evil / "payload" / "run.py").write_text(
        '"""Fixture payload. Does nothing; the point is the manifest it ships with."""\n\n\n'
        "def main() -> int:\n    return 0\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        evil / "package.json",
        {
            "name": "evil-overreach",
            "version": "1.0.0",
            "channel": "stable",
            "kind": "hook",
            "summary": "Fixture package requesting excessive permissions; must be refused.",
            "license": {
                "spdx": "MIT",
                "notice_required": False,
                "aggregate_verified": True,
            },
            "permissions": [
                "secrets:read:**",
                "net:egress:**",
                "exec:process:**",
                "fs:write:**",
                "hook:register:PreToolUse",
            ],
            "compatibility": {
                "platforms": ["any"],
                "clients": [{"id": "claude-code", "range": ">=2.0.0"}],
            },
            "provenance": {
                "source": "https://fixture.invalid/evil-overreach",
                "source_revision": "1" * 40,
                "builder": "mkt-fixture/1.0.0",
                "reproducible": True,
            },
            "payload_files": ["README.md", "run.py"],
            "file_licenses": {"README.md": "MIT", "run.py": "MIT"},
            "categories": ["security"],
            "tags": ["fixture", "malicious"],
        },
    )

    # 2. secret leakage -- payload carries a credential-shaped line and owner topology
    leaker = root / "secret-leaker-1.0.0"
    (leaker / "payload").mkdir(parents=True, exist_ok=True)
    (leaker / "payload" / "README.md").write_text(
        "# secret-leaker\n\nFixture package whose payload carries a fake credential and an\n"
        "absolute local path. `mkt publish` must refuse it (deny-by-default scan).\n",
        encoding="utf-8",
        newline="\n",
    )
    (leaker / "payload" / "config.ini").write_text(
        "[service]\n"
        f"api_key = {_FAKE_TOKEN}\n"
        "cache_dir = C:/Users/example-operator/AppData/Local/fixture\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        leaker / "package.json",
        {
            "name": "secret-leaker",
            "version": "1.0.0",
            "channel": "beta",
            "kind": "library",
            "summary": "Fixture package leaking a fake credential; publish must refuse.",
            "license": {
                "spdx": "MIT",
                "notice_required": False,
                "aggregate_verified": True,
            },
            "permissions": ["fs:read:packages/secret-leaker/**"],
            "compatibility": {
                "platforms": ["any"],
                "clients": [{"id": "claude-code", "range": ">=2.0.0"}],
            },
            "provenance": {
                "source": "https://fixture.invalid/secret-leaker",
                "source_revision": "2" * 40,
                "builder": "mkt-fixture/1.0.0",
                "reproducible": False,
            },
            "payload_files": ["README.md", "config.ini"],
            "file_licenses": {"README.md": "MIT", "config.ini": "MIT"},
            "tags": ["fixture"],
        },
    )

    # 3. the M1 licence-misstatement shape: Apache-2.0 component under a declared MIT
    mixer = root / "apache-mixer-1.0.0"
    (mixer / "payload").mkdir(parents=True, exist_ok=True)
    (mixer / "payload" / "README.md").write_text(
        "# apache-mixer\n\nDeclares an MIT aggregate while shipping an Apache-2.0 component.\n"
        "This is the TOURNAMENT-VERDICT M1 defect shape, as a fixture.\n",
        encoding="utf-8",
        newline="\n",
    )
    (mixer / "payload" / "vendored.py").write_text(
        '"""Vendored third-party helper, Apache-2.0 (fixture)."""\n\n\ndef helper() -> int:\n    return 1\n',
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        mixer / "package.json",
        {
            "name": "apache-mixer",
            "version": "1.0.0",
            "channel": "stable",
            "kind": "library",
            "summary": "Fixture package with an Apache-2.0 component under a declared MIT aggregate.",
            "license": {
                "spdx": "MIT",
                "notice_required": False,
                "aggregate_verified": False,
            },
            "permissions": ["fs:read:packages/apache-mixer/**"],
            "compatibility": {
                "platforms": ["any"],
                "clients": [{"id": "claude-code", "range": ">=2.0.0"}],
            },
            "provenance": {
                "source": "https://fixture.invalid/apache-mixer",
                "source_revision": "3" * 40,
                "builder": "mkt-fixture/1.0.0",
                "reproducible": True,
            },
            "payload_files": ["README.md", "vendored.py"],
            "file_licenses": {"README.md": "MIT", "vendored.py": "Apache-2.0"},
            "tags": ["fixture"],
        },
    )


def package_sources(work_root: str | Path) -> Path:
    """Materialise every fixture package source (committed + synthesised) under ``work_root``."""
    out = Path(work_root) / "sources"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    committed = FIXTURE_SRC / "packages"
    for child in sorted(committed.iterdir()):
        if child.is_dir():
            shutil.copytree(child, out / child.name)
    _write_adversarial(out)
    return out


# --------------------------------------------------------------------------- #
# registry construction
# --------------------------------------------------------------------------- #

PUBLISHABLE: tuple[tuple[str, str], ...] = (
    ("hello-skill-1.0.0", "pub:alpha-tools"),
    ("hello-skill-1.1.0", "pub:alpha-tools"),
    ("dep-consumer-1.0.0", "pub:beta-labs"),
    ("vulnerable-lib-1.0.0", "pub:beta-labs"),
)

MUST_REFUSE: tuple[tuple[str, str, str], ...] = (
    ("evil-overreach-1.0.0", "pub:alpha-tools", "MKT-P07"),
    ("secret-leaker-1.0.0", "pub:beta-labs", "MKT-P06"),
    ("apache-mixer-1.0.0", "pub:beta-labs", "MKT-P08"),
)


def empty_index(*, with_mirror: bool = True, now: str = T0) -> dict[str, Any]:
    index: dict[str, Any] = {
        "schema_version": "1.0.0",
        "registry_id": REGISTRY_ID,
        "title": "mkt fixture marketplace",
        "generated_at": now,
        "entries": [],
        "publishers": publisher_documents(now=now),
        "revocation_path": "revocation.json",
        "advisory_path": "advisories.json",
        "collections": [
            {
                "collection_id": "col:starter",
                "title": "Starter set",
                "description": "The packages a fresh install should carry.",
                "curator": "pub:registry-root",
                "members": [
                    {
                        "name": "hello-skill",
                        "range": "^1.0.0",
                        "note": "the canonical example",
                    }
                ],
            }
        ],
    }
    if with_mirror:
        index["mirrors"] = [
            {
                "mirror_id": "mir:private-a",
                "title": "Private mirror A",
                "root": "mirrors/private-a",
                "priority": 10,
                "visibility": "private",
                "trust_mode": "verify-and-require-primary-index",
                "enabled": True,
            }
        ]
    return index


def build(
    work_root: str | Path,
    *,
    now: str = T0,
    include_mirror: bool = True,
    strict_policy: bool = True,
) -> dict[str, Any]:
    """Build the whole fixture marketplace under ``work_root``.

    Returns a dict with the registry root, the trust policy, the governance policy, the
    publish results, and the refusals -- the refusals are RETURNED, not swallowed, so a
    caller can assert that each expected refusal actually happened with its expected code.
    """
    work = Path(work_root)
    registry_root = work / "registry"
    registry_root.mkdir(parents=True, exist_ok=True)
    sources = package_sources(work)

    policy = trust_policy(strict=strict_policy)
    governance = governance_policy()
    root_secret, _ = keys_for("pub:registry-root")

    index = empty_index(with_mirror=include_mirror, now=now)
    sign_index(index, root_secret, now=now)
    write_json(reg.index_path(registry_root), index)

    # an empty, signed revocation list: PRESENT and EMPTY is a different fact from ABSENT,
    # and the fail-closed installer treats them differently on purpose.
    from .moderation import _write_revocation, publish_advisory  # noqa: PLC0415 - avoids an import cycle

    _write_revocation(
        registry_root,
        index,
        {
            "schema_version": "1.0.0",
            "registry_id": REGISTRY_ID,
            "updated_at": now,
            "revocations": [],
        },
        root_secret,
        now,
    )
    publish_advisory(
        registry_root,
        advisory={
            "advisory_id": "adv:2026-0001",
            "state": "confirmed",
            "severity": "high",
            "title": "vulnerable-lib mishandles untrusted input in the fixture scenario",
            "detail": "Fixture advisory used to prove the vulnerability gate blocks and that the override is recorded.",
            "cwe": "CWE-20",
            "affected": [
                {"name": "vulnerable-lib", "range": "<=1.0.0", "fixed_in": "1.0.1"}
            ],
            "reported_at": now,
            "reporter": "fixture-harness",
            "triaged_by": "pub:security-response",
        },
        authority="pub:security-response",
        maintainer_secret_hex=root_secret,
        now=now,
    )

    published: list[dict[str, Any]] = []
    for folder, publisher in PUBLISHABLE:
        secret, _ = keys_for(publisher)
        result = publish_mod.publish_into(
            sources / folder,
            registry_root,
            secret_hex=secret,
            publisher_id=publisher,
            maintainer_secret_hex=root_secret,
            trust_policy=policy,
            governance=governance,
            now=now,
            license_basis_path=FIXTURE_SRC / "LICENSE",
        )
        published.append(
            {
                "name": result.name,
                "version": result.version,
                "score": result.score["total"],
                "files": result.payload_files,
            }
        )

    refusals: list[dict[str, Any]] = []
    for folder, publisher, expected in MUST_REFUSE:
        secret, _ = keys_for(publisher)
        try:
            publish_mod.publish_into(
                sources / folder,
                registry_root,
                secret_hex=secret,
                publisher_id=publisher,
                maintainer_secret_hex=root_secret,
                trust_policy=policy,
                governance=governance,
                now=now,
                license_basis_path=FIXTURE_SRC / "LICENSE",
            )
        except publish_mod.PublishRefused as exc:
            refusals.append(
                {
                    "folder": folder,
                    "expected": expected,
                    "actual": exc.code,
                    "message": str(exc)[:300],
                }
            )
        else:
            refusals.append(
                {
                    "folder": folder,
                    "expected": expected,
                    "actual": "PUBLISHED",
                    "message": "NOT REFUSED",
                }
            )

    if include_mirror:
        _build_mirror(registry_root, root_secret, now=now)

    return {
        "registry_root": registry_root,
        "sources": sources,
        "trust_policy": policy,
        "governance": governance,
        "index": reg.load_index(registry_root),
        "published": published,
        "refusals": refusals,
        "root_secret_hex": root_secret,
        "now": now,
    }


def _build_mirror(registry_root: Path, root_secret: str, *, now: str) -> Path:
    """A private mirror carrying only the stable hello-skill, in require-primary-index mode."""
    index = reg.load_index(registry_root)
    mirror_root = registry_root / "mirrors" / "private-a"
    mirror_root.mkdir(parents=True, exist_ok=True)
    keep = [
        e
        for e in index["entries"]
        if e["name"] == "hello-skill" and e["channel"] == "stable"
    ]
    mirror_index = {
        "schema_version": "1.0.0",
        "registry_id": "reg:fixture-mirror-a",
        "title": "Private mirror A",
        "generated_at": now,
        "entries": keep,
        "publishers": index["publishers"],
        "revocation_path": "revocation.json",
        "advisory_path": "advisories.json",
    }
    sign_index(mirror_index, root_secret, now=now)
    write_json(reg.index_path(mirror_root), mirror_index)
    for entry in keep:
        rel = f"packages/{entry['name']}/{entry['version']}"
        dst = mirror_root / rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(registry_root / rel, dst)
    for name in ("revocation.json", "advisories.json"):
        src = registry_root / name
        if src.is_file():
            shutil.copy2(src, mirror_root / name)
    return mirror_root
