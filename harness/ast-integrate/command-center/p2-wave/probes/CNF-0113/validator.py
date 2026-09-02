#!/usr/bin/env python3
"""Marketplace package validator for CNF-0113.

Named rules (reject vs warn are distinct dispositions and distinct exit codes):

  MP-PERM-EXCESSIVE       reject  permission outside the package-root allow-list
  MP-POSTINSTALL-NETWORK  reject  install-time script that reaches the network
  MP-PATH-TRAVERSAL       reject  declared or on-disk path that escapes the package
  MP-TYPOSQUAT            reject  name collides with a registry package
  MP-UNSIGNED-PUBLISHER   warn    publisher.signed is false or signature missing

Materialize never writes a path that resolves outside the sandbox, even when a
rule is not consulted. Install-time scripts are inspected, never executed.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_REGISTRY = HERE / "fixtures" / "registry.json"

RULE_PERM = "MP-PERM-EXCESSIVE"
RULE_POSTINSTALL_NET = "MP-POSTINSTALL-NETWORK"
RULE_TRAVERSAL = "MP-PATH-TRAVERSAL"
RULE_TYPOSQUAT = "MP-TYPOSQUAT"
RULE_UNSIGNED = "MP-UNSIGNED-PUBLISHER"

EXIT_PASS = 0
EXIT_WARN = 10
EXIT_REJECT = 20

ALLOWED_PERMISSIONS = frozenset(
    {
        "fs:package-root",
        "fs:read-package",
        "network:none",
    }
)

NETWORK_RE = re.compile(
    r"(?:"
    r"\bcurl\b|\bwget\b|\bnetcat\b|\bnc\b|"
    r"fetch\s*\(|invoke-webrequest|"
    r"https?://|/dev/tcp|"
    r"socket\.(?:connect|create)|"
    r"urllib|requests\.(?:get|post|put|delete)|"
    r"http\.client|aiohttp"
    r")",
    re.IGNORECASE,
)

HOMOGLYPH = str.maketrans(
    {
        "\u0430": "a",  # Cyrillic a
        "\u0435": "e",
        "\u043e": "o",
        "\u0456": "i",
        "\u0455": "s",
        "\u0440": "p",
        "\u0441": "c",
        "\u0443": "y",
        "\u04bb": "h",
        "\u03b1": "a",
        "\u03bf": "o",
        "\uff41": "a",
        "\uff45": "e",
        "\uff4f": "o",
        "\uff49": "i",
        "\uff53": "s",
    }
)


def load_registry(path: Path | None = None) -> list[str]:
    src = path or DEFAULT_REGISTRY
    data = json.loads(src.read_text(encoding="utf-8"))
    names = data.get("packages") if isinstance(data, dict) else data
    return [str(n) for n in (names or []) if str(n).strip()]


def load_manifest(package_dir: Path) -> dict[str, Any]:
    for name in ("plugin.json", "marketplace.json", "package.json"):
        p = package_dir / name
        if p.is_file():
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                return doc
    return {}


def fold_name(name: str) -> str:
    nfkc = unicodedata.normalize("NFKC", name)
    return nfkc.translate(HOMOGLYPH).casefold()


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def is_typosquat(name: str, registry: list[str]) -> tuple[bool, str]:
    folded = fold_name(name)
    for other in registry:
        if other == name:
            continue
        of = fold_name(other)
        if folded == of:
            return True, f"casefold/homoglyph collision with {other!r}"
        if min(len(folded), len(of)) >= 5 and levenshtein(folded, of) <= 1:
            return True, f"edit-distance-1 collision with {other!r}"
    return False, ""


def is_absolute_rel(rel: str) -> bool:
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        return True
    if len(rel) >= 2 and rel[1] == ":":
        return True
    return False


def safe_join(root: Path, rel: str) -> Path | None:
    """Return sandbox-inside path, or None if the entry would escape."""
    if is_absolute_rel(rel):
        return None
    if ".." in Path(rel).parts:
        return None
    root_res = root.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root_res)
    except ValueError:
        return None
    return candidate


def declared_file_entries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in manifest.get("files") or []:
        if isinstance(item, str):
            out.append({"path": item, "contents": ""})
        elif isinstance(item, dict) and item.get("path"):
            out.append(
                {
                    "path": str(item["path"]),
                    "contents": str(item.get("contents") or ""),
                }
            )
    return out


def install_scripts(manifest: dict[str, Any]) -> list[str]:
    scripts = manifest.get("scripts") or {}
    bodies: list[str] = []
    if isinstance(scripts, dict):
        for key in ("preinstall", "install", "postinstall", "post-install"):
            val = scripts.get(key)
            if isinstance(val, str) and val.strip():
                bodies.append(val)
    elif isinstance(scripts, list):
        bodies.extend(str(s) for s in scripts if str(s).strip())
    return bodies


def publisher_signed(manifest: dict[str, Any]) -> bool:
    pub = manifest.get("publisher")
    if not isinstance(pub, dict):
        return False
    if pub.get("signed") is True and str(pub.get("signature") or "").strip():
        return True
    return False


def find_on_disk_escapes(package_dir: Path) -> list[str]:
    escapes: list[str] = []
    root = package_dir.resolve()
    if not package_dir.is_dir():
        return escapes
    for p in package_dir.rglob("*"):
        if p.is_symlink():
            target = p.resolve()
            try:
                target.relative_to(root)
            except ValueError:
                escapes.append(str(p.relative_to(package_dir)))
            continue
        try:
            p.resolve().relative_to(root)
        except ValueError:
            escapes.append(str(p.relative_to(package_dir)))
    return escapes


def materialize(
    entries: list[dict[str, str]], sandbox: Path
) -> tuple[list[str], list[str]]:
    """Write only sandbox-inside paths. Returns (written, refused)."""
    sandbox.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    refused: list[str] = []
    for entry in entries:
        rel = entry["path"]
        dest = safe_join(sandbox, rel)
        if dest is None:
            refused.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(entry.get("contents") or "", encoding="utf-8")
        written.append(rel)
    return written, refused


def validate_package(
    package_dir: Path,
    *,
    registry: list[str] | None = None,
    sandbox: Path | None = None,
    materialize_files: bool = True,
) -> dict[str, Any]:
    package_dir = Path(package_dir)
    names = registry if registry is not None else load_registry()
    manifest = load_manifest(package_dir)
    findings: list[dict[str, str]] = []

    pkg_name = str(manifest.get("name") or package_dir.name)

    perms = manifest.get("permissions") or []
    if not isinstance(perms, list):
        perms = [str(perms)]
    bad_perms = sorted({str(p) for p in perms if str(p) not in ALLOWED_PERMISSIONS})
    if bad_perms:
        findings.append(
            {
                "rule": RULE_PERM,
                "severity": "reject",
                "message": "excessive permissions: " + ", ".join(bad_perms),
            }
        )

    for body in install_scripts(manifest):
        if NETWORK_RE.search(body):
            findings.append(
                {
                    "rule": RULE_POSTINSTALL_NET,
                    "severity": "reject",
                    "message": "install-time script reaches the network",
                }
            )
            break

    entries = declared_file_entries(manifest)
    traversal_paths = [
        e["path"] for e in entries if safe_join(package_dir, e["path"]) is None
    ]
    traversal_paths.extend(find_on_disk_escapes(package_dir))
    # Dedup while preserving order
    seen: set[str] = set()
    uniq_trav: list[str] = []
    for t in traversal_paths:
        if t not in seen:
            seen.add(t)
            uniq_trav.append(t)
    if uniq_trav:
        findings.append(
            {
                "rule": RULE_TRAVERSAL,
                "severity": "reject",
                "message": "path escapes package root: " + "; ".join(uniq_trav),
            }
        )

    hit, why = is_typosquat(pkg_name, names)
    if hit:
        findings.append(
            {
                "rule": RULE_TYPOSQUAT,
                "severity": "reject",
                "message": why,
            }
        )

    if not publisher_signed(manifest):
        findings.append(
            {
                "rule": RULE_UNSIGNED,
                "severity": "warn",
                "message": "publisher is unsigned or signature is missing",
            }
        )

    wrote: list[str] = []
    refused: list[str] = []
    wrote_outside = False
    if materialize_files and sandbox is not None:
        wrote, refused = materialize(entries, Path(sandbox))
        # Refused paths are the write-gate; never set wrote_outside True.
        wrote_outside = False
        for rel in wrote:
            dest = safe_join(Path(sandbox), rel)
            if dest is None:
                wrote_outside = True

    rejects = [f for f in findings if f["severity"] == "reject"]
    warns = [f for f in findings if f["severity"] == "warn"]
    if rejects:
        disposition = "reject"
        exit_code = EXIT_REJECT
        firing_rule = rejects[0]["rule"]
    elif warns:
        disposition = "warn"
        exit_code = EXIT_WARN
        firing_rule = warns[0]["rule"]
    else:
        disposition = "pass"
        exit_code = EXIT_PASS
        firing_rule = None

    return {
        "package_dir": str(package_dir),
        "name": pkg_name,
        "disposition": disposition,
        "exit_code": exit_code,
        "firing_rule": firing_rule,
        "findings": findings,
        "rejections": rejects,
        "warnings": warns,
        "materialized": wrote,
        "refused_writes": refused,
        "wrote_outside_sandbox": wrote_outside,
        "scripts_executed": False,
    }


def classify_buckets(results: list[dict[str, Any]]) -> dict[str, list[str]]:
    rejected = [r["name"] for r in results if r["disposition"] == "reject"]
    warned = [r["name"] for r in results if r["disposition"] == "warn"]
    passed = [r["name"] for r in results if r["disposition"] == "pass"]
    return {"rejected": rejected, "warned": warned, "passed": passed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNF-0113 marketplace validator")
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--sandbox", type=Path, default=None)
    args = parser.parse_args(argv)
    result = validate_package(
        args.package_dir,
        registry=load_registry(args.registry),
        sandbox=args.sandbox,
        materialize_files=args.sandbox is not None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
