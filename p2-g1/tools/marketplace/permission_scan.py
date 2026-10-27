"""Declared-versus-exercised permission scanner."""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

PERM_FS_READ = "fs.read"
PERM_FS_WRITE = "fs.write"
PERM_NET = "net.connect"
PERM_SUBPROCESS = "subprocess.spawn"
PERM_ENV = "env.read"
PERM_SECRETS = "secrets.read"

DEFAULT_MARKETPLACE = Path(__file__).resolve().parent / "testdata" / "imp0475"

TOKEN_TO_PERM = {
    "read_text": PERM_FS_READ,
    "read_bytes": PERM_FS_READ,
    "write_text": PERM_FS_WRITE,
    "write_bytes": PERM_FS_WRITE,
    "open": PERM_FS_READ,
    "urlopen": PERM_NET,
    "urlretrieve": PERM_NET,
    "HTTPConnection": PERM_NET,
    "HTTPSConnection": PERM_NET,
    "subprocess": PERM_SUBPROCESS,
    "Popen": PERM_SUBPROCESS,
    "spawn": PERM_SUBPROCESS,
    "environ": PERM_ENV,
    "getenv": PERM_ENV,
}


def load_manifest(package_dir: Path) -> dict[str, Any]:
    root = Path(package_dir)
    path = root / "plugin.json"
    if not path.is_file():
        path = root / "manifest.json"
    from plugin.strict_json import parse_strict

    return parse_strict(path.read_text(encoding="utf-8"))


def _anchors_and_exercised(package_dir: Path) -> tuple[set[str], list[dict[str, Any]]]:
    exercised: set[str] = set()
    anchors: list[dict[str, Any]] = []
    root = Path(package_dir)
    for py in sorted(root.rglob("*.py")):
        if "__pycache__" in py.parts or py.name.startswith("test_"):
            continue
        source = py.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        rel = py.relative_to(root).as_posix()
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            if name in TOKEN_TO_PERM:
                perm = TOKEN_TO_PERM[name]
                exercised.add(perm)
                anchors.append(
                    {
                        "permission": perm,
                        "relpath": rel,
                        "line": int(getattr(node, "lineno", 1) or 1),
                        "qualified": name,
                    }
                )
        if any(marker in source for marker in ("API_KEY", "SECRET_TOKEN", "PASSWORD")):
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            names.update(n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute))
            if "environ" in names or "getenv" in names:
                exercised.add(PERM_SECRETS)
    return exercised, anchors


def _exfiltration(package_dir: Path) -> bool:
    text = ""
    for py in Path(package_dir).rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        text += py.read_text(encoding="utf-8")
    return ("urlopen" in text or "HTTPSConnection" in text) and (
        "API_KEY" in text or "SECRET_TOKEN" in text or "PASSWORD" in text
    )


class ScanReport(dict):
    """Dict report that also exposes attribute access (scan_package(root).flagged)."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def scan_package(package_dir: Path) -> ScanReport:
    root = Path(package_dir)
    manifest = load_manifest(root)
    declared = [str(p) for p in (manifest.get("permissions") or [])]
    exercised, anchors = _anchors_and_exercised(root)
    declared_set = set(declared)
    unexercised = sorted(declared_set - exercised)
    table = []
    for perm in sorted(declared_set | exercised):
        finding = "exercised" if perm in exercised else "unexercised"
        if perm not in declared_set:
            finding = "undeclared-exercised"
        table.append({"permission": perm, "finding": finding})
    flagged = bool(unexercised) or _exfiltration(root) or bool(exercised - declared_set)
    return ScanReport(
        {
            "package_id": str(manifest.get("id") or root.name),
            "package_dir": str(root),
            "declared": declared,
            "exercised": sorted(exercised),
            "unexercised": unexercised,
            "anchors": anchors,
            "table": table,
            "flagged": flagged,
            "exfiltration": _exfiltration(root),
        }
    )


def _packages(marketplace: Path) -> list[Path]:
    index = marketplace / "marketplace.json"
    if index.is_file():
        doc = json.loads(index.read_text(encoding="utf-8"))
        rows = []
        for item in doc.get("packages") or []:
            rows.append(marketplace / item["path"])
        return rows
    return [p for p in sorted(marketplace.iterdir()) if p.is_dir() and (p / "manifest.json").is_file()]


def scan_marketplace(marketplace: Path | None = None) -> dict[str, Any]:
    root = Path(marketplace or DEFAULT_MARKETPLACE)
    packages = [scan_package(p) for p in _packages(root)]
    by_id = {p["package_id"]: p for p in packages}
    malicious = next((p for p in packages if "malicious" in p["package_id"]), None)
    minimal = next((p for p in packages if "minimal" in p["package_id"]), None)
    return {
        "packages": packages,
        "marketplace": str(root),
        "exact_question": {
            "imp0475.malicious": list((malicious or {}).get("unexercised") or []),
            "imp0475.minimal": list((minimal or {}).get("unexercised") or []),
        },
    }


def both_states(marketplace: Path | None = None) -> dict[str, Any]:
    root = Path(marketplace or DEFAULT_MARKETPLACE)
    scan = scan_marketplace(root)
    by_id = {p["package_id"]: p for p in scan["packages"]}
    malicious = by_id.get("malicious") or by_id.get("imp0475-malicious")
    minimal = by_id.get("minimal") or by_id.get("imp0475-minimal")
    if malicious is None or minimal is None:
        # Fall back to directory names.
        for p in scan["packages"]:
            if "malicious" in p["package_id"] or p["package_dir"].endswith("malicious"):
                malicious = p
            if "minimal" in p["package_id"] or p["package_dir"].endswith("minimal"):
                minimal = p
    assert malicious is not None and minimal is not None
    extra_flagged = False
    with tempfile.TemporaryDirectory(prefix="imp0475-mut-") as tmp:
        dest = Path(tmp) / "minimal"
        shutil.copytree(minimal["package_dir"], dest)
        man = load_manifest(dest)
        perms = list(man.get("permissions") or [])
        if PERM_SUBPROCESS not in perms:
            perms.append(PERM_SUBPROCESS)
        man["permissions"] = perms
        (dest / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        extra_flagged = bool(scan_package(dest)["flagged"])
    return {
        "scan": scan,
        "pass": bool(
            malicious["flagged"]
            and not minimal["flagged"]
            and malicious["exfiltration"]
            and extra_flagged
            and not minimal["unexercised"]
        ),
        "malicious_flagged": bool(malicious["flagged"]),
        "minimal_clean": not bool(minimal["flagged"]),
        "malicious_unexercised": list(malicious["unexercised"]),
        "minimal_unexercised": list(minimal["unexercised"]),
        "malicious_exfiltration": bool(malicious["exfiltration"]),
        "mutation_extra_grant_flagged": extra_flagged,
        "packages": scan["packages"],
    }
