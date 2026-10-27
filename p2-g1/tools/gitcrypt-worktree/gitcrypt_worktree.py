#!/usr/bin/env python3
"""git-crypt worktree doctor + backfill.

Replaces the R1 section-5b shell doctor/backfill pair, which had four
defects proven in ``04a-repro-gitcrypt-worktree.md``:

(a) the doctor's process exit code was unconditionally ``0`` (``rc=1`` was
    assigned inside a piped ``while``, i.e. a subshell, and discarded),
(b) findings were reported by ``basename`` only, so two worktrees sharing a
    basename produced identical rows with opposite verdicts,
(c) the backfill was ungated: it rewrote git-crypt filters into *every*
    worktree, including ones deliberately configured to preserve ciphertext,
(d) the worktree counts quoted in R1 were wrong.

Design rules this module holds to:

* ``doctor`` is READ-ONLY. It never writes config, never writes a file, and
  never runs a git command that materialises or converts content.
* ``backfill`` defaults to DRY-RUN, requires an explicit target selection,
  classifies each target *before* touching it, refuses states it cannot
  classify, and never reconfigures a ciphertext-preserving worktree merely
  because a key exists elsewhere.
* No secret content is ever read into the report. Files are classified from
  a 10-byte header probe and from object-id comparison; the report carries
  sizes, object ids and booleans only.

Exit codes (see README.md for the full contract)::

    0  OK           every inspected worktree matched its expected state
    1  UNSAFE       >=1 worktree risks secret exposure or blob corruption
    2  USAGE        invocation error (not a repo, bad/absent selection)
    3  AMBIGUOUS    >=1 worktree could not be classified
    4  UNREADABLE   >=1 required path could not be read
    5  INCONSISTENT >=1 worktree's declared intent contradicts its config
    6  MISMATCH     observed differs from expected, but is not unsafe
    7  REFUSED      a mutation was requested and denied by a safety gate
    8  IO           an output artifact (journal / --json-out) is unwritable

The process exit code is the highest-severity code across all findings, in
the precedence order USAGE > IO > UNREADABLE > AMBIGUOUS > INCONSISTENT >
UNSAFE > REFUSED > MISMATCH > OK.

``backfill --apply`` is protected by a WRITE-AHEAD journal: the complete
pre-image of every configuration key it is about to write -- including the
shared ``extensions.worktreeConfig`` flag -- is fsync'd to the ``--journal``
path BEFORE the first mutation. ``rollback`` validates the whole journal
before restoring anything, restores in reverse order, and verifies each
restore by re-reading the key, so a partial rollback cannot report success.

Scope of the ciphertext guarantee: it holds for DECLARED intent. A worktree
that holds ciphertext but declares nothing (no ``gitcrypt.worktreeMode``, no
worktree-scoped identity filter) resolves to ``expected_state=plaintext`` and
is a legitimate backfill target. See README "Scope of the guarantees".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict

EXIT_OK = 0
EXIT_UNSAFE = 1
EXIT_USAGE = 2
EXIT_AMBIGUOUS = 3
EXIT_UNREADABLE = 4
EXIT_INCONSISTENT = 5
EXIT_MISMATCH = 6
EXIT_REFUSED = 7
EXIT_IO = 8

EXIT_NAMES = {
    EXIT_OK: "OK",
    EXIT_UNSAFE: "UNSAFE",
    EXIT_USAGE: "USAGE",
    EXIT_AMBIGUOUS: "AMBIGUOUS",
    EXIT_UNREADABLE: "UNREADABLE",
    EXIT_INCONSISTENT: "INCONSISTENT",
    EXIT_MISMATCH: "MISMATCH",
    EXIT_REFUSED: "REFUSED",
    EXIT_IO: "IO",
}

# Highest severity first. The process exit code is the first code in this
# list that appears among the findings.
SEVERITY_ORDER = (
    EXIT_USAGE,
    EXIT_IO,
    EXIT_UNREADABLE,
    EXIT_AMBIGUOUS,
    EXIT_INCONSISTENT,
    EXIT_UNSAFE,
    EXIT_REFUSED,
    EXIT_MISMATCH,
    EXIT_OK,
)

GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"

# Values accepted for the explicit intent marker.
MODE_PLAINTEXT = "plaintext"
MODE_CIPHERTEXT = "ciphertext"
VALID_MODES = (MODE_PLAINTEXT, MODE_CIPHERTEXT)

# git config keys this tool reads and (only in backfill --apply) writes.
CFG_MODE = "gitcrypt.worktreeMode"
CFG_SMUDGE = "filter.git-crypt.smudge"
CFG_CLEAN = "filter.git-crypt.clean"
CFG_REQUIRED = "filter.git-crypt.required"
CFG_TEXTCONV = "diff.git-crypt.textconv"
CFG_WORKTREE_EXT = "extensions.worktreeConfig"

JOURNAL_VERSION = 2
# v1 journals carried no ``scope`` and no ``status``; their entries are
# worktree-scoped by construction, so they remain readable by ``rollback``.
SUPPORTED_JOURNAL_VERSIONS = (1, 2)


class ToolError(Exception):
    """A usage-level failure: reported and mapped to EXIT_USAGE."""


class ArtifactError(Exception):
    """An output artifact could not be written: mapped to EXIT_IO.

    Raised only for the rollback journal and ``--json-out``. It exists so an
    ``OSError`` on those paths cannot escape as an unhandled traceback, whose
    process exit code 1 is this contract's UNSAFE. A caller doing exit-code
    dispatch would otherwise read "the journal directory does not exist" as
    "a worktree holds plaintext against its declared intent".
    """


# --------------------------------------------------------------------------
# process / path helpers
# --------------------------------------------------------------------------


def run_git(args, cwd=None):
    """Run git with a literal argv (never a shell). Returns (rc, out, err)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_git_bytes(args, cwd=None, stdin_bytes=None):
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=stdin_bytes,
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def norm(path):
    """Absolute, symlink-resolved, forward-slash path.

    Forward slashes matter on Windows: a backslash path passed back to git as
    a revision or pathspec is a known failure mode, and mixed separators make
    two spellings of one worktree look like two worktrees.
    """
    return os.path.realpath(os.path.abspath(str(path))).replace("\\", "/")


def path_key(path):
    """Comparison key for worktree identity (Windows paths are case-folded)."""
    return norm(path).casefold()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------


@dataclass
class FileProbe:
    """Per-file classification. Carries NO file content."""

    path_rel: str
    path_abs: str
    present: bool
    size: int | None = None
    sha256: str | None = None
    magic_gitcrypt: bool | None = None
    index_oid: str | None = None
    raw_oid: str | None = None
    signals_agree: bool | None = None
    state: str = "absent"  # plaintext|ciphertext|absent|unreadable|conflicted
    error: str | None = None


@dataclass
class Finding:
    worktree_path: str
    gitdir_entry: str
    gitdir_path: str
    repo_relative_path: str
    is_main: bool
    head: str
    branch: str
    expected_state: str
    expected_source: str
    observed_state: str
    key_available: bool
    key_source: str
    verdict: str
    exit_code: int
    risk: str
    safe_next_action: str
    action_performed: str
    owner_approval_required: bool
    detail: list = field(default_factory=list)
    files: list = field(default_factory=list)

    def to_dict(self):
        out = asdict(self)
        out["files"] = [asdict(f) if not isinstance(f, dict) else f for f in self.files]
        return out


# --------------------------------------------------------------------------
# repository / worktree enumeration
# --------------------------------------------------------------------------


