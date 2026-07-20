"""Tests for the git-crypt worktree doctor + backfill.

Every assertion here is made against the REAL executable run as a
subprocess, and the signal asserted is the PROCESS exit code plus the JSON
artifact it wrote -- never an imported function's return value. That is the
specific false-green that defeated R1's shell doctor: its internal ``rc``
was correct and its process exit code was not.

Each detector is exercised in BOTH states: it must fire on a known-broken
fixture and stay silent on a known-good one. ``test_mutation_*`` reintroduce
the original defects into an isolated copy of the script and prove the suite
goes red -- a suite that stays green under mutation is not protecting the
behaviour it claims to protect.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures_lib import (  # noqa: E402
    GITCRYPT_MAGIC,
    SYNTHETIC,
    add_worktree,
    git,
    init_repo,
    is_ciphertext,
    make_ciphertext_worktree,
    sha256,
)

SCRIPT = Path(__file__).resolve().parent.parent / "gitcrypt_worktree.py"

EXIT_OK = 0
EXIT_UNSAFE = 1
EXIT_USAGE = 2
EXIT_AMBIGUOUS = 3
EXIT_UNREADABLE = 4
EXIT_INCONSISTENT = 5
EXIT_MISMATCH = 6
EXIT_REFUSED = 7


def run_tool(*args, script=None):
    """Invoke the real CLI as a subprocess. Returns (returncode, report)."""
    proc = subprocess.run(
        [sys.executable, str(script or SCRIPT), *args, "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = None
    if proc.stdout.strip():
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            report = None
    return proc.returncode, report, proc


def doctor(repo, script=None):
    return run_tool("doctor", "--repo", str(repo), script=script)


def finding_for(report, path):
    want = os.path.realpath(str(path)).replace("\\", "/").casefold()
    for finding in report["findings"]:
        if finding["worktree_path"].casefold() == want:
            return finding
    raise AssertionError(
        f"no finding for {want}; got {[f['worktree_path'] for f in report['findings']]}"
    )


def assert_no_secret_leak(proc):
    """The tool must never surface decrypted content."""
    blob = (proc.stdout or "") + (proc.stderr or "")
    assert "SYNTHETIC_FIXTURE_04B_NOT_A_REAL_SECRET" not in blob


# ---------------------------------------------------------------------------
# fixture 1 -- expected plaintext, observed plaintext  -> OK / exit 0
# ---------------------------------------------------------------------------


def test_fixture01_expected_plaintext_is_ok(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = add_worktree(repo, tmp_path / "wt-plain", "plain")
    assert not is_ciphertext(wt / "secret.json")

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_OK, report
    assert report["exit_name"] == "OK"

    found = finding_for(report, wt)
    assert found["expected_state"] == "plaintext"
    assert found["observed_state"] == "plaintext"
    assert found["verdict"] == "OK"
    assert found["action_performed"] == "none"
    assert found["owner_approval_required"] is False
    assert found["risk"] == "none"
    # both independent signals were available and agreed
    probe = found["files"][0]
    assert probe["magic_gitcrypt"] is False
    assert probe["signals_agree"] is True


# ---------------------------------------------------------------------------
# fixture 2 -- expected ciphertext, observed ciphertext -> OK / exit 0
# and byte-identical after doctor AND after a dry-run backfill
# ---------------------------------------------------------------------------


def test_fixture02_expected_ciphertext_is_ok_and_untouched(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "cipher")
    secret = wt / "secret.json"
    before = sha256(secret)
    before_size = secret.stat().st_size
    cfg = repo / ".git" / "worktrees" / "wt-cipher" / "config.worktree"
    cfg_before = sha256(cfg)

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_OK, report
    found = finding_for(report, wt)
    assert found["expected_state"] == "ciphertext"
    assert found["expected_source"] == "declared"
    assert found["observed_state"] == "ciphertext"
    assert found["verdict"] == "OK"

    # doctor is read-only
    assert sha256(secret) == before
    assert secret.stat().st_size == before_size
    assert sha256(cfg) == cfg_before

    # dry-run backfill is read-only too
    rc, breport, proc = run_tool("backfill", "--repo", str(repo), "--all")
    assert_no_secret_leak(proc)
    assert breport["dry_run"] is True
    assert sha256(secret) == before
    assert sha256(cfg) == cfg_before
    entry = next(
        e
        for e in breport["plan"]
        if e["worktree_path"].casefold()
        == os.path.realpath(wt).replace("\\", "/").casefold()
    )
    assert entry["decision"] == "skip"
    assert entry["action_performed"] == "none (dry-run)"


# ---------------------------------------------------------------------------
# fixture 3 -- declared ciphertext but plaintext on disk -> UNSAFE / exit 1
# ---------------------------------------------------------------------------


def test_fixture03_unexpectedly_plaintext_is_unsafe(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "cipher")
    (wt / "secret.json").write_bytes(SYNTHETIC)  # plaintext lands where it must not

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_UNSAFE, report
    found = finding_for(report, wt)
    assert found["expected_state"] == "ciphertext"
    assert found["observed_state"] == "plaintext"
    assert found["verdict"] == "UNSAFE"
    assert found["risk"] == "secret-exposure"
    assert found["owner_approval_required"] is True
    assert wt.name in found["worktree_path"]


# ---------------------------------------------------------------------------
# fixture 4 -- declared plaintext but ciphertext on disk -> MISMATCH / exit 6
# ---------------------------------------------------------------------------


def test_fixture04_unexpectedly_ciphertext_is_mismatch(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt", "b", declare=False)
    # drop the identity filter, declare plaintext: the file stays ciphertext
    for key in (
        "filter.git-crypt.smudge",
        "filter.git-crypt.clean",
        "filter.git-crypt.required",
    ):
        git(["config", "--worktree", "--unset-all", key], cwd=wt, check=False)
    git(["config", "--worktree", "gitcrypt.worktreeMode", "plaintext"], cwd=wt)
    assert is_ciphertext(wt / "secret.json")

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_MISMATCH, report
    found = finding_for(report, wt)
    assert found["expected_state"] == "plaintext"
    assert found["observed_state"] == "ciphertext"
    assert found["verdict"] == "MISMATCH"
    assert found["risk"] == "not-materialised"
    assert found["key_available"] is True


# ---------------------------------------------------------------------------
# fixture 5 -- declared plaintext, NO key reachable -> MISMATCH + key missing
# ---------------------------------------------------------------------------


def test_fixture05_missing_key(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    clone = tmp_path / "clone"
    git(["clone", "--no-hardlinks", "-q", str(repo), str(clone)], cwd=tmp_path)
    git(["config", "extensions.worktreeConfig", "true"], cwd=clone)
    git(["config", "--worktree", "gitcrypt.worktreeMode", "plaintext"], cwd=clone)
    assert is_ciphertext(clone / "secret.json")

    rc, report, proc = doctor(clone)
    assert_no_secret_leak(proc)
    assert rc == EXIT_MISMATCH, report
    found = finding_for(report, clone)
    assert found["key_available"] is False
    assert found["key_source"] == "none"
    assert found["verdict"] == "MISMATCH"
    assert "key" in found["safe_next_action"].lower()

    # backfill must refuse: no key to point a filter at
    rc, breport, proc = run_tool("backfill", "--repo", str(clone), "--all")
    assert rc == EXIT_REFUSED, breport
    assert breport["plan"][0]["decision"] == "refuse"
    assert "key" in breport["plan"][0]["reason"].lower()


# ---------------------------------------------------------------------------
# fixture 6 -- inaccessible filtered path -> UNREADABLE / exit 4
# ---------------------------------------------------------------------------


def test_fixture06_inaccessible_file_is_unreadable(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = add_worktree(repo, tmp_path / "wt", "b")
    secret = wt / "secret.json"
    os.remove(secret)
    secret.mkdir()  # the path exists but cannot be read as a regular file

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_UNREADABLE, report
    found = finding_for(report, wt)
    assert found["verdict"] == "UNREADABLE"
    assert found["observed_state"] == "unreadable"
    assert found["owner_approval_required"] is True
    assert any("unreadable" in d for d in found["detail"])

    # backfill refuses an unclassifiable target
    rc, breport, _ = run_tool("backfill", "--repo", str(repo), "--worktree", str(wt))
    assert breport["plan"][0]["decision"] == "refuse"
    assert rc in (EXIT_UNREADABLE, EXIT_REFUSED)

    # known-good leg: restore the file and the detector goes silent
    secret.rmdir()
    git(["checkout", "--", "secret.json"], cwd=wt)
    rc, report, _ = doctor(repo)
    assert rc == EXIT_OK, report


# ---------------------------------------------------------------------------
# fixture 7 -- same basename under different parents -> distinct identity
# ---------------------------------------------------------------------------


def test_fixture07_same_basename_worktrees_are_distinguished(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    (tmp_path / "parentA").mkdir()
    (tmp_path / "parentB").mkdir()
    good = make_ciphertext_worktree(repo, tmp_path / "parentA" / "lane", "a")
    bad = make_ciphertext_worktree(repo, tmp_path / "parentB" / "lane", "b")
    (bad / "secret.json").write_bytes(SYNTHETIC)  # one of the two is UNSAFE

    assert good.name == bad.name == "lane"

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_UNSAFE, report

    paths = [f["worktree_path"] for f in report["findings"]]
    assert len(paths) == len(set(paths)), "row -> path mapping is not 1:1"
    entries = [f["gitdir_entry"] for f in report["findings"]]
    assert len(entries) == len(set(entries)), "gitdir identities collide"

    f_good = finding_for(report, good)
    f_bad = finding_for(report, bad)
    assert f_good["verdict"] == "OK"
    assert f_bad["verdict"] == "UNSAFE"
    # the two rows are distinguishable on EVERY identity axis
    assert f_good["worktree_path"] != f_bad["worktree_path"]
    assert f_good["gitdir_entry"] != f_bad["gitdir_entry"]
    assert f_good["repo_relative_path"] != f_bad["repo_relative_path"]
    assert f_good["branch"] != f_bad["branch"]
    # and no finding is reported by basename alone
    for finding in report["findings"]:
        assert "/" in finding["worktree_path"]
        assert os.path.isabs(finding["worktree_path"].replace("/", os.sep))


# ---------------------------------------------------------------------------
# fixture 8 -- partially materialised worktree -> AMBIGUOUS / exit 3
# ---------------------------------------------------------------------------


def test_fixture08_partially_materialised_is_ambiguous(tmp_path):
    repo, _key = init_repo(tmp_path / "repo", secrets=("secret.json", "secret2.json"))
    wt = add_worktree(repo, tmp_path / "wt", "b")
    # secret.json stays plaintext; secret2.json is replaced by its stored blob
    oid = git(["rev-parse", ":secret2.json"], cwd=wt).stdout.strip()
    blob = subprocess.run(
        ["git", "cat-file", "blob", oid], cwd=str(wt), capture_output=True, check=True
    ).stdout
    (wt / "secret2.json").write_bytes(blob)
    assert not is_ciphertext(wt / "secret.json")
    assert is_ciphertext(wt / "secret2.json")

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_AMBIGUOUS, report
    found = finding_for(report, wt)
    assert found["observed_state"] == "partial"
    assert found["verdict"] == "AMBIGUOUS"
    assert found["owner_approval_required"] is True

    rc, breport, _ = run_tool("backfill", "--repo", str(repo), "--worktree", str(wt))
    assert breport["plan"][0]["decision"] == "refuse"

    # known-good leg
    git(["checkout", "--", "secret2.json"], cwd=wt)
    rc, report, _ = doctor(repo)
    assert rc == EXIT_OK, report


# ---------------------------------------------------------------------------
# fixture 9 -- EOL / metadata-only churn must not change the verdict
# ---------------------------------------------------------------------------


def test_fixture09_eol_and_metadata_churn_do_not_flip_classification(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = add_worktree(repo, tmp_path / "wt", "b")
    secret = wt / "secret.json"

    rc_before, report_before, _ = doctor(repo)
    before = finding_for(report_before, wt)
    assert rc_before == EXIT_OK

    # metadata-only: defeat the stat cache without changing a byte
    data = secret.read_bytes()
    secret.write_bytes(data)
    os.utime(secret, (0, 0))
    rc_touch, report_touch, _ = doctor(repo)
    assert rc_touch == EXIT_OK
    assert finding_for(report_touch, wt)["observed_state"] == before["observed_state"]
    assert finding_for(report_touch, wt)["verdict"] == before["verdict"]

    # EOL-only: LF -> CRLF. git DOES see this as a modification...
    secret.write_bytes(data.replace(b"\n", b"\r\n"))
    status = git(["status", "--porcelain"], cwd=wt).stdout
    assert "secret.json" in status, "fixture did not actually dirty the worktree"

    # ...but the doctor's classification is content-shape based and unchanged.
    rc_eol, report_eol, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc_eol == EXIT_OK, report_eol
    after = finding_for(report_eol, wt)
    assert after["observed_state"] == before["observed_state"] == "plaintext"
    assert after["verdict"] == before["verdict"] == "OK"
    assert after["risk"] == "none"


# ---------------------------------------------------------------------------
# fixture 10 -- dry-run vs explicit apply separation
# ---------------------------------------------------------------------------


def _needy_repo(tmp_path):
    """Repo with one worktree that legitimately needs a backfill and one that
    is deliberately ciphertext-preserving."""
    repo, key = init_repo(tmp_path / "repo")
    protected = make_ciphertext_worktree(repo, tmp_path / "wt-protected", "p")
    needy = make_ciphertext_worktree(repo, tmp_path / "wt-needy", "n", declare=False)
    for k in (
        "filter.git-crypt.smudge",
        "filter.git-crypt.clean",
        "filter.git-crypt.required",
    ):
        git(["config", "--worktree", "--unset-all", k], cwd=needy, check=False)
    git(["config", "--worktree", "gitcrypt.worktreeMode", "plaintext"], cwd=needy)
    return repo, key, protected, needy


def test_fixture10_dry_run_changes_nothing_and_apply_is_scoped(tmp_path):
    repo, _key, protected, needy = _needy_repo(tmp_path)
    p_secret_before = sha256(protected / "secret.json")
    p_cfg = repo / ".git" / "worktrees" / "wt-protected" / "config.worktree"
    p_cfg_before = sha256(p_cfg)
    n_cfg = repo / ".git" / "worktrees" / "wt-needy" / "config.worktree"
    n_cfg_before = sha256(n_cfg)

    # 1. apply with NO selection is a usage error and writes nothing
    rc, _report, proc = run_tool("backfill", "--repo", str(repo), "--apply")
    assert rc == EXIT_USAGE
    assert "explicit target selection" in proc.stderr
    assert sha256(n_cfg) == n_cfg_before

    # 2. apply without a rollback journal is a usage error
    rc, _report, proc = run_tool("backfill", "--repo", str(repo), "--all", "--apply")
    assert rc == EXIT_USAGE
    assert "--journal" in proc.stderr
    assert sha256(n_cfg) == n_cfg_before

    # 3. dry-run over --all: plans a change, performs none
    rc, report, _ = run_tool("backfill", "--repo", str(repo), "--all")
    assert report["dry_run"] is True
    decisions = {e["gitdir_entry"]: e["decision"] for e in report["plan"]}
    assert decisions["wt-needy"] == "configure"
    assert decisions["wt-protected"] == "skip"
    assert all(e["action_performed"] == "none (dry-run)" for e in report["plan"])
    assert sha256(n_cfg) == n_cfg_before
    assert sha256(p_cfg) == p_cfg_before
    assert sha256(protected / "secret.json") == p_secret_before

    # 4. explicitly targeting the protected worktree is REFUSED, not silently skipped
    journal = tmp_path / "j1.json"
    rc, report, _ = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(protected),
        "--apply",
        "--journal",
        str(journal),
    )
    assert rc == EXIT_REFUSED, report
    assert report["plan"][0]["decision"] == "refuse"
    assert report["plan"][0]["owner_approval_required"] is True
    assert sha256(p_cfg) == p_cfg_before
    assert sha256(protected / "secret.json") == p_secret_before

    # 5. the legitimate target still succeeds, and ONLY it is touched
    journal2 = tmp_path / "j2.json"
    rc, report, proc = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(needy),
        "--apply",
        "--journal",
        str(journal2),
    )
    assert_no_secret_leak(proc)
    assert rc == EXIT_OK, report
    assert report["plan"][0]["action_performed"] == "configured"
    assert sha256(n_cfg) != n_cfg_before
    assert sha256(p_cfg) == p_cfg_before
    assert sha256(protected / "secret.json") == p_secret_before
    smudge = git(
        ["config", "--worktree", "--get", "filter.git-crypt.smudge"], cwd=needy
    ).stdout
    assert "--key-file" in smudge

    # 6. rollback restores the prior configuration
    assert journal2.exists()
    rc, rreport, _ = run_tool("rollback", "--journal", str(journal2), "--apply")
    assert rc == EXIT_OK, rreport
    assert sha256(n_cfg) == n_cfg_before


# ---------------------------------------------------------------------------
# fixture 11 -- the exact state R1's ungated backfill left behind
# ---------------------------------------------------------------------------


def test_fixture11_declared_ciphertext_with_decrypting_filter_is_inconsistent(tmp_path):
    repo, key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt", "b")
    # simulate R1's backfill: overwrite the filters, leave the marker alone
    git(
        [
            "config",
            "--worktree",
            "filter.git-crypt.smudge",
            f"git-crypt smudge --key-file={key}",
        ],
        cwd=wt,
    )
    git(
        [
            "config",
            "--worktree",
            "filter.git-crypt.clean",
            f"git-crypt clean --key-file={key}",
        ],
        cwd=wt,
    )
    git(["config", "--worktree", "filter.git-crypt.required", "true"], cwd=wt)

    rc, report, proc = doctor(repo)
    assert_no_secret_leak(proc)
    assert rc == EXIT_INCONSISTENT, report
    found = finding_for(report, wt)
    assert found["verdict"] == "INCONSISTENT"
    assert found["owner_approval_required"] is True
    assert any("ciphertext" in d and "decrypt" in d for d in found["detail"])


# ---------------------------------------------------------------------------
# enumeration: two independent sources, no name pattern-matching
# ---------------------------------------------------------------------------


def test_enumeration_uses_two_independent_sources(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    add_worktree(repo, tmp_path / "w1", "b1")
    add_worktree(repo, tmp_path / "w2", "b2")
    rc, report, _ = doctor(repo)
    enum = report["enumeration"]
    assert enum["s1_git_registry_count"] == 3  # main + 2 linked
    assert enum["s2_filesystem_gitdir_count"] == 2
    assert enum["agree"] is True
    assert rc == EXIT_OK


def test_doctor_reports_usage_error_outside_a_repo(tmp_path):
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    rc, _report, proc = run_tool("doctor", "--repo", str(outside))
    assert rc == EXIT_USAGE
    assert "not a git repository" in proc.stderr


def test_backfill_rejects_unknown_worktree_selector(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    rc, _report, proc = run_tool(
        "backfill", "--repo", str(repo), "--worktree", str(tmp_path / "nope")
    )
    assert rc == EXIT_USAGE
    assert "unknown worktree selector" in proc.stderr


# ---------------------------------------------------------------------------
# MUTATION TESTS -- reintroduce each original defect, prove the suite goes red
# ---------------------------------------------------------------------------


def _mutant(tmp_path, old, new, name):
    src = SCRIPT.read_text(encoding="utf-8")
    assert src.count(old) == 1, f"mutation anchor not unique: {old!r}"
    mutated = tmp_path / name
    mutated.write_text(src.replace(old, new), encoding="utf-8")
    # the mutant must import its sibling package context identically
    return mutated


def test_mutation_defect_a_unconditional_exit_zero(tmp_path):
    """R1 defect (a): the process exit code carried no information."""
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt", "b")
    (wt / "secret.json").write_bytes(SYNTHETIC)

    rc_real, _r, _p = doctor(repo)
    assert rc_real == EXIT_UNSAFE, "control leg: the real tool must fire"

    mutant = _mutant(
        tmp_path, '    return report["exit_code"]', "    return 0", "mut_a.py"
    )
    rc_mut, report_mut, _p = doctor(repo, script=mutant)
    assert rc_mut == EXIT_OK, "mutant did not reintroduce the defect"
    # the JSON still knows the truth -- which is exactly why asserting on the
    # PROCESS exit code (not an internal value) is the load-bearing check
    assert report_mut["exit_code"] == EXIT_UNSAFE
    assert rc_mut != rc_real, "the test would not have caught defect (a)"


def test_mutation_defect_b_basename_only_reporting(tmp_path):
    """R1 defect (b): two same-basename worktrees became indistinguishable."""
    repo, _key = init_repo(tmp_path / "repo")
    (tmp_path / "pA").mkdir()
    (tmp_path / "pB").mkdir()
    make_ciphertext_worktree(repo, tmp_path / "pA" / "lane", "a")
    bad = make_ciphertext_worktree(repo, tmp_path / "pB" / "lane", "b")
    (bad / "secret.json").write_bytes(SYNTHETIC)

    _rc, report, _p = doctor(repo)
    paths = [f["worktree_path"] for f in report["findings"]]
    assert len(paths) == len(set(paths)), "control leg: real tool is 1:1"

    mutant = _mutant(
        tmp_path,
        "        worktree_path=worktree_path,\n",
        "        worktree_path=os.path.basename(worktree_path),\n",
        "mut_b.py",
    )
    _rc, report_mut, _p = doctor(repo, script=mutant)
    mpaths = [f["worktree_path"] for f in report_mut["findings"]]
    assert len(mpaths) != len(set(mpaths)), "mutant did not reintroduce defect (b)"
    dupes = [p for p in set(mpaths) if mpaths.count(p) > 1]
    verdicts = {
        f["verdict"] for f in report_mut["findings"] if f["worktree_path"] in dupes
    }
    assert len(verdicts) > 1, "the collision did not produce opposite verdicts"


def test_mutation_defect_c_ungated_backfill_decrypts_protected_worktree(tmp_path):
    """R1 defect (c) end to end, including the checkout that flips the bytes.

    This is the prevention proof: with the guard the protected file is
    byte-identical after backfill AND after the checkout that normally
    follows; with the guard removed the same sequence materialises plaintext.
    """
    repo, _key, protected, _needy = _needy_repo(tmp_path)
    secret = protected / "secret.json"
    before = sha256(secret)
    assert is_ciphertext(secret)

    # --- control: the real tool refuses, and the bytes survive a checkout ---
    journal = tmp_path / "j.json"
    rc, report, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(protected),
        "--apply",
        "--journal",
        str(journal),
    )
    assert rc == EXIT_REFUSED
    assert report["plan"][0]["decision"] == "refuse"
    os.utime(secret, (0, 0))  # defeat the stat cache
    git(["checkout", "--", "secret.json"], cwd=protected)
    assert sha256(secret) == before, "protected bytes changed under the real tool"
    assert is_ciphertext(secret)

    # --- mutant: remove the ciphertext guard ---
    mutant = _mutant(
        tmp_path,
        "        elif finding.expected_state == MODE_CIPHERTEXT:",
        "        elif False:",
        "mut_c.py",
    )
    journal2 = tmp_path / "j2.json"
    rc, report, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(protected),
        "--apply",
        "--journal",
        str(journal2),
        script=mutant,
    )
    assert report["plan"][0]["decision"] == "configure", "mutant did not reintroduce"
    os.utime(secret, (0, 0))
    git(["checkout", "--", "secret.json"], cwd=protected)
    assert sha256(secret) != before, "mutant failed to demonstrate the defect"
    assert not is_ciphertext(secret), "plaintext was expected to materialise"

    # restore the fixture so the mutation leaves nothing behind
    rc, _r, _p = run_tool("rollback", "--journal", str(journal2), "--apply")
    assert rc == EXIT_OK


def test_mutation_signal_b_only_one_signal(tmp_path):
    """Dropping the second independent signal hides double-encryption."""
    repo, key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt", "b")
    secret = wt / "secret.json"
    # double-encrypt: run the ciphertext through git-crypt clean once more
    doubled = subprocess.run(
        ["git-crypt", "clean", f"--key-file={key}"],
        cwd=str(repo),
        input=secret.read_bytes(),
        capture_output=True,
        check=True,
    ).stdout
    secret.write_bytes(doubled)
    assert doubled.startswith(GITCRYPT_MAGIC), "fixture is not doubly encrypted"

    rc, report, _p = doctor(repo)
    found = finding_for(report, wt)
    assert found["files"][0]["state"] == "conflicted"
    assert rc == EXIT_AMBIGUOUS, report

    mutant = _mutant(
        tmp_path,
        '        probe.state = signal_a if probe.signals_agree else "conflicted"',
        "        probe.state = signal_a",
        "mut_sig.py",
    )
    rc_mut, report_mut, _p = doctor(repo, script=mutant)
    found_mut = finding_for(report_mut, wt)
    assert found_mut["files"][0]["state"] == "ciphertext"
    assert rc_mut == EXIT_OK, "single-signal mutant should report a false green"
    assert rc_mut != rc, "the test would not have caught the single-signal defect"


# ---------------------------------------------------------------------------
# read-only guarantee for `doctor`
# ---------------------------------------------------------------------------


def _tree_snapshot(root):
    """sha256 of every file under root, keyed by forward-slash relative path."""
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                snap[rel] = sha256(full)
            except OSError:
                snap[rel] = "<unreadable>"
    return snap


def _changed_paths(before, after):
    """Content changes, excluding git's own index stat-cache refresh.

    `git rev-parse :<path>` legitimately refreshes the index stat cache. That
    is metadata, not content, and is the ONLY exemption granted here.
    """
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    return sorted(k for k in changed if not k.endswith("index"))


def test_doctor_is_byte_for_byte_read_only(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "c")
    add_worktree(repo, tmp_path / "wt-plain", "p")

    before = _tree_snapshot(tmp_path)
    rc, _report, _p = doctor(repo)
    after = _tree_snapshot(tmp_path)

    assert _changed_paths(before, after) == [], "doctor mutated the tree"
    assert rc == EXIT_OK


def test_mutation_read_only_guarantee_is_actually_checked(tmp_path):
    """Both-states leg for the read-only assertion above.

    A doctor that writes must make `_changed_paths` non-empty. If it does
    not, the read-only test is measuring nothing.
    """
    repo, _key = init_repo(tmp_path / "repo")
    make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "c")

    mutant = _mutant(
        tmp_path,
        '    shared_smudge = cfg_get(repo_root, CFG_SMUDGE, scope="--local")',
        '    shared_smudge = cfg_get(repo_root, CFG_SMUDGE, scope="--local")\n'
        '    run_git(["config", "--local", "gitcrypt.doctorTouched", "1"],'
        " cwd=repo_root)",
        "mut_ro.py",
    )
    before = _tree_snapshot(tmp_path / "repo")
    doctor(repo, script=mutant)
    after = _tree_snapshot(tmp_path / "repo")
    assert _changed_paths(before, after) != [], (
        "the read-only detector stayed silent on a writing doctor -- it is "
        "not a valid detector"
    )
    assert ".git/config" in _changed_paths(before, after)


# ---------------------------------------------------------------------------
# AC7 -- every applied change is reversible via the journal
#
# Round 1 was REFUTED here. Four defects in one family, each reproduced
# independently before it was fixed (see 04r2-evidence/01-probe-f1-round1.json):
#
#   1. apply_plan() performed every `git config --worktree` write and opened
#      the journal afterwards, so an unwritable --journal path left the
#      configuration mutated with NO record of its prior values;
#   2. the resulting OSError escaped as an unhandled traceback, i.e. process
#      exit 1 -- which this contract defines as UNSAFE;
#   3. `--enable-worktree-config` wrote SHARED repo config and journalled
#      nothing, so a full `rollback --apply` returned 0 while leaving that
#      write in place -- a false green on the happy path;
#   4. a malformed journal entry was hit mid-walk, AFTER its predecessors had
#      already been restored: a partial rollback whose only signal was a
#      KeyError traceback.
#
# Scope, stated rather than implied: this is reversibility of CONFIGURATION.
# The ciphertext-preservation guarantee it protects is scoped to DECLARED
# intent -- a worktree holding ciphertext that declares nothing resolves to
# expected_state=plaintext and is a legitimate backfill target (README,
# "Scope of the guarantees").
# ---------------------------------------------------------------------------


EXIT_IO = 8


def _wt_cfg(cwd, key, scope="--worktree"):
    proc = git(["config", scope, "--get", key], cwd=cwd, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _meta_snapshot(root):
    """sha256 + size + mtime_ns for every file under root.

    Stronger than the read-only helper above: that one compares content only,
    this one also compares mtime, because AC7 asks for byte-identity in hash
    AND mtime.
    """
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                st = os.stat(full)
                snap[rel] = (sha256(full), st.st_size, st.st_mtime_ns)
            except OSError as exc:
                snap[rel] = ("<unreadable>", -1, str(exc))
    return snap


def _snapshot_delta(before, after):
    """Classify the delta. git's index stat-cache refresh is the ONE exemption.

    `git rev-parse :<path>` and `git hash-object` legitimately rewrite the
    index stat cache; that is metadata about the checkout, not repository
    state this tool changed.
    """
    delta = {"added": [], "removed": [], "content_changed": [], "mtime_changed": []}
    for rel in sorted(set(before) | set(after)):
        if os.path.basename(rel) == "index":
            continue
        b, a = before.get(rel), after.get(rel)
        if b is None:
            delta["added"].append(rel)
        elif a is None:
            delta["removed"].append(rel)
        elif b[0] != a[0] or b[1] != a[1]:
            delta["content_changed"].append(rel)
        elif b[2] != a[2]:
            delta["mtime_changed"].append(rel)
    return delta


def test_ac7_journal_is_durable_before_any_config_write(tmp_path):
    """Defect 1+2: no config write may land without a durable journal.

    Both legs in one test: an unusable journal path must change nothing and
    exit under a DEFINED code, and a usable one must still work.
    """
    repo, _key = init_repo(tmp_path / "repo")
    needy = add_worktree(repo, tmp_path / "wt", "b")
    before = _wt_cfg(needy, "filter.git-crypt.smudge")
    assert before is None, "fixture precondition: no worktree-scoped filter yet"

    # --- broken leg: the journal path cannot be written ---
    bad_journal = tmp_path / "no-such-dir" / "j.json"
    rc, _report, proc = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(needy),
        "--apply",
        "--journal",
        str(bad_journal),
    )
    assert rc == EXIT_IO, f"expected the defined IO code, got {rc}: {proc.stderr}"
    assert rc != EXIT_UNSAFE, "an unwritable path must not impersonate UNSAFE"
    assert not bad_journal.exists()
    assert _wt_cfg(needy, "filter.git-crypt.smudge") is None, (
        "config was mutated with no journal -- the change is unrollbackable"
    )
    assert "ARTIFACT ERROR" in proc.stderr

    # --- good leg: a usable journal path still performs the work ---
    good_journal = tmp_path / "j.json"
    rc, report, proc = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(needy),
        "--apply",
        "--journal",
        str(good_journal),
    )
    assert rc == EXIT_OK, report
    assert good_journal.exists()
    assert report["journal_status"] == "complete"
    assert _wt_cfg(needy, "filter.git-crypt.smudge") is not None
    assert not (tmp_path / "j.json.tmp").exists(), "atomic write left a temp file"

    # and the journal actually reverses it
    rc, rreport, _p = run_tool("rollback", "--journal", str(good_journal), "--apply")
    assert rc == EXIT_OK, rreport
    assert rreport["unrestored"] == 0
    assert _wt_cfg(needy, "filter.git-crypt.smudge") is None


def test_ac7_enable_worktree_config_write_is_journalled_and_reversible(tmp_path):
    """Defect 3: the SHARED extensions.worktreeConfig write is an applied change."""
    repo, _key = init_repo(tmp_path / "repo")
    add_worktree(repo, tmp_path / "wt", "b")
    git(["config", "--local", "--unset", "extensions.worktreeConfig"], cwd=repo)
    before = _wt_cfg(repo, "extensions.worktreeConfig", scope="--local")
    assert before is None, "fixture precondition: the extension is off"

    journal = tmp_path / "j.json"
    rc, report, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--all",
        "--apply",
        "--enable-worktree-config",
        "--journal",
        str(journal),
    )
    assert rc == EXIT_OK, report
    assert report["enabled_worktree_config"] is True
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") == "true"
    # the shared write is IN the journal, at --local scope
    entries = json.loads(journal.read_text(encoding="utf-8"))["entries"]
    shared = [e for e in entries if e.get("scope") == "--local"]
    assert len(shared) == 1, entries
    assert shared[0]["restore"][0]["key"] == "extensions.worktreeConfig"
    assert shared[0]["restore"][0]["prior"] is None

    rc, rreport, _p = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_OK, rreport
    assert rreport["unrestored"] == 0
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") is None, (
        "the shared config write survived a full rollback"
    )


def _two_needy_worktrees(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt1 = add_worktree(repo, tmp_path / "wt1", "b1")
    wt2 = add_worktree(repo, tmp_path / "wt2", "b2")
    journal = tmp_path / "j.json"
    rc, report, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(wt1),
        "--worktree",
        str(wt2),
        "--apply",
        "--journal",
        str(journal),
    )
    assert rc == EXIT_OK, report
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") is not None
    assert _wt_cfg(wt2, "filter.git-crypt.smudge") is not None
    return repo, wt1, wt2, journal


def test_ac7_corrupt_journal_refuses_instead_of_partial_rollback(tmp_path):
    """Defect 4: a bad entry must abort the WHOLE rollback, not half of it."""
    _repo, wt1, wt2, journal = _two_needy_worktrees(tmp_path)
    applied1 = _wt_cfg(wt1, "filter.git-crypt.smudge")
    applied2 = _wt_cfg(wt2, "filter.git-crypt.smudge")
    # captured BEFORE any corruption: reading it back afterwards would capture
    # the corrupt file and make the good leg assert the wrong thing.
    pristine = journal.read_text(encoding="utf-8")

    # --- corruption shape A: a structurally malformed entry ---
    data = json.loads(journal.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 2, data
    data["entries"][-1].pop("restore")
    journal.write_text(json.dumps(data, indent=2), encoding="utf-8")

    rc, _report, proc = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_USAGE, proc.stderr
    assert "partial rollback" in proc.stderr
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") == applied1, (
        "entry 0 was restored before the malformed entry aborted the run"
    )
    assert _wt_cfg(wt2, "filter.git-crypt.smudge") == applied2

    # --- corruption shape B: the file itself is truncated ---
    journal.write_text(pristine[: len(pristine) // 2], encoding="utf-8")
    rc, _report, proc = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_USAGE, proc.stderr
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") == applied1
    assert _wt_cfg(wt2, "filter.git-crypt.smudge") == applied2

    # --- good leg: the intact journal still rolls both back ---
    journal.write_text(pristine, encoding="utf-8")
    rc, rreport, _p = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_OK, rreport
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") is None
    assert _wt_cfg(wt2, "filter.git-crypt.smudge") is None


# ---------------------------------------------------------------------------
# AC7 across ALL TEN fixture states, not just one
# ---------------------------------------------------------------------------


def _state01_expected_plaintext(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    add_worktree(repo, tmp_path / "wt-plain", "plain")
    return repo


def _state02_expected_ciphertext(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "cipher")
    return repo


def _state03_unexpectedly_plaintext(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt-cipher", "cipher")
    (wt / "secret.json").write_bytes(SYNTHETIC)
    return repo


def _state04_unexpectedly_ciphertext(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = make_ciphertext_worktree(repo, tmp_path / "wt", "b", declare=False)
    for key in (
        "filter.git-crypt.smudge",
        "filter.git-crypt.clean",
        "filter.git-crypt.required",
    ):
        git(["config", "--worktree", "--unset-all", key], cwd=wt, check=False)
    git(["config", "--worktree", "gitcrypt.worktreeMode", "plaintext"], cwd=wt)
    return repo


def _state05_missing_key(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    clone = tmp_path / "clone"
    git(["clone", "--no-hardlinks", "-q", str(repo), str(clone)], cwd=tmp_path)
    git(["config", "extensions.worktreeConfig", "true"], cwd=clone)
    git(["config", "--worktree", "gitcrypt.worktreeMode", "plaintext"], cwd=clone)
    return clone


def _state06_unreadable(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = add_worktree(repo, tmp_path / "wt", "b")
    secret = wt / "secret.json"
    os.remove(secret)
    secret.mkdir()
    return repo


def _state07_same_basename(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    (tmp_path / "parentA").mkdir()
    (tmp_path / "parentB").mkdir()
    make_ciphertext_worktree(repo, tmp_path / "parentA" / "lane", "a")
    bad = make_ciphertext_worktree(repo, tmp_path / "parentB" / "lane", "b")
    (bad / "secret.json").write_bytes(SYNTHETIC)
    return repo


def _state08_partially_materialised(tmp_path):
    repo, _key = init_repo(tmp_path / "repo", secrets=("secret.json", "secret2.json"))
    wt = add_worktree(repo, tmp_path / "wt", "b")
    oid = git(["rev-parse", ":secret2.json"], cwd=wt).stdout.strip()
    blob = subprocess.run(
        ["git", "cat-file", "blob", oid], cwd=str(wt), capture_output=True, check=True
    ).stdout
    (wt / "secret2.json").write_bytes(blob)
    return repo


def _state09_eol_churn(tmp_path):
    repo, _key = init_repo(tmp_path / "repo")
    wt = add_worktree(repo, tmp_path / "wt", "b")
    secret = wt / "secret.json"
    secret.write_bytes(secret.read_bytes().replace(b"\n", b"\r\n"))
    os.utime(secret, (0, 0))
    return repo


def _state10_needy_and_protected(tmp_path):
    repo, _key, _protected, _needy = _needy_repo(tmp_path)
    return repo


TEN_STATES = [
    ("01-expected-plaintext", _state01_expected_plaintext),
    ("02-expected-ciphertext", _state02_expected_ciphertext),
    ("03-unexpectedly-plaintext", _state03_unexpectedly_plaintext),
    ("04-unexpectedly-ciphertext", _state04_unexpectedly_ciphertext),
    ("05-missing-key", _state05_missing_key),
    ("06-unreadable", _state06_unreadable),
    ("07-same-basename", _state07_same_basename),
    ("08-partially-materialised", _state08_partially_materialised),
    ("09-eol-churn", _state09_eol_churn),
    ("10-needy-and-protected", _state10_needy_and_protected),
]


@pytest.mark.parametrize("name,builder", TEN_STATES, ids=[s[0] for s in TEN_STATES])
def test_ac7_rollback_restores_every_fixture_state(tmp_path, name, builder):
    """apply -> rollback must restore the tree, and the claim is scoped.

    What holds, measured on all ten states rather than assumed:

    * NOTHING outside `.git/` changes at all -- not content, not size, not
      mtime. That is the repository content, including every ciphertext
      secret. This is the assertion that matters.
    * Inside `.git/`, no file changes CONTENT and none is removed.
    * mtime is NOT preserved for the git config files the tool legitimately
      wrote to and then restored. It cannot be: they were rewritten twice.
      Their bytes are identical, which is the property reversibility needs.
      Measured on states 04 and 10, whose worktrees already carried a
      `config.worktree`; the earlier draft of this test claimed mtime
      identity for them and was wrong.
    * The only new files permitted are the journal the caller asked for and
      EMPTY `config.worktree` files, which git materialises on the first
      worktree-scoped write and does not remove when the last key is unset.
      Their size is asserted zero -- configuration left in them would be an
      unreversed change.
    """
    repo = builder(tmp_path)
    journal = tmp_path / "journal.json"

    before = _meta_snapshot(tmp_path)
    rc_apply, areport, aproc = run_tool(
        "backfill", "--repo", str(repo), "--all", "--apply", "--journal", str(journal)
    )
    assert_no_secret_leak(aproc)
    assert rc_apply != EXIT_IO, aproc.stderr
    assert journal.exists(), "the write-ahead journal must exist after --apply"
    assert areport["journal_status"] == "complete"

    rc_rb, rreport, rproc = run_tool("rollback", "--journal", str(journal), "--apply")
    assert_no_secret_leak(rproc)
    assert rc_rb == EXIT_OK, rreport
    assert rreport["unrestored"] == 0, rreport
    for action in rreport["actions"]:
        assert action["verified"] is True, action

    after = _meta_snapshot(tmp_path)
    delta = _snapshot_delta(before, after)

    # 1. The repository CONTENT is untouched in every respect.
    for bucket in ("added", "removed", "content_changed", "mtime_changed"):
        outside_git = [
            rel
            for rel in delta[bucket]
            if "/.git/" not in f"/{rel}" and rel != "journal.json"
        ]
        assert outside_git == [], (bucket, outside_git, delta)

    # 2. Inside .git/, nothing loses or changes content.
    assert delta["removed"] == [], delta
    assert delta["content_changed"] == [], delta

    # 3. The only permitted mtime churn is a git config file this tool wrote
    #    to and restored. Its BYTES are identical (asserted above); only its
    #    mtime is fresh, which is unavoidable once a file is written at all.
    for rel in delta["mtime_changed"]:
        assert os.path.basename(rel) in ("config", "config.worktree"), (
            f"unexpected mtime churn: {rel}"
        )

    # 4. New files: the journal, and EMPTY config.worktree files only.
    for rel in delta["added"]:
        if rel == "journal.json":
            continue
        assert os.path.basename(rel) == "config.worktree", f"residue: {rel}"
        assert (tmp_path / rel).stat().st_size == 0, (
            f"{rel} was left carrying configuration after rollback"
        )


# ---------------------------------------------------------------------------
# AC7 MUTATION TESTS -- reintroduce each defect, prove the new tests go red
# ---------------------------------------------------------------------------


def test_mutation_ac7_journal_write_failure_is_swallowed(tmp_path):
    """Defect 1 reintroduced: writes land, journal does not, nobody is told."""
    repo, _key = init_repo(tmp_path / "repo")
    needy = add_worktree(repo, tmp_path / "wt", "b")
    bad_journal = tmp_path / "no-such-dir" / "j.json"

    # control leg: the real tool changes nothing and says so under a real code
    rc, _r, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(needy),
        "--apply",
        "--journal",
        str(bad_journal),
    )
    assert rc == EXIT_IO
    assert _wt_cfg(needy, "filter.git-crypt.smudge") is None

    mutant = _mutant(
        tmp_path,
        '    tmp = f"{journal_path}.tmp"\n',
        '    tmp = f"{journal_path}.tmp"\n'
        "    return journal  # MUTANT: journal writes silently do nothing\n",
        "mut_j.py",
    )
    rc_mut, _r, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--worktree",
        str(needy),
        "--apply",
        "--journal",
        str(bad_journal),
        script=mutant,
    )
    assert not bad_journal.exists(), "mutant did not reintroduce the defect"
    assert _wt_cfg(needy, "filter.git-crypt.smudge") is not None, (
        "mutant failed to demonstrate an unrollbackable config write"
    )
    assert rc_mut != EXIT_IO, "the mutant must NOT report the defined IO code"


def test_mutation_ac7_rollback_skips_malformed_entry_instead_of_refusing(tmp_path):
    """Defect 4 reintroduced as its worst form: a SILENT partial rollback."""
    _repo, wt1, wt2, journal = _two_needy_worktrees(tmp_path)
    applied1 = _wt_cfg(wt1, "filter.git-crypt.smudge")

    data = json.loads(journal.read_text(encoding="utf-8"))
    data["entries"][-1].pop("restore")
    journal.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # control leg: the real tool refuses and restores nothing
    rc, _r, _p = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_USAGE
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") == applied1

    mutant = _mutant(
        tmp_path,
        "    steps = validate_journal(journal, norm(journal_path))\n",
        "    steps = [\n"
        "        {\n"
        '            "worktree_path": e.get("worktree_path", ""),\n'
        '            "scope": e.get("scope", "--worktree"),\n'
        '            "key": r["key"],\n'
        '            "restore_to": r["prior"],\n'
        "        }\n"
        '        for e in journal.get("entries", [])\n'
        '        for r in e.get("restore", [])\n'
        "    ]\n",
        "mut_val.py",
    )
    rc_mut, rreport, _p = run_tool(
        "rollback", "--journal", str(journal), "--apply", script=mutant
    )
    assert rc_mut == EXIT_OK, "mutant did not reintroduce the false green"
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") is None, (
        "mutant failed to demonstrate a partial rollback"
    )
    assert rc_mut != rc, "the test would not have caught the partial-rollback defect"


def test_mutation_ac7_rollback_verification_is_a_real_detector(tmp_path):
    """A rollback that restores nothing must NOT be able to report success."""
    _repo, wt1, _wt2, journal = _two_needy_worktrees(tmp_path)
    applied1 = _wt_cfg(wt1, "filter.git-crypt.smudge")
    assert applied1 is not None

    mutant = _mutant(
        tmp_path,
        "    error = None\n    if prior is None:\n",
        "    error = None\n"
        "    if True:  # MUTANT: perform no restore at all\n"
        "        pass\n"
        "    elif prior is None:\n",
        "mut_verify.py",
    )
    rc_mut, rreport_mut, _p = run_tool(
        "rollback", "--journal", str(journal), "--apply", script=mutant
    )
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") == applied1, (
        "mutant did not reintroduce the no-op restore"
    )
    assert rc_mut == EXIT_INCONSISTENT, "verification stayed silent on a no-op restore"
    assert rreport_mut["unrestored"] > 0
    assert any(a["verified"] is False for a in rreport_mut["actions"])

    # control leg: the real tool restores and verifies
    rc, rreport, _p = run_tool("rollback", "--journal", str(journal), "--apply")
    assert rc == EXIT_OK, rreport
    assert rreport["unrestored"] == 0
    assert _wt_cfg(wt1, "filter.git-crypt.smudge") is None


def test_mutation_ac7_shared_ext_write_is_recorded_at_the_wrong_scope(tmp_path):
    """Defect 3 reintroduced: journal the shared write, but not reversibly."""
    repo, _key = init_repo(tmp_path / "repo")
    add_worktree(repo, tmp_path / "wt", "b")
    git(["config", "--local", "--unset", "extensions.worktreeConfig"], cwd=repo)

    mutant = _mutant(
        tmp_path,
        '                    "worktree_path": repo_root,\n'
        '                    "scope": "--local",\n',
        '                    "worktree_path": repo_root,\n'
        '                    "scope": "--worktree",\n',
        "mut_ext.py",
    )
    journal = tmp_path / "jm.json"
    rc, _r, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--all",
        "--apply",
        "--enable-worktree-config",
        "--journal",
        str(journal),
        script=mutant,
    )
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") == "true"
    run_tool("rollback", "--journal", str(journal), "--apply", script=mutant)
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") == "true", (
        "mutant did not reintroduce the unreversed shared write"
    )

    # control leg: the real tool records it at --local and reverses it
    git(["config", "--local", "--unset", "extensions.worktreeConfig"], cwd=repo)
    journal2 = tmp_path / "jr.json"
    rc, _r, _p = run_tool(
        "backfill",
        "--repo",
        str(repo),
        "--all",
        "--apply",
        "--enable-worktree-config",
        "--journal",
        str(journal2),
    )
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") == "true"
    rc, rreport, _p = run_tool("rollback", "--journal", str(journal2), "--apply")
    assert rc == EXIT_OK, rreport
    assert _wt_cfg(repo, "extensions.worktreeConfig", scope="--local") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
