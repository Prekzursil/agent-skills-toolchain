"""Independent reviewer battery, wave-2 shard 19, round r2.

For each unit: artifact exists/non-empty/parses/not-self-blocked; live probe reruns
(exit 0 + SUCCESS marker); sha256 recomputation (CRLF->LF normalized) vs
UNIT-ARTIFACT-MANIFEST.json primary row; output_schema validation via BOTH the
estate canonical gate (platform/lib/receipt_schema_gate.py --schema-only) AND a
direct jsonschema run pinned to this tree; receipt admission pre-checks.

Read-only with respect to receipts. Emits verify_r2.json + a compact stdout table.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(r"C:\Users\Prekzursil\p2-g1")
OUT_DIR = BASE / "_p2shard19-w2-review-r2"
IDS = ["RES-0151", "RES-0157", "RES-0158", "RES-0160", "RES-0162", "RES-0164",
       "RES-0168", "RES-0175", "RES-0176", "RES-0179", "RES-0180", "RES-0182"]
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-shard19-w2-r2-2026-10-26"


def sha_norm(path: Path) -> tuple[str, int, int]:
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), crlf


def run(cmd: list[str], timeout: int = 420) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def check(ck: list[dict], name: str, ok: bool, detail: str) -> None:
    ck.append({"check": name, "pass": bool(ok), "detail": detail[:400]})


def review_unit(uid: str, cat: dict) -> dict:
    entry = cat[uid]
    ck: list[dict] = []
    res: dict = {"unit_id": uid, "checked_at": NOW, "checks": ck}

    # --- artifact existence / parse / self-declaration ---
    art_rel = entry["output_path"]
    art = BASE / art_rel
    if not art.is_file():
        check(ck, "artifact_exists", False, f"missing: {art_rel}")
        res["verdict"] = "FAIL"
        return res
    check(ck, "artifact_exists", True, art_rel)
    nbytes = art.stat().st_size
    check(ck, "artifact_nonempty", nbytes > 0, f"{nbytes} bytes")
    try:
        doc = json.loads(art.read_text(encoding="utf-8"))
        check(ck, "artifact_parses", True, "json ok")
    except Exception as exc:
        check(ck, "artifact_parses", False, f"{type(exc).__name__}: {exc}")
        res["verdict"] = "FAIL"
        return res
    state = doc.get("state")
    sentinel = str(doc.get("sentinel", ""))
    selfbad = state in ("BLOCKED", "FAILED") or sentinel.startswith(("FAILED:", "BLOCKED:"))
    check(ck, "not_self_declared_blocked_failed", not selfbad,
          f"state={state} sentinel={sentinel[:100]!r}")

    # --- manifest + sha256 ---
    man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    man = BASE / man_rel
    try:
        mdoc = json.loads(man.read_text(encoding="utf-8"))
        check(ck, "manifest_parses", True, man_rel)
    except Exception as exc:
        check(ck, "manifest_parses", False, f"{type(exc).__name__}: {exc}")
        mdoc = None
    live_sha, live_len, crlf_n = sha_norm(art)
    prim = None
    if mdoc:
        for row in mdoc.get("artifacts", []):
            if row.get("role") == "primary":
                prim = row
                break
        if prim is None:
            check(ck, "manifest_primary_row", False, "no role=primary row")
        else:
            check(ck, "manifest_primary_row", True,
                  f"path={prim.get('path')} sha={str(prim.get('sha256'))[:12]}...")
            check(ck, "manifest_primary_path_matches_catalog", prim.get("path") == art_rel,
                  f"manifest={prim.get('path')} catalog={art_rel}")
            check(ck, "sha256_matches_manifest", prim.get("sha256") == live_sha,
                  f"manifest={str(prim.get('sha256'))[:16]}.. live={live_sha[:16]}.. "
                  f"crlf_pairs={crlf_n}")
            if prim.get("bytes") not in (None, live_len):
                check(ck, "manifest_bytes_consistent", False,
                      f"manifest={prim.get('bytes')} live_norm={live_len}")
            else:
                check(ck, "manifest_bytes_consistent", True, f"{live_len}")

    # --- live probe reruns ---
    probe_files = sorted(
        [p for p in (BASE / f"command-center/p2-wave/probes/{uid}").glob("probe*")
         if p.suffix in (".py", ".mjs")])
    check(ck, "probes_present", len(probe_files) >= 1,
          ",".join(p.name for p in probe_files))
    probe_results = []
    probes_all_ok = len(probe_files) >= 1
    for pf in probe_files:
        cmd = [sys.executable, str(pf)] if pf.suffix == ".py" else ["node", str(pf)]
        try:
            r = run(cmd)
            ok = r.returncode == 0 and "SUCCESS:" in r.stdout
            marker = [ln for ln in r.stdout.splitlines() if "SUCCESS:" in ln or "FAILED:" in ln]
            passfield = None
            for ln in r.stdout.splitlines():
                if ln.strip().startswith("{") and '"pass"' in ln:
                    try:
                        passfield = json.loads(ln).get("pass")
                    except Exception:
                        pass
            check(ck, f"probe_rerun:{pf.name}", ok,
                  f"exit={r.returncode} pass_field={passfield} marker={marker[-1][:120] if marker else 'NONE'}")
            if not ok:
                probes_all_ok = False
            probe_results.append({"script": pf.name, "exit": r.returncode,
                                  "pass_field": passfield,
                                  "marker": marker[-1] if marker else None})
        except subprocess.TimeoutExpired:
            check(ck, f"probe_rerun:{pf.name}", False, "TIMEOUT 420s")
            probes_all_ok = False
            probe_results.append({"script": pf.name, "exit": None, "timeout": True})
    res["probe_reruns"] = probe_results

    # --- output_schema validation: canonical gate + independent jsonschema ---
    schema_rel = entry.get("output_schema")
    gate = run([sys.executable, "platform/lib/receipt_schema_gate.py", "--schema-only", art_rel])
    gate_ok = gate.returncode == 0 and gate.stdout.strip().startswith("SCHEMA-VALID")
    first_errs = [ln.strip() for ln in gate.stdout.splitlines() if ln.strip().startswith("- ")]
    check(ck, "output_schema_validates_gate", gate_ok,
          f"gate exit={gate.returncode} first={first_errs[0] if first_errs else gate.stdout[:150]}")
    res["schema_gate"] = {"exit": gate.returncode, "errors": first_errs,
                          "error_count": len(first_errs)}

    js_errs: list[str] = []
    try:
        import jsonschema
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012

        shim = json.loads((BASE / schema_rel).read_text(encoding="utf-8"))

        def retrieve(uri: str):
            s = uri
            if s.startswith("file:///"):
                s = s[len("file:///"):]
            elif s.startswith("file://"):
                s = s[len("file://"):]
            s = Path(s.replace("\\", "/")).as_posix()
            # pin refs declared against the sibling ast-integrate checkout onto THIS tree
            if "/source/ast-integrate/" in s:
                s = s.replace("/source/ast-integrate/", "/p2-g1/")
            data = json.loads(Path(s).read_text(encoding="utf-8"))
            return Resource.from_contents(data, default_specification=DRAFT202012)

        registry = Registry(retrieve=retrieve)
        V = jsonschema.validators.validator_for(shim)
        v = V(shim, registry=registry)
        for e in v.iter_errors(doc):
            js_errs.append(f"{e.json_path}: {e.message[:200]}")
        check(ck, "output_schema_validates_jsonschema", not js_errs,
              f"{len(js_errs)} errors; first: {js_errs[0] if js_errs else 'none'}")
    except Exception as exc:
        check(ck, "output_schema_validates_jsonschema", False,
              f"instrument error {type(exc).__name__}: {exc}")
        js_errs = [f"instrument-error: {exc}"]
    res["schema_jsonschema_error_count"] = len(js_errs)
    res["schema_jsonschema_first"] = js_errs[0] if js_errs else None

    # --- receipt admission pre-checks ---
    rec_rel = f"command-center/receipts/{uid}.json"
    rec = BASE / rec_rel
    try:
        rdoc = json.loads(rec.read_text(encoding="utf-8"))
        check(ck, "receipt_parses", True, rec_rel)
        check(ck, "receipt_builder_terminal_blocked", rdoc.get("state") == "BLOCKED",
              f"state={rdoc.get('state')}")
        cls = (rdoc.get("failure") or {}).get("classification") or []
        check(ck, "receipt_classification_reviewer_absent", "reviewer-absent" in cls,
              f"classification={cls}")
        rrow = (rdoc.get("artifacts") or [{}])[0]
        check(ck, "receipt_sha_matches_live",
              rrow.get("sha256") == live_sha and rrow.get("path") == art_rel,
              f"receipt={str(rrow.get('sha256'))[:16]}.. live={live_sha[:16]}..")
        mreg = rdoc.get("manifest_registration") or {}
        check(ck, "receipt_manifest_registered", mreg.get("registered") is True
              and (BASE / str(mreg.get("manifest_path", "x"))).is_file(),
              f"registered={mreg.get('registered')} path={mreg.get('manifest_path')}")
        res["receipt_state_before"] = rdoc.get("state")
    except FileNotFoundError:
        check(ck, "receipt_parses", False, f"missing {rec_rel}")
    except Exception as exc:
        check(ck, "receipt_parses", False, f"{type(exc).__name__}: {exc}")

    res["verdict"] = "PASS" if all(c["pass"] for c in ck) else "FAIL"
    res["failing_checks"] = [c["check"] for c in ck if not c["pass"]]
    return res


def main() -> int:
    slice_path = BASE / "command-center/catalog-slices/RES-2.json"
    cat = {x["id"]: x for x in json.loads(slice_path.read_text(encoding="utf-8"))}
    missing = [i for i in IDS if i not in cat]
    if missing:
        print(f"FAILED:reviewer-r2 catalog missing {missing}")
        return 1
    results = [review_unit(uid, cat) for uid in IDS]
    out = {
        "reviewer_id": REVIEWER_ID,
        "wave": "p2-wave-2 shard 19",
        "round": "r2",
        "checked_at": NOW,
        "receipts_modified": False,
        "results": results,
    }
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "verify_r2.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    npass = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"reviewer-r2 battery complete: {npass}/{len(results)} PASS")
    for r in results:
        print(f"{r['unit_id']} {r['verdict']} failing={r['failing_checks']}")
        if r["verdict"] == "FAIL":
            print(f"    schema_js_errors={r.get('schema_jsonschema_error_count')} "
                  f"first={r.get('schema_jsonschema_first')}")
    print("SUCCESS:reviewer-r2" if npass == len(results) else
          f"FAILED:reviewer-r2 {len(results)-npass} unit(s) failing checks")
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
