"""Test suite for scripts/sync-from-live.ps1 -- the live -> repo harness backup.

WHY THIS EXISTS
    sync-from-live.ps1 is the ONLY mechanism that moves harness work (~/.claude/rules,
    agents, commands, hooks and ~/.agents/skills) into version control. Before it existed,
    462 files / 2.73 MB were architecturally orphaned. It shipped with five guards and zero
    tests, which means every guard was one refactor away from silently regressing -- on the
    one script whose failure mode is "the backup quietly stopped backing things up".

    Every test below pins a defect that was MEASURED against the real script, not imagined.
    The script is driven as a black box through its real CLI so that parameter binding, the
    real directory walk and the real JSON emission are all exercised.

SAFETY
    Every test builds a throwaway live tree and a throwaway repo under pytest's tmp_path and
    points the script at them with -LiveHome / -Root. No test reads or writes the real
    ~/.claude, ~/.agents or the real repository.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "sync-from-live.ps1"

# live-relative -> repo-relative, mirroring $Map inside the script.
AREAS = {
    "rules": (".claude/rules", "rules"),
    "agents": (".claude/agents", "agents"),
    "commands": (".claude/commands", "commands"),
    "hooks": (".claude/hooks", "hooks"),
    "skills": (".agents/skills", ".agents/skills"),
}


# --------------------------------------------------------------------------- helpers


def run_sync(root: Path, home: Path, *args: str, timeout: int = 300):
    """Invoke the real script. Returns the CompletedProcess."""
    cmd = [
        "pwsh",
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(SCRIPT),
        "-Root",
        str(root),
        "-LiveHome",
        str(home),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def report(root: Path, home: Path, *args: str) -> dict:
    """Run with -Report json and parse stdout. Fails loudly if stdout is not pure JSON."""
    p = run_sync(root, home, "-Report", "json", *args)
    out = p.stdout.strip()
    if not out:
        pytest.fail(
            f"-Report json produced NO stdout (rc={p.returncode}).\n"
            f"STDERR:\n{p.stderr[:2000]}"
        )
    try:
        doc = json.loads(out)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"-Report json stdout is not valid JSON ({exc}).\n"
            f"--- stdout ---\n{out[:2000]}\n--- stderr ---\n{p.stderr[:1000]}"
        )
    doc["_rc"] = p.returncode
    return doc


def write(path: Path, data: bytes | str) -> Path:
    """Write exact bytes -- never let Python translate newlines, the EOL tests depend on it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def statuses(doc: dict) -> list[str]:
    return [f["status"] for f in doc.get("findings", [])]


def finding_for(doc: dict, needle: str) -> dict | None:
    for f in doc.get("findings", []):
        if needle.replace("\\", "/") in str(f.get("repoPath", "")).replace("\\", "/"):
            return f
    return None


def snapshot(tree: Path) -> dict[str, bytes]:
    """Path -> content for every file under tree. Used to prove live is never written."""
    out = {}
    for p in tree.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(tree)).replace("\\", "/")] = p.read_bytes()
    return out


@pytest.fixture
def env(tmp_path: Path):
    """A throwaway (live tree, repo tree) pair with every mapped area present."""
    home = tmp_path / "home"
    root = tmp_path / "repo"
    for live_rel, repo_rel in AREAS.values():
        (home / live_rel).mkdir(parents=True, exist_ok=True)
        (root / repo_rel).mkdir(parents=True, exist_ok=True)

    class Env:
        pass

    e = Env()
    e.home, e.root, e.tmp = home, root, tmp_path
    e.live = lambda area, rel: home / AREAS[area][0] / rel
    e.repo = lambda area, rel: root / AREAS[area][1] / rel
    return e


# --------------------------------------------------------------------------- sanity


def test_pwsh_and_script_are_present():
    """Known-positive control for the harness itself: if this fails every other result is noise."""
    assert SCRIPT.is_file(), f"script not found at {SCRIPT}"
    p = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert p.returncode == 0, f"pwsh unavailable: {p.stderr}"
    assert int(p.stdout.strip()) >= 7, f"expected PowerShell 7+, got {p.stdout!r}"


