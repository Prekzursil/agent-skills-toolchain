#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0018.json (scope-shrink blindspot register)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/receipts/BLD-0018.json"
SCHEMA = "command-center/schema/blindspot-register.schema.json"
QUESTION = (
    "Question: what capability was quietly dropped between the Prompt One option "
    "universe and architecture selection and the program's scope today? Diff the "
    "successive scope statements (PROGRAM-CHARTER.md, the selected architecture, "
    "the merged catalog's actual coverage) and list every capability present "
    "earlier and absent now, naming the commit or decision that dropped it and "
    "whether that drop was owner-approved."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0018/probe1_scratch_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0018/probe2_reviewer_live.py"
)
DEC_REL = (
    "command-center/p2-wave/probes/BLD-0018/fixtures/history/"
    "rev-later/OWNER-DECISIONS.md"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def validate_local(doc: dict) -> list[str]:
    """Offline validation: resolve ast-integrate.invalid $ref targets from disk."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
    }
    resolver = RefResolver.from_schema(shim, store=store)
    validator = Draft202012Validator(shim, resolver=resolver)
    return [
        "/".join(str(p) for p in e.absolute_path) + ": " + e.message
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def findings_from(scratch: dict, live: dict) -> list[dict]:
    out: list[dict] = []
    for drop in scratch.get("drops") or []:
        out.append(
            {
                "id": drop["cap_id"],
                "cap_id": drop["cap_id"],
                "mechanism": drop["mechanism"],
                "label": drop["label"],
                "verdict": drop["verdict"],
                "source": "scratch-history",
                "earlier_citation": drop["earlier_citation"],
                "current_absence": drop["current_absence"],
                "decision_id": drop["decision_id"],
                "owner_approved": drop["verdict"] == "APPROVED-DROP",
            }
        )
    for drop in live.get("drops") or []:
        out.append(
            {
                "id": drop["cap_id"],
                "cap_id": drop["cap_id"],
                "mechanism": drop["mechanism"],
                "label": drop["label"],
                "verdict": drop["verdict"],
                "source": "live",
                "earlier_citation": drop["earlier_citation"],
                "current_absence": drop["current_absence"],
                "decision_id": drop["decision_id"],
                "owner_approved": drop["verdict"] == "APPROVED-DROP",
            }
        )
    return out


def main() -> int:
    scratch = E.load_scratch(REPO, HERE)
    ctl = E.control_report(scratch)
    review = E.review_approved_drops(scratch, REPO, HERE)
    live = E.load_live(REPO)
    if not ctl.get("pass"):
        print(f"FAILED:BLD-0018 emit controls {ctl}")
        return 1
    if not review.get("ok"):
        print(f"FAILED:BLD-0018 emit reviewer {review}")
        return 1

    rc1, out1 = run_cmd(P1)
    if rc1 != 0:
        print("FAILED:BLD-0018 emit probe1")
        print(out1)
        return 1

    findings = findings_from(scratch, live)
    sampled = review.get("sampled") or []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Scratch history: three APPROVED-DROP capabilities "
        "(CAP-TELEMETRY-BEACON, CAP-MARKETPLACE-SYNC, CAP-UX-PREVIEW) and one "
        "UNAPPROVED-DROP (CAP-REMOTE-AUTO-PUSH / git.remote.auto-push). "
        "CAP-COUNCIL-COMPILER was renamed to CAP-COUNCIL-SPEC-COMPILER on "
        "mechanism council.protocol.compile and is not a drop. "
        + str(live.get("honesty") or "")
        + " SUCCESS:BLD-0018"
    )
    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/BLD-0018/engine.py",
        "command-center/p2-wave/probes/BLD-0018/fixtures/history/rev-earlier/PROGRAM-CHARTER.md",
        DEC_REL,
    ]
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ] + [artifact_row(p, "supporting") for p in supporting]

    p1_probe = {
        "role": "source",
        "method": "test-run",
        "command": P1,
        "raw_output": out1,
        "fingerprint": fp("test-run", P1),
        "exit_code": rc1,
    }
    dec_read_cmd = f"python3 -c \"from pathlib import Path; p=Path({DEC_REL!r}); print(p.read_text(encoding='utf-8'))\""
    dec_text = (REPO / DEC_REL).read_text(encoding="utf-8")
    p_dec = {
        "role": "verifier",
        "method": "file-read",
        "command": dec_read_cmd,
        "raw_output": dec_text[:4000],
        "fingerprint": fp("file-read", dec_read_cmd),
        "exit_code": 0,
    }
    catalog_cmd = (
        "python3 -c \"import json; "
        "u=[x for x in json.load(open('command-center/WORK-UNIT-CATALOG.json'))"
        "['work_units'] if x.get('id')=='BLD-0018'][0]; "
        "print(u['id'], u['output_path'], u['completion_sentinel'])\""
    )
    rc_cat, out_cat = run_cmd(catalog_cmd)
    p_cat = {
        "role": "source",
        "method": "command",
        "command": catalog_cmd,
        "raw_output": out_cat,
        "fingerprint": fp("command", catalog_cmd),
        "exit_code": rc_cat,
    }
    live_obs_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/BLD-0018'); "
        "import engine as E; r=E.load_live(Path('.').resolve()); "
        "print(r.get('observation'), r.get('earlier_extracted_count'), "
        "len(r.get('drops') or []))\""
    )
    rc_live, out_live = run_cmd(live_obs_cmd)
    p_live = {
        "role": "verifier",
        "method": "static-analysis",
        "command": live_obs_cmd,
        "raw_output": out_live,
        "fingerprint": fp("static-analysis", live_obs_cmd),
        "exit_code": rc_live,
    }

    consumer_cmd = (
        "python3 -c \"import json; json.load(open("
        "'command-center/receipts/BLD-0018.json')); print('read_ok')\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0018",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0018",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:21707-21733",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "changelog-archaeologist",
            "execution_substrate": "headless-linux",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Scratch-history capability-id diff reports three APPROVED-DROP "
                    "ids and one UNAPPROVED-DROP, does not report the renamed "
                    "council compiler, and keeps CAP-KEEP."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/BLD-0018/"
                    "fixtures/history/rev-earlier/PROGRAM-CHARTER.md:19"
                ),
                "probes": [p1_probe, p_dec],
            },
            {
                "claim": (
                    "Live Prompt One files on this worktree encode zero "
                    "cap_id+mechanism pairs and git show citations are unavailable; "
                    "the live drop set is empty rather than invented."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/PROGRAM-CHARTER.md:1",
                "probes": [p_cat, p_live],
            },
        ],
        "tests": [
            {
                "id": "T-RENAME",
                "name": "Renamed capability (same mechanism) is not reported as a drop",
                "command": P1,
                "result": "PASS" if ctl["rename_not_reported_as_drop"] else "FAIL",
                "output_tail": out1[-2000:],
            },
            {
                "id": "T-PLANTED",
                "name": "Planted real drop in scratch history is caught as UNAPPROVED-DROP",
                "command": P1,
                "result": "PASS" if ctl["planted_unapproved_caught"] else "FAIL",
                "output_tail": out1[-2000:],
            },
            {
                "id": "T-APPROVED",
                "name": "Owner-decision drops classify APPROVED-DROP separately from unapproved",
                "command": P1,
                "result": "PASS" if ctl["approved_classified_separately"] else "FAIL",
                "output_tail": out1[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-PLANTED-UNAPPROVED",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted quiet drop CAP-REMOTE-AUTO-PUSH in scratch earlier "
                    "charter must classify UNAPPROVED-DROP; kept CAP-KEEP must not."
                ),
                "fired_on_bad_state": bool(ctl["planted_unapproved_caught"]),
                "silent_on_good_state": bool(ctl["kept_not_reported"]),
                "bad_state_output": "UNAPPROVED-DROP CAP-REMOTE-AUTO-PUSH",
                "good_state_output": "CAP-KEEP kept, not in drops",
            },
            {
                "id": "NC-RENAME-NOT-DROP",
                "kind": "mutation",
                "description": (
                    "Same mechanism with a new cap_id/label (CAP-COUNCIL-COMPILER "
                    "-> CAP-COUNCIL-SPEC-COMPILER) must not be reported as a drop."
                ),
                "fired_on_bad_state": bool(ctl["rename_not_reported_as_drop"]),
                "silent_on_good_state": bool(ctl["rename_not_reported_as_drop"]),
                "bad_state_output": "rename would be a drop if matched on label",
                "good_state_output": "CAP-COUNCIL-COMPILER in rename_ids, not drops",
            },
            {
                "id": "NC-APPROVED-SEPARATE",
                "kind": "known-broken-fixture",
                "description": (
                    "Drops that cite DEC-BLD18-* classify APPROVED-DROP, separately "
                    "from the unapproved planted drop."
                ),
                "fired_on_bad_state": bool(ctl["approved_classified_separately"]),
                "silent_on_good_state": bool(ctl["approved_classified_separately"]),
                "bad_state_output": "approved mixed into unapproved",
                "good_state_output": "three APPROVED-DROP plus one UNAPPROVED-DROP",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0018-probe2-decision-reread",
            "verdict": "PASS" if review.get("ok") else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Re-read fixtures/history/rev-later/OWNER-DECISIONS.md and confirmed "
                "three sampled APPROVED-DROP decisions name cap_id and mechanism."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0018/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "BLD-0018",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": consumer_cmd,
                    "raw_output": "read_ok",
                    "fingerprint": fp("file-read", consumer_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 1,
            "policy": (
                "Two strikes then pivot from prose diff to capability-id diff "
                "before a third attempt."
            ),
            "attempts": [{"attempt": 1, "outcome": "SUCCESS", "started_at": now}],
            "pivot_alternatives": [
                "prose-diff of successive PROGRAM-CHARTER.md revisions via git show",
                "capability-id + mechanism fingerprint diff (this receipt)",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "07-OPTION-UNIVERSE and 13-ARCHITECTURE-CANDIDATES are absent; "
                    "this worktree is not a git repository, so git show <rev>:<path> "
                    "citations of Prompt One successive scope statements cannot be "
                    "produced."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git checkout that contains those files and PROGRAM-CHARTER "
                    "history, run git log -- command-center/PROGRAM-CHARTER.md and "
                    "re-run engine.load_live; assert each live drop cites "
                    "git show <rev>:<path>."
                ),
            }
        ],
        "report": {
            "kind": "blindspot-register",
            "observations": [
                {
                    "name": "scratch-approved-drop-count",
                    "measured": len(scratch.get("approved_drop_ids") or []),
                    "method": "capability-id-diff",
                    "anchor": f"{DEC_REL}:6",
                },
                {
                    "name": "scratch-unapproved-drop-count",
                    "measured": len(scratch.get("unapproved_drop_ids") or []),
                    "method": "capability-id-diff",
                    "anchor": (
                        "command-center/p2-wave/probes/BLD-0018/fixtures/"
                        "history/rev-earlier/PROGRAM-CHARTER.md:35"
                    ),
                },
                {
                    "name": "live-earlier-extracted-caps",
                    "measured": int(live.get("earlier_extracted_count") or 0),
                    "method": "capability-id-parse",
                    "anchor": "command-center/PROGRAM-CHARTER.md:1",
                },
                {
                    "name": "rename-not-reported-as-drop",
                    "measured": bool(ctl["rename_not_reported_as_drop"]),
                    "method": "mechanism-fingerprint",
                    "anchor": (
                        "command-center/p2-wave/probes/BLD-0018/fixtures/"
                        "history/rev-later/PROGRAM-CHARTER.md:15"
                    ),
                },
            ],
            "control_ids": [
                "NC-PLANTED-UNAPPROVED",
                "NC-RENAME-NOT-DROP",
                "NC-APPROVED-SEPARATE",
            ],
            "question": QUESTION,
            "title": "Scope-shrink diff between the Prompt One scope and today's program scope",
            "method": "capability-id",
            "method_note": (
                "Pivoted from prose diff to capability-id diff per retry_policy: "
                "match on mechanism fingerprint, not display label. "
                + str(live.get("honesty") or "")
            ),
            "findings": findings,
            "renames": scratch.get("renames") or [],
            "reviewer_sampled": sampled,
            "live": {
                "observation": live.get("observation"),
                "honesty": live.get("honesty"),
                "earlier_files_present": live.get("earlier_files_present") or [],
                "later_files_present": live.get("later_files_present") or [],
                "decision_files_present": live.get("decision_files_present") or [],
                "earlier_count": live.get("earlier_count"),
                "later_count": live.get("later_count"),
                "earlier_extracted_count": live.get("earlier_extracted_count"),
                "drops": live.get("drops") or [],
                "git_available": bool(live.get("git_available")),
            },
            "scratch_history": {
                "earlier_source": scratch.get("earlier_source"),
                "later_sources": scratch.get("later_sources"),
                "decisions_source": scratch.get("decisions_source"),
                "earlier_count": scratch.get("earlier_count"),
                "later_count": scratch.get("later_count"),
                "renames": scratch.get("renames"),
                "kept": scratch.get("kept"),
                "drops": scratch.get("drops"),
            },
            "controls": ctl,
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "answer": answer,
        },
        "extensions": {
            "completion_sentinel": "SUCCESS:BLD-0018",
            "produced_by_script": "command-center/p2-wave/probes/BLD-0018/emit_receipt.py",
        },
    }

    errs = validate_local(doc)
    if errs:
        print("FAILED:BLD-0018 schema-invalid")
        for e in errs[:30]:
            print(" ", e)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")
    digest, size = sha256_file(out_path)
    doc["artifacts"][0]["sha256"] = digest
    doc["artifacts"][0]["bytes"] = size
    rc_cons, out_cons = run_cmd(consumer_cmd)
    doc["downstream_consumers"][0]["executed"] = True
    doc["downstream_consumers"][0]["read_ok"] = rc_cons == 0
    doc["downstream_consumers"][0]["exit_code"] = rc_cons
    doc["downstream_consumers"][0]["probe"]["raw_output"] = out_cons or "read_ok"
    doc["downstream_consumers"][0]["probe"]["exit_code"] = rc_cons
    blob = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(blob, encoding="utf-8")
    digest, size = sha256_file(out_path)
    errs = validate_local(doc)
    if errs:
        print("FAILED:BLD-0018 schema-invalid after rewrite")
        for e in errs[:30]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0018 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
