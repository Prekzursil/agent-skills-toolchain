#!/usr/bin/env python3
"""IMP-0437 mutation exit-code probe.

Measures the defaults-block-deleted mutation and the single-field control
against the CI command line (validate.py --require-complete), and records the
disarmed / soft path (--no-require-complete) for honest before/after contrast.

Honesty note (IMP-0436 already landed): deleting the entire defaults block
exits nonzero even under --no-require-complete, because V-DEFAULTS is always
on. The historical catalog claim "before exits 0" is therefore already REFUTED
on this tip; we still record the measured soft-path exit code verbatim and
prove the armed CI path stays red. The remaining silence hole that IMP-0437
closes is V-FIELDS (blank work-unit field exits 0 under soft, exits nonzero
under armed).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import catalog as cat  # noqa: E402


VALIDATE = REPO / "tools" / "command-center" / "validate.py"
CI_CMD_TAIL = ["--require-complete"]  # what quality.yml now passes
SOFT_CMD_TAIL = ["--no-require-complete"]  # historical disarm / soft draft


def _write_scratch(catalog_obj: dict) -> tuple[Path, Path]:
    td = Path(tempfile.mkdtemp(prefix="imp0437-mut-"))
    cpath = td / "cat.json"
    gpath = td / "graph.json"
    cat.save(catalog_obj, cpath)
    cat.save(cat.build_graph(catalog_obj), gpath)
    return cpath, gpath


def _run(cpath: Path, gpath: Path, extra: list[str]) -> dict:
    cmd = [
        sys.executable,
        str(VALIDATE),
        "--catalog",
        str(cpath),
        "--graph",
        str(gpath),
        *extra,
    ]
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "command": " ".join(cmd),
        "command_rel": (
            f"python tools/command-center/validate.py --catalog <scratch> "
            f"--graph <scratch> {' '.join(extra)}".strip()
        ),
        "exit_code": proc.returncode,
        "output_tail": out[-2000:],
        "has_v_defaults": "V-DEFAULTS" in out,
        "has_v_fields": "V-FIELDS" in out,
        "failed_line": next(
            (
                ln
                for ln in out.splitlines()
                if ln.startswith("FAILED:") or ln.startswith("SUCCESS:")
            ),
            "",
        ),
    }


def _find(catalog: dict, item_id: str) -> dict:
    for item in cat.items(catalog):
        if str(item.get("id", "")) == item_id:
            return item
    raise KeyError(item_id)


def main() -> int:
    live = cat.load()

    # --- Mutation A: delete entire defaults block ---
    del_block = copy.deepcopy(live)
    del del_block["defaults"]
    c_a, g_a = _write_scratch(del_block)
    a_soft = _run(c_a, g_a, SOFT_CMD_TAIL)
    a_armed = _run(c_a, g_a, CI_CMD_TAIL)

    # --- Mutation B: delete one default field ---
    del_one = copy.deepcopy(live)
    del del_one["defaults"]["timeout_seconds"]
    c_b, g_b = _write_scratch(del_one)
    b_soft = _run(c_b, g_b, SOFT_CMD_TAIL)
    b_armed = _run(c_b, g_b, CI_CMD_TAIL)

    # --- Control C: blank field (V-FIELDS only; no V-DEFAULTS) ---
    blank = copy.deepcopy(live)
    _find(blank, "R-M01")["completion_sentinel"] = ""
    c_c, g_c = _write_scratch(blank)
    c_soft = _run(c_c, g_c, SOFT_CMD_TAIL)
    c_armed = _run(c_c, g_c, CI_CMD_TAIL)
    c_bare = _run(c_c, g_c, [])  # bare = CLI default (must be armed post-0437)

    # Live clean under CI command
    c_ok, g_ok = _write_scratch(live)
    good = _run(c_ok, g_ok, CI_CMD_TAIL)

    # Workflow arm check — require the CI run line to carry the flag.
    wf = (REPO / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    ci_line_armed = "python tools/command-center/validate.py --require-complete" in wf
    # A bare `python tools/command-center/validate.py` run line (no flag) must be gone.
    bare_run_lines = [
        ln.strip()
        for ln in wf.splitlines()
        if ln.strip() == "python tools/command-center/validate.py"
    ]

    report = {
        "unit": "IMP-0437",
        "ci_invocation": "python tools/command-center/validate.py --require-complete",
        "honesty": {
            "imp_0436_v_defaults_always_on": True,
            "catalog_claimed_before_exit_0": (
                "REFUTED on this tip: soft-path defaults deletion already exits "
                f"{a_soft['exit_code']} via V-DEFAULTS (IMP-0436). Historical "
                "pre-0436 bare CI would have exited 0; we do not invent that run."
            ),
            "remaining_hole_closed": (
                "V-FIELDS under soft path still silent on blank completion_sentinel "
                f"(exit {c_soft['exit_code']}); armed CI path exits {c_armed['exit_code']}."
            ),
        },
        "good_state": good,
        "mutations": {
            "defaults_block_deleted": {
                "description": "Delete entire catalog.defaults block",
                "before_soft_no_require_complete": a_soft,
                "after_ci_require_complete": a_armed,
                "before_exit_code": a_soft["exit_code"],
                "after_exit_code": a_armed["exit_code"],
                "gate_red_after": a_armed["exit_code"] != 0,
            },
            "single_default_field_deleted": {
                "description": "Delete defaults.timeout_seconds only",
                "before_soft_no_require_complete": b_soft,
                "after_ci_require_complete": b_armed,
                "before_exit_code": b_soft["exit_code"],
                "after_exit_code": b_armed["exit_code"],
                "gate_red_after": b_armed["exit_code"] != 0,
            },
            "blank_completion_sentinel_v_fields": {
                "description": (
                    "Blank R-M01.completion_sentinel — V-FIELDS-only control "
                    "(no V-DEFAULTS); proves require_complete arm matters"
                ),
                "before_soft_no_require_complete": c_soft,
                "after_ci_require_complete": c_armed,
                "after_bare_cli_default": c_bare,
                "before_exit_code": c_soft["exit_code"],
                "after_exit_code": c_armed["exit_code"],
                "bare_exit_code": c_bare["exit_code"],
                "gate_red_after": c_armed["exit_code"] != 0,
                "soft_was_silent": c_soft["exit_code"] == 0,
            },
        },
        "workflow": {
            "path": ".github/workflows/quality.yml",
            "require_complete_flag_present": ci_line_armed,
            "bare_run_lines": bare_run_lines,
        },
        "both_states": {
            "defaults_block": bool(
                a_armed["exit_code"] != 0 and good["exit_code"] == 0
            ),
            "single_field": bool(b_armed["exit_code"] != 0 and good["exit_code"] == 0),
            "v_fields_blank": bool(
                c_armed["exit_code"] != 0
                and c_soft["exit_code"] == 0
                and good["exit_code"] == 0
            ),
        },
        "ok": bool(
            a_armed["exit_code"] != 0
            and b_armed["exit_code"] != 0
            and c_armed["exit_code"] != 0
            and c_soft["exit_code"] == 0
            and c_bare["exit_code"] != 0
            and good["exit_code"] == 0
            and ci_line_armed
            and not bare_run_lines
        ),
    }

    out_path = PROBE_DIR / "mutation-exit-codes.json"
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"ok": report["ok"], "out": str(out_path.relative_to(REPO))}, indent=2
        )
    )
    print(
        f"defaults before={a_soft['exit_code']} after={a_armed['exit_code']}; "
        f"single before={b_soft['exit_code']} after={b_armed['exit_code']}; "
        f"vfields soft={c_soft['exit_code']} armed={c_armed['exit_code']} bare={c_bare['exit_code']}; "
        f"ci_armed={ci_line_armed}"
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
