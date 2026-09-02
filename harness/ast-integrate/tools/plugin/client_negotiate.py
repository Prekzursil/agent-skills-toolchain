"""Client version negotiation: refuse below-floor installs with a named floor (IMP-0008)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "plugin.json"
_SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _tuple(ver: str) -> tuple[int, int, int]:
    m = _SEMVER.search(ver)
    if not m:
        raise ValueError(ver)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def parse_cli_version(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _SEMVER.search(str(raw))
    if not m:
        return None
    return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    loc = Path(path) if path else DEFAULT_MANIFEST
    if loc.is_file():
        doc = json.loads(loc.read_text(encoding="utf-8"))
        if "min_client_version" not in doc:
            doc["min_client_version"] = "1.0.0"
        return doc
    return {
        "name": "ast-plugin",
        "min_client_version": "1.0.0",
        "supported_clients": ["claude-code", "codex"],
    }


@dataclass
class Negotiation:
    allowed: bool
    reason: str
    message: str
    required_version: str
    client_id: str = ""
    parsed_version: str | None = None
    offered_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "message": self.message,
            "required_version": self.required_version,
            "client_id": self.client_id,
            "parsed_version": self.parsed_version,
            "offered_version": self.offered_version,
        }


def negotiate(manifest: dict[str, Any], client_id: str, offered: str | None) -> Negotiation:
    floor = str(manifest.get("min_client_version") or "1.0.0")
    parsed = parse_cli_version(offered)
    if parsed is None:
        return Negotiation(
            allowed=False,
            reason="unparsable-version",
            message=f"unparsable client version {offered!r}; required version {floor}",
            required_version=floor,
            client_id=client_id,
            parsed_version=None,
            offered_version=str(offered) if offered is not None else None,
        )
    if _tuple(parsed) < _tuple(floor):
        return Negotiation(
            allowed=False,
            reason="below-floor",
            message=f"client {client_id} {parsed} is below required version {floor}",
            required_version=floor,
            client_id=client_id,
            parsed_version=parsed,
            offered_version=str(offered),
        )
    return Negotiation(
        allowed=True,
        reason="ok",
        message=f"client {client_id} {parsed} satisfies required version {floor}",
        required_version=floor,
        client_id=client_id,
        parsed_version=parsed,
        offered_version=str(offered),
    )


def preflight_install(
    dest: Path,
    manifest: dict[str, Any],
    client_id: str,
    offered: str,
    *,
    write: bool = False,
) -> dict[str, Any]:
    n = negotiate(manifest, client_id, offered)
    dest = Path(dest)
    installed = False
    if n.allowed and write:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "payload.bin").write_bytes(b"ok")
        installed = True
    return {
        "allowed": n.allowed,
        "reason": n.reason,
        "installed": installed,
        "dest_has_payload": dest.is_dir() and any(dest.iterdir()) if dest.exists() else False,
        "dest_exists": dest.exists(),
        "negotiation": n.to_dict(),
    }


def capture_cli_version(argv: list[str]) -> dict[str, Any]:
    binary = argv[0] if argv else ""
    which = shutil.which(binary)
    which_error = None if which else "FileNotFoundError"
    stdout = ""
    stderr = ""
    rc = None
    if which:
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=10,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            rc = proc.returncode
        except Exception as exc:  # noqa: BLE001
            which_error = type(exc).__name__
            stderr = str(exc)
    combined = (stdout + "\n" + stderr).strip()
    return {
        "argv": argv,
        "which": which,
        "which_error": which_error,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": rc,
        "combined": combined,
        "parsed": parse_cli_version(combined),
    }
