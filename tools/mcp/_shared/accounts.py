#!/usr/bin/env python3
"""Reusable multi-account credential store + cycling for MCP hub multiplexers.

A cswap-style layer (like ``claude-swap`` for Claude accounts, ``modal profile``,
or multiple ``gcloud config configurations``) generalized across N platforms so a
lazy MCP hub can hold SEVERAL named accounts per backend, switch the active one,
and CYCLE (rotate) through them.

Two account modes:

* ``env``  -- an account is a bundle of environment variables (literal values or
  ``${ENV}`` references). Used for key-based backends (RunPod, Kaggle, Modal,
  Lightning, rclone). The on-disk store is the source of truth; the hub injects
  the active account's env when it spawns that backend.
* ``cli``  -- an account maps to the platform CLI's own profile mechanism (Azure
  subscriptions, gcloud configurations). ``list``/``switch``/``add``/``remove``
  delegate to the CLI (the CLI is the source of truth); no env is injected.

File-based creds (social platforms): a login is often a FILE, not just env --
Instagram's ``session.json``, fb-messenger's ``cookies.json``, WhatsApp's
Baileys ``auth_info/`` directory. An ``env``-mode account may therefore also
carry a ``files`` map (``{slot_key: source_path}``); each platform declares the
matching ``FileSlot``s on its policy. On switch/cycle the hub makes the active
account's file the one the backend loads, by EITHER pointing the backend's
configurable-path env var at it (``INSTA_DATA_DIR`` -> a dir, ``FB_COOKIES_PATH``
-> a file; copy-free) OR, when the backend has no such override (WhatsApp),
COPYING the account's source onto the backend's fixed path before respawn.

Seeding: if an ``env`` platform has no stored accounts but its registration env
vars are all present, an in-memory ``default`` account is synthesized from
``${ENV}`` references. It is never persisted -- literal secrets only reach the
on-disk store when the user explicitly adds them.

The on-disk store (``accounts.json``) may legitimately hold literal secrets, so
it is written with restrictive permissions. How it is treated by git is NOT
uniform across the hubs that share this module -- check the hub you are in
before assuming either way:

* ``cloud-hub`` and ``search-hub``: the store is NOT gitignored. It is TRACKED
  and committed as git-crypt CIPHERTEXT (``.gitattributes`` maps
  ``tools/mcp/**/accounts.json`` to ``filter=git-crypt``) and decrypts to
  plaintext only in a tree where ``git-crypt unlock`` has been run. So a
  ``git add`` of this file is expected, not a leak -- provided git-crypt is
  installed, so the clean filter actually encrypts it.
* ``social-hub``: the store IS gitignored (``tools/mcp/social-hub/.gitignore``
  lists ``accounts.json``) and is not tracked at all. There, committing it
  WOULD be a plaintext leak.

For the tracked hubs there is a second consequence worth knowing: a FRESH
CHECKOUT OR WORKTREE starts LOCKED -- ``git worktree add`` does not inherit an
unlocked state -- so the store there is ciphertext beginning with the git-crypt
magic header, which ``_load`` detects and reports (see
``AccountStoreLoadError``) instead of failing with a bare ``UnicodeDecodeError``.

Design notes for reuse: this module depends only on the stdlib and a small
``AccountPolicy`` passed in per platform -- no coupling to any backend registry,
so both cloud-hub and social-hub can share it. The CLI ``runner`` is injectable
so the cli-profile path is unit-testable without a real ``az``/``gcloud``.

Switching or cycling accounts to evade a platform's per-account free-tier or
rate limits may violate that platform's Terms of Service; this tooling is
ordinary account management for the user's OWN accounts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

# A whole-string ``${NAME}`` reference (accounts.json may reference env vars
# instead of embedding literal secrets).
_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")

ACCOUNT_OPS = ("list", "current", "add", "remove", "switch", "cycle")

# git-crypt prefixes every file it encrypts with this 10-byte magic header, so a
# store checked out in a tree where git-crypt is LOCKED starts with these bytes
# and is ciphertext from offset 10 onward. Detected explicitly because the naive
# symptom (``UnicodeDecodeError`` at position 10) names neither git-crypt nor the
# remedy, and costs real time to diagnose.
_GITCRYPT_MAGIC = b"\x00GITCRYPT\x00"

# (rc, stdout, stderr)
Runner = Callable[[tuple[str, ...]], "tuple[int, str, str]"]


class AccountStoreLoadError(RuntimeError):
    """The account store exists but cannot be decoded, parsed, or used.

    Raised instead of degrading to an EMPTY store, which is never a safe
    fallback for a NON-empty file, for two measured reasons:

    * "no accounts" does not mean "no credentials" -- with the configured
      accounts gone, ``_seed_record`` synthesizes a ``default`` from the
      registration env vars, so the backend keeps running under a DIFFERENT
      credential than the operator configured (silent substitution).
    * the store is then only one ordinary op away from destruction: any
      add/remove/switch/cycle calls ``_persist``, which ``os.replace``s the
      empty-loaded state over the original file. A malformed store is usually
      still repairable by hand; after that write it is not.

    A MISSING store -- and an empty/whitespace-only one, which holds no
    accounts and so cannot trigger either failure -- is the normal first-run
    case and stays quiet.
    """


@dataclass(frozen=True)
class CliProfileSpec:
    """How to drive a platform CLI's own profile mechanism (cli mode).

    ``activate_cmd``/``add_cmd``/``remove_cmd`` may contain the literal token
    ``{name}`` which is substituted with the requested account name. ``list_cmd``
    must emit one profile name per line; ``current_cmd`` must emit the active
    name on the first non-empty line.
    """

    list_cmd: tuple[str, ...]
    current_cmd: tuple[str, ...]
    activate_cmd: tuple[str, ...]
    add_cmd: tuple[str, ...] | None = None
    remove_cmd: tuple[str, ...] | None = None
    add_hint: str = ""
    remove_hint: str = ""


@dataclass(frozen=True)
class FileSlot:
    """A session/cookie artifact a backend loads from a FIXED location.

    Social logins are FILE-based, so a multi-account model must swap the ACTIVE
    file per account -- not just env. Each account supplies the SOURCE path for a
    slot in its ``files`` map (``{key: path}``); the store then makes that source
    the one the backend reads:

    * ``env_var`` set  -- the backend honours a configurable path via this env
      var (``INSTA_DATA_DIR`` -> a directory, ``FB_COOKIES_PATH`` -> a file), so
      the hub simply exports the account's source as that var. Copy-free; the
      primary, non-destructive mechanism.
    * ``env_var`` empty -- the backend reads only its fixed ``dest`` (WhatsApp's
      Baileys ``auth_info/``), so the hub COPIES the account's source onto
      ``dest`` before respawn. The ONLY mechanism for such backends.

    ``dest`` is the backend's fixed path (used for the copy + for reporting).
    ``is_dir`` marks a directory artifact (copied recursively) vs a single file.
    """

    key: str
    dest: str
    env_var: str = ""
    is_dir: bool = False


@dataclass(frozen=True)
class AccountPolicy:
    """Per-platform account policy handed to the store by the hub."""

    platform: str
    mode: str  # "env" | "cli"
    seed_env: tuple[str, ...] = ()
    cli: CliProfileSpec | None = None
    label: str = ""
    files: tuple[FileSlot, ...] = ()


@dataclass(frozen=True)
class FileAction:
    """One planned copy of an account's source artifact onto a backend path."""

    key: str
    src: str
    dest: str
    is_dir: bool


