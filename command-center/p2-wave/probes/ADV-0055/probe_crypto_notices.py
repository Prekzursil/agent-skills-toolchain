#!/usr/bin/env python
"""ADV-0055 named probes: export-control / cryptography-distribution review.

Probe 1: enumerate crypto-bearing components in the resolved dependency tree,
distinguishing BUNDLED implementations from calls into the platform's own libraries.
Probe 2 (mechanically different): check the BUILT artifact / release metadata for the
presence of the required distribution notices, rather than checking the source repo.

Control (catalog): a component known to bundle crypto must appear in probe 1; an empty
enumeration on a package that ships a signer means the traversal missed transitives.
The known bundler on this tree: platform/marketplace/mkt/crypto.py, a self-declared
pure-Python RFC 8032 Ed25519 (its own module docstring says so).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

#: platform-provided crypto surfaces (calls into the OS/Python stdlib, not bundled code)
PLATFORM_CALL_PATTERNS = {
    "hashlib": r"\bhashlib\.[a-z0-9_]+\(",
    "hmac": r"\bhmac\.(compare_digest|new|digest)\(",
    "secrets": r"\bsecrets\.",
    "ssl": r"\bssl\.(create_default_context|wrap_socket)\(",
    "uuid-os-entropy": r"\bos\.urandom\(",
}
#: bundled-crypto signatures (implementation bodies, not calls)
BUNDLED_PATTERNS = {
    "ed25519-constants": r"2\*\*255\s*-\s*19",
    "rfc8032-mention": r"RFC 8032",
    "sha256-long-walk": r"_sha256_compress|rotr\(|sigma0\(",
    "aes-sbox": r"Sbox|SBOX|_S_BOX",
    "rsa-bigint": r"pow\(\s*\w+\s*,\s*\w+\s*,\s*\w+\s*\).*#.*rsa|# rsa modular exponentiation",
}

PRODUCTION_ROOTS = ["platform", "tools", "hooks"]


def probe1_enumerate() -> dict:
    out = {"platform_calls": [], "bundled": [], "scanned_files": 0}
    for root in PRODUCTION_ROOTS:
        base = REPO / root
        for py in base.rglob("*.py"):
            rel = str(py.relative_to(REPO)).replace("\\", "/")
            if "/test_" in rel or rel.endswith("conftest.py") or "/__pycache__/" in rel:
                continue
            try:
                text = py.read_text(encoding="utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            out["scanned_files"] += 1
            for name, pat in PLATFORM_CALL_PATTERNS.items():
                n = len(re.findall(pat, text))
                if n:
                    out["platform_calls"].append(
                        {"component": rel, "surface": name, "calls": n,
                         "classification": "platform-library-call"})
            for name, pat in BUNDLED_PATTERNS.items():
                n = len(re.findall(pat, text))
                if n:
                    out["bundled"].append(
                        {"component": rel, "primitive": name, "matches": n,
                         "classification": "bundled-implementation"})

    # dependency-tree side: node lockfile + python requirements, if present
    deps = {}
    lock = REPO / "package-lock.json"
    if lock.is_file():
        try:
            d = json.loads(lock.read_text(encoding="utf-8"))
            pkgs = d.get("packages", {})
            crypto_names = [k for k in pkgs
                            if re.search(r"crypt|sha|hash|ed25519|sodium|ssl|tls|openssl"
                                         "|tweetnacl|noble", k, re.I)]
            deps["npm_lockfile_packages_total"] = len(pkgs)
            deps["npm_crypto_named_packages"] = crypto_names[:20]
        except Exception as exc:  # noqa: BLE001
            deps["npm_lockfile_error"] = str(exc)[:120]
    for req in ("requirements.txt", "requirements-lock.txt", "pyproject.toml"):
        f = REPO / req
        if f.is_file():
            deps.setdefault("python_manifests_present", []).append(req)
    out["dependency_tree"] = deps
    return out


def probe2_notice_check() -> dict:
    """Look INSIDE the built/ship surfaces for crypto distribution notices."""
    findings: list[dict] = []
    surfaces: list[Path] = []

    # the release tree
    rel_root = REPO / "release"
    if rel_root.is_dir():
        surfaces.extend(sorted(rel_root.rglob("*"))[:400])
    # top-level metadata files
    for name in ("package.json", "README.md", "SECURITY.md", "NOTICE", "LICENSE",
                 "NOTICE.md", "LICENSE.md", "LICENSE.txt"):
        f = REPO / name
        if f.is_file():
            surfaces.append(f)
    # the shipped plugin manifest + dispatch manifest + built SBOM probe artifacts
    for name in (".claude-plugin/plugin.json", "hooks/_dispatch/manifest.json",
                 "command-center/p2-wave/probes/IMP-0062/probe1-sbom.json"):
        f = REPO / name
        if f.is_file():
            surfaces.append(f)

    notice_pat = re.compile(
        r"TSU|EAR\b|export[- ]control|Export Administration|ECCN|crypto"
        r"|cryptograph|encryption.{0,40}(notice|classification)|open-?ssl notice",
        re.I)
    crypto_pat = re.compile(r"ed25519|Ed25519|sha-?256|crypto", re.I)

    for f in surfaces:
        if not f.is_file():
            continue
        rel = str(f.relative_to(REPO)).replace("\\", "/")
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        crypto_mentions = crypto_pat.findall(text)
        notice_mentions = notice_pat.findall(text)
        if crypto_mentions or notice_mentions:
            findings.append({
                "surface": rel,
                "crypto_mentions": len(crypto_mentions),
                "notice_mentions": len(notice_mentions),
                "notice_terms": sorted(set(notice_pat.findall(text)))[:6],
            })
    return {"surfaces_scanned": len(surfaces), "findings": findings}


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-1-BEGIN:ADV-0055 (bundled vs platform crypto enumeration)")
    p1 = probe1_enumerate()
    say(f"scanned_files={p1['scanned_files']}")
    for b in p1["bundled"]:
        say(f"BUNDLED {b['component']} primitive={b['primitive']} matches={b['matches']}")
    for c in p1["platform_calls"]:
        say(f"PLATFORM-CALL {c['component']} surface={c['surface']} calls={c['calls']}")
    say(f"deps={json.dumps(p1['dependency_tree'])[:200]}")
    control = any("mkt/crypto.py" in b["component"] for b in p1["bundled"])
    say(f"CONTROL known_bundler_mkt_crypto_py_in_probe1={control} "
        f"(must be True or the traversal missed transitives)")
    say("PROBE-1-COMPLETE:ADV-0055")

    say("PROBE-2-BEGIN:ADV-0055 (built-artifact notice presence check)")
    p2 = probe2_notice_check()
    say(f"surfaces_scanned={p2['surfaces_scanned']}")
    for f in p2["findings"]:
        say(f"SURFACE {f['surface']} crypto_mentions={f['crypto_mentions']} "
            f"notice_mentions={f['notice_mentions']} terms={f['notice_terms']}")
    has_export_notice = any(
        any(re.search(r"TSU|EAR|ECCN|export[- ]control", t, re.I)
            for t in f["notice_terms"])
        for f in p2["findings"])
    say(f"MEASURE export_control_notice_present_in_release_metadata="
        f"{has_export_notice}")
    say("PROBE-2-COMPLETE:ADV-0055")

    results = {"probe1": p1, "probe2": p2,
               "control_known_bundler_present": control,
               "export_control_notice_present": has_export_notice}
    out = PROBE_DIR / "crypto-notice-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    raw = PROBE_DIR / "probe-crypto-notices.raw.txt"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