def resolve_repo(repo_arg):
    rc, out, err = run_git(["rev-parse", "--show-toplevel"], cwd=repo_arg)
    if rc != 0:
        raise ToolError(f"not a git repository: {repo_arg} ({err.strip()})")
    return norm(out.strip())


def git_common_dir(repo_root):
    rc, out, err = run_git(["rev-parse", "--git-common-dir"], cwd=repo_root)
    if rc != 0:
        raise ToolError(f"cannot resolve --git-common-dir ({err.strip()})")
    common = out.strip()
    if not os.path.isabs(common):
        common = os.path.join(repo_root, common)
    return norm(common)


def enumerate_worktrees(repo_root, common):
    """Enumerate worktrees from TWO mechanically independent sources.

    S1 is git's own registry (``git worktree list --porcelain``).
    S2 is the filesystem (``<common>/worktrees/*``).

    Neither is trusted alone: a disagreement is surfaced rather than silently
    resolved. Names are never pattern-matched against expectations.
    """
    rc, out, err = run_git(["worktree", "list", "--porcelain"], cwd=repo_root)
    if rc != 0:
        raise ToolError(f"git worktree list failed ({err.strip()})")

    s1 = []
    current = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                s1.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current = {"path": norm(line[len("worktree ") :])}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :].strip()
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :].strip()
        elif line.strip() == "detached":
            current["branch"] = "(detached)"
        elif line.strip() == "bare":
            current["bare"] = True
    if current:
        s1.append(current)

    wt_dir = os.path.join(common, "worktrees")
    s2 = []
    if os.path.isdir(wt_dir):
        for entry in sorted(os.listdir(wt_dir)):
            gitdir_file = os.path.join(wt_dir, entry, "gitdir")
            target = None
            if os.path.isfile(gitdir_file):
                try:
                    with open(gitdir_file, encoding="utf-8") as handle:
                        raw = handle.read().strip()
                    # <path>/.git -> the worktree root is its parent
                    target = norm(os.path.dirname(raw)) if raw else None
                except OSError:
                    target = None
            s2.append({"entry": entry, "path": target})

    s1_keys = {path_key(w["path"]) for w in s1 if not w.get("bare")}
    s2_keys = {path_key(w["path"]) for w in s2 if w["path"]}
    # The main worktree has no entry under <common>/worktrees, so it is
    # expected to be S1-only and is excluded from the disagreement set.
    main_key = path_key(s1[0]["path"]) if s1 else None
    s1_only = sorted(k for k in s1_keys - s2_keys if k != main_key)
    s2_only = sorted(s2_keys - s1_keys)

    return s1, s2, {"s1_only": s1_only, "s2_only": s2_only}