def _default_runner(argv: tuple[str, ...]) -> tuple[int, str, str]:
    """Run a CLI command, returning (rc, stdout, stderr). Never raises.

    ``argv[0]`` is resolved via ``shutil.which`` so PATHEXT shims (``az.CMD``,
    ``gcloud.CMD`` on Windows) are found and executed with their explicit
    extension -- a bare ``az`` would otherwise miss the ``.CMD`` under
    ``CreateProcess``.
    """
    if not argv:
        return 127, "", "empty command"
    exe = shutil.which(argv[0]) or argv[0]
    try:
        proc = subprocess.run(
            [exe, *argv[1:]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        return 127, "", str(exc)


def resolve_env(env: Mapping[str, str], environ: Mapping[str, str]) -> dict[str, str]:
    """Resolve a stored env bundle: ``${NAME}`` -> environ[NAME], else literal."""
    out: dict[str, str] = {}
    for key, val in env.items():
        if isinstance(val, str):
            match = _REF.match(val)
            out[key] = environ.get(match.group(1), "") if match else val
    return out


def resolve_path(path: str) -> str:
    """Normalize an account file source: expand ``~`` and ``$VAR``/``%VAR%``."""
    return (
        os.path.expanduser(os.path.expandvars(path)) if isinstance(path, str) else path
    )


def copy_artifact(src: str, dest: str, is_dir: bool) -> None:
    """Replace ``dest`` with a copy of ``src`` (file or directory tree).

    Used only for backends with no configurable-path env var (WhatsApp): the
    active account's session directory/file is copied onto the fixed path the
    backend reads before it respawns. Raises on failure so the caller can report.
    """
    if is_dir:
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src, dest)
    else:
        parent = os.path.dirname(dest)
        if parent:
            os.makedirs(parent, exist_ok=True)
        shutil.copyfile(src, dest)


def account_tool_defs(
    prefix: str,
    platform: str,
    mode: str,
    label: str = "",
    file_slots: tuple[str, ...] = (),
) -> list[dict]:
    """The six synthetic account-management tool schemas for one backend.

    Names are ``<prefix>_account_<op>`` so they never collide across backends
    (prefixes are unique) and are always safe to prefix (they are hub-native).
    ``file_slots`` (session/cookie slot keys) enriches the ``add`` schema so a
    social account can carry per-account session/cookie FILE paths.
    """
    who = label or platform
    string = {"type": "string"}
    name_arg = {"type": "object", "properties": {"name": string}, "required": ["name"]}
    add_props: dict = {"name": string}
    if mode == "env":
        add_props["env"] = {
            "type": "object",
            "description": "Env vars for this account; values "
            "may be literals or ${ENV} refs.",
            "additionalProperties": {"type": "string"},
        }
        add_props["label"] = {
            "type": "string",
            "description": "Optional human label / identity for "
            "this account (e.g. the account email "
            "or a friendly name), shown by "
            "list/current so you know which "
            "underlying account each name maps to.",
        }
        add_required = ["name", "env"]
        if file_slots:
            add_props["files"] = {
                "type": "object",
                "description": "Per-account session/cookie file (or dir) paths, "
                "keyed by slot: " + ", ".join(file_slots) + ". "
                "Switching points the backend at this account's "
                "file. env may be {} when only files differ.",
                "additionalProperties": {"type": "string"},
            }
            add_required = ["name"]  # a file-only account needs no env bundle
    else:
        add_required = ["name"]
    empty = {"type": "object", "properties": {}}
    files_tip = (
        " Accounts may carry per-account session/cookie files "
        f"({', '.join(file_slots)})."
        if file_slots
        else ""
    )
    tip = (
        f" Manages the user's OWN {who} accounts "
        f"({'env-var profiles' if mode == 'env' else 'CLI profiles'})." + files_tip
    )
    return [
        {
            "name": f"{prefix}_account_list",
            "description": f"List the configured {who} accounts and which is active."
            + tip,
            "inputSchema": empty,
        },
        {
            "name": f"{prefix}_account_current",
            "description": f"Show the currently active {who} account." + tip,
            "inputSchema": empty,
        },
        {
            "name": f"{prefix}_account_add",
            "description": f"Add a named {who} account." + tip,
            "inputSchema": {
                "type": "object",
                "properties": add_props,
                "required": add_required,
            },
        },
        {
            "name": f"{prefix}_account_remove",
            "description": f"Remove a named {who} account." + tip,
            "inputSchema": name_arg,
        },
        {
            "name": f"{prefix}_account_switch",
            "description": f"Switch the active {who} account by name; the hub "
            f"kills+respawns the backend so new creds take effect." + tip,
            "inputSchema": name_arg,
        },
        {
            "name": f"{prefix}_account_cycle",
            "description": f"Rotate to the NEXT {who} account (round-robin); the "
            f"hub kills+respawns the backend." + tip,
            "inputSchema": empty,
        },
    ]


class AccountStore:
    """A multi-platform, multi-account credential store with cycling.

    ``env``-mode accounts live in the JSON store; ``cli``-mode operations
    delegate to an (injectable) ``runner`` so they can be unit-tested.
    """

    def __init__(
        self,
        path: str,
        policies: Iterable[AccountPolicy],
        environ: Mapping[str, str] | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.path = path
        self.policies: dict[str, AccountPolicy] = {p.platform: p for p in policies}
        self.environ = environ if environ is not None else os.environ
        self.runner = runner or _default_runner
        self._data: dict[str, dict] = self._load()

    # ---- persistence -----------------------------------------------------
    def _load(self) -> dict[str, dict]:
        # A missing/unreadable store is the normal first-run case -> start empty.
        try:
            with open(self.path, "rb") as fh:
                raw = fh.read()
        except OSError:
            return {}
        # An UNDECODABLE store, by contrast, is a real misconfiguration: failing
        # loudly beats a silently empty rotation pool, so these two paths raise.
        if raw.startswith(_GITCRYPT_MAGIC):
            raise AccountStoreLoadError(
                f"{self.path}: this account store is still git-crypt ENCRYPTED "
                f"(it begins with the git-crypt magic header), so it cannot be "
                f"read. git-crypt is locked in this working tree -- note that "
                f"'git worktree add' does NOT inherit an unlocked state. "
                f"Remedy: unlock git-crypt here (e.g. 'git-crypt unlock "
                f"<key-file>') and retry. Refusing to continue with an empty "
                f"store, which would silently disable every configured account."
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AccountStoreLoadError(
                f"{self.path}: this account store is not valid UTF-8 and cannot "
                f"be decoded ({exc}). Remedy: repair or remove the file. "
                f"Refusing to continue with an empty store, which would silently "
                f"disable every configured account."
            ) from exc
        # An EMPTY (or whitespace-only) store is treated like a MISSING one: it
        # holds no accounts, so it can neither substitute a credential nor lose
        # one, and a zero-byte file is a plausible bootstrap artifact (``touch``,
        # an interrupted create, a truncating ``New-Item -Force``). Deliberate
        # tolerance, pinned by test_empty_store_file_starts_empty_quietly.
        if not text.strip():
            return {}
        # Anything else that fails to parse is a real misconfiguration. See
        # AccountStoreLoadError for why an empty fallback is NOT safe here.
        # Only the parser's own position/reason is reported -- never the file's
        # content, which may hold literal secrets.
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AccountStoreLoadError(
                f"{self.path}: this account store is not valid JSON "
                f"({exc.msg} at line {exc.lineno} column {exc.colno}). Remedy: "
                f"repair the file by hand (it has NOT been modified) or remove "
                f"it to start empty. Refusing to continue with an empty store, "
                f"which would silently swap in a different credential and let "
                f"the next account write overwrite this file."
            ) from exc
        if not isinstance(data, dict):
            raise AccountStoreLoadError(
                f"{self.path}: this account store must be a JSON OBJECT mapping "
                f"platform -> record, but its top level is a "
                f"{type(data).__name__}. Remedy: repair the file by hand (it has "
                f"NOT been modified) or remove it to start empty. Refusing to "
                f"continue with an empty store, which would silently swap in a "
                f"different credential and let the next account write overwrite "
                f"this file."
            )
        return data

    def _persist(self) -> None:
        tmp = f"{self.path}.tmp"
        # 0600 AT CREATION, not after: the temp file carries the SAME literal
        # secrets as the final store, so chmod-ing only the destination left the
        # whole plaintext bundle readable at the process umask (typically 0644)
        # for the length of every write.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:  # a stale tmp from an earlier crash keeps its old, laxer mode
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
        try:  # best-effort lockdown (Windows honours the read-only bit only)
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    # ---- env-mode helpers ------------------------------------------------
    def _seed_record(self, pol: AccountPolicy) -> dict | None:
        """Synthesize an in-memory ``default`` record from registration env."""
        if pol.seed_env and all(n in self.environ for n in pol.seed_env):
            return {
                "active": "default",
                "accounts": [
                    {"name": "default", "env": {n: f"${{{n}}}" for n in pol.seed_env}}
                ],
            }
        return None

    def _view(self, pol: AccountPolicy) -> dict:
        """Read-only env-mode view: stored record, else a seeded default."""
        rec = self._data.get(pol.platform)
        if rec and rec.get("accounts"):
            return rec
        return self._seed_record(pol) or {"active": None, "accounts": []}

    def _materialize(self, pol: AccountPolicy) -> dict:
        """Ensure a writable stored record exists (copying any seed in)."""
        rec = self._data.get(pol.platform)
        if not rec or not rec.get("accounts"):
            seed = self._seed_record(pol)
            rec = (
                {
                    "active": seed["active"],
                    "accounts": [dict(a) for a in seed["accounts"]],
                }
                if seed
                else {"active": None, "accounts": []}
            )
            self._data[pol.platform] = rec
        return rec

    def _active_account(self, pol: AccountPolicy) -> dict | None:
        """The active account record for an env-mode platform, or None."""
        rec = self._view(pol)
        active = rec.get("active")
        for acct in rec.get("accounts", []):
            if acct.get("name") == active:
                return acct
        return None

    def active_env(self, platform: str) -> dict[str, str]:
        """Resolved env for the active account (env mode); {} otherwise.

        Includes any ``env_var`` file-slot pointers (``INSTA_DATA_DIR`` /
        ``FB_COOKIES_PATH``) the active account supplies a source for, so a
        backend with a configurable path is redirected WITHOUT a copy.
        """
        pol = self.policies.get(platform)
        if pol is None or pol.mode != "env":
            return {}
        acct = self._active_account(pol)
        if acct is None:
            return {}
        out = resolve_env(acct.get("env", {}), self.environ)
        files = acct.get("files") or {}
        for slot in pol.files:
            if (
                slot.env_var
                and isinstance(files.get(slot.key), str)
                and files[slot.key]
            ):
                out[slot.env_var] = resolve_path(files[slot.key])
        return out

    def env_for(self, platform: str, name: str) -> dict[str, str]:
        """Resolved env for a SPECIFIC named account (env mode); {} if absent.

        Like ``active_env`` but for an EXPLICITLY named account, so a caller that
        routes per-key (search-hub's rotator lazily spawns one child per API key)
        can bind a child to ANY key, not only the active one. Read-only: it never
        changes which account is active. Additive helper -- the six account ops,
        ``active_env`` and file handling are untouched.
        """
        pol = self.policies.get(platform)
        if pol is None or pol.mode != "env":
            return {}
        rec = self._view(pol)
        acct = next((a for a in rec.get("accounts", []) if a.get("name") == name), None)
        if acct is None:
            return {}
        out = resolve_env(acct.get("env", {}), self.environ)
        files = acct.get("files") or {}
        for slot in pol.files:
            if (
                slot.env_var
                and isinstance(files.get(slot.key), str)
                and files[slot.key]
            ):
                out[slot.env_var] = resolve_path(files[slot.key])
        return out

    def active_files(self, platform: str) -> list[FileAction]:
        """Copy actions for the active account's env_var-LESS file slots.

        Slots WITH an ``env_var`` are redirected purely via env (see
        ``active_env``); only slots without one need a physical copy onto the
        backend's fixed path (WhatsApp's ``auth_info/``).
        """
        pol = self.policies.get(platform)
        if pol is None or pol.mode != "env" or not pol.files:
            return []
        acct = self._active_account(pol)
        if acct is None:
            return []
        files = acct.get("files") or {}
        actions: list[FileAction] = []
        for slot in pol.files:
            src = files.get(slot.key)
            if not slot.env_var and isinstance(src, str) and src:
                actions.append(
                    FileAction(slot.key, resolve_path(src), slot.dest, slot.is_dir)
                )
        return actions

    def materialize_files(
        self,
        platform: str,
        copier: "Callable[[str, str, bool], None] | None" = None,
    ) -> dict:
        """Copy the active account's copy-only artifacts onto their fixed paths.

        Called by the hub on switch/cycle before it respawns the backend, so the
        child loads the newly-active account's session. Never raises; returns a
        report of what was copied and any per-slot errors.
        """
        do_copy = copier or copy_artifact
        copied: list[str] = []
        errors: list[dict] = []
        for act in self.active_files(platform):
            if not os.path.exists(act.src):
                errors.append(
                    {
                        "key": act.key,
                        "src": act.src,
                        "error": "source path does not exist",
                    }
                )
                continue
            try:
                do_copy(act.src, act.dest, act.is_dir)
                copied.append(act.key)
            except (OSError, shutil.Error) as exc:
                errors.append({"key": act.key, "error": str(exc)})
        return {"platform": platform, "copied": copied, "errors": errors}

    # ---- cli-mode helpers ------------------------------------------------
    @staticmethod
    def _lines(out: str) -> list[str]:
        return [ln.strip() for ln in out.splitlines() if ln.strip()]

    def _cli_names(self, cli: CliProfileSpec) -> tuple[list[str], str]:
        _rc, out, _err = self.runner(cli.list_cmd)
        _rc2, cur, _err2 = self.runner(cli.current_cmd)
        return self._lines(out), (self._lines(cur)[0] if self._lines(cur) else "")

    @staticmethod
    def _fill(cmd: tuple[str, ...], name: str) -> tuple[str, ...]:
        return tuple(part.replace("{name}", name) for part in cmd)

    # ---- operations ------------------------------------------------------
    def handle(self, platform: str, op: str, arguments: Mapping | None) -> dict:
        """Dispatch one account operation; always returns a result dict."""
        pol = self.policies.get(platform)
        if pol is None:
            return _err(platform, op, f"unknown platform {platform!r}")
        fn = getattr(self, f"_op_{op}", None)
        if fn is None:
            return _err(platform, op, f"unknown account op {op!r}")
        try:
            return fn(pol, dict(arguments or {}))
        except _AccountError as exc:
            return _err(platform, op, str(exc))

    def _op_list(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            names, active = self._cli_names(_require_cli(pol))
            return _ok(pol, "list", accounts=names, active=active, source="cli")
        rec = self._view(pol)
        accts = rec.get("accounts", [])
        return _ok(
            pol,
            "list",
            accounts=[a.get("name") for a in accts],
            labels={
                a["name"]: a["label"] for a in accts if a.get("name") and a.get("label")
            },
            active=rec.get("active"),
            source="store",
        )

    def _op_current(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            _rc, out, _err = self.runner(_require_cli(pol).current_cmd)
            lines = self._lines(out)
            return _ok(
                pol, "current", active=(lines[0] if lines else None), source="cli"
            )
        rec = self._view(pol)
        active = rec.get("active")
        acct = next(
            (a for a in rec.get("accounts", []) if a.get("name") == active), None
        )
        keys = sorted((acct or {}).get("env", {}))
        file_keys = sorted((acct or {}).get("files", {}))
        return _ok(
            pol,
            "current",
            active=active,
            label=(acct or {}).get("label"),
            env_keys=keys,
            file_keys=file_keys,
            source="store",
        )

    def _op_add(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            if not cli.add_cmd:
                raise _AccountError(
                    f"add is not supported for {pol.platform}; {cli.add_hint}"
                )
            rc, out, err = self.runner(self._fill(cli.add_cmd, name))
            return _cli_result(pol, "add", rc, out, err, name=name)
        env = args.get("env") or {}
        files = args.get("files") or {}
        if not isinstance(env, dict):
            raise _AccountError("'env' must be an object of str->str")
        if not isinstance(files, dict):
            raise _AccountError("'files' must be an object of slot->path")
        if not env and not files:
            raise _AccountError("provide a non-empty 'env' bundle and/or a 'files' map")
        known = {s.key for s in pol.files}
        unknown = [k for k in files if k not in known]
        if unknown:
            raise _AccountError(
                f"unknown file slot(s) {unknown}; valid: {sorted(known) or 'none'}"
            )
        rec = self._materialize(pol)
        if any(a.get("name") == name for a in rec["accounts"]):
            raise _AccountError(f"account {name!r} already exists")
        entry = {"name": name, "env": {str(k): str(v) for k, v in env.items()}}
        if files:
            entry["files"] = {str(k): str(v) for k, v in files.items()}
        label = args.get("label")
        if isinstance(label, str) and label.strip():
            entry["label"] = label.strip()
        rec["accounts"].append(entry)
        if not rec.get("active"):
            rec["active"] = name
        self._persist()
        return _ok(pol, "add", added=name, active=rec["active"])

    def _op_remove(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            if not cli.remove_cmd:
                raise _AccountError(
                    f"remove is not supported for {pol.platform}; {cli.remove_hint}"
                )
            rc, out, err = self.runner(self._fill(cli.remove_cmd, name))
            return _cli_result(pol, "remove", rc, out, err, name=name)
        rec = self._materialize(pol)
        keep = [a for a in rec["accounts"] if a.get("name") != name]
        if len(keep) == len(rec["accounts"]):
            raise _AccountError(f"no such account {name!r}")
        rec["accounts"] = keep
        if rec.get("active") == name:
            rec["active"] = keep[0]["name"] if keep else None
        self._persist()
        return _ok(pol, "remove", removed=name, active=rec.get("active"))

    def _op_switch(self, pol: AccountPolicy, args: dict) -> dict:
        name = _need_name(args)
        if pol.mode == "cli":
            cli = _require_cli(pol)
            rc, out, err = self.runner(self._fill(cli.activate_cmd, name))
            res = _cli_result(pol, "switch", rc, out, err, active=name)
            res["respawn"] = res["ok"]
            return res
        rec = self._materialize(pol)
        if not any(a.get("name") == name for a in rec["accounts"]):
            raise _AccountError(f"no such account {name!r}")
        rec["active"] = name
        self._persist()
        return _ok(pol, "switch", active=name, respawn=True)

    def _op_cycle(self, pol: AccountPolicy, _args: dict) -> dict:
        if pol.mode == "cli":
            cli = _require_cli(pol)
            names, active = self._cli_names(cli)
            nxt = _next_name(names, active)
            rc, out, err = self.runner(self._fill(cli.activate_cmd, nxt))
            res = _cli_result(pol, "cycle", rc, out, err, active=nxt, previous=active)
            res["respawn"] = res["ok"]
            return res
        rec = self._materialize(pol)
        names = [a.get("name") for a in rec["accounts"]]
        nxt = _next_name(names, rec.get("active"))
        rec["active"] = nxt
        self._persist()
        return _ok(pol, "cycle", active=nxt, respawn=True)


class _AccountError(Exception):
    """A user-facing account-operation failure (surfaced as a tool error)."""


def _need_name(args: dict) -> str:
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _AccountError("'name' is required")
    return name.strip()


def _require_cli(pol: AccountPolicy) -> CliProfileSpec:
    if pol.cli is None:
        raise _AccountError(f"{pol.platform} has no CLI profile spec")
    return pol.cli


def _next_name(names: list[str], active: str | None) -> str:
    if not names:
        raise _AccountError("no accounts to cycle through")
    try:
        idx = names.index(active) if active in names else -1
    except ValueError:
        idx = -1
    return names[(idx + 1) % len(names)]


def _ok(pol: AccountPolicy, op: str, **extra) -> dict:
    return {"ok": True, "platform": pol.platform, "mode": pol.mode, "op": op, **extra}


def _err(platform: str, op: str, message: str) -> dict:
    return {"ok": False, "platform": platform, "op": op, "error": message}


def _cli_result(
    pol: AccountPolicy, op: str, rc: int, out: str, err: str, **extra
) -> dict:
    res = (
        _ok(pol, op, **extra)
        if rc == 0
        else _err(pol.platform, op, (err or out).strip() or f"CLI exited {rc}")
    )
    res["source"] = "cli"
    if out.strip():
        res["stdout"] = out.strip()[:2000]
    return res
