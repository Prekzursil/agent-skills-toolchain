#!/usr/bin/env python3
"""D-001 reconciliation and projection applier -- filter-safe, plumbing-only.

``mirror`` unions legacy ``skills/<NAME>/**`` content into the authoritative
``.agents/skills/<NAME>/**`` tree without overwriting a divergent canonical
blob.  ``project`` overlays authoritative canonical blobs onto the compatibility
``skills/<NAME>/**`` projection without deleting projection-only content.  Both
build a new branch without ever writing the working tree.

Why the working tree is never written
-------------------------------------
A repository that uses a content filter (this one uses git-crypt for
``tools/mcp/*/accounts.json``) materialises every file it checks out through
that filter's *smudge* side.  When the filter has been neutralised to an
identity passthrough -- ``smudge = cat``, ``clean = cat``, ``required = false``
in the SHARED ``.git/config`` -- any materialising operation writes the STORED
(encrypted) bytes into the working tree for every protected path, including
paths the operation never intended to touch.  Creating a second worktree of the
same repository inherits that shared config, so the corruption lands on the
FIRST command, before any per-file copy step runs.

Two consequences drive this tool's design:

1. The mirror is built with pure plumbing against a TEMPORARY index
   (``GIT_INDEX_FILE``): ``read-tree`` -> ``update-index --cacheinfo`` ->
   ``write-tree`` -> ``commit-tree`` -> ``update-ref``.  No second worktree, no
   broad index materialisation, no filter round-trip.  Protected files are
   never opened, so their bytes AND their mtime are untouched.
2. ``git status`` cannot be used as the safety check.  While the filter is
   neutralised, ``clean = cat`` maps the stored bytes back to the identical
   blob, so ``git status --porcelain`` reports a CLEAN tree over a working tree
   that holds ciphertext.  ``preflight`` therefore inspects CONTENT, with two
   mechanically independent signals (see ``cmd_preflight``).
3. ``git checkout -- <arg>`` takes a PATHSPEC, not a file name.  ``:/`` is
   git's pathspec for the repository ROOT, ``*`` and ``:(glob)**`` select every
   tracked file, and a bare directory name selects everything under it -- so a
   gate that only compares the ARGUMENT against a set of protected file names
   never engages on any of them.  ``materialize`` therefore expands every
   argument through git's own machinery (``git ls-files --error-unmatch``) and
   refuses unless it resolves to EXACTLY ITSELF (see ``cmd_materialize``).

Exit codes:
    0  OK
    1  UNSAFE  -- preflight found a filter/content problem; nothing was changed
    2  USAGE   -- bad invocation or git error
    7  REFUSED -- a mutation was requested and denied by a safety gate; no
                  worktree path or existing ref was changed (a post-build
                  refusal can leave unreachable Git objects for normal GC)

Subcommands:
    preflight    read-only filter + content audit (never writes)
    mirror       union projection-only content into canonical (dry-run default)
    project      generate selected projections from canonical (dry-run default)
    materialize  guarded, EXPLICIT-paths-only restore of files from the index
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import tempfile

EXIT_OK = 0
EXIT_UNSAFE = 1
EXIT_USAGE = 2
EXIT_REFUSED = 7

PROJECTION_ROOT = "skills"
CANONICAL_ROOT = ".agents/skills"
REGULAR_MODES = frozenset({"100644", "100755"})
SKILL_NAME_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*\Z")


# Stored-form magics used by Signal A.  git-crypt's header is the only one that
# ships; tests register their synthetic filter's magic with --magic-hex.
GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"

# Values of filter.<driver>.smudge / .clean that pass content through unchanged.
IDENTITY_FILTERS = {"cat", "cat -", "/bin/cat", "/usr/bin/cat", "type"}


class GitError(RuntimeError):
    """git exited non-zero."""


def run_git(
    repo: str,
    args: list[str],
    *,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    full_env = None
    if env:
        full_env = {**os.environ, **env}
    proc = subprocess.run(
        ["git", "-C", repo, *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        env=full_env,
    )
    if check and proc.returncode != 0:
        raise GitError(
            proc.stderr.strip() or f"git {' '.join(args)} -> {proc.returncode}"
        )
    return proc


def git_out(repo: str, args: list[str], **kw: object) -> str:
    return run_git(repo, args, **kw).stdout  # type: ignore[arg-type]


def config_get(repo: str, key: str) -> str | None:
    proc = run_git(repo, ["config", "--get", key], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def filtered_paths(repo: str) -> dict[str, str]:
    """{tracked path -> filter driver name} from .gitattributes, not a guess."""
    listing = git_out(repo, ["ls-files", "-z"])
    paths = [p for p in listing.split("\0") if p]
    if not paths:
        return {}
    out = git_out(
        repo,
        ["check-attr", "-z", "--stdin", "filter"],
        stdin="\0".join(paths) + "\0",
    )
    fields = out.split("\0")
    result: dict[str, str] = {}
    for i in range(0, len(fields) - 2, 3):
        path, _attr, value = fields[i], fields[i + 1], fields[i + 2]
        if value not in ("unspecified", "unset", ""):
            result[path] = value
    return result


def skip_worktree_paths(repo: str) -> set[str]:
    """Index entries git itself has marked as NOT present in the worktree.

    ``git ls-files -v`` tags a skip-worktree entry with a lowercase-family
    marker ``S``.  A sparse checkout is the normal way that happens, and an
    absent path there is expected, not a corruption signal -- treating it as one
    would make the preflight fire on every sparse clone, i.e. on a legitimate
    operation.  Such paths are reported as SKIPPED (counted and named) rather
    than silently ignored, so the caller is told what was NOT covered.
    """
    out = git_out(repo, ["ls-files", "-v", "-z"])
    skipped: set[str] = set()
    for field in out.split("\0"):
        if len(field) > 2 and field[0] == "S" and field[1] == " ":
            skipped.add(field[2:])
    return skipped


def expand_pathspec(repo: str, spec: str) -> list[str] | None:
    """Tracked paths that ``spec`` selects, or ``None`` if git rejects it.

    ``git checkout -- <arg>`` interprets its argument as a PATHSPEC.  Asking git
    itself what an argument covers is the only reliable way to know: ``:/``
    expands to every tracked file, so does ``*`` and ``:(glob)**``, a bare
    directory expands to its whole subtree, and a literal file path expands to
    exactly itself.  A caller that compares the raw ARGUMENT against a set of
    protected file names learns nothing about any of those.
    """
    proc = run_git(repo, ["ls-files", "-z", "--error-unmatch", "--", spec], check=False)
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.split("\0") if p]


def _magics(extra_hex: list[str] | None) -> list[bytes]:
    magics = [GITCRYPT_MAGIC]
    for h in extra_hex or []:
        magics.append(bytes.fromhex(h))
    return magics


def audit_filters(repo: str, drivers: set[str]) -> list[dict[str, object]]:
    """Config-level audit: is each driver installed, real, and required?"""
    findings: list[dict[str, object]] = []
    for driver in sorted(drivers):
        smudge = config_get(repo, f"filter.{driver}.smudge")
        clean = config_get(repo, f"filter.{driver}.clean")
        required = (config_get(repo, f"filter.{driver}.required") or "").lower()
        if smudge is None or clean is None:
            findings.append(
                {
                    "signal": "config",
                    "driver": driver,
                    "problem": "filter-absent",
                    "detail": "no filter.<driver>.smudge/.clean configured",
                }
            )
            continue
        if smudge in IDENTITY_FILTERS or clean in IDENTITY_FILTERS:
            findings.append(
                {
                    "signal": "config",
                    "driver": driver,
                    "problem": "filter-neutralized",
                    "detail": "smudge/clean is an identity passthrough",
                }
            )
        if required != "true":
            findings.append(
                {
                    "signal": "config",
                    "driver": driver,
                    "problem": "filter-not-required",
                    "detail": f"filter.{driver}.required={required or '(unset)'}",
                }
            )
    return findings


def audit_content(
    repo: str,
    paths: dict[str, str],
    magics: list[bytes],
    skipped: set[str] | None = None,
) -> list[dict[str, object]]:
    """Content-level audit with TWO mechanically independent signals.

    Signal A -- stored-form magic prefix, read directly from the working file.
                At most ``max(len(magic))`` bytes are read and they are compared
                against a constant; no file content is retained, logged or
                emitted.
    Signal B -- ``git hash-object --no-filters`` of the working file versus the
                index entry OID.  Equal means the working file is byte-identical
                to the STORED blob, i.e. the smudge side never ran.  This signal
                reads no content into this process at all.

    ``git status`` is deliberately NOT used: with an identity filter installed
    it reports a clean tree over a working tree holding stored bytes.
    """
    findings: list[dict[str, object]] = []
    width = max(len(m) for m in magics)
    skipped = skipped or set()
    for path in sorted(paths):
        if path in skipped:
            continue  # sparse checkout: git itself says this path is not here
        abs_path = os.path.join(repo, path)
        if not os.path.isfile(abs_path):
            findings.append(
                {
                    "signal": "content",
                    "path": path,
                    "problem": "not-materialized",
                    "detail": "tracked filtered path is absent from the worktree",
                }
            )
            continue
        try:
            with open(abs_path, "rb") as fh:
                head = fh.read(width)
        except OSError as exc:
            findings.append(
                {
                    "signal": "content",
                    "path": path,
                    "problem": "unreadable",
                    "detail": exc.__class__.__name__,
                }
            )
            continue
        signal_a = any(head.startswith(m) for m in magics)

        raw = git_out(repo, ["hash-object", "--no-filters", "--", path]).strip()
        index_oid = run_git(repo, ["rev-parse", f":{path}"], check=False)
        stored = index_oid.stdout.strip() if index_oid.returncode == 0 else ""
        signal_b = bool(stored) and raw == stored

        if signal_a and signal_b:
            findings.append(
                {
                    "signal": "content",
                    "path": path,
                    "problem": "stored-form-in-worktree",
                    "detail": "magic prefix AND raw-hash both say the working "
                    "file is the stored (encrypted) blob",
                }
            )
        elif signal_a != signal_b:
            findings.append(
                {
                    "signal": "content",
                    "path": path,
                    "problem": "ambiguous",
                    "detail": f"magic={signal_a} raw_hash_equals_stored={signal_b}",
                }
            )
            continue
        else:
            continue

        cleaned = run_git(
            repo, ["hash-object", "--path", path, "--", path], check=False
        )
        if cleaned.returncode == 0 and stored and cleaned.stdout.strip() != stored:
            findings.append(
                {
                    "signal": "content",
                    "path": path,
                    "problem": "double-encryption-risk",
                    "detail": "committing this working file now would store a "
                    "re-encrypted blob different from the one on record",
                }
            )
    return findings


def preflight(repo: str, magic_hex: list[str] | None = None) -> dict[str, object]:
    paths = filtered_paths(repo)
    skipped = skip_worktree_paths(repo) & set(paths)
    findings = audit_filters(repo, set(paths.values()))
    findings += audit_content(repo, paths, _magics(magic_hex), skipped)
    return {
        "filtered_path_count": len(paths),
        "sparse_skipped_count": len(skipped),
        "sparse_skipped_paths": sorted(skipped),
        "findings": findings,
        "ok": not findings,
        "safe_next_action": (
            "proceed"
            if not findings
            else "STOP. Restore the real filter (git config filter.<driver>.smudge/"
            ".clean/.required) and re-materialize the affected paths from a "
            "trusted checkout BEFORE committing anything."
        ),
    }


def cmd_preflight(ns: argparse.Namespace) -> int:
    report = preflight(ns.repo, ns.magic_hex)
    emit(ns, report)
    return EXIT_OK if report["ok"] else EXIT_UNSAFE


def _validate_skill_names(skills: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for name in skills:
        if SKILL_NAME_RE.fullmatch(name) is None:
            raise GitError(
                "--skill must be one lower-case hyphen/underscore directory name: "
                f"{name!r}"
            )
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def tree_files(
    repo: str,
    source_ref: str,
    root: str,
    name: str,
    *,
    required: bool,
) -> dict[str, dict[str, str]]:
    """Return files under one skill keyed by their skill-relative path."""
    prefix = f"{root}/{name}/"
    listing = git_out(repo, ["ls-tree", "-r", "-z", source_ref, "--", prefix])
    result: dict[str, dict[str, str]] = {}
    for entry in (e for e in listing.split("\0") if e):
        meta, separator, path = entry.partition("\t")
        if not separator or not path.startswith(prefix):
            raise GitError(f"git returned an invalid tree entry below {prefix}")
        fields = meta.split()
        if len(fields) != 3:
            raise GitError(f"git returned malformed metadata below {prefix}")
        mode, obj_type, oid = fields
        if obj_type not in {"blob", "commit"}:
            raise GitError(f"git returned unexpected object type {obj_type!r}")
        result[path[len(prefix) :]] = {
            "mode": mode,
            "oid": oid,
            "path": path,
            "type": obj_type,
        }
    if required and not result:
        raise GitError(f"{root}/{name}/ has no files at {source_ref}")
    return result


def plan_overlay(
    repo: str,
    source_ref: str,
    skills: list[str],
    source_root: str,
    destination_root: str,
    *,
    refuse_overwrite: bool,
) -> dict[str, object]:
    """Plan a union-preserving overlay between skill roots.

    Destination-only paths are named and preserved.  Equal paths are no-ops.
    Migration into canonical refuses divergent destinations; generation into the
    compatibility projection records them as explicit overwrites.
    """
    plan: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    nonregular_sources: list[dict[str, str]] = []
    preserved: list[str] = []
    overwrites: list[dict[str, str]] = []
    for name in _validate_skill_names(skills):
        source = tree_files(repo, source_ref, source_root, name, required=True)
        destination = tree_files(
            repo, source_ref, destination_root, name, required=False
        )
        preserved.extend(
            destination[rel]["path"]
            for rel in sorted(destination.keys() - source.keys())
        )
        for rel, item in sorted(source.items()):
            dst = f"{destination_root}/{name}/{rel}"
            current = destination.get(rel)
            if item["type"] != "blob" or item["mode"] not in REGULAR_MODES:
                nonregular_sources.append(
                    {
                        "path": item["path"],
                        "mode": item["mode"],
                        "type": item["type"],
                    }
                )
                continue
            if current and (current["mode"], current["oid"]) == (
                item["mode"],
                item["oid"],
            ):
                continue
            if current and refuse_overwrite:
                conflicts.append(
                    {
                        "source": item["path"],
                        "destination": dst,
                        "source_mode": item["mode"],
                        "source_oid": item["oid"],
                        "destination_mode": current["mode"],
                        "destination_oid": current["oid"],
                    }
                )
                continue
            if current:
                overwrites.append(
                    {
                        "source": item["path"],
                        "destination": dst,
                        "source_mode": item["mode"],
                        "source_oid": item["oid"],
                        "destination_mode": current["mode"],
                        "destination_oid": current["oid"],
                    }
                )
            plan.append(
                {
                    "mode": item["mode"],
                    "oid": item["oid"],
                    "src": item["path"],
                    "dst": dst,
                }
            )
    return {
        "plan": plan,
        "conflicts": conflicts,
        "nonregular_source_entries": nonregular_sources,
        "preserved_paths": sorted(preserved),
        "overwrites": overwrites,
        "overwritten_paths": sorted(item["destination"] for item in overwrites),
    }


def projection_plan_digest(source_commit: str, report: dict[str, object]) -> str:
    """Bind overwrite approval to one immutable source tree and exact plan."""
    receipt = {
        "version": 1,
        "operation": "project",
        "source_commit": source_commit,
        "plan": report["plan"],
        "overwrites": report["overwrites"],
        "preserved_paths": report["preserved_paths"],
    }
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def plan_mirror(repo: str, source_ref: str, skills: list[str]) -> dict[str, object]:
    """Union legacy projection paths into canonical without clobbering it."""
    return plan_overlay(
        repo,
        source_ref,
        skills,
        PROJECTION_ROOT,
        CANONICAL_ROOT,
        refuse_overwrite=True,
    )


def plan_projection(repo: str, source_ref: str, skills: list[str]) -> dict[str, object]:
    """Overlay canonical blobs onto selected generated projections; delete nothing."""
    return plan_overlay(
        repo,
        source_ref,
        skills,
        CANONICAL_ROOT,
        PROJECTION_ROOT,
        refuse_overwrite=False,
    )


def build_commit(
    repo: str, source_ref: str, plan: list[dict[str, str]], message: str
) -> str:
    """Build the dual-write commit against a TEMPORARY index. No worktree I/O."""
    fd, index_path = tempfile.mkstemp(prefix="d001-index-")
    os.close(fd)
    os.unlink(index_path)  # git wants to create it itself
    env = {"GIT_INDEX_FILE": index_path}
    try:
        run_git(repo, ["read-tree", source_ref], env=env)
        for item in plan:
            run_git(
                repo,
                [
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"{item['mode']},{item['oid']},{item['dst']}",
                ],
                env=env,
            )
        tree = git_out(repo, ["write-tree"], env=env).strip()
    finally:
        if os.path.exists(index_path):
            os.unlink(index_path)
    parent = git_out(repo, ["rev-parse", f"{source_ref}^{{commit}}"]).strip()
    return git_out(repo, ["commit-tree", tree, "-p", parent, "-m", message]).strip()


def tree_entry(repo: str, ref: str, path: str) -> tuple[str, str]:
    """Return one tree entry's ``(mode, oid)`` without path-text ambiguity."""
    record = git_out(repo, ["ls-tree", "-z", ref, "--", path]).rstrip("\0")
    meta, separator, listed_path = record.partition("\t")
    fields = meta.split()
    if not separator or listed_path != path or len(fields) != 3:
        raise GitError(f"could not resolve one exact tree entry for {ref}:{path}")
    mode, _obj_type, oid = fields
    return mode, oid


