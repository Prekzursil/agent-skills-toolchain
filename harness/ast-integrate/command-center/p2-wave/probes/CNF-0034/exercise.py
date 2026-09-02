#!/usr/bin/env python3
"""Live alternate-surface exercise for CNF-0034.

Author tests for these components used in-process library imports. This module
drives the same corrected behaviour through CLI / hook subprocesses the author
did not invoke, plus a mutant-CLI control that must disagree.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARC10 = REPO / "command-center/p2-wave/probes/ARC-0010"
ARC14 = REPO / "command-center/p2-wave/probes/ARC-0014"
ARC05 = REPO / "command-center/p2-wave/probes/ARC-0005"
PY = sys.executable
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

sys.path.insert(0, str(ARC10))
sys.path.insert(0, str(ARC14))
sys.path.insert(0, str(ARC05))
import freeze_hook as FH  # noqa: E402
import generator as G  # noqa: E402
import stop_hook as SH  # noqa: E402
import trees as T  # noqa: E402
from extract import SAMPLE_RELS  # noqa: E402

PLANT = "CNF-0034-PLANTED-EDIT\n"
MCP_BLOCKER = (
    "No MCP tool server or MCP tool registration for this component exists in "
    "this worktree (no MCP SDK entry point, no tools/mcp server module bound "
    "to generator, freeze_hook, or stop_hook)."
)


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ENV,
    )


def _parse_json_stdout(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def exercise_freeze_and_generator() -> dict[str, Any]:
    registry = G.load_default_registry()
    files = G.generate(registry)
    rels = [rel for rel in SAMPLE_RELS if rel in files]
    if not rels:
        raise RuntimeError("SAMPLE_RELS missing from generate() output")
    target = rels[0]
    with tempfile.TemporaryDirectory(prefix="cnf0034-freeze-") as tmp:
        root = Path(tmp)
        deploy = root / "deploy"
        G.write_tree(files, deploy)
        ledger = FH.default_ledger(rels)
        reg_path = root / "registry.json"
        led_path = root / "ledger.json"
        reg_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        led_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        cli = [
            PY,
            "-B",
            str(ARC14 / "freeze_hook.py"),
            "--root",
            str(deploy),
            "--registry",
            str(reg_path),
            "--ledger",
            str(led_path),
        ]
        clean_lib = FH.check(deploy, registry, ledger)
        clean_cli = _run(cli)
        clean_cli_doc = _parse_json_stdout(clean_cli.stdout)
        (deploy / target).write_bytes(
            (deploy / target).read_bytes() + b"\nCNF-0034-HAND-EDIT\n"
        )
        dirty_lib = FH.check(deploy, registry, ledger)
        dirty_cli = _run(cli)
        dirty_cli_doc = _parse_json_stdout(dirty_cli.stdout)
        mutant = _run(
            [
                PY,
                "-c",
                "import json,sys; print(json.dumps({'ok': True, 'reason': 'mutant-always-ok', 'rejections': []})); sys.exit(0)",
            ]
        )
        mutant_doc = _parse_json_stdout(mutant.stdout)
        lib_rejects = bool(dirty_lib.get("rejections"))
        cli_rejects = dirty_cli.returncode != 0 and dirty_cli_doc.get("ok") is False
        mutant_gap = mutant.returncode == 0 and mutant_doc.get("ok") is True and lib_rejects
        return {
            "target": target,
            "rels": rels,
            "clean_library_ok": bool(clean_lib.get("ok")),
            "clean_cli_ok": clean_cli.returncode == 0 and bool(clean_cli_doc.get("ok")),
            "dirty_library_ok": bool(dirty_lib.get("ok")),
            "dirty_library_rejections": len(dirty_lib.get("rejections") or []),
            "dirty_cli_returncode": dirty_cli.returncode,
            "dirty_cli_ok": dirty_cli_doc.get("ok"),
            "dirty_cli_reason": dirty_cli_doc.get("reason"),
            "library_cli_agree_clean": bool(clean_lib.get("ok"))
            and clean_cli.returncode == 0
            and bool(clean_cli_doc.get("ok")),
            "library_cli_agree_dirty": lib_rejects and cli_rejects,
            "mutant_cli_hides_tamper": mutant_gap,
            "hold": bool(clean_lib.get("ok"))
            and clean_cli.returncode == 0
            and lib_rejects
            and cli_rejects
            and mutant_gap,
            "cli_command": " ".join(cli),
        }


def exercise_stop_hook() -> dict[str, Any]:
    T.build_control_fixtures()
    target = T.CTRL_LIVE / "common/control.md"
    original = target.read_text(encoding="utf-8") if target.is_file() else ""
    cli = [PY, "-B", str(ARC05 / "stop_hook.py")]
    try:
        if SH.SURFACE.is_file():
            SH.SURFACE.unlink()
        good_lib = SH.run(T.CTRL_REPO, T.CTRL_LIVE)
        good_cli = _run(cli, cwd=ARC05)
        good_cli_doc = _parse_json_stdout(good_cli.stdout)
        warning_on_good = SH.SURFACE.is_file()
        target.write_text(original + PLANT, encoding="utf-8")
        bad_lib = SH.run(T.CTRL_REPO, T.CTRL_LIVE)
        if SH.SURFACE.is_file():
            SH.SURFACE.unlink()
        bad_cli = _run(cli, cwd=ARC05)
        bad_cli_doc = _parse_json_stdout(bad_cli.stdout)
        warning_on_bad = SH.SURFACE.is_file() and "DRIFT WARNING" in SH.SURFACE.read_text(
            encoding="utf-8"
        )
        mutant = _run(
            [
                PY,
                "-c",
                "import json; print(json.dumps({'fired': False, 'silent': True, 'warning_present': False}))",
            ]
        )
        mutant_doc = _parse_json_stdout(mutant.stdout)
        hold = (
            bool(good_lib.get("silent"))
            and not bool(good_cli_doc.get("fired"))
            and not warning_on_good
            and bool(bad_lib.get("fired"))
            and bool(bad_cli_doc.get("fired"))
            and warning_on_bad
            and mutant_doc.get("fired") is False
        )
        return {
            "good_library_silent": bool(good_lib.get("silent")),
            "good_cli_fired": bool(good_cli_doc.get("fired")),
            "warning_on_good": warning_on_good,
            "bad_library_fired": bool(bad_lib.get("fired")),
            "bad_cli_fired": bool(bad_cli_doc.get("fired")),
            "warning_on_bad": warning_on_bad,
            "mutant_cli_silent_on_bad": mutant_doc.get("fired") is False,
            "hold": hold,
            "cli_command": " ".join(cli),
        }
    finally:
        target.write_text(original, encoding="utf-8")
        T.build_control_fixtures()
        restored = SH.run(T.CTRL_REPO, T.CTRL_LIVE)
        if restored.get("fired") and SH.SURFACE.is_file():
            SH.SURFACE.unlink()
        elif SH.SURFACE.is_file() and not restored.get("fired"):
            SH.SURFACE.unlink()


def mcp_present() -> bool:
    """True only when an MCP server is bound to these three components.

    A glob for any *mcp* path under tools/ is the wrong detector: this
    worktree vendors unrelated MCP servers, and that glob folded a HOLD
    on CLI/hook into a false fail (not-checked-folded-into-pass inverted).
    """
    bound = (
        ARC10 / "mcp_server.py",
        ARC14 / "mcp_server.py",
        ARC05 / "mcp_server.py",
        ARC10 / "server.py",
        ARC14 / "server.py",
        ARC05 / "server.py",
    )
    return any(path.is_file() for path in bound)


def run() -> dict[str, Any]:
    freeze = exercise_freeze_and_generator()
    stop = exercise_stop_hook()
    mcp = mcp_present()
    return {
        "freeze": freeze,
        "stop": stop,
        "mcp_present": mcp,
        "mcp_blocker": MCP_BLOCKER,
        "pass": bool(freeze.get("hold")) and bool(stop.get("hold")),
    }


if __name__ == "__main__":
    doc = run()
    print(json.dumps({k: doc[k] for k in ("pass", "mcp_present")}, sort_keys=True))
    print(f"freeze_hold={doc['freeze']['hold']} stop_hold={doc['stop']['hold']}")
    raise SystemExit(0 if doc["pass"] else 1)
