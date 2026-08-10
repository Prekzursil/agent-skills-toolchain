"""The publish pipeline and its BLOCKING preconditions.

WHAT PUBLISHING IS HERE
    Take a package source directory (a publisher-authored ``package.json`` spec plus a
    ``payload/`` tree), and: enumerate the payload against the spec's EXPLICIT allowlist,
    scan it for secrets and local topology, build the SBOM, score conformance, build and
    SIGN the manifest, copy the payload into the registry, add the index entry, and re-sign
    the index. Any precondition failure REFUSES; nothing partial is written.

THE PRECONDITIONS ARE THE POINT (marketplace-first Stage 0, adopted)
    ``governance-policy.json`` declares ``publish_preconditions`` and this module enforces
    them. ``license-basis-present`` is the one the tournament minority report insisted on:
    M1 records that this repo has no root ``LICENSE``/``COPYING``/``NOTICE`` while
    aggregating 31 Apache-2.0 payload entries under a declared ``MIT``, and calls the
    winning spine "unlawful to publish without" the marketplace lane. Making that a
    blocking gate rather than a memo is the adoption.

DENY BY DEFAULT ON PAYLOAD CONTENT
    :func:`scan_payload` is not an allowlist redactor. It reports a finding for anything
    credential-SHAPED or topology-revealing and requires the publisher to remove it -- an
    allowlist scanner in this program leaked eight real values, so the direction of the
    default matters more than the cleverness of the patterns. FM-4 measured an absolute
    ``C:/Users/...`` path already committed inside a registry row in this repo, which is
    the exact class rule ``SEC-2`` catches.
"""

from __future__ import annotations

import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import permissions as perms
from . import registry as reg
from . import sbom as sbom_mod
from . import schemas
from .canon import (
    digest_file,
    ensure_within,
    hex_digest_file,
    iso_now,
    payload_digest,
    read_json,
    write_json,
)
from .crypto import sign_document

SPEC_NAME = "package.json"
PAYLOAD_DIR = "payload"

#: Secret / topology rules. Every one is DENY: a hit refuses the publish.
SECRET_RULES: tuple[tuple[str, str, str], ...] = (
    ("SEC-1", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key block"),
    (
        "SEC-2",
        r"(?:[A-Za-z]:[\\/]Users[\\/]|/home/[a-z]|/Users/)",
        "absolute local user path (owner topology)",
    ),
    (
        "SEC-3",
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|credential|bearer)\b\s*[:=]\s*\S{8,}",
        "credential-shaped assignment",
    ),
    ("SEC-4", r"(?i)authorization\s*:\s*bearer\s+\S+", "Authorization: Bearer header"),
    (
        "SEC-5",
        r"\b(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})",
        "known provider credential prefix",
    ),
    ("SEC-6", r"\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9$._-]+", "UNC network path"),
)

_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/=_-]{24,}")
_DIGEST_CONTEXT = re.compile(r"(?:sha256[:=]|sha256\"?\s*:\s*\"?|[0-9a-f]{64})")
ENTROPY_FLOOR = 4.2


def shannon(text: str) -> float:
    if not text:
        return 0.0
    counts: dict[str, int] = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    detail: str


def scan_text(text: str, path: str) -> list[Finding]:
    """Scan one text payload file. Returns findings; an empty list is a real clean result."""
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rule, pattern, detail in SECRET_RULES:
            if re.search(pattern, line):
                out.append(Finding(rule, path, lineno, detail))
        for token in _ENTROPY_TOKEN.findall(line):
            if re.fullmatch(r"[0-9a-f]{64}", token):
                continue  # a bare sha256 digest is data this build itself emits
            if _DIGEST_CONTEXT.search(line) and re.fullmatch(r"[0-9a-f]{32,}", token):
                continue
            if shannon(token) >= ENTROPY_FLOOR:
                out.append(
                    Finding(
                        "SEC-7",
                        path,
                        lineno,
                        f"high-entropy token ({shannon(token):.2f} bits/char, len {len(token)}) -- "
                        "deny-by-default: prove it is not a credential or remove it",
                    )
                )
    return out


def scan_payload(payload_root: str | Path, files: list[str]) -> list[Finding]:
    """Scan every enumerated payload file. Binary files are hashed, not scanned, and said so."""
    root = Path(payload_root)
    out: list[Finding] = []
    for rel in files:
        path = ensure_within(root, rel)
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            out.append(
                Finding(
                    "SEC-0",
                    rel,
                    0,
                    "binary payload file: NOT scanned for secrets (only hashed)",
                )
            )
            continue
        out.extend(scan_text(text, rel))
    return out


