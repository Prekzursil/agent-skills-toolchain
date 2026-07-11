#!/usr/bin/env python3
"""codex-fleet-github core -- pure dispatch/sweep/status/orchestrate logic (no MCP dep).

Drives the Wave-1 private Codex runner (``codex-runner.yml`` in
``Prekzursil/agent-skills-toolchain``) which holds the ChatGPT-subscription
``auth.json``. THIS layer never touches auth.json: it only *triggers* runs with a
scoped dispatch token (``CODEX_DISPATCH_PAT`` / ``GH_TOKEN`` / keyring) via the
GitHub CLI, exactly like the shared Wave-2 dispatch contract::

    gh workflow run codex-runner.yml --repo Prekzursil/agent-skills-toolchain \
        --ref main -f target_repo=<repo> -f task=<task> -f model=<model> \
        -f effort=<effort> -f max_changed_files=<n>

Every function is dependency-injectable (``runner=run_gh``) so the whole surface
is unit-testable without a live ``gh`` or the network. ``run_gh`` is the ONE
subprocess site; it never uses a shell and passes the token via the child env
(never on argv, never logged). Propose-only: the runner opens DRAFT PRs and
nothing here merges.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime

# --- constants -------------------------------------------------------------- #
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_EFFORT = "max"
DEFAULT_MAX_CHANGED_FILES = 40
EFFORT_ALLOWLIST = ("minimal", "low", "medium", "high", "xhigh", "max", "ultra")

MAX_TASK_LEN = 20000
MAX_PLAN_LEN = 40000
_RUN_MATCH_SKEW_S = 90.0  # tolerate local/GitHub clock skew when matching a run

_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
# Parity with the runner's validate step: alnum-led, then alnum/dot/dash/underscore.
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")

# The runner opens PRs with this label / head-branch prefix / title (see
# codex-runner.yml). Its unlabeled fallback path still uses the branch + title.
PR_LABEL = "codex-runner"
PR_BRANCH_PREFIX = "codex/"
PR_TITLE = "Codex: automated change"

# Built-in fleet catalogue: the 26 owned non-fork repos. This is NOT an
# auto-fallback -- resolve_fleet_repos() is FAIL-CLOSED and will only use these
# rows when the operator explicitly opts in (CODEX_FLEET_ALLOW_FALLBACK). Even
# then, ONLY the 4 curated PUBLIC repos are enabled; every PRIVATE repo and every
# non-curated public repo is DISABLED here so an accidental fan-out cannot reach
# private code, secrets, or payment/auth surfaces.
#
# ENABLED = the 4 curated public targets vetted for autonomous Codex changes.
_FLEET_ENABLED = (
    "Reframe",
    "env-inspector",
    "omniaudit-mcp",
    "WebCoder",
)
# DISABLED = everything else: the 8 private repos (never fan out to private
# code/secrets), momentstudio (payment/auth), and all non-curated public repos.
_FLEET_DISABLED = (
    # --- private repos (fail-closed: never auto-dispatched) ---
    "agent-skills-toolchain",
    "RESEARCH-noosphere-atlas-lyceum",
    "security-kb",
    "opusClip-bulk-downloader",
    "consiliere-ocr-pipeline",
    "battlecats-toolkit",
    "verdict-app",
    "yourfreedom-autocode",
    # --- payment/auth surface (extra caution) ---
    "momentstudio",
    # --- non-curated public repos (not vetted for autonomous changes) ---
    "quality-zero-platform",
    "bilbo-app",
    "abbyy-finereader-ocr-mcp",
    "DevExtreme-Filter-Go-Language",
    "codex-session-manager",
    "SWFOC-Mod-Menu",
    "grace-iberlef-2026",
    "codeblocks-pretty-prints-stable",
    "TanksFlashMobile",
    "Airline-Reservations-System",
    "Personal-Finance-Management",
    "Star-Wars-Galactic-Battlegrounds-Save-Game-Editor",
    "pbinfo-scrape",
)


class FleetError(ValueError):
    """Raised for invalid inputs or unrecoverable dispatch/query failures."""


# --- config accessors (env-overridable; read at call time) ------------------ #
def _env(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val.strip() if isinstance(val, str) and val.strip() else default


def runner_repo() -> str:
    """The PRIVATE runner repo that holds auth.json (dispatch target)."""
    return _env("CODEX_RUNNER_REPO", "Prekzursil/agent-skills-toolchain")


def runner_workflow() -> str:
    return _env("CODEX_RUNNER_WORKFLOW", "codex-runner.yml")


def runner_ref() -> str:
    """Ref the workflow is dispatched on (must contain the workflow file)."""
    return _env("CODEX_RUNNER_REF", "main")


def qzt_repo() -> str:
    """The PUBLIC control-plane repo that hosts codex-targets.yml."""
    return _env("CODEX_QZT_REPO", "Prekzursil/quality-zero-platform")


def fleet_owner() -> str:
    return _env("CODEX_FLEET_OWNER", runner_repo().split("/", 1)[0])


def gh_bin() -> str:
    return _env("CODEX_GH_BIN", "gh")


def actions_url() -> str:
    return f"https://github.com/{runner_repo()}/actions/workflows/{runner_workflow()}"


def targets_paths() -> tuple[str, ...]:
    """Candidate paths for codex-targets.yml inside the QZT repo (root or .github)."""
    override = os.environ.get("CODEX_TARGETS_PATH")
    if override and override.strip():
        return (override.strip(),)
    return ("codex-targets.yml", ".github/codex-targets.yml")


def default_fleet() -> list[dict]:
    """The built-in fleet catalogue as [{repo, enabled}] (26 repos: 4 enabled).

    Only the 4 curated PUBLIC repos are enabled; every private/non-curated repo is
    disabled. Never auto-used -- resolve_fleet_repos() is fail-closed and only
    consults this catalogue when CODEX_FLEET_ALLOW_FALLBACK is set.
    """
    owner = fleet_owner()
    rows = [{"repo": f"{owner}/{name}", "enabled": True} for name in _FLEET_ENABLED]
    rows += [{"repo": f"{owner}/{name}", "enabled": False} for name in _FLEET_DISABLED]
    return rows


# --- input validation (system boundary) ------------------------------------- #
def validate_repo(repo: object) -> str:
    if not isinstance(repo, str):
        raise FleetError(f"repo must be a string, got {type(repo).__name__}")
    value = repo.strip()
    segments = value.split("/")
    bad_segment = any(
        not seg or seg.startswith("-") or seg in (".", "..") for seg in segments
    )
    if not _REPO_RE.match(value) or bad_segment:
        raise FleetError(f"invalid repo (want 'owner/name'): {repo!r}")
    return value


def validate_task(
    task: object, *, field: str = "task", limit: int = MAX_TASK_LEN
) -> str:
    if not isinstance(task, str) or not task.strip():
        raise FleetError(f"{field} must be a non-empty string")
    if "\x00" in task:
        raise FleetError(f"{field} contains a NUL byte")
    if len(task) > limit:
        raise FleetError(f"{field} too long ({len(task)} > {limit} chars)")
    return task


def validate_model(model: object) -> str:
    if model is None or (isinstance(model, str) and not model.strip()):
        return DEFAULT_MODEL
    if not isinstance(model, str) or not _MODEL_RE.match(model.strip()):
        raise FleetError(f"invalid model slug: {model!r}")
    return model.strip()


def validate_effort(effort: object) -> str:
    if effort is None or (isinstance(effort, str) and not effort.strip()):
        return DEFAULT_EFFORT
    value = effort.strip().lower() if isinstance(effort, str) else str(effort)
    if value not in EFFORT_ALLOWLIST:
        raise FleetError(
            f"invalid effort {effort!r}; allowed: {', '.join(EFFORT_ALLOWLIST)}"
        )
    return value


def validate_max_changed_files(value: object) -> int:
    if value in (None, "", 0):
        return DEFAULT_MAX_CHANGED_FILES
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise FleetError(f"max_changed_files must be an integer: {value!r}") from exc
    if number < 1 or number > 1000:
        raise FleetError(f"max_changed_files out of range (1..1000): {number}")
    return number


def validate_base_branch(branch: object) -> str:
    if branch is None or (isinstance(branch, str) and not branch.strip()):
        return ""
    if not isinstance(branch, str):
        raise FleetError(f"base_branch must be a string: {branch!r}")
    value = branch.strip()
    if value.startswith("-") or ".." in value or not _REF_RE.match(value):
        raise FleetError(f"invalid base_branch: {branch!r}")
    return value


# --- dispatch token (never auth.json) --------------------------------------- #
def _keyring_lookup(service: str, user: str) -> str:
    try:
        import keyring

        return keyring.get_password(service, user) or ""
    except Exception:
        return ""


def dispatch_token(
    environ: dict | None = None, *, keyring_lookup=_keyring_lookup
) -> str:
    """Resolve the scoped dispatch token; NEVER the runner's auth.json.

    Order: CODEX_DISPATCH_PAT -> GH_TOKEN -> GITHUB_TOKEN -> keyring
    (service 'codex-fleet-github', user 'dispatch'). An empty string means "let gh
    use its own ambient auth (gh auth login)". The token is never returned to a
    tool caller and never written to argv or logs.
    """
    environ = os.environ if environ is None else environ
    for name in ("CODEX_DISPATCH_PAT", "GH_TOKEN", "GITHUB_TOKEN"):
        val = environ.get(name)
        if isinstance(val, str) and val.strip():
            return val.strip()
    try:
        return (keyring_lookup("codex-fleet-github", "dispatch") or "").strip()
    except Exception:
        return ""


# --- the single subprocess chokepoint --------------------------------------- #
def run_gh(
    args: list[str], token: str = "", timeout: float = 120.0
) -> tuple[int, str, str]:
    """The ONLY subprocess site. Runs ``gh <args>`` with no shell.

    The token is injected into the CHILD environment (GH_TOKEN/GITHUB_TOKEN),
    never placed on argv and never logged. Returns (returncode, stdout, stderr).
    """
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    try:
        proc = subprocess.run(
            [gh_bin(), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except FileNotFoundError:
        return 127, "", "gh CLI not found (install GitHub CLI or set CODEX_GH_BIN)"
    except subprocess.TimeoutExpired:
        return 124, "", f"gh timed out after {timeout}s"
    return proc.returncode, proc.stdout, proc.stderr


def build_dispatch_args(
    repo: str,
    task: str,
    model: str,
    effort: str,
    max_changed_files: int,
    base_branch: str = "",
) -> list[str]:
    """The shared dispatch call as an argv list (validated values only)."""
    args = [
        "workflow",
        "run",
        runner_workflow(),
        "--repo",
        runner_repo(),
        "--ref",
        runner_ref(),
        "-f",
        f"target_repo={repo}",
        "-f",
        f"task={task}",
        "-f",
        f"model={model}",
        "-f",
        f"effort={effort}",
        "-f",
        f"max_changed_files={max_changed_files}",
    ]
    if base_branch:
        args += ["-f", f"base_branch={base_branch}"]
    return args


# --- run-URL resolution (best-effort; workflow_dispatch returns no id) ------- #
def _safe_json_list(text: str) -> list:
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _iso_to_epoch(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _newest_since(runs: list[dict], since_epoch: float) -> dict | None:
    fresh = []
    for run in runs:
        created = _iso_to_epoch(run.get("createdAt"))
        if created is not None and created >= since_epoch - _RUN_MATCH_SKEW_S:
            fresh.append((created, run))
    if not fresh:
        return None
    fresh.sort(key=lambda item: item[0], reverse=True)
    return fresh[0][1]


def find_recent_run(
    since_epoch: float,
    *,
    token: str = "",
    runner=run_gh,
    attempts: int = 4,
    delay: float = 1.5,
    sleep=time.sleep,
) -> dict | None:
    """Best-effort: newest workflow_dispatch run created at/after ``since_epoch``.

    ``workflow_dispatch`` returns no run id, so this polls ``gh run list`` a few
    times and matches by creation time. It cannot distinguish concurrent
    dispatches to different targets -- treat the URL as the most likely run, not
    a guarantee.
    """
    args = [
        "run",
        "list",
        "--repo",
        runner_repo(),
        "--workflow",
        runner_workflow(),
        "--event",
        "workflow_dispatch",
        "--json",
        "databaseId,url,status,conclusion,createdAt,displayTitle",
        "-L",
        "12",
    ]
    for attempt in range(max(1, attempts)):
        code, out, _err = runner(args, token)
        if code == 0:
            candidate = _newest_since(_safe_json_list(out), since_epoch)
            if candidate:
                return candidate
        if attempt < attempts - 1:
            sleep(delay)
    return None


# --- single dispatch -------------------------------------------------------- #
def dispatch_one(
    repo: str,
    task: str,
    *,
    model: str = "",
    effort: str = "",
    max_changed_files: object = None,
    base_branch: str = "",
    token: str | None = None,
    runner=run_gh,
    resolve_url: bool = True,
    now=time.time,
) -> dict:
    """Trigger ONE runner dispatch for ``repo`` and return a status dict."""
    repo = validate_repo(repo)
    task = validate_task(task)
    model = validate_model(model)
    effort = validate_effort(effort)
    max_files = validate_max_changed_files(max_changed_files)
    base = validate_base_branch(base_branch)
    tok = dispatch_token() if token is None else token
    args = build_dispatch_args(repo, task, model, effort, max_files, base)
    started = now()
    code, out, err = runner(args, tok)
    result: dict = {
        "ok": code == 0,
        "repo": repo,
        "runner_repo": runner_repo(),
        "workflow": runner_workflow(),
        "ref": runner_ref(),
        "model": model,
        "effort": effort,
        "max_changed_files": max_files,
        "actions_url": actions_url(),
    }
    if base:
        result["base_branch"] = base
    if code != 0:
        result["error"] = (err or out or "gh workflow run failed").strip()
        return result
    if resolve_url:
        run = find_recent_run(started, token=tok, runner=runner)
        if run:
            result["run_url"] = run.get("url")
            result["run_id"] = run.get("databaseId")
            result["run_status"] = run.get("status")
    result["note"] = (
        "Dispatched (propose-only): the runner opens a DRAFT PR on the target. "
        "Runs serialize via the 'codex-runner' concurrency group. run_url is "
        "best-effort (workflow_dispatch returns no id) -- use fleet_status if absent."
    )
    return result


# --- codex-targets.yml (fleet source of truth) ------------------------------ #
def load_targets_text(
    *, token: str | None = None, runner=run_gh, environ: dict | None = None
) -> tuple[str, str]:
    """Return (yaml_text, source). Local CODEX_TARGETS_FILE first, else QZT via gh."""
    environ = os.environ if environ is None else environ
    local = environ.get("CODEX_TARGETS_FILE")
    if local and local.strip():
        path = os.path.expanduser(local.strip())
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read(), f"file:{path}"
        except OSError as exc:
            raise FleetError(f"cannot read CODEX_TARGETS_FILE {path}: {exc}") from exc
    tok = dispatch_token(environ) if token is None else token
    for path in targets_paths():
        code, out, _err = runner(
            [
                "api",
                "-H",
                "Accept: application/vnd.github.raw",
                f"repos/{qzt_repo()}/contents/{path}",
            ],
            tok,
        )
        if code == 0 and out.strip():
            return out, f"{qzt_repo()}:{path}"
    raise FleetError(
        "could not load codex-targets.yml (set CODEX_TARGETS_FILE or ensure "
        f"{qzt_repo()} has codex-targets.yml)"
    )


def parse_targets(text: str) -> dict:
    """Parse codex-targets.yml into {'defaults': {...}, 'targets': [...]}."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover -- declared dependency
        raise FleetError("PyYAML is required to parse codex-targets.yml") from exc
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise FleetError(f"invalid codex-targets.yml: {exc}") from exc
    if not isinstance(data, dict):
        raise FleetError("codex-targets.yml must be a mapping")
    defaults = data.get("defaults")
    targets = data.get("targets")
    return {
        "defaults": defaults if isinstance(defaults, dict) else {},
        "targets": targets if isinstance(targets, list) else [],
    }


