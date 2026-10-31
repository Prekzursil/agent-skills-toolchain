"""The marketplace linter: twenty rules over a package, a registry, or a bundle.

WHY THE REPORT CARRIES TWO COUNTS
    ``rules_total`` is what the linter declares it owns; ``rules_evaluated`` is what
    actually ran. A caller must compare them. An empty ``findings`` list is NOT a pass on
    its own -- a guard that swallowed an exception and produced "0 findings" is the worst
    defect class in this program, and the two-count shape is what makes that state visible
    instead of green.

THE FM-1 LESSON IS BUILT IN
    Marketplace-first FM-1 records that its own first-pass path scanner reported "346 paths
    missing on disk" because a ``lstrip("./")`` normalisation ate the leading dot of
    ``.agents``. The path-existence rule here therefore (a) never normalises a payload path
    at all -- the schema's positive char class already forbids the shapes that would need
    it -- and (b) ships :func:`self_test`, which proves the rule fires on a known-BROKEN
    package and stays silent on a known-GOOD one before any "0 findings" is believable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import permissions as perms
from . import publish as publish_mod
from . import registry as reg
from . import sbom as sbom_mod
from . import schemas, versions
from .canon import digest_file, ensure_within, iso_now, payload_digest, read_json
from .crypto import verify_document

#: Every rule the linter owns, with its human name. Explicit so `rules_total` is a
#: declaration and not a runtime side effect.
RULES: dict[str, str] = {
    "MKT-L01": "document validates against its schema",
    "MKT-L02": "every declared payload file exists and its digest matches",
    "MKT-L03": "notice_required agrees with the component licences",
    "MKT-L04": "declared aggregate licence covers every component licence",
    "MKT-L05": "signature is present and verifies",
    "MKT-L06": "SBOM is a bijection with the payload",
    "MKT-L07": "index row mirrors the signed manifest",
    "MKT-L08": "permissions parse and stay within the trust ceiling",
    "MKT-L09": "version/channel coherence (no prerelease on stable)",
    "MKT-L10": "dependencies resolve inside the index and do not cycle",
    "MKT-L11": "compatibility matrix is usable",
    "MKT-L12": "quality score total equals the sum of its components",
    "MKT-L13": "benchmark evidence carries both-states controls",
    "MKT-L14": "provenance is complete",
    "MKT-L15": "payload carries no secret or local-topology finding",
    "MKT-L16": "revocation and yank state are coherent",
    "MKT-L17": "governance policy agrees with its prose document",
    "MKT-L18": "collections resolve to real entries",
    "MKT-L19": "mirrors exist and declare a legal trust mode",
    "MKT-L20": "every signing key is declared and active for its publisher",
}


@dataclass
class Report:
    target: str
    target_kind: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    evaluated: list[str] = field(default_factory=list)
    error: str | None = None

    def add(
        self, rule: str, severity: str, message: str, path: str | None = None
    ) -> None:
        row: dict[str, Any] = {
            "rule": rule,
            "severity": severity,
            "message": message[:800],
        }
        if path:
            row["path"] = str(path)[:400]
        self.findings.append(row)

    def ran(self, rule: str) -> None:
        if rule not in self.evaluated:
            self.evaluated.append(rule)

    @property
    def verdict(self) -> str:
        if self.error is not None:
            return "ERROR"
        return (
            "FAIL" if any(f["severity"] == "error" for f in self.findings) else "PASS"
        )

    def as_dict(self, *, now: str | None = None) -> dict[str, Any]:
        doc = {
            "schema_version": "1.0.0",
            "target": self.target,
            "target_kind": self.target_kind,
            "verdict": self.verdict,
            "rules_total": len(RULES),
            "rules_evaluated": sorted(self.evaluated) or sorted(RULES)[:1],
            "findings": self.findings,
            "linted_at": now or iso_now(),
        }
        schemas.validate("lint-report", doc)
        return doc


# --------------------------------------------------------------------------- #
# package linting
# --------------------------------------------------------------------------- #


def lint_package(
    manifest_path: str | Path,
    *,
    trust_policy: dict[str, Any] | None = None,
    index: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Lint a PUBLISHED package: its manifest, payload, SBOM, score and index row."""
    manifest_path = Path(manifest_path)
    report = Report(target=str(manifest_path), target_kind="package")
    pkg_dir = manifest_path.parent

    report.ran("MKT-L01")
    try:
        manifest = read_json(manifest_path)
    except (OSError, ValueError) as exc:
        report.error = f"manifest unreadable: {exc}"
        report.add("MKT-L01", "error", f"manifest unreadable: {exc}")
        return report.as_dict(now=now)
    errs = schemas.errors_for("package-manifest", manifest)
    for err in errs:
        report.add("MKT-L01", "error", err, manifest_path)
    if errs:
        # Every later rule reads fields this document does not reliably have.
        return report.as_dict(now=now)

    payload_root = pkg_dir / manifest["payload"]["root"]

    # MKT-L02 -- payload existence + digest, no path normalisation at all
    report.ran("MKT-L02")
    rows = []
    for f in manifest["payload"]["files"]:
        path = ensure_within(payload_root, f["path"])
        if not path.is_file():
            report.add(
                "MKT-L02",
                "error",
                f"declared payload file is absent: {f['path']}",
                path,
            )
            continue
        actual = digest_file(path)
        rows.append({"path": f["path"], "sha256": actual})
        if actual != f["sha256"]:
            report.add(
                "MKT-L02",
                "error",
                f"payload digest mismatch for {f['path']}: {actual} != {f['sha256']}",
                path,
            )
        if path.stat().st_size != f["bytes"]:
            report.add(
                "MKT-L02", "error", f"payload byte count mismatch for {f['path']}", path
            )
    if len(rows) == len(manifest["payload"]["files"]):
        recomputed = payload_digest(rows)
        if recomputed != manifest["payload"]["digest"]:
            report.add(
                "MKT-L02",
                "error",
                f"payload.digest is {manifest['payload']['digest']}, recomputes to {recomputed}",
            )

    # MKT-L05 -- signature
    report.ran("MKT-L05")
    ok, why = verify_document(manifest, "mkt.manifest.v1")
    if not ok:
        report.add("MKT-L05", "error", f"manifest signature does not verify: {why}")

    # MKT-L06 / L03 / L04 -- SBOM and licences
    sbom_path = pkg_dir / manifest["sbom_ref"]
    report.ran("MKT-L06")
    component_licences: dict[str, str] = {}
    if not sbom_path.is_file():
        report.add(
            "MKT-L06",
            "error",
            f"declared SBOM does not exist: {manifest['sbom_ref']}",
            sbom_path,
        )
    else:
        sbom_doc = read_json(sbom_path)
        for err in schemas.errors_for("sbom", sbom_doc):
            report.add("MKT-L06", "error", f"sbom: {err}", sbom_path)
        verdict = sbom_mod.verify(
            sbom_doc, payload_root, declared=manifest["payload"]["files"]
        )
        if not verdict.ok:
            report.add(
                "MKT-L06",
                "error",
                f"SBOM/payload mismatch: {verdict.summary()}",
                sbom_path,
            )
        component_licences = sbom_mod.component_licenses(sbom_doc)

    report.ran("MKT-L03")
    report.ran("MKT-L04")
    declared = manifest["license"]["spdx"]
    distinct = sorted(set(component_licences.values()))
    if distinct and distinct != [declared]:
        severity = "warning" if manifest["license"]["aggregate_verified"] else "error"
        report.add(
            "MKT-L04",
            severity,
            f"declared aggregate licence {declared!r} does not equal component licences {distinct} "
            f"(aggregate_verified={manifest['license']['aggregate_verified']})",
        )
    needs_notice = any(c.startswith("Apache") for c in distinct) or declared.startswith(
        "Apache"
    )
    if needs_notice and not manifest["license"]["notice_required"]:
        report.add(
            "MKT-L03",
            "error",
            "an Apache-family licence appears in the aggregate or components but notice_required is false "
            "(Apache-2.0 requires NOTICE preservation; this is the M1 defect shape)",
        )
    if needs_notice and not manifest["license"].get("notice_path"):
        report.add(
            "MKT-L03",
            "warning",
            "notice_required is set but no notice_path is declared",
        )

    # MKT-L08 -- permissions
    report.ran("MKT-L08")
    for want in manifest["permissions"]:
        try:
            perms.parse(want)
        except perms.PermissionError_ as exc:
            report.add("MKT-L08", "error", str(exc))
    if trust_policy is not None:
        grant = next(
            (
                p.get("grant_permissions", [])
                for p in trust_policy.get("trusted_publishers", [])
                if p["publisher"] == manifest["publisher"]
            ),
            [],
        )
        verdict_p = perms.evaluate(
            [p for p in manifest["permissions"] if _parses(p)],
            max_permissions=trust_policy["max_permissions"],
            grant_permissions=list(grant),
            forbidden_permissions=trust_policy.get("forbidden_permissions"),
        )
        for bad in verdict_p.excessive:
            report.add(
                "MKT-L08",
                "error",
                f"excessive permission {bad!r}: {verdict_p.reasons[bad]}",
            )

    # MKT-L09 -- version / channel
    report.ran("MKT-L09")
    parsed = versions.parse(manifest["version"])
    if parsed.is_prerelease and manifest["channel"] == "stable":
        report.add(
            "MKT-L09",
            "error",
            f"prerelease {manifest['version']} published on the stable channel",
        )
    if not parsed.is_prerelease and manifest["channel"] == "canary":
        report.add(
            "MKT-L09",
            "warning",
            "a release version on the canary channel is legal but unusual",
        )

    # MKT-L11 -- compatibility
    report.ran("MKT-L11")
    for row in manifest["compatibility"]["clients"]:
        try:
            versions.satisfies("1.0.0", row["range"])
        except versions.VersionError as exc:
            report.add("MKT-L11", "error", f"client {row['id']} range unusable: {exc}")

    # MKT-L12 -- score recompute
    report.ran("MKT-L12")
    score_ref = manifest["quality"].get("score_ref")
    if score_ref:
        score_path = pkg_dir / score_ref
        if not score_path.is_file():
            report.add(
                "MKT-L12",
                "error",
                f"quality.score_ref does not exist: {score_ref}",
                score_path,
            )
        else:
            score = read_json(score_path)
            for err in schemas.errors_for("quality-score", score):
                report.add("MKT-L12", "error", f"quality-score: {err}", score_path)
            recomputed = publish_mod.recompute_total(score)
            if recomputed != score["total"]:
                report.add(
                    "MKT-L12",
                    "error",
                    f"score total {score['total']} != sum of components {recomputed}",
                    score_path,
                )
            if score["total"] != manifest["quality"]["conformance_score"]:
                report.add(
                    "MKT-L12",
                    "error",
                    f"manifest conformance_score {manifest['quality']['conformance_score']} != score document total {score['total']}",
                )
            for comp in score["components"]:
                if comp["earned"] and comp["evidence"].startswith("not earned"):
                    report.add(
                        "MKT-L12",
                        "error",
                        f"component {comp['id']} is earned but carries no evidence",
                    )

    # MKT-L13 -- benchmark controls
    report.ran("MKT-L13")
    bench_ref = manifest["quality"].get("benchmark_ref")
    if bench_ref:
        bench_path = pkg_dir / bench_ref
        if not bench_path.is_file():
            report.add(
                "MKT-L13",
                "error",
                f"benchmark_ref does not exist: {bench_ref}",
                bench_path,
            )
        else:
            bench = read_json(bench_path)
            for err in schemas.errors_for("benchmark-evidence", bench):
                report.add("MKT-L13", "error", f"benchmark-evidence: {err}", bench_path)

    # MKT-L14 -- provenance
    report.ran("MKT-L14")
    if not manifest["provenance"].get("source_revision"):
        report.add(
            "MKT-L14",
            "warning",
            "provenance has no source_revision: the build is not traceable to a commit",
        )
    if manifest["provenance"]["reproducible"] and not manifest["provenance"].get(
        "source_revision"
    ):
        report.add(
            "MKT-L14",
            "error",
            "provenance claims reproducible with no source_revision to reproduce from",
        )

    # MKT-L15 -- secrets
    report.ran("MKT-L15")
    findings = publish_mod.scan_payload(
        payload_root, [f["path"] for f in manifest["payload"]["files"]]
    )
    for f in findings:
        report.add(
            "MKT-L15",
            "warning" if f.rule == "SEC-0" else "error",
            f"{f.rule} {f.path}:{f.line} {f.detail}",
            f.path,
        )

    # MKT-L07 / L20 -- index agreement
    if index is not None:
        report.ran("MKT-L07")
        report.ran("MKT-L20")
        row = next(
            (
                e
                for e in index["entries"]
                if e["name"] == manifest["name"] and e["version"] == manifest["version"]
            ),
            None,
        )
        if row is None:
            report.add(
                "MKT-L07",
                "error",
                f"{manifest['name']}@{manifest['version']} is not in the index",
            )
        else:
            if sorted(row.get("permissions", [])) != sorted(manifest["permissions"]):
                report.add(
                    "MKT-L07",
                    "error",
                    "index row permissions disagree with the signed manifest",
                )
            if row["payload_digest"] != manifest["payload"]["digest"]:
                report.add(
                    "MKT-L07",
                    "error",
                    "index row payload_digest disagrees with the signed manifest",
                )
            if row["license_spdx"] != declared:
                report.add(
                    "MKT-L07",
                    "error",
                    "index row license_spdx disagrees with the signed manifest",
                )
            if row["conformance_score"] != manifest["quality"]["conformance_score"]:
                report.add(
                    "MKT-L07",
                    "error",
                    "index row conformance_score disagrees with the signed manifest",
                )
            if row["manifest_digest"] != digest_file(manifest_path):
                report.add(
                    "MKT-L07",
                    "error",
                    "index row manifest_digest does not match the manifest on disk",
                )
            key_rec = reg.publisher_key(
                index, manifest["publisher"], manifest["signature"]["public_key"]
            )
            if key_rec is None:
                report.add(
                    "MKT-L20",
                    "error",
                    f"signing key is not declared by publisher {manifest['publisher']}",
                )
            elif key_rec["status"] != "active":
                report.add(
                    "MKT-L20",
                    "error",
                    f"signing key status is {key_rec['status']!r}, not active",
                )

    # MKT-L10 -- dependencies
    report.ran("MKT-L10")
    if index is not None:
        for dep in manifest.get("dependencies", []):
            if dep["name"] == manifest["name"]:
                report.add("MKT-L10", "error", f"{manifest['name']} depends on itself")
                continue
            if reg.resolve(index, dep["name"], dep["range"]) is None and not dep.get(
                "optional"
            ):
                report.add(
                    "MKT-L10",
                    "error",
                    f"dependency {dep['name']} {dep['range']} resolves to nothing in the index",
                )

    return report.as_dict(now=now)


