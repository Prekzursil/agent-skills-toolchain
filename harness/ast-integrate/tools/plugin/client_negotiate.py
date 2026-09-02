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
    """Decide whether ``client_id`` at ``offered`` may install.

    Every refuse branch carries a distinct ``reason`` and a user-facing
    message that names the component, the cause and the remedy
    (``required: ...``). The gate fails closed: an unparsable floor or an
    unparsable client version is a refusal, never an allow.
    """
    raw_floor = manifest.get("min_client_version", "1.0.0")
    floor_str = str(raw_floor) if raw_floor is not None else ""
    floor_parsed = parse_cli_version(floor_str)
    clients_raw = manifest.get("supported_clients")
    clients = [str(c) for c in clients_raw] if isinstance(clients_raw, (list, tuple)) else []
    client = str(client_id or "")
    offered_str = str(offered) if offered is not None else None
    if floor_parsed is None:
        return Negotiation(
            allowed=False,
            reason="manifest-min-unparsable",
            message=(
                f"install refused: manifest min_client_version {floor_str!r} is missing "
                "or unparsable (required: a semver min_client_version such as 1.0.0 "
                "in the plugin manifest)"
            ),
            required_version=floor_str,
            client_id=client,
            parsed_version=parse_cli_version(offered),
            offered_version=offered_str,
        )
    floor = floor_parsed
    if not client.strip():
        return Negotiation(
            allowed=False,
            reason="client-id-missing",
            message=(
                f"install refused: client id is empty (required: min_client_version "
                f"{floor}; supported_clients {clients})"
            ),
            required_version=floor,
            client_id=client,
            parsed_version=parse_cli_version(offered),
            offered_version=offered_str,
        )
    if clients and client not in clients:
        return Negotiation(
            allowed=False,
            reason="unsupported-client",
            message=(
                f"install refused: client {client!r} is not in supported_clients "
                f"{clients} (required: min_client_version {floor}; one of {clients})"
            ),
            required_version=floor,
            client_id=client,
            parsed_version=parse_cli_version(offered),
            offered_version=offered_str,
        )
    parsed = parse_cli_version(offered)
    if parsed is None:
        return Negotiation(
            allowed=False,
            reason="unparsable-version",
            message=(
                f"install refused: unparsable client version {offered!r} "
                f"(fail-closed; required: min_client_version {floor})"
            ),
            required_version=floor,
            client_id=client,
            parsed_version=None,
            offered_version=offered_str,
        )
    if _tuple(parsed) < _tuple(floor):
        return Negotiation(
            allowed=False,
            reason="below-floor",
            message=(
                f"install refused: client {client} version {parsed} is below "
                f"min_client_version {floor} (required: {floor})"
            ),
            required_version=floor,
            client_id=client,
            parsed_version=parsed,
            offered_version=offered_str,
        )
    return Negotiation(
        allowed=True,
        reason="ok",
        message=f"client {client} {parsed} satisfies required version {floor}",
        required_version=floor,
        client_id=client,
        parsed_version=parsed,
        offered_version=offered_str,
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