def resolve_gitdir(worktree_path, common):
    """Resolve a worktree's gitdir from its ``.git`` FILE.

    Deliberately not ``git rev-parse --git-dir``: that resolves relative to
    the *invoking* directory and was the source of a false green in R1.
    """
    dot_git = os.path.join(worktree_path, ".git")
    if os.path.isdir(dot_git):
        return norm(dot_git), "(main)", None
    if os.path.isfile(dot_git):
        try:
            with open(dot_git, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            return None, "(unreadable)", f"cannot read {dot_git}: {exc}"
        for line in text.splitlines():
            if line.startswith("gitdir:"):
                gd = line.split(":", 1)[1].strip()
                if not os.path.isabs(gd):
                    gd = os.path.join(worktree_path, gd)
                gd = norm(gd)
                return gd, os.path.basename(gd), None
        return None, "(unreadable)", f"{dot_git} has no 'gitdir:' line"
    return None, "(missing)", f"no .git entry at {dot_git}"


# --------------------------------------------------------------------------
# configuration reads
# --------------------------------------------------------------------------


def cfg_get(cwd, key, scope=None):
    args = ["config"]
    if scope:
        args.append(scope)
    args += ["--get", key]
    rc, out, _ = run_git(args, cwd=cwd)
    if rc != 0:
        return None
    value = out.strip()
    return value if value else None


def worktree_config_enabled(repo_root):
    value = cfg_get(repo_root, CFG_WORKTREE_EXT, scope="--local")
    return (value or "").strip().lower() == "true"


def is_identity_filter(value):
    """True when the filter passes bytes through unchanged (ciphertext kept)."""
    if value is None:
        return False
    return value.strip().strip('"').lower() in ("cat", "cat -", "/bin/cat", "type")


def filter_has_keyfile(value):
    return bool(value) and "--key-file" in value


def keyfile_path_from_filter(value):
    if not value or "--key-file" not in value:
        return None
    tail = value.split("--key-file", 1)[1].lstrip()
    if tail.startswith("="):
        tail = tail[1:]
    tail = tail.strip()
    if tail.startswith('"'):
        return tail[1:].split('"', 1)[0]
    return tail.split(" ")[0] if tail else None


# --------------------------------------------------------------------------
# file classification (two independent signals, no content retained)
# --------------------------------------------------------------------------


def filtered_paths(worktree_path):
    """Paths in the index whose ``filter`` attribute is ``git-crypt``."""
    rc, out, _ = run_git_bytes(["ls-files", "-z"], cwd=worktree_path)
    if rc != 0:
        return None
    entries = [p for p in out.split(b"\0") if p]
    if not entries:
        return []
    payload = b"\0".join(entries) + b"\0"
    rc, attr_out, _ = run_git_bytes(
        ["check-attr", "--stdin", "-z", "filter"],
        cwd=worktree_path,
        stdin_bytes=payload,
    )
    if rc != 0:
        return None
    fields = attr_out.split(b"\0")
    result = []
    for i in range(0, len(fields) - 2, 3):
        path, _attr, value = fields[i], fields[i + 1], fields[i + 2]
        if value.decode("utf-8", "replace") == "git-crypt":
            result.append(path.decode("utf-8", "replace"))
    return sorted(result)


def probe_file(worktree_path, rel_path):
    """Classify one filtered path using two mechanically independent signals.

    Signal A -- the 10-byte git-crypt header magic.
    Signal B -- raw on-disk object id (``hash-object --no-filters``) versus
                the index object id. Equal means the working file is
                byte-identical to the stored (encrypted) blob.

    A disagreement is reported as ``conflicted`` rather than guessed. That is
    the state a doubly-encrypted working file lands in.
    """
    abs_path = norm(os.path.join(worktree_path, rel_path))
    probe = FileProbe(path_rel=rel_path, path_abs=abs_path, present=False)

    if not os.path.exists(abs_path):
        probe.state = "absent"
        return probe
    probe.present = True

    try:
        with open(abs_path, "rb") as handle:
            head = handle.read(len(GITCRYPT_MAGIC))
        probe.size = os.path.getsize(abs_path)
        probe.sha256 = sha256_file(abs_path)
    except OSError as exc:
        probe.state = "unreadable"
        probe.error = f"{type(exc).__name__}: {exc.strerror or exc}"
        return probe

    probe.magic_gitcrypt = head == GITCRYPT_MAGIC

    rc, out, _ = run_git(["rev-parse", f":{rel_path}"], cwd=worktree_path)
    probe.index_oid = out.strip() if rc == 0 else None
    rc, out, _ = run_git(
        ["hash-object", "--no-filters", "--", rel_path], cwd=worktree_path
    )
    probe.raw_oid = out.strip() if rc == 0 else None

    signal_a = MODE_CIPHERTEXT if probe.magic_gitcrypt else MODE_PLAINTEXT
    if probe.index_oid and probe.raw_oid:
        signal_b = (
            MODE_CIPHERTEXT if probe.index_oid == probe.raw_oid else MODE_PLAINTEXT
        )
        probe.signals_agree = signal_a == signal_b
        probe.state = signal_a if probe.signals_agree else "conflicted"
    else:
        # Only one signal available; say so rather than pretending to two.
        probe.signals_agree = None
        probe.state = signal_a
    return probe


def summarise_files(probes):
    if not probes:
        return "no-filtered-paths"
    states = {p.state for p in probes}
    if "unreadable" in states:
        return "unreadable"
    if "conflicted" in states:
        return "conflicted"
    materialised = {p.state for p in probes if p.state != "absent"}
    absent = any(p.state == "absent" for p in probes)
    if not materialised:
        return "absent"
    if len(materialised) > 1 or absent:
        return "partial"
    return materialised.pop()


# --------------------------------------------------------------------------
# expectation resolution and verdict
# --------------------------------------------------------------------------


def resolve_expectation(worktree_path, wt_smudge, shared_smudge, key_available):
    declared = cfg_get(worktree_path, CFG_MODE, scope="--worktree")
    if declared:
        declared = declared.strip().lower()
        if declared in VALID_MODES:
            return declared, "declared"
        return "unknown", f"declared-invalid:{declared}"
    if is_identity_filter(wt_smudge):
        return MODE_CIPHERTEXT, "worktree-filter-identity"
    if filter_has_keyfile(wt_smudge):
        return MODE_PLAINTEXT, "worktree-filter-keyfile"
    if wt_smudge:
        return MODE_PLAINTEXT, "worktree-filter-gitcrypt"
    if is_identity_filter(shared_smudge):
        return MODE_CIPHERTEXT, "shared-filter-identity"
    if shared_smudge:
        return MODE_PLAINTEXT, "shared-filter"
    if key_available:
        return MODE_PLAINTEXT, "key-present-no-filter"
    return MODE_CIPHERTEXT, "no-filter-no-key-default"


def detect_inconsistency(expected, expected_source, wt_smudge, shared_smudge):
    """Declared intent contradicting the effective filter configuration.

    This is the exact state R1's ungated backfill left behind: the worktree
    still declares ``worktreeMode = ciphertext`` while its filters have been
    rewritten to decrypt.
    """
    if expected_source != "declared":
        return None
    effective = wt_smudge if wt_smudge is not None else shared_smudge
    if expected == MODE_CIPHERTEXT and filter_has_keyfile(effective):
        return (
            f"declares {CFG_MODE}=ciphertext but the effective "
            f"{CFG_SMUDGE} decrypts (--key-file present)"
        )
    if expected == MODE_CIPHERTEXT and effective and not is_identity_filter(effective):
        return (
            f"declares {CFG_MODE}=ciphertext but the effective "
            f"{CFG_SMUDGE} is a git-crypt filter, not an identity filter"
        )
    if expected == MODE_PLAINTEXT and is_identity_filter(effective):
        return (
            f"declares {CFG_MODE}=plaintext but the effective "
            f"{CFG_SMUDGE} is an identity filter and cannot decrypt"
        )
    return None


def classify(repo_root, common, entry, shared_smudge):
    worktree_path = entry["path"]
    head = entry.get("head", "(unknown)")
    branch = entry.get("branch", "(detached)")
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/") :]

    gitdir, gitdir_entry, gitdir_err = resolve_gitdir(worktree_path, common)
    is_main = gitdir_entry == "(main)"

    rel = os.path.relpath(worktree_path, repo_root).replace("\\", "/")
    repo_relative = rel if not rel.startswith("..") else f"external:{worktree_path}"

    finding = Finding(
        worktree_path=worktree_path,
        gitdir_entry=gitdir_entry,
        gitdir_path=gitdir or "(unresolved)",
        repo_relative_path=repo_relative,
        is_main=is_main,
        head=head,
        branch=branch,
        expected_state="unknown",
        expected_source="unresolved",
        observed_state="unknown",
        key_available=False,
        key_source="none",
        verdict="UNREADABLE",
        exit_code=EXIT_UNREADABLE,
        risk="cannot-inspect",
        safe_next_action="investigate manually; do not run backfill on it",
        action_performed="none",
        owner_approval_required=True,
    )

    if not os.path.isdir(worktree_path):
        finding.detail.append(
            "registered worktree path does not exist on disk (prunable)"
        )
        finding.observed_state = "worktree-missing"
        finding.safe_next_action = (
            "confirm with the owner, then `git worktree prune` if intended"
        )
        return finding
    if gitdir_err:
        finding.detail.append(gitdir_err)
        return finding

    wt_smudge = cfg_get(worktree_path, CFG_SMUDGE, scope="--worktree")
    key_available, key_source = resolve_key(common, gitdir, wt_smudge, shared_smudge)

    expected, expected_source = resolve_expectation(
        worktree_path, wt_smudge, shared_smudge, key_available
    )
    finding.expected_state = expected
    finding.expected_source = expected_source
    finding.key_available = key_available
    finding.key_source = key_source

    paths = filtered_paths(worktree_path)
    if paths is None:
        finding.detail.append("could not enumerate git-crypt-filtered paths")
        return finding
    probes = [probe_file(worktree_path, p) for p in paths]
    finding.files = probes
    observed = summarise_files(probes)
    finding.observed_state = observed

    inconsistency = detect_inconsistency(
        expected, expected_source, wt_smudge, shared_smudge
    )

    finding.detail.append(
        f"{len(probes)} filtered path(s); "
        f"plaintext={sum(1 for p in probes if p.state == MODE_PLAINTEXT)} "
        f"ciphertext={sum(1 for p in probes if p.state == MODE_CIPHERTEXT)} "
        f"absent={sum(1 for p in probes if p.state == 'absent')} "
        f"unreadable={sum(1 for p in probes if p.state == 'unreadable')} "
        f"conflicted={sum(1 for p in probes if p.state == 'conflicted')}"
    )

    if observed == "unreadable":
        bad = [p for p in probes if p.state == "unreadable"]
        finding.verdict, finding.exit_code = "UNREADABLE", EXIT_UNREADABLE
        finding.risk = "cannot-inspect"
        finding.detail += [f"unreadable: {p.path_abs} ({p.error})" for p in bad]
        finding.safe_next_action = (
            "restore read access to the listed path(s), then re-run doctor"
        )
        finding.owner_approval_required = True
        return finding

    if inconsistency:
        finding.verdict, finding.exit_code = "INCONSISTENT", EXIT_INCONSISTENT
        finding.risk = "corruption-or-misleading-intent"
        finding.detail.append(inconsistency)
        finding.safe_next_action = (
            "reconcile the declared mode with the filter config before any "
            "checkout or commit in this worktree; a commit taken now can "
            "store a doubly-encrypted blob"
        )
        finding.owner_approval_required = True
        return finding

    if observed == "conflicted":
        finding.verdict, finding.exit_code = "AMBIGUOUS", EXIT_AMBIGUOUS
        finding.risk = "corruption"
        finding.detail.append(
            "header magic and object-id signals disagree -- the working file "
            "is neither the stored blob nor a clean decryption of it "
            "(double-encryption is the known cause)"
        )
        finding.safe_next_action = (
            "do NOT commit; restore the file from the index with the correct "
            "filter configuration, then re-run doctor"
        )
        finding.owner_approval_required = True
        return finding

    if observed in ("partial", "absent") and probes:
        finding.verdict, finding.exit_code = "AMBIGUOUS", EXIT_AMBIGUOUS
        finding.risk = "indeterminate"
        finding.detail.append(
            "filtered paths are only partially materialised; the worktree "
            "state cannot be classified as a whole"
        )
        finding.safe_next_action = (
            "complete or reset the checkout, then re-run doctor; "
            "backfill will refuse this worktree"
        )
        finding.owner_approval_required = True
        return finding

    if observed == "no-filtered-paths":
        finding.verdict, finding.exit_code = "OK", EXIT_OK
        finding.risk = "none"
        finding.safe_next_action = "none -- no git-crypt-filtered paths tracked here"
        finding.owner_approval_required = False
        return finding

    if observed == expected:
        finding.verdict, finding.exit_code = "OK", EXIT_OK
        finding.risk = "none"
        finding.safe_next_action = "none"
        finding.owner_approval_required = False
        return finding

    if expected == MODE_CIPHERTEXT and observed == MODE_PLAINTEXT:
        finding.verdict, finding.exit_code = "UNSAFE", EXIT_UNSAFE
        finding.risk = "secret-exposure"
        finding.safe_next_action = (
            "this worktree is configured to hold ciphertext but holds "
            "plaintext; confirm intent with the owner, then either update "
            f"{CFG_MODE} or restore ciphertext with an identity filter"
        )
        finding.owner_approval_required = True
        return finding

    finding.verdict, finding.exit_code = "MISMATCH", EXIT_MISMATCH
    finding.risk = "not-materialised"
    if not key_available:
        finding.detail.append("no git-crypt key reachable from this worktree")
        finding.safe_next_action = (
            "provide the key (git-crypt unlock, or a worktree-scoped "
            "--key-file filter via `backfill --apply`)"
        )
    else:
        finding.safe_next_action = (
            "a key is available but the worktree still holds ciphertext; run "
            "`backfill --worktree <path> --apply` to install a worktree-scoped "
            "--key-file filter, then re-checkout the filtered paths"
        )
    finding.owner_approval_required = False
    return finding


def resolve_key(common, gitdir, wt_smudge, shared_smudge):
    for value, label in ((wt_smudge, "worktree-filter"), (shared_smudge, "shared")):
        kf = keyfile_path_from_filter(value)
        if kf and os.path.isfile(kf):
            return True, f"{label}:--key-file"
    if gitdir:
        local = os.path.join(gitdir, "git-crypt", "keys", "default")
        if os.path.isfile(local):
            return True, "gitdir-key-copy"
    shared_key = os.path.join(common, "git-crypt", "keys", "default")
    if os.path.isfile(shared_key):
        return True, "shared-key"
    return False, "none"


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------


def run_doctor(repo_root):
    common = git_common_dir(repo_root)
    s1, s2, disagreement = enumerate_worktrees(repo_root, common)
    shared_smudge = cfg_get(repo_root, CFG_SMUDGE, scope="--local")

    findings = [
        classify(repo_root, common, entry, shared_smudge)
        for entry in s1
        if not entry.get("bare")
    ]

    report = {
        "tool": "gitcrypt-worktree",
        "command": "doctor",
        "repo_root": repo_root,
        "git_common_dir": common,
        "worktree_config_extension": worktree_config_enabled(repo_root),
        "shared_smudge_configured": shared_smudge is not None,
        "enumeration": {
            "s1_git_registry_count": len([w for w in s1 if not w.get("bare")]),
            "s2_filesystem_gitdir_count": len(s2),
            "agree": not (disagreement["s1_only"] or disagreement["s2_only"]),
            "s1_only": disagreement["s1_only"],
            "s2_only": disagreement["s2_only"],
        },
        "findings": [f.to_dict() for f in findings],
    }
    codes = [f.exit_code for f in findings]
    if not report["enumeration"]["agree"]:
        codes.append(EXIT_AMBIGUOUS)
        report["enumeration"]["note"] = (
            "git's worktree registry and the filesystem disagree; "
            "counts derived from either alone would be wrong"
        )
    report["exit_code"] = worst(codes)
    report["exit_name"] = EXIT_NAMES[report["exit_code"]]
    return report


def worst(codes):
    for code in SEVERITY_ORDER:
        if code in codes:
            return code
    return EXIT_OK


# --------------------------------------------------------------------------
# backfill
# --------------------------------------------------------------------------


def select_targets(findings, worktree_args, select_all):
    if select_all:
        return list(findings), []
    selected, unknown = [], []
    by_key = {path_key(f.worktree_path): f for f in findings}
    for arg in worktree_args:
        found = by_key.get(path_key(arg))
        if found is None:
            unknown.append(norm(arg))
        else:
            selected.append(found)
    return selected, unknown


def plan_backfill(findings, targets, explicit, common, key_path):
    """Decide, per target, what would happen. Performs no writes."""
    plan = []
    for finding in targets:
        entry = {
            "worktree_path": finding.worktree_path,
            "gitdir_entry": finding.gitdir_entry,
            "repo_relative_path": finding.repo_relative_path,
            "branch": finding.branch,
            "head": finding.head,
            "expected_state": finding.expected_state,
            "observed_state": finding.observed_state,
            "verdict": finding.verdict,
        }
        if finding.verdict in ("UNREADABLE", "AMBIGUOUS", "INCONSISTENT"):
            entry["decision"] = "refuse"
            entry["reason"] = (
                f"target state is {finding.verdict}; backfill refuses states "
                "it cannot classify with confidence"
            )
            entry["exit_code"] = EXIT_REFUSED
            entry["owner_approval_required"] = True
        elif finding.expected_state == MODE_CIPHERTEXT:
            # The whole point of defect (c): a key existing elsewhere is NOT
            # authority to decrypt a worktree whose owner asked for ciphertext.
            entry["decision"] = "refuse" if explicit else "skip"
            entry["reason"] = (
                "worktree is ciphertext-preserving "
                f"(expected_state=ciphertext via {finding.expected_source}); "
                "installing a decrypting filter here would materialise "
                "plaintext against the owner's declared intent"
            )
            entry["exit_code"] = EXIT_REFUSED if explicit else EXIT_OK
            entry["owner_approval_required"] = True
        elif finding.verdict == "UNSAFE":
            entry["decision"] = "refuse"
            entry["reason"] = (
                "target already holds plaintext against its declared intent; "
                "resolve that before changing filter configuration"
            )
            entry["exit_code"] = EXIT_REFUSED
            entry["owner_approval_required"] = True
        elif not key_path:
            entry["decision"] = "refuse"
            entry["reason"] = (
                "no git-crypt key found at <git-common-dir>/git-crypt/keys/"
                "default; refusing to write a filter pointing at a "
                "non-existent key"
            )
            entry["exit_code"] = EXIT_REFUSED
            entry["owner_approval_required"] = True
        else:
            existing = cfg_get(finding.worktree_path, CFG_SMUDGE, scope="--worktree")
            if filter_has_keyfile(existing):
                entry["decision"] = "skip"
                entry["reason"] = (
                    "worktree already carries a worktree-scoped --key-file filter"
                )
                entry["exit_code"] = EXIT_OK
                entry["owner_approval_required"] = False
            else:
                entry["decision"] = "configure"
                entry["reason"] = (
                    "worktree expects plaintext, a key is reachable, and no "
                    "worktree-scoped git-crypt filter is installed"
                )
                entry["writes"] = [
                    [CFG_SMUDGE, f"git-crypt smudge --key-file={key_path}"],
                    [CFG_CLEAN, f"git-crypt clean --key-file={key_path}"],
                    [CFG_REQUIRED, "true"],
                    [CFG_TEXTCONV, f"git-crypt diff --key-file={key_path}"],
                ]
                entry["exit_code"] = EXIT_OK
                entry["owner_approval_required"] = False
        plan.append(entry)
    return plan


def new_journal():
    """An empty write-ahead journal."""
    return {
        "journal_version": JOURNAL_VERSION,
        "tool": "gitcrypt-worktree",
        "status": "pending",
        "entries": [],
    }


def write_journal(journal_path, journal):
    """Persist the journal atomically, or raise ArtifactError.

    Atomic because a half-written journal is worse than no journal: it may
    still parse, and a caller that trusts it performs a partial rollback.
    Written to a sibling temp file, flushed, fsync'd, then renamed --
    ``os.replace`` is atomic on Windows and POSIX alike.
    """
    if not journal_path:
        raise ToolError("a rollback journal path is required for --apply")
    tmp = f"{journal_path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, journal_path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ArtifactError(
            f"cannot write rollback journal {journal_path}: {exc}"
        ) from exc
    return journal