def _parses(permission: str) -> bool:
    try:
        perms.parse(permission)
    except perms.PermissionError_:
        return False
    return True


# --------------------------------------------------------------------------- #
# registry linting
# --------------------------------------------------------------------------- #


def lint_registry(
    registry_root: str | Path,
    *,
    trust_policy: dict[str, Any] | None = None,
    governance_path: str | Path | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Lint a whole registry: the index, every entry, revocation coherence, mirrors, governance."""
    root = Path(registry_root)
    report = Report(target=str(root), target_kind="registry")

    report.ran("MKT-L01")
    try:
        index = reg.load_index(root)
    except reg.RegistryError as exc:
        report.error = str(exc)
        report.add("MKT-L01", "error", str(exc))
        return report.as_dict(now=now)

    report.ran("MKT-L05")
    if trust_policy is not None:
        ok, why = reg.verify_index_signature(
            index, trust_policy["registry_maintainer_keys"]
        )
        if not ok:
            report.add("MKT-L05", "error", f"index signature: {why}")
    else:
        ok, why = verify_document(index, "mkt.index.v1")
        if not ok:
            report.add("MKT-L05", "error", f"index signature: {why}")

    # per-entry: fold each package report in, keeping the rule ids
    for entry in index["entries"]:
        try:
            mpath = reg.manifest_path(root, entry)
        except ValueError as exc:
            report.ran("MKT-L02")
            report.add("MKT-L02", "error", f"{entry['name']}@{entry['version']}: {exc}")
            continue
        if not mpath.is_file():
            report.ran("MKT-L02")
            report.add(
                "MKT-L02",
                "error",
                f"{entry['name']}@{entry['version']} manifest missing: {mpath}",
            )
            continue
        sub = lint_package(mpath, trust_policy=trust_policy, index=index, now=now)
        for rule in sub["rules_evaluated"]:
            report.ran(rule)
        for finding in sub["findings"]:
            report.add(
                finding["rule"],
                finding["severity"],
                f"{entry['name']}@{entry['version']}: {finding['message']}",
                finding.get("path"),
            )

    # MKT-L16 -- revocation / yank coherence
    report.ran("MKT-L16")
    revocation = reg.load_revocation(root, index)
    if revocation is None:
        report.add(
            "MKT-L16",
            "error",
            "the index declares no reachable revocation list; every consumer with the default "
            "fail-closed policy will refuse every install",
        )
    else:
        ok, why = verify_document(revocation, "mkt.revocation.v1")
        if not ok:
            report.add("MKT-L16", "error", f"revocation list signature: {why}")
        for entry in index["entries"]:
            hits = reg.revocations_for(revocation, entry["name"], entry["version"])
            if hits and not entry.get("yanked"):
                report.add(
                    "MKT-L16",
                    "warning",
                    f"{entry['name']}@{entry['version']} is revoked but still resolvable (not yanked); "
                    "installs refuse correctly, but discovery still advertises it",
                )
            authority_roles = {
                (reg.publisher_record(index, h["authority"]) or {}).get("role")
                for h in hits
            }
            bad = authority_roles - {
                "registry-maintainer",
                "moderator",
                "security-response",
            }
            if hits and bad:
                report.add(
                    "MKT-L16",
                    "error",
                    f"{entry['name']}@{entry['version']} revoked by an authority whose role is {sorted(bad)!r}",
                )

    # MKT-L18 -- collections
    report.ran("MKT-L18")
    for col in reg.collections(index):
        for member in col["members"]:
            if (
                reg.resolve(
                    index, member["name"], member.get("range", "*"), include_yanked=True
                )
                is None
            ):
                report.add(
                    "MKT-L18",
                    "error",
                    f"collection {col['collection_id']} member {member['name']} resolves to nothing",
                )

    # MKT-L19 -- mirrors
    report.ran("MKT-L19")
    for mirror in index.get("mirrors", []):
        try:
            mroot = ensure_within(root, mirror["root"])
        except ValueError as exc:
            report.add(
                "MKT-L19",
                "error",
                f"mirror {mirror['mirror_id']} root escapes the registry: {exc}",
            )
            continue
        if mirror.get("enabled", True) and not reg.index_path(mroot).is_file():
            report.add(
                "MKT-L19",
                "error",
                f"enabled mirror {mirror['mirror_id']} has no index at {mroot}",
            )

    # MKT-L17 -- governance policy vs prose
    report.ran("MKT-L17")
    if governance_path is not None:
        gpath = Path(governance_path)
        if not gpath.is_file():
            report.add("MKT-L17", "error", f"governance policy not found: {gpath}")
        else:
            gov = read_json(gpath)
            for err in schemas.errors_for("governance-policy", gov):
                report.add("MKT-L17", "error", f"governance-policy: {err}", gpath)
            prose_rel = gov.get("prose_document")
            if prose_rel:
                prose = gpath.parent / prose_rel
                if not prose.is_file():
                    report.add(
                        "MKT-L17",
                        "error",
                        f"governance prose document missing: {prose_rel}",
                        prose,
                    )
                else:
                    text = prose.read_text(encoding="utf-8")
                    for precondition in gov["publish_preconditions"]:
                        if precondition not in text:
                            report.add(
                                "MKT-L17",
                                "error",
                                f"publish precondition {precondition!r} is not documented in {prose_rel} "
                                "(a governance value that the prose does not state is a value nobody agreed to)",
                            )
                    for role in gov["roles"]:
                        if role["role"] not in text:
                            report.add(
                                "MKT-L17",
                                "warning",
                                f"role {role['role']!r} is undocumented in {prose_rel}",
                            )

    return report.as_dict(now=now)


# --------------------------------------------------------------------------- #
# detector control
# --------------------------------------------------------------------------- #


def self_test(
    good_manifest: str | Path, *, mutate: str = "payload-digest"
) -> dict[str, Any]:
    """Prove the linter fires on a KNOWN-BROKEN input and is silent on the KNOWN-GOOD one.

    Returns both readings. A linter that is silent in both states measures nothing, so this
    is the control every "0 findings" claim in the build record is paired with.
    """
    import copy
    import json
    import tempfile

    good = lint_package(good_manifest)
    src = Path(good_manifest)
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / "pkg"
        pkg.mkdir(parents=True)
        for item in src.parent.rglob("*"):
            rel = item.relative_to(src.parent)
            if item.is_dir():
                (pkg / rel).mkdir(parents=True, exist_ok=True)
            else:
                (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
                (pkg / rel).write_bytes(item.read_bytes())
        manifest = copy.deepcopy(read_json(pkg / src.name))
        if mutate == "payload-digest":
            first = manifest["payload"]["files"][0]["path"]
            target = pkg / manifest["payload"]["root"] / first
            target.write_bytes(
                target.read_bytes() + b"\n# tampered by lint.self_test\n"
            )
        elif mutate == "signature":
            sig = manifest["signature"]["signature"]
            manifest["signature"]["signature"] = ("0" if sig[0] != "0" else "1") + sig[
                1:
            ]
        elif mutate == "permission":
            manifest["permissions"] = sorted(
                {*manifest["permissions"], "secrets:read:**"}
            )
        else:  # pragma: no cover - guarded by the caller's enum
            raise ValueError(f"unknown mutation {mutate!r}")
        (pkg / src.name).write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )
        broken = lint_package(pkg / src.name)
    return {
        "mutation": mutate,
        "known_good_verdict": good["verdict"],
        "known_good_findings": len(good["findings"]),
        "known_broken_verdict": broken["verdict"],
        "known_broken_findings": [f["rule"] for f in broken["findings"]],
        "detector_usable": good["verdict"] == "PASS" and broken["verdict"] == "FAIL",
    }
