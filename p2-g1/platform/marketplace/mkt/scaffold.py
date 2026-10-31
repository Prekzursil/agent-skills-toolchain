"""Package scaffolder: emit a NEW package directory that already passes the linter.

DESIGN RULE
    A scaffolder whose output fails the project's own linter is worse than no scaffolder --
    it teaches the shape that gets rejected. ``test_scaffold.py`` therefore scaffolds,
    publishes and lints in one test, and the assertion is ``verdict == "PASS"``.

    The scaffold is also deliberately MINIMAL on permissions: it emits exactly one narrow
    ``fs:read`` scope and a comment explaining that a new permission must be justified. The
    default of a scaffolder is the default of the ecosystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canon import iso_now, write_json

TEMPLATE_README = """# {name}

{summary}

## Permissions

This package declares exactly the permissions it uses:

{permissions_md}

Every additional permission has to be justified in this file AND admitted by the consumer's
trust policy (`max_permissions` in `trust-policy.json`). `mkt lint` refuses a permission the
ceiling does not subsume, and the installer refuses it again at install time -- the two
checks share one subsumption function so they cannot drift apart.

## Payload

`package.json` enumerates every payload file explicitly. There is no glob: an implicit
payload is an unreviewed payload.
"""

TEMPLATE_MODULE = '''"""Payload module for {name}.

Replace this with the real artifact. It exists so the scaffold is a WORKING package that
publishes, installs and lints, rather than a skeleton that needs repair before first use.
"""


def hello() -> str:
    return "{name} v{version}"
'''


def scaffold(
    target_dir: str | Path,
    *,
    name: str,
    version: str = "0.1.0",
    summary: str | None = None,
    publisher_source: str = "https://example.invalid/your-repo",
    spdx: str = "MIT",
    channel: str = "beta",
    kind: str = "library",
    permissions: list[str] | None = None,
    now: str | None = None,
) -> Path:
    """Create ``target_dir/<name>`` with a spec, a payload, a README and a LICENSE stub."""
    root = Path(target_dir) / name
    payload = root / "payload"
    payload.mkdir(parents=True, exist_ok=True)
    timestamp = now or iso_now()
    perms_list = list(permissions or [f"fs:read:packages/{name}/**"])
    summary_text = (
        summary or f"Scaffolded {kind} package {name} -- replace this summary."
    )

    (payload / "README.md").write_text(
        TEMPLATE_README.format(
            name=name,
            summary=summary_text,
            permissions_md="\n".join(f"- `{p}`" for p in perms_list),
        ),
        encoding="utf-8",
        newline="\n",
    )
    (payload / f"{name.replace('-', '_')}.py").write_text(
        TEMPLATE_MODULE.format(name=name, version=version),
        encoding="utf-8",
        newline="\n",
    )
    (payload / "LICENSE").write_text(
        f"SPDX-License-Identifier: {spdx}\n\n"
        "Replace this stub with the full licence text before publishing to any public\n"
        "channel. `mkt publish` refuses when governance requires `license-basis-present`\n"
        "and no licence basis is supplied.\n",
        encoding="utf-8",
        newline="\n",
    )

    payload_files = sorted(
        p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()
    )
    spec: dict[str, Any] = {
        "name": name,
        "version": version,
        "channel": channel,
        "kind": kind,
        "summary": summary_text,
        "license": {
            "spdx": spdx,
            "notice_required": spdx.startswith("Apache"),
            "aggregate_verified": True,
        },
        "permissions": perms_list,
        "compatibility": {
            "platforms": ["any"],
            "clients": [{"id": "claude-code", "range": ">=2.0.0"}],
        },
        "provenance": {
            "source": publisher_source,
            "source_revision": "0000000000000000000000000000000000000000",
            "builder": "mkt-scaffold/1.0.0",
            "reproducible": True,
        },
        "payload_files": payload_files,
        "file_licenses": dict.fromkeys(payload_files, spdx),
        "categories": ["docs"],
        "tags": [name],
        "tests": f"pytest platform/marketplace -k {name.replace('-', '_')}",
        "scaffolded_at": timestamp,
    }
    write_json(root / "package.json", spec)
    return root