def apply_plan(plan, journal_path, journal=None):
    """Perform the planned writes behind a WRITE-AHEAD journal.

    Ordering is the whole point. The round-1 implementation performed every
    ``git config --worktree`` write first and opened the journal afterwards,
    so an unwritable journal path left the configuration mutated with no
    record of its prior values: reversibility was documented and absent. Here
    the complete pre-image is durable on disk BEFORE the first write, so every
    applied change is reversible from the journal even if the process dies
    part-way through.
    """
    if journal is None:
        journal = new_journal()

    # Phase 1 -- read the complete pre-image. Reads only, no mutation yet.
    pending = []
    for entry in plan:
        if entry["decision"] != "configure":
            entry["action_performed"] = (
                "refused" if entry["decision"] == "refuse" else "skipped"
            )
            continue
        wt = entry["worktree_path"]
        restore = [
            {"key": key, "prior": cfg_get(wt, key, scope="--worktree")}
            for key, _value in entry["writes"]
        ]
        journal["entries"].append(
            {"worktree_path": wt, "scope": "--worktree", "restore": restore}
        )
        pending.append(entry)

    # Phase 2 -- make the pre-image durable BEFORE any mutation.
    write_journal(journal_path, journal)

    # Phase 3 -- mutate. Everything from here is already recorded.
    for entry in pending:
        wt = entry["worktree_path"]
        for key, value in entry["writes"]:
            rc, _out, err = run_git(["config", "--worktree", key, value], cwd=wt)
            if rc != 0:
                entry["action_performed"] = "failed"
                entry["error"] = err.strip()
                entry["exit_code"] = EXIT_REFUSED
                break
        else:
            entry["action_performed"] = "configured"

    # Phase 4 -- record completion. The journal was already sufficient to roll
    # back before this write, so losing it costs the marker and nothing else.
    journal["status"] = "complete"
    write_journal(journal_path, journal)
    return journal