def enabled_targets(parsed: dict) -> list[dict]:
    """Enabled target rows as [{repo, tasks, max_changed_files}]."""
    rows = []
    for entry in parsed.get("targets") or []:
        if not isinstance(entry, dict) or not entry.get("enabled"):
            continue
        repo = entry.get("repo")
        if not isinstance(repo, str) or not repo.strip():
            continue
        rows.append(
            {
                "repo": repo.strip(),
                "tasks": entry.get("tasks") or [],
                "max_changed_files": entry.get("max_changed_files"),
            }
        )
    return rows


_FALLBACK_OPT_IN = ("1", "true", "yes", "on")


def _fallback_allowed(environ: dict) -> bool:
    """Whether the operator has explicitly opted into the built-in fallback fleet."""
    val = environ.get("CODEX_FLEET_ALLOW_FALLBACK")
    return isinstance(val, str) and val.strip().lower() in _FALLBACK_OPT_IN


def resolve_fleet_repos(
    repos: list[str] | None = None,
    *,
    token: str | None = None,
    runner=run_gh,
    environ: dict | None = None,
) -> tuple[list[dict], str, list[str]]:
    """Resolve target repos for a sweep/orchestration (FAIL-CLOSED).

    Explicit ``repos`` win. Otherwise use enabled rows from codex-targets.yml.
    If codex-targets.yml cannot be loaded OR yields zero enabled targets, this
    RAISES ``FleetError`` rather than silently fanning out -- the built-in fleet
    catalogue is only consulted when the operator sets
    ``CODEX_FLEET_ALLOW_FALLBACK`` (and even then only the 4 curated public repos
    are enabled). Returns (rows, source, notes); each row is
    {repo, max_changed_files}.
    """
    environ = os.environ if environ is None else environ
    notes: list[str] = []
    if repos:
        rows = [{"repo": validate_repo(r), "max_changed_files": None} for r in repos]
        return rows, "explicit", notes
    try:
        text, _src = load_targets_text(token=token, runner=runner, environ=environ)
        rows = [
            {
                "repo": validate_repo(row["repo"]),
                "max_changed_files": row.get("max_changed_files"),
            }
            for row in enabled_targets(parse_targets(text))
        ]
        if rows:
            return rows, "codex-targets.yml", notes
        reason = "codex-targets.yml has no enabled targets"
    except FleetError as exc:
        reason = f"codex-targets.yml unavailable ({exc})"
    if _fallback_allowed(environ):
        notes.append(
            f"{reason}; using built-in curated fallback "
            "(CODEX_FLEET_ALLOW_FALLBACK is set)"
        )
        rows = [
            {"repo": row["repo"], "max_changed_files": None}
            for row in default_fleet()
            if row["enabled"]
        ]
        return rows, "builtin-fallback", notes
    raise FleetError(
        f"{reason}. Refusing to fan out to the built-in fleet (fail-closed). "
        "Fix codex-targets.yml, pass explicit repos=[...], or set "
        "CODEX_FLEET_ALLOW_FALLBACK=1 to opt into the curated 4-repo fallback."
    )


