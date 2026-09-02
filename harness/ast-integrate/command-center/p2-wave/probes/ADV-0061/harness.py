"""Shared ADV-0061 fixtures: pinned vs unpinned blobs, lockfile, capture."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.fetch import FetchError, fetch_to_cache  # noqa: E402
from marketplace.install import InstallRequest, marketplace_install  # noqa: E402
from marketplace.tests.support import (  # noqa: E402
    KEY_ID,
    PACKAGE_ID,
    PACKAGE_REF,
    PACKAGE_VERSION,
    generate_publisher,
    linux_compat,
    lockfile_for,
    sign_digest,
)
from marketplace.verify import (  # noqa: E402
    GateFailure,
    blob_digest,
    run_verification,
)
from plugin.census import census  # noqa: E402
from plugin.installer import install_direct, install_from_handoff  # noqa: E402
from plugin.payloadutil import PAYLOAD_FILES, PAYLOAD_MODES, write_deterministic_tar  # noqa: E402
from plugin.repair import seed_install  # noqa: E402

UNIT = "ADV-0061"
PINNED_VERSION = "1.0.1"
UNPINNED_VERSION = "9.9.9"
SCAN_RELS = (
    "tools/marketplace/install.py",
    "tools/marketplace/verify.py",
    "tools/marketplace/fetch.py",
    "tools/marketplace/handoff.py",
    "tools/plugin/installer.py",
    "tools/plugin/repair.py",
)
WARN_NEEDLES = ("lockfile", "pin", "pinned", "digest mismatch", "unpinned")


def blob_for(tmp: Path, version: str, name: str) -> tuple[Path, str]:
    files = dict(PAYLOAD_FILES)
    files["plugin.json"] = json.dumps(
        {"name": "demo", "version": version}, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    dest = tmp / name
    digest = write_deterministic_tar(dest, files=files, modes=dict(PAYLOAD_MODES))
    return dest, digest


def signed_pair(tmp: Path) -> dict[str, Any]:
    pinned, pin = blob_for(tmp, PINNED_VERSION, "pinned.tar.gz")
    unpinned, other = blob_for(tmp, UNPINNED_VERSION, "unpinned.tar.gz")
    if pin == other:
        raise AssertionError("pinned and unpinned blobs must differ")
    private, public_hex = generate_publisher()
    return {
        "pinned": pinned,
        "pin": pin,
        "unpinned": unpinned,
        "other": other,
        "signature": sign_digest(private, pin),
        "public_hex": public_hex,
        "private": private,
    }


def request_for(
    dest_home: Path,
    cache_dir: Path,
    blob: Path,
    digest: str,
    signature: dict[str, str],
    public_hex: str,
    **overrides: Any,
) -> InstallRequest:
    kwargs: dict[str, Any] = dict(
        source=blob,
        dest_home=dest_home,
        cache_dir=cache_dir,
        package_id=PACKAGE_ID,
        package_version=PACKAGE_VERSION,
        lockfile=lockfile_for(digest, str(blob)),
        signature=signature,
        trust_store={KEY_ID: public_hex},
        revocation={"revoked_versions": [], "revoked_keys": []},
        compatibility=linux_compat(),
        projection_map={rel: rel for rel in PAYLOAD_FILES},
        declared_permissions=["fs:plugin-root"],
        transaction_id="txn-adv0061",
        client_version="1.0.0",
        platform="linux",
    )
    kwargs.update(overrides)
    return InstallRequest(**kwargs)


def capture_call(fn, *args, **kwargs) -> dict[str, Any]:
    out, err = io.StringIO(), io.StringIO()
    raised: str | None = None
    gate: str | None = None
    result: Any = None
    with redirect_stdout(out), redirect_stderr(err):
        try:
            result = fn(*args, **kwargs)
        except GateFailure as exc:
            raised = f"GateFailure:{exc.gate}:{exc.reason}"
            gate = exc.gate
        except FetchError as exc:
            raised = f"FetchError:{exc}"
        except Exception as exc:  # noqa: BLE001 — probe records any install outcome
            raised = f"{type(exc).__name__}:{exc}"
    text = (out.getvalue() + err.getvalue()).strip()
    lowered = text.lower()
    warns = any(n in lowered for n in WARN_NEEDLES)
    return {
        "result": result,
        "raised": raised,
        "gate": gate,
        "stdout": text[-4000:],
        "warns": warns,
    }


def installed_digest(dest_home: Path) -> str | None:
    live = dest_home / "plugins" / PACKAGE_ID
    if not live.exists():
        return None
    files = sorted(p for p in live.rglob("*") if p.is_file())
    if not files:
        return None
    h = hashlib.sha256()
    for path in files:
        rel = path.relative_to(live).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
    return "tree:" + h.hexdigest()


def dest_empty(dest_home: Path) -> bool:
    return not census(dest_home)


def static_inventory() -> dict[str, Any]:
    functions: list[dict[str, str]] = []
    flags: list[dict[str, str]] = []
    lockfile_mentions: list[dict[str, Any]] = []
    fallback_hits: list[dict[str, str]] = []
    for rel in SCAN_RELS:
        path = REPO / rel
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(
                    {
                        "path": rel,
                        "name": node.name,
                        "lineno": str(node.lineno),
                    }
                )
            if isinstance(node, ast.Call):
                func = node.func
                attr = func.attr if isinstance(func, ast.Attribute) else ""
                if attr == "add_argument" and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        flags.append({"path": rel, "flag": arg0.value})
        lowered = src.lower()
        lockfile_mentions.append(
            {
                "path": rel,
                "lockfile_count": lowered.count("lockfile"),
                "has_check_lockfile_digest": "check_lockfile_digest" in src,
            }
        )
        for needle in ("fallback", "unpinned", "latest version", "skip_verify"):
            if needle in lowered:
                fallback_hits.append({"path": rel, "needle": needle})
    install_names = {
        row["name"]
        for row in functions
                if any(
                    key in row["name"]
                    for key in (
                        "install",
                        "repair",
                        "fetch",
                        "deliver",
                        "verif",
                        "lockfile",
                    )
                )
    }
    return {
        "scanned": list(SCAN_RELS),
        "functions": functions,
        "install_like_names": sorted(install_names),
        "cli_flags": flags,
        "lockfile_mentions": lockfile_mentions,
        "fallback_hits": fallback_hits,
        "verify_has_fallback_word": any(
            h["path"] == "tools/marketplace/verify.py" for h in fallback_hits
        ),
        "repair_cli_lockfile_flag": any(
            "lock" in f["flag"].lower() for f in flags
        ),
    }


def planted_unpinned_fallback(
    req: InstallRequest,
    unpinned_blob: Path,
    dest_home: Path,
    other_digest: str,
) -> dict[str, Any]:
    """Known-bad recovery: on lockfile failure, place the unpinned blob anyway."""
    try:
        return {"mode": "pinned", "result": marketplace_install(req)}
    except GateFailure as exc:
        placed = install_direct(
            unpinned_blob,
            dest_home,
            package_id=PACKAGE_ID,
            projection_map=dict(req.projection_map),
            transaction_id="txn-planted-fallback",
            digest=other_digest,
            declared_permissions=["fs:plugin-root"],
        )
        return {
            "mode": "unpinned-fallback",
            "gate": exc.gate,
            "reason": exc.reason,
            "result": placed,
        }


__all__ = [
    "FetchError",
    "GateFailure",
    "HERE",
    "KEY_ID",
    "PACKAGE_ID",
    "PACKAGE_REF",
    "PACKAGE_VERSION",
    "REPO",
    "TOOLS",
    "UNIT",
    "blob_digest",
    "capture_call",
    "census",
    "dest_empty",
    "fetch_to_cache",
    "install_direct",
    "install_from_handoff",
    "installed_digest",
    "lockfile_for",
    "marketplace_install",
    "planted_unpinned_fallback",
    "request_for",
    "run_verification",
    "seed_install",
    "signed_pair",
    "sign_digest",
    "static_inventory",
]