def validate_journal(journal, journal_path):
    """Validate the WHOLE journal before performing any restore.

    The round-1 implementation walked the entries and restored as it went, so
    a malformed entry N crashed with a ``KeyError`` *after* entries 0..N-1 had
    already been restored: a partial rollback whose only report was an
    unhandled traceback (process exit 1, which the contract defines as
    UNSAFE). Validation is therefore a separate, total pass -- either every
    entry is usable and the restore proceeds, or nothing is touched at all.
    """
    where = f"rollback journal {journal_path}"
    if not isinstance(journal, dict):
        raise ToolError(f"{where} is not a JSON object")
    version = journal.get("journal_version")
    if version not in SUPPORTED_JOURNAL_VERSIONS:
        raise ToolError(f"{where}: unsupported journal_version {version!r}")
    entries = journal.get("entries")
    if not isinstance(entries, list):
        raise ToolError(f"{where}: 'entries' is not a list; refusing to restore")

    steps = []
    for index, item in enumerate(entries):
        at = f"{where} entries[{index}]"
        if not isinstance(item, dict):
            raise ToolError(f"{at} is not an object; refusing a partial rollback")
        wt = item.get("worktree_path")
        if not isinstance(wt, str) or not wt.strip():
            raise ToolError(
                f"{at} has no usable worktree_path; refusing a partial rollback"
            )
        scope = item.get("scope", "--worktree")
        if scope not in ("--worktree", "--local"):
            raise ToolError(
                f"{at} has unsupported scope {scope!r}; refusing a partial rollback"
            )
        restore = item.get("restore")
        if not isinstance(restore, list) or not restore:
            raise ToolError(
                f"{at} carries no restore records; refusing a partial rollback"
            )
        if not os.path.isdir(wt):
            raise ToolError(
                f"{at} names {wt}, which is not a directory; "
                "refusing a partial rollback"
            )
        for r_index, record in enumerate(restore):
            rat = f"{at}.restore[{r_index}]"
            if not isinstance(record, dict):
                raise ToolError(f"{rat} is not an object; refusing a partial rollback")
            key = record.get("key")
            if not isinstance(key, str) or not key.strip():
                raise ToolError(f"{rat} has no usable key; refusing a partial rollback")
            if "prior" not in record:
                raise ToolError(
                    f"{rat} has no 'prior' value; refusing a partial rollback"
                )
            prior = record["prior"]
            if prior is not None and not isinstance(prior, str):
                raise ToolError(
                    f"{rat} has a non-string 'prior'; refusing a partial rollback"
                )
            steps.append(
                {
                    "worktree_path": wt,
                    "scope": scope,
                    "key": key,
                    "restore_to": prior,
                }
            )
    return steps


def restore_one(step):
    """Apply one restore and VERIFY its postcondition by re-reading the key."""
    wt = step["worktree_path"]
    scope = step["scope"]
    key = step["key"]
    prior = step["restore_to"]
    error = None
    if prior is None:
        rc, _out, err = run_git(["config", scope, "--unset-all", key], cwd=wt)
        # git exits 5 when the key is already absent: the postcondition holds.
        if rc not in (0, 5):
            error = err.strip()
    else:
        rc, _out, err = run_git(["config", scope, key, prior], cwd=wt)
        if rc != 0:
            error = err.strip()
    observed = cfg_get(wt, key, scope=scope)
    return observed, observed == prior, error


def run_rollback(journal_path, apply):
    try:
        with open(journal_path, encoding="utf-8") as handle:
            journal = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(f"cannot read rollback journal {journal_path}: {exc}") from exc

    # TOTAL validation first. Nothing below this line runs on a bad journal.
    steps = validate_journal(journal, norm(journal_path))

    actions = []
    unrestored = 0
    # Undo in REVERSE order. The shared extensions.worktreeConfig entry is
    # recorded first because it is written first, and unsetting it before the
    # worktree-scoped keys are restored would make those restores impossible.
    for step in reversed(steps):
        action = dict(step)
        action["performed"] = False
        action["observed_after"] = None
        action["verified"] = None
        action["error"] = None
        if apply:
            observed, verified, error = restore_one(step)
            action["performed"] = True
            action["observed_after"] = observed
            action["verified"] = verified
            action["error"] = error
            if not verified:
                unrestored += 1
        actions.append(action)

    exit_code = EXIT_INCONSISTENT if unrestored else EXIT_OK
    return {
        "tool": "gitcrypt-worktree",
        "command": "rollback",
        "journal": norm(journal_path),
        "journal_status": journal.get("status", "unknown"),
        "dry_run": not apply,
        "actions": actions,
        "unrestored": unrestored,
        "exit_code": exit_code,
        "exit_name": EXIT_NAMES[exit_code],
    }


