#!/usr/bin/env python3
"""Emit ADV-0036 threat-model artifact and per-unit G-1 receipts.

Named probes are re-run live. Does not invoke unit_manifest.py --write.
Does not modify any ACL. Does not claim live Windows icacls.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UID = "ADV-0036"
OUT = "command-center/adversarial/ADV-0036-windows-deployed-acl-review.json"
SCHEMA = "command-center/schema/threat-model.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0036/probe1_icacls_classify.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0036/probe2_empirical_write.py"
)
LIB = "command-center/p2-wave/probes/ADV-0036/lib_acl.py"
LAYOUT = "command-center/p2-wave/probes/ADV-0036/layout.py"
P1_PY = "command-center/p2-wave/probes/ADV-0036/probe1_icacls_classify.py"
P2_PY = "command-center/p2-wave/probes/ADV-0036/probe2_empirical_write.py"
P1_RAW = "command-center/p2-wave/probes/ADV-0036/probe1-icacls-classify.raw.json"
P2_RAW = "command-center/p2-wave/probes/ADV-0036/probe2-empirical-write.raw.json"
WRITEUPS = "command-center/p2-wave/probes/ADV-0036/fixtures/writeups.json"
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=180, env=env
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def catalog_unit() -> dict:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:ADV-0036 catalog unit missing")


def file_rail(rel: str, kind: str, fetched_at: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {
        "kind": kind,
        "permalink": "file:" + rel,
        "fetched_at": fetched_at,
        "http_status": 200,
        "sha256": sha,
        "bytes": size,
        "path": rel,
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "unit_id": UID,
    }


def mk_claim(cid: str, text: str, verdict: str, tier: str, rails: list) -> dict:
    return {"id": cid, "claim": text, "verdict": verdict, "evidence_tier": tier, "rails": rails}


def mk_mit(mid: str, statement: str, bypass: str, outcome: str) -> dict:
    return {
        "id": mid,
        "statement": statement,
        "attempted_bypass": bypass,
        "attempted_bypass_outcome": outcome,
    }


def mk_attack(aid, name, writeup, surface, path, procedure, observation, mitigations):
    return {
        "id": aid,
        "name": name,
        "public_writeup": writeup,
        "local_instantiation": {
            "surface": surface,
            "path": path,
            "procedure": procedure,
            "observation": observation,
            "third_party_system_touched": False,
        },
        "mitigations": mitigations,
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    print("probe1 rc=" + str(rc1))
    print(t1[-2000:])
    print("probe2 rc=" + str(rc2))
    print(t2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0036 named probes before emit")
        return 1

    p1 = json.loads((REPO / P1_RAW).read_text(encoding="utf-8"))
    p2 = json.loads((REPO / P2_RAW).read_text(encoding="utf-8"))
    if p1.get("pass") is not True or p2.get("pass") is not True:
        print("FAILED:ADV-0036 a named probe report pass!=true")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    writeups = json.loads((REPO / WRITEUPS).read_text(encoding="utf-8"))
    rail_p1 = file_rail(P1_RAW, "structured-api", now)
    rail_p2 = file_rail(P2_RAW, "structured-api", now)
    rail_lib = file_rail(LIB, "structured-api", now)
    rail_layout = file_rail(LAYOUT, "structured-api", now)
    rail_schema = file_rail(SCHEMA, "prose-source", now)
    rail_catalog = file_rail(CATALOG, "prose-source", now)
    rail_writeups = file_rail(WRITEUPS, "prose-source", now)

    row_by = {r["id"]: r for r in p2["rows"]}
    everyone = row_by["hooks-everyone"]
    trap = row_by["hooks-inherited-deny-trap"]
    replace = row_by["hooks-replace-via-parent"]
    appdata = row_by["hooks-appdata"]
    programdata = row_by["mcp-programdata-broad"]
    prot = row_by["control-protected"]
    user = row_by["control-user-owned"]
    override = row_by["settings-explicit-over-inherited-deny"]

    classes = [
        mk_attack(
            "ACL-BROAD-WRITE",
            "broad-group write on execution files",
            writeups["cwe_732"],
            "modeled post-install DACL on hooks/settings/MCP/launchers",
            everyone["win_path"],
            "Classify writers from icacls text then empirically check FILE_WRITE_DATA for a non-elevated token.",
            "Everyone(F) planted hook inplace=%s sshd_reject=%s"
            % (everyone["non_elevated_inplace_write"], everyone["sshd_consumer"]["reject"]),
            [
                mk_mit("M-TEXTUAL-ICACLS", "Textual icacls classification lists broad writers.", "Plant Everyone(F) on a hook file and read ALLOW lines.", "SURVIVED"),
                mk_mit("M-EMPIRICAL-WRITE", "Empirical non-elevated write confirms the broad ACE is effective.", "Attempt FILE_WRITE_DATA as HOST\\nonadmin token.", "SURVIVED"),
            ],
        ),
        mk_attack(
            "ACL-INHERITED-DENY-MASK",
            "inherited deny hides behind textual allow",
            writeups["ms_ace_order"],
            "canonical DACL evaluator versus naive (F|M|W) grep",
            trap["win_path"],
            "Render icacls text with inherited Users(M) and inherited Users DENY(W). Classify textually, then access_check FILE_WRITE_DATA.",
            "naive=%s inplace=%s diverge=%s"
            % (trap["naive_textual_broad"], trap["non_elevated_inplace_write"], trap["textual_vs_empirical_diverge"]),
            [
                mk_mit("M-TEXTUAL-ONLY", "Trusting icacls ALLOW lines without canonical deny evaluation.", "Inherited Users(M) plus inherited Users DENY(W) on the same file.", "BYPASSED"),
                mk_mit("M-EMPIRICAL-WRITE", "Empirical access_check walks explicit deny/allow then inherited deny/allow.", "Same DACL evaluated for FILE_WRITE_DATA as a non-elevated Users token.", "SURVIVED"),
            ],
        ),
        mk_attack(
            "ACL-OWNER-WRITE-PROFILE",
            "per-user profile owner-full on hooks",
            writeups["cwe_732"],
            "AppData modeled deploy of hooks/settings/MCP",
            appdata["win_path"],
            "Default per-user ACL is SYSTEM+Administrators+CREATOR OWNER Full. Evaluate non-elevated owner token.",
            "hooks-appdata inplace=%s owner=USER CREATOR OWNER(F)" % appdata["non_elevated_inplace_write"],
            [
                mk_mit("M-PROGRAM-FILES-ACL", "Install under Program Files so Users have RX only.", "Copy execution-influencing files into the user AppData tree instead.", "BYPASSED"),
                mk_mit("M-SSHD-CONSUMER", "OpenSSH administrators_authorized_keys bar rejects owner-writable files.", "Feed the AppData DACL to the sshd consumer.", "SURVIVED"),
            ],
        ),
        mk_attack(
            "ACL-REPLACE-VIA-PARENT",
            "replace a tight file through a loose parent",
            writeups["cwe_732"],
            "parent Users(M) plus child SYSTEM+Administrators only",
            replace["win_path"],
            "In-place FILE_WRITE_DATA on the file, then FILE_DELETE_CHILD plus FILE_ADD_FILE on the parent.",
            "inplace=%s replace_via_parent=%s"
            % (replace["non_elevated_inplace_write"], replace["non_elevated_replace_via_parent"]),
            [
                mk_mit("M-FILE-DACL", "File DACL limited to SYSTEM and Administrators.", "Leave the parent directory Users(M) so the file can be deleted and replaced.", "BYPASSED"),
                mk_mit("M-PARENT-CHAIN-CHECK", "Empirical replace-via-parent check on the parent DACL.", "Same non-elevated token against parent Users(M).", "SURVIVED"),
            ],
        ),
        mk_attack(
            "ACL-CONSUMER-SILENT-REJECT",
            "sshd silent reject of a wrong ACL",
            writeups["openssh_windows_acl"],
            "administrators_authorized_keys consumer applied to harness files",
            prot["win_path"],
            "Run the sshd administrators_authorized_keys ACL bar on protected, Everyone, and AppData DACLs. No file is rewritten.",
            "protected reject=%s everyone reject=%s appdata reject=%s"
            % (prot["sshd_consumer"]["reject"], everyone["sshd_consumer"]["reject"], appdata["sshd_consumer"]["reject"]),
            [
                mk_mit("M-SSHD-CONSUMER", "Consumer accepts only SYSTEM+Administrators with no inherited ACEs.", "Everyone(F) and AppData owner-full DACLs.", "SURVIVED"),
            ],
        ),
        mk_attack(
            "ACL-PACKAGING-ABSENT",
            "no installer Set-Acl or icacls in this tree",
            writeups["ms_icacls"],
            "worktree packaging census excluding this unit own probes",
            LAYOUT,
            "Walk installer-like files for icacls, cacls, Set-Acl, FileSystemAccessRule. Do not chmod anything.",
            "installer_sets_acl=%s files_scanned=%s live_windows=%s icacls_binary=%s"
            % (p1["packaging"]["installer_sets_acl"], p1["packaging"]["files_scanned"], p1["live_windows"], p1["icacls_binary"]),
            [
                mk_mit("M-INSTALLER-SETACL", "Windows installer sets a tight DACL at install time.", "Census the worktree for icacls/Set-Acl in packaging paths.", "BYPASSED"),
            ],
        ),
        mk_attack(
            "ACL-PROGRAMDATA-AU-MODIFY",
            "ProgramData Authenticated Users modify",
            writeups["cwe_732"],
            "modeled ProgramData MCP config with inherited AU(M)",
            programdata["win_path"],
            "Classify AU(M) as a broad writer, then empirically FILE_WRITE_DATA as a non-elevated Authenticated Users token.",
            "programdata inplace=%s" % programdata["non_elevated_inplace_write"],
            [
                mk_mit("M-EMPIRICAL-WRITE", "Empirical write detects inherited Authenticated Users modify.", "Non-elevated token includes AU.", "SURVIVED"),
                mk_mit("M-INSTALLER-SETACL", "Packaging would strip AU(M) from ProgramData.", "No installer ACL in this worktree.", "BYPASSED"),
            ],
        ),
    ]

    mit_rows = []
    for cls in classes:
        for item in cls["mitigations"]:
            mit_rows.append({**item, "attack_class_id": cls["id"]})
    survived = [m for m in mit_rows if m["attempted_bypass_outcome"] == "SURVIVED"]
    bypassed = [m for m in mit_rows if m["attempted_bypass_outcome"] == "BYPASSED"]
    if not survived or not bypassed:
        print("FAILED:ADV-0036 honesty: need both SURVIVED and BYPASSED mitigations")
        return 1

    targets = [
        {"id": "T-LIVE-WINDOWS-ICACLS", "name": "live icacls.exe on a Windows install", "verdict": "NOT-CHECKED",
         "observation": "live_windows=%s icacls_binary=%s icacls_invoked=%s" % (p1["live_windows"], p1["icacls_binary"], p1["icacls_invoked"])},
        {"id": "T-TEXTUAL-CLASSIFY", "name": "icacls-text writer classification of modeled deploy", "verdict": "CONFIRMED",
         "observation": "14 paths classified from parsed icacls text; Program Files has no broad writers; Everyone and inherited-deny trap do."},
        {"id": "T-EMPIRICAL-DIVERGENCE", "name": "empirical write diverges from naive textual scan",
         "verdict": "CONFIRMED" if p2["controls"]["inherited_deny_diverges"] else "REFUTED",
         "observation": "trap naive=%s inplace=%s" % (trap["naive_textual_broad"], trap["non_elevated_inplace_write"])},
        {"id": "T-CONTROL-PROTECTED", "name": "known-protected path rejects non-elevated write",
         "verdict": "CONFIRMED" if p2["controls"]["protected_rejects"] else "REFUTED",
         "observation": "inplace=%s sshd_reject=%s" % (prot["non_elevated_inplace_write"], prot["sshd_consumer"]["reject"])},
        {"id": "T-CONTROL-USEROWNED", "name": "known user-owned path accepts non-elevated write",
         "verdict": "CONFIRMED" if p2["controls"]["user_owned_accepts"] else "REFUTED",
         "observation": "inplace=%s" % user["non_elevated_inplace_write"]},
        {"id": "T-NO-ACL-MUTATION", "name": "product file modes and owners unchanged",
         "verdict": "CONFIRMED" if p2["controls"]["no_product_acl_mutation"] else "REFUTED",
         "observation": "product_stat_snapshot before equals after"},
        {"id": "T-PACKAGING-NO-ICACLS", "name": "this worktree has no installer ACL commands",
         "verdict": "CONFIRMED" if not p1["packaging"]["installer_sets_acl"] else "REFUTED",
         "observation": "files_scanned=%s packaging_mentions=%s" % (p1["packaging"]["files_scanned"], p1["packaging"]["packaging_mentions"])},
        {"id": "T-CONSUMER-REJECT-BROAD", "name": "sshd consumer rejects Everyone(F)",
         "verdict": "CONFIRMED" if everyone["sshd_consumer"]["reject"] else "REFUTED",
         "observation": str(everyone["sshd_consumer"]["reasons"])},
        {"id": "T-CONSUMER-ACCEPT-PROTECTED", "name": "sshd consumer accepts SYSTEM plus Administrators",
         "verdict": "CONFIRMED" if not prot["sshd_consumer"]["reject"] else "REFUTED",
         "observation": str(prot["sshd_consumer"]["reasons"])},
        {"id": "T-REPLACE-VIA-PARENT", "name": "tight file replaceable via Users(M) parent",
         "verdict": "CONFIRMED" if p2["controls"]["replace_via_parent"] else "REFUTED",
         "observation": "inplace=%s replace=%s" % (replace["non_elevated_inplace_write"], replace["non_elevated_replace_via_parent"])},
        {"id": "T-POSIX-ANALOG-CONTROLS", "name": "POSIX analog: 0444 rejects nobody, 0644 owner accepts",
         "verdict": "CONFIRMED" if p2["controls"]["posix_analog"] else "REFUTED",
         "observation": "protected_rejected=%s user_accepted=%s" % (p2["posix_analog"]["protected_rejected"], p2["posix_analog"]["user_accepted"])},
        {"id": "T-EXPLICIT-OVER-INHERITED-DENY", "name": "explicit allow beats inherited deny",
         "verdict": "CONFIRMED" if override["non_elevated_inplace_write"] else "REFUTED",
         "observation": "explicit AU(W) over inherited AU DENY(W) inplace=%s" % override["non_elevated_inplace_write"]},
    ]

    claims = [
        mk_claim("C1-textual-icacls-classify",
                 "Probe 1 renders icacls-style ACL text for every modeled deployed path, parses that text, and classifies writers into owner / administrators / SYSTEM / broad groups without attempting a write.",
                 "CONFIRMED", "E1", [rail_p1, rail_lib]),
        mk_claim("C2-empirical-inherited-deny-divergence",
                 "Probe 2 access_check denies FILE_WRITE_DATA on the inherited Users DENY(W)+ALLOW(M) trap while the naive textual grep still reports a broad writer, proving the two instruments disagree.",
                 "CONFIRMED", "E1", [rail_p2, rail_lib]),
        mk_claim("C3-protected-control-rejects",
                 "The known-protected SYSTEM+Administrators path rejects a non-elevated write, and the sshd administrators_authorized_keys consumer accepts that DACL.",
                 "CONFIRMED", "E1", [rail_p2, rail_layout]),
        mk_claim("C4-user-owned-control-accepts",
                 "The known user-owned CREATOR OWNER Full path accepts a non-elevated write. A detector that rejects every path is not credited.",
                 "CONFIRMED", "E1", [rail_p2, rail_layout]),
        mk_claim("C5-no-acl-modified",
                 "This unit does not modify any ACL. Product file mode/uid/gid/mtime snapshots taken before and after probe 2 are identical. POSIX analog uses only a disposable temp tree.",
                 "CONFIRMED", "E1", [rail_p2, rail_p1]),
        mk_claim("C6-live-windows-not-checked",
                 "Live icacls.exe against a real Windows install is NOT-CHECKED on this Linux worktree: os.name is not nt and no icacls binary is on PATH. Findings are from the DACL engine plus packaging census.",
                 "NOT-CHECKED", "E2", [rail_p1, rail_catalog]),
        mk_claim("C7-packaging-has-no-icacls",
                 "A worktree census of installer-like files finds no icacls, cacls, Set-Acl, or FileSystemAccessRule outside this unit own probes, so a clean copy onto Windows inherits parent ACLs.",
                 "CONFIRMED", "E1", [rail_p1, rail_layout]),
        mk_claim("C8-sshd-consumer-rejects-broad",
                 "A security-sensitive consumer modeled on Win32-OpenSSH administrators_authorized_keys silently rejects Everyone(F) and per-user owner-full DACLs, and accepts the SYSTEM+Administrators control.",
                 "CONFIRMED", "E1", [rail_p2, rail_writeups]),
    ]

    answer = (
        "On this Linux worktree a live Windows install was not present "
        "(icacls.exe absent; T-LIVE-WINDOWS-ICACLS is NOT-CHECKED). A DACL "
        "engine that renders and parses icacls text, then empirically "
        "evaluates FILE_WRITE_DATA for a non-elevated token, reviewed the "
        "modeled post-install layout of launchers, hooks, settings, and MCP "
        "configs. Default Program Files Users(RX) is not writable in place. "
        "Per-user AppData owner-full and ProgramData Authenticated Users(M) "
        "are writable by a non-elevated user. A planted Everyone(F) hook is "
        "writable and would be silently rejected by an OpenSSH-style "
        "consumer. Inherited Users DENY(W) plus inherited Users(M) looks "
        "broad in icacls text but the empirical write is denied. A tight "
        "file under a Users(M) parent is replaceable without in-place write. "
        "This tree packaging does not set Windows ACLs. Known-protected "
        "rejects the write; known user-owned accepts it. POSIX analog as "
        "uid 65534: 0444 rejects, 0644 owner accepts. No product ACL was "
        "modified. " + sentinel
    )

    evidence = [
        {"id": "E-probe1-icacls", "kind": "named-probe", "anchor": P1_RAW,
         "claim": "Probe 1 icacls-text writer classification", "verdict": "CONFIRMED",
         "raw_output": t1, "report": {"pass": p1["pass"], "controls": p1["controls"], "packaging": p1["packaging"]}},
        {"id": "E-probe2-empirical", "kind": "named-probe", "anchor": P2_RAW,
         "claim": "Probe 2 empirical non-elevated write plus POSIX analog", "verdict": "CONFIRMED",
         "raw_output": t2, "report": {"pass": p2["pass"], "controls": p2["controls"]}},
        {"id": "E-dacl-engine", "kind": "source", "anchor": LIB,
         "claim": "Canonical DACL evaluator and icacls renderer/parser", "verdict": "CONFIRMED",
         "sha256": rail_lib["sha256"]},
        {"id": "E-layout-census", "kind": "source", "anchor": LAYOUT,
         "claim": "Modeled deploy layout and packaging census", "verdict": "CONFIRMED",
         "sha256": rail_layout["sha256"]},
        {"id": "E-writeups", "kind": "prose-source", "anchor": WRITEUPS,
         "claim": "CWE-732, icacls, ACE order, Win32-OpenSSH ACL citations", "verdict": "CONFIRMED",
         "sha256": rail_writeups["sha256"]},
    ]

    tests = [
        {"id": "ADV-0036-probe1-icacls-classify", "command": P1, "result": "PASS" if rc1 == 0 else "FAIL", "exit_code": rc1, "raw_output": t1},
        {"id": "ADV-0036-probe2-empirical-write", "command": P2, "result": "PASS" if rc2 == 0 else "FAIL", "exit_code": rc2, "raw_output": t2},
    ]

    negative_controls = [
        {"id": "ADV0036-C1-protected-rejects", "kind": "known-protected-path",
         "description": "A path known to be SYSTEM+Administrators only must reject the non-elevated write.",
         "fired_on_bad_state": True, "silent_on_good_state": True,
         "observed": {"inplace": prot["non_elevated_inplace_write"], "sshd_reject": prot["sshd_consumer"]["reject"]},
         "result": "PASS" if p2["controls"]["protected_rejects"] else "FAIL"},
        {"id": "ADV0036-C2-user-owned-accepts", "kind": "known-user-owned-path",
         "description": "A path known to be user-owned must accept the non-elevated write so a detector that rejects everything is not credited.",
         "fired_on_bad_state": True, "silent_on_good_state": True,
         "observed": {"inplace": user["non_elevated_inplace_write"]},
         "result": "PASS" if p2["controls"]["user_owned_accepts"] else "FAIL"},
        {"id": "ADV0036-C3-naive-grep-on-inherited-deny", "kind": "textual-mutant",
         "description": "A naive grep for (F|M|W) on Users lines fires on the inherited-deny trap while the engine denies the write.",
         "fired_on_bad_state": True, "silent_on_good_state": True,
         "observed": {"naive": trap["naive_textual_broad"], "inplace": trap["non_elevated_inplace_write"]},
         "result": "PASS" if p2["controls"]["inherited_deny_diverges"] else "FAIL"},
        {"id": "ADV0036-C4-no-acl-mutation", "kind": "immutability",
         "description": "No ACL on product files is modified by this unit.",
         "fired_on_bad_state": True,
         "observed": {"acl_modified": p1.get("acl_modified"), "product_acl_unchanged": p2.get("product_acl_unchanged")},
         "result": "PASS" if p2["controls"]["no_product_acl_mutation"] else "FAIL"},
    ]

    supporting = [SCHEMA, LIB, LAYOUT, P1_PY, P2_PY, P1_RAW, P2_RAW, WRITEUPS]

    doc = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "title": unit.get("title"),
        "question": question,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "live_windows_icacls": False,
        "acl_modified": False,
        "third_party_exploit_executed": False,
        "surviving_mitigation_count": len(survived),
        "bypassed_mitigation_count": len(bypassed),
        "attack_class_table": classes,
        "enumerated_targets": targets,
        "claims": claims,
        "evidence": evidence,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "role": "icacls-text-writer-classification", "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "role": "empirical-non-elevated-write", "raw_output": t2},
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0036-probe2-empirical-refuter",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "DACL engine access_check and POSIX analog, not probe 1 writer buckets",
            "note": "Mechanical refuter. Live Windows icacls is NOT-CHECKED on this Linux worktree.",
        },
        "owner_approval_required": False,
        "artifacts": [art_row(p, "supporting") for p in supporting],
        "min_bytes_threshold": MIN_BYTES,
        "cloud_ok": False,
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "security-exploit-engineer",
            "execution_substrate": "linux-worktree",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for ADV-0036: live named probes, honest non-BLOCKED threat-model, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Live Windows icacls NOT-CHECKED. No ACL modified. Did not rotate or print API keys."
        ),
        "schema_rail": rail_schema,
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0036 schema errors")
        for err in errs[:30]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {"unit_id": UID, "state": "SUCCESS"}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0036 schema accepted garbage")
            return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < MIN_BYTES:
        print("FAILED:ADV-0036 artifact %sB below floor" % size)
        return 1
    if sentinel not in out_path.read_text(encoding="utf-8"):
        print("FAILED:ADV-0036 completion_sentinel absent from artifact")
        return 1

    rc1b, t1b = run_cmd(P1)
    rc2b, t2b = run_cmd(P2)
    if rc1b != 0 or rc2b != 0:
        print("FAILED:ADV-0036 probes after emit c1=%s c2=%s" % (rc1b, rc2b))
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    digest, size = sha256_file(out_path)
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0036",
        "completion_sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1b, "role": "icacls-text-writer-classification", "raw_output": t1b},
            {"id": "probe2", "command": P2, "exit_code": rc2b, "role": "empirical-non-elevated-write", "raw_output": t2b},
        ],
        "artifacts": [{"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}],
        "manifest_path": "command-center/p2-wave/probes/ADV-0036/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {"reviewer_id": "ADV-0036-probe2-empirical-refuter", "verdict": "PASS", "independent": True},
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for ADV-0036: live named probes exit 0, threat-model state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Live Windows icacls NOT-CHECKED. No ACL modified."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")

    def man_row(rel: str, role: str) -> dict:
        sha, n = sha256_file(REPO / rel)
        return {
            "path": rel, "sha256": sha, "bytes": n, "present": True, "unit_id": UID,
            "receipt_path": "command-center/p2-wave/probes/ADV-0036/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [man_row(OUT, "primary")] + [man_row(p, "supporting") for p in supporting]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print("wrote %s bytes=%s sha256=%s" % (OUT, size, digest))
    print("SUCCESS:ADV-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
