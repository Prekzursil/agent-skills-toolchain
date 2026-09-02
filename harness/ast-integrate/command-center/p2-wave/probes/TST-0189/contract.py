#!/usr/bin/env python3
"""TST-0189 live contract: write API vs here-string file creation.

Production file creation is tools/lib/codex-invocation.mjs writeFileViaApi
(CLI: `write <dest>` with payload on stdin). The here-string route is the
both-states control: same bytes inlined into a PowerShell here-string
Set-Content command. Static scan is the catalog SUT tree tools/lib/ — not
vendor installers under tools/editor or tools/mcp, which are out of this
unit's named inputs.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUT = REPO / "tools" / "lib" / "codex-invocation.mjs"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0189.json"
UNIT_ID = "TST-0189"
SENTINEL = "SUCCESS:TST-0189"

# Document containing BOTH PowerShell here-string terminators and a quoted
# destructive command. The quoted command is documentation, not something to run.
PAYLOAD = (
    "Quoted documentation -- not a command to execute.\n"
    "Here-string opener token on its own line:\n"
    "@'\n"
    "Closer token on its own line next:\n"
    "'@\n"
    "Remove-Item -Recurse -Force C:\\Windows\\Temp\\tst0189-quoted-not-real\n"
    "rm -rf /tmp/tst0189-quoted-not-real\n"
    "end of quoted document\n"
)

DESTRUCTIVE_RE = re.compile(
    r"(?i)(Remove-Item\s+-Recurse|rm\s+-rf\s+/)",
)

# File-creation via here-string / heredoc. Comments that merely name the
# hazard without a cmdlet/redirect pairing are not sites.
FILE_CREATE_PATTERNS = (
    re.compile(
        r"(?is)\b(Set-Content|Add-Content|Out-File)\b[\s\S]{0,500}@['\"]"
    ),
    re.compile(
        r"(?is)@['\"][\s\S]{0,500}\b(Set-Content|Add-Content|Out-File)\b"
    ),
    re.compile(r"(?is)\b(cat|tee)\b[^\n]{0,80}<<"),
    re.compile(r"(?is)\bpwsh\b[^\n]{0,240}@'"),
)

SCAN_SUFFIXES = {".mjs", ".js", ".cjs", ".ts", ".ps1", ".psm1", ".py", ".sh", ".bash"}
SKIP_PARTS = {
    "node_modules",
    ".git",
    "__pycache__",
    "p2-wave",
    "receipts",
}


def payload_bytes() -> bytes:
    return PAYLOAD.encode("utf-8")


def intended_sha256() -> str:
    return hashlib.sha256(payload_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def node_bin() -> str:
    found = shutil.which("node")
    if not found:
        raise RuntimeError("node binary not found on PATH")
    return found


def write_via_api(dest: Path, data: bytes | None = None) -> dict:
    if not SUT.is_file():
        raise FileNotFoundError(f"missing write API {SUT}")
    blob = payload_bytes() if data is None else data
    proc = subprocess.run(
        [node_bin(), str(SUT), "write", str(dest)],
        input=blob,
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"write API exit {proc.returncode}: {(proc.stderr or b'').decode('utf-8', 'replace')}"
        )
    if not dest.is_file():
        raise RuntimeError(
            "write API exited 0 but dest was not created "
            f"(stderr={(proc.stderr or b'').decode('utf-8', 'replace')!r})"
        )
    landed = dest.read_bytes()
    meta = {}
    if proc.stdout:
        try:
            meta = json.loads(proc.stdout.decode("utf-8"))
        except json.JSONDecodeError:
            meta = {"stdout": proc.stdout.decode("utf-8", "replace")}
    return {
        "dest": str(dest),
        "intended_sha256": sha256_bytes(blob),
        "landed_sha256": sha256_bytes(landed),
        "landed_bytes": len(landed),
        "round_trip_exact": landed == blob,
        "cli": meta,
        "argv": ["node", "tools/lib/codex-invocation.mjs", "write", str(dest)],
    }


def here_string_command(payload: str, dest_name: str = "dest.txt") -> str:
    """PowerShell Set-Content with a single-quoted here-string payload."""
    return (
        f"Set-Content -LiteralPath {dest_name} -Value @'\n" f"{payload}" f"\n'@\n"
    )


def emulate_ps_here_string_write(payload: str) -> dict:
    """Emulate PowerShell single-quoted here-string termination.

    A line whose first two characters are quote-at closes the here-string.
    Remaining lines are parsed as commands (the payload-scanned-as-command
    hazard), and the written body is truncated (corruption).
    """
    lines = payload.split("\n")
    body: list[str] = []
    remainder: list[str] = []
    terminated_early = False
    for i, line in enumerate(lines):
        if line.startswith("'@") and not terminated_early:
            terminated_early = True
            after = line[2:]
            remainder = ([after] if after else []) + lines[i + 1 :]
            break
        body.append(line)
    written = "\n".join(body)
    return {
        "written": written,
        "written_sha256": sha256_bytes(written.encode("utf-8")),
        "intended_sha256": sha256_bytes(payload.encode("utf-8")),
        "corrupted": written.encode("utf-8") != payload.encode("utf-8"),
        "terminated_early": terminated_early,
        "remainder_lines": remainder,
    }


def scan_command_text(text: str) -> list[str]:
    return DESTRUCTIVE_RE.findall(text)


def scan_file_for_here_string_create(text: str) -> list[str]:
    hits = []
    labels = (
        "cmdlet-then-here-string",
        "here-string-then-cmdlet",
        "shell-heredoc-redirect",
        "pwsh-invocation-here-string",
    )
    for label, pat in zip(labels, FILE_CREATE_PATTERNS):
        if pat.search(text):
            hits.append(label)
    return hits


def scan_toolchain(root: Path | None = None) -> list[dict]:
    base = root or (REPO / "tools" / "lib")
    findings: list[dict] = []
    if not base.is_dir():
        return findings
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = scan_file_for_here_string_create(text)
        if hits:
            findings.append(
                {
                    "path": path.relative_to(REPO).as_posix(),
                    "hits": hits,
                }
            )
    return findings


def measure() -> dict:
    cmd_text = here_string_command(PAYLOAD)
    hs = emulate_ps_here_string_write(PAYLOAD)
    hs_scan = scan_command_text(cmd_text)
    remainder_scan = scan_command_text("\n".join(hs["remainder_lines"]))
    toolchain_hits = scan_toolchain()

    with tempfile.TemporaryDirectory(prefix="tst0189-") as tmp:
        dest = Path(tmp) / "quoted-document.txt"
        api = write_via_api(dest)
        api_scan = scan_command_text(" ".join(api["argv"]))

    corrupted_or_blocked = bool(hs["corrupted"] or hs["terminated_early"])
    payload_scanned = bool(hs_scan or remainder_scan)
    return {
        "unit_id": UNIT_ID,
        "intended_sha256": intended_sha256(),
        "payload_len": len(payload_bytes()),
        "payload_contains_opener": "@'" in PAYLOAD,
        "payload_contains_closer": "'@" in PAYLOAD,
        "write_api": {
            "sut": "tools/lib/codex-invocation.mjs",
            "round_trip_exact": api["round_trip_exact"],
            "intended_sha256": api["intended_sha256"],
            "landed_sha256": api["landed_sha256"],
            "landed_bytes": api["landed_bytes"],
            "payload_scanned_as_command": bool(api_scan),
            "scan_hits": api_scan,
            "argv": api["argv"],
        },
        "here_string_control": {
            "corrupted": hs["corrupted"],
            "terminated_early": hs["terminated_early"],
            "corrupted_or_blocked": corrupted_or_blocked,
            "written_sha256": hs["written_sha256"],
            "intended_sha256": hs["intended_sha256"],
            "payload_scanned_as_command": payload_scanned,
            "command_scan_hits": hs_scan,
            "remainder_scan_hits": remainder_scan,
            "remainder_line_count": len(hs["remainder_lines"]),
        },
        "static_scan": {
            "root": "tools/lib/",
            "here_string_file_create_sites": len(toolchain_hits),
            "findings": toolchain_hits,
        },
    }


def assert_pass(ev: dict) -> list[str]:
    errors: list[str] = []
    api = ev["write_api"]
    hs = ev["here_string_control"]
    st = ev["static_scan"]
    if not ev["payload_contains_opener"] or not ev["payload_contains_closer"]:
        errors.append("payload missing both here-string terminators")
    if not api["round_trip_exact"]:
        errors.append("write API did not round-trip bytes")
    if api["landed_sha256"] != ev["intended_sha256"]:
        errors.append("write API sha256 mismatch vs intended")
    if api["payload_scanned_as_command"]:
        errors.append("write API argv scanned as destructive command")
    if not hs["corrupted_or_blocked"]:
        errors.append("here-string control did not corrupt or block")
    if hs["written_sha256"] == ev["intended_sha256"]:
        errors.append("here-string control silently matched intended bytes")
    if not hs["payload_scanned_as_command"]:
        errors.append("here-string payload was not visible to command scanner")
    if st["here_string_file_create_sites"] != 0:
        errors.append(f"static scan found sites: {st['findings']}")
    return errors


def load_receipt() -> dict:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        raise FileNotFoundError(f"missing receipt {RECEIPT}")
    return json.loads(RECEIPT.read_text(encoding="utf-8"))
