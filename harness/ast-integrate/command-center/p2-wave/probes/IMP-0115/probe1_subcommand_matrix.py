#!/usr/bin/env python3
"""Probe 1: each publisher subcommand's observed exit code and emitted artifact."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import workspace as W  # noqa: E402

ART = W.REPO / "command-center/receipts/IMP-0115.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="imp0115-p1-"))
    good = W.write_good_tree(root)
    index = W.write_empty_index(root)
    key = root / "hmac.key"
    key.write_text("0123456789abcdef0123456789abcdef", encoding="utf-8")
    pkg = root / "echo-skill-1.0.0.zip"
    receipt = root / "pack.receipt.json"
    sig = root / "echo-skill-1.0.0.sig.json"
    validate_out = root / "validate.json"
    submit_pr = root / "submit.pr.json"
    yank_pr = root / "yank.pr.json"
    deprecate_pr = root / "deprecate.pr.json"
    egress = root / "egress.jsonl"

    rows = []

    pack = W.run_cli(
        ["pack", "--src", str(good), "--out", str(pkg), "--receipt", str(receipt)],
        root,
    )
    rows.append(
        {
            "subcommand": "pack",
            "exit_code": pack.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(pkg),
            "artifact_exists": pkg.is_file() and pkg.stat().st_size > 0,
            "artifact_sha256": sha256(pkg) if pkg.is_file() else None,
        }
    )

    validate = W.run_cli(
        ["validate", "--package", str(pkg), "--out", str(validate_out)],
        root,
    )
    rows.append(
        {
            "subcommand": "validate",
            "exit_code": validate.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(validate_out),
            "artifact_exists": validate_out.is_file(),
        }
    )

    sign = W.run_cli(
        ["sign", "--package", str(pkg), "--key", str(key), "--out", str(sig)],
        root,
    )
    rows.append(
        {
            "subcommand": "sign",
            "exit_code": sign.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(sig),
            "artifact_exists": sig.is_file(),
        }
    )

    submit = W.run_cli(
        [
            "submit",
            "--package",
            str(pkg),
            "--index",
            str(index),
            "--out",
            str(submit_pr),
            "--egress-log",
            str(egress),
            "--signature",
            str(sig),
        ],
        root,
    )
    rows.append(
        {
            "subcommand": "submit",
            "exit_code": submit.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(submit_pr),
            "artifact_exists": submit_pr.is_file(),
            "kind": json.loads(submit_pr.read_text(encoding="utf-8")).get("kind")
            if submit_pr.is_file()
            else None,
        }
    )

    yank = W.run_cli(
        [
            "yank",
            "--id",
            "echo-skill",
            "--version",
            "1.0.0",
            "--index",
            str(index),
            "--out",
            str(yank_pr),
            "--egress-log",
            str(egress),
        ],
        root,
    )
    rows.append(
        {
            "subcommand": "yank",
            "exit_code": yank.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(yank_pr),
            "artifact_exists": yank_pr.is_file(),
        }
    )

    deprecate = W.run_cli(
        [
            "deprecate",
            "--id",
            "echo-skill",
            "--version",
            "1.0.0",
            "--index",
            str(index),
            "--out",
            str(deprecate_pr),
            "--egress-log",
            str(egress),
        ],
        root,
    )
    rows.append(
        {
            "subcommand": "deprecate",
            "exit_code": deprecate.returncode,
            "expected": W.EXIT_OK,
            "artifact": str(deprecate_pr),
            "artifact_exists": deprecate_pr.is_file(),
        }
    )

    (HERE / "probe1-subcommand-matrix.raw.json").write_text(
        json.dumps({"rows": rows, "workdir": str(root)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": rows}, sort_keys=True))

    for row in rows:
        if row["exit_code"] != row["expected"] or not row["artifact_exists"]:
            print(f"FAILED:IMP-0115-probe1 {row['subcommand']}")
            return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0115-probe1 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:IMP-0115" not in ART.read_text(encoding="utf-8"):
            print("FAILED:IMP-0115-probe1 sentinel absent")
            return 1

    print("SUCCESS:IMP-0115-probe1 subcommand matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
