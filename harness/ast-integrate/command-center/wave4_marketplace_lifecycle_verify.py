"""WAVE 4 -- INDEPENDENT verification of the Phase 6 marketplace lifecycle.

INDEPENDENCE
    The build lane's own proof (``platform/marketplace/probe_e2e_marketplace.py``) calls the
    Python API in-process: ``install.Installer(...).install(...)``. This probe drives the
    SHIPPED CLI through ``subprocess`` -- ``python -m mkt <verb>`` -- and reads the process
    EXIT CODE and the terminal ``SUCCESS:``/``FAILED:`` marker. Different entry point,
    different transport, different pass signal. Where no CLI verb exists (there is no
    ``mkt verify``), that gap is recorded as a finding rather than papered over, and the
    library is used only for the cryptographic primitive itself.

BOTH-STATES DISCIPLINE
    Every refusal claimed here is paired with the SAME command succeeding on a valid input.
    A refusal that was never seen to succeed proves nothing.

    python command-center/wave4_marketplace_lifecycle_verify.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
MKT_DIR = REPO / "platform" / "marketplace"
CC = REPO / "command-center"
OUT_JSON = CC / "WAVE4-MARKETPLACE-LIFECYCLE.json"
LICENSE_BASIS = MKT_DIR / "fixture" / "LICENSE"
PY = sys.executable

RESULT: dict[str, Any] = {
    "unit": "verify/marketplace-lifecycle",
    "state": "RUNNING - write-as-you-go; any UNKNOWN below was not reached",
    "probe": "command-center/wave4_marketplace_lifecycle_verify.py",
    "transport": "subprocess -> python -m mkt <verb> (CLI), exit code + terminal marker",
    "checks": {
        "1_publish": "UNKNOWN - not yet measured",
        "2_install": "UNKNOWN - not yet measured",
        "3_verify_and_corrupt_signature": "UNKNOWN - not yet measured",
        "4_revoke_blocks": "UNKNOWN - not yet measured",
        "5_malicious_permissions": "UNKNOWN - not yet measured",
        "6_lockfile_determinism": "UNKNOWN - not yet measured",
    },
    "bypass_hunt": {},
    "commands": [],
}


def redact(text: str) -> str:
    """Local paths out of the artifact; the temp root differs every run anyway."""
    import os
    import re

    out = text.replace(str(REPO), "<REPO>").replace(
        str(REPO).replace("\\", "/"), "<REPO>"
    )
    out = re.sub(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\"' ]+", "<HOME>", out)
    out = out.replace(os.environ.get("TEMP", "%%NOTEMP%%"), "<TMP>")
    return out.replace("\\\\", "/").replace("\\", "/")


def scrub(node: Any) -> Any:
    """Redact every STRING VALUE, then serialise.

    Redacting the serialised document instead (as the first draft of this probe did) rewrites
    JSON's own backslash escapes and produces a file that will not parse -- a self-inflicted
    detector failure, caught by reading the artifact back.
    """
    if isinstance(node, str):
        return redact(node)
    if isinstance(node, dict):
        return {k: scrub(v) for k, v in node.items()}
    if isinstance(node, list):
        return [scrub(v) for v in node]
    return node


def flush() -> None:
    """Rewrite the artifact after every step. Whatever is on disk is always truthful."""
    text = json.dumps(scrub(json.loads(json.dumps(RESULT, default=str))), indent=2)
    json.loads(text)  # the artifact must parse; a broken artifact is not a result
    OUT_JSON.write_text(text, encoding="utf-8", newline="\n")


def mkt(*args: str, expect: int | None = None, label: str = "") -> dict[str, Any]:
    """Run the CLI. Returns exit code, the terminal marker, and parsed JSON if any."""
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [PY, "-m", "mkt", *args],
        cwd=str(MKT_DIR),
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = proc.stdout
    marker = next(
        (
            ln.strip()
            for ln in reversed(out.splitlines())
            if ln.startswith(("SUCCESS:", "FAILED:"))
        ),
        "",
    )
    doc: Any = None
    brace = out.find("{")
    if brace >= 0:
        try:
            doc = json.loads(out[brace : out.rfind("}") + 1])
        except ValueError:
            doc = None
    rec = {
        "label": label or args[0],
        "argv": "python -m mkt " + " ".join(redact(a) for a in args),
        "exit": proc.returncode,
        "marker": redact(marker),
        "stderr_tail": redact(proc.stderr.strip()[-400:]),
    }
    RESULT["commands"].append(rec)
    if expect is not None and proc.returncode != expect:
        rec["UNEXPECTED_EXIT"] = f"expected {expect}"
    flush()
    return {**rec, "json": doc, "stdout": out}


def code_of(res: dict[str, Any]) -> str:
    doc = res.get("json") or {}
    return str(doc.get("code") or doc.get("refusal_code") or "")


def site_has(site: Path, name: str, version: str | None = None) -> bool:
    root = site / "packages" / name
    if version:
        root = root / version
    return root.exists()


def n_files(site: Path, name: str) -> int:
    root = site / "packages" / name
    return len([p for p in root.rglob("*") if p.is_file()]) if root.exists() else 0


# --------------------------------------------------------------------------- #


def main() -> int:  # noqa: PLR0915 - a linear proof; splitting it hides the sequence
    tmp = Path(tempfile.mkdtemp(prefix="wave4-mkt-"))
    RESULT["temp_root"] = "<TMP>"
    try:
        return run(tmp)
    finally:
        RESULT["state"] = RESULT.get("state", "").replace("RUNNING", "FINISHED")
        flush()
        shutil.rmtree(tmp, ignore_errors=True)


def run(tmp: Path) -> int:  # noqa: PLR0915
    base = tmp / "base"
    fx = mkt("fixture", "--into", str(base), expect=0, label="fixture-build")
    registry = base / "registry"
    sources = base / "sources"
    RESULT["step0_fixture"] = {
        "exit": fx["exit"],
        "published": (fx["json"] or {}).get("published"),
        "refusals": (fx["json"] or {}).get("refusals"),
        "registry_index_exists": (registry / "index.json").is_file(),
    }
    flush()

    def fresh(name: str) -> Path:
        p = tmp / name
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True)
        return p

    def copy_of(src: Path, name: str) -> Path:
        dst = tmp / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        return dst

    def copy_registry(name: str) -> Path:
        return copy_of(registry, name)

    def do_install(
        reg_root: Path,
        site: Path,
        name: str,
        rng: str = "*",
        *,
        expect: int | None = None,
        extra: tuple[str, ...] = (),
        label: str = "",
        verb: str = "install",
    ) -> dict[str, Any]:
        return mkt(
            verb,
            name,
            "--registry",
            str(reg_root),
            "--site",
            str(site),
            "--range",
            rng,
            "--fixture-policy",
            *extra,
            expect=expect,
            label=label or f"{verb}-{name}{rng}",
        )

    # ---------------------------------------------------------------- 1 PUBLISH
    src = tmp / "src"
    mkt(
        "scaffold",
        "--name",
        "verify-probe",
        "--into",
        str(src),
        "--version",
        "1.0.0",
        "--channel",
        "stable",
        expect=0,
        label="scaffold",
    )
    pkg = src / "verify-probe"
    pub_args = (
        "publish",
        str(pkg),
        "--registry",
        str(registry),
        "--publisher",
        "pub:alpha-tools",
        "--fixture-key",
        "pub:alpha-tools",
        "--fixture-policy",
    )
    bad = mkt(*pub_args, expect=1, label="publish-WITHOUT-license-basis")
    good = mkt(
        *pub_args,
        "--license-basis",
        str(LICENSE_BASIS),
        expect=0,
        label="publish-WITH-license-basis",
    )
    RESULT["checks"]["1_publish"] = {
        "verdict": "PASS" if (good["exit"] == 0 and bad["exit"] == 1) else "FAIL",
        "good_state": {"exit": good["exit"], "marker": good["marker"]},
        "published": (good["json"] or {}),
        "control_bad_state": {
            "exit": bad["exit"],
            "code": code_of(bad),
            "note": "no --license-basis -> governance precondition refuses",
        },
    }
    flush()

    # ---------------------------------------------------------------- 2 INSTALL
    site = fresh("site")
    i1 = do_install(registry, site, "verify-probe", "=1.0.0", expect=0)
    i2 = do_install(registry, site, "hello-skill", "=1.0.0", expect=0)
    RESULT["checks"]["2_install"] = {
        "verdict": "PASS"
        if i1["exit"] == 0
        and i2["exit"] == 0
        and site_has(site, "verify-probe", "1.0.0")
        and site_has(site, "hello-skill", "1.0.0")
        else "FAIL",
        "temp_prefix": "<TMP>/site",
        "verify_probe_files": n_files(site, "verify-probe"),
        "hello_skill_files": n_files(site, "hello-skill"),
        "gates_evaluated": len((i2["json"] or {}).get("gates", [])),
        "state_file": (site / "state" / "installed.json").is_file(),
        "lockfile": (site / "mkt-lock.json").is_file(),
    }
    flush()

    # ------------------------------------------------- 3 VERIFY sig + SBOM
    sys.path.insert(0, str(MKT_DIR))
    from mkt import registry as reg  # noqa: PLC0415
    from mkt import sbom as sbom_mod  # noqa: PLC0415
    from mkt.canon import read_json  # noqa: PLC0415
    from mkt.crypto import verify_document  # noqa: PLC0415

    index = reg.load_index(registry)
    entry = reg.resolve(index, "hello-skill", "=1.0.0")
    manifest = reg.load_manifest(registry, entry)
    pub_key = entry["signature"]["public_key"]
    ok_real, _ = verify_document(
        manifest, "mkt.manifest.v1", expected_public_key=pub_key
    )
    forged = json.loads(json.dumps(manifest))
    sig = forged["signature"]["signature"]
    forged["signature"]["signature"] = sig[:-1] + ("a" if sig[-1] != "a" else "b")
    ok_forged, why_forged = verify_document(
        forged, "mkt.manifest.v1", expected_public_key=pub_key
    )
    pkg_dir = registry / "packages" / "hello-skill" / "1.0.0"
    sbom_doc = read_json(pkg_dir / manifest["sbom_ref"])
    installed_payload = site / "packages" / "hello-skill" / "1.0.0"
    sv = sbom_mod.verify(
        sbom_doc, installed_payload, declared=manifest["payload"]["files"]
    )
    # BOTH-STATES for the SBOM check itself: tamper one installed byte in a THROWAWAY copy
    # and require the same verifier to report a hash mismatch. A verifier that says "ok"
    # on the good input and was never shown to say "not ok" measures nothing.
    tamper_root = tmp / "sbom-tamper"
    if tamper_root.exists():
        shutil.rmtree(tamper_root)
    shutil.copytree(installed_payload, tamper_root)
    victim = next(p for p in sorted(tamper_root.rglob("*")) if p.is_file())
    victim.write_bytes(victim.read_bytes() + b"\n# wave4 tamper\n")
    sv_bad = sbom_mod.verify(
        sbom_doc, tamper_root, declared=manifest["payload"]["files"]
    )

    reg_sig = copy_registry("reg-badsig")
    m_path = reg.manifest_path(reg_sig, entry)
    doc = read_json(m_path)
    s = doc["signature"]["signature"]
    doc["signature"]["signature"] = s[:-1] + ("a" if s[-1] != "a" else "b")
    m_path.write_text(json.dumps(doc, indent=2), encoding="utf-8", newline="\n")
    bad_sig_install = do_install(
        reg_sig,
        fresh("site-badsig"),
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-CORRUPTED-signature",
    )
    good_sig_install = do_install(
        registry,
        fresh("site-goodsig"),
        "hello-skill",
        "=1.0.0",
        expect=0,
        label="install-GOOD-signature-control",
    )

    reg_sbom = copy_registry("reg-badsbom")
    sb_path = reg_sbom / "packages" / "hello-skill" / "1.0.0" / manifest["sbom_ref"]
    sb = read_json(sb_path)
    for comp in sb.get("components", []):
        for h in comp.get("hashes", []):
            h["content"] = "0" * len(h["content"])
            break
        break
    sb_path.write_text(json.dumps(sb, indent=2), encoding="utf-8", newline="\n")
    bad_sbom_install = do_install(
        reg_sbom,
        fresh("site-badsbom"),
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-CORRUPTED-sbom",
    )

    RESULT["checks"]["3_verify_and_corrupt_signature"] = {
        "verdict": "PASS"
        if (
            ok_real
            and not ok_forged
            and sv.ok
            and not sv_bad.ok
            and bad_sig_install["exit"] == 1
            and code_of(bad_sig_install) == "MKT-I03"
            and good_sig_install["exit"] == 0
            and bad_sbom_install["exit"] == 1
            and code_of(bad_sbom_install) == "MKT-I10"
        )
        else "FAIL",
        "manifest_signature_verifies": ok_real,
        "one_char_forgery_verifies": ok_forged,
        "forgery_reason": why_forged,
        "sbom": {
            "ok": sv.ok,
            "summary": sv.summary(),
            "hash_mismatch": len(sv.hash_mismatch),
            "control_tampered_payload_ok": sv_bad.ok,
            "control_tampered_hash_mismatch": len(sv_bad.hash_mismatch),
            "components": len(sbom_doc.get("components", [])),
            "spec": sbom_doc.get("bomFormat", "")
            + " "
            + sbom_doc.get("specVersion", ""),
            "note": "component hashes recomputed against the INSTALLED copy in the temp prefix",
        },
        "corrupt_signature_install": {
            "exit": bad_sig_install["exit"],
            "code": code_of(bad_sig_install),
            "nothing_landed": not site_has(tmp / "site-badsig", "hello-skill"),
        },
        "control_good_signature_install": {
            "exit": good_sig_install["exit"],
            "landed": site_has(tmp / "site-goodsig", "hello-skill", "1.0.0"),
        },
        "corrupt_sbom_install": {
            "exit": bad_sbom_install["exit"],
            "code": code_of(bad_sbom_install),
            "nothing_landed": not site_has(tmp / "site-badsbom", "hello-skill"),
        },
        "standalone_cli_verify_verb": "see side_observations.no_verify_verb -- measured, not assumed",
    }
    flush()

    # ------------------------------------------------------------- 4 REVOKE
    rev = copy_registry("reg-revoke")
    before = do_install(
        rev,
        fresh("site-rev-before"),
        "hello-skill",
        "=1.0.0",
        expect=0,
        label="install-BEFORE-revocation",
    )
    rvk = mkt(
        "revoke",
        "--registry",
        str(rev),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.0.0",
        "--reason",
        "wave4 independent verification",
        "--severity",
        "critical",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="revoke-version",
    )
    after_site = fresh("site-rev-after")
    after = do_install(
        rev,
        after_site,
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-AFTER-revocation",
    )
    scoped = do_install(
        rev,
        fresh("site-rev-scoped"),
        "hello-skill",
        "=1.1.0",
        expect=0,
        label="install-OTHER-version-after-revocation",
    )
    # fail-closed: delete the list entirely. Copied from the REVOKED registry, so every
    # variant below differs from the baseline only in the revocation list itself.
    reg_norev = copy_of(rev, "reg-norev")
    (reg_norev / "revocation.json").unlink()
    norev = do_install(
        reg_norev,
        fresh("site-norev"),
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-with-revocation-list-DELETED",
    )
    # emptied + maintainer-signed => a maintainer MAY un-revoke (control that the refusal
    # is about the CONTENT, and that the same file re-signed by a rogue key still refuses)
    from mkt.crypto import sign_document  # noqa: PLC0415
    from mkt.fixture import keys_for  # noqa: PLC0415

    def rewrite_revocation(root: Path, signer: str, revocations: list[Any]) -> None:
        """Rewrite the list with the given content, SIGNED by ``signer``'s key.

        ``sign_document`` RETURNS the block and does not mutate; the first draft of this probe
        discarded the return value and wrote an UNSIGNED list, so both the rogue-key case and
        the maintainer case refused for the same wrong reason. Assigning the block is the fix.
        """
        p = root / "revocation.json"
        doc = read_json(p)
        doc.pop("signature", None)
        doc["revocations"] = revocations
        doc["signature"] = sign_document(
            doc, "mkt.revocation.v1", keys_for(signer)[0], signed_at=doc["updated_at"]
        )
        p.write_text(json.dumps(doc, indent=2), encoding="utf-8", newline="\n")

    reg_empty = copy_of(rev, "reg-emptyrev")
    rewrite_revocation(reg_empty, "pub:registry-root", [])
    emptied_ok = do_install(
        reg_empty,
        fresh("site-emptyrev"),
        "hello-skill",
        "=1.0.0",
        expect=0,
        label="install-after-maintainer-EMPTIED-the-list",
    )
    reg_rogue = copy_of(rev, "reg-roguerev")
    rewrite_revocation(reg_rogue, "pub:alpha-tools", [])
    rogue = do_install(
        reg_rogue,
        fresh("site-roguerev"),
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-after-ROGUE-key-emptied-the-list",
    )

    RESULT["checks"]["4_revoke_blocks"] = {
        "verdict": "PASS"
        if (
            before["exit"] == 0
            and rvk["exit"] == 0
            and after["exit"] == 1
            and code_of(after) == "MKT-I04"
            and not site_has(after_site, "hello-skill")
            and scoped["exit"] == 0
            and norev["exit"] == 1
            and rogue["exit"] == 1
            and emptied_ok["exit"] == 0
        )
        else "FAIL",
        "both_states": {
            "before_revocation": {
                "exit": before["exit"],
                "files": n_files(tmp / "site-rev-before", "hello-skill"),
            },
            "after_revocation": {
                "exit": after["exit"],
                "code": code_of(after),
                "files_in_site": n_files(after_site, "hello-skill"),
            },
        },
        "revocation_ids": (rvk["json"] or {}).get("revocations"),
        "scoped_not_killswitch": {
            "other_version_exit": scoped["exit"],
            "version": "1.1.0",
        },
        "fail_closed_list_deleted": {"exit": norev["exit"], "code": code_of(norev)},
        "rogue_signed_empty_list": {"exit": rogue["exit"], "code": code_of(rogue)},
        "maintainer_emptied_list_control": {
            "exit": emptied_ok["exit"],
            "note": "the SAME emptied file, maintainer-signed, installs -> the refusal above is about the KEY, not the emptiness",
        },
    }
    flush()

    # --------------------------------------------- 4b revocation bypass hunt
    hunt: dict[str, Any] = {}

    # (a) update -> a revoked NEWER version
    up_reg = copy_registry("reg-update")
    up_site = fresh("site-update")
    do_install(up_reg, up_site, "hello-skill", "=1.0.0", expect=0, label="update-seed")
    mkt(
        "revoke",
        "--registry",
        str(up_reg),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.1.0",
        "--reason",
        "wave4 update-path probe",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="revoke-1.1.0",
    )
    upd = do_install(
        up_reg,
        up_site,
        "hello-skill",
        "^1.0.0",
        expect=1,
        verb="update",
        label="update-to-REVOKED-version",
    )
    hunt["update_to_revoked_version"] = {
        "blocked": upd["exit"] == 1,
        "code": code_of(upd),
        "installed_version_after": read_json(up_site / "state" / "installed.json")[
            "packages"
        ]["hello-skill"]["version"],
    }
    flush()

    # (b) rollback -> a version revoked after the update
    rb_reg = copy_registry("reg-rollback")
    rb_site = fresh("site-rollback")
    do_install(
        rb_reg, rb_site, "hello-skill", "=1.0.0", expect=0, label="rollback-seed"
    )
    do_install(
        rb_reg,
        rb_site,
        "hello-skill",
        "=1.1.0",
        expect=0,
        verb="update",
        label="rollback-update-to-1.1.0",
    )
    mkt(
        "revoke",
        "--registry",
        str(rb_reg),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.0.0",
        "--reason",
        "wave4 rollback-path probe",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="revoke-1.0.0-after-update",
    )
    rbk = do_install(
        rb_reg,
        rb_site,
        "hello-skill",
        "*",
        expect=1,
        verb="rollback",
        label="rollback-to-REVOKED-version",
    )
    hunt["rollback_to_revoked_version"] = {
        "blocked": rbk["exit"] == 1,
        "code": code_of(rbk),
    }
    flush()

    # (c) a revoked DEPENDENCY pulled in by a clean dependant
    dep_reg = copy_registry("reg-dep")
    dep_ok = do_install(
        dep_reg,
        fresh("site-dep-before"),
        "dep-consumer",
        "=1.0.0",
        expect=0,
        label="install-dependant-BEFORE-dep-revocation",
    )
    mkt(
        "revoke",
        "--registry",
        str(dep_reg),
        "--scope",
        "package",
        "--name",
        "hello-skill",
        "--reason",
        "wave4 dependency-path probe",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="revoke-the-dependency",
    )
    dep_site = fresh("site-dep-after")
    dep_bad = do_install(
        dep_reg,
        dep_site,
        "dep-consumer",
        "=1.0.0",
        expect=1,
        label="install-dependant-AFTER-dep-revocation",
    )
    hunt["revoked_dependency"] = {
        "dependant_installs_before": dep_ok["exit"] == 0,
        "blocked_after": dep_bad["exit"] == 1,
        "code": code_of(dep_bad),
        "dependant_left_in_site": site_has(dep_site, "dep-consumer"),
        "dependency_left_in_site": site_has(dep_site, "hello-skill"),
    }
    flush()

    # (d) offline bundle: export BEFORE the revocation, import AFTER it
    bun_reg = copy_registry("reg-bundle")
    bundle_out = tmp / "bundle-stale"
    mkt(
        "export",
        "--registry",
        str(bun_reg),
        "--out",
        str(bundle_out),
        "--package",
        "hello-skill@1.0.0",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="export-bundle-BEFORE-revocation",
    )
    mkt(
        "revoke",
        "--registry",
        str(bun_reg),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.0.0",
        "--reason",
        "wave4 stale-bundle probe",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:registry-root",
        expect=0,
        label="revoke-then-import-a-stale-bundle",
    )
    pre_import = do_install(
        bun_reg,
        fresh("site-bundle-pre"),
        "hello-skill",
        "=1.0.0",
        expect=1,
        label="install-after-revocation-BEFORE-the-stale-import",
    )
    imp = mkt(
        "import",
        str(bundle_out),
        "--registry",
        str(bun_reg),
        "--fixture-policy",
        "--fixture-key",
        "pub:registry-root",
        label="import-the-STALE-bundle-into-the-revoked-registry",
    )
    post_site = fresh("site-bundle-post")
    post_import = do_install(
        bun_reg,
        post_site,
        "hello-skill",
        "=1.0.0",
        label="install-AFTER-the-stale-import",
    )
    rev_now = read_json(bun_reg / "revocation.json")
    hunt["stale_offline_bundle_import"] = {
        "revocation_ids_still_present": [
            r["revocation_id"] for r in rev_now.get("revocations", [])
        ],
        "install_refused_before_import": pre_import["exit"] == 1,
        "refusal_code_before_import": code_of(pre_import),
        "import_exit": imp["exit"],
        "install_after_import_exit": post_import["exit"],
        "install_after_import_code": code_of(post_import),
        "revocations_left_in_destination_list": len(rev_now.get("revocations", [])),
        "landed_in_site": site_has(post_site, "hello-skill", "1.0.0"),
        "BYPASS": post_import["exit"] == 0,
        "note": "bundle.import_bundle copies the bundle's revocation.json OVER the destination's",
    }
    flush()

    # (e) a stale MIRROR list, when the mirror is the resolution source.
    #     Run it TWICE -- once per mirror trust_mode -- so the discriminator is measured and
    #     not assumed. The fixture ships verify-and-require-primary-index.
    from mkt.publish import sign_index  # noqa: PLC0415

    def mirror_case(trust_mode: str, tag: str) -> dict[str, Any]:
        root = copy_registry(f"reg-mirror-{tag}")
        idx = read_json(root / "index.json")
        idx["mirrors"][0]["trust_mode"] = trust_mode
        idx["entries"] = [
            e
            for e in idx["entries"]
            if not (e["name"] == "hello-skill" and e["version"] == "1.0.0")
        ]
        idx.pop("signature", None)
        sign_index(idx, keys_for("pub:registry-root")[0])
        (root / "index.json").write_text(
            json.dumps(idx, indent=2), encoding="utf-8", newline="\n"
        )
        mkt(
            "revoke",
            "--registry",
            str(root),
            "--scope",
            "version",
            "--name",
            "hello-skill",
            "--version",
            "1.0.0",
            "--reason",
            "wave4 stale-mirror probe",
            "--authority",
            "pub:registry-root",
            "--fixture-key",
            "pub:registry-root",
            expect=0,
            label=f"revoke-in-primary-mirror-{tag}",
        )
        s = fresh(f"site-mirror-{tag}")
        r = do_install(
            root,
            s,
            "hello-skill",
            "=1.0.0",
            label=f"install-from-mirror-{tag}-with-a-STALE-revocation-list",
        )
        src_registry = None
        if (s / "state" / "installed.json").is_file():
            src_registry = read_json(s / "state" / "installed.json")["packages"][
                "hello-skill"
            ]["registry_id"]
        return {
            "mirror_trust_mode": trust_mode,
            "install_exit": r["exit"],
            "code": code_of(r),
            "landed_in_site": site_has(s, "hello-skill", "1.0.0"),
            "recorded_source_registry_id": src_registry,
        }

    lax_mirror = mirror_case("verify-always", "verify-always")
    strict_mirror = mirror_case(
        "verify-and-require-primary-index", "require-primary-index"
    )
    hunt["stale_mirror_revocation_list"] = {
        "primary_row_removed": True,
        "verify_always_mirror": lax_mirror,
        "control_require_primary_index_mirror": strict_mirror,
        "BYPASS": lax_mirror["install_exit"] == 0,
        "reachability": "requires the registry index to declare a verify-always mirror AND the primary row withdrawn; the fixture's require-primary-index mode is the control",
        "second_signal": "the install receipt records registry_id reg:fixture-mirror-a, so the mirror WAS the resolution source",
    }
    RESULT["bypass_hunt"] = hunt
    flush()

    # ------------------------------------------------ 5 MALICIOUS PERMISSIONS
    lax = tmp / "lax-trust-policy.json"
    lax_doc = {
        "schema_version": "1.0.0",
        "policy_id": "pol:wave4-lax",
        "registry_maintainer_keys": [keys_for("pub:registry-root")[1]],
        "trusted_publishers": [
            {"publisher": p, "public_key": keys_for(p)[1]}
            for p in ("pub:alpha-tools", "pub:beta-labs", "pub:registry-root")
        ],
        "max_permissions": [
            "secrets:read:**",
            "net:egress:**",
            "exec:process:**",
            "fs:write:**",
            "fs:read:**",
            "hook:register:**",
            "env:read:**",
            "mcp:mount:**",
        ],
        "forbidden_permissions": [],
        "license_policy": {"allowed_spdx": ["MIT"], "on_unknown": "refuse"},
        "thresholds": {"min_conformance_score": 0, "max_advisory_severity": "critical"},
        "on_missing": {
            "revocation_list": "refuse",
            "advisory_list": "refuse",
            "sbom": "refuse",
            "signature": "refuse",
            "publisher": "refuse",
        },
        "allow_vulnerable_override": True,
    }
    lax.write_text(json.dumps(lax_doc, indent=2), encoding="utf-8", newline="\n")

    evil_reg = copy_registry("reg-evil")
    evil_strict = mkt(
        "publish",
        str(sources / "evil-overreach-1.0.0"),
        "--registry",
        str(evil_reg),
        "--publisher",
        "pub:alpha-tools",
        "--fixture-key",
        "pub:alpha-tools",
        "--fixture-policy",
        "--license-basis",
        str(LICENSE_BASIS),
        expect=1,
        label="publish-MALICIOUS-under-the-strict-policy",
    )
    evil_lax = mkt(
        "publish",
        str(sources / "evil-overreach-1.0.0"),
        "--registry",
        str(evil_reg),
        "--publisher",
        "pub:alpha-tools",
        "--fixture-key",
        "pub:alpha-tools",
        "--trust-policy",
        str(lax),
        "--license-basis",
        str(LICENSE_BASIS),
        label="publish-MALICIOUS-under-a-LAX-registry-policy",
    )
    evil_site = fresh("site-evil")
    evil_install = do_install(
        evil_reg,
        evil_site,
        "evil-overreach",
        "=1.0.0",
        label="install-MALICIOUS-with-the-STRICT-consumer-policy",
    )
    benign_same_index = do_install(
        evil_reg,
        fresh("site-evil-control"),
        "hello-skill",
        "=1.0.0",
        expect=0,
        label="control-benign-package-from-the-SAME-index",
    )
    from mkt.canon import read_json as _rj  # noqa: PLC0415

    evil_perms = None
    ep = evil_reg / "packages" / "evil-overreach" / "1.0.0"
    if ep.exists():
        cand = list(ep.glob("manifest.json")) + list(ep.glob("*.json"))
        if cand:
            evil_perms = _rj(cand[0]).get("permissions")
    RESULT["checks"]["5_malicious_permissions"] = {
        "verdict": "PASS"
        if (
            evil_strict["exit"] == 1
            and code_of(evil_strict) == "MKT-P07"
            and evil_lax["exit"] == 0
            and evil_install["exit"] == 1
            and code_of(evil_install) == "MKT-I05"
            and benign_same_index["exit"] == 0
            and not site_has(evil_site, "evil-overreach")
        )
        else "FAIL",
        "requested_permissions": evil_perms,
        "publish_refused_strict": {
            "exit": evil_strict["exit"],
            "code": code_of(evil_strict),
        },
        "publish_accepted_by_a_lax_registry": {"exit": evil_lax["exit"]},
        "install_refused_by_strict_consumer": {
            "exit": evil_install["exit"],
            "code": code_of(evil_install),
            "nothing_landed": not site_has(evil_site, "evil-overreach"),
        },
        "control_benign_from_same_index": {"exit": benign_same_index["exit"]},
        "note": "the second half is the load-bearing one: refusing only at publish protects only a registry the attacker does not control",
    }
    flush()

    # -------------------------------------------------- 6 LOCKFILE DETERMINISM
    lock_reg = copy_registry("reg-lock")
    seed_site = fresh("site-lock-seed")
    do_install(
        lock_reg, seed_site, "hello-skill", "=1.0.0", expect=0, label="lockfile-seed"
    )
    lockfile = seed_site / "mkt-lock.json"
    lock_doc = read_json(lockfile)
    runs = []
    for n in ("site-lock-a", "site-lock-b"):
        s = fresh(n)
        shutil.copy2(lockfile, s / "mkt-lock.json")
        r = do_install(
            lock_reg,
            s,
            "hello-skill",
            "*",
            expect=0,
            extra=("--frozen",),
            label=f"frozen-install-{n}",
        )
        state = read_json(s / "state" / "installed.json")["packages"]["hello-skill"]
        runs.append(
            {
                "site": n,
                "exit": r["exit"],
                "resolved_version": state["version"],
                "payload_digest": state["payload_digest"],
                "lockfile_digest_matches": read_json(s / "mkt-lock.json")["packages"]
                == lock_doc["packages"],
            }
        )
    unfrozen = fresh("site-lock-unfrozen")
    do_install(
        lock_reg,
        unfrozen,
        "hello-skill",
        "*",
        expect=0,
        label="control-UNfrozen-install-same-range",
    )
    un_version = read_json(unfrozen / "state" / "installed.json")["packages"][
        "hello-skill"
    ]["version"]
    drift_site = fresh("site-lock-drift")
    shutil.copy2(lockfile, drift_site / "mkt-lock.json")
    dl = read_json(drift_site / "mkt-lock.json")
    dl["packages"][0]["payload_digest"] = "sha256:" + "0" * 64
    (drift_site / "mkt-lock.json").write_text(
        json.dumps(dl, indent=2), encoding="utf-8", newline="\n"
    )
    drift = do_install(
        lock_reg,
        drift_site,
        "hello-skill",
        "*",
        expect=1,
        extra=("--frozen",),
        label="frozen-install-with-a-DRIFTED-pin",
    )
    RESULT["checks"]["6_lockfile_determinism"] = {
        "verdict": "PASS"
        if (
            len({r["resolved_version"] for r in runs}) == 1
            and len({r["payload_digest"] for r in runs}) == 1
            and all(r["exit"] == 0 for r in runs)
            and un_version != runs[0]["resolved_version"]
            and drift["exit"] == 1
        )
        else "FAIL",
        "pinned_version": lock_doc["packages"][0]["version"],
        "two_runs": runs,
        "identical_resolved_version": len({r["resolved_version"] for r in runs}) == 1,
        "identical_payload_digest": len({r["payload_digest"] for r in runs}) == 1,
        "control_unfrozen_same_range_resolves": un_version,
        "control_note": "the unfrozen install of the SAME range picks a DIFFERENT version, so the lockfile is what pinned it",
        "control_drifted_pin_refused": {"exit": drift["exit"], "code": code_of(drift)},
        "nothing_landed_on_drift": not site_has(drift_site, "hello-skill"),
    }
    flush()

    # ------------------------------------------------------- side observations
    mu = mkt("mutations", label="mkt-mutations-battery")
    tail = [ln for ln in mu["stdout"].splitlines() if ln.strip()][-3:]
    revoke_nonmaint = mkt(
        "revoke",
        "--registry",
        str(copy_registry("reg-authz")),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.0.0",
        "--reason",
        "wave4 authority probe",
        "--authority",
        "pub:alpha-tools",
        "--fixture-key",
        "pub:alpha-tools",
        label="revoke-with-a-PUBLISHER-authority",
    )
    # Wave 3 reported "a non-maintainer can publish a revocation that appears accepted".
    # The role check refuses a PUBLISHER authority (above), so the reachable shape is a
    # maintainer AUTHORITY string with a non-maintainer SIGNING KEY -- nothing checks the key
    # at revoke time.
    authz2_reg = copy_registry("reg-authz2")
    revoke_wrongkey = mkt(
        "revoke",
        "--registry",
        str(authz2_reg),
        "--scope",
        "version",
        "--name",
        "hello-skill",
        "--version",
        "1.0.0",
        "--reason",
        "wave4 authority-vs-key probe",
        "--authority",
        "pub:registry-root",
        "--fixture-key",
        "pub:alpha-tools",
        label="revoke-maintainer-AUTHORITY-signed-by-a-PUBLISHER-key",
    )
    after_wrongkey = do_install(
        authz2_reg,
        fresh("site-authz2"),
        "hello-skill",
        "=1.1.0",
        label="install-an-UNRELATED-version-after-that-revoke",
    )
    # DETECTOR CONTROL for "there is no `mkt verify` verb": a substring search of --help is a
    # BROKEN detector -- the word "verify" appears in the `import` help text. Ask argparse.
    verify_probe = subprocess.run(  # noqa: S603
        [PY, "-m", "mkt", "verify"],
        cwd=str(MKT_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )
    control_known_verb = subprocess.run(  # noqa: S603
        [PY, "-m", "mkt", "install"],
        cwd=str(MKT_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )
    RESULT["side_observations"] = {
        "mkt_mutations_exit": mu["exit"],
        "mkt_mutations_marker": mu["marker"],
        "mkt_mutations_tail": [redact(t) for t in tail],
        "mkt_mutations_stderr_tail": mu["stderr_tail"][-200:],
        "revoke_with_publisher_authority_exit": revoke_nonmaint["exit"],
        "revoke_maintainer_authority_publisher_key": {
            "exit": revoke_wrongkey["exit"],
            "marker": revoke_wrongkey["marker"],
            "unrelated_version_install_exit_after": after_wrongkey["exit"],
            "unrelated_version_install_code": code_of(after_wrongkey),
            "impact": "denial-of-service on EVERY install from that registry, not a revocation bypass",
        },
        "no_verify_verb": {
            "invalid_choice": "invalid choice" in verify_probe.stderr,
            "verify_exit": verify_probe.returncode,
            "control_known_verb_stderr_has_invalid_choice": "invalid choice"
            in control_known_verb.stderr,
            "control_known_verb_exit": control_known_verb.returncode,
            "note": "a --help substring search reported the opposite; 'verify' occurs in the import help text",
        },
    }
    verdicts = {
        k: v.get("verdict") for k, v in RESULT["checks"].items() if isinstance(v, dict)
    }
    RESULT["summary"] = {
        "checks_pass": sum(1 for v in verdicts.values() if v == "PASS"),
        "checks_total": len(RESULT["checks"]),
        "verdicts": verdicts,
        "bypasses_found": [k for k, v in hunt.items() if v.get("BYPASS")],
    }
    RESULT["state"] = "FINISHED"
    flush()
    ok = all(v == "PASS" for v in verdicts.values())
    print(json.dumps(RESULT["summary"], indent=2))
    print(
        "SUCCESS:wave4-marketplace-lifecycle"
        if ok
        else "FAILED:wave4-marketplace-lifecycle one or more required checks did not pass"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
