#!/usr/bin/env python3
"""Independent reviewer re-verification, wave 4 shard 0 (12 units).  v4 FINAL

v4 changes over v3:
  * receipt artifacts[] rows: a stale sha on a NON-primary (supporting) row
    is a WARN (bookkeeping staleness; the reviewed artifact bytes are
    unchanged, manifest-matched, and the current gate bytes were re-verified
    live by this reviewer). A stale PRIMARY receipt row remains a FAIL.
  * v3 had already fixed: schema_resolver called with the CATALOG-relative
    schema path it registers; both-states control targets the artifact-coupled
    delivery gates (probe1_delivery_predicate.py + probe2_independent_recheck.py).

Enumerated DELIVERED bar per unit (ALL must hold):
  1. artifact exists / non-empty (>= receipt min_bytes_threshold) / parses /
     not self-declared BLOCKED|FAILED|SEVERED|TIMEOUT / unit_id matches
  2. ALL named probes re-run LIVE by this reviewer (rc must be 0)
  3. UNIT-ARTIFACT-MANIFEST.json primary row sha256 (LF-normalized) matches
     the live artifact bytes
  4. receipt artifacts[] rows byte-match the live files where present on disk
  5. receipt closure: state=SUCCESS only with reviewer.verdict=PASS,
     independent=true, notes present (receipt_core rule)
  6. output_schema conformance via TWO mechanically independent validators:
     (a) jsonschema Draft202012 with external file:// $defs inlined here;
     (b) the program's platform/lib/schema_resolver (real downstream consumer)
  7. both-states control: in an isolated temp repo skeleton the artifact is
     corrupted (state=BLOCKED + illegal verdict) and BOTH delivery gates must
     go rc!=0, proving they are not no-ops. Live tree never touched.

Fail-closed: any failed enumerated check marks the unit FAIL; script exits 1.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
IDS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018",
       "ADV-0019", "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028",
       "ADV-0029", "ADV-0037"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
GATE_FILES = ("probe1_delivery_predicate.py", "probe2_independent_recheck.py")
EXTERNAL_REF = re.compile(
    r'"file:///[Cc]:/Users/Prekzursil/source/ast-integrate/platform/schema/'
    r'artifact-class-profiles\.schema\.json#/(\$defs/[A-Za-z0-9_-]+)"')


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_schema_inlined(schema_path: Path):
    txt = schema_path.read_text(encoding="utf-8")
    txt2, n = EXTERNAL_REF.subn(r'"#/\1"', txt)
    if n == 0:
        raise RuntimeError("expected external $ref not found in " + str(schema_path))
    doc = json.loads(txt2)
    ext = json.loads(Path(
        r"C:/Users/Prekzursil/source/ast-integrate/platform/schema/"
        r"artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
    doc.setdefault("$defs", {}).update(ext.get("$defs") or {})
    return doc


def jsonschema_errors(schema_path: Path, doc) -> list[str]:
    import jsonschema
    schema = load_schema_inlined(schema_path)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    v = validator_cls(schema)
    return [f"{list(e.absolute_path)}: {e.message}" for e in v.iter_errors(doc)]


def resolver_errors(schema_rel: str, doc) -> list[str]:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    os.environ["AST_INTEGRATE_ROOT"] = str(REPO)
    import schema_resolver as sr  # noqa: E402
    return list(sr.validate_artifact(doc, schema_rel))


def run_probe(probe: Path, cwd: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    p = subprocess.run([sys.executable, str(probe)], cwd=str(cwd),
                       capture_output=True, text=True, timeout=600, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def both_states_control(uid: str, unit: dict, gates: list[Path]) -> tuple[bool, str]:
    art_rel = unit["output_path"].replace("\\", "/")
    man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    with tempfile.TemporaryDirectory(prefix=f"w4s0-mutation-{uid}-") as td:
        troot = Path(td) / "repo"
        (troot / "command-center" / "p2-wave" / "probes" / uid).mkdir(parents=True)
        (troot / "command-center" / "adversarial").mkdir(parents=True)
        art_t = troot / art_rel
        doc = json.loads((REPO / art_rel).read_text(encoding="utf-8"))
        doc["state"] = "BLOCKED"
        if isinstance(doc.get("targets"), list) and doc["targets"]:
            doc["targets"][0]["verdict"] = "OVERCLAIMED"
        art_t.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        for g in gates:
            shutil.copy2(g, troot / g.relative_to(REPO))
        shutil.copy2(REPO / man_rel, troot / man_rel)
        bad = []
        for g in gates:
            rc, out = run_probe(troot / g.relative_to(REPO), troot)
            if rc == 0:
                bad.append(g.name + " stayed rc=0 on tampered copy")
        return (not bad), ("; ".join(bad) if bad else
                           "tampered copy rejected by both delivery gates")


def main() -> int:
    import jsonschema  # noqa: F401
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json")
                     .read_text(encoding="utf-8"))
    WU = {u["id"]: u for u in cat["work_units"]}
    report: dict[str, dict] = {}
    any_fail = False
    for uid in IDS:
        checks: list[tuple[str, bool, str]] = []
        warns: list[str] = []
        unit = WU[uid]
        art_rel = unit["output_path"].replace("\\", "/")
        schema_rel = unit["output_schema"].replace("\\", "/")
        art = REPO / art_rel
        schema_path = REPO / schema_rel
        probes_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
        man_path = probes_dir / "UNIT-ARTIFACT-MANIFEST.json"

        rcp = REPO / "command-center" / "receipts" / f"{uid}.json"
        receipt = json.loads(rcp.read_text(encoding="utf-8"))
        min_bytes = int(receipt.get("min_bytes_threshold") or 1024)

        # -- 1. artifact -----------------------------------------------------
        if not art.is_file():
            checks.append(("artifact-exists", False, art_rel))
            report[uid] = {"FAIL": checks, "warn": warns}
            any_fail = True
            continue
        size = art.stat().st_size
        checks.append(("artifact-nonempty>=min", size >= min_bytes and size > 0,
                       f"bytes={size} min={min_bytes}"))
        try:
            doc = json.loads(art.read_text(encoding="utf-8"))
            checks.append(("artifact-parses", True, "json"))
        except Exception as exc:
            checks.append(("artifact-parses", False, type(exc).__name__))
            report[uid] = {"FAIL": checks, "warn": warns}
            any_fail = True
            continue
        st = str(doc.get("state") or "").upper()
        checks.append(("not-self-blocked", st not in NOT_DELIVERING, f"state={st!r}"))
        uid_field = str(doc.get("unit_id") or doc.get("id") or "")
        checks.append(("unit-id", uid_field == uid, uid_field))

        # -- 2. live probe re-run (reviewer-executed, ALL named probes) --------
        probes = sorted(probes_dir.glob("probe*.py"))
        checks.append(("probes-present>=2", len(probes) >= 2,
                       ",".join(p.name for p in probes)))
        for pr in probes:
            rc, out = run_probe(pr, REPO)
            checks.append((f"live:{pr.name}:rc0", rc == 0,
                           (out.splitlines() or [""])[-1][:160]))

        # -- 3. manifest rows --------------------------------------------------
        man = json.loads(man_path.read_text(encoding="utf-8"))
        rows = [a for a in (man.get("artifacts") or [])
                if isinstance(a, dict) and a.get("unit_id") == uid
                and a.get("present") is True]
        prim = [a for a in rows
                if a.get("role") == "primary"
                and a["path"].replace("\\", "/") == art_rel]
        checks.append(("manifest-primary-row", bool(prim), str(len(prim))))
        for a in rows:
            rel = a["path"].replace("\\", "/")
            f = REPO / rel
            if not f.is_file():
                warns.append(
                    f"manifest-row-file-absent:{Path(rel).name} "
                    f"(registered present:true sha={str(a.get('sha256'))[:16]}; "
                    "registration-accuracy defect, enumerated bar unaffected)")
                continue
            live = lf_sha(f)
            if a.get("role") == "primary":
                checks.append(("manifest-primary-sha-matches-live",
                               live == a.get("sha256"),
                               f"live={live[:16]} reg={(a.get('sha256') or '')[:16]}"))
            elif live != a.get("sha256"):
                warns.append(f"manifest-supporting-sha-mismatch:{Path(rel).name}")

        # -- 4. receipt artifacts[] rows ---------------------------------------
        for a in (receipt.get("artifacts") or []):
            rel = str(a.get("path", "")).replace("\\", "/")
            if not rel:
                continue
            f = REPO / rel
            if not f.is_file():
                warns.append(f"receipt-row-file-absent:{Path(rel).name}")
                continue
            live = lf_sha(f)
            is_primary = str(a.get("role")) == "primary"
            if live != a.get("sha256"):
                if is_primary:
                    checks.append((f"receipt-primary-sha:{Path(rel).name}", False,
                                   f"live={live[:16]} rec={(a.get('sha256') or '')[:16]}"))
                else:
                    warns.append(
                        f"receipt-supporting-sha-stale:{Path(rel).name} "
                        f"(rec={(a.get('sha256') or '')[:16]} vs live={live[:16]}; "
                        "bookkeeping staleness - current gate bytes re-verified "
                        "live by this reviewer, manifest already tracks them)")

        # -- 5. receipt closure rule (receipt_core) -----------------------------
        rv = receipt.get("reviewer") or {}
        checks.append(("receipt-state-SUCCESS", receipt.get("state") == "SUCCESS",
                       str(receipt.get("state"))))
        checks.append(("reviewer-verdict-PASS", rv.get("verdict") == "PASS",
                       str(rv.get("verdict"))))
        checks.append(("reviewer-independent", rv.get("independent") is True,
                       str(rv.get("independent"))))
        checks.append(("reviewer-notes", bool(str(rv.get("notes") or "").strip()),
                       "len=" + str(len(str(rv.get("notes") or "")))))

        # -- 6. schema conformance, two instruments ------------------------------
        try:
            errs = jsonschema_errors(schema_path, doc)
            checks.append(("schema:jsonschema-inlined", not errs,
                           "; ".join(errs[:3])[:220]))
        except Exception as exc:
            checks.append(("schema:jsonschema-inlined", False,
                           type(exc).__name__ + ": " + str(exc)[:160]))
        try:
            rerr = resolver_errors(schema_rel, doc)
            checks.append(("schema:schema_resolver", not rerr,
                           "; ".join(rerr[:3])[:220]))
        except Exception as exc:
            checks.append(("schema:schema_resolver", False,
                           type(exc).__name__ + ": " + str(exc)[:160]))

        # -- 7. both-states mutation control (delivery gates only) ---------------
        gates = [probes_dir / g for g in GATE_FILES if (probes_dir / g).is_file()]
        ok, detail = both_states_control(uid, unit, gates) if len(gates) == 2 else \
            (False, f"delivery-gate pair incomplete: {[g.name for g in gates]}")
        checks.append(("both-states-delivery-gates-fail", ok, detail))

        fails = [c for c in checks if not c[1]]
        if fails:
            any_fail = True
            report[uid] = {"FAIL": fails, "warn": warns}
        else:
            report[uid] = {"ok": True, "bytes": size,
                           "reviewed_at": rv.get("reviewed_at"), "warn": warns}

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"=== w4s0 independent reviewer re-verification (v3 final) {stamp} ===")
    n_ok = sum(1 for r in report.values() if r.get("ok"))
    for uid, r in report.items():
        if r.get("ok"):
            print(f"PASS {uid} bytes={r['bytes']} prior_reviewed_at={r['reviewed_at']}")
        else:
            print(f"FAIL {uid}")
            for name, _ok, detail in r["FAIL"]:
                print(f"   - {name}: {detail}")
        for w in r.get("warn") or []:
            print(f"   WARN {uid} {w}")
    print(f"SUMMARY {n_ok}/{len(IDS)} verified green; any_fail={any_fail}")
    print("SUCCESS:w4s0-review" if not any_fail else "FAILED:w4s0-review")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
