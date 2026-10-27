"""Shared paths and hashing for RES-0141. No detector, no labels."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"
CORPUS_REL = "command-center/p2-wave/probes/RES-0141/corpus.json"
LABELS_REL = "command-center/p2-wave/probes/RES-0141/labels.json"
CORPUS = REPO / CORPUS_REL
LABELS = REPO / LABELS_REL
LABELS = LABELS

PRERELEASE_RE = re.compile(r"(?i)(rc|alpha|beta|dev|pre)|\d[ab]\d")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Parse a main-package tag. Reject monorepo @tags and prereleases."""
    text = (tag or "").strip()
    if not text or "@" in text:
        return None
    if PRERELEASE_RE.search(text):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r"(\d+)\.(\d+)$", text)
    if m:
        return int(m.group(1)), int(m.group(2)), 0
    return None


def is_x_0_0(ver: tuple[int, int, int] | None) -> bool:
    return bool(ver) and ver[1] == 0 and ver[2] == 0 and ver[0] >= 1


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


dump_json = dump_json
load_json = load_json
sha256_bytes = sha256_bytes
now_iso = now_iso


def digest_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))
