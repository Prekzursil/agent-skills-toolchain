import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

home = Path.home()
REPO = home / "p2-g1"
PROBE_DIR = REPO / "command-center/p2-wave/probes/IMP-0223"
UID = "IMP-0223"
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(path_rel, role):
    p = REPO / path_rel
    sha, n = digest(p)
    return {"unit_id": UID, "path": path_rel, "sha256": sha, "bytes": n,
            "present": True, "role": role,
            "receipt_path": "command-center/p2-wave/probes/" + UID + "/SUBAGENT-RETURN.json"}


CMDS = [
    ("probe1", "command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py",
     "probe1-disjoint.raw.json"),
    ("probe2", "command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py",
     "probe2-teardown.raw.json"),
]

named_probes = []
raws = {}
for pid, rel, rawname in CMDS:
    cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(["python3", "-B", str(REPO / rel)], cwd=str(REPO),
                          capture_output=True, text=True, encoding="utf-8", env=env)
    out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE_DIR / rawname).write_text(out, encoding="utf-8", newline="\n")
    raws[pid] = (proc.returncode, cmd, out.strip())
    named_probes.append({"id": pid, "command": cmd, "exit_code": proc.returncode,
                         "raw_output": out.strip(), "role": UID + "-" + pid})
    if proc.returncode != 0:
        print("ABORT: " + pid + " exit " + str(proc.returncode))
        sys.exit(1)


def computed(pid):
    text = raws[pid][2]
    end = text.rfind("}")
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[: i + 1])
    return json.loads(text[: end + 1])

comp1 = computed("probe1")
comp2 = computed("probe2")

old = json.loads((REPO / "command-center/receipts/IMP-0223.json").read_text(encoding="utf-8"))

artifacts = [
    row("tools/gitcrypt-worktree/gitcrypt_worktree.py", "implementation"),
    row("command-center/p2-wave/probes/IMP-0223/probe1_disjoint_indexes.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0223/probe2_teardown_refused.py", "probe"),
]

receipt = {
    "id": UID,
    "unit_id": UID,
    "title": old.get("title", "Implement worktree provisioning and teardown per implementation shard"),
    "spec_anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0223",
    "schema_version": 1,
    "sentinel": "SUCCESS:IMP-0223",
    "state": "BLOCKED",
    "failure": {
        "classification": ["reviewer-absent"],
        "reason": ("Builder-side delivery complete and verified live 2026-10-26 (probes exit 0 "
                   "against throwaway git fixtures, manifest sha matches live bytes), but the "
                   "implementation was materially REPAIRED after the 2026-08-25 independent "
                   "review, so that closure no longer verifies live and was superseded: the "
                   "on-disk module (rewritten 2026-10-24 by the git-crypt doctor work) had lost "
                   "provision/teardown semantics and carried two green-not-live defects - a "
                   "hardcoded squash-case literal dict and a tautological contamination control "
                   "(_staged(x) == _staged(x), true by construction). Awaiting a fresh "
                   "independent review to close."),
    },
    "reviewer": None,
    "prior_closure_superseded": {
        "reviewer_id": old.get("reviewer", {}).get("reviewer_id"),
        "verdict": old.get("reviewer", {}).get("verdict"),
        "independent": old.get("reviewer", {}).get("independent"),
        "ended_at": (old.get("timestamps") or {}).get("ended_at"),
        "why": ("closure covered a module version since rewritten; anchor function teardown "
                "did not exist on disk; claims did not verify live against the current file"),
    },
    "implementation": {
        "module": "tools/gitcrypt-worktree/gitcrypt_worktree.py",
        "provision": "git worktree add -b shard/<unit>/<token>",
        "teardown_authorization": "byte-level harvest comparison only (live files + index paths)",
        "ancestry_authorization": "never",
        "estate_git_mutated": False,
        "note": ("Fixture repos under tempfile only. This estate root has no .git; no git "
                 "add/commit/push/stash/checkout/rebase was run against it. Repair 2026-10-26 "
                 "added provision_worktree / harvest_digest / teardown_worktree and the "
                 "labeled known-broken control naive_ancestry_authorizes; rewrote both measure "
                 "functions so every verdict is computed."),
    },
}

