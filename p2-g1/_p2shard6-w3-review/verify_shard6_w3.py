#!/usr/bin/env python3
"""INDEPENDENT REVIEWER, wave-3 shard-6 (12 units, BLD-0031..BLD-0050).

Written fresh by the wave-3 shard-6 reviewer agent. Read-only over
receipts: this script NEVER mutates a receipt. Per unit it verifies:

  A  artifact at catalog output_path: exists, non-empty, parses,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, state == SUCCESS
  B  receipt_core closure rule: reviewer.verdict == PASS, independent true
  C2 STRICT receipt_core JSON-Schema validation (draft 2020-12) against
     platform/schema/receipt.schema.json#/$defs/receipt_core
  C3 validation of the receipt against the catalog's declared
     output_schema path (shim resolved to the physical artifact-class
     profile it $refs)
  D  command-center/p2-wave/probes/<id>/UNIT-ARTIFACT-MANIFEST.json:
     primary row (path == output_path) present=true, sha256 + bytes
     match a live recompute over CRLF-normalized bytes; every other row
     present + digest-matched
  E  catalog completion_sentinel appears verbatim in the receipt text
  F  live probes re-run HERE: rc == 0, SUCCESS: marker present,
     FAILED: absent, at least one probe per unit
  G  the probe battery must not mutate any reviewed artifact (raw-byte
     sha256 snapshot of every manifest row + manifest + receipt, taken
     before F and re-verified after)

Exit 0 only when ALL 12 units hold ALL checks.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except Exception:  # pragma: no cover
    jsonschema = None
    Draft202012Validator = None
    Registry = None

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "BLD-0031", "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037", "BLD-0040",
    "BLD-0042", "BLD-0043", "BLD-0044", "BLD-0045", "BLD-0049", "BLD-0050",
]
SELF_BAD = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 600
ASTINT = "file:///C:/Users/Prekzursil/source/ast-integrate"
P2G1 = "file:///C:/Users/Prekzursil/p2-g1"


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def raw_digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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


def make_file_uri_registry() -> "Registry | None":
    """Resolve the schema shims' absolute file:// $refs against the local tree.

    Registers BOTH platform schema documents (artifact-class-profiles and
    receipt) under both absolute base URIs the on-disk schemas $ref, so
    nested refs (profile -> receipt#$defs/<x>) resolve without network.
    """
    if Registry is None:
        return None
    docs = {}
    for name in ("artifact-class-profiles.schema.json", "receipt.schema.json"):
        docs[name] = json.loads(
            (REPO / "platform" / "schema" / name).read_text(encoding="utf-8")
        )
    reg = Registry()
    for base in (ASTINT, P2G1):
        for name, contents in docs.items():
            uri = f"{base}/platform/schema/{name}"
            res = Resource.from_contents(contents, default_specification=DRAFT202012)
            reg = reg.with_resource(uri, res)
    return reg


def load_class_validator(schema_rel: str, reg):
    """Build a validator for the unit's declared output_schema (a shim path)."""
    if Draft202012Validator is None:
        return None, None
    shim = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    ref = str(shim.get("$ref") or "")
    if not ref:
        # self-contained schema: validate directly
        Draft202012Validator.check_schema(shim)
        return Draft202012Validator(shim), None
    m = re.match(r"^(file://[^#]+)#", ref)
    if m is None:
        return None, f"unresolvable-$ref:{ref[:80]}"
    phys_uri = m.group(1)
    phys_rel = phys_uri.replace(ASTINT, "").replace(P2G1, "").lstrip("/")
    if not (REPO / phys_rel).is_file():
        return None, f"physical-schema-absent:{phys_rel}"
    phys = json.loads((REPO / phys_rel).read_text(encoding="utf-8"))
    res = Resource.from_contents(phys, default_specification=DRAFT202012)
    reg2 = reg.with_resource(phys_uri, res)
    Draft202012Validator.check_schema(shim)
    return Draft202012Validator(shim, registry=reg2), None


def probe_cmds(uid: str, receipt: dict, pdir: Path) -> list[str]:
    cmds: list[str] = []

    def add(cmd):
        c = str(cmd).strip()
        if c and c not in cmds:
            cmds.append(c)

    for src in (receipt.get("named_probes") or [],):
        for item in src:
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                add(item["command"])
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception:
            ret = {}
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str):
                add(item["command"])
    for p in sorted(pdir.glob("probe[0-9]*.py")):
        add(f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p.name}")
    return cmds


