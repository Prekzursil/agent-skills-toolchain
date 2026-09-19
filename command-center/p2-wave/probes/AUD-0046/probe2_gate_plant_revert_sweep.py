#!/usr/bin/env python3
"""AUD-0046 NAMED PROBE 2: plant a matched mutation, require RED, revert, require 0.

Catalog evidence_requirement Probe 2:
  gate exit code with the planted mutation applied (must be non-zero).

Catalog tests_required:
  the sweep IS the both-states test; additionally require that the mutation is
  reverted and the gate returns to 0, proving the RED was caused by the
  mutation and not by scratch-tree contamination.

Catalog reviewer_requirement: one cross-vendor Codex reviewer who re-runs ONLY
this probe. This script is therefore self-contained: it creates its own
disposable `git worktree add --detach` scratch checkout, runs the full
plant -> RED -> revert -> GREEN cycle for each of the 8 gates named in
`fixtures/gate_cases.json`, and removes the worktree when done. It never
mutates the live tree and never depends on state left over from probe1.

Per-gate cycle, all inside the SAME scratch worktree instance (so a RED that
disappears on revert cannot be scratch-tree contamination from a fresh clone):
  1. baseline run          -- exit code must equal expected_baseline_exit (0)
  2. apply planted mutation -- matched to the exact defect class the gate's own
     docstring says it detects (see fixtures/gate_cases.json for the mapping)
  3. mutated run           -- exit code must be NON-ZERO (RED)
  4. revert the mutation   -- `git checkout --`, `git reset --hard`, or restore
     the moved file, depending on the case
  5. reverted run          -- exit code must equal expected_baseline_exit (0)
     again, in the SAME worktree instance the mutation was planted in
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe2-gate-plant-revert-sweep.json"
RAW = PROBE / "probe2-gate-plant-revert-sweep.raw.txt"
CASES_FILE = PROBE / "fixtures" / "gate_cases.json"


def run(cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"


def git(wt: Path, *args: str, timeout: int = 120) -> tuple[int, str]:
    return run(["git", *args], cwd=wt, timeout=timeout)


def make_worktree() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="aud0046-p2-"))
    wt = tmp / "wt"
    rc, out = run(
        ["git", "worktree", "add", "--detach", str(wt), "HEAD"], cwd=REPO, timeout=300
    )
    if rc != 0:
        raise RuntimeError(f"git worktree add failed rc={rc}: {out[-2000:]}")
    return wt


def remove_worktree(wt: Path) -> None:
    run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, timeout=120)


class MutationError(Exception):
    pass


def apply_mutation(wt: Path, case: dict) -> dict:
    """Apply the planted mutation; return state needed to revert it."""
    m = case["mutation"]
    if "move" in m:
        src = wt / m["move"]["from"]
        stash = Path(tempfile.mkdtemp(prefix="aud0046-moved-")) / src.name
        if not src.is_file():
            raise MutationError(f"move source missing: {src}")
        src.rename(stash)
        return {"kind": "move", "src": str(src), "stash": str(stash)}

    if "json_field_increment" in m:
        target = wt / m["file"]
        doc = json.loads(target.read_text(encoding="utf-8"))
        field = m["json_field_increment"]
        original = doc[field]
        doc[field] = original + 1
        target.write_text(
            json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return {"kind": "file-restore-by-checkout", "path": m["file"]}

    if "remove_skill_entry" in m:
        target = wt / m["file"]
        doc = json.loads(target.read_text(encoding="utf-8"))
        skills = doc["plugins"][0]["skills"]
        entry = m["remove_skill_entry"]
        if entry not in skills:
            raise MutationError(f"{entry!r} not present in {m['file']} skills list")
        skills.remove(entry)
        target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return {"kind": "file-restore-by-checkout", "path": m["file"]}

    if "drop_line_containing" in m:
        target = wt / m["file"]
        needle = m["drop_line_containing"]
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        idx = next((i for i, ln in enumerate(lines) if needle in ln), None)
        if idx is None:
            raise MutationError(f"no line containing {needle!r} in {m['file']}")
        del lines[idx]
        target.write_text("".join(lines), encoding="utf-8")
        return {"kind": "file-restore-by-checkout", "path": m["file"]}

    if "append" in m:
        target = wt / m["file"]
        before_sha = git(wt, "rev-parse", "HEAD")[1].strip()
        with target.open("a", encoding="utf-8") as fh:
            fh.write(m["append"])
        if case.get("commit_required"):
            rc, out = git(wt, "add", m["file"])
            if rc != 0:
                raise MutationError(f"git add failed: {out}")
            rc, out = git(
                wt, "commit", "-q", "-m", "AUD-0046 scratch mutation (never pushed)"
            )
            if rc != 0:
                raise MutationError(f"git commit failed: {out}")
        return {
            "kind": "commit-restore-by-reset"
            if case.get("commit_required")
            else "file-restore-by-checkout",
            "path": m["file"],
            "before_sha": before_sha,
        }

    if "find" in m and "replace" in m:
        target = wt / m["file"]
        text = target.read_text(encoding="utf-8")
        occ = m.get("occurrence")
        if occ is not None:
            # replace only the Nth occurrence (1-indexed)
            parts = text.split(m["find"])
            if len(parts) - 1 < occ:
                raise MutationError(
                    f"occurrence {occ} of {m['find']!r} not found in {m['file']}"
                )
            rebuilt = parts[0]
            for i in range(1, len(parts)):
                rebuilt += (m["replace"] if i == occ else m["find"]) + parts[i]
            new_text = rebuilt
        else:
            if m["find"] not in text:
                raise MutationError(f"{m['find']!r} not found in {m['file']}")
            new_text = text.replace(m["find"], m["replace"])
        target.write_text(new_text, encoding="utf-8")
        if case.get("commit_required"):
            rc, out = git(wt, "add", m["file"])
            if rc != 0:
                raise MutationError(f"git add failed: {out}")
            before_sha = git(wt, "rev-parse", "HEAD~0")[1].strip()
            rc, out = git(
                wt, "commit", "-q", "-m", "AUD-0046 scratch mutation (never pushed)"
            )
            if rc != 0:
                raise MutationError(f"git commit failed: {out}")
            return {
                "kind": "commit-restore-by-reset",
                "path": m["file"],
                "before_sha": before_sha,
            }
        return {"kind": "file-restore-by-checkout", "path": m["file"]}

    raise MutationError(f"unrecognised mutation shape: {m}")


def revert_mutation(wt: Path, state: dict) -> None:
    kind = state["kind"]
    if kind == "move":
        Path(state["stash"]).rename(state["src"])
        return
    if kind == "file-restore-by-checkout":
        rc, out = git(wt, "checkout", "--", state["path"])
        if rc != 0:
            raise MutationError(f"git checkout revert failed: {out}")
        return
    if kind == "commit-restore-by-reset":
        rc, out = git(wt, "reset", "-q", "--hard", state["before_sha"])
        if rc != 0:
            raise MutationError(f"git reset revert failed: {out}")
        return
    raise MutationError(f"unrecognised revert kind: {kind}")


def sweep_one(wt: Path, case: dict) -> dict:
    cmd = case["command"]
    expect0 = case["expected_baseline_exit"]

    baseline_rc, baseline_out = run(cmd, cwd=wt)
    baseline_ok = baseline_rc == expect0

    mutation_error = None
    mutated_rc = None
    mutated_out = ""
    reverted_rc = None
    reverted_out = ""
    revert_ok = False
    mutated_ok = False
    both_states_and_revert = False

    if baseline_ok:
        try:
            state = apply_mutation(wt, case)
        except MutationError as exc:
            mutation_error = str(exc)
        else:
            mutated_rc, mutated_out = run(cmd, cwd=wt)
            mutated_ok = mutated_rc != 0
            try:
                revert_mutation(wt, state)
                reverted_rc, reverted_out = run(cmd, cwd=wt)
                revert_ok = reverted_rc == expect0
            except MutationError as exc:
                mutation_error = str(exc)

    both_states_and_revert = bool(baseline_ok and mutated_ok and revert_ok)

    return {
        "id": case["id"],
        "gate": case["gate"],
        "claim": case["claim"],
        "command": " ".join(cmd),
        "mutation_kind": case["mutation_kind"],
        "commit_required": bool(case.get("commit_required")),
        "baseline_exit": baseline_rc,
        "baseline_ok": baseline_ok,
        "mutated_exit": mutated_rc,
        "mutated_ok": mutated_ok,
        "reverted_exit": reverted_rc,
        "revert_ok": revert_ok,
        "both_states_and_revert_ok": both_states_and_revert,
        "mutation_error": mutation_error,
        "baseline_output_tail": baseline_out[-800:],
        "mutated_output_tail": mutated_out[-800:],
        "reverted_output_tail": reverted_out[-800:],
    }


def main() -> int:
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    gates = cases["gates"]

    wt = make_worktree()
    lines: list[str] = [
        "AUD-0046 NAMED PROBE 2: plant matched mutation -> RED -> revert -> GREEN",
        "unit=AUD-0046",
        f"gates_swept={len(gates)}",
    ]
    per_gate: list[dict] = []
    try:
        for case in gates:
            row = sweep_one(wt, case)
            per_gate.append(row)
            lines.append(
                f"GATE\t{row['id']}\t{row['gate']}\t"
                f"baseline={row['baseline_exit']}(ok={row['baseline_ok']})\t"
                f"mutated={row['mutated_exit']}(ok={row['mutated_ok']})\t"
                f"reverted={row['reverted_exit']}(ok={row['revert_ok']})\t"
                f"both_states_and_revert={row['both_states_and_revert_ok']}"
                + (f"\tERROR={row['mutation_error']}" if row["mutation_error"] else "")
            )
    finally:
        remove_worktree(wt)

    all_ok = all(row["both_states_and_revert_ok"] for row in per_gate)
    swept_ok_count = sum(1 for row in per_gate if row["both_states_and_revert_ok"])

    result = {
        "ok": all_ok,
        "unit": "AUD-0046",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gates_swept": len(gates),
        "gates_both_states_and_revert_ok": swept_ok_count,
        "all_ok": all_ok,
        "per_gate": per_gate,
        "worktree_mode": "git worktree add --detach (removed after run)",
        "live_tree_mutated": False,
        "notes": (
            "Each gate's mutation is matched to the exact defect class its own "
            "docstring names (see fixtures/gate_cases.json). check_published_commands.py "
            "reads `git cat-file -p HEAD:<path>` rather than working-tree bytes, so its "
            "case commits the mutation in the scratch worktree and reverts with "
            "`git reset --hard` to the pre-mutation commit; every other case reverts "
            "with a plain working-tree restore (`git checkout --` or move-back)."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines.append(f"gates_both_states_and_revert_ok={swept_ok_count}/{len(gates)}")
    lines.append(f"all_ok={all_ok}")
    lines.append("SUCCESS:AUD-0046-probe2" if all_ok else "FAILED:AUD-0046-probe2")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