def test_identical_trees_report_clean(env):
    """Baseline control: when nothing differs the verdict must be CLEAN and rc 0.

    A detector that reports drift on identical trees is useless; a suite that never
    exercises the clean path cannot notice if the fix over-reports."""
    write(env.live("rules", "a.md"), "same\n")
    write(env.repo("rules", "a.md"), "same\n")
    doc = report(env.root, env.home, "-Drift")
    assert doc["verdict"] == "CLEAN", doc
    assert doc["_rc"] == 0
    assert doc["totals"]["divergent"] == 0


# --------------------------------------------------------------------------- (b) JSON contract


def test_json_report_carries_the_documented_schema(env):
    """-Report json must emit the versioned contract B2's Stop hook binds to."""
    write(env.live("rules", "a.md"), "x\n")
    doc = report(env.root, env.home, "-Drift")
    assert doc["schema"] == "harness-drift/v1"
    for key in (
        "generatedUtc",
        "mode",
        "repoRoot",
        "liveHome",
        "ok",
        "verdict",
        "exitCode",
        "totals",
        "areas",
        "findings",
        "detectorControl",
    ):
        assert key in doc, f"missing top-level key {key!r}; got {sorted(doc)}"
    for key in (
        "filesSeen",
        "new",
        "changed",
        "same",
        "excluded",
        "held",
        "pruned",
        "unreadable",
        "reparse",
        "caseMismatch",
        "eolOnly",
        "divergent",
    ):
        assert key in doc["totals"], (
            f"missing totals.{key}; got {sorted(doc['totals'])}"
        )
    assert doc["verdict"] in ("CLEAN", "DRIFT", "FAILED")
    assert isinstance(doc["ok"], bool)
    assert doc["ok"] == (doc["verdict"] == "CLEAN")


def test_json_mode_emits_only_json_on_stdout(env):
    """A hook consuming stdout must not have to strip banner text out of it."""
    write(env.live("rules", "a.md"), "x\n")
    p = run_sync(env.root, env.home, "-Drift", "-Report", "json")
    out = p.stdout.strip()
    assert out.startswith("{") and out.endswith("}"), (
        f"stdout is not bare JSON:\n{out[:800]}"
    )
    assert "===" not in out, "human banner leaked into JSON stdout"
    json.loads(out)


def test_exit_code_distinguishes_clean_from_drift(env):
    """A Stop hook must be able to branch without parsing anything. 0=CLEAN 3=DRIFT 1=FAILED."""
    write(env.live("rules", "a.md"), "LIVE\n")
    write(env.repo("rules", "a.md"), "REPO\n")
    p = run_sync(env.root, env.home, "-Drift")
    assert p.returncode == 3, (
        f"expected rc=3 for drift, got {p.returncode}. The script exits 0 unconditionally, "
        f"so no automated consumer can tell drift from clean.\nSTDOUT:\n{p.stdout[:800]}"
    )


# --------------------------------------------------------------------------- D-1 held files


def test_held_file_is_reported_as_drift_not_as_clean(env):
    """A repo-owned hold means the two sides DIFFER -- that is drift by definition.

    Measured against the live tree 2026-07-18: the script listed three REPO-OWNED holds and
    then printed 'NO DRIFT: every shared file is byte-identical' seven lines later. The drift
    detector hides exactly the divergence it most needs to surface."""
    write(env.live("skills", "multi-agent-quickstart/SKILL.md"), "LIVE side\n")
    write(
        env.repo("skills", "multi-agent-quickstart/SKILL.md"), "REPO side, different\n"
    )
    p = run_sync(env.root, env.home, "-Drift")
    assert "NO DRIFT" not in p.stdout, (
        "script claimed 'NO DRIFT' while holding a file whose two sides differ.\n"
        f"STDOUT:\n{p.stdout}"
    )
    doc = report(env.root, env.home, "-Drift")
    assert "HELD" in statuses(doc), (
        f"held file missing from findings: {doc.get('findings')}"
    )
    assert doc["verdict"] == "DRIFT"
    assert doc["totals"]["held"] == 1


def test_held_file_is_never_overwritten_by_sync(env):
    """Regression guard on the existing hold list -- it must keep working after hardening."""
    repo_f = write(
        env.repo("skills", "multi-agent-quickstart/SKILL.md"), "REPO AUTHORITATIVE\n"
    )
    write(env.live("skills", "multi-agent-quickstart/SKILL.md"), "live junk\n")
    run_sync(env.root, env.home)
    assert repo_f.read_bytes() == b"REPO AUTHORITATIVE\n", (
        "hold list failed to protect the repo copy"
    )


