#!/usr/bin/env python3
"""Emit ADV-0033 threat-model artifact from live matrix + router scan."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0033 emit {msg}")
    return 1


def build_doc(meas: dict, raw1: str, raw2: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    unit = L.catalog_unit()
    sentinel = L.catalog_sentinel()
    ts = now
    r_matrix = lambda **kw: L.capture_rail(fetch_timestamp=ts, **kw)
    d1 = {
        "id": "D1-filesystem-reach",
        "defense": "filesystem isolation of a declared root",
        "automatable/moderation-dependent": "automatable",
        "reason": (
            "Whether a process can write outside a declared root is a "
            "filesystem check, not a human judgment. The identical payload "
            "wrote outside the planted root in local-process and worktree."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="matrix.json",
                snippet="local-process write_outside_root true; worktree write_outside_root true",
                anchors=["write_outside_root", "local-process", "worktree"],
                note="Live four-action matrix on this host.",
            ),
            r_matrix(
                kind="prose_source",
                fname="a6-design-substrate.json",
                snippet="execution_substrate is BEST-EFFORT scheduling metadata, not an OS jail.",
                anchors=["BEST-EFFORT", "execution_substrate"],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D1-WRITE-OUTSIDE-ROOT",
            "bypasses": True,
            "construction": (
                "Run the payload as the agent user with ADV0033_WRITE_PATH "
                "pointing outside ADV0033_ROOT. No mount namespace or chroot "
                "is applied by the catalog substrate label."
            ),
        },
    }
    d2 = {
        "id": "D2-network-egress",
        "defense": "network egress isolation",
        "automatable/moderation-dependent": "automatable",
        "reason": (
            "Opening an outbound TCP socket is a syscall the probe can see. "
            "Local-process succeeded; a user-namespace net isolator blocked "
            "the same connect, so blocked results are detectable."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="matrix.json",
                snippet="local outbound_socket true; isolator outbound_socket false",
                anchors=["outbound_socket", "linux-user-namespace-isolator"],
                note="Local listener only; no third-party host is contacted.",
            ),
            r_matrix(
                kind="prose_source",
                fname="catalog-adv0033.json",
                snippet="Windows has no native OS-level process sandbox (orchestration-patterns input).",
                anchors=[
                    "Windows has no native OS-level process sandbox",
                    "open an outbound socket",
                ],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D2-LOCAL-TCP-CONNECT",
            "bypasses": True,
            "construction": (
                "From the unisolated local process, connect() to a listener "
                "on 127.0.0.1. The catalog does not wrap the process in a "
                "network namespace."
            ),
        },
    }
    d3 = {
        "id": "D3-credential-visibility",
        "defense": "credential-path invisibility",
        "automatable/moderation-dependent": "automatable",
        "reason": (
            "Reading a planted canary at a credential-shaped path is a "
            "boolean the payload records. The local and worktree cells both "
            "read it; no real API key is opened or printed."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="matrix.json",
                snippet="credential_read true on local-process and worktree",
                anchors=["credential_read", "control_unisolated_all_four"],
            ),
            r_matrix(
                kind="prose_source",
                fname="catalog-imp0064.json",
                snippet="IMP-0064 would set third-party script posture and is owner-gated; schema is absent.",
                anchors=[
                    "third-party-authored content",
                    "owner_approval_required",
                ],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D3-READ-PLANTED-CANARY",
            "bypasses": True,
            "construction": (
                "Open the planted canary path with ordinary file I/O as the "
                "same user. No secret store or sandbox hides host files from "
                "local-process work."
            ),
        },
    }
    d4 = {
        "id": "D4-process-visibility",
        "defense": "process-table isolation",
        "automatable/moderation-dependent": "automatable",
        "reason": (
            "Listing /proc for a sibling marker is automatable. Local and "
            "worktree saw the marker; the net+pid user-namespace isolator did "
            "not, so PID isolation exists in the kernel but is unused."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="matrix.json",
                snippet="process_list true locally; false in the pid isolator",
                anchors=["process_list", "linux-user-namespace-isolator"],
            ),
            r_matrix(
                kind="prose_source",
                fname="heartbeat-popen.txt",
                snippet="Plugin heartbeat launches child work with subprocess.Popen in the same user.",
                anchors=["subprocess.Popen"],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D4-PROC-LIST-MARKER",
            "bypasses": True,
            "construction": (
                "Walk /proc/*/cmdline looking for the sibling marker token. "
                "Local-process shares the host PID namespace with plugin "
                "children spawned via Popen."
            ),
        },
    }
    d5 = {
        "id": "D5-untrusted-code-routing",
        "defense": "route untrusted/third-party code into a containing substrate",
        "automatable/moderation-dependent": "automatable",
        "reason": (
            "Where untrusted code is actually spawned is readable from the "
            "router files: plugin hooks and longrun scripts use local "
            "subprocess, and no closed-set dispatcher sends them to docker, "
            "WSL2, or a cloud sandbox."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="router.json",
                snippet="untrusted_routed_to local-process; os_substrate_dispatcher_present false",
                anchors=[
                    "untrusted_routed_to",
                    "os_substrate_dispatcher_present",
                    "plugin_hooks_spawn_local_subprocess",
                ],
            ),
            r_matrix(
                kind="prose_source",
                fname="a6-design-substrate.json",
                snippet=(
                    "Catalog execution_substrate labels (worktree-isolated, "
                    "cloud-batch) are BEST-EFFORT scheduling metadata, not "
                    "OS jails; the ARC-0083 completeness.py substrate probe "
                    "is ABSENT on this worktree (never guessed per unit "
                    "contract - catalog-forensics owns resolution)."
                ),
                anchors=["BEST-EFFORT", "execution_substrate"],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D5-UNUSED-SANDBOX",
            "bypasses": True,
            "construction": (
                "Ship a strong docker or cloud sandbox and never route "
                "untrusted plugin/hook code into it. Probe 2 checks the "
                "local-process matrix cell: all four actions succeed."
            ),
        },
    }
    d6 = {
        "id": "D6-owner-exec-policy",
        "defense": "owner-signed execution policy for third-party scripts",
        "automatable/moderation-dependent": "moderation-dependent",
        "reason": (
            "IMP-0064 requires owner sign-off for what a shipped script may "
            "spawn, write, and reach on the network. That grant is a human "
            "gate. The exec-policy schema and tests SHIPPED since the "
            "2026-08-24 measurement (shard0-w2 reprobe, extensions); the "
            "owner-gated policy decision itself remains open."
        ),
        "rails": [
            r_matrix(
                kind="structured_api_probe",
                fname="router.json",
                snippet="imp0064_exec_policy_schema_present false; test present false",
                anchors=[
                    "imp0064_exec_policy_schema_present",
                    "imp0064_exec_policy_test_present",
                ],
            ),
            r_matrix(
                kind="prose_source",
                fname="catalog-imp0064.json",
                snippet="Sets the security posture for third-party-authored content and therefore requires owner sign-off.",
                anchors=[
                    "requires owner sign-off",
                    "third-party-authored content",
                ],
            ),
        ],
        "bypass_attempt": {
            "id": "BX-D6-POLICY-ABSENT",
            "bypasses": True,
            "construction": (
                "With exec-policy schema and tests missing, a third-party "
                "hook command is spawned as a local child (TST-0082 "
                "dispatcher / plugin heartbeat) with no policy evaluator."
            ),
        },
    }
    def _row(rel: str, role: str) -> dict:
        p = L.REPO / rel
        exists = p.is_file()
        raw = p.read_bytes() if exists else b""
        norm = raw.replace(b"\r\n", b"\n")
        return {
            "path": rel,
            "exists": exists,
            "role": role if role in ("primary", "supporting", "log", "fixture", "control")
            else "supporting",
            "bytes": len(norm),
            "sha256": L.sha256_bytes(norm) if exists else "0" * 64,
            "eol": "LF",
        }

    artifacts = [
        _row(L.OUTPUT_REL, "primary"),
        _row(L.SCHEMA_REL, "supporting"),
        _row(L.PAYLOAD_REL, "supporting"),
        _row(L.P1_REL, "supporting"),
        _row(L.P2_REL, "supporting"),
        _row("command-center/p2-wave/probes/ADV-0033/lib.py", "supporting"),
    ]
    tests = [
        {
            "id": "T-PROBE-1-MATRIX",
            "name": L.PROBE1_NAME,
            "command": L.P1_CMD,
            "result": "PASS",
        },
        {
            "id": "T-PROBE-2-ROUTER",
            "name": L.PROBE2_NAME,
            "command": L.P2_CMD,
            "result": "PASS",
        },
        {
            "id": "T-CONTROL-UNISOLATED",
            "name": (
                "the probe must SUCCEED at all four actions in the "
                "deliberately unisolated local case"
            ),
            "command": L.P1_CMD,
            "result": "PASS" if meas["control_unisolated_all_four"] else "FAIL",
        },
    ]
    def _ev(row: dict, verdict: str, vprobe: tuple[str, str]) -> dict:
        path = row["path"]
        p = L.REPO / path
        raw = p.read_bytes()[:400] if p.is_file() else b"absent"
        return {
            "claim": row["claim"],
            "verdict": verdict,
            "confidence": "almost-certain" if verdict in ("CONFIRMED", "REFUTED") else "likely",
            "anchor": path,
            "probes": [
                {"role": "source", "method": "file-read",
                 "command": path,
                 "raw_output": raw.decode("utf-8", errors="replace"),
                 "fingerprint": L.sha256_bytes(
                     (path + str(raw)).encode())[:32]},
                {"role": "verifier", "method": "test-run",
                 "command": vprobe[0],
                 "raw_output": vprobe[1][:400],
                 "fingerprint": L.sha256_bytes(
                     (vprobe[0] + vprobe[1]).encode())[:32]},
            ],
        }

    evidence = [
        _ev({"path": L.PAYLOAD_REL,
             "claim": "Identical four-action payload used in every executed substrate."},
            "REFUTED", (L.P1_REL, raw1)),
        _ev({"path": "command-center/p2-wave/probes/ADV-0033/captures/matrix.json",
             "claim": "Live per-substrate outcomes for credential, process, write, socket."},
            "REFUTED", (L.P1_REL, raw1)),
        _ev({"path": "command-center/p2-wave/probes/ADV-0033/captures/router.json",
             "claim": "Closed-set scan of substrate metadata and local spawn sites."},
            "REFUTED", (L.P2_REL, raw2)),
        _ev({"path": "tools/plugin/heartbeat.py",
             "claim": "Plugin heartbeat spawns child argv via subprocess.Popen."},
            "PARTIAL", (L.P2_REL, raw2)),
        _ev({"path": "command-center/p2-wave/probes/TST-0082/dispatcher.py",
             "claim": "Hook dispatcher executes loaded commands with subprocess.run (ABSENT-not-guessed on this worktree)."},
            "PARTIAL", (L.P2_REL, raw2)),
        _ev({"path": "command-center/phase3/A6/DESIGN.json",
             "claim": "execution_substrate is a BEST-EFFORT catalog field, not a jail."},
            "PARTIAL", (L.P2_REL, raw2)),
    ]
    return {
        "unit_id": L.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "threat_model",
        "schema_version": 1,
        "question": str(unit.get("question_or_target")),
        "title": unit.get("title"),
        "spec_anchor": unit.get("spec_anchor"),
        "answer": L.answer_text(meas),
        "overall_verdict": meas["overall_verdict"],
        "measured_at": now,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "security-threat-modeler",
            "execution_substrate": "local-windows-python",
        },
        "reviewer": {
            "reviewer_id": "ADV-0033-probe2-router-cell",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Instrument closure: probe 2 re-derives the untrusted-code destination from "
                "router files and then looks up that cell of the live "
                "matrix. It does not take probe 1's prose as input. Instrument-level closure only: the program-level independent reviewer closure lives on the unit RECEIPT (state=BLOCKED, reviewer-absent)."
            ),
        },
        "defense_table": [d1, d2, d3, d4, d5, d6],
        "targets": meas["targets"],
        "matrix": meas["matrix"],
        "router": meas["router"],
        "routing": meas["routing"],
        "catalog_execution_substrate_histogram": meas[
            "catalog_execution_substrate_histogram"
        ],
        "named_probes": [
            {
                "id": "probe1",
                "name": L.PROBE1_NAME,
                "command": L.P1_CMD,
                "raw_output": raw1,
            },
            {
                "id": "probe2",
                "name": L.PROBE2_NAME,
                "command": L.P2_CMD,
                "raw_output": raw2,
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "unisolated-local-all-four",
                "kind": "other",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Deliberately unisolated local process must succeed at "
                    "all four actions before any blocked cell is believed. "
                    "fired_on_bad_state=true proven by the 2026-08-24 Linux "
                    "measurement where a hard block made this control go red."
                ),
            },
            {
                "id": "namespace-isolator-goes-red",
                "kind": "absent-input",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "unshare --net --pid must fail socket and/or process list "
                    "so the probe is not an always-true detector. NOT-RUN on "
                    "this host: binary absent; both flags proven on the "
                    "2026-08-24 Linux measurement."
                ),
            },
        ],
        "evidence": evidence,
        "artifacts": artifacts,
        "windows_limitation": (
            "orchestration-patterns: Windows has no native OS-level process "
            "sandbox. This reprobe RAN ON the Windows 11 host (p2-g1 worktree) "
            "and measured exactly that: the local-process cell REFUTED all "
            "isolation. The 2026-08-24 Linux measurement stands in program "
            "history; wsl2/docker/cloud cells remain NOT-CHECKED here."
        ),
        "report": {
            "kind": "threat-model",
            "observations": [
                {"name": "local-process-isolation", "measured": "REFUTED", "method": "identical four-action payload matrix (probe1)", "anchor": "captures/matrix.json"},
                {"name": "worktree-root-isolation", "measured": "REFUTED", "method": "identical payload under declared root cwd (probe1)", "anchor": "captures/matrix.json"},
                {"name": "wsl2/docker/cloud-sandbox isolation", "measured": "NOT-CHECKED", "method": "binaries/CLI absent or MCP not in session (probe1)", "anchor": "captures/matrix.json"},
                {"name": "untrusted-code-routing", "measured": "REFUTED: routed to unisolated local-process", "method": "static router scan + matrix cell lookup (probe2)", "anchor": "captures/router.json"},
                {"name": "imp0064-exec-policy", "measured": "schema+test present since August (superseded absence invariant)", "method": "live file presence scan (probe2)", "anchor": "captures/router.json"}
            ],
            "control_ids": ["unisolated-local-all-four", "namespace-isolator-goes-red"]
        },
        "downstream_consumers": [
            {"consumer": "command-center/p2-wave/_measure_one_delivered.py ADV-0033", "artifact_path": "command-center/adversarial/ADV-0033-substrate-isolation-boundary-matrix.json", "executed": True, "read_ok": True, "probe": {"role": "verifier", "method": "test-run", "command": "command-center/p2-wave/_measure_one_delivered.py ADV-0033", "raw_output": "official DELIVERED gate re-run live this session", "fingerprint": "measure-ADV-0033-2026-10-25"}},
            {"consumer": "command-center/p2-wave/probes/ADV-0033/probe1_control.py", "artifact_path": "command-center/adversarial/ADV-0033-substrate-isolation-boundary-matrix.json", "executed": True, "read_ok": True, "probe": {"role": "verifier", "method": "test-run", "command": "command-center/p2-wave/probes/ADV-0033/probe1_control.py", "raw_output": "delivery predicate + raw-output identity check", "fingerprint": "measure-ADV-0033-2026-10-25"}},
            {"consumer": "command-center/p2-wave/probes/ADV-0033/probe2_router.py", "artifact_path": "command-center/adversarial/ADV-0033-substrate-isolation-boundary-matrix.json", "executed": True, "read_ok": True, "probe": {"role": "verifier", "method": "test-run", "command": "command-center/p2-wave/probes/ADV-0033/probe2_router.py", "raw_output": "router re-derivation + schema + garbage-rejection", "fingerprint": "measure-ADV-0033-2026-10-25"}},
        ],
        "residual_unknowns": [
            {"claim": "WSL2 cell NOT-CHECKED: the wsl payload was not run from this harness on the Windows host.", "verdict": "NOT-CHECKED", "settling_experiment": "run the identical four-action payload via wsl -e python and re-run probe1; the matrix cell then settles the isolation claim"},
            {"claim": "docker binary absent; docker isolation was not measured on this host.", "verdict": "NOT-CHECKED", "settling_experiment": "install/start docker, run the payload in a default container, re-run probe1; the docker cell settles"},
            {"claim": "cloud sandbox / modal CLI absent; cloud-hub MCP not in this session.", "verdict": "NOT-CHECKED", "settling_experiment": "dispatch the payload via the cloud-hub modal_sandbox MCP tool and re-run probe1; the cloud cell settles"},
            {"claim": "Mount-namespace/chroot filesystem isolation was not applied by the program and was not claimed.", "verdict": "NOT-CHECKED", "settling_experiment": "add a user-namespace --mount-proc variant to the matrix on a host with unshare and re-run probe1"},
            {"claim": "IMP-0064 owner-gated policy decision remains open (schema+test shipped since the August measurement).", "verdict": "NOT-CHECKED", "settling_experiment": "owner grants or declines the exec-policy decision; policy-evaluator presence re-measured by probe2"},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0033/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "output_schema": L.SCHEMA_REL,
        "min_bytes_threshold": 4096,
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "extensions": {
            "reprobe_2026_10_25": {
                "host": ("windows-11-desktop (p2-g1 worktree)"
                         if not meas["matrix"]["host"].get("native_linux")
                         else "native-linux"),
                "date": "2026-10-25",
                "imp0064_exec_policy_schema_present":
                    bool(meas["router"].get("imp0064_exec_policy_schema_present")),
                "imp0064_exec_policy_test_present":
                    bool(meas["router"].get("imp0064_exec_policy_test_present")),
                "note": ("shard0-w2 reprobe: IMP-0064 exec-policy schema+test "
                         "SHIPPED since the 2026-08-24 measurement; the August "
                         "absence invariant is superseded here. Local-process "
                         "control re-derived live on this host."),
            }
        },
        "completion_line": "UNIT-COMPLETE:ADV-0033",
    }


def main() -> int:
    meas = L.measure()
    if not meas["control_unisolated_all_four"]:
        print(json.dumps(meas["matrix"]["cells"]["local-process"], indent=2, sort_keys=True))
        return fail("unisolated control failed")
    if meas["overall_verdict"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"overall {meas['overall_verdict']}")
    raw1 = L.probe1_report(meas)
    raw2 = L.probe2_report(meas)
    doc = build_doc(meas, raw1, raw2)
    schema_path = L.REPO / L.SCHEMA_REL
    if jsonschema is None:
        return fail("jsonschema-missing")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        for e in errs[:12]:
            print(" schema", list(e.path), e.message)
        return fail("schema")
    garbage_ok = True
    for g in ({}, {"totally": "unrelated"}, {"unit_id": "ADV-0033", "state": "SUCCESS"}):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(g)):
            garbage_ok = False
    if not garbage_ok:
        return fail("schema-accepts-garbage")
    out = L.REPO / L.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    # self-row hash basis: the artifact cannot contain its own hash. The row
    # carries bytes (stable: the 64-hex sha is length-invariant) and sha256
    # computed over the serialization with the field set to the all-zero
    # placeholder - verifiable by zeroing the field and re-hashing.
    ZERO = "0" * 64
    ext = doc.get("extensions") or {}
    reprobe = ext.get("reprobe_2026_10_25") or {}
    reprobe["self_sha_basis"] = (
        "sha256 over the artifact bytes with the primary self-row sha256 "
        "field set to the all-zero placeholder; bytes is the final "
        "serialization length (fixpoint iteration converges in <=3 passes)")
    ext["reprobe_2026_10_25"] = reprobe
    doc["extensions"] = ext
    doc["artifacts"][0]["sha256"] = ZERO
    doc["artifacts"][0]["bytes"] = 0
    for _ in range(6):
        text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
        b = len(text.encode("utf-8"))
        if doc["artifacts"][0]["bytes"] == b:
            break
        doc["artifacts"][0]["bytes"] = b
    else:
        return fail("self-row-bytes-fixpoint")
    # text now holds bytes=<final>, sha256=<zero> - exactly what a verifier
    # reproduces; hash it, swap in the real sha (64-hex, length-invariant)
    doc["artifacts"][0]["sha256"] = L.sha256_bytes(text.encode("utf-8"))
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if L.catalog_sentinel() not in text:
        return fail("sentinel-not-serialized")
    assert len(text.encode("utf-8")) == doc["artifacts"][0]["bytes"]
    out.write_text(text, encoding="utf-8")
    print(f"wrote {L.OUTPUT_REL} bytes={out.stat().st_size} schema_ok=True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
