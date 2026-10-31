r"""_i1_gate_proof.py -- ONE executable end-to-end check for the H5 integration.

It fails if ANY link in the chain is missing, and each link is a separate arm so a failure
names which one broke:

  WIRING   the commands are PARSED OUT OF `.github/workflows/hook-audit.yml`, never
           hardcoded here. Unwire the gate and this script stops running it, the
           `gate_is_wired` assertion goes False, and the proof fails. A proof that runs its
           own hardcoded copy of the command would stay green through an unwiring -- it would
           be measuring the script, not the integration.
  DEPTH    the clone uses the fetch-depth the workflow actually declares, read from the same
           YAML. `_b10_ci_proof.py` cloned at FULL depth while `actions/checkout` defaults to
           1, so its "4/4 green in a fresh clone" was emitted under both "runner-green" and
           "reds on a shallow checkout" -- and reality already refuted it (commit e0f5ba1c:
           "FAILED:cite-gate-test cannot read the pinned pre-round-3 blob 66855eed4857").
           A local-PATH clone makes git IGNORE --depth, so the clone goes through a file://
           URL and a control asserts the depth took effect.
  ARM-C    PRE-fix documents + the PRE-R5 gate blob -> must be GREEN. This is the positive
           control that the hole was real and ungated. Without it, ARM-A's red would be
           indistinguishable from a rule that fails everything.
  ARM-D    the same PRE-fix documents with ONE CITED value mutated + the PRE-R5 gate ->
           must be RED. Without this, ARM-C's green could mean "the old gate is dead in this
           clone" rather than "the old gate cannot see a verdict count". A silence that is
           silent in both states measures nothing.
  ARM-A    PRE-fix documents + the SHIPPED gate -> must be RED naming UNCITED-VERDICT-COUNT.
           This is "show it going red without the fix", on the real content, not a synthetic.
  ARM-B    the clone's own documents + the SHIPPED gate -> must be GREEN.
  WIRED    every command the workflow declares, run in that clone with HOME and USERPROFILE
           redirected to a nonexistent directory (control first: the redirection must bite).

The PRE-fix documents are pinned as BLOB shas, not `HEAD~1`: this is a worktree four lanes
commit into, so `HEAD~1` drifts onto a sibling's commit between one run and the next -- a
defect this program has already shipped once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "command-center" / "hook-audit"
WORKFLOW = REPO / ".github" / "workflows" / "hook-audit.yml"

# The documents as they stood BEFORE the H5 fix, and the gate as it stood before H5.
PRE_FIX_BLOBS = {
    "docs/hook-audit/HOOK-AUDIT.md": "479d39378ce63fc311adad533da4bd620dffa57f",
    "docs/hook-audit/GROUNDING.md": "45467ec3bd23f18da87150dec4edb4d5d8c92ae8",
}
PRE_R5_GATE_BLOB = "ff46af27783f4620cc27ec0bb71f1da86fe32a4f"
GATE_REL = "command-center/hook-audit/check_citations.py"


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=900,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or ""))[-4000:]


def blob(sha: str) -> str:
    p = subprocess.run(
        ["git", "cat-file", "-p", sha], cwd=str(REPO), capture_output=True, timeout=60
    )
    if p.returncode != 0 or not p.stdout.strip():
        raise SystemExit(f"FAILED:gate-proof cannot read pinned blob {sha[:12]}")
    return p.stdout.decode("utf-8", "replace")


def workflow_commands() -> tuple[list[str], int | None, bool]:
    """-> (run: commands, declared fetch-depth, whether the gate is among the commands).

    Parsed, not hardcoded. This is the assertion that the work is REACHABLE: if a future edit
    drops the citation gate from CI, `gate_is_wired` goes False here.
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    depth: int | None = None
    cmds: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            with_ = step.get("with") or {}
            if "fetch-depth" in with_:
                depth = int(with_["fetch-depth"])
            if isinstance(step.get("run"), str):
                cmds.append(step["run"].strip())
    return cmds, depth, any(GATE_REL in c for c in cmds)