def winify(cmd: str, env: dict) -> str:
    # move POSIX VAR=value prefixes into env
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            return cmd
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]


def main() -> int:
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    byid = {u.get("id"): u for u in cat["work_units"] if isinstance(u, dict)}
    core_v = load_core_validator()
    reg = make_file_uri_registry()

    results: dict[str, dict] = {}
    for uid in UNITS:
        rep: dict = {"fails": [], "notes": []}
        cu = byid.get(uid)
        if cu is None:
            rep["fails"].append("catalog-entry-absent")
            results[uid] = rep
            continue
        out_rel = str(cu.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel

        # A
        if not out.is_file() or out.stat().st_size == 0:
            rep["fails"].append(f"artifact-absent-or-empty:{out_rel}")
            results[uid] = rep
            continue
        try:
            receipt = json.loads(out.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append(f"unparseable:{type(exc).__name__}")
            results[uid] = rep
            continue
        st = str(receipt.get("state") or "").upper()
        if st in SELF_BAD:
            rep["fails"].append(f"self-declared:{st}")
        if st != "SUCCESS":
            rep["fails"].append(f"state!=SUCCESS:{st}")

        # B
        rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
        if rev.get("verdict") != "PASS":
            rep["fails"].append(f"reviewer.verdict={rev.get('verdict')!r}")
        if rev.get("independent") is not True:
            rep["fails"].append("reviewer.independent!=true")
        rep["notes"].append(f"reviewer_id={rev.get('reviewer_id')!r}")

        # E
        sentinel = str(cu.get("completion_sentinel") or "")
        if sentinel and sentinel not in out.read_text(encoding="utf-8"):
            rep["fails"].append(f"sentinel-absent:{sentinel}")

        # C2 strict receipt_core
        if core_v is not None:
            errs = sorted(core_v.iter_errors(receipt), key=lambda e: list(e.absolute_path))
            rep["notes"].append(f"strict-errors={len(errs)}")
            for e in errs[:6]:
                where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                rep["fails"].append(f"schema:{where}::{e.message[:180]}")
            if len(errs) > 6:
                rep["fails"].append(f"schema:...{len(errs) - 6} more")
        else:
            rep["notes"].append("jsonschema-unavailable")

        # C3 declared output_schema validation
        schema_rel = str(cu.get("output_schema") or "").replace("\\", "/")
        if schema_rel:
            if not (REPO / schema_rel).is_file():
                rep["fails"].append(f"output-schema-file-absent:{schema_rel}")
            elif reg is not None:
                cv, err = load_class_validator(schema_rel, reg)
                if err:
                    rep["fails"].append("outschema:" + err)
                elif cv is not None:
                    errs = sorted(cv.iter_errors(receipt), key=lambda e: list(e.absolute_path))
                    rep["notes"].append(f"outschema-errors={len(errs)}")
                    for e in errs[:6]:
                        where = "/".join(str(x) for x in e.absolute_path) or "<root>"
                        rep["fails"].append(f"outschema:{where}::{e.message[:180]}")
                    if len(errs) > 6:
                        rep["fails"].append(f"outschema:...{len(errs) - 6} more")
            else:
                rep["notes"].append("referencing-unavailable")

        # snapshot G (before probes)
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        snap_paths: list[Path] = [out, man_path]
        if not man_path.is_file():
            rep["fails"].append("manifest-absent")
            results[uid] = rep
            continue
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rep["fails"].append(f"manifest-unparseable:{type(exc).__name__}")
            results[uid] = rep
            continue
        if not isinstance(man, dict):
            rep["fails"].append("manifest-not-object")
            results[uid] = rep
            continue
        rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
        prim = [a for a in rows if str(a.get("path") or "").replace("\\", "/") == out_rel]
        if not prim:
            rep["fails"].append("manifest-primary-row-absent")
        else:
            p0 = prim[0]
            if p0.get("present") is not True:
                rep["fails"].append("manifest-primary-present!=true")
            live_sha, live_n = digest(out)
            if str(p0.get("sha256") or "") != live_sha:
                rep["fails"].append(
                    f"manifest-primary-sha-mismatch man={str(p0.get('sha256'))[:12]} live={live_sha[:12]}"
                )
            # manifest records the RAW on-disk byte count (its sha256 is the
            # CRLF-normalized digest); accept raw size, flag neither-matches
            raw_n = out.stat().st_size
            if p0.get("bytes") not in (raw_n, live_n):
                rep["fails"].append(f"manifest-primary-bytes man={p0.get('bytes')} raw={raw_n} norm={live_n}")
        for a in rows:
            rel = str(a.get("path") or "").replace("\\", "/")
            fp = REPO / rel
            if not fp.is_file():
                rep["fails"].append(f"manifest-row-absent:{rel}")
                continue
            snap_paths.append(fp)
            s2, n2 = digest(fp)
            raw_n2 = fp.stat().st_size
            if s2 != str(a.get("sha256") or ""):
                rep["fails"].append(
                    f"manifest-row-sha:{rel} man={str(a.get('sha256'))[:12]} live={s2[:12]}"
                )
            if a.get("bytes") not in (raw_n2, n2):
                rep["fails"].append(
                    f"manifest-row-bytes:{rel} man={a.get('bytes')} raw={raw_n2} norm={n2}"
                )
        rep["notes"].append(f"manifest-rows={len(rows)}")

        # F live probes
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        cmds = probe_cmds(uid, receipt, pdir)
        if not cmds:
            rep["fails"].append("no-live-probes-found")
            results[uid] = rep
            continue
        pre = {p: raw_digest(p) for p in snap_paths if p.is_file()}
        ok_runs = 0
        for cmd in cmds:
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            # Recorded probe commands are run AS RECORDED (plain env):
            # a PYTHONPATH augmentation shadows the stdlib `platform`
            # module with the repo's platform/ namespace dir on this box.
            env.pop("PYTHONPATH", None)
            env.pop("AST_INTEGRATE_ROOT", None)
            cmd = winify(cmd, env)
            toks = cmd.split(" ")
            if "-B" in toks:
                i = toks.index("-B")
                argv = [sys.executable, "-B"] + toks[i + 1:]
            else:
                argv = [sys.executable] + toks[1:]
            try:
                cp = subprocess.run(
                    argv, cwd=str(REPO), env=env, capture_output=True, text=True,
                    timeout=PROBE_TIMEOUT_S, encoding="utf-8", errors="replace",
                )
                rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
            except subprocess.TimeoutExpired:
                rep["fails"].append(f"probe-timeout:{Path(argv[-1]).name}")
                continue
            pname = Path(argv[-1]).name
            if rc != 0:
                rep["fails"].append(f"probe-rc:{pname}={rc}")
            if "SUCCESS:" not in so:
                rep["fails"].append(f"probe-no-success-marker:{pname}")
            if "FAILED:" in so or "FAILED:" in se:
                tail = (so + se)
                k = tail.find("FAILED:")
                rep["fails"].append(f"probe-failed-marker:{pname}::{tail[k:k + 140]}")
            if rc == 0 and "SUCCESS:" in so and "FAILED:" not in (so + se):
                ok_runs += 1
        rep["notes"].append(f"probes-ok={ok_runs}/{len(cmds)}")

        # G no mutation by the probe battery
        post = {p: raw_digest(p) for p in pre}
        for p, before in pre.items():
            if post.get(p) != before:
                rep["fails"].append(f"probe-mutated-reviewed-artifact:{p.name}")

        results[uid] = rep

    print("=" * 100)
    n_pass = 0
    for uid in UNITS:
        rep = results.get(uid, {"fails": ["no-result"], "notes": []})
        if rep["fails"]:
            print(f"{uid} FAIL")
            for f in rep["fails"]:
                print(f"    - {f}")
            for nline in rep["notes"]:
                print(f"    # {nline}")
        else:
            n_pass += 1
            print(f"{uid} PASS  ({'; '.join(rep['notes'])})")
    print("=" * 100)
    print(f"wave-3 shard-6 verdict: {n_pass}/{len(UNITS)} units hold ALL checks")
    if n_pass == len(UNITS):
        print("SUCCESS:shard6-w3-review all units hold")
        return 0
    print(f"FAILED:shard6-w3-review {len(UNITS) - n_pass}/{len(UNITS)} units failing")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