def run_backfill(repo_root, worktree_args, select_all, apply, journal_path, allow_ext):
    common = git_common_dir(repo_root)
    doctor = run_doctor(repo_root)
    findings = [rebuild_finding(d) for d in doctor["findings"]]

    explicit = bool(worktree_args)
    targets, unknown = select_targets(findings, worktree_args, select_all)
    if unknown:
        raise ToolError(
            "unknown worktree selector(s): "
            + ", ".join(unknown)
            + " -- run `doctor` to list the exact normalised paths"
        )
    if not targets:
        raise ToolError("no targets selected (use --worktree PATH ... or --all)")

    key_path = os.path.join(common, "git-crypt", "keys", "default")
    key_path = norm(key_path) if os.path.isfile(key_path) else None

    report = {
        "tool": "gitcrypt-worktree",
        "command": "backfill",
        "repo_root": repo_root,
        "dry_run": not apply,
        "selection": "explicit" if explicit else "all",
        "key_path": key_path,
        "worktree_config_extension": worktree_config_enabled(repo_root),
    }

    # Establish the rollback journal BEFORE anything below can mutate state.
    # An unusable --journal path must fail HERE, with nothing changed, rather
    # than after the writes have already landed.
    journal = new_journal() if apply else None
    if apply:
        write_journal(journal_path, journal)

    if not report["worktree_config_extension"]:
        if not allow_ext:
            report["plan"] = []
            report["refused_globally"] = (
                f"{CFG_WORKTREE_EXT} is not true in this repository's shared "
                "config. Worktree-scoped config cannot be written without it, "
                "and enabling it modifies SHARED repository config. Re-run "
                "with --enable-worktree-config to authorise that, or set it "
                "yourself."
            )
            report["exit_code"] = EXIT_REFUSED
            report["exit_name"] = EXIT_NAMES[EXIT_REFUSED]
            return report
        if apply:
            # A SHARED-config write. It is an applied change, so it must be
            # journalled -- and journalled BEFORE it happens.
            journal["entries"].append(
                {
                    "worktree_path": repo_root,
                    "scope": "--local",
                    "restore": [
                        {
                            "key": CFG_WORKTREE_EXT,
                            "prior": cfg_get(
                                repo_root, CFG_WORKTREE_EXT, scope="--local"
                            ),
                        }
                    ],
                }
            )
            write_journal(journal_path, journal)
            run_git(["config", "--local", CFG_WORKTREE_EXT, "true"], cwd=repo_root)
            report["enabled_worktree_config"] = True

    plan = plan_backfill(findings, targets, explicit, common, key_path)
    for entry in plan:
        entry["action_performed"] = "none (dry-run)" if not apply else "pending"
    report["plan"] = plan

    if apply:
        journal = apply_plan(plan, journal_path, journal)
        report["journal_path"] = norm(journal_path)
        report["journal_entries"] = len(journal["entries"])
        report["journal_status"] = journal["status"]
    report["exit_code"] = worst([e.get("exit_code", EXIT_OK) for e in plan])
    report["exit_name"] = EXIT_NAMES[report["exit_code"]]
    return report


def rebuild_finding(data):
    files = data.pop("files", [])
    finding = Finding(**data)
    finding.files = files
    return finding


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def render_doctor(report, stream):
    enum = report["enumeration"]
    print(f"repo            : {report['repo_root']}", file=stream)
    print(f"git-common-dir  : {report['git_common_dir']}", file=stream)
    print(
        "enumeration     : "
        f"git-registry={enum['s1_git_registry_count']} "
        f"filesystem-gitdirs={enum['s2_filesystem_gitdir_count']} "
        f"agree={enum['agree']}",
        file=stream,
    )
    if not enum["agree"]:
        print(f"  s1_only: {enum['s1_only']}", file=stream)
        print(f"  s2_only: {enum['s2_only']}", file=stream)
    print("", file=stream)
    for finding in report["findings"]:
        print(f"[{finding['verdict']}] {finding['worktree_path']}", file=stream)
        print(
            f"    identity  : gitdir_entry={finding['gitdir_entry']} "
            f"repo_relative={finding['repo_relative_path']}",
            file=stream,
        )
        print(
            f"    ref       : branch={finding['branch']} head={finding['head'][:12]}",
            file=stream,
        )
        print(
            f"    expected  : {finding['expected_state']} "
            f"(source={finding['expected_source']})",
            file=stream,
        )
        print(
            f"    observed  : {finding['observed_state']} "
            f"key={'available' if finding['key_available'] else 'MISSING'}"
            f"({finding['key_source']})",
            file=stream,
        )
        print(f"    risk      : {finding['risk']}", file=stream)
        print(f"    next      : {finding['safe_next_action']}", file=stream)
        print(
            f"    performed : {finding['action_performed']}   "
            f"owner_approval_required="
            f"{'yes' if finding['owner_approval_required'] else 'no'}",
            file=stream,
        )
        for line in finding["detail"]:
            print(f"    - {line}", file=stream)
        print("", file=stream)
    print(
        f"exit: {report['exit_code']} ({report['exit_name']})",
        file=stream,
    )


def render_backfill(report, stream):
    print(f"repo      : {report['repo_root']}", file=stream)
    print(
        f"mode      : {'DRY-RUN (no writes)' if report['dry_run'] else 'APPLY'}",
        file=stream,
    )
    print(f"selection : {report['selection']}", file=stream)
    print(f"key       : {report['key_path'] or '(none found)'}", file=stream)
    if report.get("refused_globally"):
        print(f"REFUSED   : {report['refused_globally']}", file=stream)
    for entry in report.get("plan", []):
        print(
            f"[{entry['decision'].upper()}] {entry['worktree_path']}",
            file=stream,
        )
        print(
            f"    identity  : gitdir_entry={entry['gitdir_entry']} "
            f"repo_relative={entry['repo_relative_path']}",
            file=stream,
        )
        print(
            f"    state     : expected={entry['expected_state']} "
            f"observed={entry['observed_state']} verdict={entry['verdict']}",
            file=stream,
        )
        print(f"    reason    : {entry['reason']}", file=stream)
        print(
            f"    performed : {entry.get('action_performed', 'none')}   "
            f"owner_approval_required="
            f"{'yes' if entry.get('owner_approval_required') else 'no'}",
            file=stream,
        )
        for key, value in entry.get("writes", []):
            print(f"      would-set {key} = {value}", file=stream)
        print("", file=stream)
    if report.get("journal_path"):
        print(f"rollback journal: {report['journal_path']}", file=stream)
    print(f"exit: {report['exit_code']} ({report['exit_name']})", file=stream)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gitcrypt_worktree",
        description="git-crypt worktree doctor and gated backfill.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="read-only inspection (no writes)")
    doctor.add_argument("--repo", default=".", help="path inside the repository")
    doctor.add_argument("--json", action="store_true", help="emit JSON")
    doctor.add_argument("--json-out", help="also write JSON to this file")

    backfill = sub.add_parser(
        "backfill", help="install worktree-scoped git-crypt filters (dry-run default)"
    )
    backfill.add_argument("--repo", default=".", help="path inside the repository")
    backfill.add_argument(
        "--worktree",
        action="append",
        default=[],
        help="explicit target worktree path (repeatable)",
    )
    backfill.add_argument(
        "--all", action="store_true", help="explicitly select every worktree"
    )
    backfill.add_argument(
        "--apply", action="store_true", help="perform the writes (default: dry-run)"
    )
    backfill.add_argument(
        "--enable-worktree-config",
        action="store_true",
        help=f"authorise setting {CFG_WORKTREE_EXT} in SHARED repo config",
    )
    backfill.add_argument(
        "--journal", help="rollback journal path (written on --apply)"
    )
    backfill.add_argument("--json", action="store_true", help="emit JSON")
    backfill.add_argument("--json-out", help="also write JSON to this file")

    rollback = sub.add_parser("rollback", help="restore config from a journal")
    rollback.add_argument("--journal", required=True)
    rollback.add_argument("--apply", action="store_true")
    rollback.add_argument("--json", action="store_true")
    rollback.add_argument("--json-out")

    return parser


