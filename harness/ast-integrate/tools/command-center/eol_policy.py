#!/usr/bin/env python3
"""EOL policy for command-center gates on Windows and Linux checkouts.

WHY. `validate.py` REACH-6 and `render.py` render_manifest hash text files.
Git stores LF. A Windows working tree under core.autocrlf=true materialises
CRLF. Hashing raw working-tree bytes therefore made both gates unsatisfiable
on the authoring box while Linux CI stayed green. That is a portability
defect in checkout policy, not a backlog-data defect.

This module:

  * checks `.gitattributes` for the `eol=lf` rules that make a Windows
    checkout emit LF for the hashed extensions
  * builds a min command-center tree the *real* CLIs accept
  * runs `validate.py` and `render.py --check` on that tree as LF and as
    CRLF (Windows working-tree byte form)
  * reproduces the pre-fix red state: RAW CRLF sha256 disagrees with the
    recorded LF digest; LF-normalised sha256 matches

It does not rewrite the live working tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat  # noqa: E402
import render as rnd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
GITATTRIBUTES = REPO / ".gitattributes"
REQUIRED_EOL_LF: tuple[str, ...] = (
    "*.md",
    "*.py",
    "*.json",
    "*.yml",
    "*.yaml",
    "*.sh",
    "*.ps1",
)
VALIDATE_PY = REPO / "tools" / "command-center" / "validate.py"
RENDER_PY = REPO / "tools" / "command-center" / "render.py"


def check_gitattributes(path: Path | None = None) -> list[str]:
    """Return REQUIRED_EOL_LF patterns that do not carry eol=lf.

    Last matching attribute line wins, same as git. A later `-text` or
    `eol=crlf` on the same pattern removes it from the present set.
    """
    target = Path(path) if path is not None else GITATTRIBUTES
    present: set[str] = set()
    for raw in target.read_text(encoding="utf-8").splitlines():
        stripped = raw.split("#", 1)[0].strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        pattern, attrs = parts[0], parts[1:]
        if pattern not in REQUIRED_EOL_LF:
            continue
        if "eol=lf" in attrs:
            present.add(pattern)
        if "eol=crlf" in attrs or "-text" in attrs or "binary" in attrs:
            present.discard(pattern)
    return [pattern for pattern in REQUIRED_EOL_LF if pattern not in present]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def build_min_command_center(root: Path) -> dict[str, Any]:
    """A catalog + register the live validate/render CLIs accept.

    The live tree may fail for missing-source reasons that are not EOL.
    Dual-platform proof therefore uses a min tree, then invokes the real
    `validate.py` / `render.py --check` against it.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "events").mkdir(parents=True, exist_ok=True)
    register = root / "sources" / "REGISTER.md"
    register_text = (
        "# REGISTER (IMP-0441 min fixture)\n"
        "\n"
        "Min command-center tree for dual-platform EOL proof.\n"
        "\n"
        "## 1. OUTSTANDING\n"
        "\n"
        "### 1A. Program A - toolchain / Prompt Two (2)\n"
        "\n"
        "| id | title | next |\n"
        "| --- | --- | --- |\n"
        "| R-A01 | min root item | act |\n"
        "| R-A02 | min dependent item | act |\n"
        "\n"
    )
    register.write_text(register_text, encoding="utf-8", newline="\n")
    digest = _sha256(_lf(register_text.encode("utf-8")))
    defaults = {
        "title": "min fixture item",
        "phase": "P2",
        "target": "min-target",
        "inputs": [],
        "assignment": "owner",
        "tool_permissions": ["read"],
        "execution_substrate": "local",
        "timeout_seconds": 60,
        "output_path": "command-center/receipts/IMP-0441.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "evidence_requirement": "named-probes",
        "tests_required": True,
        "reviewer_requirement": "independent",
        "completion_sentinel": "SUCCESS:IMP-0441",
        "retry_policy": "none",
        "failure_classification": "probe-exit",
        "owner_approval_required": False,
    }
    catalog: dict[str, Any] = {
        "defaults": defaults,
        "owner_questions": [
            {
                "id": "OQ-1",
                "state": "OPEN",
                "text": "min open question for the IMP-0441 fixture",
            }
        ],
        "provenance": {
            # Absolute: render_status() calls validate() without --register,
            # and `repo_root / abs_path` resolves to abs_path.
            "register": str(register.resolve()),
            "register_sha256": digest,
        },
        "items": [
            {
                "id": "R-A01",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the root thing",
                "dependencies": [],
            },
            {
                "id": "R-A02",
                "status": "OPEN",
                "program": "A-toolchain",
                "next_smallest_action": "do the other thing",
                "dependencies": ["R-A01"],
            },
        ],
    }
    (root / "events" / "EVENTS.jsonl").write_text("", encoding="utf-8", newline="\n")
    cat.save(catalog, root / "WORK-UNIT-CATALOG.json")
    rnd.write_all(root, catalog)
    return catalog


