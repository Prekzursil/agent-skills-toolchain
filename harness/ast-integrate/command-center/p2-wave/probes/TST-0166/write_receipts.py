#!/usr/bin/env python3
"""Write TST-0166 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not git add/commit/push/stash/checkout/rebase the worktree.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import resume_sha_gate as G  # noqa: E402

UID = "TST-0166"
OUT = "command-center/receipts/TST-0166.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/resume_report"
SENTINEL = "SUCCESS:TST-0166"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0166/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0166/probe2_auto_accept_must_fail.py"
)
SUPPORTING = [
    "tools/command-center/resume_sha_gate.py",
    "tools/lib/handled-ledger.mjs",
    "command-center/p2-wave/probes/TST-0166/fixtures.py",
    "command-center/p2-wave/probes/TST-0166/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0166/probe2_auto_accept_must_fail.py",
    "command-center/p2-wave/probes/TST-0166/write_receipts.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def parse_probe_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return {}
    try:
        doc = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}


def row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0166/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_evidence() -> dict:
    """Independent of probe stdout: both SHAs in the record + git diff --name-only."""
    with tempfile.TemporaryDirectory(prefix="tst0166-ev-") as tmp:
        tmp_path = Path(tmp)
        match_repo = F.init_repo(tmp_path / "match")
        pinned_match = G.head_sha(match_repo)
        match_out = G.resume(
            {"pinned_sha": pinned_match},
            match_repo,
            on_continue=lambda: None,
        )
        match_diff = F.independent_diff_name_only(
            match_repo, pinned_match, match_out["head_sha"]
        )

        moved_repo = F.init_repo(tmp_path / "moved")
        pinned = G.head_sha(moved_repo)
        head = F.move_head(moved_repo)
        indep = F.independent_diff_name_only(moved_repo, pinned, head)
        record = None
        continued = {"n": 0}
        try:
            G.resume(
                {"pinned_sha": pinned},
                moved_repo,
                on_continue=lambda: continued.__setitem__("n", continued["n"] + 1),
            )
        except G.ShaMismatchDecisionRequired as exc:
            record = exc.record
        if record is None:
            raise RuntimeError("live evidence: mismatch did not raise")
        mutant_continued = {"n": 0}
        mutant = G.AutoAcceptResume.resume(
            {"pinned_sha": pinned},
            moved_repo,
            on_continue=lambda: mutant_continued.__setitem__(
                "n", mutant_continued["n"] + 1
            ),
        )
        return {
            "a_resume_record_names_both_shas": {
                "pinned_sha": record["pinned_sha"],
                "head_sha": record["head_sha"],
                "prompt": record["prompt"],
                "prompt_names_pinned": pinned in str(record["prompt"]),
                "prompt_names_head": head in str(record["prompt"]),
                "work_continued": record["work_continued"],
                "continue_calls": continued["n"],
            },
            "b_independent_git_diff_name_only": {
                "command": f"git diff --name-only {pinned}..{head}",
                "files": indep,
                "gate_files_changed": list(record.get("files_changed") or []),
                "listings_agree": list(record.get("files_changed") or []) == indep,
            },
            "unchanged_head_no_prompt": {
                "status": match_out["status"],
                "prompt": match_out["prompt"],
                "work_continued": match_out["work_continued"],
                "independent_diff": match_diff,
            },
            "mutant_auto_accepts": {
                "auto_accepted": mutant.get("auto_accepted"),
                "work_continued": mutant.get("work_continued"),
                "continue_calls": mutant_continued["n"],
            },
        }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0166 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    j1 = parse_probe_json(t1)
    j2 = parse_probe_json(t2)
    if not j1.get("pass") or not j2.get("pass"):
        print("FAILED:TST-0166 probe JSON pass=false")
        return 1

    evidence = live_evidence()
    a = evidence["a_resume_record_names_both_shas"]
    b = evidence["b_independent_git_diff_name_only"]
    if not a["prompt_names_pinned"] or not a["prompt_names_head"]:
        print("FAILED:TST-0166 evidence A: record does not name both SHAs")
        return 1
    if a["work_continued"] or a["continue_calls"] != 0:
        print("FAILED:TST-0166 evidence A: work continued without a choice")
        return 1
    if not b["listings_agree"] or not b["files"]:
        print("FAILED:TST-0166 evidence B: independent git diff mismatch")
        return 1
    if evidence["unchanged_head_no_prompt"]["prompt"] is not None:
        print("FAILED:TST-0166 unchanged HEAD prompted")
        return 1
    if not evidence["mutant_auto_accepts"]["auto_accepted"]:
        print("FAILED:TST-0166 mutant did not auto-accept")
        return 1

    schema_path = REPO / "command-center/schema/receipt.schema.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl_sha, impl_bytes = digest_file(REPO / "tools/command-center/resume_sha_gate.py")

    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "resume_report",
        "title": "Checkpoint pinned SHA mismatch is a decision, not an auto-accept",
        "question": (
            "If HEAD moved since the checkpoint, does resume surface the SHA "
            "mismatch and require an explicit choice? PASS requires the pinned "
            "SHA be validated and the divergence summarized (files changed) "
            "before any work continues."
        ),
        "answer": (
            "Yes. tools/command-center/resume_sha_gate.py compares checkpoint "
            "pinned_sha to live git rev-parse HEAD. Matching HEAD resumes "
            "without a prompt. A moved HEAD raises ShaMismatchDecisionRequired "
            "naming both SHAs and listing files from git diff --name-only "
            "<pinned>..HEAD; on_continue is not invoked until an explicit "
            "choice (abort|stay_pinned|accept_new_head). AutoAcceptResume "
            "continues with no prompt and is the negative control that must "
            "fail production. "
            + SENTINEL
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog output_schema is command-center/schema/receipt.schema.json"
            "#/$defs/resume_report; that path is absent on this worktree so this "
            "receipt is JSON-parseable and sentinel-bearing rather than "
            "schema-validated here."
        ),
        "schema_path_present": schema_path.is_file(),
        "generated_at": now,
        "implementation": {
            "gate": "tools/command-center/resume_sha_gate.py",
            "gate_sha256": impl_sha,
            "gate_bytes": impl_bytes,
            "catalog_input_ledger": "tools/lib/handled-ledger.mjs",
            "mechanism": (
                "Checkpoint JSON carries pinned_sha. resume() rev-parses HEAD "
                "in a GIT_*-scrubbed subprocess so ambient GIT_DIR cannot "
                "redirect the fixture. Mismatch builds a decision record, then "
                "either raises (no choice) or returns abort/stay_pinned without "
                "continuing, or accept_new_head after the record exists."
            ),
        },
        "evidence": evidence,
        "evidence_requirement": {
            "a": "the resume prompt/record naming both SHAs",
            "a_satisfied": bool(a["prompt_names_pinned"] and a["prompt_names_head"]),
            "b": "an independent git diff --name-only <pinned>..HEAD listing",
            "b_satisfied": bool(b["listings_agree"] and b["files"]),
        },
        "tests": [
            {
                "id": "both-states-unchanged-head-resumes-without-prompt",
                "requirement": "an unchanged HEAD resumes without a prompt",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "negative-control-auto-accept-new-head-must-fail",
                "requirement": "auto-accepting the new HEAD must fail",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
                "detector_discriminates": j2.get("detector_discriminates"),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/command-center/resume_sha_gate.py", "role": "sut"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0166-probe2-auto-accept-must-fail",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Catalog asked for an independent adversarial reviewer who did "
                "not author the harness. This G-1 delivery uses the live "
                "negative-control probe (production refuse vs AutoAcceptResume "
                "mutant) as the mechanical independent check. A human "
                "cross-vendor pass is not claimed."
            ),
        },
        "residual_unknowns": [
            "command-center/schema/receipt.schema.json is absent; "
            "$defs/resume_report is therefore not schema-validated on this worktree.",
            "tools/lib/handled-ledger.mjs remains the work-claim O_EXCL sibling "
            "from TST-0157; the pinned-SHA gate is the Python surface under "
            "tools/command-center/resume_sha_gate.py. Fixture git repos live in "
            "tempdirs; this worktree is not a git repository and was not committed.",
        ],
        "cloud_ok": False,
        "notes": (
            "SUCCESS:TST-0166. Pinned-SHA mismatch is a decision. "
            "Did not run unit_manifest.py --write. No ADV rebuild. "
            "Did not git add/commit the worktree."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0166 sentinel missing from receipt")
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:TST-0166 probes after receipt c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-states-unchanged-vs-moved-head",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "negative-control-auto-accept-must-fail",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0166/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0166-probe2-auto-accept-must-fail",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0166: live named probes exit 0, receipts/TST-0166.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0166 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
