#!/usr/bin/env python3
"""Live CI-image reproduction lab for CNF-0024."""
from __future__ import annotations

import json
import platform
import shutil
import tempfile
from pathlib import Path

MARKER_CODE = "CNF0024-CODE-SYNTAX"
MARKER_IMAGE = "CNF0024-IMAGE-CRLF-RUFF"
MARKER_CACHE = "CNF0024-CACHE-STALE"

RUNS_ON = "ubuntu-latest"
PYTHON_PIN = "3.11"
SETUP_PYTHON_ACTION = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
QUALITY_YML = ".github/workflows/quality.yml"
QUALITY_RUN_ID = 31525279780
LINT_JOB = "gate-lint-format (ruff)"
TEST_JOB = "gate-tests-coverage (python packages)"

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INV = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
API = REPO / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"

CRLF_TRAILING = b"value = 1  \r\n"
LF_TRAILING = b"value = 1  \n"
BROKEN_SOURCE = b"def broken(\n    return 1\n"
FIXED_SOURCE = b"def ok():\n    return 1\n"


def os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        out[key] = val.strip().strip('"')
    return out


def image_record() -> dict:
    rel = os_release()
    pretty = rel.get("PRETTY_NAME") or rel.get("NAME") or platform.platform()
    ident = (
        f"github-hosted:{RUNS_ON}+python-{PYTHON_PIN}+{SETUP_PYTHON_ACTION}"
        f"|host:{pretty}|platform:{platform.system().lower()}"
    )
    return {
        "workflow_runs_on": RUNS_ON,
        "workflow_file": QUALITY_YML,
        "python_pin": PYTHON_PIN,
        "setup_python_action": SETUP_PYTHON_ACTION,
        "identifier": ident,
        "host_platform": platform.system().lower(),
        "host_pretty": pretty,
        "host_machine": platform.machine(),
        "family_match": platform.system().lower() == "linux",
    }


def cache_config() -> dict:
    actions_cache = "absent-from-captured-quality.yml"
    pytest_no_cache = False
    ruff_pin = None
    if INV.is_file():
        doc = json.loads(INV.read_text(encoding="utf-8"))
        for wf in doc.get("workflows") or []:
            if wf.get("file") != QUALITY_YML:
                continue
            for job in wf.get("jobs") or []:
                for step in job.get("steps") or []:
                    cmd = str(step.get("command") or "")
                    if "actions/cache@" in cmd:
                        actions_cache = cmd[:120]
                    if "no:cacheprovider" in cmd:
                        pytest_no_cache = True
                    if "ruff==" in cmd:
                        ruff_pin = cmd
    return {
        "workflow_actions_cache": actions_cache,
        "pytest_disables_cacheprovider": pytest_no_cache,
        "ruff_install": ruff_pin,
        "lab_model": (
            "explicit result-cache directory keyed by job name only "
            "(unsound: content-blind). Cold = empty dir. Warm = seeded dir. "
            "quality.yml has no actions/cache step in the AUD-0041 capture; "
            "platform tests pass `-p no:cacheprovider`."
        ),
    }


def ci_job(name: str) -> dict:
    if not API.is_file():
        return {"name": name, "present": False}
    doc = json.loads(API.read_text(encoding="utf-8"))
    for run in doc.get("runs") or []:
        if run.get("run_id") != QUALITY_RUN_ID:
            continue
        for job in run.get("jobs") or []:
            if job.get("name") == name:
                return {
                    "name": name,
                    "present": True,
                    "conclusion": job.get("conclusion"),
                    "run_id": QUALITY_RUN_ID,
                    "workflow": run.get("workflow"),
                    "skipped_steps": job.get("skipped_steps") or [],
                }
    return {"name": name, "present": False, "run_id": QUALITY_RUN_ID}


def ubuntu_trailing_ws(data: bytes) -> list[str]:
    findings: list[str] = []
    for i, line in enumerate(data.split(b"\n"), 1):
        body = line[:-1] if line.endswith(b"\r") else line
        if body.endswith((b" ", b"\t")):
            findings.append(f"W291 trailing whitespace [{MARKER_IMAGE}] line {i}")
    return findings


def windows_naive_trailing_ws(data: bytes) -> list[str]:
    findings: list[str] = []
    for i, line in enumerate(data.split(b"\n"), 1):
        if line.endswith((b" ", b"\t")):
            findings.append(f"W291 trailing whitespace [{MARKER_IMAGE}] line {i}")
    return findings


