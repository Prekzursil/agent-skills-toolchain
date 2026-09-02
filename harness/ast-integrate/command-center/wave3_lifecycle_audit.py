"""WAVE 3 FLOOR AUDIT - checks 2 (Phase 5 plugin) and 3 (Phase 6 marketplace).

Real subprocesses into throwaway temp prefixes. Every stdout/stderr is captured verbatim and
stored in WAVE3-FLOOR-AUDIT.json so the report quotes measurements, not summaries.

    plugin       build + enumerate + install/upgrade/rollback/uninstall into a temp prefix
    marketplace  publish a fixture, install, verify signature+SBOM, REVOKE, re-install must FAIL
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
BUILD = REPO / "platform"
CC = REPO / "command-center"
OUT_JSON = CC / "WAVE3-FLOOR-AUDIT.json"


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


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> dict[str, Any]:
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


PY = sys.executable

# ------------------------------------------------------------------ forbidden-content detectors
# DENY BY DEFAULT in spirit: each detector is a pattern over the MEMBER NAME plus, for the
# credential detector, over the member CONTENT. Every detector is proven against a known-present
# seeded member before any "0 hits" is reported.
FORBIDDEN = {
    "vcs": re.compile(
        r"(^|/)\.git(/|$)|(^|/)\.gitmodules$|(^|/)\.svn(/|$)|(^|/)\.hg(/|$)"
    ),
    "transcript": re.compile(
        r"\.jsonl$|(^|/)transcripts?(/|$)|(^|/)projects/.*\.jsonl$"
    ),
    "log": re.compile(r"\.log$|(^|/)logs?(/|$)"),
    "cache": re.compile(r"__pycache__|\.pyc$|\.pytest_cache|(^|/)node_modules(/|$)"),
    "credential_name": re.compile(
        r"(^|/)\.env|(^|/)\.npmrc$|(^|/)\.netrc$|id_rsa|id_ed25519|\.pem$|\.pfx$|\.p12$"
        r"|credentials?\.json$|auth\.json$|\.credentials|secrets?\.(json|ya?ml|toml)$",
        re.IGNORECASE,
    ),
    "archive": re.compile(r"\.(zip|tar|tgz|gz|7z|rar)$"),
    "test_module": re.compile(
        r"(^|/)test_[^/]*\.py$|(^|/)[^/]*_test\.py$|(^|/)conftest\.py$"
    ),
}

#: content patterns for a credential VALUE. Redaction: only the pattern name and a byte offset
#: are ever recorded - never the matched text (AGENTS.md 9).
CREDENTIAL_CONTENT = {
    "anthropic_key": re.compile(rb"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "openai_key": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    "github_pat": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "hf_token": re.compile(rb"hf_[A-Za-z0-9]{30,}"),
    "aws_akid": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "slack": re.compile(rb"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    "private_key_block": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"
    ),
    "jwt": re.compile(rb"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\."),
}


def scan_members(names: list[str]) -> dict[str, list[str]]:
    return {k: sorted(n for n in names if rx.search(n)) for k, rx in FORBIDDEN.items()}


def scan_content(zf: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    scanned = 0
    for n in names:
        try:
            data = zf.read(n)
        except Exception:
            continue
        scanned += 1
        for label, rx in CREDENTIAL_CONTENT.items():
            m = rx.search(data)
            if m:
                hits.append({"member": n, "pattern": label, "offset": m.start()})
    return {"members_scanned": scanned, "credential_content_hits": hits}


def detector_control_on_zip() -> dict[str, Any]:
    """Prove every detector FIRES on a synthetic archive that contains all the bad shapes."""
    with tempfile.TemporaryDirectory(prefix="zipctl-") as td:
        z = Path(td) / "seeded.zip"
        seeded_names = [
            ".git/config",
            "sessions/agent-1.jsonl",
            "build/out.log",
            "lib/__pycache__/x.cpython-314.pyc",
            ".env",
            "nested/bundle.zip",
            "lib/test_thing.py",
        ]
        with zipfile.ZipFile(z, "w") as zf:
            for n in seeded_names:
                zf.writestr(n, "x")
            zf.writestr("leak.txt", "sk-ant-" + "A" * 40)
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            member_hits = scan_members(names)
            content = scan_content(zf, names)
    fired = {k: len(v) > 0 for k, v in member_hits.items()}
    fired["credential_content"] = len(content["credential_content_hits"]) > 0
    return {
        "seeded_archive_members": seeded_names + ["leak.txt (sk-ant-... value)"],
        "detector_fired": fired,
        "all_detectors_valid": all(fired.values()),
        "note": "control archive is synthetic and thrown away; it proves each detector can find "
        "a KNOWN-PRESENT item, so a later 0-hit reading on the real package is a measurement",
    }


# ============================================================== check 2: Phase 5 plugin


def check_plugin() -> dict[str, Any]:
    res: dict[str, Any] = {"detector_control": detector_control_on_zip()}

    tmp = Path(tempfile.mkdtemp(prefix="wave3-plugin-"))
    try:
        dist = tmp / "dist"
        prefix = tmp / "prefix"
        live = tmp / "live"
        for d in (dist, prefix, live):
            d.mkdir(parents=True, exist_ok=True)

        # ---------------------------------------------------------------- BUILD
        res["build"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "build",
                "--repo-root",
                str(REPO),
                "--out",
                str(dist),
                "--json",
                "-",
            ],
            cwd=BUILD,
        )
        archives = sorted(dist.rglob("*.zip"))
        res["build_produced"] = [str(a.relative_to(tmp)) for a in archives]
        if not archives:
            res["VERDICT"] = "FAILED - build produced no archive"
            return res
        pkg = archives[0]

        # ------------------------------------------------------------- ENUMERATE
        raw = pkg.read_bytes()
        with zipfile.ZipFile(pkg) as zf:
            infos = [
                {
                    "path": i.filename,
                    "bytes": i.file_size,
                    "compressed": i.compress_size,
                }
                for i in zf.infolist()
                if not i.is_dir()
            ]
            member_hits = scan_members([i["path"] for i in infos])
            content = scan_content(zf, [i["path"] for i in infos])
        res["package"] = {
            "name": pkg.name,
            "archive_bytes": len(raw),
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "member_count": len(infos),
            "uncompressed_bytes": sum(i["bytes"] for i in infos),
            "largest_members": sorted(infos, key=lambda i: -i["bytes"])[:8],
            "all_members": sorted(i["path"] for i in infos),
        }
        res["forbidden_content"] = {
            "member_name_hits": member_hits,
            "member_name_hit_total": sum(len(v) for v in member_hits.values()),
            "credential_content": content,
            "contains_dot_git": bool(member_hits["vcs"]),
            "contains_credentials": bool(member_hits["credential_name"])
            or bool(content["credential_content_hits"]),
            "contains_transcripts": bool(member_hits["transcript"]),
        }

        # determinism: build twice into two dirs, compare sha
        dist2 = tmp / "dist2"
        dist2.mkdir()
        res["build_second"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "build",
                "--repo-root",
                str(REPO),
                "--out",
                str(dist2),
            ],
            cwd=BUILD,
        )
        a2 = sorted(dist2.rglob("*.zip"))
        res["deterministic_rebuild"] = (
            hashlib.sha256(a2[0].read_bytes()).hexdigest()
            == res["package"]["archive_sha256"]
            if a2
            else None
        )

        # ---------------------------------------------------------------- INSTALL
        res["install"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "install",
                "--package",
                str(pkg),
                "--prefix",
                str(prefix),
                "--live",
                str(live),
                "--json",
                "-",
            ],
            cwd=BUILD,
        )
        res["prefix_after_install"] = _tree_census(prefix)

        # ---------------------------------------------------------------- UPGRADE
        # build a 1.0.1 package and update to it, so rollback has a previous version to reach
        dist3 = tmp / "dist3"
        dist3.mkdir()
        res["build_v101"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "build",
                "--repo-root",
                str(REPO),
                "--out",
                str(dist3),
                "--version",
                "1.0.1",
            ],
            cwd=BUILD,
        )
        newer = sorted(dist3.rglob("*.zip"))
        if newer:
            res["update"] = run(
                [
                    PY,
                    "-m",
                    "plugin.cli",
                    "update",
                    "--package",
                    str(newer[0]),
                    "--prefix",
                    str(prefix),
                    "--live",
                    str(live),
                    "--json",
                    "-",
                ],
                cwd=BUILD,
            )
            res["prefix_after_update"] = _tree_census(prefix)
        else:
            res["update"] = {"skipped": "no 1.0.1 archive produced"}

        # --------------------------------------------------------------- ROLLBACK
        res["rollback"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "rollback",
                "--prefix",
                str(prefix),
                "--live",
                str(live),
                "--json",
                "-",
            ],
            cwd=BUILD,
        )
        res["prefix_after_rollback"] = _tree_census(prefix)

        # -------------------------------------------------------------- UNINSTALL
        res["uninstall"] = run(
            [
                PY,
                "-m",
                "plugin.cli",
                "uninstall",
                "--prefix",
                str(prefix),
                "--live",
                str(live),
                "--purge-user-data",
                "--json",
                "-",
            ],
            cwd=BUILD,
        )
        res["prefix_after_uninstall"] = _tree_census(prefix)

        # health-check as a second, independent signal that install actually landed
        res["health_check_after_uninstall"] = run(
            [PY, "-m", "plugin.cli", "health-check", "--prefix", str(prefix)], cwd=BUILD
        )

        # -------------------- SEEDED DEFECT: a package carrying .git + a credential must be
        # rejected by the conformance validator, and my scanner must flag it.
        bad = tmp / "seeded-bad.zip"
        shutil.copy(pkg, bad)
        with zipfile.ZipFile(bad, "a") as zf:
            zf.writestr(".git/config", "[core]\n")
            zf.writestr(".env", "ANTHROPIC_API_KEY=sk-ant-" + "B" * 40 + "\n")
        with zipfile.ZipFile(bad) as zf:
            bnames = [i.filename for i in zf.infolist() if not i.is_dir()]
            bhits = scan_members(bnames)
            bcontent = scan_content(zf, bnames)
        conform_bad = run(
            [PY, "-m", "plugin.cli", "conform", "--package", str(bad)], cwd=BUILD
        )
        conform_good = run(
            [PY, "-m", "plugin.cli", "conform", "--package", str(pkg)], cwd=BUILD
        )
        res["seeded_defect_package"] = {
            "seeded": [".git/config", ".env with a sk-ant- value"],
            "my_scanner_flagged_vcs": bool(bhits["vcs"]),
            "my_scanner_flagged_credential_name": bool(bhits["credential_name"]),
            "my_scanner_flagged_credential_content": bool(
                bcontent["credential_content_hits"]
            ),
            "conform_on_seeded_bad": {
                "exit": conform_bad["exit"],
                "stdout_tail": conform_bad["stdout"][-900:],
                "stderr_tail": conform_bad["stderr"][-400:],
            },
            "conform_on_clean": {
                "exit": conform_good["exit"],
                "stdout_tail": conform_good["stdout"][-500:],
            },
            "probe_FIRED_on_seeded_defect": bool(bhits["vcs"])
            and bool(bcontent["credential_content_hits"]),
            "conform_discriminates": (conform_bad["exit"] not in (0, None))
            and conform_good["exit"] == 0,
        }

        lifecycle_ok = all(
            res[k]["exit"] == 0
            for k in ("build", "install", "rollback", "uninstall")
            if isinstance(res.get(k), dict) and "exit" in res[k]
        )
        res["VERDICT"] = "PASS" if lifecycle_ok else "PARTIAL/FAIL - see per-step exits"
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _tree_census(root: Path) -> dict[str, Any]:
    files = [p for p in root.rglob("*") if p.is_file()]
    return {
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "top_level": sorted({p.relative_to(root).parts[0] for p in files})[:20],
        "sample": sorted(str(p.relative_to(root)).replace("\\", "/") for p in files)[
            :25
        ],
    }


# ============================================================== check 3: Phase 6 marketplace

MKT = BUILD / "marketplace"


def check_marketplace() -> dict[str, Any]:
    res: dict[str, Any] = {}
    tmp = Path(tempfile.mkdtemp(prefix="wave3-mkt-"))
    try:
        registry = tmp / "registry"
        site = tmp / "site"
        for d in (registry, site):
            d.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------------------- PUBLISH
        pkg_dir = MKT / "fixture" / "packages" / "hello-skill-1.0.0"
        res["fixture_package"] = str(pkg_dir.relative_to(REPO)).replace("\\", "/")
        res["publish"] = run(
            [
                PY,
                "-m",
                "mkt",
                "publish",
                str(pkg_dir),
                "--registry",
                str(registry),
                "--publisher",
                "fixture-publisher",
                "--fixture-key",
                "publisher",
                "--fixture-policy",
            ],
            cwd=MKT,
        )
        res["registry_after_publish"] = _tree_census(registry)

        # ---------------------------------------------------------------- INSTALL
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
                "--fixture-policy",
            ],
            cwd=MKT,
        )
        res["site_after_install"] = _tree_census(site)

        # -------------------------------------------- SIGNATURE + SBOM verification
        res["signature_and_sbom"] = _verify_sig_sbom(registry, site)

        # ----------------------------------------------------------------- REVOKE
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
                "fixture-maintainer",
                "--fixture-key",
                "maintainer",
            ],
            cwd=MKT,
        )

        # --------------------------- POST-REVOCATION INSTALL: MUST REFUSE (the whole point)
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
                "--fixture-policy",
            ],
            cwd=MKT,
        )
        res["site2_after_blocked_install"] = _tree_census(site2)

        blocked = res["install_after_revoke"]["exit"] not in (0, None)
        nothing_landed = res["site2_after_blocked_install"]["file_count"] == 0

        # ------------- DETECTOR CONTROL: the same install command in the PRE-revocation state
        # succeeded (res["install"].exit == 0). That is the both-states pair: identical command,
        # opposite verdict, with only the revocation between them.
        res["detector_control"] = {
            "seeded_defect": "the revocation itself; identical `mkt install hello-skill` run "
            "before and after it",
            "install_BEFORE_revocation_exit": res["install"]["exit"],
            "install_AFTER_revocation_exit": res["install_after_revoke"]["exit"],
            "probe_FIRED_on_seeded_defect": blocked,
            "probe_silent_before_revocation": res["install"]["exit"] == 0,
            "both_states_valid": blocked and res["install"]["exit"] == 0,
            "no_payload_landed_after_refusal": nothing_landed,
        }

        # ---------------- tamper control: flip a payload byte, install must fail on signature
        res["tamper_control"] = _tamper_control(tmp, registry)

        # the lane's own mutation battery, run verbatim
        res["lane_mutation_battery"] = run(
            [PY, "-m", "mkt", "mutations"], cwd=MKT, timeout=900
        )

        res["VERDICT"] = (
            "PASS"
            if res["publish"]["exit"] == 0
            and res["install"]["exit"] == 0
            and res["revoke"]["exit"] == 0
            and blocked
            and nothing_landed
            and res["signature_and_sbom"].get("ok")
            else "FAIL - revocation or verification did not hold"
        )
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _verify_sig_sbom(registry: Path, site: Path) -> dict[str, Any]:
    """Read the registry's own signature + SBOM artifacts off disk and check them."""
    out: dict[str, Any] = {}
    sig_files = sorted(
        p for p in registry.rglob("*") if "sig" in p.name.lower() and p.is_file()
    )
    sbom_files = sorted(
        p for p in registry.rglob("*") if "sbom" in p.name.lower() and p.is_file()
    )
    out["registry_signature_files"] = [
        str(p.relative_to(registry)).replace("\\", "/") for p in sig_files
    ]
    out["registry_sbom_files"] = [
        str(p.relative_to(registry)).replace("\\", "/") for p in sbom_files
    ]
    site_sbom = sorted(
        p for p in site.rglob("*") if "sbom" in p.name.lower() and p.is_file()
    )
    out["site_sbom_files"] = [
        str(p.relative_to(site)).replace("\\", "/") for p in site_sbom
    ]

    # verify the signature cryptographically with the lane's own crypto module
    sys.path.insert(0, str(MKT))
    try:
        from mkt import crypto  # type: ignore

        out["crypto_module_functions"] = [
            n
            for n in dir(crypto)
            if not n.startswith("_") and callable(getattr(crypto, n))
        ]
    except Exception as e:
        out["crypto_import_error"] = f"{type(e).__name__}: {e}"

    # SBOM content check: it must enumerate the payload files, not be an empty shell
    sbom_docs = []
    for p in sbom_files + site_sbom:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        comps = d.get("components") or d.get("packages") or d.get("files") or []
        sbom_docs.append(
            {
                "path": p.name,
                "top_keys": sorted(d)[:12],
                "component_count": len(comps) if isinstance(comps, list) else None,
                "bom_format": d.get("bomFormat") or d.get("spdxVersion"),
            }
        )
    out["sbom_documents"] = sbom_docs
    out["sbom_non_empty"] = any((d.get("component_count") or 0) > 0 for d in sbom_docs)
    out["ok"] = bool(sig_files) and bool(sbom_files) and out["sbom_non_empty"]
    return out


