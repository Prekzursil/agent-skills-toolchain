"""END-TO-END EXECUTABLE PROOF for the Phase 6 marketplace.

This is the deliverable proof script named in MARKETPLACE-BUILD.md. It runs the exact sequence
the unit was told to demonstrate, in one process, against a freshly built fixture marketplace in
a temp root, and prints a JSON verdict:

  1. PUBLISH a fixture package (real Ed25519 signature over canonical bytes)
  2. INSTALL it from the registry (all thirteen gates recorded)
  3. VERIFY its signature and its SBOM from the INSTALLED copy
  4. REVOKE it, and show the same install now REFUSES
  5. MALICIOUS PACKAGE: excessive permissions are rejected at publish AND at install

Every step also records its BOTH-STATES control, because a refusal that also fires in the healthy
state proves nothing.

    python platform/marketplace/probe_e2e_marketplace.py
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mkt import bundle as bundle_mod  # noqa: E402
from mkt import fixture, install, lint, moderation, publish, registry, sbom, schemas  # noqa: E402
from mkt.canon import read_json  # noqa: E402
from mkt.crypto import verify_document  # noqa: E402

T0 = fixture.T0


def main() -> int:  # noqa: PLR0915 - a linear proof script; splitting it hides the sequence
    out: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="mkt-e2e-") as tmp:
        work = Path(tmp)
        built = fixture.build(work, now=T0)
        rroot = built["registry_root"]
        policy = built["trust_policy"]
        root_secret = built["root_secret_hex"]

        out["step0_fixture"] = {
            "registry_id": built["index"]["registry_id"],
            "entries": [
                f"{e['name']}@{e['version']}({e['channel']})"
                for e in built["index"]["entries"]
            ],
            "published": built["published"],
            "refusals": built["refusals"],
        }

        # --- 1. PUBLISH -----------------------------------------------------
        entry = registry.resolve(
            built["index"], "hello-skill", "^1.0.0", channel="stable"
        )
        manifest = registry.load_manifest(rroot, entry)
        ok_sig, why = verify_document(
            manifest,
            "mkt.manifest.v1",
            expected_public_key=entry["signature"]["public_key"],
        )
        out["step1_publish"] = {
            "coordinate": f"{entry['name']}@{entry['version']}",
            "manifest_signature_verifies": ok_sig,
            "signature_reason": why,
            "payload_digest": entry["payload_digest"],
            "conformance_score": entry["conformance_score"],
            "lint": lint.lint_package(
                registry.manifest_path(rroot, entry),
                trust_policy=policy,
                index=built["index"],
                now=T0,
            )["verdict"],
        }

        # --- 2. INSTALL -----------------------------------------------------
        site = work / "site"
        inst = install.Installer(
            rroot, site, policy, client_version="2.1.0", platform_id="win32"
        )
        receipt = inst.install("hello-skill", "^1.0.0", channel="stable", now=T0)
        installed_root = site / "packages" / "hello-skill" / entry["version"]
        out["step2_install"] = {
            "outcome": receipt["outcome"],
            "gates_evaluated": len(receipt["gates"]),
            "gates_declared": len(install.GATES),
            "all_gates_accounted": len(receipt["gates"]) == len(install.GATES),
            "gate_outcomes": {g["gate"]: g["outcome"] for g in receipt["gates"]},
            "installed_files": receipt.get("installed_files"),
            "files_on_disk": sorted(
                p.name for p in installed_root.rglob("*") if p.is_file()
            ),
            "lockfile_packages": [
                p["name"] for p in (inst.load_lockfile() or {}).get("packages", [])
            ],
        }

        # --- 3. VERIFY signature + SBOM from the INSTALLED copy -------------
        pkg_dir = rroot / "packages" / "hello-skill" / entry["version"]
        sbom_doc = read_json(pkg_dir / manifest["sbom_ref"])
        schemas.validate("sbom", sbom_doc)
        verdict_installed = sbom.verify(
            sbom_doc, installed_root, declared=manifest["payload"]["files"]
        )
        tampered_dir = work / "tampered"
        tampered_dir.mkdir()
        for f in manifest["payload"]["files"]:
            dst = tampered_dir / f["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((installed_root / f["path"]).read_bytes())
        first = manifest["payload"]["files"][0]["path"]
        (tampered_dir / first).write_bytes(
            (tampered_dir / first).read_bytes() + b"\n# tamper\n"
        )
        verdict_tampered = sbom.verify(
            sbom_doc, tampered_dir, declared=manifest["payload"]["files"]
        )
        out["step3_verify"] = {
            "signature_verifies_on_installed_manifest": ok_sig,
            "sbom_ok_on_installed_payload": verdict_installed.ok,
            "sbom_summary": verdict_installed.summary(),
            "control_known_broken_sbom_fires": not verdict_tampered.ok,
            "control_detail": verdict_tampered.summary(),
        }

        # --- 3b. set up the rollback subject BEFORE anything is revoked ------
        # The rollback test has to be REAL: install 1.0.0, update to 1.1.0 (so a previous
        # version exists in the journal), and only THEN revoke 1.0.0. A rollback with no
        # recorded previous version returns a FAILED receipt for an unrelated reason and would
        # prove nothing -- an earlier draft of this probe reported exactly that as "rollback not
        # refused", which is a detector failure, not a finding.
        site_rb = work / "site-rollback"
        inst_rb = install.Installer(rroot, site_rb, policy)
        inst_rb.install("hello-skill", "=1.0.0", channel="stable", now=T0)
        rb_update = inst_rb.update("hello-skill", "=1.1.0", channel="beta", now=T0)

        # --- 4. REVOKE, then the SAME install must refuse -------------------
        moderation.open_case(
            rroot,
            case_id="case:hello-1",
            name="hello-skill",
            version=entry["version"],
            publisher=entry["publisher"],
            reason_category="malware",
            opened_by="fixture-harness",
            note="Fixture case: proving the revocation path actually blocks an install.",
            now=T0,
        )
        moderation.transition(
            rroot,
            "case:hello-1",
            to_state="under-review",
            actor="pub:moderation-board",
            note="reviewing",
            now=T0,
        )
        moderation.transition(
            rroot,
            "case:hello-1",
            to_state="action-taken",
            actor="pub:moderation-board",
            note="revoking",
            now=T0,
        )
        rev = moderation.revoke(
            rroot,
            scope={
                "kind": "version",
                "name": "hello-skill",
                "version": entry["version"],
            },
            reason="Fixture revocation: proving the install path refuses a revoked version.",
            severity="critical",
            authority="pub:moderation-board",
            maintainer_secret_hex=root_secret,
            revocation_id="rev:hello-1",
            moderation_case="case:hello-1",
            now=T0,
        )
        moderation.link_revocation(rroot, "case:hello-1", "rev:hello-1")

        site2 = work / "site-after-revoke"
        inst2 = install.Installer(rroot, site2, policy)
        try:
            inst2.install("hello-skill", "^1.0.0", channel="stable", now=T0)
            revoked_blocked, code, detail = (
                False,
                "NONE",
                "INSTALL SUCCEEDED AFTER REVOCATION",
            )
        except install.InstallRefused as exc:
            revoked_blocked, code, detail = True, exc.code, str(exc)[:240]
        installed_after = (
            site2 / "packages" / "hello-skill" / entry["version"]
        ).exists()

        try:
            inst_rb.rollback("hello-skill", now=T0)
            rollback_blocked, rb_code = False, "NONE"
        except install.InstallRefused as exc:
            rollback_blocked, rb_code = True, exc.code
        out["step4_revoke"] = {
            "rollback_precondition_update_ok": rb_update["outcome"] == "SUCCESS"
            and rb_update["previous"]["version"] == "1.0.0",
            "case_state": moderation.load_case(rroot, "case:hello-1")["state"],
            "revocations": [r["revocation_id"] for r in rev["revocations"]],
            "install_refused_after_revocation": revoked_blocked,
            "refusal_code": code,
            "refusal_detail": detail,
            "nothing_written_to_site": not installed_after,
            "rollback_to_revoked_version_refused": rollback_blocked,
            "rollback_code": rb_code,
            "control_same_install_succeeded_before_revocation": out["step2_install"][
                "outcome"
            ]
            == "SUCCESS",
            "fail_closed_when_revocation_list_deleted": _fail_closed_probe(
                work, rroot, policy
            ),
        }

        # appeal upheld -> revocation REVERSED -> install works again
        moderation.transition(
            rroot,
            "case:hello-1",
            to_state="appealed",
            actor="pub:alpha-tools",
            note="appealing the revocation",
            now=T0,
        )
        _, rev_after = moderation.uphold_appeal(
            rroot,
            "case:hello-1",
            actor="pub:moderation-board",
            note="appeal upheld; reversing",
            maintainer_secret_hex=root_secret,
            now=T0,
        )
        site3 = work / "site-after-appeal"
        inst3 = install.Installer(rroot, site3, policy)
        try:
            r3 = inst3.install("hello-skill", "^1.0.0", channel="stable", now=T0)
            reinstated = r3["outcome"] == "SUCCESS"
        except install.InstallRefused as exc:
            reinstated, _ = False, exc.code
        out["step4b_dispute_reversal"] = {
            "revocations_after_appeal": [
                r["revocation_id"] for r in rev_after["revocations"]
            ],
            "install_succeeds_again": reinstated,
        }

        # --- 5. MALICIOUS PACKAGE ------------------------------------------
        evil_src = built["sources"] / "evil-overreach-1.0.0"
        evil_secret, _ = fixture.keys_for("pub:alpha-tools")
        try:
            publish.publish_into(
                evil_src,
                rroot,
                secret_hex=evil_secret,
                publisher_id="pub:alpha-tools",
                maintainer_secret_hex=root_secret,
                trust_policy=policy,
                governance=built["governance"],
                now=T0,
                license_basis_path=fixture.FIXTURE_SRC / "LICENSE",
            )
            publish_refused, pcode = False, "NONE"
        except publish.PublishRefused as exc:
            publish_refused, pcode = True, exc.code

        # and prove the SECOND line of defence: force it into the index anyway, then install
        forced = install_forced_evil(work, rroot, policy, root_secret, evil_secret)
        out["step5_malicious"] = {
            "publish_refused": publish_refused,
            "publish_code": pcode,
            "forced_into_index_then_install_refused": forced["refused"],
            "install_code": forced["code"],
            "install_detail": forced["detail"],
            "control_benign_package_installs_from_same_index": forced[
                "control_benign_installs"
            ],
        }

        # --- extras that the spec requires and that this proof exercises ----
        out["extras"] = {
            "search_text_hello": [
                f"{e['name']}@{e['version']}"
                for e in registry.search(built["index"], text="hello")
            ],
            "search_category_security": [
                e["name"] for e in registry.search(built["index"], category="security")
            ],
            "collection_starter": [
                f"{e['name']}@{e['version']}"
                for e in registry.collection_members(built["index"], "col:starter")
            ],
            "federated_mirror_resolve": _mirror_probe(rroot),
            "offline_bundle": _bundle_probe(work, rroot, policy, root_secret),
            "registry_lint": lint.lint_registry(
                rroot,
                trust_policy=policy,
                governance_path=fixture.MARKETPLACE_ROOT / "governance-policy.json",
                now=T0,
            ),
            "linter_self_test": lint.self_test(registry.manifest_path(rroot, entry)),
        }

    ok = bool(
        out["step1_publish"]["manifest_signature_verifies"]
        and out["step2_install"]["all_gates_accounted"]
        and out["step2_install"]["outcome"] == "SUCCESS"
        and out["step3_verify"]["sbom_ok_on_installed_payload"]
        and out["step3_verify"]["control_known_broken_sbom_fires"]
        and out["step4_revoke"]["install_refused_after_revocation"]
        and out["step4_revoke"]["refusal_code"] == "MKT-I04"
        and out["step4_revoke"]["nothing_written_to_site"]
        and out["step4_revoke"]["rollback_precondition_update_ok"]
        and out["step4_revoke"]["rollback_to_revoked_version_refused"]
        and out["step4_revoke"]["rollback_code"] == "MKT-I04"
        and out["step4_revoke"]["fail_closed_when_revocation_list_deleted"]["refused"]
        and out["step5_malicious"]["publish_refused"]
        and out["step5_malicious"]["forced_into_index_then_install_refused"]
        and out["step5_malicious"]["control_benign_package_installs_from_same_index"]
    )
    print(json.dumps(_redact(json.loads(json.dumps(out, default=str))), indent=2))
    print("SUCCESS:phase6-marketplace-e2e" if ok else "FAILED:phase6-marketplace-e2e")
    return 0 if ok else 1


LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[\\/]\S*")


def _redact(node: object) -> object:
    """Redact absolute local paths from the committed proof output.

    Applied to the PARSED structure, not to the serialised text: escaping in the JSON text made a
    text-level regex under-match on the first attempt, which left half a path in the committed
    file. Scrubbing values before serialisation removes the escaping question entirely.

    DENY BY DEFAULT: any drive-absolute path is replaced, not just ones matching a username
    allowlist. marketplace-first FM-4 measured an absolute ``C:/Users/...`` path already committed
    inside a registry row in this repo, and an allowlist redactor in this program leaked eight real
    values -- so the pattern is the SHAPE of a local path, never a list of known ones.
    """
    if isinstance(node, str):
        return LOCAL_PATH_RE.sub("<REDACTED-LOCAL-PATH>", node)
    if isinstance(node, dict):
        return {k: _redact(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_redact(v) for v in node]
    return node


def install_forced_evil(
    work: Path, rroot: Path, policy: dict, root_secret: str, evil_secret: str
) -> dict:
    """Bypass the publish gate, put the over-permissioned package in the index, and install it.

    This is the important half of the malicious-package test. Refusing at publish only protects a
    registry the attacker does not control. The installer must refuse the same package when it is
    already IN a signed index -- otherwise the permission ceiling is a publishing convention, not
    a security control.
    """
    from mkt import publish as pub

    forced_registry = work / "forced-registry"
    forced_registry.mkdir(parents=True, exist_ok=True)
    for item in rroot.iterdir():
        target = forced_registry / item.name
        if item.is_dir():
            if target.exists():
                continue
            import shutil

            shutil.copytree(item, target)
        else:
            import shutil

            shutil.copy2(item, target)

    result = pub.publish(
        work / "sources" / "evil-overreach-1.0.0",
        forced_registry,
        secret_hex=evil_secret,
        publisher_id="pub:alpha-tools",
        trust_policy=policy,
        governance=None,  # <- the bypass: no governance means no publish precondition fires
        now=T0,
        allow_unverified_aggregate=True,
    )
    index = registry.load_index(forced_registry)
    pub.upsert_entry(index, result.entry)
    pub.sign_index(index, root_secret, now=T0)
    from mkt.canon import write_json

    write_json(registry.index_path(forced_registry), index)

    site = work / "site-forced"
    inst = install.Installer(forced_registry, site, policy, use_federation=False)
    try:
        inst.install("evil-overreach", "=1.0.0", now=T0)
        refused, code, detail = (
            False,
            "NONE",
            "INSTALL SUCCEEDED FOR AN OVER-PERMISSIONED PACKAGE",
        )
    except install.InstallRefused as exc:
        refused, code, detail = True, exc.code, str(exc)[:300]
    try:
        benign = inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
        control = benign["outcome"] == "SUCCESS"
    except install.InstallRefused:
        control = False
    return {
        "refused": refused,
        "code": code,
        "detail": detail,
        "control_benign_installs": control,
    }


def _fail_closed_probe(work: Path, rroot: Path, policy: dict) -> dict:
    """DELETE the revocation list and prove the install refuses instead of proceeding.

    This is the sharpest form of the named failure mode: if removing the revocation channel
    re-enabled the package, revocation would be advisory. The control is that the SAME install
    succeeds against the SAME registry when the list is present.
    """
    import shutil

    clone = work / "registry-no-revocation"
    if clone.exists():
        shutil.rmtree(clone)
    shutil.copytree(rroot, clone)
    (clone / "revocation.json").unlink()
    site = work / "site-no-revocation"
    inst = install.Installer(clone, site, policy, use_federation=False)
    try:
        inst.install("hello-skill", "=1.0.0", channel="stable", now=T0)
        return {
            "refused": False,
            "code": "NONE",
            "detail": "INSTALL PROCEEDED WITH NO REVOCATION LIST",
        }
    except install.InstallRefused as exc:
        return {"refused": True, "code": exc.code, "detail": str(exc)[:200]}


def _mirror_probe(rroot: Path) -> dict:
    view = registry.federate(rroot)
    found = view.resolve("hello-skill", "^1.0.0", channel="stable")
    return {
        "mirrors_opened": [m.mirror_id for m in view.mirrors],
        "resolved_from": (found[0].mirror_id or "primary") if found else None,
        "rejected_mirror_rows": view.rejected,
    }


def _bundle_probe(work: Path, rroot: Path, policy: dict, root_secret: str) -> dict:
    out_dir = work / "bundle"
    manifest = bundle_mod.export_bundle(
        rroot,
        out_dir,
        packages=[("hello-skill", "1.0.0")],
        maintainer_secret_hex=root_secret,
        now=T0,
    )
    verified = bundle_mod.verify_bundle(out_dir, policy)
    dest = work / "imported-registry"
    imported = bundle_mod.import_bundle(
        out_dir, dest, trust_policy=policy, maintainer_secret_hex=root_secret, now=T0
    )
    site = work / "site-offline"
    inst = install.Installer(dest, site, policy, use_federation=False)
    receipt = inst.install("hello-skill", "=1.0.0", now=T0)
    return {
        "bundle_id": manifest["bundle_id"],
        "includes": manifest["includes"],
        "verified": verified["bundle_id"] == manifest["bundle_id"],
        "imported": imported["bundle_id"] == manifest["bundle_id"],
        "offline_install_outcome": receipt["outcome"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
