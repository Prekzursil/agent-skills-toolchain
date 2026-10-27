#!/usr/bin/env python3
"""Wave-2 shard-10 INDEPENDENT REVIEWER (12 units).

Units (triangulated: READY-UNITS partition window between review:w2s9's
CNF-0169..IMP-0031 and review:w2s11's IMP-0095..IMP-0161; _p2shard10-w2 resume
notes name IMP-0070/0084/0090/0093; build:w2s10 transcript works IMP-0068/0070):
  IMP-0035 IMP-0036 IMP-0037 IMP-0038 IMP-0041 IMP-0044
  IMP-0051 IMP-0068 IMP-0070 IMP-0084 IMP-0090 IMP-0093

Adversarial verification per unit per the P2 fail-closed contract:
  1. catalog entry exists (output_path / output_schema) in WORK-UNIT-CATALOG.json
  2. artifact at output_path: exists, non-empty, parses as JSON, not
     self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  3. live probes re-run BY THE REVIEWER (exit 0 required)
  4. artifact sha256 recomputed (CRLF->LF normalized) matches
     probes/<id>/UNIT-ARTIFACT-MANIFEST.json row; manifest parses, unit_id
     matches; other registered rows also hash-checked (advisory)
  5. artifact validates against its output_schema (draft 2020-12)
  6. closure check per receipt_core: state==SUCCESS requires
     reviewer.verdict==PASS AND reviewer.independent==true; failure
     classification must not carry reviewer-absent; existing valid PASS
     closure stays SUCCESS (receipt bytes untouched - the manifest sha
     covers them)

ALL checks hold  -> CONFIRMED (closure confirmed, receipt untouched)
ANY check fails  -> FAIL with the precise failing check; receipt NOT touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CC = REPO / "command-center"
PROBES_ROOT = CC / "p2-wave" / "probes"
UNITS = [
    "IMP-0035", "IMP-0036", "IMP-0037", "IMP-0038",
    "IMP-0041", "IMP-0044", "IMP-0051", "IMP-0068",
    "IMP-0070", "IMP-0084", "IMP-0090", "IMP-0093",
]
PROBE_TIMEOUT = 300
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
REVIEWER_ABSENT_MARKS = {"reviewer-absent", "reviewer-unavailable", "reviewer-unavailable-cross-vendor"}

warnings.filterwarnings("ignore", category=DeprecationWarning)


def norm_sha256(path: Path) -> tuple[str, int, int]:
    b = path.read_bytes()
    n_raw = len(b)
    b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest(), n_raw, len(b)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(schema_path: Path, instance) -> list[str]:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
    from jsonschema.validators import RefResolver

    schema = load_json(schema_path)
    resolver = RefResolver(base_uri=schema_path.parent.as_uri() + "/", referrer=schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        return ["schema itself invalid: " + e.message[:200]]
    errs = []
    validator = Draft202012Validator(schema, resolver=resolver)
    for e in validator.iter_errors(instance):
        loc = "$" + "/".join(str(x) for x in e.absolute_path)
        errs.append(loc + ": " + e.message[:220])
    return errs[:5]


def main() -> int:
    catalog = load_json(CC / "WORK-UNIT-CATALOG.json")["work_units"]
    by_id = {u["id"]: u for u in catalog if isinstance(u, dict) and u.get("id")}
    results = []
    overall_ok = True

    for uid in UNITS:
        checks: list[str] = []
        fails: list[str] = []
        notes: list[str] = []
        t0 = time.time()

        def check(name: str, ok: bool, detail: str = "") -> None:
            tag = "ok" if ok else "FAIL"
            line = "[" + tag + "] " + name + ((" :: " + detail) if detail else "")
            checks.append(line)
            if not ok:
                fails.append(name + ((" :: " + detail) if detail else ""))

        def note(msg: str) -> None:
            notes.append(msg)

        # --- 1. catalog entry
        entry = by_id.get(uid)
        check("catalog-entry", entry is not None)
        if entry is None:
            results.append({"unit": uid, "verdict": "FAIL", "fails": fails})
            overall_ok = False
            print("== " + uid + ": FAIL (no catalog entry)")
            continue

        out_rel = entry.get("output_path") or ""
        schema_rel = entry.get("output_schema") or ""
        art = REPO / out_rel
        check("catalog-output-path", bool(out_rel), out_rel)
        check("catalog-output-schema", bool(schema_rel), schema_rel)
        check("owner-gate", entry.get("owner_approval_required") is not True,
              str(entry.get("owner_approval_required")))

        # --- 2. artifact exists / non-empty / parses / not self-blocked
        check("artifact-exists", art.is_file(), str(art))
        doc = None
        if art.is_file():
            raw_len = art.stat().st_size
            check("artifact-nonempty", raw_len > 0, str(raw_len) + " bytes")
            try:
                doc = load_json(art)
                check("artifact-parses-json", True)
            except Exception as e:
                check("artifact-parses-json", False, str(e)[:200])
            if doc is not None:
                state = str(doc.get("state") or "").upper()
                check("state-not-self-blocked", state not in NOT_DELIVERING, "state=" + repr(state))
                check("state-success", state == "SUCCESS", "state=" + repr(state))
                rid = str(doc.get("unit_id") or doc.get("id") or "")
                check("receipt-unit-id", rid == uid, "unit_id=" + repr(rid))
                sent = str(doc.get("sentinel") or doc.get("completion_sentinel") or "")
                check("sentinel-success-form", sent.startswith("SUCCESS:" + uid), sent[:90])
                rev = doc.get("reviewer") or {}
                rverdict = rev.get("verdict")
                rind = rev.get("independent")
                check("reviewer-verdict-PASS", rverdict == "PASS", "verdict=" + repr(rverdict))
                check("reviewer-independent-true", rind is True, "independent=" + repr(rind))
                fc = doc.get("failure") or {}
                fcl = set(str(x).lower() for x in (fc.get("classification") or []))
                check("no-reviewer-absent-classification",
                      not (fcl & REVIEWER_ABSENT_MARKS), str(fc.get("classification"))[:120])
                check("receipt-core-closure",
                      state == "SUCCESS" and rverdict == "PASS" and rind is True)
        else:
            doc = None

        # --- 3. re-run live probes (exit 0 required)
        pdir = PROBES_ROOT / uid
        probe_files = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
        check("probes-dir-present", pdir.is_dir(), str(pdir))
        check("probes-present", len(probe_files) > 0, str(len(probe_files)) + " probe scripts")
        probe_log = {}
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for pf in probe_files:
            try:
                r = subprocess.run(
                    [sys.executable, "-B", str(pf)],
                    cwd=str(REPO), capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT, env=env,
                )
                rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired:
                rc, out = 124, "TIMEOUT after " + str(PROBE_TIMEOUT) + "s"
            out = out or ""
            last = [ln for ln in out.strip().splitlines() if ln.strip()]
            marker = last[-1][:120] if last else "(no output)"
            ok = rc == 0
            probe_log[pf.name] = {"rc": rc, "marker": marker}
            check("probe-exit0:" + pf.name, ok, "rc=" + str(rc) + " :: " + marker)

        # --- 4. manifest sha256 match (CRLF->LF), post-probe re-read
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        check("manifest-exists", man_path.is_file(), str(man_path))
        if man_path.is_file() and art.is_file():
            try:
                man = load_json(man_path)
                check("manifest-parses-json", True)
            except Exception as e:
                check("manifest-parses-json", False, str(e)[:200])
                man = None
            if man is not None:
                rows0 = man.get("artifacts") or man.get("rows") or []
                row_ids = set(str(a.get("unit_id")) for a in rows0 if a.get("unit_id"))
                top_id = man.get("unit_id")
                check("manifest-unit-id",
                      top_id == uid or (row_ids and row_ids <= {uid}),
                      "top=" + repr(top_id) + " rows=" + repr(sorted(row_ids)))
                rows = man.get("artifacts") or man.get("rows") or []
                row = next(
                    (a for a in rows
                     if Path(str(a.get("path", ""))).as_posix() == Path(out_rel).as_posix()),
                    None,
                )
                check("manifest-row-for-output-path", row is not None, out_rel)
                if row is not None:
                    live_sha, n_raw, n_norm = norm_sha256(art)
                    check("sha256-match-normalized", row.get("sha256") == live_sha,
                          "manifest=" + str(row.get("sha256"))[:12] + " live=" + live_sha[:12])
                    try:
                        load_json(art)
                        check("artifact-stable-post-probes", True)
                    except Exception as e:
                        check("artifact-stable-post-probes", False, str(e)[:160])
                for a in rows:
                    if a is row:
                        continue
                    ap = REPO / str(a.get("path", ""))
                    if not ap.is_file():
                        note("manifest-row-missing-on-disk: " + str(a.get("path")))
                        continue
                    ash, _, _ = norm_sha256(ap)
                    if ash != a.get("sha256"):
                        note("manifest-row-drift: " + str(a.get("path")))

        # --- 5. output_schema validation
        if schema_rel and doc is not None:
            parts = [p.strip() for p in schema_rel.split("+")]
            primary = REPO / parts[0].split()[0]
            check("schema-file-exists", primary.is_file(), str(primary))
            if primary.is_file():
                errs = validate_schema(primary, doc)
                check("output-schema-valid", not errs, "; ".join(errs)[:300])
            for extra in parts[1:]:
                extra_p = REPO / extra.split()[0]
                if extra_p.suffix == ".json":
                    try:
                        load_json(extra_p)
                        check("secondary-schema-parses:" + extra_p.name, True)
                    except Exception as e:
                        check("secondary-schema-parses:" + extra_p.name, False, str(e)[:160])

        # --- 6. cross-instrument check: the repo's own admission gate
        adm_rc, adm_line = 0, "not-run"
        try:
            ra = subprocess.run(
                [sys.executable, "command-center/receipt_validate.py", str(art)],
                cwd=str(REPO), capture_output=True, text=True, timeout=120,
            )
            adm_rc = ra.returncode
            lines = [l for l in ((ra.stdout or "") + (ra.stderr or "")).splitlines() if l.strip()]
            adm_line = lines[-1][:220] if lines else f"rc={adm_rc} (no output)"
        except Exception as e:
            adm_rc, adm_line = -1, "validator-exec-error: " + str(e)[:120]
        check("repo-admission-validator", adm_rc == 0, adm_line)

        verdict = "CONFIRMED" if not fails else "FAIL"
        if fails:
            overall_ok = False
        results.append({
            "unit": uid,
            "verdict": verdict,
            "artifact": out_rel,
            "probes": probe_log,
            "advisories": notes,
            "fails": fails,
            "seconds": round(time.time() - t0, 1),
        })
        print("== " + uid + ": " + verdict + " (" + str(round(time.time() - t0, 1)) + "s)")
        for c in checks:
            print("   " + c)
        for w in notes:
            print("   [warn] " + w)

    out_path = REPO / "_reviewer10w2" / "reviewer_wave2_results.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_ok = sum(1 for r in results if r["verdict"] == "CONFIRMED")
    tail = ("SUCCESS:shard10-wave2-reviewer all 12 units hold" if overall_ok
            else "FAILED:shard10-wave2-reviewer see per-unit FAIL lines")
    print("\nSHARD10-W2 REVIEW: " + str(n_ok) + "/" + str(len(UNITS)) + " CONFIRMED -> " + tail)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