def materialize_eol(src: Path, dst: Path, mode: str) -> None:
    """Copy `src` to `dst` and rewrite text to LF or CRLF.

    `mode='crlf'` is the working-tree byte form Git emits under
    core.autocrlf=true. Binary (NUL) files are copied unchanged.
    """
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    if mode not in {"lf", "crlf"}:
        raise ValueError(f"mode must be lf or crlf, got {mode!r}")
    for path in dst.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        normalised = _lf(data)
        path.write_bytes(
            normalised.replace(b"\n", b"\r\n") if mode == "crlf" else normalised
        )


def _run_cli(script: Path, args: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [sys.executable, "-B", str(script), *args]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": " ".join(cmd),
    }


def run_gates(cc_root: Path) -> dict[str, Any]:
    """Invoke the real CLIs, not re-implementations of the gates."""
    catalog = cc_root / "WORK-UNIT-CATALOG.json"
    graph = cc_root / "DEPENDENCY-GRAPH.json"
    register = cc_root / "sources" / "REGISTER.md"
    return {
        "validate": _run_cli(
            VALIDATE_PY,
            [
                "--catalog",
                str(catalog),
                "--graph",
                str(graph),
                "--register",
                str(register),
            ],
        ),
        "render": _run_cli(
            RENDER_PY,
            ["--check", "--root", str(cc_root), "--catalog", str(catalog)],
        ),
    }


def dual_platform(tmp: Path) -> dict[str, Any]:
    """LF tree (Linux CI) and CRLF sibling (Windows working-tree bytes)."""
    lf_root = tmp / "lf" / "command-center"
    crlf_root = tmp / "crlf" / "command-center"
    build_min_command_center(lf_root)
    linux_lf = run_gates(lf_root)
    materialize_eol(lf_root, crlf_root, "crlf")
    windows = run_gates(crlf_root)
    linux_green = (
        linux_lf["validate"]["exit_code"] == 0 and linux_lf["render"]["exit_code"] == 0
    )
    windows_green = (
        windows["validate"]["exit_code"] == 0 and windows["render"]["exit_code"] == 0
    )
    return {
        "linux_lf": linux_lf,
        "windows_crlf_sim": windows,
        "linux_green": linux_green,
        "windows_green_after": windows_green,
    }


def prefix_raw_hash_red(crlf_root: Path) -> dict[str, Any]:
    """Pre-fix REACH-6 / render_manifest path: hash RAW CRLF bytes.

    Must disagree with recorded LF digests. LF-normalised hashes must still
    match, so after-green is not silence in both states.
    """
    register = (crlf_root / "sources" / "REGISTER.md").read_bytes()
    status = (crlf_root / "STATUS.md").read_bytes()
    catalog = json.loads(
        (crlf_root / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    recorded_reg = str(
        (catalog.get("provenance") or {}).get("register_sha256") or ""
    )
    manifest = json.loads(
        (crlf_root / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8")
    )
    recorded_status = ""
    for entry in manifest.get("artifacts") or []:
        if isinstance(entry, dict) and str(entry.get("path") or "").endswith(
            "STATUS.md"
        ):
            recorded_status = str(entry.get("sha256") or "")
            break
    register_raw = _sha256(register)
    register_lf = _sha256(_lf(register))
    status_raw = _sha256(status)
    status_lf = _sha256(_lf(status))
    reach6_raw_would_fail = bool(recorded_reg) and register_raw != recorded_reg
    reach6_lf_matches = bool(recorded_reg) and register_lf == recorded_reg
    render_raw_would_fail = bool(recorded_status) and status_raw != recorded_status
    render_lf_matches = bool(recorded_status) and status_lf == recorded_status
    return {
        "register_crlf_count": register.count(b"\r\n"),
        "register_raw_sha256": register_raw,
        "register_lf_sha256": register_lf,
        "register_recorded": recorded_reg,
        "status_raw_sha256": status_raw,
        "status_lf_sha256": status_lf,
        "status_recorded": recorded_status,
        "reach6_raw_would_fail": reach6_raw_would_fail,
        "reach6_lf_matches": reach6_lf_matches,
        "render_raw_would_fail": render_raw_would_fail,
        "render_lf_matches": render_lf_matches,
        "both_prefix_red": reach6_raw_would_fail and render_raw_would_fail,
        "both_postfix_match": reach6_lf_matches and render_lf_matches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check .gitattributes EOL policy for command-center gates."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if a required extension is missing eol=lf",
    )
    parser.add_argument(
        "--gitattributes",
        default=None,
        help="attributes file (default: repo .gitattributes)",
    )
    args = parser.parse_args(argv)
    if not args.check:
        parser.error("--check is required")
    ga = Path(args.gitattributes) if args.gitattributes else GITATTRIBUTES
    missing = check_gitattributes(ga)
    if missing:
        print(f"FAILED:eol-policy missing rules: {missing}")
        return 1
    print(
        "SUCCESS:eol-policy "
        + " ".join(REQUIRED_EOL_LF)
        + " all carry eol=lf"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