def main() -> int:
    out: dict[str, object] = {"controls": {}, "arms": {}, "wired": []}
    cmds, depth, wired = workflow_commands()
    out["workflow_commands"] = cmds
    out["declared_fetch_depth"] = depth
    out["gate_is_wired"] = wired
    if not wired:
        # Deliberately WITHOUT writing I1-GATE-PROOF.json. That file is tracked, so a stub
        # written on this fail path would overwrite committed evidence with a partial record
        # -- the exact defect round 5 gated in test_failpath_evidence.py, and this script
        # shipped it: the regression went red the moment the evidence file became tracked.
        # Leaving the last good measurement in place is the correct failure mode; the reason
        # goes to stdout, where a terminal state belongs.
        print(
            "FAILED:gate-proof the citation gate is NOT among the commands "
            f"{WORKFLOW.name} declares -- the rule may work and it is not reachable. "
            f"Parsed steps: {cmds}"
        )
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="i1-gate-proof-"))
    try:
        clone = tmp / "clone"
        # file:// so --depth is HONOURED. A local-path clone silently ignores it, which is
        # how a depth control can pass while measuring a full clone.
        url = "file:///" + str(REPO).replace("\\", "/").lstrip("/")
        argv = ["git", "clone", "--quiet"]
        if depth and depth > 0:
            argv += ["--depth", str(depth)]
        argv += [url, str(clone)]
        rc_clone, tail_clone = run(argv, tmp, dict(os.environ))
        if rc_clone != 0:
            print(f"FAILED:gate-proof clone failed rc={rc_clone}\n{tail_clone}")
            return 1
        n_commits = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(clone),
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout.strip()
        out["commits_in_clone"] = int(n_commits or 0)
        # C1: the declared depth actually took effect. A depth that does not bite proves
        # nothing about how the runner will check this repo out.
        out["controls"]["C1_depth_took_effect"] = (
            out["commits_in_clone"] == 1 if depth == 1 else out["commits_in_clone"] > 1
        )

        env = dict(os.environ)
        env.pop("HOOK_AUDIT_REPO", None)
        fake_home = str(tmp / "nonexistent-home")
        env["HOME"] = fake_home
        env["USERPROFILE"] = fake_home
        env["PYTHONIOENCODING"] = "utf-8"
        # C2: the HOME redirection bites. Verified in the CHILD process, not assumed.
        rc_h, out_h = run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path;print(Path.home());"
                "print((Path.home()/'.claude').exists())",
            ],
            clone,
            env,
        )
        out["controls"]["C2_home_redirection_bites"] = (
            rc_h == 0 and "nonexistent-home" in out_h and "False" in out_h
        )

        # C3: the clone really carries the files under test.
        out["controls"]["C3_clone_has_the_gate"] = (clone / GATE_REL).is_file()

        old_gate = tmp / "pre_r5_gate.py"
        old_src = blob(PRE_R5_GATE_BLOB)
        # C4: the control gate is genuinely the PRE-fix one. Comparing the new gate with
        # itself is the failure this pin exists to prevent.
        out["controls"]["C4_control_gate_lacks_the_fix"] = (
            "UNCITED-VERDICT-COUNT" not in old_src
        )
        old_gate.write_text(old_src, encoding="utf-8")

        shipped = clone / GATE_REL
        post_docs = {
            rel: (clone / rel).read_text(encoding="utf-8") for rel in PRE_FIX_BLOBS
        }
        pre_docs = {rel: blob(sha) for rel, sha in PRE_FIX_BLOBS.items()}

        def put(docs: dict[str, str]) -> None:
            for rel, text in docs.items():
                (clone / rel).write_text(text, encoding="utf-8", newline="")

        genv = dict(env)
        genv["HOOK_AUDIT_REPO"] = str(clone)

        # ARM-C: pre-fix documents, pre-fix gate -> GREEN (the hole was ungated).
        put(pre_docs)
        rc_c, tail_c = run([sys.executable, str(old_gate)], clone, genv)
        out["arms"]["C_prefix_docs_prefix_gate_rc"] = rc_c

        # ARM-D: the same, with one CITED value mutated -> RED (the old gate was alive).
        mutated = dict(pre_docs)
        target = "docs/hook-audit/HOOK-AUDIT.md"
        m = re.search(r"(<!--\s*cite:[^>]*?value=)(\d+)", mutated[target])
        if not m:
            print("FAILED:gate-proof no cited value found to mutate -- ARM-D is blind")
            return 1
        mutated[target] = (
            mutated[target][: m.start(2)]
            + str(int(m.group(2)) + 4242)
            + mutated[target][m.end(2) :]
        )
        put(mutated)
        rc_d, _tail_d = run([sys.executable, str(old_gate)], clone, genv)
        out["arms"]["D_mutated_citation_prefix_gate_rc"] = rc_d

        # ARM-A: pre-fix documents, SHIPPED gate -> RED naming the rule.
        put(pre_docs)
        rc_a, tail_a = run([sys.executable, str(shipped)], clone, genv)
        out["arms"]["A_prefix_docs_shipped_gate_rc"] = rc_a
        out["arms"]["A_names_the_rule"] = "UNCITED-VERDICT-COUNT" in tail_a
        out["arms"]["A_names_both_documents"] = (
            "HOOK-AUDIT.md" in tail_a and "GROUNDING.md" in tail_a
        )

        # ARM-B: the clone's own documents, SHIPPED gate -> GREEN.
        put(post_docs)
        rc_b, tail_b = run([sys.executable, str(shipped)], clone, genv)
        out["arms"]["B_shipped_docs_shipped_gate_rc"] = rc_b

        # ARM-E: the DEPTH link's distinguishing control. C1 only asserts that the declared
        # depth took effect; it cannot tell a proxy that is SENSITIVE to depth from one that
        # would report green either way -- which is exactly how `_b10_ci_proof.py` certified a
        # workflow that then went red on its first real run. So clone at depth 1 regardless of
        # what the workflow declares and require the pinned-blob step to FAIL there. If this
        # arm comes back green, this script cannot reproduce the shallow-checkout failure and
        # its verdict on fetch-depth means nothing.
        shallow = tmp / "shallow"
        rc_s, tail_s = run(
            ["git", "clone", "--quiet", "--depth", "1", url, str(shallow)],
            tmp,
            dict(os.environ),
        )
        out["arms"]["E_shallow_clone_rc"] = rc_s
        n_shallow = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=str(shallow),
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout.strip()
        out["arms"]["E_commits_in_shallow_clone"] = int(n_shallow or 0)
        senv = dict(env)
        senv["HOOK_AUDIT_REPO"] = str(shallow)
        rc_e, tail_e = run(
            [sys.executable, "command-center/hook-audit/test_citation_gate.py"],
            shallow,
            senv,
        )
        out["arms"]["E_pinned_blob_step_rc_at_depth_1"] = rc_e
        out["arms"]["E_names_the_missing_blob"] = "cannot read" in tail_e
        depth_sensitive = (
            out["arms"]["E_commits_in_shallow_clone"] == 1
            and rc_e != 0
            and out["arms"]["E_names_the_missing_blob"]
        )
        out["controls"]["C5_proxy_is_sensitive_to_depth"] = depth_sensitive

        # ARM-F: the WIRING link's red-proof. The suite asserts that CI still declares the
        # gate; this arm removes that declaration and requires the suite to go RED. Done in
        # the CLONE, never in the shared worktree -- four lanes commit into this tree and a
        # mutated workflow sitting there for even ten seconds is one `git add` away from
        # shipping. Restored immediately afterwards and re-run, so a green ARM-F cannot be a
        # suite that was already broken.
        wf_clone = clone / ".github" / "workflows" / "hook-audit.yml"
        wf_orig = wf_clone.read_text(encoding="utf-8")
        wf_cut = "\n".join(
            ln
            for ln in wf_orig.splitlines()
            if not (
                ln.strip().startswith("run:")
                and GATE_REL in ln
                and "--self-test" not in ln
            )
        )
        out["arms"]["F_unwired_a_step"] = wf_cut != wf_orig
        wf_clone.write_text(wf_cut, encoding="utf-8", newline="")
        rc_f, tail_f = run(
            [sys.executable, "command-center/hook-audit/test_citation_gate.py"],
            clone,
            genv,
        )
        out["arms"]["F_suite_rc_when_unwired"] = rc_f
        # The precise case, not the loose one. `XX [WIRING check_citations.py ...` would NOT
        # fire here: removing the bare invocation leaves the `--self-test` step, so the
        # membership test stays green. That is what the first run of this arm measured, and
        # it is why the suite now asserts the two steps separately.
        out["arms"]["F_names_the_wiring_case"] = (
            "XX [WIRING the gate itself is declared" in tail_f
        )
        wf_clone.write_text(wf_orig, encoding="utf-8", newline="")
        rc_f2, _ = run(
            [sys.executable, "command-center/hook-audit/test_citation_gate.py"],
            clone,
            genv,
        )
        out["arms"]["F_suite_rc_when_restored"] = rc_f2

        # Every command the workflow declares, in the clone, with HOME redirected.
        all_green = True
        for cmd in cmds:
            argv = cmd.split()
            if argv and argv[0] in {"python", "python3"}:
                argv = [sys.executable, *argv[1:]]
            rc, tail = run(argv, clone, env)
            out["wired"].append({"cmd": cmd, "rc": rc, "tail": tail[-600:]})
            all_green = all_green and rc == 0
        out["all_wired_commands_green"] = all_green

        ok = (
            all(out["controls"].values())
            and out["arms"]["F_unwired_a_step"]
            and rc_f != 0
            and out["arms"]["F_names_the_wiring_case"]
            and rc_f2 == 0
            and rc_c == 0
            and rc_d == 1
            and rc_a == 1
            and out["arms"]["A_names_the_rule"]
            and out["arms"]["A_names_both_documents"]
            and rc_b == 0
            and all_green
        )
        out["verdict"] = "PASS" if ok else "FAIL"
        (EVID / "I1-GATE-PROOF.json").write_text(
            json.dumps(out, indent=1), encoding="utf-8"
        )
        for k, v in out["controls"].items():  # type: ignore[union-attr]
            print(f"CONTROL {k} = {v}")
        print(
            f"declared fetch-depth={depth}  commits_in_clone={out['commits_in_clone']}"
        )
        print(
            f"ARM-C pre-fix docs + PRE-R5 gate   rc={rc_c}  (want 0: the hole was ungated)"
        )
        print(
            f"ARM-D mutated citation + PRE-R5    rc={rc_d}  (want 1: that gate was alive)"
        )
        print(
            f"ARM-A pre-fix docs + SHIPPED gate  rc={rc_a}  (want 1: the fix catches it)"
        )
        print(f"ARM-B shipped docs + SHIPPED gate  rc={rc_b}  (want 0)")
        print(
            f"ARM-F gate step removed from the workflow  rc={rc_f} "
            f"(want non-zero), restored rc={rc_f2} (want 0)"
        )
        print(
            f"ARM-E depth-1 clone, pinned-blob step rc={rc_e} "
            f"commits={out['arms']['E_commits_in_shallow_clone']}  "
            "(want non-zero: the proxy can reproduce the shallow-checkout red)"
        )
        for w in out["wired"]:  # type: ignore[union-attr]
            print(f"  wired rc={w['rc']}  {w['cmd']}")
        print(
            f"SUCCESS:gate-proof {len(cmds)}/{len(cmds)} wired commands green in a "
            f"depth-{depth} clone, and the H5 rule reds the pre-fix documents there"
            if ok
            else "FAILED:gate-proof " + json.dumps(out["arms"])
        )
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
