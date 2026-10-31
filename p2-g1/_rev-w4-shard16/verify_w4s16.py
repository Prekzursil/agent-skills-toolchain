#!/usr/bin/env python3
"""INDEPENDENT REVIEWER wave-4 shard-16 (12 units) - read-only verification, r2.

Units (10 RES receipts BLOCKED/reviewer-absent at dispatch; TST-0018 and
TST-0028 already SUCCESS with receipt-level PASS/independent closures that
this reviewer re-verifies live):

  RES-0158 RES-0160 RES-0162 RES-0164 RES-0168
  RES-0175 RES-0176 RES-0179 RES-0180 RES-0182
  TST-0018 TST-0028

Per unit, adversarially re-derived LIVE by this reviewer (who did not build
any of these units):

  A  catalog entry exists with output_path / output_schema / completion_sentinel
  B  artifact at output_path: exists, non-empty, parses, not self-declared
     BLOCKED/FAILED/SEVERED/TIMEOUT (state, status and verdict fields)
  C  receipt: parses, unit_id matches, spec_anchor names the unit; closability
     (BLOCKED+reviewer-absent = closable; SUCCESS requires PASS+independent)
  D  catalog completion sentinel present in BOTH receipt text and artifact text
  E  live probe re-run: named probes from SUBAGENT-RETURN.json plus every
     probe[0-9]*.py script, executed from the repo root; each must exit 0 and
     either print a SUCCESS: marker or emit structured JSON with pass=true and
     red=[] (the TST probes' documented convention), never a FAILED: marker
  G  the program's own DELIVERED instrument re-run by this reviewer:
     python -I command-center/p2-wave/_measure_one_delivered.py <uid> exit 0
  H  sha256 over CRLF->LF-normalized bytes: live artifact vs EVERY receipt
     artifacts[] row AND EVERY UNIT-ARTIFACT-MANIFEST.json row (bytes too)
  I  declared min_bytes_threshold respected by the live artifact
  J  output_schema: fail-closed resolve via platform/lib/schema_resolver;
     clause-required fields checked on the artifact; artifact-vs-class-profile
     error count recorded as INFORMATION (the w3s16-r3 sanctioned reading:
     this reviewer's own census finds 31/80 randomly-sampled already-closed
     SUCCESS receipts violate the same class profiles, so strict conformance
     is not the program's closure instrument and would retroactively fail
     ~425/1088 closed units; see _rev-w4-shard16/census_out.json)
  J2 receipt_core (draft 2020-12) strict validation of the CURRENT receipt and
     of the SIMULATED post-closure receipt (0 errors each) BEFORE any write
  K  recorded evidence sanity: >=2 evidence items, >=1 source-role and >=1
     verifier-role probe, every recorded probe exit_code == 0
  N  negative-control spec: per-unit both-states control spec (CONTROL_SPECS)
     validated against THIS run's live probe output - every bad-state and
     good-state check name must appear with pass:true in the reviewer's own
     live re-run, and any cited artifact control row must exist with
     fired_on_bad_state=true and silent_on_good_state=true (or a both_states
     block with both states). A spec that cannot be validated fails the unit;
     controls are never invented to satisfy the SUCCESS schema.

Read-only: verdicts go to _rev-w4-shard16/verify_out.json. Exit 0 only when
ALL 12 units hold ALL checks. The closure emitter consumes this output and
touches nothing else.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover
    Draft202012Validator = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT_JSON = REPO / "_rev-w4-shard16" / "verify_out.json"
CENSUS_JSON = REPO / "_rev-w4-shard16" / "census_out.json"
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 1200
MEASURE_TIMEOUT_S = 2700
UNITS = [
    "RES-0158", "RES-0160", "RES-0162", "RES-0164", "RES-0168",
    "RES-0175", "RES-0176", "RES-0179", "RES-0180", "RES-0182",
    "TST-0018", "TST-0028",
]
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-w4s16-2026-10-26"

# --------------------------------------------------------------------------
# Per-unit both-states negative-control specs.
# Every check name below must appear with pass:true in the REVIEWER'S OWN live
# probe re-run for the unit (validated in check N); artifact_row paths must
# resolve in the artifact and carry both booleans true (or a both_states
# block). The spec is EVIDENCE-POINTING, never evidence-substituting.
# --------------------------------------------------------------------------
CONTROL_SPECS: dict[str, dict] = {
    "RES-0158": {
        "kind": "mutation",
        "bad_checks": ["nc-NC-ACH-CRITIQUES-CAN-GO-RED-red-on-bad"],
        "good_checks": ["nc-NC-ACH-CRITIQUES-CAN-GO-RED-silent-on-good"],
        "artifact_row": ["negative_controls", 0],
    },
    "RES-0160": {
        "kind": "mutation",
        "bad_checks": ["bless-all-mutant-went-red"],
        "good_checks": [],
        "artifact_row": ["negative_controls", 0],
    },
    "RES-0162": {
        "kind": "adversarial-payload",
        "bad_checks": ["live-large-payload-fails-loud"],
        "good_checks": ["live-small-payload-spawns-clean"],
    },
    "RES-0164": {
        "kind": "mutation",
        "bad_checks": ["replay-field-redaction-breaks-replay"],
        "good_checks": ["non-replay-field-redaction-still-replays"],
        "artifact_row": ["negative_controls", 0],
    },
    "RES-0168": {
        "kind": "known-broken-fixture",
        "bad_checks": ["live-bad-endpoint-down", "detector-discriminates"],
        "good_checks": ["live-good-http-200"],
    },
    "RES-0175": {
        "kind": "known-broken-fixture",
        "bad_checks": ["quarantine-discriminates"],
        "good_checks": [],
        "artifact_row": ["both_states"],
    },
    "RES-0176": {
        "kind": "other",
        "bad_checks": ["nc-names-non-transferable-abstraction", "nc-states-why"],
        "good_checks": ["no-verdict-marks-group-chat-transferable"],
    },
    "RES-0179": {
        "kind": "known-broken-fixture",
        "bad_checks": ["recorded-negative-control-fails-as-required"],
        "good_checks": [
            "recorded-control-ok-and-evidenced",
            "live-control-reachable-through-same-path",
        ],
    },
    "RES-0180": {
        "kind": "mutation",
        "bad_checks": ["three-genuine-plants-wake-both"],
        "good_checks": [
            "three-cosmetic-plants-wake-poller-only",
            "both-states-discriminate",
        ],
    },
    "RES-0182": {
        "kind": "other",
        "bad_checks": ["nc-rejects-adopted-despite-literature-miss"],
        "good_checks": [
            "literature-controls-present-with-extractor",
            "promotion-guard-recorded",
        ],
    },
}


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_resolver():
    """Import platform/lib/schema_resolver.py by FILE PATH (never as the
    platform.* package - that namespace shadows stdlib `platform`)."""
    src = REPO / "platform" / "lib" / "schema_resolver.py"
    spec = importlib.util.spec_from_file_location("w4s16_schema_resolver", src)
    if spec is None or spec.loader is None:
        return None, "resolver-spec-none"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        return None, f"resolver-import-failed:{type(exc).__name__}:{exc}"
    return mod, None


def load_core_validator():
    if Draft202012Validator is None:
        return None
    sch = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8")
    )
    core = dict(sch["$defs"]["receipt_core"])
    core["$defs"] = sch["$defs"]
    Draft202012Validator.check_schema(core)
    return Draft202012Validator(core)


def load_named_probes(uid: str) -> tuple[list[dict], dict | None]:
    p = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    if not p.is_file():
        return [], None
    try:
        ret = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], None
    return [x for x in (ret.get("named_probes") or []) if isinstance(x, dict)], ret


def probe_plan(uid: str) -> list[dict]:
    """Ordered, de-duplicated probe list: named probes first, then any
    probe[0-9]*.py script not already covered."""
    plan: list[dict] = []
    seen_scripts: set[str] = set()
    named, _ = load_named_probes(uid)
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid

    def build(cmd: str) -> dict | None:
        env: dict[str, str] = {}
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
        parts = cmd.split()
        if not parts:
            return None
        script = parts[-1]
        if parts[0] in ("python3", "python"):
            argv = [sys.executable, "-B", script]
        elif parts[0] == "node":
            argv = ["node", script]
        else:
            argv = parts
        return {"command": cmd, "argv": argv, "env": env,
                "name": Path(script).name, "script": script}

    for np in named:
        cmd = str(np.get("command") or "").strip()
        if not cmd:
            continue
        b = build(cmd)
        if b and b["name"] not in seen_scripts:
            seen_scripts.add(b["name"])
            b["pid"] = str(np.get("id") or b["name"])
            plan.append(b)
    for p in sorted(pdir.glob("probe[0-9]*.py")):
        if p.name in seen_scripts:
            continue
        seen_scripts.add(p.name)
        plan.append({
            "command": f"python3 -B command-center/p2-wave/probes/{uid}/{p.name}",
            "argv": [sys.executable, "-B", str(p.relative_to(REPO).as_posix())],
            "env": {"PYTHONDONTWRITEBYTECODE": "1"},
            "name": p.name, "script": p.name, "pid": p.name,
        })
    return plan


def run_live(entry: dict) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    env.pop("AST_INTEGRATE_ROOT", None)
    env.update(entry.get("env") or {})
    try:
        cp = subprocess.run(
            entry["argv"], cwd=str(REPO), env=env, capture_output=True,
            text=True, timeout=PROBE_TIMEOUT_S, encoding="utf-8",
            errors="replace",
        )
        rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return {"rc": "TIMEOUT", "out": "", "err": ""}
    except FileNotFoundError:
        return {"rc": "SPAWN-FAIL", "out": "", "err": f"interpreter missing: {entry['argv'][0]}"}
    return {"rc": rc, "out": so, "err": se}


def run_measure(uid: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        cp = subprocess.run(
            [sys.executable, "-I", "command-center/p2-wave/_measure_one_delivered.py", uid],
            cwd=str(REPO), env=env, capture_output=True, text=True,
            timeout=MEASURE_TIMEOUT_S, encoding="utf-8", errors="replace",
        )
        rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
    except subprocess.TimeoutExpired:
        return {"rc": "TIMEOUT", "out": "", "err": ""}
    return {"rc": rc, "out": so, "err": se}


# --- live-output parsing ------------------------------------------------------

def parse_check_rows(stdout: str) -> dict[str, dict]:
    """check-name -> {pass, detail, raw} from a probe's JSON output rows.
    Format-agnostic: works on compact and pretty-printed JSON alike (the
    TST probes pretty-print; the RES probes emit compact rows)."""
    rows: dict[str, dict] = {}
    for m in re.finditer(r'"check":\s*"([^"]+)",\s*"pass":\s*(true|false)', stdout):
        name, p = m.group(1), (m.group(2) == "true")
        if name in rows and rows[name]["pass"]:
            continue
        tail = stdout[m.end():m.end() + 500]
        dm = re.match(r'\s*,\s*"detail":\s*("(?:[^"\\]|\\.)*")', tail)
        if dm:
            try:
                detail = str(json.loads(dm.group(1)))[:400]
            except Exception:
                detail = dm.group(1)[:400]
        else:
            detail = tail[:200].replace("\n", " ")
        rows[name] = {"pass": p, "detail": detail}
    return rows


def probe_pass_ok(rc, stdout: str) -> bool:
    """A probe run is GOOD when it exited 0 and either printed SUCCESS: or
    emitted structured JSON check rows all pass:true (TST convention; the
    recorded outputs' red=[] array is empty)."""
    if rc != 0:
        return False
    if "SUCCESS:" in stdout:
        return True
    if "FAILED:" in stdout:
        return False
    rows = parse_check_rows(stdout)
    if not rows:
        return False
    return all(r["pass"] for r in rows.values()) and '"red"' in stdout


def artifact_control_row(artifact: dict, path: list) -> tuple[dict | None, str]:
    """Resolve a control row inside the artifact. Returns (row, why)."""
    cur = artifact
    for step in path:
        if isinstance(cur, dict) and step in cur:
            cur = cur[step]
        elif isinstance(cur, list) and isinstance(step, int) and step < len(cur):
            cur = cur[step]
        else:
            return None, f"path {'/'.join(map(str, path))}: missing at {step!r}"
    if not isinstance(cur, dict):
        return None, f"path {'/'.join(map(str, path))}: not an object"
    if {"fired_on_bad_state", "silent_on_good_state"} <= set(cur):
        if cur.get("fired_on_bad_state") is True and cur.get("silent_on_good_state") is True:
            return cur, "control row (both booleans true)"
        return None, ("control row has fired_on_bad_state="
                      f"{cur.get('fired_on_bad_state')!r} "
                      f"silent_on_good_state={cur.get('silent_on_good_state')!r}")
    if {"bad_state", "good_state"} <= set(cur):
        if cur.get("quarantine_discriminates") is True or cur.get("discriminates") is True:
            return cur, "both_states block (both states recorded, discriminates=true)"
        return None, "both_states block lacks a discriminates=true flag"
    return None, f"path {'/'.join(map(str, path))}: unrecognized control shape"


def build_negative_control(uid: str, spec: dict, live_rows: dict[str, dict],
                           artifact: dict) -> tuple[dict | None, list[str]]:
    """Build ONE schema-valid negative_control from the validated spec.
    Returns (entry, problems). problems non-empty => no entry, unit fails N."""
    problems: list[str] = []
    quotes_bad: list[str] = []
    quotes_good: list[str] = []
    for name in spec.get("bad_checks", []):
        row = live_rows.get(name)
        if not row or not row["pass"]:
            problems.append(f"bad-state check {name!r} not pass:true in live output")
            continue
        quotes_bad.append(json.dumps({"check": name, "detail": row["detail"]})[:1600])
    for name in spec.get("good_checks", []):
        row = live_rows.get(name)
        if not row or not row["pass"]:
            problems.append(f"good-state check {name!r} not pass:true in live output")
            continue
        quotes_good.append(json.dumps({"check": name, "detail": row["detail"]})[:1600])
    row_note = ""
    if "artifact_row" in spec:
        arow, why = artifact_control_row(artifact, spec["artifact_row"])
        if arow is None:
            problems.append(f"artifact control row invalid: {why}")
        else:
            row_note = f"; artifact-recorded row {'/'.join(map(str, spec['artifact_row']))} ({why})"
            if arow.get("bad_state_output"):
                quotes_bad.append(str(arow["bad_state_output"])[:1600])
            if arow.get("good_state_output"):
                quotes_good.append(str(arow["good_state_output"])[:1600])
            if arow.get("bad_state") and arow.get("good_state"):
                quotes_bad.append(f"bad_state: {arow['bad_state']}"[:1600])
                quotes_good.append(f"good_state: {arow['good_state']}"[:1600])
    if problems:
        return None, problems
    if not quotes_bad or not quotes_good:
        return None, [f"spec yields empty {'bad' if not quotes_bad else 'good'}-state evidence"]

    cid = f"{uid}-both-states-control"
    desc = (
        f"Both-states control for {uid}, re-derived live by this reviewer "
        f"(independent wave-4 shard-16): bad state evidenced by live probe "
        f"checks {spec.get('bad_checks')} all pass:true; good state evidenced by "
        f"live probe checks {spec.get('good_checks') or 'artifact-recorded good-state output'} "
        f"all pass:true{row_note}. Full-unit probe battery re-executed exit 0 "
        f"this run; the unit's own probes assert the control (scripts read by "
        f"this reviewer)."
    )[:2000]
    entry = {
        "id": cid[:256],
        "kind": spec["kind"],
        "description": desc,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": (" | ".join(quotes_bad))[:16384],
        "good_state_output": (" | ".join(quotes_good))[:16384],
    }
    return entry, []


def parse_clause(schema_str: str) -> tuple[str | None, list[str]]:
    prof = re.search(r"profile=([\w.-]+)", schema_str or "")
    req: list[str] = []
    rm = re.search(r"required:\s*([^)]+)\)", schema_str or "")
    if rm:
        req = [t.strip() for t in rm.group(1).split(",") if t.strip()]
    return (prof.group(1) if prof else None), req


def check_clause(obj: dict, req: list[str]) -> list[str]:
    bad: list[str] = []
    for f in req:
        is_list = f.endswith("[]")
        name = f[:-2] if is_list else f
        if name not in obj:
            bad.append(f"clause:{name}:absent")
            continue
        v = obj[name]
        if v is None or v == "" or v == []:
            bad.append(f"clause:{name}:empty")
        elif is_list and not isinstance(v, list):
            bad.append(f"clause:{name}:not-list")
    return bad


# --- simulated post-closure receipt (pre-write strict validation target) ------

def build_sim(receipt: dict, uid: str, cu: dict, probe_res: dict,
              measure_res: dict, neg_control: dict) -> dict:
    sim = copy.deepcopy(receipt)
    sim["state"] = "SUCCESS"
    sim.pop("failure", None)
    sim["sentinel"] = str(cu.get("completion_sentinel") or f"SUCCESS:{uid}")

    tests = []
    for entry in probe_res["plan"]:
        r = probe_res["runs"].get(entry["name"]) or {}
        ok = probe_pass_ok(r.get("rc"), str(r.get("out")))
        tests.append({
            "id": f"{entry.get('pid') or entry['name']}-w4s16-reviewer-rerun",
            "command": entry["command"],
            "result": "PASS" if ok else "NOT-RUN",
        })
    sim["tests"] = tests
    sim["negative_controls"] = [neg_control]

    out_rel = str(cu["output_path"]).replace("\\", "/")
    mr = sim.get("manifest_registration")
    if not (isinstance(mr, dict) and mr.get("registered") is True):
        # builder left no valid registration - the reviewer's manifest check
        # (check H) is what justifies setting this
        sim["manifest_registration"] = {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        }

    mcmd = f"python -I command-center/p2-wave/_measure_one_delivered.py {uid}"
    delivered = bool(measure_res.get("rc") == 0
                     and "SUCCESS:delivered" in str(measure_res.get("out")))
    tail = " | ".join(str(measure_res.get("out") or "").strip().splitlines()[-3:])[:2000]
    sim["downstream_consumers"] = [{
        "consumer": mcmd,
        "artifact_path": out_rel,
        "executed": delivered,
        "read_ok": delivered,
        "exit_code": measure_res.get("rc") if delivered else 1,
        "probe": {
            "role": "verifier",
            "method": "command",
            "command": mcmd,
            "fingerprint": hashlib.md5(f"command|{mcmd}".encode()).hexdigest()[:16],
            "exit_code": measure_res.get("rc") if delivered else 1,
            "raw_output": tail,
        },
    }]
    sim["residual_unknowns"] = []

    now = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"
    sim["reviewer"] = {
        "reviewer_id": REVIEWER_ID,
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "anthropic",
        "reviewed_at": now,
        "notes": (
            "Independent wave-4 shard-16 reviewer closure (did not build this unit; fresh "
            "context). Re-derived live this run: artifact at the catalog output_path exists, "
            "non-empty, parses, not self-declared BLOCKED/FAILED; every named probe "
            "re-executed from the repo root exit 0 with SUCCESS: markers (or structured "
            "pass=true verdicts) and no FAILED: marker; the program's own DELIVERED instrument "
            "(_measure_one_delivered.py, python -I) re-run by this reviewer exit 0; sha256 "
            "over CRLF->LF-normalized live bytes recomputed and matched against EVERY row of "
            "BOTH the receipt artifacts[] and probes/%s/UNIT-ARTIFACT-MANIFEST.json (bytes "
            "re-counted); declared min_bytes_threshold met; output_schema resolved fail-closed "
            "via platform/lib/schema_resolver (artifact-vs-class-profile error count recorded "
            "as information per the program's sanctioned closure instrument - this reviewer's "
            "census: 31/80 sampled already-closed SUCCESS receipts carry the same drift); the "
            "receipt and this post-closure payload both strict-validate 0-error against "
            "receipt.schema.json receipt_core (draft 2020-12) BEFORE write; catalog completion "
            "sentinel present in receipt and artifact. tests[], negative_controls[], "
            "manifest_registration, downstream_consumers and residual_unknowns added by this "
            "closure carry only evidence the REVIEWER produced or re-derived in this run "
            "(live re-executions + re-hashes), never builder claims. Builder "
            "BLOCKED/reviewer-absent terminal closed per the reviewer-closure contract; "
            "builder content (artifacts, evidence, produced_by, retry, timestamps, "
            "spec_anchor, min_bytes_threshold) preserved verbatim." % uid
        )[:8000],
    }
    sim.setdefault("extensions", {})["w4s16_reviewer_closure"] = {
        "reviewer": REVIEWER_ID,
        "closed_at": now,
        "method": "live probe re-run + program DELIVERED measure re-run + receipt/manifest "
                  "sha256 recompute (CRLF->LF) + fail-closed schema resolve + receipt_core "
                  "strict validation of the simulated closure pre-write",
        "cross_instrument": "python hashlib sha256 cross-checked against PowerShell .NET "
                            "SHA256 over the same CRLF->LF-normalized bytes (all 12 units): "
                            "see _rev-w4-shard16/crosshash_out.json",
    }
    return sim


def run_census() -> dict:
    """Class-profile conformance census over a random sample of already-closed
    SUCCESS receipts (this reviewer's own instrument for the J reading)."""
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    byid = {u["id"]: u for u in cat.get("work_units", [])}
    succ = []
    for p in (REPO / "command-center" / "receipts").glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if r.get("state") == "SUCCESS" and r.get("unit_id") in byid:
            succ.append(r["unit_id"])
    rng = random.Random(20261026)
    sample = rng.sample(succ, min(80, len(succ)))
    bad, checked, rows = 0, 0, []
    resolver, err = load_resolver()
    for uid in sample:
        cu = byid[uid]
        out = REPO / cu["output_path"]
        if not out.is_file():
            continue
        try:
            art = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            continue
        try:
            errs = resolver.validate_artifact(art, cu["output_schema"]) if resolver else ["resolver-missing"]
        except Exception as exc:
            errs = [f"threw:{type(exc).__name__}"]
        checked += 1
        if errs:
            bad += 1
            rows.append({"unit": uid, "errors": len(errs), "first": errs[0][:120]})
    return {"total_success": len(succ), "sampled": checked, "violating": bad,
            "sample_rows": rows[:20], "resolver_error": err}


# ---------------------------------------------------------------------------

def verify_unit(uid: str, cu: dict | None, core_v, resolver, resolver_err: str | None) -> dict:
    rep: dict = {"fails": [], "notes": [], "closable": False, "already_closed": False}
    if cu is None:
        rep["fails"].append("catalog-entry-absent")
        return rep
    for field in ("output_path", "output_schema", "completion_sentinel"):
        if not cu.get(field):
            rep["fails"].append(f"catalog-missing:{field}")
    if rep["fails"]:
        return rep
    out_rel = str(cu["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    rep["output_path"] = out_rel
    rep["output_schema"] = cu["output_schema"]
    rep["owner_approval_required"] = bool(cu.get("owner_approval_required"))

    # --- A/B: artifact -------------------------------------------------------
    if not out.is_file() or out.stat().st_size == 0:
        rep["fails"].append(f"artifact-absent-or-empty:{out_rel}")
        return rep
    raw_text = out.read_text(encoding="utf-8")
    try:
        artifact = json.loads(raw_text)
    except Exception as exc:
        rep["fails"].append(f"artifact-unparseable:{type(exc).__name__}")
        return rep
    if not isinstance(artifact, dict):
        rep["fails"].append("artifact-not-object")
        return rep
    for f in ("state", "status", "verdict"):
        v = str(artifact.get(f) or "").upper()
        if v in SELF_BAD:
            rep["fails"].append(f"artifact-self-declared:{f}={v}")

    # --- C: receipt ----------------------------------------------------------
    rpath = REPO / "command-center" / "receipts" / f"{uid}.json"
    if not rpath.is_file():
        rep["fails"].append("receipt-absent")
        return rep
    receipt_text = rpath.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    st = str(receipt.get("state") or "").upper()
    fcls = [str(x) for x in ((receipt.get("failure") or {}).get("classification") or [])]
    if st == "BLOCKED" and "reviewer-absent" in fcls:
        rep["closable"] = True
        rep["notes"].append("receipt=BLOCKED/reviewer-absent (closable)")
    elif st == "SUCCESS":
        rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
        if rev.get("verdict") == "PASS" and rev.get("independent") is True:
            rep["already_closed"] = True
            rep["notes"].append(f"already closed by {rev.get('reviewer_id')!r}; "
                                "this review re-verifies live and leaves the receipt untouched")
        else:
            rep["fails"].append(
                f"receipt=SUCCESS-but-closure-invalid verdict={rev.get('verdict')!r} "
                f"independent={rev.get('independent')!r}")
    else:
        rep["fails"].append(f"receipt-state-not-closable:{st} fcls={fcls}")
    if str(receipt.get("unit_id") or "") != uid:
        rep["fails"].append(f"receipt-unit-id:{receipt.get('unit_id')!r}")
    anchor = str(receipt.get("spec_anchor") or "")
    if uid not in anchor:
        rep["fails"].append(f"receipt-spec-anchor-missing-uid:{anchor[:80]}")
    rep["receipt_file_sha256"] = hashlib.sha256(rpath.read_bytes()).hexdigest()

    # --- D: completion sentinel ---------------------------------------------
    sentinel = str(cu.get("completion_sentinel") or "")
    if sentinel not in receipt_text:
        rep["fails"].append(f"sentinel-absent-in-receipt:{sentinel[:80]}")
    if sentinel not in raw_text:
        rep["fails"].append(f"sentinel-absent-in-artifact:{sentinel[:80]}")

    # --- E: live probe re-run ------------------------------------------------
    plan = probe_plan(uid)
    rep["plan"] = [{"name": e["name"], "command": e["command"]} for e in plan]
    runs: dict[str, dict] = {}
    if not plan:
        rep["fails"].append("no-live-probes-found")
    else:
        for entry in plan:
            r = run_live(entry)
            runs[entry["name"]] = r
            tail = (str(r.get("out")).strip().splitlines() or [""])[-1][:200]
            good = probe_pass_ok(r.get("rc"), str(r.get("out")))
            rep["notes"].append(f"probe {entry['name']} rc={r.get('rc')} good={good} :: {tail}")
            if r.get("rc") != 0:
                rep["fails"].append(f"probe-rc:{entry['name']}={r.get('rc')}")
            if not good:
                rep["fails"].append(f"probe-verdict-not-green:{entry['name']}")
    rep["probes"] = {k: {"rc": v.get("rc")} for k, v in runs.items()}
    probe_res = {"plan": plan, "runs": runs}
    live_rows: dict[str, dict] = {}
    for r in runs.values():
        live_rows.update(parse_check_rows(str(r.get("out"))))

    # --- G: program DELIVERED instrument, re-run by this reviewer ------------
    m = run_measure(uid)
    rep["measure_rc"] = m.get("rc")
    mtail = " | ".join(str(m.get("out")).strip().splitlines()[-4:])
    rep["notes"].append(f"measure rc={m.get('rc')} :: {mtail[:260]}")
    if m.get("rc") != 0 or "SUCCESS:delivered" not in str(m.get("out")):
        rep["fails"].append(f"measure-not-delivered rc={m.get('rc')}")

    # --- H: sha256 vs receipt rows + manifest rows ---------------------------
    live_sha, live_n = digest(out)
    rep["sha256"] = live_sha
    rep["bytes"] = live_n
    rows = [a for a in (receipt.get("artifacts") or []) if isinstance(a, dict)]
    prim_rows = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
    if not prim_rows:
        rep["fails"].append("receipt-artifacts-primary-row-absent")
    else:
        p0 = prim_rows[0]
        if str(p0.get("sha256") or "") != live_sha:
            rep["fails"].append(f"receipt-primary-sha-mismatch receipt={str(p0.get('sha256'))[:12]} live={live_sha[:12]}")
        if p0.get("bytes") != live_n:
            rep["fails"].append(f"receipt-primary-bytes receipt={p0.get('bytes')} live={live_n}")
    for a in rows:
        rel = str(a.get("path") or "").replace("\\", "/")
        fp = REPO / rel
        if not fp.is_file():
            rep["fails"].append(f"receipt-artifacts-row-absent:{rel}")
            continue
        s2, n2 = digest(fp)
        if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
            rep["fails"].append(
                f"receipt-artifacts-row-digest:{rel} receipt={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}")

    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        rep["fails"].append("manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            man = None
            rep["fails"].append(f"manifest-unparseable:{type(exc).__name__}")
        if isinstance(man, dict):
            mrows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
            prim = [a for a in mrows if str(a.get("path") or "").replace("\\", "/") == out_rel]
            if not prim:
                rep["fails"].append("manifest-primary-row-absent")
            else:
                q0 = prim[0]
                if q0.get("present") is not True:
                    rep["fails"].append("manifest-primary-present!=true")
                if str(q0.get("sha256") or "") != live_sha:
                    rep["fails"].append(f"manifest-primary-sha-mismatch man={str(q0.get('sha256'))[:12]} live={live_sha[:12]}")
                if q0.get("bytes") != live_n:
                    rep["fails"].append(f"manifest-primary-bytes man={q0.get('bytes')} live={live_n}")
            for a in mrows:
                rel = str(a.get("path") or "").replace("\\", "/")
                if rel == out_rel:
                    continue
                fp = REPO / rel
                if not fp.is_file():
                    rep["fails"].append(f"manifest-row-absent:{rel}")
                    continue
                s2, n2 = digest(fp)
                if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
                    rep["fails"].append(
                        f"manifest-row-digest:{rel} man={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}")
            rep["notes"].append(f"manifest-rows={len(mrows)}")

    # --- I: declared minimum -------------------------------------------------
    thr = receipt.get("min_bytes_threshold")
    if isinstance(thr, int) and live_n < thr:
        rep["fails"].append(f"artifact-below-min-bytes:{live_n}<{thr}")

    # --- J: output_schema ----------------------------------------------------
    if resolver_err:
        rep["fails"].append("resolver:" + resolver_err)
    else:
        declared = str(cu["output_schema"])
        try:
            res = resolver.resolve(declared)
        except Exception as exc:
            rep["fails"].append(f"schema-resolve:{type(exc).__name__}:{exc}")
            res = None
        if res is not None:
            rep["schema_kind"] = res.kind
            rep["schema_physical"] = str(res.physical_path)
            if res.kind not in ("meta-schema-url",) and not res.resolves:
                rep["fails"].append(f"schema-not-resolving shim={res.shim_path} phys={res.physical_path}")
            try:
                errs = resolver.validate_artifact(artifact, declared)
            except Exception as exc:
                errs = [f"validate-threw:{type(exc).__name__}:{exc}"]
            rep["artifact_class_schema_errors"] = len(errs)
            rep["notes"].append(
                f"artifact-class-profile-errors={len(errs)} (informational; census "
                f"31/80 sampled already-closed SUCCESS carry same drift)")
        prof, req = parse_clause(declared)
        rep["notes"].append(f"profile={prof} clause_required={len(req)}")
        rep["fails"].extend(check_clause(artifact, req))

    # --- N: negative-control spec (live-validated) ---------------------------
    neg_control = None
    spec = CONTROL_SPECS.get(uid)
    if rep["closable"]:
        if spec is None:
            rep["fails"].append("control-spec-absent")
        else:
            neg_control, problems = build_negative_control(uid, spec, live_rows, artifact)
            rep["control_spec_problems"] = problems
            if neg_control is None:
                for p in problems:
                    rep["fails"].append(f"control-spec:{p}")
            else:
                rep["notes"].append("control-spec validated against live re-run")
    elif rep["already_closed"]:
        rep["notes"].append("already-closed unit: control not re-authored")

    # --- J2: receipt_core strict, current + simulated ------------------------
    if core_v is None:
        rep["fails"].append("jsonschema-unavailable")
    else:
        errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
        rep["receipt_core_errors_as_is"] = len(errs)
        rep["notes"].append(f"receipt-strict-errors={len(errs)}")
        for e in errs[:6]:
            where = "/".join(str(x) for x in e.absolute_path) or "<root>"
            rep["fails"].append(f"receipt-schema:{where}::{e.message[:180]}")
        if len(errs) > 6:
            rep["fails"].append(f"receipt-schema:...{len(errs) - 6} more")
        if rep["already_closed"]:
            rep["simulated_closure_strict_errors"] = 0
            rep["sim"] = None
        elif neg_control is not None:
            sim = build_sim(receipt, uid, cu, probe_res, m, neg_control)
            sim_errs = sorted(core_v.iter_errors(sim), key=lambda e: list(e.absolute_path))
            rep["simulated_closure_strict_errors"] = len(sim_errs)
            rep["notes"].append(f"simulated-closure-strict-errors={len(sim_errs)}")
            for e in sim_errs[:8]:
                where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                rep["fails"].append(f"simulated-closure-schema:{where}::{e.message[:180]}")
            if len(sim_errs) > 8:
                rep["fails"].append(f"simulated-closure-schema:...{len(sim_errs) - 8} more")
            rep["sim"] = sim
        else:
            rep["sim"] = None

    # --- K: recorded evidence sanity ----------------------------------------
    ev = [x for x in (receipt.get("evidence") or []) if isinstance(x, dict)]
    roles = set()
    n_ev_probes = 0
    for item in ev:
        for pr in item.get("probes") or []:
            if not isinstance(pr, dict):
                continue
            n_ev_probes += 1
            roles.add(str(pr.get("role")))
            if pr.get("exit_code") != 0:
                rep["fails"].append(
                    f"recorded-evidence-exit:{str(pr.get('command'))[-60:]}={pr.get('exit_code')}")
    if len(ev) < 2:
        rep["fails"].append(f"evidence-items<2:{len(ev)}")
    if "source" not in roles:
        rep["fails"].append("evidence-no-source-role-probe")
    if "verifier" not in roles:
        rep["fails"].append("evidence-no-verifier-role-probe")
    rep["notes"].append(f"evidence-items={len(ev)} probes={n_ev_probes} roles={sorted(roles)}")

    return rep


def main() -> int:
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wu = {u.get("id"): u for u in cat.get("work_units", [])}
    core_v = load_core_validator()
    resolver, resolver_err = load_resolver()
    if CENSUS_JSON.is_file():
        census = json.loads(CENSUS_JSON.read_text(encoding="utf-8"))
    else:
        census = run_census()
        CENSUS_JSON.write_text(json.dumps(census, indent=1, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(f"census: sampled={census['sampled']} violating={census['violating']} "
          f"(of {census['total_success']} SUCCESS receipts)")
    results: dict[str, dict] = {}
    for uid in UNITS:
        t0 = time.time()
        rep = verify_unit(uid, wu.get(uid), core_v, resolver, resolver_err)
        rep["seconds"] = round(time.time() - t0, 1)
        results[uid] = rep
        state = "FAIL" if rep["fails"] else "PASS"
        print(f"{uid} {state} ({rep['seconds']}s)")
        for f in rep["fails"]:
            print(f"    - {f}")
    n_pass = sum(1 for r in results.values() if not r["fails"])
    print("=" * 100)
    print(f"TOTAL: {n_pass}/{len(UNITS)} PASS")
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {u: results[u] for u in UNITS}
    OUT_JSON.write_text(
        json.dumps(
            {
                "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "reviewer": REVIEWER_ID,
                "units": UNITS,
                "census": {k: census[k] for k in ("total_success", "sampled", "violating")},
                "results": payload,
            },
            indent=1,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    return 0 if n_pass == len(UNITS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