# --------------------------------------------------------------------------- D-2 loose files


def test_findings_contain_no_duplicate_paths(env):
    """Second symptom of the switch/continue bug: a terminal status recorded its finding and
    then fell through and recorded a second one for the same file. A consumer counting
    findings would double-count every held or eol-only file."""
    write(env.live("skills", "multi-agent-quickstart/SKILL.md"), "LIVE\n")
    write(env.repo("skills", "multi-agent-quickstart/SKILL.md"), "REPO\n")
    write(env.live("rules", "eol.md"), b"a\nb\n")
    write(env.repo("rules", "eol.md"), b"a\r\nb\r\n")
    doc = report(env.root, env.home, "-Drift")
    keys = [(f["area"], f["repoPath"]) for f in doc["findings"]]
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"duplicate findings emitted for {dupes}"


def test_loose_file_divergence_is_reported_as_drift(env):
    """Loose files bypass the drift table entirely, so -Drift can print a divergence line
    and then claim 'every shared file is byte-identical' in the same run."""
    live_loose = env.home / ".local/bin/codexmon.ps1"
    write(live_loose, "LIVE version\n")
    write(env.root / "tools/monitor/codexmon.ps1", "REPO version, different\n")
    p = run_sync(env.root, env.home, "-Drift")
    assert "NO DRIFT" not in p.stdout, (
        f"loose-file divergence not counted as drift.\nSTDOUT:\n{p.stdout}"
    )
    doc = report(env.root, env.home, "-Drift")
    assert doc["verdict"] == "DRIFT"
    assert finding_for(doc, "tools/monitor/codexmon.ps1") is not None, doc.get(
        "findings"
    )


# --------------------------------------------------------------------------- D-3 hash failure


def test_unreadable_file_is_never_reported_as_identical(env):
    """Get-Hash swallows every failure and returns $null, and the comparison is
    `(Get-Hash live) -eq (Get-Hash repo)`. Two unreadable files therefore compare
    $null -eq $null -> TRUE -> counted 'same' and skipped. Verified in isolation:
    two nonexistent paths hash-compare equal."""
    live_f = write(env.live("rules", "locked.md"), "LIVE CONTENT\n")
    write(env.repo("rules", "locked.md"), "REPO CONTENT DIFFERENT\n")
    # Hold the live file open with no sharing so Get-FileHash cannot read it.
    handle = os.open(str(live_f), os.O_RDONLY)
    try:
        import msvcrt

        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        doc = report(env.root, env.home, "-Drift")
    finally:
        try:
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        os.close(handle)
    assert doc["totals"]["same"] == 0, (
        "a file whose hash could not be computed was counted as byte-identical"
    )


def test_hash_failure_status_is_exposed(env):
    """The report must carry an UNREADABLE bucket so a consumer can see 'could not verify'
    as distinct from 'verified identical'."""
    write(env.live("rules", "a.md"), "x\n")
    doc = report(env.root, env.home, "-Drift")
    assert "unreadable" in doc["totals"]


# --------------------------------------------------------------------------- D-4 no control


def test_missing_live_area_fails_loudly(env):
    """A mapped live root that has vanished is indistinguishable from a typo or a rename.
    The script prints a grey note and carries on, so the run reports 'NO DRIFT' having
    compared nothing -- the exact single-unvalidated-probe failure this program exists to kill."""
    import shutil

    shutil.rmtree(env.home / ".claude/rules")
    p = run_sync(env.root, env.home, "-Drift")
    assert p.returncode != 0, (
        f"a missing live area exited {p.returncode}; a broken backup must not look like success.\n"
        f"STDOUT:\n{p.stdout}"
    )
    assert "NO DRIFT" not in p.stdout


