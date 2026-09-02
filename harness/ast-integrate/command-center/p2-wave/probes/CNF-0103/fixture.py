"""Known-non-empty hostile fixture: reserved device names + path > 260 chars."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESERVED_NAMES = ("NUL", "CON", "AUX", "PRN", "COM1", "LPT1")
ORDINARY = "ordinary/control.txt"
LONG_PAYLOAD = "payload.bin"


def _deep_dir(root: Path, min_chars: int) -> Path:
    p = root / "long"
    n = 0
    while len(str(p)) < min_chars:
        n += 1
        p = p / f"seg{n:02d}xxxxxxxxxx"
        p.mkdir(parents=True, exist_ok=True)
    return p


def write_file(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def build_hostile_tree(root: Path, *, min_long_chars: int = 280) -> dict[str, Any]:
    """Create a known-non-empty tree. Returns the inventory (not a count guess)."""
    root.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, str]] = []

    control = root / ORDINARY
    write_file(control, "CNF-0103-known-present-ordinary\n")
    files.append({"rel": ORDINARY.replace("\\", "/"), "cls": "ordinary-control"})

    for name in RESERVED_NAMES:
        rel = f"reserved/{name}"
        write_file(root / "reserved" / name, f"reserved-payload-{name}\n")
        files.append({"rel": rel, "cls": "reserved-device"})

    deep = _deep_dir(root, min_long_chars)
    payload = deep / LONG_PAYLOAD
    write_file(payload, "long-path-payload\n")
    rel_long = payload.relative_to(root).as_posix()
    files.append({"rel": rel_long, "cls": "long-path"})

    by_rel = {row["rel"]: row["cls"] for row in files}
    long_full = str(payload)
    return {
        "root": str(root),
        "files": files,
        "known_count": len(files),
        "by_rel": by_rel,
        "reserved_relpaths": [f"reserved/{n}" for n in RESERVED_NAMES],
        "ordinary_rel": ORDINARY,
        "long_rel": rel_long,
        "long_full_chars": len(long_full),
        "long_exceeds_legacy_260": len(long_full) > 260,
    }


def receipt_doc(unit_id: str, artifact_rel: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "artifacts": [{"path": artifact_rel.replace("\\", "/")}],
    }


def build_manifest_repo(root: Path, *, min_long_chars: int = 280) -> dict[str, Any]:
    """Fake repo so tools/command-center/unit_manifest.derive walks hostile names.

    Does not touch the live command-center/receipts tree.
    """
    receipts = root / "command-center" / "receipts"
    payloads = root / "payloads"
    receipts.mkdir(parents=True, exist_ok=True)
    payloads.mkdir(parents=True, exist_ok=True)

    planted: list[dict[str, str]] = []

    control_art = "payloads/control.bin"
    write_file(root / control_art, "manifest-control\n")
    write_file(
        receipts / "control.json",
        json.dumps(receipt_doc("CNF-0103", control_art), indent=1) + "\n",
    )
    planted.append({"receipt": "command-center/receipts/control.json", "artifact": control_art})

    nul_art = "payloads/reserved/NUL"
    write_file(root / nul_art, "manifest-nul\n")
    write_file(
        receipts / "NUL.json",
        json.dumps(receipt_doc("CNF-0103", nul_art), indent=1) + "\n",
    )
    planted.append({"receipt": "command-center/receipts/NUL.json", "artifact": nul_art})

    deep = _deep_dir(receipts, min_long_chars)
    long_receipt = deep / "deep.json"
    long_art = "payloads/long/payload.bin"
    write_file(root / long_art, "manifest-long\n")
    write_file(long_receipt, json.dumps(receipt_doc("CNF-0103", long_art), indent=1) + "\n")
    planted.append(
        {
            "receipt": long_receipt.relative_to(root).as_posix(),
            "artifact": long_art,
        }
    )

    return {
        "root": str(root),
        "known_receipt_count": len(planted),
        "known_artifact_count": len(planted),
        "planted": planted,
        "long_receipt_chars": len(str(long_receipt)),
        "long_exceeds_legacy_260": len(str(long_receipt)) > 260,
    }