def fail_io(message):
    """Report an output-artifact failure under a DEFINED exit code.

    Never let this path exit 1: that is UNSAFE in this contract, and a caller
    doing exit-code dispatch would act on a secret-exposure verdict that was
    really an unwritable file.
    """
    print(f"ARTIFACT ERROR: {message}", file=sys.stderr)
    print(f"exit: {EXIT_IO} ({EXIT_NAMES[EXIT_IO]})", file=sys.stderr)
    return EXIT_IO


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = run_doctor(resolve_repo(args.repo))
            renderer = render_doctor
        elif args.command == "backfill":
            if args.worktree and args.all:
                raise ToolError("--worktree and --all are mutually exclusive")
            if not args.worktree and not args.all:
                raise ToolError(
                    "backfill requires an explicit target selection: "
                    "--worktree PATH (repeatable) or --all"
                )
            if args.apply and not args.journal:
                raise ToolError("--apply requires --journal PATH (rollback record)")
            report = run_backfill(
                resolve_repo(args.repo),
                args.worktree,
                args.all,
                args.apply,
                args.journal,
                args.enable_worktree_config,
            )
            renderer = render_backfill
        else:
            report = run_rollback(args.journal, args.apply)
            renderer = lambda r, s: print(json.dumps(r, indent=2), file=s)  # noqa: E731
    except ToolError as exc:
        print(f"USAGE ERROR: {exc}", file=sys.stderr)
        print(f"exit: {EXIT_USAGE} ({EXIT_NAMES[EXIT_USAGE]})", file=sys.stderr)
        return EXIT_USAGE
    except ArtifactError as exc:
        return fail_io(str(exc))
    except OSError as exc:
        # Backstop. An OSError escaping as an unhandled traceback exits 1,
        # which this contract defines as UNSAFE. Never let I/O impersonate it.
        return fail_io(f"unexpected I/O failure: {exc}")

    if getattr(args, "json_out", None):
        try:
            with open(args.json_out, "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
        except OSError as exc:
            return fail_io(f"cannot write --json-out {args.json_out}: {exc}")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        renderer(report, sys.stdout)
    return report["exit_code"]


def _git(args, cwd):
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return proc


def _staged(repo) -> list[str]:
    proc = _git(["diff", "--cached", "--name-only"], cwd=repo)
    return [ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()]

# --------------------------------------------------------------------------
# IMP-0223: disposable per-unit worktree provision + content-gated teardown
# --------------------------------------------------------------------------
# Repair 2026-10-26 (builder shard11 wave3): the previous versions of
# measure_disjoint_indexes / measure_teardown_both_states carried two
# green-not-live defects:
#   * the contamination control compared _staged(shared) == _staged(shared),
#     a tautology that could never fail;
#   * the squash-merge teardown case was a hardcoded literal dict, and the
#     "harvested" case force-removed the worktree without any harvest check.
# Both are replaced below with computed measurements. The provision /
# teardown primitives are real functions, not probe narration.


def provision_worktree(repo, unit_id, worktrees_root, token=None):
    """Provision a disposable worktree for one file-mutating unit.

    Each unit gets its own branch (shard/<unit>/<token>) and, because every
    linked worktree owns a separate $GIT_DIR/index, its own git index -- a
    broad git add in unit A can never sweep unit B's paths.
    """
    import uuid
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)
    token = token or uuid.uuid4().hex[:8]
    branch = f"shard/{unit_id}/{token}"
    safe = str(unit_id).replace("/", "-")
    path = root / f"{safe}-{token}"
    _git(["worktree", "add", "-b", branch, str(path), "HEAD"], cwd=repo)
    common = git_common_dir(repo)
    gitdir, _base, err = resolve_gitdir(path, common)
    if gitdir is None:
        raise ArtifactError(f"provisioned worktree has no resolvable gitdir: {err}")
    return {
        "unit_id": unit_id,
        "token": token,
        "branch": branch,
        "path": str(path),
        "gitdir": gitdir,
        "index_path": str(Path(gitdir) / "index"),
    }