def test_detector_self_control_runs_and_is_reported(env):
    """The known-positive control, made MECHANICAL rather than remembered.

    INPUT-known-harness-defects.md D2 asks whether 'prove your detector can find a
    known-present item' can be enforced by the tool instead of by an agent's memory.
    The script plants divergences in a scratch fixture and must detect all of them
    before it is allowed to report CLEAN."""
    write(env.live("rules", "a.md"), "same\n")
    write(env.repo("rules", "a.md"), "same\n")
    doc = report(env.root, env.home, "-Drift")
    ctl = doc["detectorControl"]
    assert ctl["ran"] is True
    assert ctl["passed"] is True
    assert ctl["planted"] > 0
    assert ctl["detected"] == ctl["planted"], ctl


def test_clean_verdict_is_refused_when_the_self_control_fails(env):
    """If the detector cannot find planted divergences, 'CLEAN' is unearned and must not
    be printed. Fault is injected through an env var the control honours."""
    write(env.live("rules", "a.md"), "same\n")
    write(env.repo("rules", "a.md"), "same\n")
    e = dict(os.environ, SYNC_FROM_LIVE_BREAK_CONTROL="1")
    p = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Root",
            str(env.root),
            "-LiveHome",
            str(env.home),
            "-Drift",
            "-Report",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=e,
    )
    doc = json.loads(p.stdout.strip())
    assert doc["detectorControl"]["passed"] is False
    assert doc["verdict"] == "FAILED", doc
    assert p.returncode == 1


# --------------------------------------------------------------------------- D-5 wildcards


def test_prune_does_not_delete_a_live_file_whose_name_holds_brackets(env):
    """WORST CASE -- DATA LOSS. -Prune decides a repo file is orphaned with
    `Test-Path (Join-Path $Live $rel)`, and Test-Path GLOB-EXPANDS its argument.
    Verified in isolation: Test-Path on an existing 'file[1].md' returns False while
    -LiteralPath returns True. So a bracketed live file reads as absent and its repo
    counterpart is deleted even though live still holds it."""
    write(env.live("rules", "note[1].md"), "still here\n")
    repo_f = write(env.repo("rules", "note[1].md"), "still here\n")
    run_sync(env.root, env.home, "-Prune")
    assert repo_f.exists(), (
        "-Prune DELETED a repo file whose live counterpart exists; "
        "Test-Path glob-expanded the '[1]' in the filename"
    )


def test_bracketed_held_file_is_not_silently_overwritten(env):
    """`Test-Path $dest` glob-expands too, so a bracketed destination reads as absent,
    is classified NEW, and skips both the repo-owned hold check and the drift row."""
    write(env.live("rules", "held[x].md"), "live\n")
    write(env.repo("rules", "held[x].md"), "REPO AUTHORITATIVE\n")
    doc = report(env.root, env.home, "-Drift")
    f = finding_for(doc, "held[x].md")
    assert f is not None, (
        f"bracketed divergence invisible to the detector: {doc.get('findings')}"
    )
    assert f["status"] in ("CHANGED", "HELD"), f
    assert doc["totals"]["new"] == 0, "existing bracketed repo file misreported as NEW"


def test_nested_repo_is_detected_through_a_bracketed_directory(env):
    """Test-InNestedRepo checks `Test-Path (Join-Path $dir '.git')` -- also glob-expanded.
    A vendored third-party clone sitting under a bracketed directory name is therefore
    NOT recognised and gets committed, which is the crypto-ctf/RsaCtfTool failure again."""
    nested = env.live("skills", "vendor[old]/RsaCtfTool")
    (nested / ".git").mkdir(parents=True)
    write(nested / ".git/HEAD", "ref: refs/heads/main\n")
    write(nested / "LICENSE.txt", "someone else's licence\n")
    run_sync(env.root, env.home)
    leaked = env.repo("skills", "vendor[old]/RsaCtfTool/LICENSE.txt")
    assert not leaked.exists(), (
        "third-party nested repo was vendored in through a bracketed dir"
    )


def test_nested_repo_is_still_excluded_normally(env):
    """Known-positive control for the guard I am modifying: the ordinary case must keep working."""
    nested = env.live("skills", "crypto-ctf/RsaCtfTool")
    (nested / ".git").mkdir(parents=True)
    write(nested / "LICENSE.txt", "someone else's licence\n")
    run_sync(env.root, env.home)
    assert not env.repo("skills", "crypto-ctf/RsaCtfTool/LICENSE.txt").exists()


