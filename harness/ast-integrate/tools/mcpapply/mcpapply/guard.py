"""Fail-CLOSED preconditions for a write.

Two gates, both returning a REFUSAL STRING (empty means "go ahead"):

* :func:`running_host_refusal` -- the host application rewrites ``~/.claude.json``
  continuously, so writing it while sessions are live races them. Every other
  MCP-config writer in this repo refuses under the same condition
  (``tools/mcp/closed-batch/apply_closed_batch.py``,
  ``tools/mcp/linkedin-mcp/apply_linkedin_userscope.py``,
  ``hooks/mcp-userscope-sync/promote-mcp-userscope.ps1``); this package matches them
  rather than being the one tool that silently races.
* :func:`user_scope_promotion_refusal` -- promotion of MCP config to USER scope is a
  recorded HUMAN gate ("requires Claude to be CLOSED"). It is surfaced as a required
  human step and is never auto-satisfied. Passing ``--force`` does not bypass it;
  only the operator actually closing the host does.

**Fail-closed** means the probe's own failure is a refusal, not a pass. A process
listing that errors tells us nothing about whether the host is running, and "we could
not check, so we wrote anyway" is the failure mode that corrupts a profile.

The process listing is an injected PORT (``runner``). The production default shells
out once; the tests drive both a fake runner and the real one against a short-lived
Python child, so the default is proven rather than merely seamed around.
"""

from __future__ import annotations

import subprocess  # noqa: S404 -- process listing is this module's entire purpose.
import sys
from collections.abc import Callable, Sequence

__all__ = [
    "HOST_PROCESS_NAMES",
    "Runner",
    "default_runner",
    "make_guard",
    "running_host_refusal",
    "user_scope_promotion_refusal",
]

#: Process names that mean "a host session is live". ``claude.exe`` is the packaged
#: Bun build on this box; ``claude`` covers the POSIX/WSL form; ``node`` alone is NOT
#: included because it would refuse on any unrelated Node process.
HOST_PROCESS_NAMES: tuple[str, ...] = ("claude.exe", "claude")

Runner = Callable[[Sequence[str]], str]

_LIST_ARGV_WINDOWS: tuple[str, ...] = ("tasklist", "/FO", "CSV", "/NH")
_LIST_ARGV_POSIX: tuple[str, ...] = ("ps", "-eo", "comm=")


def default_runner(argv: Sequence[str]) -> str:
    """Run ``argv`` and return its stdout. Raises on failure -- the caller fails closed."""
    completed = subprocess.run(  # noqa: S603 -- argv is a module constant, never user text.
        list(argv),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return completed.stdout


def list_argv(os_name: str) -> tuple[str, ...]:
    """The process-listing command for ``os_name`` (``os.name``)."""
    return _LIST_ARGV_WINDOWS if os_name == "nt" else _LIST_ARGV_POSIX


def _names_in(listing: str) -> set[str]:
    """Extract lowercase process names from a tasklist-CSV or ``ps comm=`` listing."""
    found: set[str] = set()
    for line in listing.splitlines():
        text = line.strip()
        if not text:
            continue
        first = text.split(",")[0].strip('" ') if text.startswith('"') else text
        found.add(first.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower())
    return found


def running_host_refusal(*, os_name: str, runner: Runner, force: bool = False) -> str:
    """``""`` when it is safe to write; otherwise the reason to refuse.

    ``force`` is an explicit operator override for the LIVE-SESSION check only. It
    does NOT override :func:`user_scope_promotion_refusal`.
    """
    try:
        listing = runner(list_argv(os_name))
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            f"could not enumerate processes ({type(exc).__name__}: {exc}); FAILING "
            "CLOSED -- an unverifiable host state is treated as 'running'"
        )
    live = sorted(_names_in(listing) & {n.lower() for n in HOST_PROCESS_NAMES})
    if not live:
        return ""
    if force:
        return ""
    return (
        f"a host session is running ({', '.join(live)}) and rewrites the MCP config "
        "continuously; close every Claude Code window, or pass --force to accept the "
        "race"
    )


def user_scope_promotion_refusal(
    *, touches_user_scope: bool, host_running: bool
) -> str:
    """The recorded human gate for USER-scope promotion. Never auto-satisfied."""
    if touches_user_scope and host_running:
        return (
            "promoting MCP configuration to USER scope requires the host to be CLOSED. "
            "This is a HUMAN step: close every Claude Code window and re-run. This tool "
            "will not fake, bypass, or auto-satisfy it, and --force does not apply here."
        )
    return ""


def make_guard(
    *,
    os_name: str = "",
    runner: Runner | None = None,
    force: bool = False,
    touches_user_scope: bool = False,
) -> Callable[[], str]:
    """Compose the guards into the single callable :func:`~mcpapply.apply.apply_plan` wants."""
    resolved_os = os_name or ("nt" if sys.platform.startswith("win") else "posix")
    resolved_runner = default_runner if runner is None else runner

    def _guard() -> str:
        try:
            listing = resolved_runner(list_argv(resolved_os))
            host_running = bool(
                _names_in(listing) & {n.lower() for n in HOST_PROCESS_NAMES}
            )
        except (OSError, subprocess.SubprocessError):
            host_running = True
        promotion = user_scope_promotion_refusal(
            touches_user_scope=touches_user_scope, host_running=host_running
        )
        if promotion:
            return promotion
        return running_host_refusal(
            os_name=resolved_os, runner=resolved_runner, force=force
        )

    return _guard