# --- status: recent runs + open PRs ----------------------------------------- #
def list_recent_runs(
    limit: int = 15, *, token: str | None = None, runner=run_gh
) -> list:
    tok = dispatch_token() if token is None else token
    try:
        capped = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        capped = 15
    code, out, err = runner(
        [
            "run",
            "list",
            "--repo",
            runner_repo(),
            "--workflow",
            runner_workflow(),
            "--json",
            "databaseId,displayTitle,status,conclusion,event,createdAt,url",
            "-L",
            str(capped),
        ],
        tok,
    )
    if code != 0:
        raise FleetError((err or out or "gh run list failed").strip())
    return _safe_json_list(out)


def _search_prs(extra_args: list[str], token: str, runner) -> tuple[list, str]:
    args = [
        "search",
        "prs",
        "--owner",
        fleet_owner(),
        "--state",
        "open",
        "--json",
        "number,title,url,repository,createdAt,author,isDraft,labels",
        "-L",
        "40",
        *extra_args,
    ]
    code, out, err = runner(args, token)
    if code != 0:
        return [], (err or out or "gh search prs failed").strip()
    return _safe_json_list(out), ""


def _pr_key(pr: dict):
    return pr.get("url") or (str(pr.get("repository")), pr.get("number"))


def list_open_prs(*, token: str | None = None, runner=run_gh) -> tuple[list, list[str]]:
    """Open runner PRs across the fleet.

    Matched by the 'codex-runner' label AND, separately, the runner's PR title
    (the runner's unlabeled fallback path omits the label). Results are merged
    and de-duplicated by URL.
    """
    tok = dispatch_token() if token is None else token
    notes: list[str] = []
    found: dict = {}
    passes = (["--label", PR_LABEL], [PR_TITLE, "--match", "title"])
    for extra in passes:
        prs, err = _search_prs(extra, tok, runner)
        if err:
            notes.append(err)
            continue
        for pr in prs:
            found[_pr_key(pr)] = pr
    return list(found.values()), notes


