"""Disposable sandbox: isolated tree, loopback HTTP, no live credentials."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from common import HERE, NARROW_PERMS, WIDE_PERMS

LOOPBACK_BODY = b"ADV0022-LOOPBACK"


class _HitLog:
    def __init__(self) -> None:
        self.paths: list[str] = []


def _handler(log: _HitLog) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/adv0022-loopback"):
                log.paths.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(LOOPBACK_BODY)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return Handler


def start_loopback() -> tuple[ThreadingHTTPServer, _HitLog, str]:
    log = _HitLog()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(log))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/adv0022-loopback"
    return server, log, url


def stop_loopback(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def write_manifest(path: Path, name: str, perms: tuple[str, ...], entry: str) -> None:
    doc = {
        "name": name,
        "class": "skill",
        "tool_permissions": list(perms),
        "entry": entry,
        "root": ".",
    }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def build_tree(root: Path) -> dict[str, Path]:
    narrow = root / "narrow"
    wide = root / "wide"
    control = root / "control"
    outside = root / "outside"
    for folder in (narrow, wide, control, outside):
        folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "fixtures" / "narrow_skill.py", narrow / "skill.py")
    shutil.copy2(HERE / "fixtures" / "wide_skill.py", wide / "skill.py")
    shutil.copy2(HERE / "fixtures" / "narrow_skill.py", control / "skill.py")
    write_manifest(narrow / "plugin.json", "narrow-skill", NARROW_PERMS, "skill.py")
    write_manifest(wide / "plugin.json", "wide-sibling", WIDE_PERMS, "skill.py")
    write_manifest(control / "plugin.json", "wide-control", WIDE_PERMS, "skill.py")
    return {
        "root": root,
        "narrow": narrow,
        "wide": wide,
        "control": control,
        "outside": outside,
        "sibling_entry": wide / "skill.py",
        "sibling_beacon": wide / "sibling.beacon",
        "narrow_spawn": narrow / "spawn.beacon",
        "control_spawn": control / "spawn.beacon",
        "outside_file": outside / "escape.txt",
        "narrow_report": narrow / "report.json",
        "control_report": control / "report.json",
    }


class Sandbox:
    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="adv0022-")
        self.root = Path(self._tmp.name).resolve()
        self.paths = build_tree(self.root)
        self.server: ThreadingHTTPServer | None = None
        self.hits: _HitLog | None = None
        self.loopback_url = ""

    def __enter__(self) -> "Sandbox":
        self.server, self.hits, self.loopback_url = start_loopback()
        return self

    def __exit__(self, *exc: object) -> None:
        if self.server is not None:
            stop_loopback(self.server)
        self._tmp.cleanup()

    def component_env(self, component: Path, report: Path) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.root),
            "LANG": os.environ.get("LANG", "C"),
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "ADV0022_COMPONENT_ROOT": str(component),
            "ADV0022_OUTSIDE": str(self.paths["outside"]),
            "ADV0022_SIBLING_ENTRY": str(self.paths["sibling_entry"]),
            "ADV0022_SIBLING_BEACON": str(self.paths["sibling_beacon"]),
            "ADV0022_LOOPBACK_URL": self.loopback_url,
            "ADV0022_REPORT": str(report),
        }
        python = os.environ.get("PYTHON") or ""
        if python:
            env["PYTHON"] = python
        return env
