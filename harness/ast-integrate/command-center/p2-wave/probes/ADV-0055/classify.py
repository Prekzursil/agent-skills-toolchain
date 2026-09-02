"""Bundled-versus-platform crypto classification for ADV-0055.

Walks a resolved dependency tree (transitive), then independently classifies
Python imports. Platform stdlib hashing/TLS is not a distribution-notice
trigger. Known bundled implementations (OpenSSL-in-cryptography, libsodium,
etc.) are.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

PLATFORM_IMPORT_ROOTS = frozenset(
    {
        "hashlib",
        "hmac",
        "ssl",
        "secrets",
        "_hashlib",
        "_ssl",
        "hashlib",
    }
)

# Third-party packages whose wheels/source typically ship a cryptographic
# implementation (OpenSSL, libsodium, nettle, …) rather than calling the OS.
BUNDLED_PACKAGES: dict[str, dict[str, str]] = {
    "cryptography": {
        "impl": "pyca/cryptography wheels bundle OpenSSL",
        "obligation": "OpenSSL attribution plus encryption-software distribution notices",
    },
    "pyopenssl": {
        "impl": "pyOpenSSL binds OpenSSL",
        "obligation": "OpenSSL attribution",
    },
    "openssl": {
        "impl": "OpenSSL itself",
        "obligation": "OpenSSL attribution plus EAR/ECCN channel notices",
    },
    "pycryptodome": {
        "impl": "bundled C crypto (AES/RSA/etc.)",
        "obligation": "encryption-software distribution notices",
    },
    "pycrypto": {
        "impl": "bundled C crypto",
        "obligation": "encryption-software distribution notices",
    },
    "pynacl": {
        "impl": "libsodium",
        "obligation": "libsodium/NaCl distribution notices",
    },
    "nacl": {
        "impl": "libsodium (import name)",
        "obligation": "libsodium/NaCl distribution notices",
    },
    "bcrypt": {
        "impl": "bundled Blowfish C",
        "obligation": "encryption-software distribution notices",
    },
    "argon2-cffi": {
        "impl": "bundled Argon2 C",
        "obligation": "encryption-software distribution notices",
    },
    "cryptography-vectors": {
        "impl": "test vectors for cryptography (not a runtime impl)",
        "obligation": "none-runtime",
    },
}

BUNDLED_IMPORT_ROOTS = frozenset(
    {
        "cryptography",
        "OpenSSL",
        "Crypto",
        "Cryptodome",
        "nacl",
        "bcrypt",
        "argon2",
    }
)

LIVE_SCAN_ROOTS = (
    "tools/plugin",
    "tools/marketplace",
    "tools/command-center",
)


def _norm_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def classify_package_name(name: str) -> str:
    n = _norm_name(name)
    if n in BUNDLED_PACKAGES and BUNDLED_PACKAGES[n].get("obligation") != "none-runtime":
        return "bundled"
    if n in {"hashlib", "hmac", "ssl", "secrets"}:
        return "platform"
    return "other"


def walk_lockfile_transitive(tree: dict[str, Any]) -> list[str]:
    """BFS over depends_on from declared direct deps. Includes transitives."""
    nodes = tree.get("nodes") or {}
    if not isinstance(nodes, dict):
        return []
    stack = [str(x) for x in (tree.get("direct") or [])]
    seen: list[str] = []
    visited: set[str] = set()
    while stack:
        name = stack.pop()
        key = _norm_name(name) if name.lower() != name else name
        # Prefer exact key, then case-insensitive.
        real = name if name in nodes else next((k for k in nodes if k.lower() == name.lower()), name)
        if real in visited:
            continue
        visited.add(real)
        seen.append(real)
        meta = nodes.get(real) if isinstance(nodes.get(real), dict) else {}
        for child in meta.get("depends_on") or []:
            stack.append(str(child))
    return seen


def walk_lockfile_direct_only(tree: dict[str, Any]) -> list[str]:
    """Mutant: declared direct deps only. Misses transitive cryptography."""
    return [str(x) for x in (tree.get("direct") or [])]


def bundled_in_closure(names: Iterable[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in names:
        kind = classify_package_name(raw)
        if kind != "bundled":
            continue
        n = _norm_name(raw)
        info = BUNDLED_PACKAGES.get(n) or {}
        out.append(
            {
                "name": raw,
                "classification": "bundled",
                "impl": str(info.get("impl") or "bundled-crypto"),
                "obligation": str(info.get("obligation") or "distribution-notice"),
            }
        )
    return out


def load_tree(name: str) -> dict[str, Any]:
    path = FIXTURES / "trees" / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"tree {name} is not an object")
    return data


def classify_import_root(root: str) -> str:
    if root in PLATFORM_IMPORT_ROOTS:
        return "platform"
    if root in BUNDLED_IMPORT_ROOTS:
        return "bundled"
    return "other"


def scan_python_imports(root: Path, repo: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if not root.is_dir():
        return hits
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        rel = path.relative_to(repo).as_posix()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names if a.name]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for dotted in names:
                top = dotted.split(".")[0]
                kind = classify_import_root(top)
                if kind == "other":
                    continue
                hits.append(
                    {
                        "path": rel,
                        "line": int(getattr(node, "lineno", 1) or 1),
                        "module": dotted,
                        "root": top,
                        "classification": kind,
                    }
                )
    return hits


def scan_live_tooling(repo: Path) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for rel in LIVE_SCAN_ROOTS:
        hits.extend(scan_python_imports(repo / rel, repo))
    bundled = [h for h in hits if h["classification"] == "bundled"]
    platform = [h for h in hits if h["classification"] == "platform"]
    return {
        "roots": list(LIVE_SCAN_ROOTS),
        "bundled_import_count": len(bundled),
        "platform_import_count": len(platform),
        "bundled_imports": bundled[:40],
        "platform_imports_sample": platform[:40],
        "platform_modules": sorted({h["root"] for h in platform}),
        "bundled_modules": sorted({h["root"] for h in bundled}),
    }


def evaluate_signer_control(tree: dict[str, Any]) -> dict[str, Any]:
    trans = walk_lockfile_transitive(tree)
    direct = walk_lockfile_direct_only(tree)
    bundled_t = bundled_in_closure(trans)
    bundled_d = bundled_in_closure(direct)
    ships = bool(tree.get("ships_signer"))
    empty_trans = ships and not bundled_t
    return {
        "tree_id": tree.get("id"),
        "ships_signer": ships,
        "transitive_names": trans,
        "direct_names": direct,
        "bundled_transitive": bundled_t,
        "bundled_direct_only": bundled_d,
        "control_pass": bool(bundled_t) and not empty_trans,
        "direct_only_misses_transitive": bool(bundled_t) and not bundled_d,
        "empty_on_signer_means_missed_transitives": empty_trans,
    }
