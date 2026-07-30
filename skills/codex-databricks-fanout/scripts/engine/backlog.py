"""R5: untrusted issue/PR text never drives privileged action. Parse only allowlisted STRUCTURED
fields; free text is discarded. Write-capable units require an owner-authored entry.

Scope of "hardened" (the commit-message claim, scoped): `_touches_workflows` normalizes a Windows
separator, a leading `./` and a trailing `/`, and `ingest_issue` type-checks `changed_paths` — the one
field the workflow guard reads. It is NOT a general schema validator: no other field's type is
checked, so a bare `str` in `labels`/`failing_checks` still explodes into single characters under
`list()`. That is cosmetic (no guard reads those fields) but it is not validated either."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacklogItem:
    labels: list[str]
    changed_paths: list[str]
    failing_checks: list[str]
    write_capable: bool
    directive: str | None = None  # ALWAYS None from issue/PR text


def _touches_workflows(path: str) -> bool:
    norm = (
        path.replace("\\", "/").removeprefix("./").rstrip("/")
    )  # removeprefix, NOT lstrip (lstrip is a charset strip -> eats .github's dot)
    return norm == ".github/workflows" or norm.startswith(".github/workflows/")


def ingest_issue(fields: dict) -> "BacklogItem | None":
    raw = fields.get("changed_paths") or []
    if not isinstance(raw, list):
        # A bare `str` char-EXPLODES under list(), so `_touches_workflows` sees single characters,
        # matches nothing, and a workflow edit is ACCEPTED and write_capable — the combination design
        # R5 forbids. RAISE rather than coerce: `None` already means "policy-rejected", so reusing it
        # would hide a caller bug, and splitting a str would be inventing input the caller never sent.
        # A tuple/set is rejected too — the allowlist is the shape this guard is tested against.
        raise TypeError(f"changed_paths must be a list, got {type(raw).__name__}")
    changed = list(raw)
    if any(_touches_workflows(p) for p in changed):
        return None
    return BacklogItem(
        labels=list(fields.get("labels") or []),
        changed_paths=changed,
        failing_checks=list(fields.get("failing_checks") or []),
        write_capable=bool(fields.get("owner_authored")),
        directive=None,
    )