def test_junk_exclusions_are_still_applied(env):
    """Known-positive control: the exclusion set is load-bearing (357 MB raw vs 14 MB clean)."""
    write(env.live("skills", "s/.venv/lib/mod.py"), "vendored\n")
    write(env.live("skills", "s/__pycache__/x.pyc"), "bytecode\n")
    write(env.live("skills", "s/notes.py.bak-fleet-20260713"), "backup cruft\n")
    write(env.live("skills", "s/real.py"), "real content\n")
    run_sync(env.root, env.home)
    assert env.repo("skills", "s/real.py").exists(), "a real file was wrongly excluded"
    assert not env.repo("skills", "s/.venv/lib/mod.py").exists()
    assert not env.repo("skills", "s/__pycache__/x.pyc").exists()
    assert not env.repo("skills", "s/notes.py.bak-fleet-20260713").exists()


# --------------------------------------------------------------------------- D-7 prune vs hold


def test_prune_respects_the_repo_owned_hold_list(env):
    """The hold list exists because those repo copies are authoritative. -Prune never
    consults it, so a live deletion destroys the very file the guard protects."""
    repo_f = write(
        env.repo("hooks", "README.md"), "REPO tree documentation -- authoritative\n"
    )
    # live hooks/README.md deliberately absent
    run_sync(env.root, env.home, "-Prune")
    assert repo_f.exists(), "-Prune deleted a repo-owned held file"


# --------------------------------------------------------------------------- D-9 reparse


def test_reparse_point_is_reported_rather_than_silently_handled(env):
    """Copy-Item dereferences a symlink and copies the TARGET's bytes, so a link pointing
    outside the tree drags foreign content into the repo. Get-ChildItem -Recurse does not
    traverse directory links, so link-delivered content silently never reaches the backup.
    Either way the operator must be told, not left with a clean-looking report."""
    target = env.tmp / "outside-secret.txt"
    write(target, "CONTENT FROM OUTSIDE THE HARNESS\n")
    link = env.live("skills", "s/linked.txt")
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(str(target), str(link))
    except OSError as exc:  # 1314 = SeCreateSymbolicLinkPrivilege not held
        pytest.skip(
            f"cannot create symlinks on this box (winerror={getattr(exc, 'winerror', None)})"
        )
    doc = report(env.root, env.home, "-Drift")
    assert doc["totals"]["reparse"] >= 1, f"reparse point not surfaced: {doc['totals']}"
    assert (
        not env.repo("skills", "s/linked.txt").exists()
        or env.repo("skills", "s/linked.txt").read_bytes() != target.read_bytes()
    ), "symlink target content was silently copied into the repo"


# --------------------------------------------------------------------------- D-10 case


def test_case_only_rename_is_detected(env):
    """Windows is case-insensitive, git's index is not. Live renames Foo.md -> foo.md and
    Test-Path still says the repo file exists, hashes match, so the detector reports
    'identical' forever while the repo keeps the old name permanently."""
    write(env.live("rules", "casing.md"), "body\n")
    write(env.repo("rules", "CASING.md"), "body\n")
    doc = report(env.root, env.home, "-Drift")
    assert doc["totals"]["caseMismatch"] >= 1, (
        f"case-only divergence invisible; totals={doc['totals']}"
    )
    assert doc["verdict"] == "DRIFT"


# --------------------------------------------------------------------------- D-11 mtime tie


def test_mtime_tie_is_labelled_tie_not_repo(env):
    """`if (live -gt repo) {'LIVE'} else {'REPO'}` silently calls an exact tie 'REPO'.
    The column already carries a warning that it is only a hint; mislabelling a tie
    makes that hint actively wrong."""
    live_f = write(env.live("rules", "tie.md"), "LIVE\n")
    repo_f = write(env.repo("rules", "tie.md"), "REPO\n")
    ts = 1_700_000_000
    os.utime(live_f, (ts, ts))
    os.utime(repo_f, (ts, ts))
    doc = report(env.root, env.home, "-Drift")
    f = finding_for(doc, "tie.md")
    assert f is not None
    assert f["mtimeSays"] == "TIE", f"equal mtimes reported as {f['mtimeSays']!r}"


# --------------------------------------------------------------------------- EOL normalisation


