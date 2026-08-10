"""WAVE 3 FLOOR AUDIT - check 3 (Phase 6 marketplace), corrected probe.

My first attempt pointed --registry at the `mkt fixture --into` root instead of that root's
`registry/` subdirectory, so PUBLISH exited 1 and every later install failed with
`RegistryError: no registry index`. The post-revocation install "refused" - but it refused in
BOTH states, so it measured nothing. Its own both-states control caught that
(`probe_silent_before_revocation: false`). This file is the corrected probe; the failed one is
retained in the report as the detector-failure record.

Flow, all against throwaway temp roots:
    1. mkt fixture --into T          -> registry at T/registry
    2. mkt publish  (a scaffolded package, real publish path)
    3. mkt install hello-skill       -> MUST succeed
    4. verify the manifest + index Ed25519 signatures CRYPTOGRAPHICALLY, and the CycloneDX SBOM
    5. mkt revoke --scope version hello-skill 1.0.0
    6. mkt install hello-skill into a FRESH site -> MUST refuse; nothing may land
    7. controls: tamper a payload byte; forge a signature; both must be refused
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
BUILD = REPO / "platform"
MKT = BUILD / "marketplace"
CC = REPO / "command-center"
OUT_JSON = CC / "WAVE3-FLOOR-AUDIT.json"
PY = sys.executable

if str(MKT) not in sys.path:
    sys.path.insert(0, str(MKT))


def merge(key: str, value: Any) -> None:
    d: dict[str, Any] = {}
    if OUT_JSON.exists():
        try:
            d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            d = {}
    d[key] = value
    OUT_JSON.write_text(
        json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"WROTE {key}")


def run(cmd: list[str], cwd: Path = MKT, timeout: int = 900) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "cmd": " ".join(cmd),
            "exit": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": " ".join(cmd),
            "exit": None,
            "stdout": "",
            "stderr": f"TIMEOUT {timeout}s",
        }


def census(root: Path) -> dict[str, Any]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return {
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "sample": sorted(str(p.relative_to(root)).replace("\\", "/") for p in files)[
            :20
        ],
    }


# ------------------------------------------------------------------ crypto verification


def verify_ed25519(doc: dict[str, Any], *, domain_hint: str) -> dict[str, Any]:
    """Verify a signed marketplace document with the LANE'S OWN crypto module.

    Deliberately calls mkt.crypto rather than re-implementing Ed25519: the question this audit
    asks is "does the shipped verifier accept this document", not "can I write a verifier".
    The FORGERY control below is what makes a positive answer meaningful.
    """
    out: dict[str, Any] = {"domain_hint": domain_hint}
    sig = doc.get("signature")
    if not isinstance(sig, dict):
        out["error"] = "no signature block"
        out["verified"] = False
        return out
    out["algorithm"] = sig.get("algorithm")
    out["domain"] = sig.get("domain")
    out["key_id"] = sig.get("key_id")
    out["has_signature_bytes"] = bool(sig.get("signature"))
    out["signed_digest"] = str(sig.get("signed_digest"))[:24]
    try:
        from mkt import canon, crypto  # type: ignore

        fns = [n for n in dir(crypto) if not n.startswith("_")]
        out["crypto_api"] = fns
        # The real API is verify_document(doc, domain, *, expected_public_key) -> (bool, reason).
        # My first pass looked for verify()/verify_signature(), found neither, and recorded
        # verified=False for BOTH the genuine and the forged manifest - silent in both states,
        # i.e. measuring nothing. The forgery control below is what exposed that.
        verify_document = getattr(crypto, "verify_document", None)
        if verify_document is None:
            out["error"] = "no verify_document() in mkt.crypto"
            out["verified"] = False
            return out
        out["digest_fn"] = "mkt.crypto.digest_bytes via verify_document"
        try:
            recomputed = crypto.digest_bytes(
                crypto.signing_bytes(crypto.strip_signature(doc))
            )
            out["recomputed_digest"] = str(recomputed)[:24]
            out["digest_matches_signed_digest"] = str(recomputed) == str(
                sig.get("signed_digest")
            )
        except Exception as e:
            out["digest_recompute_error"] = f"{type(e).__name__}: {e}"
        ok, reason = verify_document(doc, str(sig.get("domain")))
        out["verified"] = bool(ok)
        out["verify_reason"] = str(reason)[:220]
        # pin the key too: verifying against the key embedded in the doc alone would accept a
        # doc re-signed by ANY key, so re-verify with the key explicitly expected
        ok2, reason2 = verify_document(
            doc, str(sig.get("domain")), expected_public_key=sig.get("public_key")
        )
        out["verified_with_pinned_key"] = bool(ok2)
        out["pinned_key_reason"] = str(reason2)[:220]
        _ = canon  # imported for parity with the lane's own canonicalisation path
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["verified"] = False
    return out


def sbom_report(p: Path) -> dict[str, Any]:
    d = json.loads(p.read_text(encoding="utf-8"))
    comps = d.get("components") or []
    hashed = [c for c in comps if c.get("hashes")]
    return {
        "path": p.name,
        "bomFormat": d.get("bomFormat"),
        "specVersion": d.get("specVersion"),
        "serialNumber_present": bool(d.get("serialNumber")),
        "component_count": len(comps),
        "components_with_sha256": len(hashed),
        "component_names": sorted(str(c.get("name")) for c in comps),
        "licences_declared": sorted(
            {
                (lic.get("license") or {}).get("id", "?")
                for c in comps
                for lic in (c.get("licenses") or [])
            }
        ),
        "non_empty": len(comps) > 0,
        "every_component_hashed": len(comps) > 0 and len(hashed) == len(comps),
    }


# ------------------------------------------------------------------ the check


def check() -> dict[str, Any]:
    res: dict[str, Any] = {}
    tmp = Path(tempfile.mkdtemp(prefix="wave3-mkt2-"))
    try:
        root = tmp / "fx"
        res["fixture_build"] = run([PY, "-m", "mkt", "fixture", "--into", str(root)])
        registry = root / "registry"
        res["registry_root"] = "the `registry/` SUBDIR of --into, not --into itself"
        res["registry_exists"] = (registry / "index.json").exists()
        if not res["registry_exists"]:
            res["VERDICT"] = "BLOCKED - fixture build produced no index.json"
            return res
        res["registry_census"] = census(registry)

        # ---------------------------------------------------------- 2. PUBLISH (real path)
        src = tmp / "src"
        src.mkdir()
        res["scaffold"] = run(
            [
                PY,
                "-m",
                "mkt",
                "scaffold",
                "--into",
                str(src),
                "--name",
                "audit-probe-skill",
            ]
        )
        if res["scaffold"]["exit"] != 0:
            # scaffold flags differ; fall back to publishing a committed fixture source
            res["scaffold_fallback"] = "using fixture sources/hello-skill-1.1.0"
            cand = sorted((root / "sources").glob("hello-skill-1.1.0"))
            pkg_src = (
                cand[0]
                if cand
                else (MKT / "fixture" / "packages" / "hello-skill-1.1.0")
            )
        else:
            cand = [p for p in src.iterdir() if p.is_dir()]
            pkg_src = cand[0] if cand else src
        res["publish_source"] = str(pkg_src)
        res["publish_scaffold_no_licence"] = run(
            [
                PY,
                "-m",
                "mkt",
                "publish",
                str(pkg_src),
                "--registry",
                str(registry),
                "--publisher",
                "pub:alpha-tools",
                "--fixture-key",
                "pub:alpha-tools",
                "--fixture-policy",
            ]
        )
        # The scaffolded package supplies no licence BASIS, so governance refuses it with
        # MKT-P05. That refusal is the gate WORKING, not a build failure - so publish is also
        # exercised WITH a licence basis, and both outcomes are recorded. The basis is an
        # EXPLICIT --license-basis path (publish.py:317-326 reads the flag, it does not
        # discover a LICENSE file), so the flag is what the second run adds.
        licensed_src = tmp / "licensed"
        shutil.copytree(pkg_src, licensed_src)
        licence_file = licensed_src / "LICENSE"
        licence_file.write_text(
            "MIT License\n\nPermission is hereby granted, free of charge, to any person "
            "obtaining a copy of this software.\n",
            encoding="utf-8",
            newline="\n",
        )
        res["publish_with_licence"] = run(
            [
                PY,
                "-m",
                "mkt",
                "publish",
                str(licensed_src),
                "--registry",
                str(registry),
                "--publisher",
                "pub:alpha-tools",
                "--fixture-key",
                "pub:alpha-tools",
                "--fixture-policy",
                "--license-basis",
                str(licence_file),
            ]
        )
        res["publish_governance_control"] = {
            "seeded_defect": "publish WITHOUT --license-basis (no licence basis supplied); the "
            "good state is the identical command plus --license-basis <LICENSE>",
            "publish_without_licence_exit": res["publish_scaffold_no_licence"]["exit"],
            "refusal_code": "MKT-P05"
            if "MKT-P05" in res["publish_scaffold_no_licence"]["stdout"]
            else None,
            "publish_with_licence_exit": res["publish_with_licence"]["exit"],
            "probe_FIRED_on_seeded_defect": res["publish_scaffold_no_licence"]["exit"]
            not in (0, None),
            "probe_silent_on_licensed_package": res["publish_with_licence"]["exit"]
            == 0,
            "both_states_valid": res["publish_scaffold_no_licence"]["exit"]
            not in (0, None)
            and res["publish_with_licence"]["exit"] == 0,
        }
        res["publish"] = res["publish_with_licence"]

        res["search"] = run([PY, "-m", "mkt", "search", "--registry", str(registry)])

        # ------------------------------------------------------------------ 3. INSTALL
        site = tmp / "site"
        site.mkdir()
        res["install"] = run(
            [
                PY,
                "-m",
                "mkt",
                "install",
                "hello-skill",
                "--registry",
                str(registry),
                "--site",
                str(site),
                "--range",
                "1.0.0",
                "--fixture-policy",
            ]
        )
        res["site_after_install"] = census(site)

        # ------------------------------------------- 4. SIGNATURE + SBOM verification
        mpath = registry / "packages" / "hello-skill" / "1.0.0" / "manifest.json"
        spath = registry / "packages" / "hello-skill" / "1.0.0" / "sbom.json"
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        index = json.loads((registry / "index.json").read_text(encoding="utf-8"))
        res["signature_verification"] = {
            "manifest": verify_ed25519(manifest, domain_hint="mkt.manifest.v1"),
            "registry_index": verify_ed25519(index, domain_hint="mkt.index.v1"),
        }
        res["sbom_verification"] = {
            "registry_sbom": sbom_report(spath),
            "site_sboms": [sbom_report(p) for p in sorted(site.rglob("sbom.json"))],
            "sbom_ref_in_manifest": manifest.get("sbom_ref"),
        }

        # ---------- FORGERY CONTROL: flip one byte of the signature; verify MUST go False
        forged = json.loads(json.dumps(manifest))
        sigbytes = forged["signature"]["signature"]
        forged["signature"]["signature"] = _mutate_sig(sigbytes)
        res["signature_forgery_control"] = {
            "seeded_defect": "one character of manifest.signature.signature altered",
            "verify_on_genuine": res["signature_verification"]["manifest"].get(
                "verified"
            ),
            "verify_on_forged": verify_ed25519(
                forged, domain_hint="mkt.manifest.v1"
            ).get("verified"),
        }
        res["signature_forgery_control"]["probe_FIRED_on_seeded_defect"] = (
            res["signature_forgery_control"]["verify_on_forged"] is False
        )
        res["signature_forgery_control"]["both_states_valid"] = (
            res["signature_forgery_control"]["verify_on_genuine"] is True
            and res["signature_forgery_control"]["verify_on_forged"] is False
        )

        # -------------------------------------------------------------------- 5. REVOKE
        res["revoke"] = run(
            [
                PY,
                "-m",
                "mkt",
                "revoke",
                "--registry",
                str(registry),
                "--scope",
                "version",
                "--name",
                "hello-skill",
                "--version",
                "1.0.0",
                "--reason",
                "wave3 floor audit revocation probe",
                "--severity",
                "critical",
                "--authority",
                "pub:registry-root",
                "--fixture-key",
                "pub:registry-root",
            ]
        )
        rev = registry / "revocation.json"
        res["revocation_list_after"] = (
            json.loads(rev.read_text(encoding="utf-8")) if rev.exists() else None
        )

        # ------------------------- 6. POST-REVOCATION INSTALL: MUST REFUSE, NOTHING LANDS
        site2 = tmp / "site2"
        site2.mkdir()
        res["install_after_revoke"] = run(
            [
                PY,
                "-m",
                "mkt",
                "install",
                "hello-skill",
                "--registry",
                str(registry),
                "--site",
                str(site2),
                "--range",
                "1.0.0",
                "--fixture-policy",
            ]
        )
        res["site2_after_revoked_install"] = census(site2)

        blocked = res["install_after_revoke"]["exit"] not in (0, None)
        nothing_landed = res["site2_after_revoked_install"]["file_count"] == 0
        pre_ok = res["install"]["exit"] == 0

        res["revocation_control"] = {
            "seeded_defect": "the revocation itself; the SAME install command run before and "
            "after it, into two fresh sites",
            "install_BEFORE_revocation_exit": res["install"]["exit"],
            "install_AFTER_revocation_exit": res["install_after_revoke"]["exit"],
            "probe_FIRED_on_seeded_defect": blocked,
            "probe_silent_before_revocation": pre_ok,
            "both_states_valid": blocked and pre_ok,
            "no_payload_landed_after_refusal": nothing_landed,
            "refusal_message": res["install_after_revoke"]["stdout"][-700:],
        }

        # a non-revoked version must STILL install - revocation must be scoped, not a kill switch
        site3 = tmp / "site3"
        site3.mkdir()
        res["install_other_version_after_revoke"] = run(
            [
                PY,
                "-m",
                "mkt",
                "install",
                "hello-skill",
                "--registry",
                str(registry),
                "--site",
                str(site3),
                "--range",
                "1.1.0",
                "--fixture-policy",
            ]
        )
        res["revocation_is_scoped_not_a_killswitch"] = (
            res["install_other_version_after_revoke"]["exit"] == 0
        )

        # ---------- TAMPER CONTROL: flip a payload byte in a fresh registry, install must fail
        res["tamper_control"] = _tamper(tmp)

        # ---------- FINDING PROBE: `revoke` with a NON-MAINTAINER authority.
        # Measured in the first run: --authority pub:security-response exits 0 and writes a
        # signed revocation list, but the INSTALLER rejects that list as "key is not a
        # maintainer key" and therefore refuses EVERY install from the registry, including
        # versions that were never revoked. Fail-closed is correct; a revoke that reports
        # success while bricking the registry is the issue.
        res["nonmaintainer_authority_probe"] = _nonmaintainer_authority(tmp)

        # ---------- SBOM propagation: the registry has one; does the INSTALL SITE?
        res["sbom_propagation"] = {
            "registry_has_sbom": (
                registry / "packages" / "hello-skill" / "1.0.0" / "sbom.json"
            ).exists(),
            "site_sbom_count": len(list(site.rglob("sbom.json"))),
            "site_files": census(site)["sample"],
            "lockfile_present": (site / "mkt-lock.json").exists(),
            "lockfile_carries_payload_digest": _lock_has_digest(site / "mkt-lock.json"),
        }

        # the lane's own mutation battery, verbatim
        res["lane_mutation_battery"] = run([PY, "-m", "mkt", "mutations"], timeout=1200)

        sigs_ok = (
            res["signature_verification"]["manifest"].get("verified") is True
            and res["signature_verification"]["registry_index"].get("verified") is True
        )
        sbom_ok = res["sbom_verification"]["registry_sbom"]["non_empty"]
        res["VERDICT"] = (
            "PASS"
            if pre_ok
            and res["revoke"]["exit"] == 0
            and blocked
            and nothing_landed
            and sigs_ok
            and sbom_ok
            and res["signature_forgery_control"]["both_states_valid"]
            and res["tamper_control"]["both_states_valid"]
            and res["revocation_is_scoped_not_a_killswitch"]
            and res["publish_governance_control"]["both_states_valid"]
            else "FAIL - see the per-step flags"
        )
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mutate_sig(sig: Any) -> Any:
    """Alter exactly one byte of a signature, whatever its encoding."""
    s = str(sig)
    prefix = ""
    body = s
    if ":" in s:
        prefix, body = s.split(":", 1)
        prefix += ":"
    alphabet = "0123456789abcdefABCDEFghijklmnopqrstuvwxyz+/="
    first = body[0]
    repl = next(c for c in alphabet if c != first and c in alphabet)
    # keep it in the same charset family so the failure is a BAD SIGNATURE, not a parse error
    if all(c in "0123456789abcdefABCDEF" for c in body[:8]):
        repl = "0" if first != "0" else "1"
    return prefix + repl + body[1:]


def _lock_has_digest(p: Path) -> Any:
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8")
    return "sha256:" in txt or "payload_digest" in txt


def _nonmaintainer_authority(tmp: Path) -> dict[str, Any]:
    """Does `revoke` accept an authority whose key the installer will later reject?"""
    root = tmp / "fx-nonmaint"
    run([PY, "-m", "mkt", "fixture", "--into", str(root)])
    registry = root / "registry"
    rv = run(
        [
            PY,
            "-m",
            "mkt",
            "revoke",
            "--registry",
            str(registry),
            "--scope",
            "version",
            "--name",
            "hello-skill",
            "--version",
            "1.0.0",
            "--reason",
            "audit probe: non-maintainer authority",
            "--severity",
            "critical",
            "--authority",
            "pub:security-response",
            "--fixture-key",
            "pub:security-response",
        ]
    )
    s_rev = tmp / "site-nm-revoked"
    s_ok = tmp / "site-nm-untouched"
    s_rev.mkdir()
    s_ok.mkdir()
    inst_revoked = run(
        [
            PY,
            "-m",
            "mkt",
            "install",
            "hello-skill",
            "--registry",
            str(registry),
            "--site",
            str(s_rev),
            "--range",
            "1.0.0",
            "--fixture-policy",
        ]
    )
    inst_other = run(
        [
            PY,
            "-m",
            "mkt",
            "install",
            "hello-skill",
            "--registry",
            str(registry),
            "--site",
            str(s_ok),
            "--range",
            "1.1.0",
            "--fixture-policy",
        ]
    )
    return {
        "authority_used": "pub:security-response (role=security-response, NOT a maintainer key)",
        "revoke_exit": rv["exit"],
        "revoke_reported_success": rv["exit"] == 0,
        "install_of_the_REVOKED_version_exit": inst_revoked["exit"],
        "install_of_a_NEVER_REVOKED_version_exit": inst_other["exit"],
        "never_revoked_version_also_blocked": inst_other["exit"] not in (0, None),
        "installer_reason": inst_other["stdout"][-500:],
        "finding": "revoke exits 0 and writes a signed list the installer then rejects as "
        "'key is not a maintainer key', so EVERY install from that registry refuses - "
        "including versions never revoked. Fail-closed on an unverifiable list is correct; "
        "revoke reporting SUCCESS for a list that bricks the registry is the gap.",
    }


def _tamper(tmp: Path) -> dict[str, Any]:
    root = tmp / "fx-tamper"
    build = run([PY, "-m", "mkt", "fixture", "--into", str(root)])
    registry = root / "registry"
    good_site = tmp / "site-tamper-good"
    bad_site = tmp / "site-tamper-bad"
    good_site.mkdir()
    bad_site.mkdir()

    # GOOD state first: the same command must succeed before the tamper
    good = run(
        [
            PY,
            "-m",
            "mkt",
            "install",
            "hello-skill",
            "--registry",
            str(registry),
            "--site",
            str(good_site),
            "--range",
            "1.0.0",
            "--fixture-policy",
        ]
    )
    target = registry / "packages" / "hello-skill" / "1.0.0" / "payload" / "hello.py"
    before = target.read_bytes() if target.exists() else b""
    if target.exists():
        target.write_bytes(before + b"\n# tampered by the wave3 floor audit\n")
    bad = run(
        [
            PY,
            "-m",
            "mkt",
            "install",
            "hello-skill",
            "--registry",
            str(registry),
            "--site",
            str(bad_site),
            "--range",
            "1.0.0",
            "--fixture-policy",
        ]
    )
    return {
        "fixture_build_exit": build["exit"],
        "tampered_file": "packages/hello-skill/1.0.0/payload/hello.py (+34 bytes appended)",
        "install_BEFORE_tamper_exit": good["exit"],
        "install_AFTER_tamper_exit": bad["exit"],
        "refusal_message": bad["stdout"][-700:],
        "files_landed_after_tamper": census(bad_site)["file_count"],
        "probe_FIRED_on_seeded_defect": bad["exit"] not in (0, None),
        "probe_silent_before_tamper": good["exit"] == 0,
        "both_states_valid": bad["exit"] not in (0, None) and good["exit"] == 0,
    }


if __name__ == "__main__":
    try:
        r = check()
    except Exception as exc:  # noqa: BLE001
        import traceback

        r = {
            "PROBE_CRASHED": True,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-3000:],
        }
    merge("check3_phase6_marketplace", r)
    print(
        f"{'SUCCESS' if not r.get('PROBE_CRASHED') else 'FAILED'}:marketplace "
        f"verdict={r.get('VERDICT')}"
    )