def _worktree_files(worktree_path):
    """Every live file under the worktree except the .git entry itself."""
    from pathlib import Path

    wt = Path(worktree_path)
    out = []
    for p in sorted(wt.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(wt)
        if rel.parts and rel.parts[0] == ".git":
            continue
        out.append((rel.as_posix(), p))
    return out


def harvest_digest(worktree_path):
    """Content digest of every live worktree file (CRLF-normalized)."""
    rows = {}
    for rel, p in _worktree_files(worktree_path):
        rows[rel] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return rows


def _harvest_rows(harvest_dir):
    from pathlib import Path

    rows = {}
    hd = Path(harvest_dir)
    for p in sorted(hd.rglob("*")):
        if p.is_file():
            rows[p.relative_to(hd).as_posix()] = hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
    return rows


def teardown_worktree(repo, provisioned, harvest_dir=None, harvest_digests=None):
    """Tear down a provisioned unit worktree ONLY after content is proven.

    Authorization is byte-level comparison of every live file AND every
    index-referenced path against the harvest. Commit ancestry is never
    consulted: after a squash-merge a fully-carried branch still reports
    AHEAD, so ancestry can neither prove nor disprove preservation.
    """
    from pathlib import Path

    repo = Path(repo)
    wt = Path(provisioned["path"])
    if not wt.exists():
        return {"deleted": False, "refused": True, "reason": "worktree-absent", "missing": []}

    live = harvest_digest(wt)
    preserved = {}
    if harvest_digests is not None:
        preserved = dict(harvest_digests)
    elif harvest_dir is not None:
        preserved = _harvest_rows(harvest_dir)

    missing = sorted(rel for rel, sha in live.items() if preserved.get(rel) != sha)
    # Index-referenced paths (committed + staged) must be preserved too, so a
    # path deleted from disk but still in the index cannot silently vanish.
    rc, out, err = run_git(["ls-files"], cwd=wt)
    if rc != 0:
        return {"deleted": False, "refused": True, "reason": "index-unreadable",
                "missing": [], "detail": err.strip()}
    for rel in (ln.strip().replace("\\", "/") for ln in out.splitlines()):
        if rel and rel not in missing and rel not in preserved:
            missing.append(rel)
    missing = sorted(set(missing))
    if missing:
        return {
            "deleted": False,
            "refused": True,
            "reason": "unpreserved-content",
            "missing": missing[:20],
            "missing_count": len(missing),
            "path": str(wt),
        }

    _git(["worktree", "remove", "--force", str(wt)], cwd=repo)
    try:
        _git(["branch", "-D", provisioned["branch"]], cwd=repo)
    except RuntimeError:
        pass
    return {
        "deleted": not wt.exists(),
        "refused": False,
        "reason": "content-proven",
        "missing": [],
        "path": str(wt),
    }


def naive_ancestry_authorizes(repo, branch):
    """KNOWN-BROKEN control (measured, never used for authorization).

    The naive mutant reads "branch reports AHEAD of integration" - exactly
    what a squash-merged branch shows, since its unique commit is by
    construction not an ancestor of the squash commit - as "the PR carried
    the work, delete is safe". On a shard with an uncommitted remainder this
    authorizes deletion of unique content. Returned so probes can measure the
    mutant verdict on the same state the content gate refuses.
    """
    ahead = int(_git(["rev-list", "--count", f"HEAD..{branch}"],
                     cwd=str(repo)).stdout.strip() or "0")
    rc, _out, _err = run_git(["merge-base", "--is-ancestor", branch, "HEAD"],
                             cwd=str(repo))
    merged = rc == 0
    return {
        "authorize": ahead > 0 or merged,
        "ahead_count": ahead,
        "reports_ahead": ahead > 0,
        "merged": merged,
    }


def measure_disjoint_indexes(repo, worktrees_root) -> dict:
    """Signal 1: two concurrent mutating units produce disjoint staged sets.

    Also runs the real contamination control: the same two unit files on ONE
    shared checkout plus a broad git add -A stage both paths, which is the
    measured contamination mode isolated provisioning prevents.
    """
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)
    a = provision_worktree(repo, "unit-a", root)
    b = provision_worktree(repo, "unit-b", root)
    shared = None
    try:
        (Path(a["path"]) / "unit-a.txt").write_text("A-mut\n", encoding="utf-8")
        (Path(b["path"]) / "unit-b.txt").write_text("B-mut\n", encoding="utf-8")
        _git(["add", "unit-a.txt"], cwd=a["path"])
        _git(["add", "unit-b.txt"], cwd=b["path"])
        staged_a = _staged(a["path"])
        staged_b = _staged(b["path"])
        inter = sorted(set(staged_a) & set(staged_b))
        idx_a, idx_b = Path(a["index_path"]), Path(b["index_path"])
        index_paths_distinct = path_key(a["gitdir"]) != path_key(b["gitdir"])
        index_bytes_differ = (
            idx_a.is_file() and idx_b.is_file() and idx_a.read_bytes() != idx_b.read_bytes()
        )
        # Real contamination control: shared checkout + broad add sweeps both.
        shared = provision_worktree(repo, "shared", root)
        (Path(shared["path"]) / "unit-a.txt").write_text("A-mut\n", encoding="utf-8")
        (Path(shared["path"]) / "unit-b.txt").write_text("B-mut\n", encoding="utf-8")
        _git(["add", "-A"], cwd=shared["path"])
        staged_shared = _staged(shared["path"])
        shared_intersection = sorted({"unit-a.txt", "unit-b.txt"} & set(staged_shared))
        contamination_detected = len(shared_intersection) == 2
        return {
            "pass": (
                not inter
                and bool(staged_a)
                and bool(staged_b)
                and index_paths_distinct
                and index_bytes_differ
                and contamination_detected
            ),
            "staged_a": staged_a,
            "staged_b": staged_b,
            "intersection": inter,
            "intersection_empty": not inter,
            "indexes_disjoint": not inter,
            "index_a": a["index_path"],
            "index_b": b["index_path"],
            "index_paths_distinct": index_paths_distinct,
            "index_bytes_differ": index_bytes_differ,
            "branches": [a["branch"], b["branch"]],
            "contamination_control": {
                "mode": "shared-checkout-broad-add",
                "staged_shared": staged_shared,
                "shared_intersection": shared_intersection,
                "detected": contamination_detected,
            },
        }
    finally:
        for prov in (a, b, shared):
            if prov is None:
                continue
            try:
                teardown_worktree(repo, prov, harvest_digests=harvest_digest(prov["path"]))
            except (RuntimeError, OSError):
                pass


def measure_teardown_both_states(repo, worktrees_root) -> dict:
    """Signal 2: teardown of an unpreserved worktree is refused; a harvested
    one is deleted; and on the squash-merge state the naive ancestry mutant
    authorizes while the content gate refuses - all computed, none asserted.
    """
    import shutil
    from pathlib import Path

    repo = Path(repo)
    root = Path(worktrees_root)
    root.mkdir(parents=True, exist_ok=True)

    # (1) unharvested unique remainder must refuse and stay on disk
    danger = provision_worktree(repo, "danger", root)
    dpath = Path(danger["path"])
    (dpath / "uncommitted.txt").write_text("remainder\n", encoding="utf-8")
    ref_danger = teardown_worktree(repo, danger, harvest_dir=None)
    dangerous = {
        "refused": bool(ref_danger["refused"]),
        "deleted": bool(ref_danger["deleted"]),
        "reason": ref_danger.get("reason"),
        "worktree_still_on_disk": dpath.exists(),
    }

    # (2) squash-merge: content IS carried, ancestry reports AHEAD; the naive
    # mutant authorizes deletion while the uncommitted remainder is unique.
    squash = provision_worktree(repo, "squash", root)
    spath = Path(squash["path"])
    (spath / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(["add", "feature.txt"], cwd=spath)
    _git(["commit", "-m", "shard feature"], cwd=spath)
    _git(["merge", "--squash", squash["branch"]], cwd=repo)
    _git(["commit", "-m", "integration squash"], cwd=repo)
    naive = naive_ancestry_authorizes(repo, squash["branch"])
    (spath / "uncommitted.txt").write_text("remainder\n", encoding="utf-8")
    ref_squash = teardown_worktree(repo, squash, harvest_dir=None)
    squash_res = {
        "refused": bool(ref_squash["refused"]),
        "deleted": bool(ref_squash["deleted"]),
        "reason": ref_squash.get("reason"),
        "reports_ahead": naive["reports_ahead"],
        "ahead_count": naive["ahead_count"],
        "merged_check_false_despite_content_carried": naive["merged"] is False,
        "naive_ancestry_would_authorize": bool(naive["authorize"]),
        "worktree_still_on_disk": spath.exists(),
    }

    # (3) content-proven harvest authorizes deletion
    good = provision_worktree(repo, "good", root)
    gpath = Path(good["path"])
    (gpath / "kept.txt").write_text("kept\n", encoding="utf-8")
    hdir = Path(str(gpath) + "-harvest")
    shutil.copytree(gpath, hdir, ignore=shutil.ignore_patterns(".git"))
    ref_good = teardown_worktree(repo, good, harvest_dir=hdir)
    good_res = {
        "refused": bool(ref_good["refused"]),
        "deleted": bool(ref_good["deleted"]),
        "reason": ref_good.get("reason"),
    }
    shutil.rmtree(hdir, ignore_errors=True)

    # best-effort fixture cleanup through the same content gate
    for prov, p in ((danger, dpath), (squash, spath)):
        if p.exists():
            try:
                teardown_worktree(repo, prov, harvest_digests=harvest_digest(p))
            except (RuntimeError, OSError):
                pass

    return {
        "pass": (
            dangerous["refused"]
            and dangerous["worktree_still_on_disk"]
            and not dangerous["deleted"]
            and squash_res["refused"]
            and squash_res["worktree_still_on_disk"]
            and squash_res["reports_ahead"]
            and squash_res["naive_ancestry_would_authorize"]
            and good_res["deleted"]
            and not good_res["refused"]
        ),
        "dangerous": dangerous,
        "squash_unharvested": squash_res,
        "good": good_res,
    }


if __name__ == "__main__":
    sys.exit(main())
