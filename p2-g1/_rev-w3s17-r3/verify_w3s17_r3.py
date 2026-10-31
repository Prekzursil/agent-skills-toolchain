"""INDEPENDENT REVIEWER wave-3 shard-17 RESUME r3 - final verification battery.

Written fresh by the r3 resumed reviewer agent (a THIRD pass over this shard;
I did not build these units; my PASS is what closes them). READ-ONLY over
receipts/artifacts: this battery NEVER writes to command-center/ unless every
check on a unit holds AND the receipt still needs a closure stamp.

Prior passes: r1 (~06:00Z 2026-10-26, _review_w3s17_verify.py) found 12x FAIL
on output_schema, receipts untouched. w4s15/w4s16 then stamped SUCCESS/PASS
closures (07:29-07:32Z) while treating strict artifact-vs-output_schema
conformance as "non-gating census". r2 (_rev-w3s17-r2) re-verified the current
bytes and found all 12 still red; receipts left unchanged. The owner then
asked for the failed review checks to be re-run ("resume only the unfinished
ones + the red ones"); this r3 pass re-verifies the CURRENT bytes
adversarially with the SAME A-F checks, byte-identical logic.

Checks per unit:
  A  artifact at catalog output_path: exists, non-empty, parses as JSON dict;
     no state-like field self-declares BLOCKED/FAILED/SEVERED/TIMEOUT
     (recursive scan incl. sentinel text); catalog completion_sentinel in bytes
  B  EVERY named probe from SUBAGENT-RETURN re-run live HERE (Git-Bash pinned,
     python3 -> C:/Python314 verified, node verified): exit 0 required;
     literal FAILED: markers flagged
  C  probes/<id>/UNIT-ARTIFACT-MANIFEST.json: primary row path==output_path,
     present=true; EVERY row's sha256 recomputed over CRLF->LF-normalized bytes
     matches, bytes count matches
  D  output_schema: artifact validated against the catalog's declared
     output_schema via the repo's fail-closed resolver (instrument 1) AND via
     a directly-compiled physical profile with a hand-built referencing
     Registry (instrument 2, mechanically independent code path)
  E  canonical gate _measure_one_delivered.py <uid> -> SUCCESS:delivered
  F  receipt snapshot (state / reviewer block) - recorded, never modified here

Closure rule (fail-closed):
  ALL A-F green AND receipt already SUCCESS with PASS+independent => CONFIRMED
  ALL A-F green AND receipt BLOCKED/reviewer-absent => stamp closure
  ANY failed check => verdict FAIL with the precise failing check, receipt
  UNCHANGED.

Output: _rev-w3s17-r3/verify_out.json + one line per unit on stdout.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT_DIR = REPO / "_rev-w3s17-r3"
OUT_JSON = OUT_DIR / "verify_out.json"
BASH = r"C:\Program Files\Git\bin\bash.exe"

IDS = [
    "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157", "RES-0158",
    "RES-0160", "RES-0162", "RES-0164", "RES-0168", "RES-0175", "RES-0176",
]

SELF_BAD_TOKENS = ("BLOCKED", "FAILED", "SEVERED", "TIMEOUT")
STATEISH_KEYS = {"state", "status", "verdict", "result", "disposition", "sentinel"}
PROBE_TIMEOUT_S = 420
MEASURE_TIMEOUT_S = 420


def norm_sha(path: Path) -> tuple[str, int]:
    """sha256 over CRLF->LF-normalized bytes + raw byte count."""
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), len(raw)


def bash_run(cmd: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-lc", cmd],
        cwd=str(REPO), capture_output=True, text=True,
        errors="replace", timeout=timeout,
    )


def probe_commands(uid: str) -> list[str]:
    ret = json.loads(
        (REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")
        .read_text(encoding="utf-8")
    )
    nps = ret.get("named_probes")
    if isinstance(nps, str):
        nps = json.loads(nps)
    if nps is None:
        nps = ret.get("probes") or []
    cmds = []
    for item in nps or []:
        if isinstance(item, dict) and item.get("command"):
            cmds.append(str(item["command"]).strip())
    return cmds


def walk_self_decls(node, path="$", hits=None) -> list[tuple[str, str, str]]:
    """Return (path, key, value) for state-like keys whose string value carries
    a self-declaring bad token (value-form: 'FAILED', 'FAILED:...', etc.)."""
    if hits is None:
        hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}"
            if k in STATEISH_KEYS and isinstance(v, str):
                up = v.upper()
                for tok in SELF_BAD_TOKENS:
                    if re.search(rf"\b{tok}\b", up):
                        hits.append((p, k, v[:300]))
                        break
            walk_self_decls(v, p, hits)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_self_decls(v, f"{path}[{i}]", hits)
    return hits


# ---------------------------------------------------------------- instrument 2
def direct_physical_validator(resolver_mod, output_schema: str):
    """Compile the physical profile def straight from its file with a hand-built
    Registry - deliberately not the resolver's build_registry() code path."""
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    res = resolver_mod.resolve(output_schema)
    phys = (REPO / res.physical_path).resolve()
    frag = res.physical_fragment or ""
    doc = json.loads(phys.read_text(encoding="utf-8"))

    # Hand-built registry: anchor the physical doc (and receipt defs it refs)
    # by their own URIs, loaded from raw files - no resolver _retrieve.
    reg = Registry()
    receipt_path = (REPO / "platform/schema/receipt.schema.json").resolve()
    receipt_doc = json.loads(receipt_path.read_text(encoding="utf-8"))
    reg = reg.with_resource(receipt_path.as_uri(), Resource.from_contents(receipt_doc))
    reg = reg.with_resource(phys.as_uri(), Resource.from_contents(doc))
    return Draft202012Validator({"$ref": phys.as_uri() + frag}, registry=reg), res