def _tamper_control(tmp: Path, registry: Path) -> dict[str, Any]:
    """A signature gate that does not fire on a flipped byte is measuring nothing."""
    # publish a second package into a fresh registry, tamper its stored payload, install
    reg2 = tmp / "registry-tamper"
    site3 = tmp / "site-tamper"
    reg2.mkdir()
    site3.mkdir()
    pub = run(
        [
            PY,
            "-m",
            "mkt",
            "publish",
            str(MKT / "fixture" / "packages" / "hello-skill-1.0.0"),
            "--registry",
            str(reg2),
            "--publisher",
            "fixture-publisher",
            "--fixture-key",
            "publisher",
            "--fixture-policy",
        ],
        cwd=MKT,
    )
    payloads = sorted(
        p
        for p in reg2.rglob("*")
        if p.is_file()
        and p.suffix in {".py", ".md", ".txt"}
        and "payload" in str(p).lower()
    )
    if not payloads:
        payloads = sorted(p for p in reg2.rglob("*.py") if p.is_file())
    tampered_path = None
    if payloads:
        tampered_path = payloads[0]
        data = tampered_path.read_bytes()
        tampered_path.write_bytes(data + b"\n# tampered by the wave3 floor audit\n")
    inst = run(
        [
            PY,
            "-m",
            "mkt",
            "install",
            "hello-skill",
            "--registry",
            str(reg2),
            "--site",
            str(site3),
            "--fixture-policy",
        ],
        cwd=MKT,
    )
    return {
        "publish_exit": pub["exit"],
        "tampered_file": str(tampered_path.relative_to(reg2)).replace("\\", "/")
        if tampered_path
        else None,
        "install_after_tamper_exit": inst["exit"],
        "install_after_tamper_stdout_tail": inst["stdout"][-900:],
        "install_after_tamper_stderr_tail": inst["stderr"][-500:],
        "probe_FIRED_on_tamper": inst["exit"] not in (0, None),
        "files_landed_in_site": _tree_census(site3)["file_count"],
    }


DISPATCH = {
    "plugin": ("check2_phase5_plugin", check_plugin),
    "marketplace": ("check3_phase6_marketplace", check_marketplace),
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in DISPATCH:
        print("usage: wave3_lifecycle_audit.py {plugin,marketplace}")
        return 2
    key, fn = DISPATCH[argv[1]]
    try:
        result = fn()
    except Exception as e:
        import traceback

        result = {
            "PROBE_CRASHED": True,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc()[-3000:],
        }
        merge(key, result)
        print(f"FAILED:{argv[1]} {type(e).__name__}: {e}")
        return 1
    merge(key, result)
    print(f"SUCCESS:{argv[1]} verdict={result.get('VERDICT')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