def verify_mirror(
    repo: str, source_ref: str, commit: str, plan: list[dict[str, str]]
) -> dict[str, object]:
    listing = git_out(
        repo, ["diff", "--name-status", "-z", "--no-renames", source_ref, commit]
    )
    fields = [f for f in listing.split("\0") if f]
    changed = [
        (fields[i].strip()[:1], fields[i + 1]) for i in range(0, len(fields) - 1, 2)
    ]
    expected = sorted(item["dst"] for item in plan)
    actual = sorted(p for _s, p in changed)
    pairs = []
    for item in plan:
        left_mode, left_oid = tree_entry(repo, source_ref, item["src"])
        right_mode, right_oid = tree_entry(repo, commit, item["dst"])
        pairs.append(
            {
                "src": item["src"],
                "dst": item["dst"],
                "source_mode": left_mode,
                "destination_mode": right_mode,
                "blob_identical": left_oid == right_oid,
                "mode_identical": left_mode == right_mode,
                "identical": (left_mode, left_oid) == (right_mode, right_oid),
            }
        )
    return {
        "changed_paths": actual,
        "expected_paths": expected,
        "scope_exact": actual == expected,
        "statuses": sorted({s for s, _p in changed}),
        "additive_only": all(s in ("A", "M", "T") for s, _p in changed),
        "blob_pairs": pairs,
        "all_blobs_identical": all(p["blob_identical"] for p in pairs),
        "all_modes_identical": all(p["mode_identical"] for p in pairs),
    }


