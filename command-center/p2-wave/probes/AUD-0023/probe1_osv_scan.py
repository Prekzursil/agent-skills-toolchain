#!/usr/bin/env python3
"""AUD-0023 named probe 1: osv-scanner over the repo's real lockfiles/manifests
plus a pip-freeze snapshot of the AUD-0022 installed Python closure.

Scope is explicit and bounded (never silently widened or narrowed):
  * every committed package-lock.json under the repo (excluding node_modules),
  * every committed requirements*.txt under the repo EXCLUDING other units'
    fixture directories (command-center/p2-wave/probes/**) so a planted-bad
    fixture belonging to a different unit is never counted as a production
    dependency,
  * a `pip freeze` snapshot of the interpreter that ran AUD-0022's probe2
    (the same installed-package closure AUD-0022 already measured), because
    this repo has no committed Python lockfile (poetry.lock / Pipfile.lock)
    for that closure -- recorded as an explicit residual, not silently
    invented as a lockfile that does not exist on disk.

Requires the real `osv-scanner` binary (Go binary, installed this session via
`go install github.com/google/osv-scanner/cmd/osv-scanner@v1`). If the binary
is absent, this probe reports ok=false with a diagnostic instead of inventing
a scan result.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "probe1-osv-scan.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-osv-scan.raw.txt"
FREEZE_SNAPSHOT = Path(__file__).resolve().parent / "pip-freeze-snapshot.txt"


def find_targets() -> dict:
    lockfiles = sorted(
        str(p.relative_to(REPO))
        for p in REPO.rglob("package-lock.json")
        if "node_modules" not in p.parts and ".git" not in p.parts
    )
    requirements = sorted(
        str(p.relative_to(REPO))
        for p in REPO.rglob("requirements*.txt")
        if "node_modules" not in p.parts
        and ".git" not in p.parts
        and "p2-wave/probes" not in str(p.relative_to(REPO)).replace("\\", "/")
    )
    return {"lockfiles": lockfiles, "requirements": requirements}


def write_pip_freeze() -> str:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    FREEZE_SNAPSHOT.write_text(r.stdout, encoding="utf-8")
    return r.stdout


def run_osv_scanner(binary: str, targets: list[str]) -> tuple[int, str, str]:
    args = [binary, "--format", "json"]
    for t in targets:
        args += ["-L", t]
    r = subprocess.run(
        args, cwd=str(REPO), capture_output=True, text=True, timeout=600
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def parser_hint(rel_path: str) -> str:
    """osv-scanner infers a parser from the filename; the pip-freeze snapshot
    is not literally named requirements.txt, so it needs the explicit
    `parser-type:path` form documented by `osv-scanner scan --help` (-L)."""
    if rel_path.endswith("pip-freeze-snapshot.txt"):
        return f"requirements.txt:{rel_path}"
    return rel_path


def summarize(osv_json: dict | None) -> dict:
    """Dedup vulnerability IDs across all scanned packages/files."""
    vuln_ids: set[str] = set()
    by_severity: dict[str, int] = {}
    affected_packages: list[dict] = []
    if osv_json:
        for result in osv_json.get("results", []):
            src = result.get("source", {}).get("path", "?")
            for pkg in result.get("packages", []):
                name = pkg.get("package", {}).get("name")
                version = pkg.get("package", {}).get("version")
                ecosystem = pkg.get("package", {}).get("ecosystem")
                vulns = pkg.get("vulnerabilities", []) or []
                if not vulns:
                    continue
                ids_here = []
                for v in vulns:
                    vid = v.get("id")
                    if vid:
                        vuln_ids.add(vid)
                        ids_here.append(vid)
                    sevs = v.get("database_specific", {}).get("severity")
                    if sevs:
                        by_severity[sevs] = by_severity.get(sevs, 0) + 1
                affected_packages.append(
                    {
                        "source_file": src,
                        "name": name,
                        "version": version,
                        "ecosystem": ecosystem,
                        "vuln_ids": sorted(set(ids_here)),
                    }
                )
    return {
        "distinct_vuln_id_count": len(vuln_ids),
        "distinct_vuln_ids": sorted(vuln_ids),
        "severity_histogram": by_severity,
        "affected_package_count": len(affected_packages),
        "affected_packages": affected_packages,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    binary = shutil.which("osv-scanner")
    targets_meta = find_targets()
    freeze_text = ""
    try:
        freeze_text = write_pip_freeze()
    except Exception as exc:  # noqa: BLE001
        freeze_text = f"<pip freeze failed: {type(exc).__name__}: {exc}>"

    if binary is None:
        doc = {
            "started_at": started,
            "binary_found": False,
            "ok": False,
            "error": "osv-scanner not found on PATH",
            "targets": targets_meta,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        raw = "AUD-0023 NAMED PROBE 1: osv-scanner over lockfiles\nBINARY NOT FOUND\nFAILED:AUD-0023-probe1\n"
        OUT_RAW.write_text(raw, encoding="utf-8")
        print(raw)
        return 1

    all_targets = [
        parser_hint(t)
        for t in (
            targets_meta["lockfiles"]
            + targets_meta["requirements"]
            + [str(FREEZE_SNAPSHOT.relative_to(REPO))]
        )
    ]
    rc, stdout_text, stderr_text = run_osv_scanner(binary, all_targets)
    out = stdout_text + ("\n--STDERR--\n" + stderr_text if stderr_text else "")

    parsed = None
    parse_err = None
    # osv-scanner prints "Scanned ..." status lines to stdout BEFORE the JSON
    # blob and a summary AFTER it; find the first '{' and parse with
    # raw_decode so trailing text after the JSON object does not trigger a
    # spurious "Extra data" failure.
    brace = stdout_text.find("{")
    if brace != -1:
        try:
            decoder = json.JSONDecoder()
            parsed, _end = decoder.raw_decode(stdout_text[brace:])
        except json.JSONDecodeError as exc:
            parse_err = f"{type(exc).__name__}: {exc}"
    else:
        parse_err = "no JSON object found in osv-scanner stdout"

    summary = summarize(parsed)
    ok = parsed is not None and rc in (0, 1)  # osv-scanner exits 1 when vulns found

    doc = {
        "started_at": started,
        "binary_found": True,
        "binary_version_cmd": f"{binary} --version",
        "targets": targets_meta,
        "pip_freeze_package_count": len(
            [ln for ln in freeze_text.splitlines() if ln.strip() and "==" in ln]
        ),
        "scan_exit_code": rc,
        "parse_error": parse_err,
        "ok": ok,
        **summary,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines = [
        "AUD-0023 NAMED PROBE 1: osv-scanner over real lockfiles + pip-freeze closure",
        f"unit=AUD-0023",
        f"binary={binary}",
        f"lockfile_targets={len(targets_meta['lockfiles'])}",
        f"requirements_targets={len(targets_meta['requirements'])}",
        f"pip_freeze_packages={doc['pip_freeze_package_count']}",
        f"scan_exit_code={rc}",
        f"distinct_vuln_id_count={summary['distinct_vuln_id_count']}",
        f"affected_package_count={summary['affected_package_count']}",
        "---- raw osv-scanner stdout/stderr (may be large) ----",
        out[:60000],
        f"{'SUCCESS' if ok else 'FAILED'}:AUD-0023-probe1",
    ]
    raw = "\n".join(raw_lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(f"unit=AUD-0023 scan_exit_code={rc} distinct_vuln_id_count={summary['distinct_vuln_id_count']} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
