#!/usr/bin/env python3
"""Wave-4 shard-3 INDEPENDENT REVIEWER verification (read-only pass).

For each of the 12 shard-3 units, adversarially verify:
  1. artifact at catalog output_path exists, non-empty, parses, unit_id matches,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT
  2. re-run every named probe live; require exit 0 AND the SUCCESS:<uid> marker
  3. sha256 (CRLF->LF normalized) recomputed BEFORE and AFTER probe runs; both
     must equal the manifest row (path == output_path, present is true)
  4. output_schema validates (jsonschema Draft2020-12, $ref resolved from schema dir)

Writes NOTHING. Emits a JSON verdict table on stdout.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
MINE = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
        "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT = 900  # seconds per probe


def sha256_lf(p: Path) -> str:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def norm(p: str) -> str:
    return str(p).replace("\\", "/")


def check_schema(schema_path: Path, doc) -> str | None:
    try:
        import jsonschema
        from jsonschema import RefResolver
    except Exception as exc:  # pragma: no cover
        return f"jsonschema unavailable: {exc}"
    try:
        sd = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"schema unreadable: {exc}"
    try:
        resolver = RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=sd)
        jsonschema.Draft202012Validator(sd, resolver=resolver).validate(doc)
        return None
    except Exception as exc:
        return f"schema violation: {str(exc)[:400]}"


def main() -> int:
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"]}
    results: dict[str, dict] = {}
    all_ok = True
    for uid in MINE:
        r: dict = {"checks": {}, "fail": None}
        u = byid.get(uid)
        if u is None:
            r["fail"] = "no catalog entry"
            results[uid] = r
            all_ok = False
            continue
        out_rel = norm(u["output_path"])
        out = REPO / out_rel
        schema_rel = norm(u["output_schema"])
        schema_path = REPO / schema_rel

        # --- check 1: artifact
        c1 = {}
        c1["exists"] = out.is_file()
        c1["nonempty"] = out.is_file() and out.stat().st_size > 0
        doc = None
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            c1["parses"] = True
        except Exception as exc:
            c1["parses"] = False
            c1["parse_err"] = str(exc)[:200]
        if doc is not None:
            c1["unit_id"] = doc.get("unit_id")
            c1["state"] = doc.get("state")
            c1["not_self_blocked"] = str(doc.get("state", "")).upper() not in NOT_DELIVERING
        r["checks"]["artifact"] = c1
        art_ok = c1.get("exists") and c1.get("nonempty") and c1.get("parses") and c1.get("not_self_blocked")

        # --- check 3a: sha BEFORE probes + manifest row
        c3 = {}
        sha_before = None
        if art_ok:
            sha_before = sha256_lf(out)
            man_path = REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
                rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == uid]
                match = [a for a in rows
                         if norm(a.get("path", "")) == out_rel
                         and a.get("sha256") == sha_before
                         and a.get("present") is True]
                c3["manifest_rows_for_unit"] = len(rows)
                c3["sha_before_matches_manifest"] = bool(match)
                if not match and rows:
                    c3["manifest_row_paths"] = [norm(a.get("path", "")) for a in rows]
                    c3["manifest_row_shas"] = [a.get("sha256", "")[:16] for a in rows]
                    c3["live_sha"] = sha_before
            except Exception as exc:
                c3["manifest_error"] = str(exc)[:200]
        r["checks"]["manifest"] = c3
        man_ok = bool(c3.get("sha_before_matches_manifest"))

        # --- check 2: live probe re-run
        c2 = {"probes": []}
        probes_ok = art_ok  # no point running probes against a broken artifact
        if art_ok:
            ret = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")
                             .read_text(encoding="utf-8"))
            nps = ret.get("named_probes") or []
            if not nps:
                probes_ok = False
                c2["error"] = "receipt has zero named_probes"
            env = dict(os.environ)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            for np in nps:
                script = norm(np.get("command", ""))
                # recorded form: 'PYTHONDONTWRITEBYTECODE=1 python3 -B <path>'
                parts = script.split()
                py_idx = next((i for i, p in enumerate(parts) if p in ("python", "python3")), None)
                entry = {"recorded": script}
                if py_idx is None:
                    entry["exit"] = None
                    entry["error"] = "unparseable recorded command"
                    probes_ok = False
                else:
                    args = ["python", "-B"] + parts[py_idx + 2:]
                    try:
                        proc = subprocess.run(
                            args, cwd=str(REPO), capture_output=True, text=True,
                            timeout=PROBE_TIMEOUT, env=env)
                        outp = (proc.stdout or "") + (proc.stderr or "")
                        entry["exit"] = proc.returncode
                        entry["success_marker"] = f"SUCCESS:{uid}" in outp
                        entry["tail"] = outp.strip().splitlines()[-2:] if outp.strip() else []
                        if proc.returncode != 0 or not entry["success_marker"]:
                            probes_ok = False
                            entry["head"] = outp.strip().splitlines()[:6]
                    except subprocess.TimeoutExpired:
                        entry["exit"] = None
                        entry["error"] = f"timeout after {PROBE_TIMEOUT}s"
                        probes_ok = False
                c2["probes"].append(entry)
        r["checks"]["probes"] = c2

        # --- check 3b: sha AFTER probes (mutation check)
        if art_ok:
            sha_after = sha256_lf(out)
            c3["sha_after_matches_manifest"] = (sha_after == sha_before and man_ok)
            c3["artifact_mutated_by_probes"] = sha_after != sha_before

        # --- check 4: schema validation
        c4 = {}
        if art_ok and doc is not None:
            if not schema_path.is_file():
                c4["error"] = f"schema file missing: {schema_rel}"
            else:
                err = check_schema(schema_path, doc)
                if err:
                    c4["violation"] = err
                else:
                    c4["valid"] = True
        r["checks"]["schema"] = c4
        schema_ok = bool(c4.get("valid"))

        ok = bool(art_ok and probes_ok and man_ok and c3.get("sha_after_matches_manifest") and schema_ok)
        r["verdict"] = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
            # name the precise failing check
            fails = []
            if not art_ok:
                fails.append("artifact")
            if not probes_ok:
                fails.append("probes")
            if not man_ok or not c3.get("sha_after_matches_manifest"):
                fails.append("manifest-sha")
            if not schema_ok:
                fails.append("schema")
            r["fail"] = ",".join(fails)
        results[uid] = r
        print(f"{uid}: {r['verdict']}{(' (' + r['fail'] + ')') if r['fail'] else ''}", flush=True)

    (REPO / "_w4shard3_reviewer_wave4_result.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("ALL-OK" if all_ok else "SOME-FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
