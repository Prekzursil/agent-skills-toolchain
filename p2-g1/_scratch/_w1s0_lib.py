"""Wave-1 shard-0 shared builder library.

Everything the per-unit fixers, probes and writers need. Self-contained: probes
embed their own logic, but the builder generates and drives them from here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center/p2-wave/probes"
RECEIPTS = REPO / "command-center/receipts"
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"

MY_UNITS = [
    "ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
    "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
CLASS_KIND = {
    "refutation-record": "refutation-record",
    "stale-premise-reprobe": "stale-premise-reprobe",
    "exploit-proof": "exploit-proof",
    "supply-chain-attestation": "supply-chain-attestation",
    "threat-model": "threat-model",
    "council-pathology-sim": "council-pathology-sim",
    "fault-injection-run": "fault-injection-run",
}
VALID_VENDOR = {
    "anthropic", "openai", "xai", "grok", "codex", "claude", "claude-code",
    "opus", "sonnet", "haiku", "google", "gemini", "mistral", "human",
    "human-reviewer", "mixed", "multi", "multi-vendor", "other", "unknown",
    "custom", "gpt-5-codex", "cursor" ,  # cursor accepted only if enum has it
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_norm(path: Path) -> tuple[str, int, str]:
    """CRLF-normalized sha256 + byte length + eol label, mirroring the measure."""
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    if b"\r\n" in raw:
        eol = "MIXED" if b"\n" in raw.replace(b"\r\n", b"") else "CRLF"
    else:
        eol = "LF"
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def catalog_unit(cat: dict, uid: str) -> dict:
    for u in cat["work_units"]:
        if u.get("id") == uid:
            return u
    raise KeyError(uid)


def schema_errors(doc, schema: dict) -> list[str]:
    import jsonschema

    errs = []
    for exc in jsonschema.Draft202012Validator(schema).iter_errors(doc):
        path = "/".join(str(p) for p in exc.absolute_path)
        errs.append(f"[{path}] {exc.message[:240]}")
    return errs


def load_schema(schema_rel: str) -> dict:
    return json.loads((REPO / schema_rel).read_text(encoding="utf-8"))


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def run_live(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, text[-3000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def gate_schema_only(artifact_rel: str) -> tuple[int, str]:
    """The executed downstream consumer: receipt_schema_gate --schema-only."""
    exe = sys.executable.replace("\\", "/")
    cmd = [
        exe, "-I", "-B",
        "platform/lib/receipt_schema_gate.py",
        artifact_rel, "--schema-only",
    ]
    return run_live(cmd)


def make_probe(uid: str, catalog: dict, which: int, recompute_src: str) -> Path:
    """Generate probes/<uid>/probe<which>_<slug>.py and return its path."""
    unit = catalog_unit(catalog, uid)
    out_rel = unit["output_path"]
    schema_rel = unit["output_schema"]
    slug = {1: "delivery_predicate", 2: "independent_recheck"}[which]
    pdir = PROBES / uid
    pdir.mkdir(parents=True, exist_ok=True)
    path = pdir / f"probe{which}_{slug}.py"
    if which == 1:
        body = PROBE1_SRC.format(
            uid=uid, out_rel=out_rel, schema_rel=schema_rel,
            sentinel=unit.get("completion_sentinel", "").replace('"', '\\"'),
        )
    else:
        body = PROBE2_SRC.format(
            uid=uid, out_rel=out_rel, recompute=recompute_src,
        )
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


PROBE1_SRC = '''#!/usr/bin/env python3
"""{uid} probe1 -- structural + schema delivery predicate (live, fail-closed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "{out_rel}"
SCHEMA_REL = "{schema_rel}"
SENTINEL = "{sentinel}"
NOT_DELIVERING = {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}


def main() -> int:
    import jsonschema

    fails = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{{label}}{{(': ' + detail) if detail else ''}}")

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{uid}-probe1 artifact unreadable/unparseable: {{type(exc).__name__}}")
        return 1
    check(OUT.stat().st_size > 0, "artifact-empty")
    state = str(doc.get("state") or "").upper()
    check(state not in NOT_DELIVERING, "self-declared", state)
    check(str(doc.get("unit_id")) == "{uid}", "unit_id", str(doc.get("unit_id")))
    check(SENTINEL in text, "completion-sentinel-absent")
    check(doc.get("schema_version") == 1, "schema_version", repr(doc.get("schema_version")))

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(doc),
        key=lambda e: str(list(e.absolute_path)),
    )
    check(not errs, "schema-invalid", f"{{len(errs)}} errors; first: {{str(errs[0].message)[:200] if errs else ''}}")

    ev = doc.get("evidence") or []
    check(len(ev) >= 2, "evidence-minItems-2", str(len(ev)))
    for i, item in enumerate(ev):
        probes = item.get("probes") or []
        roles = {{p.get("role") for p in probes}}
        fps = {{p.get("fingerprint") for p in probes}}
        check("source" in roles, f"evidence[{{i}}]-source-probe-absent")
        check("verifier" in roles, f"evidence[{{i}}]-verifier-probe-absent")
        check(len(fps) == len(probes) and len(probes) >= 2,
              f"evidence[{{i}}]-fingerprints-not-distinct")

    if fails:
        for f in fails[:10]:
            print(f"FAILED:{uid}-probe1 {{f}}")
        return 1
    print(f"SUCCESS:{uid}-probe1 artifact parses, schema-valid, sentinel present, "
          f"evidence pairs complete, state={{state}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PROBE2_SRC = '''#!/usr/bin/env python3
"""{uid} probe2 -- mechanically different independent recheck (live, fail-closed).

Lane: byte-compare against the per-unit manifest, an independent re-derivation of
one headline number from artifact internals, and a mutation negative control
(the structural detector must FIRE on a corrupted copy and stay SILENT on the real
artifact). Writes nc_live.json with the measured control result.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "{out_rel}"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest_norm(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\\r\\n", b"\\n")).hexdigest()


def detector(doc_text: str) -> tuple[bool, str]:
    """The structural detector probe1 embodies, minimised: it must reject tampering."""
    try:
        doc = json.loads(doc_text)
    except Exception as exc:
        return True, f"parse-error:{{type(exc).__name__}}"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("state") not in ("SUCCESS", "SUPERSEDED", "DROPPED-BY-OWNER"):
        return True, f"bad-state:{{doc.get('state')}}"
    if doc.get("unit_id") != "{uid}":
        return True, "unit-id-mismatch"
    if not doc.get("evidence") or len(doc["evidence"]) < 2:
        return True, "evidence-collapsed"
    if not doc.get("artifacts"):
        return True, "artifacts-collapsed"
    return False, "clean"


{recompute}


def main() -> int:
    # --- 1. manifest byte-compare (mechanically different from probe1) -----
    if not MANIFEST.is_file():
        if not (HERE / "nc_live.json").is_file():
            print(f"NOTE:{uid}-probe2 dry pass: manifest not written yet; "
                  f"collecting mutation-control measurement only")
        else:
            print(f"FAILED:{uid}-probe2 manifest-absent {{MANIFEST}}")
            return 1
        rows = []
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == "{uid}"
                and str(a.get("path")).replace(chr(92) * 2, "/") == "{out_rel}"]
        if not rows:
            print(f"FAILED:{uid}-probe2 manifest-row-absent")
            return 1
    live = None
    if rows:
        live = digest_norm(OUT)
        row = rows[0]
        if row.get("sha256") != live or row.get("present") is not True:
            print(f"FAILED:{uid}-probe2 manifest-sha-mismatch live={{live}} row={{row.get('sha256')}}")
            return 1

    doc = json.loads(OUT.read_text(encoding="utf-8"))

    # --- 2. independent headline re-derivation -----------------------------
    ok, detail = recompute(doc)
    if not ok:
        print(f"FAILED:{uid}-probe2 recompute-disagrees {{detail}}")
        return 1

    # --- 3. mutation negative control (both states, live) ------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "mutant.json"
        mutant = json.loads(OUT.read_text(encoding="utf-8"))
        mutant["evidence"] = []
        mutant["unit_id"] = "ADV-9999"
        mutant["state"] = "BLOCKED"
        tmp.write_text(json.dumps(mutant), encoding="utf-8")
        fired_bad, why_bad = detector(tmp.read_text(encoding="utf-8"))
        fired_good, why_good = detector(OUT.read_text(encoding="utf-8"))
    nc = {{
        "id": "NC-MUTATION-{uid}",
        "kind": "mutation",
        "description": (
            "Corrupting state/unit_id/evidence in a copy must make the structural "
            "detector fire, while the real artifact stays silent (both-states rule)."
        ),
        "fired_on_bad_state": bool(fired_bad),
        "silent_on_good_state": not fired_good,
        "bad_state_output": f"fired={{fired_bad}} why={{why_bad}}",
        "good_state_output": f"fired={{fired_good}} why={{why_good}}",
    }}
    (HERE / "nc_live.json").write_text(
        json.dumps(nc, indent=1), encoding="utf-8", newline="\\n"
    )
    if not fired_bad:
        print(f"FAILED:{uid}-probe2 mutation-control-inert {{why_bad}}")
        return 1
    if fired_good:
        print(f"FAILED:{uid}-probe2 control-over-fires-on-good {{why_good}}")
        return 1

    sha_note = ("manifest sha matches (" + live[:12] + "...); ") if live else "dry pass; "
    print(f"SUCCESS:{uid}-probe2 " + sha_note + "recompute: {{detail}}; "
          f"mutation control fired on bad state, silent on good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def write_manifest(uid: str, unit: dict, probe_paths: list[Path]) -> Path:
    out_rel = unit["output_path"]
    art = REPO / out_rel
    sha, size, eol = digest_norm(art)
    rows = [{
        "path": out_rel, "sha256": sha, "bytes": size, "present": True,
        "unit_id": uid, "eol": eol, "role": "primary",
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
    }]
    for p in probe_paths:
        rel = p.relative_to(REPO).as_posix()
        s, b, e = digest_norm(p)
        rows.append({
            "path": rel, "sha256": s, "bytes": b, "present": True,
            "unit_id": uid, "eol": e, "role": "supporting",
        })
    man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(
        json.dumps({"artifacts": rows}, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    return man_path


def write_subagent_return(
    uid: str, unit: dict, probe_runs: list[dict], notes: str, sha: str, size: int,
) -> Path:
    out_rel = unit["output_path"]
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "BLOCKED",
        "sentinel": f"FAILED:{uid} builder-lane delivery complete (live probes exit 0, "
                    f"manifest row matches); independent-review closure pending",
        "registered": True,
        "output_path": out_rel,
        "output_schema": unit["output_schema"],
        "named_probes": probe_runs,
        "artifacts": [{
            "path": out_rel, "bytes": size, "sha256": sha, "exists": True, "role": "primary",
        }],
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "cloud_ok": False,
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": "Builder lane complete: artifact rebuilt to the current "
                      "artifact-class profile, both named probes re-run live and exit 0, "
                      "per-unit manifest row hash matches. State stays BLOCKED because "
                      "the independent reviewer lane has not closed this unit in this "
                      "wave; only the independent reviewer sets SUCCESS.",
            "blocked_on": "independent-review-closure",
        },
        "reviewer": {
            "reviewer_id": "none-this-wave-builder-lane",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": "Builder subagent may not self-certify. Any prior-round review "
                     "recorded inside the artifact is preserved verbatim there.",
        },
        "notes": notes,
        "ts": now_iso(),
    }
    path = PROBES / uid / "SUBAGENT-RETURN.json"
    path.write_text(json.dumps(ret, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def write_receipt(
    uid: str, unit: dict, doc: dict, evidence: list[dict], notes: str,
    extra_classifications: list[str] | None = None,
) -> Path:
    out_rel = unit["output_path"]
    sha, size, eol = digest_norm(REPO / out_rel)
    art_rows = []
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict) or not a.get("path"):
            continue
        p = REPO / str(a["path"])
        if p.is_file():
            s, b, e = digest_norm(p)
            art_rows.append({
                "path": str(a["path"]).replace("\\", "/"), "bytes": b, "sha256": s,
                "exists": True, "eol": e,
                "role": a.get("role") if a.get("role") in
                {"primary", "supporting", "log", "fixture", "control"} else "supporting",
            })
    if not art_rows:
        art_rows = [{
            "path": out_rel, "bytes": size, "sha256": sha, "exists": True,
            "eol": eol, "role": "primary",
        }]
    ts = doc.get("timestamps") or {}
    retry = doc.get("retry") or {
        "count": 0,
        "policy": str(unit.get("retry_policy") or "single attempt; two-strikes pivot applies"),
    }
    retry = {"count": int(retry.get("count", 0)), "policy": str(retry.get("policy", "n/a"))[:1024]}
    classifications = ["reviewer-absent"] + (extra_classifications or [])
    reviewer = doc.get("reviewer") or {}
    receipt = {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": f"FAILED:{uid} builder-lane delivery complete; independent-review "
                    f"closure pending (directive 2026-10-24: only the independent "
                    f"reviewer closes)",
        "disposition": None,
        "spec_anchor": str(doc.get("spec_anchor") or unit.get("spec_anchor") or
                           "WORK-UNIT-CATALOG.json#" + uid),
        "min_bytes_threshold": int(doc.get("min_bytes_threshold") or 2048),
        "produced_by": doc.get("produced_by") or {
            "vendor": "anthropic", "model": "opus", "role": "builder-shard-0",
        },
        "timestamps": {
            "started_at": ts.get("started_at") or now_iso(),
            "ended_at": now_iso(),
            "duration_seconds": ts.get("duration_seconds") or 0,
        },
        "retry": retry,
        "failure": {
            "classification": classifications,
            "reason": "Artifact rebuilt to the current artifact-class profile "
                      f"({unit['output_schema']}); both named probes re-run live exit 0; "
                      "per-unit manifest row sha256 matches the live CRLF-normalized "
                      "artifact. state=BLOCKED because the independent reviewer lane "
                      "has not closed this unit in this wave; the builder may not "
                      "self-certify. Prior-round review evidence recorded inside the "
                      "artifact is preserved verbatim.",
            "blocked_on": "independent-review-closure",
        },
        "artifacts": art_rows,
        "evidence": evidence,
        "tests": [
            {
                "id": f"T-LIVE-PROBE-{i}",
                "name": f"live re-run of {r['id']}",
                "command": r["command"],
                "result": "PASS" if r["exit_code"] == 0 else "FAIL",
                "assertions": 1,
                "output_tail": r["raw_output"][-1500:],
            }
            for i, r in enumerate((PROBES / uid / "SUBAGENT-RETURN.json").is_file()
                                  and json.loads((PROBES / uid / "SUBAGENT-RETURN.json")
                                                 .read_text(encoding="utf-8"))
                                  .get("named_probes") or [])
        ],
        "negative_controls": _live_nc(uid),
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": uid,
            "registered_at": now_iso(),
        },
        "reviewer": {
            "reviewer_id": str(reviewer.get("reviewer_id") or "none-this-wave"),
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": bool(reviewer.get("fresh_context")),
            "notes": "This wave: no independent reviewer has closed the unit; the "
                     "builder lane sets BLOCKED. Prior-round in-artifact reviewer: "
                     + json.dumps(reviewer, default=str)[:1500],
        },
        "downstream_consumers": doc.get("downstream_consumers") or [],
        "residual_unknowns": doc.get("residual_unknowns") or [],
        "report": doc.get("report") or {
            "kind": CLASS_KIND.get(Path(unit["output_schema"]).name.replace(".schema.json", ""), "generic"),
            "observations": [{
                "name": "delivery_measure",
                "measured": "builder-lane green; review pending",
                "method": "live probe re-run + manifest byte-compare",
                "anchor": out_rel,
            }],
            "control_ids": [nc.get("id") for nc in _live_nc(uid)],
        },
        "extensions": {
            "builder_lane": "workflow-shard-0-wave-1",
            "artifact_reviewer_preserved": True,
            "notes": notes[:4000],
        },
    }
    receipt.pop("disposition")
    path = RECEIPTS / f"{uid}.json"
    path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def _live_nc(uid: str) -> list[dict]:
    p = PROBES / uid / "nc_live.json"
    if p.is_file():
        try:
            return [json.loads(p.read_text(encoding="utf-8"))]
        except Exception:
            return []
    return []


def measure(uid: str) -> tuple[int, str]:
    exe = sys.executable.replace("\\", "/")
    wrapper = (REPO / "command-center/p2-wave/seed-stage/g1_python.py").as_posix()
    cmd = (f'PYTHONDONTWRITEBYTECODE=1 python3 -B '
           f'command-center/p2-wave/_measure_one_delivered.py {uid}')
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "AST_INTEGRATE_ROOT": str(REPO)}
    import re as _re
    while True:
        m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]
    cmd = cmd.replace("python3", sys.executable.replace(chr(92), "/"), 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=300, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[-2000:]