def atomic_create_ref(repo: str, ref: str, commit: str) -> bool:
    """Create ``ref`` iff no direct or symbolic ref occupies that name.

    ``update-ref <ref> <new> <zero>`` treats a dangling symbolic ref as absent,
    even with ``--no-deref``.  A prepared transaction holds the ref lock while
    the still-visible pre-image is inspected; a symbolic pre-image aborts the
    transaction, and a direct pre-image makes ``prepare`` fail.

    The transaction is driven over a BYTE pipe, never a text one: a text-mode
    stdin on Windows rewrites the newline command terminator to CR+LF
    (os.linesep) and git then rejects the carriage-return-suffixed command as
    unknown (measured), so every ref creation would otherwise falsely conflict.
    """
    proc = subprocess.Popen(
        ["git", "-C", repo, "update-ref", "--no-deref", "--stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    def request(command: str) -> bool:
        proc.stdin.write(command.encode("utf-8", "surrogateescape") + b"\n")
        proc.stdin.flush()
        expected = command.split()[0].encode("utf-8") + b": ok"
        return proc.stdout.readline().strip() == expected

    prepared = request("start")
    if prepared:
        proc.stdin.write(f"create {ref} {commit}\n".encode("utf-8", "surrogateescape"))
        prepared = request("prepare")
    occupied_by_symref = False
    if prepared:
        occupied_by_symref = (
            run_git(repo, ["symbolic-ref", "--quiet", ref], check=False).returncode == 0
        )
        terminal = "abort" if occupied_by_symref else "commit"
        completed = request(terminal)
    else:
        completed = False
    proc.stdin.close()
    returncode = proc.wait()
    return prepared and not occupied_by_symref and completed and returncode == 0


def cmd_overlay(ns: argparse.Namespace, *, project: bool) -> int:
    pre = preflight(ns.repo, ns.magic_hex)
    if not pre["ok"]:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "preflight-unsafe",
                "message": "REFUSED before any write: the repository's content "
                "filters or working tree are not in a safe state.",
                "preflight": pre,
            },
        )
        return EXIT_REFUSED
    valid_branch = run_git(
        ns.repo, ["check-ref-format", "--branch", ns.branch], check=False
    )
    if valid_branch.returncode != 0:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "invalid-branch-name",
                "message": "REFUSED before any write: --branch must be one valid "
                "Git branch name.",
            },
        )
        return EXIT_REFUSED
    try:
        source_commit = git_out(
            ns.repo, ["rev-parse", f"{ns.source_ref}^{{commit}}"]
        ).strip()
        report = (
            plan_projection(ns.repo, source_commit, ns.skill)
            if project
            else plan_mirror(ns.repo, source_commit, ns.skill)
        )
    except GitError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE
    report["source_commit"] = source_commit
    if project:
        report["plan_digest"] = projection_plan_digest(source_commit, report)
    plan = report["plan"]
    nonregular = report["nonregular_source_entries"]
    if nonregular:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "nonregular-source-refused",
                "message": "REFUSED before any write: a skill source contains a "
                "symlink, gitlink, or other non-regular entry. Canonical skill "
                "content must use mode 100644 or 100755.",
                **report,
            },
        )
        return EXIT_REFUSED
    conflicts = report["conflicts"]
    if conflicts:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "canonical-conflict-route-required",
                "message": "REFUSED before any write: projection content differs "
                "from an existing canonical blob. Route and resolve each conflict; "
                "this migration command never overwrites canonical content.",
                **report,
            },
        )
        return EXIT_REFUSED
    exists = run_git(
        ns.repo,
        ["rev-parse", "--verify", "--quiet", f"refs/heads/{ns.branch}"],
        check=False,
    )
    symbolic = run_git(
        ns.repo,
        ["symbolic-ref", "--quiet", f"refs/heads/{ns.branch}"],
        check=False,
    )
    if exists.returncode == 0 or symbolic.returncode == 0:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "branch-exists",
                "message": f"REFUSED: refs/heads/{ns.branch} already exists. This "
                "tool never moves an existing ref; choose a new branch name.",
            },
        )
        return EXIT_REFUSED
    if not ns.apply:
        emit(
            ns,
            {
                "decision": "dry-run",
                "branch": ns.branch,
                "source_ref": ns.source_ref,
                **report,
                "message": "DRY RUN -- nothing written. Re-run with --apply.",
            },
        )
        return EXIT_OK
    if project and report["overwritten_paths"]:
        supplied = ns.plan_digest or ""
        expected = str(report["plan_digest"])
        if not hmac.compare_digest(supplied, expected):
            emit(
                ns,
                {
                    "decision": "refuse",
                    "reason": "projection-plan-not-reviewed",
                    "message": "REFUSED before any write: overwrites require the "
                    "plan_digest from a dry run of this exact immutable source tree. "
                    "Review overwrites, then pass --plan-digest <digest>.",
                    **report,
                },
            )
            return EXIT_REFUSED
    if not plan:
        emit(
            ns,
            {
                "decision": "no-op",
                "branch": ns.branch,
                "source_ref": ns.source_ref,
                **report,
                "message": "NO-OP -- selected skills are already reconciled.",
            },
        )
        return EXIT_OK
    commit = build_commit(ns.repo, source_commit, plan, ns.message)
    verification = verify_mirror(ns.repo, source_commit, commit, plan)
    if not (
        verification["scope_exact"]
        and verification["additive_only"]
        and verification["all_blobs_identical"]
        and verification["all_modes_identical"]
    ):
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "verification-failed",
                "message": "REFUSED: the built commit did not verify; the ref was "
                "NOT updated and the worktree/existing refs are untouched. The "
                "unreachable test commit may remain until normal Git GC.",
                "verification": verification,
            },
        )
        return EXIT_REFUSED
    created = atomic_create_ref(ns.repo, f"refs/heads/{ns.branch}", commit)
    if not created:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "branch-create-conflict",
                "message": "REFUSED: the target ref exists or appeared after "
                "preflight. Atomic create failed, so no existing ref or worktree "
                "path was changed; the unreachable commit may remain until normal "
                "Git GC.",
                "commit": commit,
                **report,
                "verification": verification,
            },
        )
        return EXIT_REFUSED
    emit(
        ns,
        {
            "decision": "applied",
            "branch": ns.branch,
            "commit": commit,
            **report,
            "verification": verification,
        },
    )
    return EXIT_OK