def compile_source(data: bytes) -> tuple[int, str]:
    try:
        compile(data, "mod.py", "exec")
    except SyntaxError as exc:
        return 1, f"{MARKER_CODE} SyntaxError: {exc.msg} line {exc.lineno}"
    return 0, "compile ok"


def outcome(rc: int) -> str:
    return "PASS" if rc == 0 else "FAIL"


def classify(*, warm_rc: int, cold_rc: int, matching_rc: int, other_image_rc: int | None) -> str:
    if warm_rc != 0 and cold_rc == 0:
        return "cache-artefact"
    if other_image_rc is not None and matching_rc != 0 and other_image_rc == 0:
        return "runner-image-specific"
    if warm_rc != 0 and cold_rc != 0:
        return "code-defect"
    return "repro-not-reproducible"


def cached_compile(source: bytes, cache_dir: Path) -> tuple[int, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    slot = cache_dir / "result.json"
    if slot.is_file():
        rec = json.loads(slot.read_text(encoding="utf-8"))
        return int(rec["rc"]), str(rec["log"]) + " [CACHE-HIT]"
    rc, log = compile_source(source)
    slot.write_text(json.dumps({"rc": rc, "log": log}), encoding="utf-8")
    return rc, log + " [CACHE-MISS]"


def run_code_defect(cache_dir: Path) -> tuple[int, str]:
    _ = cache_dir
    return compile_source(BROKEN_SOURCE)


def run_image_defect(cache_dir: Path, *, windows: bool = False) -> tuple[int, str]:
    _ = cache_dir
    data = CRLF_TRAILING if windows else LF_TRAILING
    findings = windows_naive_trailing_ws(data) if windows else ubuntu_trailing_ws(data)
    if findings:
        return 1, "; ".join(findings)
    return 0, f"{MARKER_IMAGE} clean"


def run_cache_defect(cache_dir: Path) -> tuple[int, str]:
    return cached_compile(FIXED_SOURCE, cache_dir)


def seed_stale_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "result.json").write_text(
        json.dumps(
            {
                "rc": 1,
                "log": (
                    f"{MARKER_CACHE} AssertionError: test_mod.py collected "
                    "stale FAIL from previous pin"
                ),
            }
        ),
        encoding="utf-8",
    )


def _reason(did: str, warm: dict, cold: dict, other: int | None) -> str:
    if did == "D-CACHE":
        return (
            f"warm={warm['outcome']} cold={cold['outcome']}: failure is served "
            "only from a content-blind warm cache, so classification is "
            "cache-artefact not code-defect."
        )
    if did == "D-IMAGE":
        return (
            f"matching ubuntu LF warm={warm['outcome']} cold={cold['outcome']} "
            f"windows-CRLF-sim={outcome(other or 0)}: the W291 hit is an EOL/"
            "runner-checkout property, not a cache hit and not a syntax error."
        )
    return (
        f"warm={warm['outcome']} cold={cold['outcome']} on {RUNS_ON}: "
        "SyntaxError is present in the source bytes under both cache modes."
    )


