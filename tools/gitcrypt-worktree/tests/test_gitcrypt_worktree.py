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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