def cmd_mirror(ns: argparse.Namespace) -> int:
    return cmd_overlay(ns, project=False)


def cmd_project(ns: argparse.Namespace) -> int:
    return cmd_overlay(ns, project=True)


def cmd_materialize(ns: argparse.Namespace) -> int:
    if not ns.path:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "broad-materialization-refused",
                "message": "REFUSED: this tool never materialises the whole index. "
                "Every path must be named explicitly with --path; a broad restore "
                "writes every filtered file through the smudge filter and can "
                "replace protected plaintext with stored bytes.",
            },
        )
        return EXIT_REFUSED
    for path in ns.path:
        if os.path.isabs(path) or path.startswith("..") or path in (".", ""):
            sys.stderr.write(f"--path must be a repo-relative file path: {path!r}\n")
            return EXIT_USAGE
    protected = filtered_paths(ns.repo)

    # GATE: every argument must be a LITERAL, TRACKED, SINGLE file path.
    # git resolves `--path` as a pathspec, so an argument that expands to
    # anything other than exactly itself is a broad materialisation wearing a
    # file name -- `:/`, `*`, `:(glob)**`, `secrets`, `secrets/` all expand to
    # other people's files.  Comparing the ARGUMENT against `protected` (below)
    # cannot see any of that, because none of those strings IS a protected path.
    covered: set[str] = set()
    not_literal: list[str] = []
    not_tracked: list[str] = []
    for path in ns.path:
        expanded = expand_pathspec(ns.repo, path)
        if expanded is None:
            not_tracked.append(path)
        elif expanded != [path]:
            not_literal.append(path)
            covered.update(expanded)
        else:
            covered.add(path)
    if not_literal or not_tracked:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "pathspec-refused",
                "message": "REFUSED before any write: --path takes a literal "
                "tracked file path, not a git pathspec. These arguments select "
                "something other than exactly themselves (or nothing tracked at "
                "all), and a restore through them writes files this tool was "
                "never asked to touch -- through the smudge filter: "
                + ", ".join(sorted(not_literal + not_tracked)),
                "not_a_literal_tracked_file": sorted(not_literal),
                "not_tracked": sorted(not_tracked),
                "would_have_covered_count": len(covered),
                "protected_in_expansion": sorted(covered & set(protected)),
            },
        )
        return EXIT_REFUSED

    # GATE: no filtered path may be restored -- tested against the EXPANSION,
    # not against the literal argument.  The gate above makes the two identical
    # today; keeping this one expansion-shaped means a future loosening of that
    # gate cannot silently re-open the hole.
    hits = sorted(covered & set(protected))
    if hits:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "filtered-path-refused",
                "message": "REFUSED: these paths carry a content filter and must "
                "not be restored by this tool: " + ", ".join(hits),
                "paths": hits,
            },
        )
        return EXIT_REFUSED
    config_findings = audit_filters(ns.repo, set(protected.values()))
    if config_findings:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "filter-config-unsafe",
                "message": "REFUSED: the repository's content filters are not in a "
                "safe state; restoring anything now risks writing stored bytes "
                "into protected paths.",
                "findings": config_findings,
            },
        )
        return EXIT_REFUSED

    # GATE: the two-signal CONTENT detector -- the one that catches an identity
    # passthrough spelled outside IDENTITY_FILTERS -- now guards the one command
    # in this tool that writes, not just `preflight`.
    content_findings = audit_content(
        ns.repo,
        protected,
        _magics(ns.magic_hex),
        skip_worktree_paths(ns.repo) & set(protected),
    )
    if content_findings:
        emit(
            ns,
            {
                "decision": "refuse",
                "reason": "worktree-content-unsafe",
                "message": "REFUSED: the working tree already holds stored-form "
                "bytes for at least one protected path; restoring anything now "
                "compounds the damage. Fix the filter and re-materialize from a "
                "trusted checkout first.",
                "findings": content_findings,
            },
        )
        return EXIT_REFUSED
    if not ns.apply:
        emit(
            ns,
            {
                "decision": "dry-run",
                "paths": list(ns.path),
                "message": "DRY RUN -- nothing written. Re-run with --apply.",
            },
        )
        return EXIT_OK
    run_git(ns.repo, ["checkout", "--", *ns.path])
    emit(ns, {"decision": "applied", "paths": list(ns.path)})
    return EXIT_OK


