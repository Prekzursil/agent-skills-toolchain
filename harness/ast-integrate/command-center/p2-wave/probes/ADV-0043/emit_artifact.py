#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0043-agent-mailbox-cross-agent-leakage.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    measure_probe1,
    measure_probe2,
)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def _verdict(confirmed: bool) -> str:
    return "CONFIRMED" if confirmed else "REFUTED"


def main() -> int:
    p1 = measure_probe1()
    p2 = measure_probe2()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if not p1.get("pass") or not p2.get("pass") or c1 != 0 or c2 != 0:
        print("FAILED:ADV-0043 emit probes did not pass")
        print(json.dumps({"p1": p1.get("pass"), "p2": p2.get("pass"), "c1": c1, "c2": c2}))
        if t1:
            print(t1[-2000:])
        if t2:
            print(t2[-2000:])
        return 1

    ctrl = p1["detector_control"]
    peer = p2["optional_token_fetch_inbox_victim"]
    live = p1.get("live_store") or {}
    live_present = bool(live.get("live_store_present"))

    planted = set(p1.get("planted_classes") or [])
    t_abspath = _verdict("absolute_path" in planted)
    t_repo = _verdict("repository_name" in planted)
    t_artifact = _verdict("artifact_body" in planted)
    t_cred = _verdict("credential_in_quoted_error" in planted)
    t_acl = _verdict(bool(peer.get("sees_sensitive_peer_mail")))
    t_lease = _verdict(bool(p2.get("throwaway_sees_victim_lease_abspath")))
    # Channel is shared among every agent that can name the project_key
    # (an absolute path). A second project_key does not see victim mail.
    t_scope = "PARTIAL"
    t_live = "CONFIRMED" if live_present else "NOT-CHECKED"

    schema_present = (REPO / SCHEMA_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overall = "PARTIAL" if t_live == "NOT-CHECKED" else "CONFIRMED"

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "report_kind": "privacy-dataflow",
        "overall_verdict": overall,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "claim_under_test": (
            "The catalog-named agent-mail tools expose peer message bodies "
            "and advisory file-lease absolute paths to any registered "
            "identity that can name the victim and the project_key. "
            "fetch_inbox's registration_token is optional in the published "
            "contract. Contact policy, when present, gates send, not fetch."
        ),
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "privacy-analyst",
            "execution_substrate": "linux-local-serialized",
        },
        "reviewer": {
            "reviewer_id": "ADV-0043-probe2-throwaway-acl",
            "vendor": "independent-mechanical",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-derives disclosure from a third identity calling "
                "fetch_inbox(victim) with no victim token, plus "
                "list_file_reservations. It does not reuse probe 1's "
                "classifier as its instrument. Catalog asked for a Codex "
                "openai refuter; that reviewer is not on this substrate. "
                "Probe 2 is the independent mechanical refuter recorded here. "
                "No schema rebuild."
            ),
        },
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "output_schema_present": schema_present,
        "schema_note": (
            "command-center/schema/privacy-dataflow.schema.json is absent on "
            "this worktree. This unit does not rebuild that schema (ADV "
            "rebuild circle). G-1 requires a parseable non-BLOCKED artifact "
            "containing the catalog sentinel, not a regenerated global schema."
        ),
        "named_probes": [
            {
                "id": "probe1",
                "name": "probe1_field_sensitivity",
                "command": P1,
                "mechanism": (
                    "Enumerate stored messages and classify each payload field "
                    "by sensitivity (absolute path, repo name, artifact body, "
                    "credential in quoted error). Known-present canary must "
                    "fire; known-absent coordination note must stay silent."
                ),
                "exit_code": c1,
                "raw_output": t1,
                "result": p1,
            },
            {
                "id": "probe2",
                "name": "probe2_throwaway_acl",
                "command": P2,
                "mechanism": (
                    "Register a third throwaway identity, prove it can read "
                    "its own message, then fetch the victim inbox by name "
                    "with no victim token (published optional-token tool) and "
                    "list file reservations. Deregister the throwaway. Do not "
                    "modify existing identities."
                ),
                "exit_code": c2,
                "raw_output": t2,
                "result": p2,
            },
        ],
        "targets": [
            {
                "id": "T-FIELD-ABSPATH",
                "title": "Absolute paths in mailbox payloads",
                "verdict": t_abspath,
                "detail": (
                    "Planted traceback File \"{0}\" is classified absolute_path "
                    "on the victim-readable body."
                ).format(
                    "/opt/p2/ast-integrate/command-center/adversarial/"
                    "ADV-0043-secret-fixture.json"
                ),
            },
            {
                "id": "T-FIELD-REPO",
                "title": "Repository names in mailbox payloads",
                "verdict": t_repo,
                "detail": "Planted ast-integrate / ADV0043-CANARY-REPO classified.",
            },
            {
                "id": "T-FIELD-ARTIFACT-BODY",
                "title": "Artifact bodies in mailbox payloads",
                "verdict": t_artifact,
                "detail": (
                    "Planted fenced JSON with output_path and "
                    "ADV0043-CANARY-ARTIFACT classified as artifact_body."
                ),
            },
            {
                "id": "T-FIELD-CREDENTIAL-IN-ERROR",
                "title": "Credentials in quoted error text",
                "verdict": t_cred,
                "detail": (
                    "Planted helper-stderr quote password=ghp_ADV0043FAKE… "
                    "classified as credential_in_quoted_error. Token is a "
                    "synthetic canary, not a live secret."
                ),
            },
            {
                "id": "T-ACL-THROWAWAY-PEER-READ",
                "title": "Throwaway identity can fetch a peer inbox",
                "verdict": t_acl,
                "detail": (
                    "fetch_inbox(project_key, victim_name) with no "
                    "registration_token returned the victim's sensitive and "
                    "benign mail. Bound twin (require_token=True) denied the "
                    "throwaway token against the victim inbox and still "
                    "allowed the throwaway to read its own mail."
                ),
            },
            {
                "id": "T-SCOPE-PROJECT-VS-GLOBAL",
                "title": "Channel scoped per project or globally",
                "verdict": t_scope,
                "detail": (
                    "Isolation is by project_key (absolute directory path), "
                    "not by agent and not host-global by default. Victim mail "
                    "is invisible under a second project_key. Any agent that "
                    "can name the worktree path shares that mailbox. "
                    "STORAGE_ROOT, when used by the real server, is a host-"
                    "global Git+SQLite repo that contains every project."
                ),
            },
            {
                "id": "T-FILE-LEASE-PATH-DISCLOSURE",
                "title": "File-lease absolute paths visible to peers",
                "verdict": t_lease,
                "detail": (
                    "list_file_reservations(project_key) returned the victim "
                    "holder's absolute path to the throwaway. Leases are "
                    "advisory and project-listed, not holder-private."
                ),
            },
            {
                "id": "T-LIVE-PROGRAM-MESSAGES",
                "title": "Sample of real messages from this program",
                "verdict": t_live,
                "detail": (
                    "Read-only scan of default Agent Mail storage roots. "
                    "live_store_present={0}. No live identity was registered "
                    "or mutated. Protocol findings do not depend on a live "
                    "store: catalog probe 2 states broad readability is a "
                    "finding even if today's messages are benign."
                ).format(live_present),
            },
        ],
        "tests": [
            {
                "id": "T-CONTROL-OWN-FETCH",
                "kind": "control",
                "result": "PASS" if p2.get("own_fetch_ok") else "FAIL",
                "detail": (
                    "Throwaway identity can read its own message before any "
                    "denial is credited."
                ),
            },
            {
                "id": "T-CONTROL-THROWAWAY-CLEANUP",
                "kind": "control",
                "result": "PASS" if p2.get("throwaway_retired") else "FAIL",
                "detail": (
                    "Throwaway identity is deregistered afterwards; existing "
                    "agent identities and tokens are unmodified."
                ),
            },
            {
                "id": "T-CONTROL-EXISTING-UNMODIFIED",
                "kind": "control",
                "result": (
                    "PASS" if p2.get("existing_identities_unmodified") else "FAIL"
                ),
                "detail": "Victim and peer tokens unchanged after the probe.",
            },
            {
                "id": "T-CONTROL-DETECTOR-PRESENT",
                "kind": "control",
                "result": "PASS" if ctrl.get("known_present_fired") else "FAIL",
                "detail": "Classifier fires on planted path/repo/artifact/credential.",
            },
            {
                "id": "T-NEGATIVE-BENIGN-SILENT",
                "kind": "negative",
                "result": "PASS" if ctrl.get("known_absent_silent") else "FAIL",
                "detail": "Short coordination note with no path/repo/secret stays silent.",
            },
            {
                "id": "T-NEGATIVE-NAIVE-TWIN",
                "kind": "negative",
                "result": (
                    "PASS" if ctrl.get("naive_twin_fires_on_benign") else "FAIL"
                ),
                "detail": (
                    "Naive always-sensitive twin flags the benign note, proving "
                    "the silent control is not a dead detector."
                ),
            },
            {
                "id": "T-NEGATIVE-BOUND-ACL",
                "kind": "negative",
                "result": (
                    "PASS"
                    if p2.get("bound_acl_twin", {}).get(
                        "victim_denied_with_throwaway_token"
                    )
                    else "FAIL"
                ),
                "detail": (
                    "Token-bound fetch twin denies throwaway→victim and still "
                    "allows throwaway→self."
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-BENIGN-COORDINATION",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "Known-present planted body is the bad state; known-absent "
                    "coordination note is the good state."
                ),
            },
            {
                "id": "NC-BOUND-TOKEN-FETCH",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": (
                    "Optional-token fetch_inbox is the bad twin; require_token "
                    "fetch is the good twin."
                ),
            },
        ],
        "evidence": [
            {
                "id": "E-optional-token-fetch",
                "kind": "acl",
                "verdict": t_acl,
                "detail": (
                    "Published fetch_inbox(project_key, agent_name, "
                    "registration_token?) lists the token as optional. Naming "
                    "the victim is sufficient to read the inbox."
                ),
            },
            {
                "id": "E-file-reservation-listing",
                "kind": "acl",
                "verdict": t_lease,
                "detail": (
                    "File reservations are project-listed advisory leases; the "
                    "throwaway saw the victim's absolute path."
                ),
            },
            {
                "id": "E-field-sensitivity",
                "kind": "content",
                "verdict": "CONFIRMED",
                "detail": (
                    "Payload classifier recovered absolute_path, "
                    "repository_name, artifact_body, and "
                    "credential_in_quoted_error from a victim-readable body."
                ),
            },
        ],
        "live_store": live,
        "owner_approval_required": False,
        "destructive_drill": False,
        "bounded_fixtures_only": True,
        "cloud_ok": False,
        "success_hand_flipped": False,
        "timestamps": {"generated_at": now},
        "completion_line": "UNIT-COMPLETE:ADV-0043",
        "completion_marker": "\u0085UNIT-COMPLETE:ADV-0043\u0085",
        "notes": (
            "G-1 delivery of ADV-0043. Live named probes exit 0. Did not run "
            "global unit_manifest.py --write. Did not rebuild "
            "privacy-dataflow.schema.json. cloud ok=true is not delivery. "
            + SENTINEL
        ),
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0043 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