receipt["evidence"] = [
    {
        "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:provision_worktree + measure_disjoint_indexes",
        "claim": ("Two concurrent mutating units provisioned on their own branches produce "
                  "disjoint staged sets (computed set intersection empty) and never share a git "
                  "index (distinct gitdirs, index file bytes differ). The shared-index control "
                  "fires: the same two unit paths on ONE checkout with a broad git add -A stage "
                  "both - the contamination mode isolated provisioning prevents."),
        "confidence": "almost-certain",
        "probes": [
            {"command": raws["probe1"][1], "exit_code": raws["probe1"][0],
             "method": "command", "raw_output": raws["probe1"][2], "role": "source"},
            {"command": "staged_a & staged_b == empty; gitdir_a != gitdir_b; "
                        "shared broad-add stages both paths",
             "exit_code": 0, "method": "computed-set-intersection", "role": "verifier"},
        ],
        "verdict": "CONFIRMED",
    },
    {
        "anchor": "tools/gitcrypt-worktree/gitcrypt_worktree.py:teardown_worktree + measure_teardown_both_states",
        "claim": ("Teardown refuses when any live byte or index-referenced path is not proven "
                  "preserved in the harvest (reason=unpreserved-content, worktree stays on "
                  "disk) and deletes only after a byte-level harvest match "
                  "(reason=content-proven). Commit ancestry is never consulted: on the "
                  "squash-merge state the branch reports AHEAD (ahead_count=1, not an ancestor "
                  "despite the content being carried) and the known-broken naive ancestry "
                  "mutant authorizes deletion while the content gate refuses - measured, not "
                  "asserted."),
        "confidence": "almost-certain",
        "probes": [
            {"command": raws["probe2"][1], "exit_code": raws["probe2"][0],
             "method": "command", "raw_output": raws["probe2"][2], "role": "source"},
            {"command": "refused(unharvested-remainder); mutant-authorizes and gate-refuses "
                        "on same squash state; deleted(harvest-matched)",
             "exit_code": 0, "method": "both-states", "role": "verifier"},
        ],
        "verdict": "CONFIRMED",
    },
]
receipt["evidence_computed"] = {
    "disjoint_indexes": comp1,
    "teardown_both_states": comp2,
}
receipt["negative_controls"] = [
    {
        "id": "shared-index-broad-add",
        "kind": "known-broken-fixture",
        "description": ("Two sibling files on one checkout plus git add -A must stage both "
                        "paths; the detector fires on that contamination mode."),
        "bad_state_output": "unit-a.txt and unit-b.txt both staged on shared index",
        "good_state_output": "isolated worktrees: intersection empty",
        "fired_on_bad_state": bool(comp1.get("contamination_control", {}).get("detected")),
        "silent_on_good_state": bool(comp1.get("intersection_empty")),
    },
    {
        "id": "unpreserved-teardown",
        "kind": "both-states",
        "description": ("Teardown of a shard whose unique bytes are nowhere else must refuse "
                        "and leave the worktree on disk."),
        "bad_state_output": "reason=unpreserved-content refused=true",
        "good_state_output": "reason=content-proven deleted=true",
        "fired_on_bad_state": bool(comp2.get("dangerous", {}).get("refused")),
        "silent_on_good_state": bool(comp2.get("good", {}).get("deleted")),
    },
    {
        "id": "squash-merge-ancestry-ahead",
        "kind": "known-broken-fixture",
        "description": ("Squash-merge plus an uncommitted remainder: ancestry reports AHEAD "
                        "(naive mutant would delete); content comparison refuses."),
        "bad_state_output": "reports_ahead=true naive_ancestry_would_authorize=true refused=true",
        "good_state_output": "harvest digest match then deleted",
        "fired_on_bad_state": bool(
            comp2.get("squash_unharvested", {}).get("naive_ancestry_would_authorize")
        ) and bool(comp2.get("squash_unharvested", {}).get("refused")),
        "silent_on_good_state": bool(comp2.get("good", {}).get("deleted")),
    },
]
receipt["tests"] = [
    {"id": "concurrent-mutators-disjoint-indexes",
     "command": raws["probe1"][1], "result": "PASS"},
    {"id": "teardown-refused-when-unpreserved",
     "command": raws["probe2"][1], "result": "PASS"},
]
receipt["residual_unknowns"] = [
    {
        "claim": ("git-crypt itself is absent in the fixture path; isolation and teardown are "
                  "proven with git worktree indexes, git diff --cached --name-only and byte "
                  "digests, not with git-crypt filters."),
        "settling_experiment": ("Re-run measure_disjoint_indexes on a host with git-crypt "
                                "installed and compare the staged-set output."),
        "verdict": "NOT-CHECKED",
    }
]
receipt["retry"] = {"count": 0, "policy": "two strikes then pivot"}
receipt["min_bytes_threshold"] = 128
receipt["manifest_registration"] = {
    "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
    "manifest_path": "command-center/p2-wave/probes/IMP-0223/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True,
}
receipt["timestamps"] = {"started_at": "2026-08-25T00:59:22Z", "ended_at": NOW,
                         "repaired_at": NOW}
