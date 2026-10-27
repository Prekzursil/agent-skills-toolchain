"""Independent reviewer battery v1 for wave-3 shard-23 (12 units).

Written by the r2 independent reviewer (fresh instruments, not a re-run of the
06:28 reviewer battery). Checks per unit:
  1. receipt exists / non-empty / parses / not self-BLOCKED-FAILED / sentinel
  2. live probe re-run (exit 0, final JSON ok!=false, no FAILED: marker) under
     pinned Git Bash AND pwsh7 (catalog second-shell requirement)
  3. CRLF-normalized sha256 recomputation vs UNIT-ARTIFACT-MANIFEST.json rows
  4. primary manifest row path == catalog output_path
  5. output_schema validation - instrument A: estate-canonical
     platform/lib/schema_resolver.validate_artifact; instrument B: raw
     whole-doc draft-2020-12 validation against the physical schema docs
Fail-closed: any failing check fails the unit.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = Path(__file__).resolve().parent / "_w3s23r2_results.json"
GITBASH = r"C:\Program Files\Git\bin\bash.exe"

UNITS = [
    "TST-0195", "TST-0197", "TST-0202", "TST-0204", "TST-0206", "TST-0215",
    "TST-0219", "TST-0221", "TST-0223", "TST-0227", "TST-0230", "TST-0233",
]

sys.path.insert(0, str(ROOT / "platform" / "lib"))
from schema_resolver import validate_artifact  # instrument A (canonical)

# --- instrument B: raw whole-doc validation, independently loaded docs ------
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

_TAIL = re.compile(r"/(platform/schema/|command-center/schema/)(.+)$")


def _retrieve(uri: str) -> Resource:
    raw = uri.split("#", 1)[0]
    path_s = urlparse(raw).path if raw.startswith("file:") else raw
    if re.match(r"^/[A-Za-z]:/", path_s or ""):
        path_s = path_s[1:]
    posix = (path_s or "").replace("\\", "/")
    m = _TAIL.search(posix)
    if not m:
        raise RuntimeError(f"instrument-B retrieval escaped repo: {uri}")
    doc = json.loads((ROOT / m.group(1) / m.group(2)).read_text(encoding="utf-8"))
    return Resource.from_contents(doc, default_specification=DRAFT202012)


_REG_B = Registry(retrieve=_retrieve)


def instrument_b(receipt: dict, output_schema: str) -> list[str]:
    shim_path, frag = output_schema.split("#", 1)
    shim_doc = json.loads((ROOT / shim_path).read_text(encoding="utf-8"))
    validator = Draft202012Validator(shim_doc, registry=_REG_B)
    errs = []
    for e in sorted(validator.iter_errors(receipt), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(f"{loc}: {e.message}")
    return errs


def norm_sha(p: Path) -> tuple[str, int, int, str]:
    """Returns (sha256 of CRLF->LF normalized bytes, raw length,
    normalized length, eol form). The unit contract fixes the HASH
    normalization; the manifest 'bytes' convention is accepted against
    either raw or normalized length (builder convention varies) and the
    eol form is recorded so the choice is auditable."""
    raw = p.read_bytes()
    n_raw = len(raw)
    norm = raw.replace(b"\r\n", b"\n")
    n_norm = len(norm)
    if n_raw == n_norm:
        eol = "LF"
    elif raw.count(b"\r\n") * 2 + raw.count(b"\r") + raw.count(b"\n") == n_raw + n_norm and raw.count(b"\r") == raw.count(b"\n"):
        eol = "CRLF"
    else:
        eol = "MIXED"
    return hashlib.sha256(norm).hexdigest(), n_raw, n_norm, eol


def run_probe(rel_path: str, shell: str, timeout: int = 600) -> dict:
    if shell == "bash":
        cmd = f'cd "{ROOT.as_posix()}" && PYTHONDONTWRITEBYTECODE=1 python3 -B {rel_path}'
        argv = [GITBASH, "-c", cmd]
    else:
        ps = (
            f'Set-Location "{ROOT}"; '
            "$env:PYTHONDONTWRITEBYTECODE='1'; "
            f"python3 -B {rel_path}"
        )
        argv = ["pwsh", "-NoProfile", "-Command", ps]
    try:
        cp = subprocess.run(argv, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
        out, err, code = cp.stdout or "", cp.stderr or "", cp.returncode
    except subprocess.TimeoutExpired:
        return {"shell": shell, "exit": "TIMEOUT", "ok_flag": None,
                "failed_marker": False, "tail": "timeout"}
    ok_flag = None
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if lines:
        try:
            tail_obj = json.loads(lines[-1])
            if isinstance(tail_obj, dict):
                ok_flag = tail_obj.get("ok", "absent")
        except Exception:
            ok_flag = "unparsed"
    marker = bool(re.search(r"(?m)^FAILED:", out + err))
    return {"shell": shell, "exit": code, "ok_flag": ok_flag,
            "failed_marker": marker,
            "tail": (lines[-1][:160] if lines else (err.strip()[-160:] if err.strip() else ""))}


def main() -> None:
    catalog = json.loads((ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wu = {u["id"]: u for u in catalog["work_units"]}

    results: dict[str, dict] = {}
    for uid in UNITS:
        entry = wu[uid]
        out_path = entry["output_path"]
        checks: dict[str, dict] = {}
        receipt_path = ROOT / out_path
        receipt: dict = {}
        raw_text = ""

        # ---- 1. existence / parse / self-declared state -------------------
        if not receipt_path.is_file():
            checks["receipt"] = {"pass": False, "why": f"missing: {out_path}"}
        else:
            raw_bytes = receipt_path.read_bytes()
            if not raw_bytes.strip():
                checks["receipt"] = {"pass": False, "why": "empty file"}
            else:
                try:
                    receipt = json.loads(raw_bytes.decode("utf-8"))
                    raw_text = raw_bytes.decode("utf-8", errors="replace")
                    state = receipt.get("state")
                    sentinel = receipt.get("sentinel", "")
                    self_failed = state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
                    dead_sentinel = bool(re.search(rf"(?i)FAILED:\s*{re.escape(uid)}\b", raw_text))
                    open_defects = [
                        d.get("id", "?") for d in receipt.get("defects", [])
                        if isinstance(d, dict) and d.get("severity") in {"P0", "P1"}
                        and d.get("status", "open") == "open"
                    ]
                    rev = receipt.get("reviewer") or {}
                    checks["receipt"] = {
                        "pass": not (self_failed or dead_sentinel),
                        "bytes": len(raw_bytes),
                        "state": state,
                        "sentinel": sentinel,
                        "catalog_sentinel_present": entry["completion_sentinel"] in raw_text,
                        "self_failed_state": self_failed,
                        "dead_sentinel_in_text": dead_sentinel,
                        "open_p0p1_defects": open_defects,
                        "reviewer_block": {k: rev.get(k) for k in
                                           ("verdict", "independent", "reviewer_id")},
                    }
                except Exception as exc:
                    checks["receipt"] = {"pass": False, "why": f"unparseable: {exc}"}

        # ---- 2/3/4. manifest rows: presence, size, sha, primary==catalog ---
        man_path = ROOT / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        probes: list[str] = []
        if not man_path.is_file():
            checks["manifest"] = {"pass": False, "why": f"missing manifest {man_path}"}
        else:
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
            except Exception as exc:
                checks["manifest"] = {"pass": False, "why": f"unparseable manifest: {exc}"}
            else:
                rows = man.get("artifacts", [])
                bad_rows, ok_rows = [], 0
                eol_notes = []
                for row in rows:
                    rp = ROOT / row["path"]
                    if not rp.is_file():
                        bad_rows.append(f"DEAD {row['path']}")
                        continue
                    sha, n_raw, n_norm, eol = norm_sha(rp)
                    if row.get("role") == "named-probe":
                        probes.append(row["path"])
                    sha_ok = sha == row.get("sha256")
                    bytes_ok = row.get("bytes") in (n_raw, n_norm)
                    if not (sha_ok and bytes_ok):
                        bad_rows.append(
                            f"HASH {row['path']} live=({sha[:12]},{n_raw}raw/{n_norm}lf,{eol}) "
                            f"manifest=({str(row.get('sha256'))[:12]},{row.get('bytes')})")
                    else:
                        ok_rows += 1
                        if n_raw != n_norm:
                            eol_notes.append(f"{Path(row['path']).name}:{eol} "
                                             f"(bytes row={row.get('bytes')} = LF-normalized)")
                primary = [r for r in rows if r.get("role") == "primary"]
                prim_ok = len(primary) == 1 and primary[0]["path"] == out_path
                checks["manifest"] = {
                    "pass": not bad_rows and prim_ok and ok_rows >= 1,
                    "rows": len(rows), "rows_matching": ok_rows,
                    "bad_rows": bad_rows,
                    "eol_notes": eol_notes,
                    "primary_path_matches_catalog": prim_ok,
                    "named_probes": probes,
                }

        # ---- 5. live probe re-run under BOTH shells ------------------------
        probe_res = {}
        for rel in probes:
            b = run_probe(rel, "bash")
            w = run_probe(rel, "pwsh")
            gate_b = b["exit"] == 0 and b["ok_flag"] is not False and not b["failed_marker"]
            gate_w = w["exit"] == 0 and w["ok_flag"] is not False and not w["failed_marker"]
            divergence = (b["exit"] != w["exit"]) or (b["ok_flag"] != w["ok_flag"])
            probe_res[Path(rel).name] = {
                "bash": b, "pwsh": w,
                "pass": gate_b and gate_w,
                "second_shell_divergence": divergence,
            }
        checks["probes"] = {
            "pass": bool(probes) and all(r["pass"] for r in probe_res.values()),
            "count": len(probes),
            "results": probe_res,
        }

        # ---- 6. schema: instrument A (canonical) + instrument B (raw) ------
        if receipt:
            try:
                errs_a = validate_artifact(receipt, entry["output_schema"])
            except Exception as exc:
                errs_a = [f"instrument A raised: {exc}"]
            errs_b = instrument_b(receipt, entry["output_schema"])
            checks["schema"] = {
                "pass": not errs_a and not errs_b,
                "instrument_A_resolver_errors": errs_a,
                "instrument_B_whole_doc_errors": errs_b,
            }
        else:
            checks["schema"] = {"pass": False,
                                "instrument_A_resolver_errors": ["no receipt"],
                                "instrument_B_whole_doc_errors": ["no receipt"]}

        unit_pass = all(c.get("pass") for c in checks.values())
        results[uid] = {"unit_pass": unit_pass, "checks": checks}
        print(f"{uid}: {'PASS' if unit_pass else 'FAIL'} "
              f"(receipt={checks['receipt'].get('pass')} manifest={checks['manifest'].get('pass')} "
              f"probes={checks['probes'].get('pass')}/{checks['probes'].get('count')} "
              f"schema={checks['schema'].get('pass')} "
              f"schemaA={len(checks['schema'].get('instrument_A_resolver_errors', []))} "
              f"schemaB={len(checks['schema'].get('instrument_B_whole_doc_errors', []))})",
              flush=True)

    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_pass = sum(1 for r in results.values() if r["unit_pass"])
    print(f"\ntotal {n_pass}/{len(UNITS)} PASS; results -> {OUT}")


if __name__ == "__main__":
    main()
