"""Shared helpers for wave-2 shard 17 probe layer (RES units).

Recreated 2026-10-25 after the original probe tree was lost with the prior
builder session; every probe stays fail-closed: any failed check exits 1.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
RESEARCH = REPO / "command-center" / "research"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

_CATALOG_CACHE = None


def catalog_unit(uid: str) -> dict:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        _CATALOG_CACHE = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in _CATALOG_CACHE.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise SystemExit(f"FAILED:catalog-missing {uid}")


def artifact_path(uid: str) -> Path:
    rel = str(catalog_unit(uid).get("output_path") or "").replace("\\", "/")
    p = REPO / rel
    if not p.is_file() or p.stat().st_size <= 0:
        raise SystemExit(f"FAILED:{uid} artifact-absent {rel}")
    return p


def load_artifact(uid: str) -> tuple[Path, dict, str]:
    p = artifact_path(uid)
    text = p.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        raise SystemExit(f"FAILED:{uid} self-declared:{st}")
    sentinel = str(catalog_unit(uid).get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        raise SystemExit(f"FAILED:{uid} sentinel-absent")
    return p, doc, text


def norm_sha(path: Path) -> tuple[str, int]:
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def finish(uid: str, probe: str, checks: list[tuple[str, bool, str]]) -> int:
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if bad:
        print(f"FAILED:{uid}-{probe} {len(bad)} checks failed")
        return 1
    print(f"SUCCESS:{uid}-{probe}")
    return 0


def mutation_copy(doc, mutate, suffix: str = ".mutant.json"):
    """Write a mutated copy of the artifact into a temp file, return path."""
    mutated = mutate(json.loads(json.dumps(doc)))
    fd = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=suffix, delete=False
    )
    json.dump(mutated, fd, indent=1)
    fd.close()
    return Path(fd.name)


# -- credential scanner (value shapes only; key NAMES are legitimate content) --
CREDS = [
    ("jwt-three-segment", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("openai-sk", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github-pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("aws-akia", re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    ("bearer-line", re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{10,}", re.I)),
    ("long-secret-blob", re.compile(r'"(?:access_token|refresh_token|secret|password)"\s*:\s*"([A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,})"')),
]


def scan_credentials(text: str) -> list[tuple[str, str]]:
    hits = []
    for name, rx in CREDS:
        m = rx.search(text)
        if m:
            hits.append((name, m.group(0)[:24] + "..."))
    return hits


def char3gram_overlap(a: str, b: str) -> int:
    ga = {a[i:i + 3] for i in range(0, max(len(a) - 3, 0), 7)}
    gb = {b[i:i + 3] for i in range(0, max(len(b) - 3, 0), 7)}
    return len(ga & gb)


def cim_snapshot() -> list[dict]:
    """One PowerShell CIM query for all processes -> list of dicts."""
    import subprocess
    ps = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,HandleCount,CommandLine | "
        "ConvertTo-Json -Compress -Depth 2"
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=120,
    )
    data = json.loads(out.stdout or "[]")
    if isinstance(data, dict):
        data = [data]
    return data