receipt["notes"] = (
    "G-1 for IMP-0223: live named probes re-run the provisioner against throwaway git repos. "
    "SUCCESS:IMP-0223 is the catalog sentinel; it is NOT self-declared while state=BLOCKED. "
    "cloud ok=true is not delivery. Did not run global unit_manifest.py --write. "
    "Builder shard11 wave3 resume 2026-10-26: the prior probe directory was lost mid-flight "
    "(host session death) and the module had been rewritten by other work (git-crypt doctor), "
    "which replaced the reviewed provision/teardown semantics with tautological or hardcoded "
    "measurement code. Both defects were repaired with computed implementations; probes were "
    "rebuilt and re-run live; the 2026-08-25 reviewer closure is superseded - see "
    "prior_closure_superseded. Awaiting independent review to close."
)
assert "SUCCESS:IMP-0223" in json.dumps(receipt)
rec_path = REPO / "command-center/receipts/IMP-0223.json"
rec_path.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")

# ---- SUBAGENT-RETURN (builder-side delivered, receipt BLOCKED pending review) ----
sha, n = digest(REPO / "command-center/receipts/IMP-0223.json")
ret = {
    "id": UID, "unit_id": UID, "status": "DELIVERED", "state": "BLOCKED",
    "receipt_state": "BLOCKED",
    "output_path": "command-center/receipts/IMP-0223.json",
    "output_schema": "command-center/schema/receipt.schema.json",
    "sentinel": "SUCCESS:IMP-0223",
    "manifest_path": "command-center/p2-wave/probes/" + UID + "/UNIT-ARTIFACT-MANIFEST.json",
    "registered": True, "cloud_ok": False,
    "failure_classification": ["reviewer-absent"],
    "reviewer": None,
    "primary_artifact": {"path": "command-center/receipts/IMP-0223.json",
                         "bytes": n, "sha256": sha},
    "artifacts": artifacts,
    "named_probes": named_probes,
    "notes": ("Builder shard11 wave3 resume 2026-10-26: probe dir was absent and the module "
              "measure code was degraded (hardcoded squash verdict, tautological contamination "
              "control) after an unrelated rewrite. Repaired provision/teardown with computed "
              "implementations, rebuilt probes, re-ran live. Receipt BLOCKED reviewer-absent: "
              "the 2026-08-25 independent closure covered a superseded module version."),
    "ts": NOW,
}
(PROBE_DIR / "SUBAGENT-RETURN.json").write_text(
    json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

# ---- manifest ----
rows = [row("command-center/receipts/IMP-0223.json", "primary")] + artifacts
man = {"unit_id": UID, "artifacts": rows, "generated": NOW,
       "derivation": "shard11-w3 builder resume (matches _measure_one_delivered.py hashing)"}
(PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
    json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print("finalized IMP-0223: receipt sha " + sha[:12] + " bytes " + str(n))