def status(limit: int = 15, *, token: str | None = None, runner=run_gh) -> dict:
    """Assemble recent runner runs + open runner PRs (read-only)."""
    tok = dispatch_token() if token is None else token
    notes: list[str] = []
    try:
        runs = list_recent_runs(limit, token=tok, runner=runner)
    except FleetError as exc:
        runs = []
        notes.append(f"runs unavailable: {exc}")
    prs, pr_notes = list_open_prs(token=tok, runner=runner)
    notes.extend(pr_notes)
    return {
        "ok": True,
        "runner_repo": runner_repo(),
        "workflow": runner_workflow(),
        "recent_runs": runs,
        "open_prs": prs,
        "notes": notes,
        "actions_url": actions_url(),
    }


# --- orchestration: plan -> per-repo tasks ---------------------------------- #
def render_repo_task(plan: str, repo: str) -> str:
    name = repo.split("/", 1)[1] if "/" in repo else repo
    return (
        f"{plan.strip()}\n\n"
        f"Scope: apply this ONLY to the `{name}` repository. Make the smallest "
        "coherent, well-tested change that satisfies the plan and open a "
        "propose-only DRAFT PR. If the plan does not apply here, change nothing "
        "and say so in the PR body."
    )


def decompose_plan(plan: str, repos: list[str]) -> list[dict]:
    """Template decomposition: one concrete task per repo (deterministic).

    A smarter, per-repo-aware decomposition (reading each repo's stack/state to
    tailor the task) is a documented follow-up; this template keeps the tool
    safe and offline.
    """
    plan = validate_task(plan, field="plan", limit=MAX_PLAN_LEN)
    items = []
    for repo in repos:
        valid = validate_repo(repo)
        items.append({"repo": valid, "task": render_repo_task(plan, valid)})
    return items