def test_eol_only_difference_is_not_reported_as_content_drift(env):
    """MEASURED: core.autocrlf=true is set at SYSTEM level on this box, so a fresh clone
    materialises text files CRLF while the live tree is mixed. The detector compares raw
    SHA256, which line endings change but git does not see. 342 of 2,035 shared files
    (16.8%) would report CHANGED on a fresh clone with no content difference whatsoever."""
    write(env.live("rules", "eol.md"), b"line one\nline two\n")
    write(env.repo("rules", "eol.md"), b"line one\r\nline two\r\n")
    doc = report(env.root, env.home, "-Drift")
    assert doc["totals"]["eolOnly"] == 1, (
        f"EOL-only difference not classified: {doc['totals']}"
    )
    assert doc["totals"]["changed"] == 0, (
        "EOL-only difference miscounted as content drift"
    )
    assert doc["verdict"] == "CLEAN", (
        "line-ending normalisation must not raise a drift alarm"
    )


def test_real_content_difference_is_still_drift_despite_eol_handling(env):
    """Known-positive control for the EOL fix: normalising newlines must not blind the
    detector to genuine edits. A discriminator that silences everything is worthless."""
    write(env.live("rules", "real.md"), b"line one\nCHANGED\n")
    write(env.repo("rules", "real.md"), b"line one\r\noriginal\r\n")
    doc = report(env.root, env.home, "-Drift")
    assert doc["totals"]["changed"] == 1, doc["totals"]
    assert doc["verdict"] == "DRIFT"


def test_binary_files_are_never_newline_normalised(env):
    """Newline normalisation applied to binary content would make genuinely different
    blobs compare equal. Files containing NUL must be compared byte-exactly."""
    write(env.live("skills", "s/blob.bin"), b"\x00\x01\n\x02")
    write(env.repo("skills", "s/blob.bin"), b"\x00\x01\r\n\x02")
    doc = report(env.root, env.home, "-Drift")
    assert doc["totals"]["changed"] == 1, (
        f"binary difference was normalised away: {doc['totals']}"
    )


# --------------------------------------------------------------------------- D-8 copy integrity


def test_every_copied_file_is_verified_after_writing(env):
    """windows-shell.md rule 1: always verify after a write, the empty-file state is silent.
    The report must state how many copies were hash-verified so a silent partial write
    cannot masquerade as success."""
    write(env.live("rules", "a.md"), "alpha\n")
    write(env.live("skills", "s/b.md"), "beta\n")
    doc = report(env.root, env.home)
    assert "verifiedCopies" in doc["totals"], doc["totals"]
    assert (
        doc["totals"]["verifiedCopies"]
        == doc["totals"]["new"] + doc["totals"]["changed"]
    )
    assert env.repo("rules", "a.md").read_bytes() == b"alpha\n"
    assert env.repo("skills", "s/b.md").read_bytes() == b"beta\n"


# --------------------------------------------------------------------------- safety invariants


def test_sync_never_writes_to_the_live_tree(env):
    """The script's first safety claim: live is read-only in both directions of intent.
    Exercised with the most destructive flag combination available."""
    write(env.live("rules", "a.md"), "alpha\n")
    write(env.live("skills", "s/b.md"), "beta\n")
    write(env.repo("rules", "orphan.md"), "only in repo\n")
    before = snapshot(env.home)
    run_sync(env.root, env.home, "-Prune")
    after = snapshot(env.home)
    assert before == after, (
        "live tree mutated by a sync run; "
        f"added={sorted(set(after) - set(before))} removed={sorted(set(before) - set(after))}"
    )


def test_whatif_writes_nothing_at_all(env):
    write(env.live("rules", "a.md"), "alpha\n")
    before = snapshot(env.root)
    run_sync(env.root, env.home, "-WhatIf")
    assert snapshot(env.root) == before, "-WhatIf wrote to the repo"


def test_prune_removes_a_genuinely_orphaned_repo_file(env):
    """Known-positive control for -Prune: after hardening it must still do its job."""
    orphan = write(env.repo("rules", "gone.md"), "live no longer has this\n")
    write(env.live("rules", "kept.md"), "kept\n")
    run_sync(env.root, env.home, "-Prune")
    assert not orphan.exists(), "-Prune failed to remove a genuinely orphaned file"
    assert env.repo("rules", "kept.md").exists()