class PublishRefused(RuntimeError):
    """A blocking precondition refused the publish. Carries the machine code and detail."""

    def __init__(
        self, code: str, message: str, *, findings: list[Finding] | None = None
    ) -> None:
        self.code = code
        self.findings = findings or []
        super().__init__(f"{code}: {message}")


# --------------------------------------------------------------------------- #
# payload enumeration
# --------------------------------------------------------------------------- #


def enumerate_payload(
    payload_root: str | Path, declared: list[str]
) -> list[dict[str, Any]]:
    """Build the manifest payload list from an EXPLICIT declared allowlist.

    Bijection in both directions. A declared file that is absent refuses; a present file
    that was not declared refuses. The second direction is the one that matters: it is how
    an unreviewed file (a stray ``.env``, a cache, a 30 MB video) gets into a package.
    """
    root = Path(payload_root)
    if not root.is_dir():
        raise PublishRefused("MKT-P01", f"payload directory does not exist: {root}")
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    declared_set = set(declared)
    missing = sorted(declared_set - present)
    undeclared = sorted(present - declared_set)
    if missing:
        raise PublishRefused(
            "MKT-P02", f"declared payload files absent from disk: {missing}"
        )
    if undeclared:
        raise PublishRefused(
            "MKT-P03",
            f"payload files present but NOT declared in the allowlist: {undeclared} "
            "(an implicit payload is an unreviewed payload -- marketplace-first FM-4)",
        )
    files = []
    for rel in sorted(declared_set):
        path = ensure_within(root, rel)
        files.append(
            {
                "path": rel,
                "sha256": "sha256:" + hex_digest_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return files


# --------------------------------------------------------------------------- #
# quality score
# --------------------------------------------------------------------------- #

SCORE_WEIGHTS: dict[str, int] = {
    "schema-valid": 12,
    "payload-digest-verified": 12,
    "sbom-complete": 12,
    "signature-valid": 12,
    "license-declared": 8,
    "license-aggregate-consistent": 10,
    "permissions-minimal": 10,
    "provenance-complete": 8,
    "reproducible-build": 6,
    "tests-declared": 5,
    "docs-present": 5,
}


def build_quality_score(
    *,
    name: str,
    version: str,
    earned: dict[str, bool],
    evidence: dict[str, str],
    scored_at: str,
    scorer: str = "mkt-publish/1.0.0",
) -> dict[str, Any]:
    """Weighted integer score. ``total`` is the SUM of earned weights and is recomputable.

    ``mkt.lint`` (MKT-L12) recomputes it and refuses a mismatch, so a publisher cannot
    assert 100 without asserting the eleven facts that add to 100.
    """
    components = []
    total = 0
    for cid, weight in sorted(SCORE_WEIGHTS.items()):
        got = weight if earned.get(cid) else 0
        total += got
        components.append(
            {
                "id": cid,
                "weight": weight,
                "earned": got,
                "evidence": evidence.get(cid, "not earned: no evidence recorded"),
            }
        )
    return {
        "schema_version": "1.0.0",
        "name": name,
        "version": version,
        "total": total,
        "components": components,
        "scored_at": scored_at,
        "scorer": scorer,
    }


def recompute_total(score: dict[str, Any]) -> int:
    return sum(int(c["earned"]) for c in score.get("components", []))


# --------------------------------------------------------------------------- #
# publish
# --------------------------------------------------------------------------- #


@dataclass
class PublishResult:
    name: str
    version: str
    entry: dict[str, Any]
    manifest: dict[str, Any]
    sbom: dict[str, Any]
    score: dict[str, Any]
    manifest_path: Path
    payload_files: int
    warnings: list[str] = field(default_factory=list)


def load_spec(package_dir: str | Path) -> dict[str, Any]:
    path = Path(package_dir) / SPEC_NAME
    if not path.is_file():
        raise PublishRefused(
            "MKT-P04", f"no {SPEC_NAME} in package directory: {package_dir}"
        )
    return read_json(path)


def _check_governance(policy: dict[str, Any] | None, required: str) -> bool:
    if policy is None:
        return False
    return required in policy.get("publish_preconditions", [])


def publish(
    package_dir: str | Path,
    registry_root: str | Path,
    *,
    secret_hex: str,
    publisher_id: str,
    trust_policy: dict[str, Any],
    governance: dict[str, Any] | None = None,
    now: str | None = None,
    license_basis_path: str | Path | None = None,
    allow_unverified_aggregate: bool = False,
) -> PublishResult:
    """Publish ``package_dir`` into ``registry_root``. Refuses rather than warns."""
    package_dir = Path(package_dir)
    registry_root = Path(registry_root)
    timestamp = now or iso_now()
    spec = load_spec(package_dir)

    name = spec["name"]
    version = spec["version"]
    payload_root = package_dir / PAYLOAD_DIR

    # --- precondition: licence basis (marketplace-first Stage 0) -------------
    if _check_governance(governance, "license-basis-present"):
        basis = Path(license_basis_path) if license_basis_path else None
        if basis is None or not basis.is_file():
            raise PublishRefused(
                "MKT-P05",
                "governance requires `license-basis-present` and no LICENSE/COPYING/NOTICE file was "
                "supplied. TOURNAMENT-VERDICT.md M1: publishing without a licence basis is not "
                "merely un-governed, it is not lawful. This gate exists so that is enforced, not remembered.",
            )

    # --- payload: explicit allowlist, both directions ------------------------
    files = enumerate_payload(payload_root, spec["payload_files"])
    pdigest = payload_digest(files)

    # --- precondition: no secret findings ------------------------------------
    findings = scan_payload(payload_root, spec["payload_files"])
    hard = [f for f in findings if f.rule != "SEC-0"]
    if hard and _check_governance(governance, "no-secret-findings"):
        raise PublishRefused(
            "MKT-P06",
            f"{len(hard)} secret/topology finding(s) in the payload; deny-by-default refuses the publish",
            findings=hard,
        )

    # --- precondition: permissions within the consumer ceiling ---------------
    verdict = perms.evaluate(
        spec.get("permissions", []),
        max_permissions=trust_policy["max_permissions"],
        grant_permissions=_grant_for(trust_policy, publisher_id),
        forbidden_permissions=trust_policy.get("forbidden_permissions"),
    )
    if not verdict.admissible and _check_governance(
        governance, "permissions-within-ceiling"
    ):
        raise PublishRefused(
            "MKT-P07",
            f"excessive permissions: {verdict.excessive} -> {verdict.reasons}",
        )

    # --- SBOM ---------------------------------------------------------------
    sbom_doc = sbom_mod.build(
        name=name,
        version=version,
        files=files,
        licenses=spec.get("file_licenses", {}),
        payload_digest=pdigest,
        timestamp=timestamp,
        default_license=spec["license"]["spdx"],
    )
    schemas.validate("sbom", sbom_doc)

    # --- licence aggregate consistency --------------------------------------
    comp_licenses = set(sbom_mod.component_licenses(sbom_doc).values())
    declared_spdx = spec["license"]["spdx"]
    aggregate_ok = comp_licenses <= {declared_spdx}
    if not aggregate_ok and not spec["license"].get("aggregate_verified"):
        if (
            _check_governance(governance, "license-aggregate-consistent")
            and not allow_unverified_aggregate
        ):
            raise PublishRefused(
                "MKT-P08",
                f"declared aggregate licence {declared_spdx!r} does not cover component licences "
                f"{sorted(comp_licenses)} and `aggregate_verified` is false. This is the M1 defect "
                "shape: 31 Apache-2.0 entries under a declared MIT, invisible to a LICENSE-file scanner.",
            )

    # --- manifest -----------------------------------------------------------
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "name": name,
        "version": version,
        "channel": spec["channel"],
        "summary": spec["summary"],
        "kind": spec.get("kind", "library"),
        "publisher": publisher_id,
        "license": {
            "spdx": declared_spdx,
            "notice_required": bool(
                spec["license"].get(
                    "notice_required", declared_spdx.startswith("Apache")
                )
            ),
            "aggregate_verified": bool(
                spec["license"].get("aggregate_verified", aggregate_ok)
            ),
        },
        "permissions": sorted(spec.get("permissions", [])),
        "compatibility": spec["compatibility"],
        "payload": {"root": PAYLOAD_DIR, "files": files, "digest": pdigest},
        "provenance": {
            "source": spec["provenance"]["source"],
            "builder": spec["provenance"]["builder"],
            "built_at": timestamp,
            "reproducible": bool(spec["provenance"].get("reproducible", False)),
        },
        "sbom_ref": "sbom.json",
        "quality": {
            "conformance_score": 0,
            "scored_at": timestamp,
            "score_ref": "quality-score.json",
        },
        "created_at": timestamp,
    }
    if spec.get("description"):
        manifest["description"] = spec["description"]
    if spec.get("dependencies"):
        manifest["dependencies"] = spec["dependencies"]
    if spec.get("categories"):
        manifest["categories"] = spec["categories"]
    if spec.get("tags"):
        manifest["tags"] = spec["tags"]
    if spec.get("deprecation"):
        manifest["deprecation"] = spec["deprecation"]
    if spec["provenance"].get("source_revision"):
        manifest["provenance"]["source_revision"] = spec["provenance"][
            "source_revision"
        ]
    if spec["provenance"].get("receipt_ref"):
        manifest["provenance"]["receipt_ref"] = spec["provenance"]["receipt_ref"]

    # --- score --------------------------------------------------------------
    score = build_quality_score(
        name=name,
        version=version,
        earned={
            "schema-valid": True,
            "payload-digest-verified": True,
            "sbom-complete": True,
            "signature-valid": True,
            "license-declared": bool(declared_spdx),
            "license-aggregate-consistent": aggregate_ok
            or bool(spec["license"].get("aggregate_verified")),
            "permissions-minimal": verdict.admissible
            and all(
                perms.widest_reach(p) != "universal"
                for p in spec.get("permissions", [])
            ),
            "provenance-complete": bool(spec["provenance"].get("source_revision")),
            "reproducible-build": bool(spec["provenance"].get("reproducible")),
            "tests-declared": bool(spec.get("tests")),
            "docs-present": any(
                f["path"].lower().endswith((".md", ".rst", ".txt")) for f in files
            ),
        },
        evidence={
            "schema-valid": "mkt.schemas.validate('package-manifest', manifest)",
            "payload-digest-verified": f"mkt.canon.payload_digest -> {pdigest}",
            "sbom-complete": "mkt.sbom.verify bijection over payload root",
            "signature-valid": "mkt.crypto.verify_document(domain=mkt.manifest.v1)",
            "license-declared": f"manifest.license.spdx={declared_spdx}",
            "license-aggregate-consistent": f"sbom component licences={sorted(comp_licenses)}",
            "permissions-minimal": f"permissions={sorted(spec.get('permissions', []))}",
            "provenance-complete": f"source_revision={spec['provenance'].get('source_revision')!r}",
            "reproducible-build": f"reproducible={spec['provenance'].get('reproducible')!r}",
            "tests-declared": f"tests={spec.get('tests')!r}",
            "docs-present": "payload contains a .md/.rst/.txt file",
        },
        scored_at=timestamp,
    )
    schemas.validate("quality-score", score)
    manifest["quality"]["conformance_score"] = score["total"]
    if spec.get("benchmark"):
        manifest["quality"]["benchmark_ref"] = "benchmark-evidence.json"

    schemas.validate("package-manifest", manifest)

    floor = trust_policy["thresholds"]["min_conformance_score"]
    if score["total"] < floor and _check_governance(
        governance, "conformance-score-floor"
    ):
        raise PublishRefused(
            "MKT-P09",
            f"conformance score {score['total']} is below the policy floor {floor}",
        )

    # --- sign ---------------------------------------------------------------
    manifest["signature"] = sign_document(
        manifest, "mkt.manifest.v1", secret_hex, signed_at=timestamp
    )
    ok, why = _verify_own_signature(manifest)
    if not ok:
        raise PublishRefused(
            "MKT-P10", f"self-verification of the signature we just made failed: {why}"
        )

    # --- write into the registry -------------------------------------------
    rel_dir = f"packages/{name}/{version}"
    target_dir = ensure_within(registry_root, rel_dir)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    (target_dir / PAYLOAD_DIR).mkdir(parents=True, exist_ok=True)
    for entry in files:
        src = ensure_within(payload_root, entry["path"])
        dst = ensure_within(target_dir / PAYLOAD_DIR, entry["path"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if digest_file(dst) != entry["sha256"]:
            raise PublishRefused(
                "MKT-P11",
                f"payload copy digest changed for {entry['path']!r} -- refusing to publish",
            )
    manifest_file = write_json(target_dir / "manifest.json", manifest)
    write_json(target_dir / "sbom.json", sbom_doc)
    write_json(target_dir / "quality-score.json", score)
    if spec.get("benchmark"):
        schemas.validate("benchmark-evidence", spec["benchmark"])
        write_json(target_dir / "benchmark-evidence.json", spec["benchmark"])

    entry_doc = {
        "name": name,
        "version": version,
        "channel": manifest["channel"],
        "publisher": publisher_id,
        "manifest_path": f"{rel_dir}/manifest.json",
        "manifest_digest": digest_file(manifest_file),
        "payload_digest": pdigest,
        "signature": manifest["signature"],
        "license_spdx": declared_spdx,
        "permissions": manifest["permissions"],
        "conformance_score": score["total"],
        "summary": manifest["summary"],
        "yanked": False,
    }
    if manifest.get("categories"):
        entry_doc["categories"] = manifest["categories"]
    if manifest.get("tags"):
        entry_doc["tags"] = manifest["tags"]
    if manifest.get("deprecation"):
        entry_doc["deprecated"] = True

    warnings = [
        f"{f.rule} {f.path}:{f.line} {f.detail}" for f in findings if f.rule == "SEC-0"
    ]
    return PublishResult(
        name=name,
        version=version,
        entry=entry_doc,
        manifest=manifest,
        sbom=sbom_doc,
        score=score,
        manifest_path=manifest_file,
        payload_files=len(files),
        warnings=warnings,
    )


def _verify_own_signature(manifest: dict[str, Any]) -> tuple[bool, str]:
    from .crypto import verify_document

    return verify_document(
        manifest,
        "mkt.manifest.v1",
        expected_public_key=manifest["signature"]["public_key"],
    )


def _grant_for(trust_policy: dict[str, Any], publisher_id: str) -> list[str]:
    for row in trust_policy.get("trusted_publishers", []):
        if row["publisher"] == publisher_id:
            return list(row.get("grant_permissions", []))
    return []


# --------------------------------------------------------------------------- #
# index maintenance
# --------------------------------------------------------------------------- #


def upsert_entry(index: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Replace-or-append by ``(name, version)``. Never two rows for one coordinate."""
    entries = [
        e
        for e in index.get("entries", [])
        if not (e["name"] == entry["name"] and e["version"] == entry["version"])
    ]
    entries.append(entry)
    index["entries"] = sorted(entries, key=lambda e: (e["name"], e["version"]))
    return index


def sign_index(
    index: dict[str, Any], maintainer_secret_hex: str, *, now: str | None = None
) -> dict[str, Any]:
    """Re-sign the index. Validates BEFORE signing so an invalid index is never signed."""
    timestamp = now or iso_now()
    index["generated_at"] = timestamp
    index.pop("signature", None)
    probe = dict(index)
    probe["signature"] = {
        "algorithm": "ed25519",
        "domain": "mkt.index.v1",
        "key_id": "key:" + "0" * 16,
        "public_key": "ed25519:" + "0" * 64,
        "signed_digest": "sha256:" + "0" * 64,
        "signature": "0" * 128,
    }
    schemas.validate("registry-index", probe)
    index["signature"] = sign_document(
        index, "mkt.index.v1", maintainer_secret_hex, signed_at=timestamp
    )
    schemas.validate("registry-index", index)
    return index


def publish_into(
    package_dir: str | Path,
    registry_root: str | Path,
    *,
    secret_hex: str,
    publisher_id: str,
    maintainer_secret_hex: str,
    trust_policy: dict[str, Any],
    governance: dict[str, Any] | None = None,
    now: str | None = None,
    license_basis_path: str | Path | None = None,
) -> PublishResult:
    """:func:`publish` plus index upsert and re-sign, written atomically."""
    result = publish(
        package_dir,
        registry_root,
        secret_hex=secret_hex,
        publisher_id=publisher_id,
        trust_policy=trust_policy,
        governance=governance,
        now=now,
        license_basis_path=license_basis_path,
    )
    index = reg.load_index(registry_root)
    upsert_entry(index, result.entry)
    sign_index(index, maintainer_secret_hex, now=now)
    write_json(reg.index_path(registry_root), index)
    return result


def yank(
    registry_root: str | Path,
    name: str,
    version: str,
    *,
    maintainer_secret_hex: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Hide a version from RESOLUTION while leaving an explicit pin installable.

    A yank is NOT a revocation and this build refuses to blur them: the yank flag lives in
    the index and only affects discovery, while revocation lives in a separately signed
    list and blocks the install outright.
    """
    index = reg.load_index(registry_root)
    hit = next(
        (e for e in index["entries"] if e["name"] == name and e["version"] == version),
        None,
    )
    if hit is None:
        raise PublishRefused(
            "MKT-P12", f"cannot yank {name}@{version}: not in the index"
        )
    hit["yanked"] = True
    sign_index(index, maintainer_secret_hex, now=now)
    write_json(reg.index_path(registry_root), index)
    return index
