#!/usr/bin/env python3
"""Wave-2 shard-9 INDEPENDENT REVIEWER (12 units) - final instrument.

Instrument aligned to the established reviewer precedent (_rev1-w1-shard2/revlib.py):
whole-doc jsonschema draft-2020-12 against the catalog output_schema, with the
canonical-foreign file:// schema refs redirected onto THIS checkout.

Checks per unit (task contract):
  1. catalog entry exists with output_path/output_schema
  2. artifact: exists, non-empty, parses JSON, state==SUCCESS (not self-blocked)
  3. live probes re-run BY THE REVIEWER, exit 0 required
  4. artifact sha256 recomputed (CRLF->LF) matches probes/<id>/UNIT-ARTIFACT-MANIFEST.json
     row for the output_path (row-level unit_id accepted - older manifest shapes)
  5. output_schema validation (local-registry whole-doc, precedent instrument)
  6. closure: reviewer.verdict==PASS + independent==True (valid PASS closure stays SUCCESS)

ALL hold  -> CONFIRMED (no receipt write needed; closure stays SUCCESS)
ANY fail  -> FAIL with the precise failing check; receipt NOT touched.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
CC = REPO / "command-center"
PROBES_ROOT = CC / "p2-wave" / "probes"
FOREIGN = "file:///C:/Users/Prekzursil/source/ast-integrate/"
UNITS = [
    "CNF-0169", "CNF-0171", "CNF-0172", "CNF-0177", "CNF-0184", "CNF-0188",
    "CNF-0191", "CNL-0078", "IMP-0002", "IMP-0006", "IMP-0022", "IMP-0031",
]
PROBE_TIMEOUT = 300


def norm_sha256(path: Path) -> tuple[str, int, int]:
    b = path.read_bytes()
    n_raw = len(b)
    b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest(), n_raw, len(b)


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def validate_against_schema(doc, schema_rel: str) -> tuple[bool, str]:
    """Precedent instrument: local-registry whole-doc draft-2020-12 validation."""
    try:
        import warnings
        from referencing import Registry, Resource
        warnings.simplefilter("ignore")
        import jsonschema

        def _retrieve(uri: str):
            if uri.startswith(FOREIGN):
                local = REPO / uri[len(FOREIGN):]
            elif uri.startswith("file:///"):
                local = Path(uri[len("file:///"):])
            else:
                raise FileNotFoundError(uri)
            return Resource.from_contents(json.loads(local.read_text(encoding="utf-8")))

        schema_path = REPO / schema_rel
        schema = load_json(schema_path)
        reg = Registry(retrieve=_retrieve)
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        validator = cls(schema, registry=reg)
        errs = sorted(validator.iter_errors(doc), key=lambda e: [str(x) for x in e.absolute_path])
        if errs:
            firsts = "; ".join(
                f"${'/'.join(map(str, e.absolute_path))[:60]}: {e.message[:110]}" for e in errs[:3]
            )
            return False, f"{len(errs)} errors; first: {firsts}"
        return True, f"valid against {schema_rel} ({cls.__name__})"
    except Exception as ex:  # noqa: BLE001
        return False, f"validator error: {ex!r}"[:280]


def main() -> int:
    catalog = load_json(CC / "WORK-UNIT-CATALOG.json")["work_units"]
    by_id = {u.get("id"): u for u in catalog if isinstance(u, dict) and u.get("id")}
    results = []
    overall_ok = True

    for uid in UNITS:
        checks: list[str] = []
        fails: list[str] = []
        t0 = time.time()

        def check(name: str, ok: bool, detail: str = "") -> None:
            checks.append(f"[{'ok' if ok else 'FAIL'}] {name}" + (f" :: {detail}" if detail else ""))
            if not ok:
                fails.append(name + (f" ({detail[:150]})" if detail else ""))

        entry = by_id.get(uid)
        check("catalog-entry", entry is not None)
        if entry is None:
            results.append({"unit": uid, "verdict": "FAIL", "fails": fails})
            overall_ok = False
            continue

        out_rel = entry.get("output_path") or ""
        schema_rel = entry.get("output_schema") or ""
        art = REPO / out_rel
        check("catalog-output-path", bool(out_rel), out_rel)
        check("catalog-output-schema", bool(schema_rel), schema_rel)

        # 2. artifact exists / non-empty / parses / not self-blocked / reviewer closure
        check("artifact-exists", art.is_file(), str(art))
        doc = None
        if art.is_file():
            check("artifact-nonempty", art.stat().st_size > 0, f"{art.stat().st_size} bytes")
            try:
                doc = load_json(art)
                check("artifact-parses-json", True)
            except Exception as e:  # noqa: BLE001
                check("artifact-parses-json", False, str(e)[:200])
            if doc is not None:
                state = doc.get("state")
                check("state-not-blocked", state == "SUCCESS", f"state={state!r}")
                rev = doc.get("reviewer") or {}
                check("reviewer-verdict-PASS", rev.get("verdict") == "PASS", f"verdict={rev.get('verdict')!r}")
                check("reviewer-independent-true", rev.get("independent") is True,
                      f"independent={rev.get('independent')!r}")
                fc = doc.get("failure") or {}
                check("no-reviewer-absent-classification",
                      "reviewer-absent" not in (fc.get("classification") or []),
                      str(fc.get("classification"))[:120])

        # 3. live probes re-run by reviewer (exit 0)
        pdir = PROBES_ROOT / uid
        probe_files = sorted(pdir.glob("probe*.py")) if pdir.is_dir() else []
        check("probes-dir-present", pdir.is_dir(), str(pdir))
        check("probes-present", len(probe_files) > 0, f"{len(probe_files)} probe scripts")
        probe_log = {}
        for pf in probe_files:
            try:
                r = subprocess.run([sys.executable, "-B", str(pf)], cwd=str(REPO),
                                   capture_output=True, text=True, timeout=PROBE_TIMEOUT)
                rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired:
                rc, out = 124, f"TIMEOUT after {PROBE_TIMEOUT}s"
            last = [ln for ln in out.strip().splitlines() if ln.strip()]
            marker = last[-1][:120] if last else "(no output)"
            probe_log[pf.name] = {"rc": rc, "marker": marker}
            check(f"probe-exit0:{pf.name}", rc == 0, f"rc={rc} :: {marker}")

        # 4. manifest row sha256 match (CRLF->LF), post-probe stability
        man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        check("manifest-exists", man_path.is_file(), str(man_path))
        if man_path.is_file() and art.is_file():
            try:
                man = load_json(man_path)
                check("manifest-parses-json", True)
            except Exception as e:  # noqa: BLE001
                check("manifest-parses-json", False, str(e)[:200])
                man = None
            if man is not None:
                row = next((a for a in man.get("artifacts", [])
                            if Path(a.get("path", "")).as_posix() == Path(out_rel).as_posix()), None)
                check("manifest-row-for-output-path", row is not None, out_rel)
                if row is not None:
                    uid_ok = (man.get("unit_id") in (None, uid)) or (row.get("unit_id") == uid)
                    check("manifest-unit-id", uid_ok,
                          f"top={man.get('unit_id')!r} row={row.get('unit_id')!r}")
                    live_sha, n_raw, n_norm = norm_sha256(art)
                    check("sha256-match-normalized", row.get("sha256") == live_sha,
                          f"manifest={str(row.get('sha256'))[:12]} live={live_sha[:12]}")
                    try:
                        load_json(art)
                        check("artifact-stable-post-probes", True)
                    except Exception as e:  # noqa: BLE001
                        check("artifact-stable-post-probes", False, str(e)[:160])
                    rb = row.get("bytes")
                    note = "bytes==raw" if rb == n_raw else ("bytes==normalized" if rb == n_norm else "bytes-neither")
                    checks.append(f"[info] bytes: manifest={rb} raw={n_raw} norm={n_norm} ({note})")

        # 5. output_schema validation (precedent instrument)
        if schema_rel and doc is not None:
            primary = schema_rel.split("+")[0].strip().split()[0]
            ok, msg = validate_against_schema(doc, primary)
            check("output-schema-valid", ok, msg)
            for extra in schema_rel.split("+")[1:]:
                extra = extra.strip().split()[0]
                if extra.endswith(".json"):
                    ep = REPO / extra
                    try:
                        load_json(ep)
                        checks.append(f"[info] secondary schema parses: {extra}")
                    except Exception as e:  # noqa: BLE001
                        check(f"secondary-schema-parses:{Path(extra).name}", False, str(e)[:160])

        verdict = "CONFIRMED" if not fails else "FAIL"
        if fails:
            overall_ok = False
        results.append({
            "unit": uid,
            "verdict": verdict,
            "artifact": out_rel,
            "output_schema": schema_rel,
            "probes": probe_log,
            "fails": fails,
            "checks": checks,
            "seconds": round(time.time() - t0, 1),
        })
        print(f"== {uid}: {verdict} ({round(time.time() - t0, 1)}s)")
        for c in checks:
            if not c.startswith("[info]"):
                print("   " + c)

    out_path = REPO / "_p2shard9-w2" / "reviewer_wave2_results.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    n_ok = sum(1 for r in results if r["verdict"] == "CONFIRMED")
    print(f"\nSHARD9-W2 REVIEW: {n_ok}/{len(UNITS)} CONFIRMED -> "
          f"{'SUCCESS:shard9-wave2-reviewer all 12 units hold' if overall_ok else 'FAILED:shard9-wave2-reviewer see per-unit FAIL lines'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
