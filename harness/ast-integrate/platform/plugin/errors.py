"""Error taxonomy, the CLI exit-code contract, and the user-facing message renderer.

One stable code per failure class (IMP-0051), one exit code per class (IMP-0055), and every
message carries cause / impact / the exact next command (IMP-0052). Codes are part of the
published contract: they may be added, never renumbered.

The taxonomy is data, not prose, so ``schemas.ERROR_TAXONOMY_SCHEMA`` can validate an emitted
taxonomy document and ``test_errors.py`` can assert the invariants (unique codes, unique exit
codes, every field populated, every ``next_command`` a real subcommand).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

EXIT_OK = 0
EXIT_USAGE = 2


@dataclass(frozen=True)
class ErrorClass:
    """One row of the published error taxonomy."""

    code: str
    exit_code: int
    title: str
    cause: str
    impact: str
    next_command: str
    fail_mode: str  # "fail-closed" | "fail-open"

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "exit_code": self.exit_code,
            "title": self.title,
            "cause": self.cause,
            "impact": self.impact,
            "next_command": self.next_command,
            "fail_mode": self.fail_mode,
        }


#: The taxonomy. Ordered by exit code so the table reads as the contract it is.
TAXONOMY: tuple[ErrorClass, ...] = (
    ErrorClass(
        "E_USAGE",
        2,
        "Command usage error",
        "The command line did not parse, or a required argument was missing.",
        "Nothing was read and nothing was written.",
        "astplugin --help",
        "fail-closed",
    ),
    ErrorClass(
        "E_MANIFEST",
        10,
        "Manifest rejected by the strict parser",
        "plugin.json is missing a required field, carries an unknown field outside the "
        "reserved 'x-' namespace, or declares two keys that differ only by case.",
        "The package is not installable; no file was staged.",
        "astplugin conform --package <zip>",
        "fail-closed",
    ),
    ErrorClass(
        "E_PAYLOAD",
        11,
        "Payload violates the include allowlist",
        "A staged path is not matched by the deny-by-default allowlist, or matches a "
        "forbidden pattern (.git, caches, logs, transcripts).",
        "No archive was written.",
        "astplugin build --explain-payload",
        "fail-closed",
    ),
    ErrorClass(
        "E_SECRET",
        12,
        "Credential-shaped content found in the payload",
        "The deny-by-default secret gate matched high-entropy or key-shaped content in a "
        "file that was about to be shipped.",
        "No archive was written. The finding names the file and the offset, never the value.",
        "astplugin build --report-secrets <path>",
        "fail-closed",
    ),
    ErrorClass(
        "E_BUDGET",
        13,
        "Package exceeds its size or file-count budget",
        "The staged payload is larger than the declared budget, which is how a 2 GB "
        "accident is caught before it ships.",
        "No archive was written.",
        "astplugin build --inventory <path>",
        "fail-closed",
    ),
    ErrorClass(
        "E_PREFLIGHT",
        20,
        "Preflight refused the operation",
        "Insufficient disk space, an unwritable prefix, or a missing parent directory.",
        "Nothing was mutated.",
        "astplugin health-check --prefix <prefix>",
        "fail-closed",
    ),
    ErrorClass(
        "E_LOCK",
        21,
        "Another lifecycle operation holds the prefix lock",
        "A concurrent install/update/rollback/uninstall is in progress, or a previous run "
        "died holding the lock.",
        "Nothing was mutated.",
        "astplugin health-check --prefix <prefix>",
        "fail-closed",
    ),
    ErrorClass(
        "E_TXN",
        22,
        "Transaction failed and was rolled back",
        "A staged step raised after the journal opened; the inverse of every applied step "
        "was replayed.",
        "The prefix is back at its pre-operation state. No partial install remains.",
        "astplugin health-check --prefix <prefix>",
        "fail-closed",
    ),
    ErrorClass(
        "E_DRIFT",
        30,
        "Diverged file needs an owner decision",
        "Live and repo both hold unique content for the same path, so neither side can be "
        "overwritten without losing something.",
        "The file was left untouched and a decision packet was written.",
        "astplugin sync --prefix <prefix> --decisions <path>",
        "fail-closed",
    ),
    ErrorClass(
        "E_CACHE",
        40,
        "Cache entry corrupted or unreadable",
        "A content-addressed entry does not hash to its own key.",
        "The entry was quarantined; the operation continues from source.",
        "astplugin cache --prefix <prefix> --invalidate",
        "fail-open",
    ),
    ErrorClass(
        "E_HEALTH",
        50,
        "Health check reported a failing probe",
        "At least one registered probe returned FAIL.",
        "Nothing was mutated. The report names each probe and its remediating command.",
        "astplugin doctor --prefix <prefix>",
        "fail-closed",
    ),
    ErrorClass(
        "E_CONFORM",
        51,
        "Conformance validator rejected the package",
        "The package violates the plugin contract (manifest, interpreters, layout, or "
        "schema of an emitted artifact).",
        "The package is not publishable.",
        "astplugin conform --package <zip> --json <path>",
        "fail-closed",
    ),
    ErrorClass(
        "E_MIGRATE",
        60,
        "Migration from an old layout failed",
        "A migration step raised, or a legacy fingerprint matched two mutually exclusive "
        "layouts.",
        "The ledger holds the inverse of every applied step; nothing is half-migrated.",
        "astplugin migrate --prefix <prefix> --dry-run",
        "fail-closed",
    ),
    ErrorClass(
        "E_COMPAT",
        70,
        "Client, OS, or shell is not supported",
        "The manifest's compatibility range excludes the detected client version, or the "
        "platform has no launch adapter.",
        "Nothing was mutated.",
        "astplugin diagnose",
        "fail-closed",
    ),
    ErrorClass(
        "E_INTERP",
        80,
        "Declared interpreter missing or below its version floor",
        "A script entrypoint names an interpreter that is absent from PATH or older than "
        "the declared floor.",
        "Nothing was mutated. Scripts are never run through an inferred interpreter.",
        "astplugin diagnose --json <path>",
        "fail-closed",
    ),
    ErrorClass(
        "E_IO",
        90,
        "Filesystem operation refused",
        "A path escaped its root, used a reserved device name, or exceeded the platform "
        "path limit.",
        "Nothing was written at that path.",
        "astplugin health-check --prefix <prefix>",
        "fail-closed",
    ),
)

BY_CODE: dict[str, ErrorClass] = {e.code: e for e in TAXONOMY}


class PluginError(Exception):
    """A classified, renderable failure. Never raised without a taxonomy code."""

    def __init__(
        self, code: str, detail: str, *, context: dict[str, object] | None = None
    ) -> None:
        if code not in BY_CODE:
            raise KeyError(f"unknown error code {code!r}: the taxonomy is closed")
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.context: dict[str, object] = dict(context or {})

    @property
    def klass(self) -> ErrorClass:
        return BY_CODE[self.code]

    @property
    def exit_code(self) -> int:
        return self.klass.exit_code

    def render(self, op: str, *, next_command: str | None = None) -> str:
        """Render the user-facing block: what happened, what it means, what to run next."""
        k = self.klass
        lines = [
            f"FAILED:{op} {k.code} {k.title}",
            f"  what happened : {self.detail}",
            f"  cause         : {k.cause}",
            f"  impact        : {k.impact}",
            f"  next command  : {next_command or k.next_command}",
            f"  exit code     : {k.exit_code} ({k.fail_mode})",
        ]
        for key in sorted(self.context):
            lines.append(f"  {key:<14}: {self.context[key]}")
        return "\n".join(lines)


def taxonomy_document() -> dict[str, object]:
    """The taxonomy as a validatable artifact (tools/plugin/schema/error-taxonomy.schema.json)."""
    return {
        "artifact": "error-taxonomy",
        "version": 1,
        "classes": [e.as_dict() for e in TAXONOMY],
    }


def emit_failure(err: PluginError, op: str, *, stream: TextIO | None = None) -> int:
    """Print the rendered block to stderr and return the exit code. Never swallows."""
    print(err.render(op), file=stream or sys.stderr)
    return err.exit_code
