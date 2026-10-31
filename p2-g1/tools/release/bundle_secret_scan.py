"""Scan extracted release bundles for secrets. Report only; never rotate."""
from __future__ import annotations

import hashlib
import json
import re
import tarfile
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

SCANNER_NAME = "bundle-secret-scan"
SCANNER_VERSION = "1.0.0"
RULESET_PATH = "tools/release/ruleset_v1.json"
RULESET_ID = "bundle-secret-ruleset-v1"
CANARY_VARIABLE = "REL0010_CANARY_TOKEN"
_CANARY_FILE = "CANARY.env"

_SECRET_LINE = re.compile(
    r"(?P<var>[A-Z][A-Z0-9_]{2,})=(?P<val>\S+)"
)
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


@dataclass
class Finding:
    variable_name: str
    path: str
    offset: int
    length: int
    prefix: str
    byte_length: int = 0
    authenticates: bool = False

    def __post_init__(self) -> None:
        if not self.byte_length:
            self.byte_length = self.length

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable_name": self.variable_name,
            "path": self.path,
            "offset": self.offset,
            "length": self.length,
            "prefix": self.prefix,
        }


@dataclass
class Skipped:
    path: str
    suffix: str


@dataclass
class ScanResult:
    completed: bool
    findings: list[Finding] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    files_examined: int = 0
    exit_code: int = 0
    status: str = "clean"

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "findings": [f.to_dict() for f in self.findings],
            "skipped": [s.__dict__ for s in self.skipped],
            "files_examined": self.files_examined,
            "exit_code": self.exit_code,
            "status": self.status,
        }


def classify_scan_status(result: ScanResult) -> str:
    if not result.completed:
        return "tooling-error"
    if result.findings:
        return "findings"
    return "clean"


def ensure_clean_bundle(root: Path) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("clean bundle\n", encoding="utf-8")
    app = root / "app"
    app.mkdir(exist_ok=True)
    (app / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (app / "config.json").write_text('{"ok": true}\n', encoding="utf-8")
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    png = assets / "pixel.png"
    if not png.is_file():
        png.write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        )
    extra = root / "untracked-by-design"
    extra.mkdir(exist_ok=True)
    (extra / "packaged.txt").write_text("packaged\n", encoding="utf-8")


def plant_canary(extracted: Path, value: str, variable: str = CANARY_VARIABLE) -> Path:
    path = Path(extracted) / _CANARY_FILE
    path.write_text(f"{variable}={value}\n", encoding="utf-8")
    return path


def pack_layer_tar(root: Path, dest: Path | None = None) -> bytes:
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for path in Path(root).rglob("*"):
            if path.is_file():
                tf.add(path, arcname=str(path.relative_to(root)).replace("\\", "/"))
    raw = buf.getvalue()
    if dest is not None:
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(raw)
    return raw


def _iter_files(root: Path) -> Iterable[Path]:
    for path in Path(root).rglob("*"):
        if path.is_file():
            yield path


def scan_extracted(root: Path, *args, **kwargs) -> ScanResult:
    findings: list[Finding] = []
    skipped: list[Skipped] = []
    examined = 0
    for path in _iter_files(root):
        suffix = path.suffix.lower()
        if suffix in SKIP_SUFFIXES:
            skipped.append(Skipped(str(path.relative_to(root)).replace("\\", "/"), suffix))
            continue
        examined += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        for m in _SECRET_LINE.finditer(text):
            var = m.group("var")
            val = m.group("val")
            if var == CANARY_VARIABLE or var.endswith("_TOKEN") or "SECRET" in var or "PASSWORD" in var:
                findings.append(
                    Finding(
                        variable_name=var,
                        path=rel,
                        offset=m.start("val"),
                        length=len(val),
                        prefix=val[:3],
                    )
                )
    status = "findings" if findings else "clean"
    return ScanResult(
        completed=True,
        findings=findings,
        skipped=skipped,
        files_examined=examined,
        exit_code=0 if not findings else 1,
        status=status,
    )


def scan_tree(root: Path) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    result = scan_extracted(root)
    examined_paths = [str(p.relative_to(root)).replace("\\", "/") for p in _iter_files(root)]
    skipped_paths = [s.path for s in result.skipped]
    findings_d = [f.to_dict() for f in result.findings]
    return examined_paths, skipped_paths, findings_d


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted-root", required=True)
    args = parser.parse_args(argv)
    examined, skipped, findings = scan_tree(Path(args.extracted_root))
    print(
        json.dumps(
            {
                "examined": examined,
                "skipped": skipped,
                "findings": findings,
                "n_findings": len(findings),
            }
        )
    )
    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())