def sweep(
    task: str,
    repos: list[str] | None = None,
    *,
    model: str = "",
    effort: str = "",
    max_changed_files: object = None,
    token: str | None = None,
    runner=run_gh,
    environ: dict | None = None,
    resolve_url: bool = False,
) -> dict:
    """Dispatch the SAME ``task`` to many repos (default: enabled targets).

    Dispatched sequentially; the runner also serializes every run via its
    'codex-runner' concurrency group. ``resolve_url`` defaults False (a sweep
    would otherwise poll per repo) -- use ``status`` for the links.
    """
    task = validate_task(task)
    tok = dispatch_token(environ) if token is None else token
    rows, source, notes = resolve_fleet_repos(
        repos, token=tok, runner=runner, environ=environ
    )
    dispatches = []
    for row in rows:
        per_repo = max_changed_files
        if per_repo in (None, 0) and row.get("max_changed_files"):
            per_repo = row["max_changed_files"]
        try:
            dispatches.append(
                dispatch_one(
                    row["repo"],
                    task,
                    model=model,
                    effort=effort,
                    max_changed_files=per_repo,
                    token=tok,
                    runner=runner,
                    resolve_url=resolve_url,
                )
            )
        except FleetError as exc:
            dispatches.append({"ok": False, "repo": row["repo"], "error": str(exc)})
    ok = sum(1 for item in dispatches if item.get("ok"))
    return {
        "ok": bool(dispatches) and ok == len(dispatches),
        "task": task,
        "repos_source": source,
        "requested": len(rows),
        "dispatched_ok": ok,
        "notes": notes,
        "dispatches": dispatches,
        "actions_url": actions_url(),
        "hint": "Call fleet_status for run URLs + PR links (dispatch returns no id).",
    }