# ---------------------------------------------------------------- main battery
def verify_unit(uid: str, byid: dict) -> dict:
    cat = byid[uid]
    out_path = REPO / cat["output_path"]
    r: dict = {"id": uid, "output_path": cat["output_path"], "ok": True,
               "fails": [], "info": {}}

    def fail(msg: str):
        r["ok"] = False
        r["fails"].append(msg)

    # -- A: artifact ---------------------------------------------------------
    if not out_path.is_file():
        fail(f"A artifact missing at output_path: {cat['output_path']}")
        r["info"]["artifact"] = "MISSING"
        return r
    raw = out_path.read_bytes()
    if not raw.strip():
        fail("A artifact is empty")
    try:
        art = json.loads(raw.decode("utf-8"))
    except Exception as e:
        fail(f"A artifact does not parse as JSON: {e}")
        return r
    if not isinstance(art, dict):
        fail("A artifact is not a JSON object")
    decls = walk_self_decls(art)
    r["info"]["self_declarations"] = [
        {"path": p, "key": k, "value": v} for p, k, v in decls
    ]
    if decls:
        fail(
            "A artifact self-declares non-delivered state at: "
            + "; ".join(f"{p}={v[:120]}" for p, k, v in decls[:6])
            + (" ..." if len(decls) > 6 else "")
        )
    sentinel = cat.get("completion_sentinel") or ""
    if sentinel and sentinel.encode() not in raw:
        fail(f"A completion_sentinel absent from artifact bytes: {sentinel}")
    r["info"]["artifact_bytes"] = len(raw)

    # -- B: live probes ------------------------------------------------------
    probe_results = []
    for cmd in probe_commands(uid):
        t0 = time.time()
        try:
            cp = bash_run(cmd, PROBE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            probe_results.append({"command": cmd, "exit": "TIMEOUT",
                                  "tail": f"timeout after {PROBE_TIMEOUT_S}s"})
            fail(f"B probe TIMEOUT: {cmd}")
            continue
        dt = time.time() - t0
        tail = ((cp.stdout or "") + (cp.stderr or ""))[-500:]
        entry = {"command": cmd, "exit": cp.returncode, "secs": round(dt, 1),
                 "tail": tail}
        probe_results.append(entry)
        if cp.returncode != 0:
            fail(f"B probe exit {cp.returncode}: {cmd} :: ...{tail[-220:]}")
        elif re.search(r"^FAILED:", cp.stdout or "", re.M):
            fail(f"B probe printed FAILED: marker: {cmd}")
    r["info"]["probes"] = probe_results

    # -- C: manifest ---------------------------------------------------------
    mpath = REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    try:
        man = json.loads(mpath.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"C manifest unreadable: {e}")
        man = {"artifacts": []}
    rows = man.get("artifacts") or []
    primary = [x for x in rows if x.get("role") == "primary"]
    if not primary:
        fail("C manifest has no primary row")
    else:
        prow = primary[0]
        if prow.get("path") != cat["output_path"]:
            fail(f"C primary row path != output_path: {prow.get('path')}")
        if not prow.get("present"):
            fail("C primary row present != true")
    for row in rows:
        rp = REPO / row["path"]
        if not rp.is_file():
            fail(f"C manifest row file missing: {row['path']}")
            continue
        sha, nbytes = norm_sha(rp)
        if sha != row.get("sha256"):
            fail(f"C sha mismatch for {row['path']}: manifest={row.get('sha256')} live={sha}")
        if row.get("bytes") is not None and nbytes != row.get("bytes"):
            fail(f"C bytes mismatch for {row['path']}: manifest={row.get('bytes')} live={nbytes}")
    r["info"]["manifest_rows"] = len(rows)

    # -- D: output_schema, two instruments ------------------------------------
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "schema_resolver", REPO / "platform/lib/schema_resolver.py")
    resolver_mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = resolver_mod
    spec.loader.exec_module(resolver_mod)

    schema_decl = cat.get("output_schema")
    errs1: list[str] = []
    try:
        errs1 = resolver_mod.validate_artifact(art, schema_decl)
    except Exception as e:
        errs1 = [f"<resolver raised> {e}"]
    r["info"]["schema_resolver_errors"] = errs1
    if errs1:
        fail(f"D output_schema violation ({len(errs1)} error(s), resolver): "
             + " | ".join(e[:200] for e in errs1[:6]))

    try:
        validator, res = direct_physical_validator(resolver_mod, schema_decl)
        errs2 = sorted(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in validator.iter_errors(art)
        )
    except Exception as e:
        errs2 = [f"<direct compile raised> {e}"]
    r["info"]["schema_direct_errors_count"] = len(errs2)
    r["info"]["schema_direct_first"] = errs2[:3]
    if errs1 and not errs2:
        fail("D INSTRUMENT DIVERGENCE: resolver red but direct validator green - "
             "investigate before any verdict")
    r["info"]["schema_physical"] = {
        "logical": getattr(res, "logical_id", None),
        "physical": str(getattr(res, "physical_path", "")),
        "fragment": str(getattr(res, "physical_fragment", "")),
    }

    # -- E: canonical measure gate -------------------------------------------
    try:
        cp = bash_run(
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B "
            f"command-center/p2-wave/_measure_one_delivered.py {uid}",
            MEASURE_TIMEOUT_S,
        )
        outline = (cp.stdout or "").strip().splitlines()
        last = outline[-1] if outline else ""
        r["info"]["measure_gate"] = {"exit": cp.returncode, "last": last[:200]}
        if cp.returncode != 0 or "SUCCESS:delivered" not in (cp.stdout or ""):
            fail(f"E canonical measure gate not SUCCESS:delivered: "
                 f"exit={cp.returncode} last={last[:160]}")
    except subprocess.TimeoutExpired:
        fail(f"E canonical measure gate TIMEOUT after {MEASURE_TIMEOUT_S}s")

    # -- F: receipt snapshot (read-only) --------------------------------------
    rpath = REPO / f"command-center/receipts/{uid}.json"
    try:
        rec = json.loads(rpath.read_text(encoding="utf-8"))
        rv = rec.get("reviewer") or {}
        r["info"]["receipt"] = {
            "state": rec.get("state"),
            "reviewer_verdict": rv.get("verdict") if isinstance(rv, dict) else None,
            "reviewer_independent": (rv.get("independent")
                                     if isinstance(rv, dict) else None),
            "reviewer_id": rv.get("reviewer_id") if isinstance(rv, dict) else None,
        }
    except Exception as e:
        fail(f"F receipt unreadable: {e}")
    return r


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {u["id"]: u for u in cat["work_units"]}
    missing = [u for u in IDS if u not in byid]
    if missing:
        print(f"FAILED:w3s17r3 catalog missing ids: {missing}")
        return 1

    results = {}
    for uid in IDS:
        t0 = time.time()
        res = verify_unit(uid, byid)
        res["secs"] = round(time.time() - t0, 1)
        res["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        results[uid] = res
        verdict = "OK" if res["ok"] else "FAIL"
        print(f"[{verdict}] {uid} ({res['secs']}s, {len(res['fails'])} fail(s))")
        for f in res["fails"]:
            print(f"    * {f[:400]}")
        print(f"    receipt: {json.dumps(res['info'].get('receipt'))}")

    # closure logic (only touches receipts if EVERYTHING holds on a unit)
    closures = {}
    for uid, res in results.items():
        if not res["ok"]:
            closures[uid] = "FAIL - receipt unchanged"
            continue
        rec_state = res["info"]["receipt"]
        if rec_state["state"] == "SUCCESS" and rec_state["reviewer_verdict"] == "PASS" \
                and rec_state["reviewer_independent"]:
            closures[uid] = "CONFIRMED - existing PASS closure stays SUCCESS"
        elif rec_state["state"] == "SUCCESS":
            closures[uid] = ("NEEDS-STAMP - all checks green but existing closure "
                             "invalid; reviewer stamp required")
        else:
            closures[uid] = "NEEDS-STAMP - all checks green; closure stamp required"

    out = {
        "battery": "w3s17-r3 independent reviewer (resume)",
        "reviewer": "claude-opus-5-5 independent reviewer review:w3s17 r3 2026-10-26",
        "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime": {"bash": BASH, "python3": "C:/Python314 (verified 3.14.6)",
                    "node": "v24.16.0 (verified)"},
        "results": results,
        "closures": closures,
        "tally": {
            "green_all_checks": sum(1 for r in results.values() if r["ok"]),
            "red": sum(1 for r in results.values() if not r["ok"]),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nTALLY:", json.dumps(out["tally"]))
    for uid, c in closures.items():
        print(f"  {uid}: {c}")
    print("SUCCESS:w3s17r3 battery complete" if all(
        r["ok"] for r in results.values()) else
        "FAILED:w3s17r3 one or more units red - receipts unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
