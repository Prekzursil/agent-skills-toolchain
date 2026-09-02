"""Live pin-vs-comparison matrix for formatter/linter/scanner claims."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import toolchain as T  # noqa: E402

DIV = HERE / "fixtures" / "divergent_up051.py"
F401 = HERE / "fixtures" / "stable_f401.py"
CLEAN = HERE / "fixtures" / "stable_clean.py"

QUESTION = (
    "Question: which claims change verdict between the CI-pinned tool version "
    "and the ambient local one? Measured precedent on this estate: CI pinned "
    "ruff 0.15.17 while local had 0.15.22, and the two disagreed on the same "
    "commit. Build the pinned-version inventory, re-run each claim under both, "
    "and record the version-sensitive set."
)


def domain_get(doc: dict, key: str, default=None):
    """Read a matrix field from report (schema envelope) or top-level (legacy)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report, dict) and key in report:
        return report[key]
    return doc.get(key, default)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _run_claim(claim_id: str, args: list[str], target: Path) -> dict:
    pin = T.run_ruff(T.RUFF_PIN, args + [str(target)])
    newer = T.run_ruff(T.RUFF_LOCAL_PRECEDENT, args + [str(target)])
    v_pin = T.verdict_from_proc(pin)
    v_new = T.verdict_from_proc(newer)
    return {
        "id": claim_id,
        "target": _rel(target),
        "args": args,
        "verdict_ci_pin": v_pin,
        "verdict_comparison": v_new,
        "ci_pin_rc": pin.returncode,
        "comparison_rc": newer.returncode,
        "ci_pin_tail": ((pin.stdout or "") + (pin.stderr or "")).strip()[-800:],
        "comparison_tail": ((newer.stdout or "") + (newer.stderr or "")).strip()[-800:],
        "version_sensitive": v_pin != v_new,
        "classification": "version-sensitive" if v_pin != v_new else "version-insensitive",
    }


def run_matrix() -> dict:
    inv = I.collect()
    pin_inv, pin_out = T.ruff_version_stdout(T.RUFF_PIN)
    cmp_inv, cmp_out = T.ruff_version_stdout(T.RUFF_LOCAL_PRECEDENT)
    pin_ok = T.RUFF_PIN in pin_out
    cmp_ok = T.RUFF_LOCAL_PRECEDENT in cmp_out

    claims = [
        _run_claim(
            "ruff-check-UP-preview-abstractclassmethod",
            ["check", "--isolated", "--preview", "--select", "UP"],
            DIV,
        ),
        _run_claim(
            "ruff-check-F401-unused-import",
            ["check", "--isolated", "--select", "F401"],
            F401,
        ),
        _run_claim(
            "ruff-check-clean",
            ["check", "--isolated"],
            CLEAN,
        ),
        _run_claim(
            "ruff-format-check-clean",
            ["format", "--isolated", "--check"],
            CLEAN,
        ),
    ]
    sensitive = [c for c in claims if c["version_sensitive"]]
    insensitive = [c for c in claims if not c["version_sensitive"]]

    inventory_rows = []
    for tool, row in sorted(inv["by_tool"].items()):
        amb = inv["ambient"].get(tool) or {"present": False, "version": None}
        inventory_rows.append(
            {
                "tool": tool,
                "kind": row.get("kind"),
                "ci_pin": row.get("pin"),
                "ci_pin_kind": row.get("pin_kind"),
                "ci_citation": row.get("citation"),
                "ci_workflow": row.get("workflow"),
                "local_version": amb.get("version"),
                "local_present": bool(amb.get("present")),
                "local_which": amb.get("which"),
            }
        )

    missing = [
        {
            "tool": m["tool"],
            "workflow": m["workflow"],
            "job": m.get("job"),
            "step": m.get("step"),
            "reason": f"{m.get('pin_kind')}: {m.get('citation')}",
        }
        for m in inv["missing_pins"]
    ]

    tests = {
        "known_divergent": any(
            c["id"] == "ruff-check-UP-preview-abstractclassmethod"
            and c["verdict_ci_pin"] == "PASS"
            and c["verdict_comparison"] == "FAIL"
            for c in claims
        ),
        "both_states_insensitive": bool(insensitive)
        and all(c["verdict_ci_pin"] == c["verdict_comparison"] for c in insensitive),
        "pin_fidelity": pin_ok and cmp_ok,
        "missing_pin_detection": len(missing) >= 1,
    }
    return {
        "pass": all(tests.values()),
        "tests": tests,
        "claims": claims,
        "sensitive": sensitive,
        "insensitive": insensitive,
        "inventory_rows": inventory_rows,
        "missing_pins": missing,
        "ci_source": inv["source"],
        "ci_source_note": inv["note"],
        "ambient": inv["ambient"],
        "pin_fidelity": {
            "tool": "ruff",
            "pinned_version": T.RUFF_PIN,
            "comparison_version": T.RUFF_LOCAL_PRECEDENT,
            "invocation": pin_inv,
            "version_stdout": pin_out,
            "comparison_invocation": cmp_inv,
            "comparison_version_stdout": cmp_out,
            "matches_pin": pin_ok,
            "matches_comparison": cmp_ok,
            "ambient_path_unused": True,
            "windows_shell_8b": (
                "command-center/p2-wave/probes/CNF-0185/fixtures/windows-shell-8b.md"
            ),
        },
        "question": QUESTION,
        "estate_precedent": {
            "ci_pin": T.RUFF_PIN,
            "measured_local": T.RUFF_LOCAL_PRECEDENT,
            "this_host_ambient_ruff": inv["ambient"]["ruff"],
            "comparison_role": (
                "0.15.22 is the catalog's measured local version. This host's "
                "PATH has no ruff; 0.15.22 is installed into an isolated prefix "
                "and invoked by version-qualified path, not ambient PATH."
            ),
        },
    }