def orchestrate(
    plan: str,
    repos: list[str] | None = None,
    *,
    dispatch: bool = False,
    model: str = "",
    effort: str = "",
    max_changed_files: object = None,
    token: str | None = None,
    runner=run_gh,
    environ: dict | None = None,
) -> dict:
    """Decompose ``plan`` into per-repo tasks. Safe default: no dispatch."""
    plan = validate_task(plan, field="plan", limit=MAX_PLAN_LEN)
    tok = dispatch_token(environ) if token is None else token
    rows, source, notes = resolve_fleet_repos(
        repos, token=tok, runner=runner, environ=environ
    )
    items = decompose_plan(plan, [row["repo"] for row in rows])
    result: dict = {
        "ok": True,
        "plan": plan,
        "repos_source": source,
        "notes": notes,
        "count": len(items),
        "dispatched": bool(dispatch),
        "items": items,
        "decomposition": (
            "template (one task per repo); smarter per-repo decomposition is a "
            "follow-up"
        ),
    }
    if not dispatch:
        result["hint"] = (
            "Review items, then call again with dispatch=true (or use fleet_sweep)."
        )
        return result
    mcf_by_repo = {row["repo"]: row.get("max_changed_files") for row in rows}
    dispatches = []
    for item in items:
        per_repo = max_changed_files or mcf_by_repo.get(item["repo"])
        try:
            dispatches.append(
                dispatch_one(
                    item["repo"],
                    item["task"],
                    model=model,
                    effort=effort,
                    max_changed_files=per_repo,
                    token=tok,
                    runner=runner,
                    resolve_url=False,
                )
            )
        except FleetError as exc:
            dispatches.append({"ok": False, "repo": item["repo"], "error": str(exc)})
    result["dispatches"] = dispatches
    result["dispatched_ok"] = sum(1 for item in dispatches if item.get("ok"))
    result["actions_url"] = actions_url()
    return result
