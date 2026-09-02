"""AUD-0049 comparator: promised platforms versus CI runs-on.

Probe 1 signal is the set difference. Probe 2 attaches already-measured
defects to each promised platform that CI does not exercise. The catalog
control requires Windows to be flagged promised-but-underexercised when
the runner matrix is Linux-only and three Windows-only CRLF failures are
on record. A report of full coverage on that fixture means the comparator
is not reading the matrix.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
INVENTORY = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
WFDIR = REPO / ".github/workflows"

CHARTER_CANDIDATES = (
    "CHARTER.md",
    "charter.md",
    "docs/CHARTER.md",
    "command-center/CHARTER.md",
)
README_CANDIDATES = (
    "README.md",
    "README.rst",
    "docs/README.md",
)

# Catalog-pinned already-measured Windows-only CRLF failures (AUD-0049 control).
WINDOWS_CRLF_DEFECTS: list[dict[str, Any]] = [
    {
        "defect_id": "CRLF-REACH-6-WORKTREE-HASH",
        "platform": "windows",
        "summary": (
            "CC-0005 / REACH-6: tools/command-center/validate.py hashed "
            "working-tree bytes under core.autocrlf=true. Recorded pair "
            "blob 8b3e44cc3813 vs CRLF worktree 1a404a91d819; both "
            "command-center gates went red on every Windows checkout while "
            "Linux CI stayed green."
        ),
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CC-0005",
        "live_tree": "tools/command-center/validate.py",
        "linux_ci_sees": False,
    },
    {
        "defect_id": "CRLF-GIT-ARCHIVE-EXPORT",
        "platform": "windows",
        "summary": (
            "git archive | tar -x returns CRLF worktree bytes on the Windows "
            "estate (measured 3,837 bytes / 100 CRLF) while git cat-file -p "
            "and git show return the blob (3,737 bytes / 0 CRLF). Linux CI "
            "never observes the archive conversion."
        ),
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CC-0005",
        "live_tree": "command-center/p2-wave/_build_IMP0440.py",
        "linux_ci_sees": False,
    },
    {
        "defect_id": "CRLF-SEED-RAW-DIGEST",
        "platform": "windows",
        "summary": (
            "seed.py hashed raw REGISTER.md bytes while validate.py hashed "
            "LF-normalised bytes. Under autocrlf=true, seed.py --force "
            "recorded a digest validate.py could not satisfy (721c4e577ca5 "
            "vs 60a4d35f822d), holding gate-tests-coverage red for 98 "
            "commits. Linux CI never saw that writer/reader split."
        ),
        "anchor": "tools/command-center/tests/test_seed.py:test_register_provenance_is_lf_normalised",
        "live_tree": "tools/command-center/tests/test_seed.py",
        "linux_ci_sees": False,
    },
]

MACOS_DEFECTS: list[dict[str, Any]] = [
    {
        "defect_id": "MACOS-NFD-NFC-FILENAME",
        "platform": "macos",
        "summary": (
            "TST-0198: a macOS-created NFD filename need not match its NFC "
            "manifest entry. Linux CI on ubuntu-latest never exercises that "
            "normal-form collision."
        ),
        "anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0198",
        "live_tree": "command-center/WORK-UNIT-CATALOG.json",
        "linux_ci_sees": False,
    }
]

RUNNER_OS_PREFIXES = (
    ("ubuntu", "linux"),
    ("debian", "linux"),
    ("linux", "linux"),
    ("windows", "windows"),
    ("macos", "macos"),
    ("mac-os", "macos"),
)


def classify_runner(raw: Any) -> str:
    """Map a GitHub Actions runs-on value to linux|windows|macos|unknown."""
    if raw is None:
        return "unknown"
    if isinstance(raw, list):
        labels = [str(x).strip().lower() for x in raw]
        for label in labels:
            os_id = classify_runner(label)
            if os_id != "unknown":
                return os_id
        return "unknown"
    text = str(raw).strip().lower()
    text = re.sub(r"\$\{\{\s*matrix\.os\s*\}\}", "matrix.os", text)
    for prefix, os_id in RUNNER_OS_PREFIXES:
        if text == prefix or text.startswith(prefix + "-") or prefix in text.split():
            return os_id
    return "unknown"


def compare(
    promised_os: set[str],
    exercised_os: set[str],
    defects_by_platform: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    defects_by_platform = defects_by_platform or {}
    missing = sorted(promised_os - exercised_os)
    extra = sorted(exercised_os - promised_os)
    full_coverage = bool(promised_os) and not missing
    rows = []
    for platform in sorted(promised_os | exercised_os):
        in_promised = platform in promised_os
        in_exercised = platform in exercised_os
        defects = list(defects_by_platform.get(platform) or [])
        if in_promised and in_exercised:
            status = "exercised"
            severity = "none"
        elif in_promised and not in_exercised:
            status = "promised-but-underexercised"
            severity = (
                "underexercised-with-known-defect"
                if defects
                else "underexercised-no-known-defect"
            )
        else:
            status = "exercised-but-unpromised"
            severity = "none"
        rows.append(
            {
                "platform": platform,
                "promised": in_promised,
                "exercised": in_exercised,
                "status": status,
                "severity": severity,
                "defect_count": len(defects),
                "defect_ids": [d["defect_id"] for d in defects],
            }
        )
    windows_row = next((r for r in rows if r["platform"] == "windows"), None)
    windows_underexercised = bool(
        windows_row and windows_row["status"] == "promised-but-underexercised"
    )
    return {
        "promised_os": sorted(promised_os),
        "exercised_os": sorted(exercised_os),
        "promised_minus_exercised": missing,
        "exercised_minus_promised": extra,
        "full_coverage": full_coverage,
        "windows_underexercised": windows_underexercised,
        "rows": rows,
    }


def windows_crlf_control() -> dict[str, Any]:
    """Catalog control: Ubuntu-only matrix + three CRLF failures must flag Windows."""
    promised = {"linux", "windows", "macos"}
    defects = {"windows": list(WINDOWS_CRLF_DEFECTS)}
    bad = compare(promised, {"linux"}, defects)
    good = compare(promised, {"linux", "windows"}, defects)
    unpromised = compare({"linux"}, {"linux"}, defects)
    fired = (
        bad["windows_underexercised"] is True
        and bad["full_coverage"] is False
        and "windows" in bad["promised_minus_exercised"]
        and len(WINDOWS_CRLF_DEFECTS) == 3
    )
    silent_good = good["windows_underexercised"] is False
    silent_unpromised = unpromised["windows_underexercised"] is False
    win_bad = next(r for r in bad["rows"] if r["platform"] == "windows")
    severity_ok = win_bad["severity"] == "underexercised-with-known-defect"
    empty_defects = compare(promised, {"linux"}, {"windows": []})
    win_empty = next(r for r in empty_defects["rows"] if r["platform"] == "windows")
    severity_discriminates = (
        win_empty["severity"] == "underexercised-no-known-defect"
        and win_empty["severity"] != win_bad["severity"]
    )
    return {
        "id": "AUD0049-C1-windows-crlf",
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent_good and silent_unpromised,
        "severity_discriminates": severity_discriminates,
        "pass": fired and silent_good and silent_unpromised and severity_discriminates,
        "bad": bad,
        "good": good,
        "unpromised": unpromised,
        "crlf_defect_count": len(WINDOWS_CRLF_DEFECTS),
    }


def first_present(relatives: tuple[str, ...]) -> dict[str, Any]:
    for rel in relatives:
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            return {"path": rel, "present": True, "bytes": path.stat().st_size}
    return {
        "path": relatives[0],
        "present": False,
        "bytes": 0,
        "tried": list(relatives),
    }


def promised_from_catalog() -> tuple[list[dict[str, Any]], list[str]]:
    """Recover the declared OS/client contract from on-disk catalog language.

    Charter and README are the catalog-named sources. When they are absent on
    this worktree, the recoverable contract is the catalog rows that name the
    support set this unit's own control treats as promised.
    """
    text = CATALOG.read_text(encoding="utf-8")
    notes: list[str] = []
    platforms: list[dict[str, Any]] = []

    if '"id": "AUD-0049"' not in text:
        raise SystemExit("FAILED:AUD-0049 catalog row AUD-0049 missing")
    if "Windows as promised-but-underexercised" not in text:
        raise SystemExit("FAILED:AUD-0049 catalog control sentence missing")
    notes.append("AUD-0049 tests_required names Windows as promised")

    if "{Windows, macOS, Linux}" not in text:
        raise SystemExit("FAILED:AUD-0049 BLD-0007 OS set missing from catalog")
    notes.append("BLD-0007 names the OS set {Windows, macOS, Linux}")

    for os_id, source in (
        ("linux", "BLD-0007 {Windows, macOS, Linux}"),
        ("windows", "AUD-0049 control + BLD-0007 {Windows, macOS, Linux}"),
        ("macos", "BLD-0007 {Windows, macOS, Linux}"),
    ):
        platforms.append({"id": os_id, "kind": "os", "source": source})

    if "Claude Code, Codex CLI, Antigravity/agy" not in text:
        raise SystemExit("FAILED:AUD-0049 BLD-0006 client set missing from catalog")
    notes.append("BLD-0006 names clients Claude Code, Codex CLI, Antigravity/agy")
    for client_id, label in (
        ("claude-code", "Claude Code"),
        ("codex-cli", "Codex CLI"),
        ("antigravity", "Antigravity/agy"),
    ):
        platforms.append(
            {
                "id": client_id,
                "kind": "client",
                "source": f"BLD-0006 declared client set ({label})",
            }
        )
    return platforms, notes


def expand_job_runners(job: dict[str, Any]) -> list[str]:
    raw = job.get("runs_on")
    legs = job.get("matrix_legs") or [{}]
    if isinstance(raw, str) and "matrix." in raw.lower():
        values = []
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            os_val = leg.get("os")
            if os_val:
                values.append(str(os_val))
        return values or [str(raw)]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if raw is None:
        return ["<missing>"]
    return [str(raw)]


def runners_from_inventory(inv: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for wf in inv.get("workflows") or []:
        wf_file = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            for raw in expand_job_runners(job):
                rows.append(
                    {
                        "workflow": wf_file,
                        "job_id": str(job.get("job_id") or ""),
                        "runs_on_raw": raw,
                        "os": classify_runner(raw),
                    }
                )
    return rows


def load_live_workflows() -> tuple[bool, list[dict[str, Any]]]:
    if not WFDIR.is_dir():
        return False, []
    files = sorted(WFDIR.glob("*.y*ml"))
    if not files:
        return False, []
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    rows: list[dict[str, Any]] = []
    for path in files:
        rel = path.relative_to(REPO).as_posix()
        text = path.read_text(encoding="utf-8")
        doc = {}
        if yaml is not None:
            loaded = yaml.safe_load(text) or {}
            if isinstance(loaded, dict):
                doc = loaded
        jobs = doc.get("jobs") if isinstance(doc.get("jobs"), dict) else {}
        if jobs:
            for jid, job in jobs.items():
                job = job or {}
                raw = job.get("runs-on")
                strat = (job.get("strategy") or {}).get("matrix") or {}
                os_axis = strat.get("os") if isinstance(strat, dict) else None
                if isinstance(raw, str) and "matrix.os" in raw.replace(" ", "") and isinstance(os_axis, list):
                    values = [str(x) for x in os_axis]
                elif isinstance(raw, list):
                    values = [str(x) for x in raw]
                else:
                    values = [str(raw) if raw is not None else "<missing>"]
                for val in values:
                    rows.append(
                        {
                            "workflow": rel,
                            "job_id": str(jid),
                            "runs_on_raw": val,
                            "os": classify_runner(val),
                        }
                    )
            continue
        for match in re.finditer(r"^\s*runs-on:\s*(.+?)\s*$", text, re.M):
            val = match.group(1).strip().strip("\"'")
            rows.append(
                {
                    "workflow": rel,
                    "job_id": "<regex>",
                    "runs_on_raw": val,
                    "os": classify_runner(val),
                }
            )
    return True, rows


def load_inventory() -> dict[str, Any]:
    if not INVENTORY.is_file():
        raise SystemExit(f"FAILED:AUD-0049 missing CI inventory {INVENTORY}")
    return json.loads(INVENTORY.read_text(encoding="utf-8"))


def measure() -> dict[str, Any]:
    charter = first_present(CHARTER_CANDIDATES)
    readme = first_present(README_CANDIDATES)
    promised, contract_notes = promised_from_catalog()
    promised_os = {p["id"] for p in promised if p["kind"] == "os"}
    promised_clients = [p for p in promised if p["kind"] == "client"]

    live_present, live_rows = load_live_workflows()
    inv = load_inventory()
    inv_rows = runners_from_inventory(inv)
    if not inv_rows:
        raise SystemExit("FAILED:AUD-0049 AUD-0041 inventory has no runs-on rows")

    # Live workflows are the preferred matrix. On this Linux worktree they
    # exist and are ubuntu-latest-only; AUD-0041 inventory is the fallback
    # receipt when the live tree is missing, and remains probe 2's grep target.
    source = "live-.github/workflows" if live_present and live_rows else "AUD-0041-inventory"
    runner_rows = live_rows if live_present and live_rows else inv_rows
    exercised_os = {r["os"] for r in runner_rows if r["os"] != "unknown"}
    raw_labels = sorted({r["runs_on_raw"] for r in runner_rows})

    defects_by_platform: dict[str, list[dict[str, Any]]] = {
        "windows": list(WINDOWS_CRLF_DEFECTS),
        "macos": list(MACOS_DEFECTS),
    }
    drift = compare(promised_os, exercised_os, defects_by_platform)

    absent_defects: list[dict[str, Any]] = []
    for platform in drift["promised_minus_exercised"]:
        for defect in defects_by_platform.get(platform) or []:
            absent_defects.append(
                {
                    "platform": platform,
                    "defect_id": defect["defect_id"],
                    "summary": defect["summary"],
                    "anchor": defect["anchor"],
                    "live_tree": defect.get("live_tree"),
                    "linux_ci_sees": defect["linux_ci_sees"],
                }
            )

    windows_crlf = [
        d for d in absent_defects if d["platform"] == "windows" and d["defect_id"].startswith("CRLF-")
    ]
    control = windows_crlf_control()

    headline = (
        "CI exercises "
        + (", ".join(drift["exercised_os"]) or "<none>")
        + "; promised-but-underexercised: "
        + (", ".join(drift["promised_minus_exercised"]) or "<none>")
        + f"; windows_underexercised={drift['windows_underexercised']}"
        + f"; windows_crlf_defects={len(windows_crlf)}"
    )

    gitattributes = (REPO / ".gitattributes").is_file()

    return {
        "charter": charter,
        "readme": readme,
        "contract_notes": contract_notes,
        "promised": promised,
        "promised_os": sorted(promised_os),
        "promised_clients": promised_clients,
        "live_workflows_present": live_present,
        "matrix_source": source,
        "inventory_totals": inv.get("totals") or {},
        "runner_rows": runner_rows,
        "raw_labels": raw_labels,
        "exercised_os": sorted(exercised_os),
        "drift": drift,
        "absent_platform_defects": absent_defects,
        "windows_crlf_defects": windows_crlf,
        "control": control,
        "headline": headline,
        "gitattributes_present": gitattributes,
        "validate_py_present": (REPO / "tools/command-center/validate.py").is_file(),
        "test_seed_present": (
            REPO / "tools/command-center/tests/test_seed.py"
        ).is_file(),
    }
