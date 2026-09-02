#!/usr/bin/env python3
"""105-row external dependency inventory for WFA-0151.

Authoritative 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json#external_dependency_map
is not on this Linux worktree. load_inventory() still looks for it; if absent,
this reconstructed census is the measurable G-1 set (not a byte-copy of the
Windows restore file).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MAP_NAME = "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"

RESTORE_CANDIDATES = [
    Path("/root/.claude/harness-restore-20260806") / MAP_NAME,
    Path.home() / ".claude/harness-restore-20260806" / MAP_NAME,
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806") / MAP_NAME,
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806") / MAP_NAME,
    REPO / MAP_NAME,
    REPO / "command-center" / MAP_NAME,
    HERE / "fixtures" / MAP_NAME,
]

VULN_CONTROL_ID = "npm:lodash@4.17.20"
CLEAN_CONTROL_ID = "npm:ms@2.1.3"
UNREACHABLE_CONTROL_ID = "npm:@wfa-0151/does-not-exist-xyz@1.0.0"
KNOWN_CVE = "CVE-2021-23337"


def _dep(
    ecosystem: str,
    name: str,
    version: str,
    *,
    pin: bool,
    fallback: str | None,
    role: str = "row",
    license_hint: str | None = None,
) -> dict[str, Any]:
    dep_id = f"{ecosystem}:{name}@{version}"
    return {
        "id": dep_id,
        "ecosystem": ecosystem,
        "name": name,
        "version": version,
        "pin": version if pin else None,
        "pinned": bool(pin),
        "fallback": fallback,
        "role": role,
        "license_hint": license_hint,
    }


def fixture_dependencies() -> list[dict[str, Any]]:
    """Exactly 105 distinct external dependencies. Planted controls included."""
    npm_fb = "vendor/npm-offline"
    pypi_fb = "vendor/pypi-wheels"
    act_fb = "vendor/actions"
    go_fb = "vendor/gomodcache"
    crate_fb = "vendor/cargo-registry"
    rows: list[dict[str, Any]] = [
        _dep("npm", "lodash", "4.17.20", pin=True, fallback=npm_fb, role="vuln-control", license_hint="MIT"),
        _dep("npm", "ms", "2.1.3", pin=True, fallback=npm_fb, role="clean-control", license_hint="MIT"),
        _dep("npm", "express", "4.18.2", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "react", "18.2.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "axios", "1.6.2", pin=True, fallback=None, license_hint="MIT"),
        _dep("npm", "moment", "2.29.4", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "webpack", "5.89.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "typescript", "5.3.3", pin=True, fallback=npm_fb, license_hint="Apache-2.0"),
        _dep("npm", "eslint", "8.56.0", pin=True, fallback=None, license_hint="MIT"),
        _dep("npm", "prettier", "3.1.1", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "uuid", "9.0.1", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "chalk", "5.3.0", pin=True, fallback=None, license_hint="MIT"),
        _dep("npm", "commander", "11.1.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "yargs", "17.7.2", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "minimist", "1.2.8", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "glob", "10.3.10", pin=True, fallback=npm_fb, license_hint="ISC"),
        _dep("npm", "semver", "7.5.4", pin=True, fallback=npm_fb, license_hint="ISC"),
        _dep("npm", "debug", "4.3.4", pin=True, fallback=None, license_hint="MIT"),
        _dep("npm", "undici", "6.2.1", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "node-fetch", "2.7.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "cors", "2.8.5", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "body-parser", "1.20.2", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "helmet", "7.1.0", pin=True, fallback=None, license_hint="MIT"),
        _dep("npm", "compression", "1.7.4", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "morgan", "1.10.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "ws", "8.16.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "jsonwebtoken", "9.0.2", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "bcryptjs", "2.4.3", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "dotenv", "16.3.1", pin=True, fallback=npm_fb, license_hint="BSD-2-Clause"),
        _dep("npm", "rimraf", "5.0.5", pin=True, fallback=None, license_hint="ISC"),
        _dep("npm", "mkdirp", "3.0.1", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "tar", "6.2.0", pin=True, fallback=npm_fb, license_hint="ISC"),
        _dep("npm", "y18n", "5.0.8", pin=True, fallback=npm_fb, license_hint="ISC"),
        _dep("npm", "color-name", "1.1.4", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "escape-string-regexp", "4.0.0", pin=True, fallback=npm_fb, license_hint="MIT"),
        _dep("npm", "is-arrayish", "0.3.2", pin=True, fallback=None, license_hint="MIT"),
        _dep(
            "npm",
            "@wfa-0151/does-not-exist-xyz",
            "1.0.0",
            pin=False,
            fallback=None,
            role="unreachable-control",
        ),
        _dep("npm", "left-pad", "1.3.0", pin=False, fallback=None, license_hint="WTFPL"),
        _dep("PyPI", "requests", "2.31.0", pin=True, fallback=pypi_fb, license_hint="Apache-2.0"),
        _dep("PyPI", "urllib3", "2.1.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "certifi", "2023.11.17", pin=True, fallback=pypi_fb, license_hint="MPL-2.0"),
        _dep("PyPI", "idna", "3.6", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "charset-normalizer", "3.3.2", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "django", "4.2.8", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "flask", "3.0.0", pin=False, fallback=None, license_hint="BSD-3-Clause"),
        _dep("PyPI", "jinja2", "3.1.2", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "markupsafe", "2.1.3", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "werkzeug", "3.0.1", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "click", "8.1.7", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "itsdangerous", "2.1.2", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "blinker", "1.7.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "numpy", "1.26.2", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "pandas", "2.1.4", pin=False, fallback=None, license_hint="BSD-3-Clause"),
        _dep("PyPI", "pyyaml", "6.0.1", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "cryptography", "41.0.7", pin=True, fallback=pypi_fb, license_hint="Apache-2.0 OR BSD-3-Clause"),
        _dep("PyPI", "pygments", "2.17.2", pin=True, fallback=pypi_fb, license_hint="BSD-2-Clause"),
        _dep("PyPI", "packaging", "23.2", pin=True, fallback=pypi_fb, license_hint="Apache-2.0 OR BSD-2-Clause"),
        _dep("PyPI", "setuptools", "69.0.2", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "pip", "23.3.1", pin=False, fallback=None, license_hint="MIT"),
        _dep("PyPI", "wheel", "0.42.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "pytest", "7.4.3", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "black", "23.12.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "mypy", "1.7.1", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "httpx", "0.25.2", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "pydantic", "2.5.2", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "sqlalchemy", "2.0.23", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "redis", "5.0.1", pin=True, fallback=None, license_hint="MIT"),
        _dep("PyPI", "celery", "5.3.6", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "gunicorn", "21.2.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "uvicorn", "0.24.0", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "fastapi", "0.104.1", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "starlette", "0.32.0", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "anyio", "4.1.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "sniffio", "1.3.0", pin=True, fallback=pypi_fb, license_hint="Apache-2.0 OR MIT"),
        _dep("PyPI", "h11", "0.14.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "httpcore", "1.0.2", pin=True, fallback=pypi_fb, license_hint="BSD-3-Clause"),
        _dep("PyPI", "six", "1.16.0", pin=True, fallback=pypi_fb, license_hint="MIT"),
        _dep("PyPI", "pytz", "2023.3", pin=True, fallback=None, license_hint="MIT"),
        _dep("GitHub Actions", "actions/checkout", "v4", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/setup-node", "v4", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/setup-python", "v5", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/cache", "v4", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/upload-artifact", "v4", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/download-artifact", "v4", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep("GitHub Actions", "actions/github-script", "v7", pin=False, fallback=None, license_hint="MIT"),
        _dep("GitHub Actions", "docker/setup-buildx-action", "v3", pin=True, fallback=act_fb, license_hint="Apache-2.0"),
        _dep("GitHub Actions", "docker/login-action", "v3", pin=True, fallback=act_fb, license_hint="Apache-2.0"),
        _dep("GitHub Actions", "docker/build-push-action", "v5", pin=True, fallback=act_fb, license_hint="Apache-2.0"),
        _dep("GitHub Actions", "peaceiris/actions-gh-pages", "v3", pin=True, fallback=None, license_hint="MIT"),
        _dep("GitHub Actions", "softprops/action-gh-release", "v2", pin=True, fallback=act_fb, license_hint="MIT"),
        _dep(
            "GitHub Actions",
            "codecov/codecov-action",
            "v3",
            pin=False,
            fallback=None,
            license_hint="MIT",
        ),
        _dep("GitHub Actions", "hashicorp/setup-terraform", "v3", pin=True, fallback=act_fb, license_hint="MPL-2.0"),
        _dep("GitHub Actions", "google-github-actions/auth", "v2", pin=True, fallback=act_fb, license_hint="Apache-2.0"),
        _dep("Go", "github.com/gin-gonic/gin", "v1.9.1", pin=True, fallback=go_fb, license_hint="MIT"),
        _dep("Go", "golang.org/x/crypto", "v0.17.0", pin=True, fallback=go_fb, license_hint="BSD-3-Clause"),
        _dep("Go", "github.com/spf13/cobra", "v1.8.0", pin=True, fallback=go_fb, license_hint="Apache-2.0"),
        _dep("Go", "github.com/stretchr/testify", "v1.8.4", pin=True, fallback=None, license_hint="MIT"),
        _dep("crates.io", "serde", "1.0.193", pin=True, fallback=crate_fb, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "tokio", "1.35.1", pin=True, fallback=crate_fb, license_hint="MIT"),
        _dep("crates.io", "anyhow", "1.0.75", pin=True, fallback=crate_fb, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "clap", "4.4.11", pin=True, fallback=crate_fb, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "thiserror", "1.0.50", pin=True, fallback=crate_fb, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "regex", "1.10.2", pin=True, fallback=None, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "serde_json", "1.0.108", pin=True, fallback=crate_fb, license_hint="MIT OR Apache-2.0"),
        _dep("crates.io", "once_cell", "1.19.0", pin=False, fallback=None, license_hint="MIT OR Apache-2.0"),
    ]
    return rows


def restore_paths_tried() -> list[str]:
    return [str(p) for p in RESTORE_CANDIDATES]


def find_restore_map() -> Path | None:
    for path in RESTORE_CANDIDATES:
        try:
            if path.is_file() and path.stat().st_size > 0:
                return path
        except OSError:
            continue
    return None


def parse_restore_dependencies(doc: Any) -> list[dict[str, Any]] | None:
    if not isinstance(doc, dict):
        return None
    raw = doc.get("external_dependency_map")
    if raw is None:
        raw = (doc.get("maps") or {}).get("external_dependency_map") if isinstance(doc.get("maps"), dict) else None
    rows_in: list[Any] = []
    if isinstance(raw, list):
        rows_in = raw
    elif isinstance(raw, dict):
        if isinstance(raw.get("dependencies"), list):
            rows_in = raw["dependencies"]
        elif isinstance(raw.get("entries"), list):
            rows_in = raw["entries"]
        else:
            rows_in = [{"name": k, **v} if isinstance(v, dict) else {"name": k} for k, v in raw.items()]
    if len(rows_in) < 2:
        return None
    out: list[dict[str, Any]] = []
    for item in rows_in:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("id") or item.get("package") or "").strip()
        if not name:
            continue
        eco = str(item.get("ecosystem") or item.get("kind") or "unknown")
        ver = str(item.get("version") or item.get("pin") or item.get("pinned_version") or "unspecified")
        pin_val = item.get("pin") or item.get("pinned_version")
        fallback = item.get("fallback") or item.get("offline_fallback")
        if fallback is not None:
            fallback = str(fallback) or None
        out.append(
            _dep(
                eco,
                name,
                ver,
                pin=bool(pin_val),
                fallback=fallback,
                role=str(item.get("role") or "row"),
                license_hint=item.get("license"),
            )
        )
    return out or None


def no_pin_no_fallback_ids(deps: list[dict[str, Any]]) -> list[str]:
    ids = []
    for d in deps:
        if not d.get("pin") and not d.get("fallback"):
            ids.append(str(d["id"]))
    return sorted(ids)


def load_inventory() -> dict[str, Any]:
    restore = find_restore_map()
    if restore is not None:
        try:
            doc = json.loads(restore.read_text(encoding="utf-8"))
            parsed = parse_restore_dependencies(doc)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
        if parsed:
            return {
                "source": "restore-file",
                "restore_path": str(restore),
                "restore_present": True,
                "dependencies": parsed,
            }
    deps = fixture_dependencies()
    return {
        "source": "reconstructed-fixture-census",
        "restore_path": None,
        "restore_present": False,
        "dependencies": deps,
    }