def emit(ns: argparse.Namespace, payload: dict[str, object]) -> None:
    if getattr(ns, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key in ("decision", "reason", "message", "safe_next_action"):
        if key in payload:
            print(f"{key}: {payload[key]}")
    for finding in payload.get("findings", []) or []:  # type: ignore[union-attr]
        print(f"  finding: {finding}")
    pre = payload.get("preflight")
    if isinstance(pre, dict):
        for finding in pre.get("findings", []):
            print(f"  finding: {finding}")
    for item in payload.get("plan", []) or []:  # type: ignore[union-attr]
        print(f"  mirror: {item['src']} -> {item['dst']} ({item['oid'][:12]})")
    for path in payload.get("preserved_paths", []) or []:  # type: ignore[union-attr]
        print(f"  preserved: {path}")
    for path in payload.get("overwritten_paths", []) or []:  # type: ignore[union-attr]
        print(f"  overwrite: {path}")
    for conflict in payload.get("conflicts", []) or []:  # type: ignore[union-attr]
        print(
            f"  conflict: {conflict['source']} -> {conflict['destination']} "
            f"({conflict['source_oid'][:12]} != "
            f"{conflict['destination_oid'][:12]})"
        )
    if "commit" in payload:
        print(f"commit: {payload['commit']}")
    verification = payload.get("verification")
    if isinstance(verification, dict):
        print(f"  scope_exact: {verification['scope_exact']}")
        print(f"  additive_only: {verification['additive_only']}")
        print(f"  all_blobs_identical: {verification['all_blobs_identical']}")
        print(f"  all_modes_identical: {verification['all_modes_identical']}")
    if "ok" in payload:
        print(f"ok: {payload['ok']}")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--magic-hex",
        action="append",
        default=None,
        help="extra stored-form magic prefix (hex) for Signal A; repeatable",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preflight", help="read-only filter + content audit")

    m = sub.add_parser("mirror", help="build the dual-write commit (plumbing only)")
    m.add_argument("--source-ref", required=True)
    m.add_argument("--skill", action="append", required=True)
    m.add_argument("--branch", required=True)
    m.add_argument(
        "--message",
        default="docs(skills): mirror skill changes into the canonical "
        ".agents/skills tree (D-001)",
    )
    m.add_argument("--apply", action="store_true")

    p = sub.add_parser("project", help="generate projections from canonical skills")
    p.add_argument("--source-ref", required=True)
    p.add_argument("--skill", action="append", required=True)
    p.add_argument("--branch", required=True)
    p.add_argument(
        "--message",
        default="docs(skills): generate compatibility projection from canonical "
        ".agents/skills tree (D-001)",
    )
    p.add_argument(
        "--plan-digest",
        help="digest from the reviewed dry run (required for divergent overwrites)",
    )
    p.add_argument("--apply", action="store_true")

    x = sub.add_parser("materialize", help="guarded, explicit-paths-only restore")
    x.add_argument("--path", action="append", default=None)
    x.add_argument("--apply", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    handlers = {
        "preflight": cmd_preflight,
        "mirror": cmd_mirror,
        "project": cmd_project,
        "materialize": cmd_materialize,
    }
    try:
        return handlers[ns.cmd](ns)
    except GitError as exc:
        sys.stderr.write(f"git error: {exc}\n")
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
