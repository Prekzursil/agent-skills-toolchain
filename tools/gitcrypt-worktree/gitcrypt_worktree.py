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

The process exit code is the highest-severity code across all findings, in
the precedence order USAGE > UNREADABLE > AMBIGUOUS > INCONSISTENT > UNSAFE
> REFUSED > MISMATCH > OK.
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

EXIT_NAMES = {
    EXIT_OK: "OK",
    EXIT_UNSAFE: "UNSAFE",
    EXIT_USAGE: "USAGE",
    EXIT_AMBIGUOUS: "AMBIGUOUS",
    EXIT_UNREADABLE: "UNREADABLE",
    EXIT_INCONSISTENT: "INCONSISTENT",
    EXIT_MISMATCH: "MISMATCH",
    EXIT_REFUSED: "REFUSED",
}

# Highest severity first. The process exit code is the first code in this
# list that appears among the findings.
SEVERITY_ORDER = (
    EXIT_USAGE,
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

JOURNAL_VERSION = 1


class ToolError(Exception):
    """A usage-level failure: reported and mapped to EXIT_USAGE."""


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


def apply_plan(plan, journal_path):
    journal = {
        "journal_version": JOURNAL_VERSION,
        "tool": "gitcrypt-worktree",
        "entries": [],
    }
    for entry in plan:
        if entry["decision"] != "configure":
            entry["action_performed"] = (
                "refused" if entry["decision"] == "refuse" else "skipped"
            )
            continue
        wt = entry["worktree_path"]
        restore = []
        for key, value in entry["writes"]:
            prior = cfg_get(wt, key, scope="--worktree")
            restore.append({"key": key, "prior": prior})
            rc, _, err = run_git(["config", "--worktree", key, value], cwd=wt)
            if rc != 0:
                entry["action_performed"] = "failed"
                entry["error"] = err.strip()
                entry["exit_code"] = EXIT_REFUSED
                break
        else:
            entry["action_performed"] = "configured"
            journal["entries"].append({"worktree_path": wt, "restore": restore})
            continue
        journal["entries"].append({"worktree_path": wt, "restore": restore})
    if journal_path:
        with open(journal_path, "w", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
    return journal


def run_rollback(journal_path, apply):
    try:
        with open(journal_path, encoding="utf-8") as handle:
            journal = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(f"cannot read rollback journal {journal_path}: {exc}") from exc
    if journal.get("journal_version") != JOURNAL_VERSION:
        raise ToolError(
            f"unsupported journal_version {journal.get('journal_version')!r}"
        )
    actions = []
    for item in journal.get("entries", []):
        wt = item["worktree_path"]
        for restore in item["restore"]:
            key, prior = restore["key"], restore["prior"]
            action = {
                "worktree_path": wt,
                "key": key,
                "restore_to": prior,
                "performed": False,
            }
            if apply:
                if prior is None:
                    run_git(["config", "--worktree", "--unset-all", key], cwd=wt)
                else:
                    run_git(["config", "--worktree", key, prior], cwd=wt)
                action["performed"] = True
            actions.append(action)
    return {
        "tool": "gitcrypt-worktree",
        "command": "rollback",
        "journal": norm(journal_path),
        "dry_run": not apply,
        "actions": actions,
        "exit_code": EXIT_OK,
        "exit_name": EXIT_NAMES[EXIT_OK],
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
            run_git(["config", "--local", CFG_WORKTREE_EXT, "true"], cwd=repo_root)
            report["enabled_worktree_config"] = True

    plan = plan_backfill(findings, targets, explicit, common, key_path)
    for entry in plan:
        entry["action_performed"] = "none (dry-run)" if not apply else "pending"
    report["plan"] = plan

    if apply:
        journal = apply_plan(plan, journal_path)
        report["journal_path"] = norm(journal_path) if journal_path else None
        report["journal_entries"] = len(journal["entries"])
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

    if getattr(args, "json_out", None):
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        renderer(report, sys.stdout)
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
