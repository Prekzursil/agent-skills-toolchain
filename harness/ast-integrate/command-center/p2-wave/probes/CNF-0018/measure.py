#!/usr/bin/env python3
"""CNF-0018 measurement: three Phase-0 CRLF artefacts vs one cross-platform fail.

The Phase 0 baseline's eight failures triage as three Windows-CRLF artefacts,
four a sibling agent's transient TDD red phase, and one POSIX-only
(catalog BLD-0024). BASELINE-SNAPSHOT.json is absent on this worktree, so the
three CRLF hypotheses are reconstructed from the live detectors that still
document the Windows measurement:

  F-CRLF-VALIDATE-REACH6  tools/command-center/validate.py REACH-6
  F-CRLF-SEED-PROVENANCE  tools/command-center/seed.py provenance digest
  F-CRLF-RENDER-MANIFEST  tools/command-center/render.py render_manifest

Each is the same defect: hash working-tree bytes without LF normalisation, so a
Windows autocrlf=true tree disagrees with an LF blob / Linux CI.

The baseline (pre-fix) detector is `sha256(raw_bytes)`. The current code
LF-normalises. Linux-container verdicts use the baseline detector on LF files
(the container checkout). Windows is simulated by materialising CRLF copies of
the identical logical text -- this host is Linux and has no Windows box.

F-XP-BLANK-REGISTER-SHA256 is the known cross-platform failure: validate()
fail-closes on an empty provenance.register_sha256. It must FAIL in the
container so a green CRLF table is not silent-setup.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
FIXTURE_REGISTER = HERE / "fixtures" / "register.md"
FIXTURE_OVERLAY = HERE / "fixtures" / "overlay.json"

if str(CC_TOOLS) not in sys.path:
    sys.path.insert(0, str(CC_TOOLS))

import catalog as cat  # noqa: E402
import render as rnd  # noqa: E402
import seed  # noqa: E402
import validate as val  # noqa: E402


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def raw_digest(path: Path) -> str:
    """Baseline (Phase 0) detector: hash working-tree bytes as-is."""
    return sha256_bytes(path.read_bytes())


def lf_digest(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def classify(linux_outcome: str, windows_outcome: str) -> str:
    if linux_outcome == "PASS" and windows_outcome == "FAIL":
        return "Windows-only"
    if linux_outcome == "FAIL" and windows_outcome == "FAIL":
        return "cross-platform"
    if linux_outcome == "FAIL" and windows_outcome == "PASS":
        return "Linux-only"
    return "not-reproduced"


def outcome(pass_: bool) -> str:
    return "PASS" if pass_ else "FAIL"


def write_pair(tmp: Path, lf_text: str, name: str) -> tuple[Path, Path]:
    lf_path = tmp / f"{name}.lf"
    crlf_path = tmp / f"{name}.crlf"
    lf_bytes = lf_text.replace("\r\n", "\n").encode("utf-8")
    if not lf_bytes.endswith(b"\n"):
        lf_bytes += b"\n"
    crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
    lf_path.write_bytes(lf_bytes)
    crlf_path.write_bytes(crlf_bytes)
    if crlf_path.read_bytes().count(b"\r\n") < 1:
        raise RuntimeError(f"{name} CRLF fixture has zero CRLF")
    return lf_path, crlf_path


def measure_crlf_hash_pair(lf_path: Path, crlf_path: Path) -> dict:
    """Baseline detector: PASS on LF (Linux), FAIL on CRLF (Windows sim)."""
    lf_raw = raw_digest(lf_path)
    crlf_raw = raw_digest(crlf_path)
    lf_norm = lf_digest(lf_path)
    linux_pass = lf_raw == lf_norm
    windows_fail = crlf_raw != lf_norm
    return {
        "linux_raw_sha256": lf_raw,
        "windows_sim_raw_sha256": crlf_raw,
        "lf_normalised_sha256": lf_norm,
        "linux_bytes": lf_path.stat().st_size,
        "windows_sim_bytes": crlf_path.stat().st_size,
        "crlf_count_windows_sim": crlf_path.read_bytes().count(b"\r\n"),
        "linux_pass": linux_pass,
        "windows_sim_fail": windows_fail,
    }


def current_seed_agrees(lf_path: Path, crlf_path: Path, overlay: Path) -> dict:
    built_lf = seed.build_catalog(lf_path, overlay)
    built_crlf = seed.build_catalog(crlf_path, overlay)
    want = lf_digest(lf_path)
    return {
        "lf_recorded": built_lf["provenance"]["register_sha256"],
        "crlf_recorded": built_crlf["provenance"]["register_sha256"],
        "want_lf": want,
        "linux_pass": built_lf["provenance"]["register_sha256"] == want,
        "windows_sim_pass": built_crlf["provenance"]["register_sha256"] == want,
    }


def current_validate_agrees(lf_path: Path, crlf_path: Path, overlay: Path) -> dict:
    catalog = seed.build_catalog(lf_path, overlay)
    v_lf, _ = val.validate(catalog, register_path=lf_path)
    v_crlf, _ = val.validate(catalog, register_path=crlf_path)
    reach_lf = [v for v in v_lf if v.get("check") == "REACH-6"]
    reach_crlf = [v for v in v_crlf if v.get("check") == "REACH-6"]
    return {
        "linux_reach6": reach_lf,
        "windows_sim_reach6": reach_crlf,
        "linux_pass": reach_lf == [],
        "windows_sim_pass": reach_crlf == [],
    }


def current_render_agrees(tmp: Path, lf_text: str) -> dict:
    lf_root = tmp / "render-lf"
    crlf_root = tmp / "render-crlf"
    lf_root.mkdir()
    crlf_root.mkdir()
    body = lf_text.replace("\r\n", "\n")
    if not body.endswith("\n"):
        body += "\n"
    (lf_root / "STATUS.md").write_bytes(body.encode("utf-8"))
    (crlf_root / "STATUS.md").write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
    man_lf = rnd.render_manifest(lf_root)
    man_crlf = rnd.render_manifest(crlf_root)
    row_lf = next(r for r in man_lf["artifacts"] if r["path"].endswith("STATUS.md"))
    row_crlf = next(r for r in man_crlf["artifacts"] if r["path"].endswith("STATUS.md"))
    return {
        "linux_sha256": row_lf["sha256"],
        "windows_sim_sha256": row_crlf["sha256"],
        "linux_bytes": row_lf["bytes"],
        "windows_sim_bytes": row_crlf["bytes"],
        "linux_pass": row_lf["sha256"] == row_crlf["sha256"]
        and row_lf["sha256"] == sha256_bytes(body.encode("utf-8")),
        "windows_sim_pass": row_lf["sha256"] == row_crlf["sha256"],
    }


def measure_blank_digest(lf_path: Path, overlay: Path) -> dict:
    catalog = seed.build_catalog(lf_path, overlay)
    catalog["provenance"]["register_sha256"] = ""
    v_blank, _ = val.validate(catalog, register_path=lf_path)
    fired = any(
        v.get("check") == "REACH-6" and "missing or empty" in str(v.get("detail") or "")
        for v in v_blank
    )
    # Same mutation has no line-ending dependence: Windows sim is the same call.
    return {
        "fired": fired,
        "reach6": [dict(v) for v in v_blank if v.get("check") == "REACH-6"],
        "linux_fail": fired,
        "windows_sim_fail": fired,
    }


def row(
    fid: str,
    title: str,
    anchor: str,
    *,
    linux_outcome: str,
    windows_outcome: str,
    windows_method: str,
    extra: dict | None = None,
) -> dict:
    return {
        "id": fid,
        "title": title,
        "anchor": anchor,
        "linux_container": {
            "outcome": linux_outcome,
            "host": "linux-isolation",
        },
        "windows_simulated": {
            "outcome": windows_outcome,
            "method": windows_method,
        },
        "classification": classify(linux_outcome, windows_outcome),
        "detail": extra or {},
    }


def run_measure() -> dict:
    if not FIXTURE_REGISTER.is_file() or not FIXTURE_OVERLAY.is_file():
        raise FileNotFoundError("CNF-0018 fixtures missing")
    if not (CC_TOOLS / "validate.py").is_file():
        raise FileNotFoundError("tools/command-center/validate.py missing")

    lf_text = FIXTURE_REGISTER.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="cnf0018-") as td:
        tmp = Path(td)
        lf_path, crlf_path = write_pair(tmp, lf_text, "register")
        hash_pair = measure_crlf_hash_pair(lf_path, crlf_path)
        seed_now = current_seed_agrees(lf_path, crlf_path, FIXTURE_OVERLAY)
        val_now = current_validate_agrees(lf_path, crlf_path, FIXTURE_OVERLAY)
        rnd_now = current_render_agrees(tmp, "# status fixture\nline two\nline three\n")
        xp = measure_blank_digest(lf_path, FIXTURE_OVERLAY)

    crlf_method = "CRLF-materialised copy of identical logical text"
    failures = [
        row(
            "F-CRLF-VALIDATE-REACH6",
            "cc-validate REACH-6 hashed working-tree bytes (Windows autocrlf FAIL, Linux LF PASS)",
            "tools/command-center/validate.py",
            linux_outcome=outcome(hash_pair["linux_pass"] and val_now["linux_pass"]),
            windows_outcome=outcome(not hash_pair["windows_sim_fail"]),
            windows_method=crlf_method,
            extra={
                "baseline_detector": hash_pair,
                "current_validate_lf_normalised": {
                    "linux_pass": val_now["linux_pass"],
                    "windows_sim_pass": val_now["windows_sim_pass"],
                    "linux_reach6": val_now["linux_reach6"],
                    "windows_sim_reach6": val_now["windows_sim_reach6"],
                },
            },
        ),
        row(
            "F-CRLF-SEED-PROVENANCE",
            "seed.py --force recorded a raw worktree digest validate.py could not satisfy on Windows",
            "tools/command-center/seed.py",
            linux_outcome=outcome(hash_pair["linux_pass"] and seed_now["linux_pass"]),
            windows_outcome=outcome(not hash_pair["windows_sim_fail"]),
            windows_method=crlf_method,
            extra={
                "baseline_detector": hash_pair,
                "current_seed_lf_normalised": seed_now,
            },
        ),
        row(
            "F-CRLF-RENDER-MANIFEST",
            "cc-render hashed working-tree bytes so a Windows manifest drifted on Linux CI",
            "tools/command-center/render.py",
            linux_outcome=outcome(hash_pair["linux_pass"] and rnd_now["linux_pass"]),
            windows_outcome=outcome(not hash_pair["windows_sim_fail"]),
            windows_method=crlf_method,
            extra={
                "baseline_detector": hash_pair,
                "current_render_lf_normalised": rnd_now,
            },
        ),
        row(
            "F-XP-BLANK-REGISTER-SHA256",
            "validate() fail-closes on empty provenance.register_sha256 (platform-independent)",
            "tools/command-center/validate.py",
            linux_outcome="FAIL" if xp["linux_fail"] else "PASS",
            windows_outcome="FAIL" if xp["windows_sim_fail"] else "PASS",
            windows_method="same validate() mutation; no EOL axis",
            extra={"blank_digest": xp},
        ),
    ]

    crlf_rows = [f for f in failures if f["id"].startswith("F-CRLF-")]
    xp_row = failures[-1]
    crlf_pass = all(f["linux_container"]["outcome"] == "PASS" for f in crlf_rows)
    known_fail = xp_row["linux_container"]["outcome"] == "FAIL"
    return {
        "catalog": cat.__file__,
        "crlf_pass_in_container": crlf_pass,
        "known_failure_reproduced": known_fail,
        "failures": failures,
        "ok": crlf_pass and known_fail,
    }


def main() -> int:
    doc = run_measure()
    print("CNF-0018-MEASURE-JSON:" + json.dumps(doc, sort_keys=True, default=str))
    crlf = [f for f in doc["failures"] if f["id"].startswith("F-CRLF-")]
    xp = next(f for f in doc["failures"] if f["id"].startswith("F-XP-"))
    print(
        f"crlf_pass={doc['crlf_pass_in_container']} "
        f"xp_outcome={xp['linux_container']['outcome']} "
        f"classifications={[f['classification'] for f in doc['failures']]}"
    )
    if not doc["ok"]:
        print("FAILED:CNF-0018-measure container table does not satisfy tests_required")
        return 1
    if any(f["classification"] != "Windows-only" for f in crlf):
        print("FAILED:CNF-0018-measure CRLF rows not classified Windows-only")
        return 1
    if xp["classification"] != "cross-platform":
        print("FAILED:CNF-0018-measure XP row not cross-platform")
        return 1
    print("SUCCESS:CNF-0018-measure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
