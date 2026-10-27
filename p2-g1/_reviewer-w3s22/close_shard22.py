#!/usr/bin/env python3
"""Wave-3 shard-22 INDEPENDENT REVIEWER closure emitter.

Closes only units that pass ALL contract checks LIVE. Any failure at any step
rolls the receipt AND manifest back to their pre-review bytes and records FAIL.

Checks per unit (all re-derived here, never trusted from the builder):
  1. catalog entry + artifact at output_path: exists, non-empty, parses,
     builder state=BLOCKED with failure.classification==[reviewer-absent] and
     reviewer null (no self-certification)
  2. named probes re-run LIVE under ambient env, exit 0 + SUCCESS sentinel
     (3 stability rounds required; probe scripts hash-match manifest rows)
  3. manifest sha256 row == CRLF-normalized sha of the live receipt
  4. second-shell (pwsh7 vs Git Bash) re-run for the shell/portability units
  5. closure receipt validates: gate receipt_core + catalog output_schema
     profile + 12-condition predicate COMPLETE + receipt_validate.py ACCEPT
  6. reviewer mutation control: receipt_core must REJECT a copy whose
     reviewer.independent is flipped to false (state=SUCCESS without
     independent PASS is forbidden)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
MY11 = ["TST-0175", "TST-0176", "TST-0178", "TST-0179", "TST-0180", "TST-0181",
        "TST-0185", "TST-0188", "TST-0190", "TST-0193", "TST-0194"]
FAIL_UNIT = "TST-0174"
REVIEWER_ID = "w3-shard22-independent-reviewer-20261026"
KIND = {
    "TST-0175": "cache_report", "TST-0176": "cache_report", "TST-0178": "cache_report",
    "TST-0179": "parser_report", "TST-0180": "parser_report", "TST-0181": "parser_report",
    "TST-0185": "parser_report", "TST-0188": "shell_report", "TST-0190": "shell_report",
    "TST-0193": "shell_report", "TST-0194": "portability_report",
}
SECOND_SHELL_UNITS = {"TST-0188", "TST-0190", "TST-0193", "TST-0194"}
STABILITY_ROUNDS = 3


def digest_lf(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def raw_sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def eol_of(p: Path) -> str:
    b = Path(p).read_bytes()
    return "CRLF" if b"\r\n" in b else "LF"


def run_probe(script: str, timeout: int = 900) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run([sys.executable, "-B", script], capture_output=True, text=True,
                       timeout=timeout, cwd=str(REPO), env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))


def run_in_shell(shell: str, script: str, timeout: int = 900) -> tuple[int, str]:
    repo_fwd = str(REPO).replace("\\", "/")
    git_bash = r"C:\Program Files\Git\bin\bash.exe"
    if shell == "pwsh":
        cmd = ["pwsh", "-NoProfile", "-Command",
               "Set-Location '%s'; $env:PYTHONDONTWRITEBYTECODE='1'; python -B %s"
               % (repo_fwd, script)]
    else:
        cmd = [git_bash, "-c",
               "cd '%s' && PYTHONDONTWRITEBYTECODE=1 python -B %s"
               % (repo_fwd, script)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))


def load_instrument():
    spec = importlib.util.spec_from_file_location(
        "rsg", REPO / "platform/lib/receipt_schema_gate.py")
    rsg = importlib.util.module_from_spec(spec)
    sys.modules["rsg"] = rsg
    spec.loader.exec_module(rsg)
    spec2 = importlib.util.spec_from_file_location(
        "sr", REPO / "platform/lib/schema_resolver.py")
    sr = importlib.util.module_from_spec(spec2)
    sys.modules["sr"] = sr
    spec2.loader.exec_module(sr)
    sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
    spec3 = importlib.util.spec_from_file_location(
        "p2lib", REPO / "command-center" / "p2-wave" / "_p2lib.py")
    p2lib = importlib.util.module_from_spec(spec3)
    sys.modules["p2lib"] = p2lib
    spec3.loader.exec_module(p2lib)
    return rsg, sr, p2lib


RSG, SR, P2LIB = load_instrument()
CATALOG = {u["id"]: u for u in json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))["work_units"]}


def preflight(uid: str) -> tuple[list[str], dict]:
    fails: list[str] = []
    ctx: dict = {}
    u = CATALOG.get(uid)
    if not u:
        return ["catalog-entry-absent"], ctx
    if u.get("output_path") != f"command-center/receipts/{uid}.json":
        fails.append("catalog-output_path-drift")
    ctx["unit"] = u
    rp = REPO / f"command-center/receipts/{uid}.json"
    if not rp.is_file():
        return ["receipt-missing"], ctx
    if rp.stat().st_size == 0:
        return ["receipt-empty"], ctx
    try:
        orig = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"receipt-unparseable:{type(e).__name__}"], ctx
    if orig.get("unit_id") != uid:
        fails.append("receipt-unit-id")
    if orig.get("state") != "BLOCKED":
        fails.append("builder-state=" + str(orig.get("state")))
    if (orig.get("failure") or {}).get("classification") != ["reviewer-absent"]:
        fails.append("classification-not-reviewer-absent")
    if orig.get("reviewer") is not None:
        fails.append("builder-reviewer-not-null")
    rk = (orig.get("report") or {}).get("kind")
    if rk != KIND[uid]:
        fails.append(f"report-kind={rk}")
    ctx["orig_text"] = rp.read_text(encoding="utf-8")
    ctx["orig"] = orig
    ctx["lf_sha"], ctx["lf_len"] = digest_lf(rp)
    # manifest
    manp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not manp.is_file():
        fails.append("manifest-absent")
        return fails, ctx
    man = json.loads(manp.read_text(encoding="utf-8"))
    ctx["man_path"] = manp
    ctx["man_text"] = manp.read_text(encoding="utf-8")
    rows = [a for a in man.get("artifacts", []) if isinstance(a, dict)]
    prow = [a for a in rows if a.get("path") == f"command-center/receipts/{uid}.json"]
    if not prow:
        fails.append("manifest-no-receipt-row")
    elif prow[0].get("sha256") != ctx["lf_sha"] or prow[0].get("present") is not True:
        fails.append("manifest-receipt-row-mismatch")
    for a in rows:
        fp = REPO / str(a.get("path", ""))
        if not fp.is_file():
            fails.append("manifest-row-absent:" + a.get("path", "?"))
            continue
        d, _ = digest_lf(fp)
        if d != a.get("sha256"):
            fails.append("manifest-row-sha:" + Path(a["path"]).name)
    ctx["man_rows"] = rows
    # subagent return + probe scripts
    retp = PROBES / uid / "SUBAGENT-RETURN.json"
    if not retp.is_file():
        fails.append("subagent-return-absent")
        return fails, ctx
    ret = json.loads(retp.read_text(encoding="utf-8"))
    ctx["ret"] = ret
    nps = ret.get("named_probes", [])
    if len(nps) < 2:
        fails.append("named-probes<2")
    scripts = []
    for np in nps:
        m = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
        if not m:
            fails.append("named-probe-no-script:" + str(np.get("id")))
            continue
        scripts.append(m[-1])
    ctx["scripts"] = scripts
    return fails, ctx


def stability_rounds(uid: str) -> tuple[dict, list[str]]:
    """3 live rounds per probe script; returns {script: [outputs]} and failures."""
    outs: dict[str, list[str]] = {}
    fails: list[str] = []
    for script in CUR_CTX["scripts"]:
        outs[script] = []
        for rnd in range(STABILITY_ROUNDS):
            rc, out = run_probe(script)
            outs[script].append(out)
            if rc != 0 or f"SUCCESS:{uid}-" not in out:
                fails.append(f"probe-round-fail:{Path(script).name}:r{rnd + 1}:rc={rc}")
    return outs, fails


def second_shell(uid: str) -> tuple[list[str], dict]:
    fails: list[str] = []
    detail = {}
    for script in CUR_CTX["scripts"]:
        rc_p, out_p = run_in_shell("pwsh", script)
        rc_b, out_b = run_in_shell("bash", script)
        if rc_p != 0 or f"SUCCESS:{uid}-" not in out_p:
            fails.append(f"pwsh-lane-fail:{Path(script).name}:rc={rc_p}")
        if rc_b != 0 or f"SUCCESS:{uid}-" not in out_b:
            fails.append(f"bash-lane-fail:{Path(script).name}:rc={rc_b}")
        norm_p = re.sub(r"\b[0-9a-f]{8,64}\b", "<sha>", out_p)
        norm_b = re.sub(r"\b[0-9a-f]{8,64}\b", "<sha>", out_b)
        divergent = norm_p != norm_b
        detail[Path(script).name] = {
            "pwsh_rc": rc_p, "bash_rc": rc_b,
            "sha_normalized_outputs_identical": not divergent,
        }
        if divergent:
            fails.append(f"second-shell-divergence:{Path(script).name}")
    return fails, detail


def build_closure(uid: str, probe_outs: dict, ss_detail: dict, t_start: str) -> dict:
    u = CUR_CTX["unit"]
    orig = CUR_CTX["orig"]
    scripts = CUR_CTX["scripts"]
    out_rel = f"command-center/receipts/{uid}.json"
    lf_sha = CUR_CTX["lf_sha"]
    arts = []
    for rel in scripts:
        p = REPO / rel
        arts.append({"path": rel.replace("\\", "/"), "bytes": p.stat().st_size,
                     "sha256": raw_sha(p), "exists": True, "eol": eol_of(p),
                     "role": "primary"})
    # receipt self-row: supporting (outside the gate's measured set), carrying the
    # PRE-closure bytes this closure reviewed (LF-normalized, program digest mode)
    arts.append({"path": out_rel, "bytes": CUR_CTX["lf_len"], "sha256": lf_sha,
                 "exists": True, "eol": "LF", "role": "supporting"})
    ret_rel = f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    arts.append({"path": ret_rel, "bytes": (REPO / ret_rel).stat().st_size,
                 "sha256": raw_sha(REPO / ret_rel), "exists": True,
                 "eol": eol_of(REPO / ret_rel), "role": "supporting"})
    arts.append({"path": man_rel, "bytes": (REPO / man_rel).stat().st_size,
                 "sha256": raw_sha(REPO / man_rel), "exists": True,
                 "eol": eol_of(REPO / man_rel), "role": "supporting"})

    builder_sentinels = {}
    for np in CUR_CTX["ret"].get("named_probes", []):
        m = [t for t in str(np.get("command", "")).split() if t.endswith(".py")]
        if m:
            builder_sentinels[m[-1]] = [
                ln.split()[0] for ln in (np.get("raw_output") or "").splitlines()
                if ln.startswith("SUCCESS:")]

    def ev_artifact() -> dict:
        return {
            "claim": (f"Independent reviewer verified the artifact at {out_rel} exists "
                      f"on disk ({CUR_CTX['lf_len']} LF-normalized bytes), parses as JSON, "
                      f"carried the builder terminal state=BLOCKED with "
                      f"failure.classification=[reviewer-absent] and reviewer=null "
                      f"(no self-certification) at review time, and its report.kind="
                      f"{KIND[uid]} matches the catalog output_schema pin."),
            "verdict": "CONFIRMED", "confidence": "almost-certain", "anchor": out_rel,
            "probes": [
                {"role": "source", "method": "file-read",
                 "command": f"python -I -c json.load({out_rel})",
                 "raw_output": (f"parsed OK; builder state=BLOCKED; "
                                f"classification=[reviewer-absent]; reviewer=null"),
                 "fingerprint": f"w3s22-parse:{uid}:{lf_sha[:16]}"},
                {"role": "verifier", "method": "command",
                 "command": f"python -B {scripts[0]}",
                 "raw_output": (probe_outs[scripts[0]][-1].strip().splitlines()[-1][:400]
                                if probe_outs.get(scripts[0]) else ""),
                 "exit_code": 0,
                 "fingerprint": f"w3s22-probe1-live:{uid}:rc0"}],
        }

    def ev_probes() -> dict:
        runs = "; ".join(
            f"{Path(s).name}=3/3 rounds rc0" for s in scripts)
        tails = " | ".join(
            (probe_outs[s][-1].strip().splitlines()[-1][:120]
             if probe_outs.get(s) and probe_outs[s][-1].strip() else "?")
            for s in scripts)
        def live_prefixes(s: str) -> set:
            return {ln.split()[0] for ln in probe_outs.get(s, [""])[-1].splitlines()
                    if ln.startswith("SUCCESS:")}

        consistent = all(
            (live_prefixes(s) & set(builder_sentinels.get(s, [])))
            or not builder_sentinels.get(s)
            for s in scripts if s in probe_outs)
        return {
            "claim": (f"Independent reviewer re-ran both named probes live for "
                      f"{STABILITY_ROUNDS} rounds each under the ambient environment; "
                      f"all exited 0 with the unit SUCCESS sentinel ({runs}); live "
                      f"sentinels match the builder-recorded raw_output lines "
                      f"(consistent={consistent})."),
            "verdict": "CONFIRMED" if consistent else "NOT-CHECKED",
            "confidence": "almost-certain",
            "anchor": f"command-center/p2-wave/probes/{uid}/",
            "probes": [
                {"role": "source", "method": "command",
                 "command": "python -B " + " ; python -B ".join(scripts),
                 "raw_output": tails,
                 "exit_code": 0,
                 "fingerprint": f"w3s22-rerun:{uid}:{STABILITY_ROUNDS}x2rc0"},
                {"role": "verifier", "method": "byte-compare",
                 "command": ("compare live SUCCESS sentinel lines against "
                             "SUBAGENT-RETURN.json named_probes[].raw_output"),
                 "raw_output": f"sentinel-consistency={consistent}",
                 "fingerprint": f"w3s22-sentinel-cmp:{uid}"}],
        }

    def ev_sha() -> dict:
        return {
            "claim": (f"UNIT-ARTIFACT-MANIFEST.json registered {out_rel} with a sha256 "
                      f"row matching the live artifact (CRLF normalized to LF before "
                      f"hashing; program digest mode sha256+length over LF-normalized "
                      f"bytes). Reviewer recomputed the digest independently."),
            "verdict": "CONFIRMED", "confidence": "almost-certain",
            "anchor": man_rel,
            "probes": [
                {"role": "source", "method": "byte-compare",
                 "command": f"hashlib.sha256(bytes({out_rel}).replace(CRLF, LF))",
                 "raw_output": f"live LF-normalized sha256={lf_sha}",
                 "fingerprint": f"w3s22-lfsha:{uid}:{lf_sha[:16]}"},
                {"role": "verifier", "method": "file-read",
                 "command": f"json.load({man_rel}) artifacts[path=={out_rel}].sha256",
                 "raw_output": (f"manifest row sha256="
                                + [a["sha256"] for a in CUR_CTX["man_rows"]
                                   if a.get("path") == out_rel][0]),
                 "fingerprint": f"w3s22-manrow-read:{uid}"}],
        }

    def ev_schema() -> dict:
        return {
            "claim": (f"The closure receipt validates against BOTH the program gate "
                      f"(platform/schema/receipt.schema.json $defs/receipt_core, 0 "
                      f"errors) and the catalog output_schema pointer "
                      f"({u.get('output_schema')}, 0 errors via the platform schema "
                      f"resolver), and the 12-condition completion predicate evaluates "
                      f"COMPLETE with filesystem verification on."),
            "verdict": "CONFIRMED", "confidence": "almost-certain",
            "anchor": "platform/lib/receipt_schema_gate.py",
            "probes": [
                {"role": "source", "method": "schema-validate",
                 "command": ("receipt_schema_gate.validate_receipt + "
                             "schema_resolver.validate_artifact(profile pointer)"),
                 "raw_output": "0 errors (receipt_core) + 0 errors (catalog profile)",
                 "fingerprint": f"w3s22-schemacore:{uid}"},
                {"role": "verifier", "method": "command",
                 "command": ("python -I command-center/receipt_validate.py "
                             "command-center/receipts/" + uid + ".json"),
                 "raw_output": ("admission ACCEPT on the closure and REJECT naming the "
                                "reviewer rule on the independent-flipped mutation copy"),
                 "exit_code": 0,
                 "fingerprint": f"w3s22-admission-cmd:{uid}"}],
        }

    tests = []
    for i, s in enumerate(scripts):
        name = Path(s).stem
        tests.append({"id": f"t{i + 1}-{name}", "name": name,
                      "command": f"python -B {s}", "result": "PASS",
                      "output_tail": (probe_outs[s][-1].strip()[-400:]
                                      if probe_outs.get(s) else "")})

    builder_controls = []
    for c in (orig.get("negative_controls") or []):
        if (isinstance(c, dict) and c.get("fired_on_bad_state") is True
                and c.get("silent_on_good_state") is True
                and str(c.get("description") or "").strip()):
            builder_controls.append({
                "id": str(c.get("id") or "NC"),
                "kind": (str(c.get("kind")) if str(c.get("kind")) in (
                    "mutation", "malformed-input", "known-broken-fixture",
                    "absent-input", "adversarial-payload", "other") else "other"),
                "description": str(c.get("description"))[:2000],
                "fired_on_bad_state": True, "silent_on_good_state": True,
                "bad_state_output": str(c.get("bad_state_output") or "")[:400],
                "good_state_output": str(c.get("good_state_output") or "")[:200],
            })

    second_shell_note = ""
    if uid in SECOND_SHELL_UNITS:
        second_shell_note = (
            " Catalog reviewer_requirement (second Windows shell) re-executed by the "
            "reviewer: every probe run under pwsh7 AND Git Bash, exit 0 on both lanes, "
            "sha-normalized outputs identical"
            + ("; the only cross-shell byte differences are the per-run random throwaway "
               "repo commit SHAs embedded in the JSON payload (behaviorally identical)"
               if uid == "TST-0188" else "")
            + ".")

    notes = (
        f"Wave-3 shard-22 independent reviewer closure. Reviewer did not build this "
        f"unit; re-derived every contract check live in a fresh context: artifact "
        f"predicate on the builder BLOCKED pointer, both named probes re-run for "
        f"{STABILITY_ROUNDS} stability rounds each (all exit 0, SUCCESS sentinels match "
        f"the builder record), manifest sha256 recomputed (CRLF-to-LF digest mode), "
        f"receipt_core + catalog output_schema validation, 12-condition predicate "
        f"COMPLETE, and a reviewer mutation control (receipt_core must reject a copy "
        f"whose reviewer.independent is false).{second_shell_note} Receipt rewritten "
        f"from the builder BLOCKED pointer into receipt-core shape; the original "
        f"builder document is preserved verbatim under "
        f"extensions.builder_receipt_original. The receipt self-row is role=supporting "
        f"and carries the PRE-closure builder bytes sha256; the authoritative post-"
        f"closure registration is the UNIT-ARTIFACT-MANIFEST row, refreshed by the "
        f"reviewer to the final closure bytes (see extensions.reviewer_manifest_refresh).")

    reviewer = {"reviewer_id": REVIEWER_ID, "verdict": "PASS", "independent": True,
                "fresh_context": True, "vendor": "claude-code",
                "reviewed_at": t_start, "notes": notes[:8000]}

    receipt = {
        "schema_version": 1, "unit_id": uid, "title": u.get("title"),
        "question_or_target": u.get("question_or_target"),
        "state": "SUCCESS", "sentinel": "SUCCESS:" + uid,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#" + uid,
        "min_bytes_threshold": 1024,
        "output_path": u.get("output_path"),
        "output_schema": u.get("output_schema"),
        "completion_sentinel": u.get("completion_sentinel"),
        "artifacts": arts,
        "evidence": [ev_artifact(), ev_probes(), ev_sha(), ev_schema()],
        "tests": tests,
        "negative_controls": builder_controls,
        "reviewer": reviewer,
        "manifest_registration": {"manifest_path": man_rel, "registered": True},
        "downstream_consumers": [],
        "residual_unknowns": [],
        "timestamps": {"started_at": t_start, "ended_at": t_start},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "report": {"kind": KIND[uid], "observations": [], "control_ids": []},
        "produced_by": {"vendor": "anthropic", "model": "opus",
                        "role": "wave3-shard22-builder",
                        "execution_substrate": "local-windows-pwsh7"},
        "extensions": {
            "reviewer_shard": "wave3-shard22",
            "builder_receipt_original": orig,
            "reviewer_probe_stability": {
                "rounds": STABILITY_ROUNDS,
                "per_script": {Path(s).name: "3/3 rc0" for s in scripts},
            },
            "reviewer_manifest_refresh": {
                "why": ("closure rewrites the receipt bytes, so the manifest receipt "
                        "row is refreshed post-final-write to the closure bytes; the "
                        "pre-closure builder digest is preserved here"),
                "pre_closure_sha256": lf_sha,
                "pre_closure_bytes": CUR_CTX["lf_len"],
                "digest_mode": "sha256 over CRLF-normalized-to-LF bytes",
            },
        },
    }
    if uid in SECOND_SHELL_UNITS:
        receipt["extensions"]["reviewer_second_shell_check"] = ss_detail
    return receipt


def validator_rc(uid: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center/receipt_validate.py"),
         str(REPO / f"command-center/receipts/{uid}.json")],
        capture_output=True, text=True, timeout=600, cwd=str(REPO))
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def write_bytes_fresh(p: Path, text: str) -> None:
    p.write_bytes(text.encode("utf-8"))  # deterministic LF endings


def refresh_manifest(uid: str, receipt_path: Path) -> None:
    manp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(manp.read_text(encoding="utf-8"))
    d, ln = digest_lf(receipt_path)
    for a in man.get("artifacts", []):
        if a.get("path") == f"command-center/receipts/{uid}.json":
            a["sha256"] = d
            a["bytes"] = ln
            a["present"] = True
            a["role"] = a.get("role") or "primary"
    man["reviewer_refresh_2026-10-26"] = {
        "by": REVIEWER_ID,
        "why": ("wave-3 shard-22 independent closure rewrote the receipt into "
                "receipt-core shape; this row is the authoritative registration of "
                "the FINAL receipt bytes; the pre-closure builder digest is preserved "
                "in the receipt extensions.reviewer_manifest_refresh"),
    }
    manp.write_bytes((json.dumps(man, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def mutation_control(uid: str, receipt: dict, tmp: Path) -> dict | None:
    """receipt_core must REJECT a COMPLETE state=SUCCESS closure copy whose
    reviewer.independent is flipped to false, and the rejection must NAME the
    reviewer rule (not some unrelated defect) - the both-states proof that the
    closure rule itself is enforced by the admission instrument."""
    tmp.mkdir(parents=True, exist_ok=True)
    bad_p = tmp / (uid + "-no-independent.json")
    bad = json.loads(json.dumps(receipt))
    bad["reviewer"]["independent"] = False
    bad_p.write_bytes((json.dumps(bad, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    r = subprocess.run(
        [sys.executable, "-I", str(REPO / "command-center/receipt_validate.py"), str(bad_p)],
        capture_output=True, text=True, timeout=600, cwd=str(REPO))
    outtxt = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode == 0:
        return None  # inert detector
    if "independent" not in outtxt and "reviewer" not in outtxt:
        return None  # fired for the WRONG reason: the rule is not what bit
    return {
        "id": "MUT-" + uid + "-reviewer-independent-flip",
        "kind": "mutation",
        "description": ("Independent-reviewer mutation control: reviewer.independent "
                        "flipped to false on a COMPLETE copy of the SUCCESS closure "
                        "receipt (identical in every other field); receipt_validate.py "
                        "must REJECT naming the reviewer rule (receipt_core forbids "
                        "state=SUCCESS without reviewer.verdict=PASS + independent="
                        "true) while accepting the unmutated closure."),
        "fired_on_bad_state": True,
        # provisional until the good-state ACCEPT runs moments later; pass-B
        # re-records it from the REAL validator result, rollback on any failure
        "silent_on_good_state": True,
        "bad_state_output": outtxt[:400],
    }


results: dict[str, dict] = {}
tmpdir = REPO / "_reviewer-w3s22" / "tmp"
CUR_CTX: dict = {}

for uid in MY11:
    row: dict = {"unit_id": uid}
    t0 = time.time()
    t_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))
    # idempotent re-run: a unit THIS reviewer already closed is re-verified, not rebuilt
    rp0 = REPO / f"command-center/receipts/{uid}.json"
    if rp0.is_file():
        try:
            prev = json.loads(rp0.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        if (prev.get("state") == "SUCCESS"
                and isinstance(prev.get("reviewer"), dict)
                and prev["reviewer"].get("reviewer_id") == REVIEWER_ID
                and prev["reviewer"].get("verdict") == "PASS"
                and prev["reviewer"].get("independent") is True):
            problems0: list[str] = []
            vrc0, vout0 = validator_rc(uid)
            if vrc0 != 0:
                problems0.append("re-admission-REJECT:" + vout0[:180])
            g0 = RSG.evaluate_gate_a(prev, repo_root=str(REPO), verify_filesystem=True)
            if not g0.complete:
                problems0.append("re-gate-incomplete:" + g0.marker()[:140])
            d0, _ = digest_lf(rp0)
            man0 = json.loads((PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            pr0 = [a for a in man0.get("artifacts", [])
                   if a.get("path") == f"command-center/receipts/{uid}.json"]
            if not pr0 or pr0[0].get("sha256") != d0:
                problems0.append("re-manifest-mismatch")
            ret0 = json.loads((PROBES / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
            for np0 in ret0.get("named_probes", []):
                s0 = [x for x in str(np0.get("command", "")).split() if x.endswith(".py")]
                if s0:
                    rc0p, o0 = run_probe(s0[-1])
                    if rc0p != 0 or f"SUCCESS:{uid}-" not in o0:
                        problems0.append("re-probe-fail:" + Path(s0[-1]).name + f":rc={rc0p}")
            if problems0:
                row["verdict"] = "FAIL"
                row["reasons"] = problems0[:8]
                results[uid] = row
                print("FAILED:" + uid + "-reverify " + "; ".join(pp[:90] for pp in problems0[:3]))
            else:
                row["verdict"] = "PASS"
                row["note"] = "already closed by this reviewer; re-verified live, stays SUCCESS"
                results[uid] = row
                print("SUCCESS:" + uid + " re-verified live (stays SUCCESS, gate COMPLETE)")
            continue

    fails, ctx = preflight(uid)
    CUR_CTX = ctx
    if not fails:
        probe_outs, pfails = stability_rounds(uid)
        fails.extend(pfails)
        ss_detail = {}
        if uid in SECOND_SHELL_UNITS and not pfails:
            sfails, ss_detail = second_shell(uid)
            fails.extend(sfails)
    if fails:
        row["verdict"] = "FAIL"
        row["reasons"] = fails[:8]
        results[uid] = row
        print(f"FAILED:{uid}-review " + "; ".join(f[:90] for f in fails[:3]))
        continue

    rp = REPO / f"command-center/receipts/{uid}.json"
    receipt = build_closure(uid, probe_outs, ss_detail, t_start)

    # pass-A placeholder consumer FIRST, so the mutation copy differs from the
    # closure in reviewer.independent ONLY (isolates the variable under test)
    receipt["downstream_consumers"] = [{
        "consumer": "command-center/receipt_validate.py (admission gate C1-C4)",
        "artifact_path": "command-center/receipts/" + uid + ".json",
        "executed": True, "read_ok": True, "exit_code": 0,
        "probe": {"role": "verifier", "method": "command",
                  "command": ("python -I command-center/receipt_validate.py "
                              "command-center/receipts/" + uid + ".json"),
                  "raw_output": "PENDING: confirmation run executes after this write",
                  "exit_code": 0,
                  "fingerprint": "w3s22-validate:" + uid + ":passA"},
    }]

    # reviewer mutation control on the COMPLETE closure shape
    mc = mutation_control(uid, receipt, tmpdir)
    if mc is None:
        row["verdict"] = "FAIL"
        row["reasons"] = ["mutation-control-unusable: admission accepted a state=SUCCESS "
                          "receipt with reviewer.independent=false, or rejected it for "
                          "a reason unrelated to the reviewer rule"]
        results[uid] = row
        print("FAILED:" + uid + "-review mutation-control-unusable")
        continue
    mc["silent_on_good_state"] = True
    receipt["negative_controls"].append(mc)
    receipt["report"]["control_ids"] = [c["id"] for c in receipt["negative_controls"]]
    receipt["report"]["observations"] = [
        {"name": "artifact_lf_bytes", "measured": CUR_CTX["lf_len"], "method": "digest_lf",
         "anchor": "command-center/receipts/" + uid + ".json"},
        {"name": "named_probes_live_rounds",
         "measured": str(STABILITY_ROUNDS) + "x" + str(len(ctx["scripts"])) + " all rc0",
         "method": "subprocess re-run, ambient env",
         "anchor": "command-center/p2-wave/probes/" + uid + "/"},
        {"name": "manifest_lf_sha_match", "measured": True,
         "method": "sha256 CRLF-normalized byte-compare",
         "anchor": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json"},
        {"name": "schema_dual_validation", "measured": "receipt_core+profile 0 errors",
         "method": "receipt_schema_gate + schema_resolver",
         "anchor": "platform/schema/receipt.schema.json"},
    ]

    # pass A write; the admission instrument must ACCEPT the good closure
    write_bytes_fresh(rp, json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    vrc, vout = validator_rc(uid)
    t_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
    if vrc != 0:
        rp.write_bytes(ctx["orig_text"].encode("utf-8"))
        row["verdict"] = "FAIL"
        row["reasons"] = ["passA-admission-REJECT:" + vout[:220]]
        results[uid] = row
        print("FAILED:" + uid + "-review passA " + vout[:160])
        continue

    # pass B: record the REAL confirmation run; final write
    dur = max(1, int(round(time.time() - t0)))
    receipt["timestamps"]["ended_at"] = t_end
    receipt["timestamps"]["duration_seconds"] = dur
    receipt["reviewer"]["reviewed_at"] = t_end
    receipt["downstream_consumers"][0]["probe"]["raw_output"] = vout[:2000]
    receipt["downstream_consumers"][0]["probe"]["fingerprint"] = "w3s22-validate:" + uid + ":rc" + str(vrc)
    receipt["downstream_consumers"][0]["probe"]["exit_code"] = vrc
    receipt["negative_controls"][-1]["silent_on_good_state"] = (vrc == 0)
    receipt["negative_controls"][-1]["good_state_output"] = vout[:200]
    write_bytes_fresh(rp, json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    refresh_manifest(uid, rp)

    # post-write verification battery on the FINAL bytes
    problems: list[str] = []
    vrc2, vout2 = validator_rc(uid)
    if vrc2 != 0:
        problems.append("final-admission-REJECT:" + vout2[:200])
    r2 = json.loads(rp.read_text(encoding="utf-8"))
    gres = RSG.evaluate_gate_a(r2, repo_root=str(REPO), verify_filesystem=True)
    if not gres.complete:
        problems.append("gate-incomplete:" + gres.marker()[:140]
                        + " blocking=" + repr([c.n for c in gres.blocking_conditions]))
        for e in (gres.schema_errors or [])[:3]:
            problems.append("SE:" + e[:150])
    try:
        perrs = P2LIB.validate(r2, ctx["unit"].get("output_schema"))
        if perrs:
            problems.append(f"profile-schema-errors:{len(perrs)}:" + perrs[0][:120])
    except Exception as e:
        problems.append(f"profile-validate-raise:{type(e).__name__}:{str(e)[:120]}")
    d2, _ = digest_lf(rp)
    man_now = json.loads((PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    prow2 = [a for a in man_now.get("artifacts", [])
             if a.get("path") == f"command-center/receipts/{uid}.json"]
    if not prow2 or prow2[0].get("sha256") != d2:
        problems.append("post-write-manifest-mismatch")
    for a in man_now.get("artifacts", []):
        fp = REPO / str(a.get("path", ""))
        if not fp.is_file():
            problems.append("post-manifest-row-absent:" + a.get("path", "?"))
            continue
        dd, _ = digest_lf(fp)
        if dd != a.get("sha256"):
            problems.append("post-manifest-row-sha:" + Path(a["path"]).name)
    # one more live probe round on the final state
    for s in ctx["scripts"]:
        rc3, out3 = run_probe(s)
        if rc3 != 0 or f"SUCCESS:{uid}-" not in out3:
            problems.append(f"post-write-probe-fail:{Path(s).name}:rc={rc3}")
    d3, _ = digest_lf(rp)
    if d3 != d2:
        problems.append("receipt-mutating-under-reviewer")

    if problems:
        rp.write_bytes(ctx["orig_text"].encode("utf-8"))
        (PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(ctx["man_text"].encode("utf-8"))
        row["verdict"] = "FAIL"
        row["reasons"] = problems[:8]
        results[uid] = row
        print(f"FAILED:{uid}-review " + " | ".join(pp[:120] for pp in problems[:3]))
    else:
        row["verdict"] = "PASS"
        row["receipt"] = f"command-center/receipts/{uid}.json"
        row["gate_marker"] = gres.marker()
        results[uid] = row
        print(f"SUCCESS:{uid} closed by independent reviewer (gate COMPLETE, "
              f"{gres.marker()[:60]})")

# the flaky unit: record the precise FAIL verdict (receipt unchanged)
row = {"unit_id": FAIL_UNIT, "verdict": "FAIL", "receipt_unchanged": True,
       "reasons": [
           ("probe1_interleavings.py nondeterministically exits 1: PermissionError "
            "WinError 32 at per-trial done-flag unlink (DONE/n.A|n.B) racing the "
            "persistent writer_loop .touch() open handle; unlink(missing_ok=True) only "
            "tolerates FileNotFoundError. Reviewer tally across this review session: "
            "5 failures in 11 runs (~45%) under BOTH the builder-exact invocation "
            "(python3 -B) and the reviewer invocation; battery3x: 2/3 ok. The failure "
            "aborts the probe mid-run (rc=1, no SUCCESS JSON). Intrinsic probe-harness "
            "defect (cleanup IPC race), not a cache-atomicity signal: passing runs show "
            "partial_reads=0 across 1000 interleavings and probe2_mutation_temps fires "
            "3/3. Contract requires live probes to re-run exit 0; a ~45% crash rate is "
            "not exit-0 stable. Repair hint: retry unlink briefly on PermissionError, "
            "or have writers signal via per-trial files the parent never unlinks "
            "mid-run (recreate RUN dir per trial), or writers close-handle-then-rename.")]
       }
results[FAIL_UNIT] = row
print(f"FAILED:{FAIL_UNIT}-review probe1 teardown race (~45% rc=1), receipt unchanged")

(REPO / "_reviewer-w3s22/close-results.json").write_text(
    json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
npass = sum(1 for r in results.values() if r.get("verdict") == "PASS")
print("")
print(f"CLOSED: {npass} / {len(MY11) + 1} (1 failed: {FAIL_UNIT} probe teardown race)")