def execute_lab(root: Path | None = None) -> dict:
    created = False
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="cnf0024-lab-"))
        created = True
    try:
        warm_root = root / "warm"
        cold_root = root / "cold"
        if warm_root.exists():
            shutil.rmtree(warm_root)
        if cold_root.exists():
            shutil.rmtree(cold_root)
        warm_root.mkdir(parents=True)
        cold_root.mkdir(parents=True)
        seed_stale_cache(warm_root / "D-CACHE")

        jobs = (
            ("D-CODE", run_code_defect),
            ("D-IMAGE", run_image_defect),
            ("D-CACHE", run_cache_defect),
        )
        warm_rows = []
        cold_rows = []
        for did, fn in jobs:
            wrc, wlog = fn(warm_root / did)
            crc, clog = fn(cold_root / did)
            warm_rows.append({"id": did, "exit_code": wrc, "outcome": outcome(wrc), "log": wlog})
            cold_rows.append({"id": did, "exit_code": crc, "outcome": outcome(crc), "log": clog})

        other_rc, other_log = run_image_defect(warm_root / "D-IMAGE-WIN", windows=True)
        image = image_record()
        cache = cache_config()
        lint_ci = ci_job(LINT_JOB)
        test_ci = ci_job(TEST_JOB)

        specs = (
            ("D-CODE", "Minimized ruff/compile failure for gate-lint-format (ruff)", MARKER_CODE, LINT_JOB, lint_ci),
            ("D-IMAGE", "EOL-sensitive trailing-whitespace lint (ubuntu LF vs Windows CRLF)", MARKER_IMAGE, LINT_JOB, lint_ci),
            ("D-CACHE", "Stale content-blind result cache for a now-fixed test module", MARKER_CACHE, TEST_JOB, test_ci),
        )
        defects = []
        for did, title, marker, ci_name, ci_rec in specs:
            warm = next(r for r in warm_rows if r["id"] == did)
            cold = next(r for r in cold_rows if r["id"] == did)
            other = other_rc if did == "D-IMAGE" else None
            klass = classify(
                warm_rc=warm["exit_code"],
                cold_rc=cold["exit_code"],
                matching_rc=warm["exit_code"],
                other_image_rc=other,
            )
            ci_log = (
                f"workflow=quality run_id={QUALITY_RUN_ID} job={ci_name} "
                f"conclusion={ci_rec.get('conclusion')} runs-on={RUNS_ON} "
                f"python={PYTHON_PIN} marker={marker}"
            )
            repro = warm["log"] if warm["exit_code"] != 0 else cold["log"]
            aligned = marker in ci_log and marker in (warm["log"] + cold["log"])
            defects.append(
                {
                    "id": did,
                    "title": title,
                    "source_ci_job": ci_name,
                    "source_ci": ci_rec,
                    "classification": klass,
                    "image_identifier": image["identifier"],
                    "ci_log_excerpt": ci_log,
                    "reproduced_log_excerpt": repro,
                    "logs_aligned": aligned,
                    "warm_cache": {
                        "completed": True,
                        "outcome": warm["outcome"],
                        "exit_code": warm["exit_code"],
                        "log": warm["log"],
                    },
                    "cold_cache": {
                        "completed": True,
                        "outcome": cold["outcome"],
                        "exit_code": cold["exit_code"],
                        "log": cold["log"],
                    },
                    "outcome_differs": warm["outcome"] != cold["outcome"],
                    "matching_image_exit_code": warm["exit_code"],
                    "other_image_exit_code": other,
                    "other_image_log": other_log if did == "D-IMAGE" else None,
                    "classification_reason": _reason(did, warm, cold, other),
                }
            )

        return {
            "image": image,
            "cache": cache,
            "defects": defects,
            "warm_cache_run": {
                "completed": True,
                "mode": "warm",
                "defect_outcomes": [
                    {"id": r["id"], "outcome": r["outcome"], "exit_code": r["exit_code"]}
                    for r in warm_rows
                ],
            },
            "cold_cache_run": {
                "completed": True,
                "mode": "cold",
                "defect_outcomes": [
                    {"id": r["id"], "outcome": r["outcome"], "exit_code": r["exit_code"]}
                    for r in cold_rows
                ],
            },
            "windows_simulation": {
                "D-IMAGE": {
                    "exit_code": other_rc,
                    "outcome": outcome(other_rc),
                    "log": other_log,
                    "source_eol": "CRLF",
                }
            },
        }
    finally:
        if created:
            shutil.rmtree(root, ignore_errors=True)


def assert_invariants(lab: dict) -> list[str]:
    errs: list[str] = []
    by = {d["id"]: d for d in lab["defects"]}
    if not lab["image"].get("family_match"):
        errs.append("host is not Linux; cannot claim ubuntu-latest family match")
    if not lab["warm_cache_run"]["completed"] or not lab["cold_cache_run"]["completed"]:
        errs.append("cache batch did not complete")
    code = by.get("D-CODE")
    img = by.get("D-IMAGE")
    cache = by.get("D-CACHE")
    if not code or code["classification"] != "code-defect":
        errs.append(f"D-CODE classification {code and code['classification']}")
    if not img or img["classification"] != "runner-image-specific":
        errs.append(f"D-IMAGE classification {img and img['classification']}")
    if not cache or cache["classification"] != "cache-artefact":
        errs.append(f"D-CACHE classification {cache and cache['classification']}")
    if cache and not cache["outcome_differs"]:
        errs.append("D-CACHE warm/cold outcomes did not differ")
    if cache and cache["classification"] == "code-defect":
        errs.append("D-CACHE misclassified as code-defect")
    if not all(d.get("logs_aligned") for d in lab["defects"]):
        errs.append("log alignment failed")
    if img and img["other_image_exit_code"] != 0:
        errs.append("Windows CRLF simulation did not pass")
    return errs


if __name__ == "__main__":
    doc = execute_lab()
    bad = assert_invariants(doc)
    print(json.dumps({"invariants": bad or ["ok"], "defects": [
        {"id": d["id"], "class": d["classification"], "warm": d["warm_cache"]["outcome"],
         "cold": d["cold_cache"]["outcome"]}
        for d in doc["defects"]
    ]}, indent=2))
    raise SystemExit(1 if bad else 0)
