"""Assemble the staging tree and build the distributable package.

**Minimality is structural.** The payload is not "the repo minus some excludes" — it is an
explicitly enumerated projection of a handful of repo paths into a staging tree
(``SOURCES`` below). That is what makes the spec's prohibition checkable rather than aspirational:
the only way ``.git``, a cache, a transcript or a credential file can enter the package is if
someone adds a rule for it here, and even then ``payload.classify_forbidden`` refuses the build.

The staging tree is built under a caller-supplied directory (a temp dir in tests, ``dist/stage``
by default), so ``build`` never mutates the repo.

Shipped layout::

    .claude-plugin/plugin.json   the strict manifest              (written by the packer)
    PLUGIN-INVENTORY.json        per-file hashes + totals         (written by the packer)
    PLUGIN-ALLOWLIST.json        the deny-by-default policy       (written by the packer)
    bin/astplugin.py             console entrypoint (python3)
    lib/astplugin/*.py           the runtime this file is part of
    schema/*.schema.json         artifact + manifest schemas
    commands/astplugin.md        the command surface deployed live
    hooks/plugin_health.py       health hook deployed live
    README.md  LICENSE
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import PluginError
from .fsops import atomic_write_text, iter_files, relposix
from .manifest import DeployTarget, Entrypoint, Manifest
from .packager import BuildResult, build_archive
from .payload import AllowRule, Payload, allowlist_document, collect

PLUGIN_NAME = "ast-integrate-platform"
PLUGIN_VERSION = "1.0.0"
#: Client floor: the manifest fields this profile adds are additive, so any client that reads
#: name/version/description/author/license works. 1.0.0 is the honest floor for "reads plugin.json".
MIN_CLIENT = "1.0.0"

#: Deliberately tight: measured payload is ~0.2 MB / ~40 files. A budget an order of magnitude
#: above the real size still catches the 2 GB accident the spec names.
MAX_BYTES = 4 * 1024 * 1024
MAX_FILES = 200

#: The runtime modules that ship. ``build.py`` ships too, so an installed copy can rebuild.
RUNTIME_MODULES = (
    "__init__.py",
    "build.py",
    "cache.py",
    "cli.py",
    "conformance.py",
    "deploy.py",
    "errors.py",
    "fsops.py",
    "health.py",
    "journal.py",
    "lifecycle.py",
    "logs.py",
    "manifest.py",
    "migrate.py",
    "packager.py",
    "payload.py",
    "policy.py",
    "proc.py",
    "schemas.py",
)

ALLOW_RULES: list[AllowRule] = [
    AllowRule("bin/*.py", "console entrypoint"),
    AllowRule("lib/astplugin/*.py", "the plugin runtime"),
    AllowRule("schema/*.schema.json", "artifact and manifest schemas"),
    AllowRule("commands/*.md", "command surface projected into live config"),
    AllowRule("hooks/*.py", "hook scripts projected into live config"),
    AllowRule("README.md", "user-facing documentation"),
    AllowRule("LICENSE", "redistribution terms; the manifest declares MIT"),
]

ENTRYPOINT_CONSOLE = "astplugin"
ENTRYPOINT_HOOK = "plugin-health"

_CONSOLE = '''"""Console entrypoint for the installed plugin.

Explicit interpreter: python3 (declared in .claude-plugin/plugin.json). A shebang is not a
portable launch contract on Windows, so the manifest names the interpreter and the launch
adapter builds the argv array.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from astplugin.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
'''

_HOOK = '''"""Health hook: reports the installed plugin\'s health without ever blocking a session.

Hook contract: exit 0 always. A hook that can fail the session is a worse outcome than a missed
health warning, so this one degrades loudly on stdout and still exits 0 (the fail-open row is
declared in the exec policy for `kind: hook`).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))


def main() -> int:
    prefix = os.environ.get("ASTPLUGIN_PREFIX")
    if not prefix:
        print("astplugin: ASTPLUGIN_PREFIX is unset; skipping the health probe")
        return 0
    try:
        from astplugin.health import health_check
        from astplugin.journal import Prefix

        report = health_check(Prefix(Path(prefix)))
        print(json.dumps({"ok": report.ok, "failed": [r.ident for r in report.failed]}, sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        print(f"astplugin: health probe degraded: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

_COMMAND_MD = """---
name: astplugin
description: Install, update, repair, roll back, uninstall, sync, and diagnose the ast-integrate platform plugin.
---

# /astplugin

Lifecycle control for the ast-integrate platform plugin.

| command | what it does | safe to repeat |
|---|---|---|
| `astplugin build` | build the deterministic package | yes |
| `astplugin install --package <zip> --prefix <p>` | stage, verify, activate, deploy | no (fails if the version exists) |
| `astplugin update --package <zip> --prefix <p>` | new version, live overrides preserved | no |
| `astplugin repair --prefix <p>` | restore files with no live-unique content | yes |
| `astplugin rollback --prefix <p>` | activate the previous version | yes |
| `astplugin uninstall --prefix <p> --retain-user-data\\|--purge-user-data` | remove | yes |
| `astplugin sync --prefix <p>` | live deployment synchronisation | yes |
| `astplugin cache --prefix <p> [--refresh\\|--invalidate\\|--verify]` | cache control | yes |
| `astplugin health-check --prefix <p> [--controls]` | probe registry + both-states control | yes |
| `astplugin conform --package <zip>` | conformance validator | yes |
| `astplugin migrate --prefix <p> [--dry-run]` | migrate an old layout | yes |
| `astplugin diagnose` | client / OS / shell compatibility | yes |
| `astplugin doctor --prefix <p>` | each failing probe -> its remediating command | yes |

Every mutating command accepts `--dry-run`. Every failure prints a stable `E_*` code, its cause,
its impact, and the exact next command; exit codes are one per failure class
(`astplugin errors --json -` prints the whole taxonomy).
"""

_README = f"""# {PLUGIN_NAME}

The ast-integrate platform, packaged as an installable Claude Code plugin.

## Install

    python bin/astplugin.py install --package <package>.zip --prefix <install-prefix>

`--prefix` is an explicit directory. Nothing is written outside it, and `--live` (default
`<prefix>/live`) is the deployment target — the plugin never writes to a real `~/.claude` unless
you point `--live` there yourself.

## Lifecycle

`install` -> `update` -> (`repair` | `rollback`) -> `uninstall`. Every one is transactional: a
failure anywhere replays the inverse of each applied step, so a failed install leaves no partial
state. `uninstall` refuses to run without an explicit `--retain-user-data` or `--purge-user-data`.

## Safety properties this package asserts, not documents

* deny-by-default payload allowlist plus an independent forbidden-content scan (no `.git`, caches,
  logs, transcripts, credentials) and a hard size/file budget;
* a deterministic archive (sorted entries, fixed timestamps, LF) so two builds of the same content
  are byte-identical;
* a two-directional drift classifier — live-unique content is never overwritten, and a diverged
  file produces a decision packet instead of a guess;
* every health probe ships a both-states control proving it fails when its invariant breaks;
* deny-by-default log redaction; the plugin never reads a credential store.

## License

MIT. See `LICENSE`.
"""

_LICENSE = """MIT License

Copyright (c) 2026 Prekzursil

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


@dataclass
class Sources:
    """Where the payload comes from. An explicit projection, never a repo-wide walk."""

    repo_root: Path

    @property
    def runtime_dir(self) -> Path:
        return self.repo_root / "platform" / "plugin"

    @property
    def schema_dir(self) -> Path:
        return self.repo_root / "tools" / "plugin" / "schema"


def stage(repo_root: Path, stage_root: Path, *, version: str = PLUGIN_VERSION) -> Path:
    """Assemble the staging tree. Returns ``stage_root``, which is created fresh."""
    src = Sources(repo_root)
    if stage_root.exists():
        shutil.rmtree(stage_root)
    (stage_root / "lib" / "astplugin").mkdir(parents=True)
    (stage_root / "bin").mkdir(parents=True)
    (stage_root / "schema").mkdir(parents=True)
    (stage_root / "commands").mkdir(parents=True)
    (stage_root / "hooks").mkdir(parents=True)

    missing = [m for m in RUNTIME_MODULES if not (src.runtime_dir / m).exists()]
    if missing:
        raise PluginError(
            "E_PAYLOAD",
            f"{len(missing)} declared runtime module(s) are missing from {src.runtime_dir}",
            context={"first": missing[0]},
        )
    for module in RUNTIME_MODULES:
        text = (src.runtime_dir / module).read_text(encoding="utf-8")
        atomic_write_text(stage_root / "lib" / "astplugin" / module, text)

    if not src.schema_dir.exists():
        raise PluginError(
            "E_PAYLOAD",
            f"schema source directory is absent: {src.schema_dir}",
            context={"hint": "run `astplugin schemas --write` first"},
        )
    for schema in sorted(src.schema_dir.glob("*.schema.json")):
        atomic_write_text(
            stage_root / "schema" / schema.name, schema.read_text(encoding="utf-8")
        )

    atomic_write_text(stage_root / "bin" / "astplugin.py", _CONSOLE)
    atomic_write_text(stage_root / "hooks" / "plugin_health.py", _HOOK)
    atomic_write_text(stage_root / "commands" / "astplugin.md", _COMMAND_MD)
    atomic_write_text(stage_root / "README.md", _README)
    atomic_write_text(stage_root / "LICENSE", _LICENSE)
    return stage_root


def manifest_for(version: str = PLUGIN_VERSION) -> Manifest:
    """The manifest this build ships. Built in code so it cannot drift from the payload layout."""
    return Manifest(
        name=PLUGIN_NAME,
        version=version,
        description=(
            "The ast-integrate platform: workflow DSL, council protocols, completion predicates "
            "and the receipt substrate, with a transactional install/update/repair/rollback/"
            "uninstall lifecycle and a two-directional live-deployment synchroniser."
        ),
        author={"name": "Prekzursil"},
        license="MIT",
        min_client=MIN_CLIENT,
        max_client=None,
        platforms=("windows", "macos", "linux"),
        shells=("pwsh", "bash", "zsh", "cmd"),
        schema_version=1,
        keywords=("agent-ops", "workflow", "council", "receipts", "platform"),
        interpreters=({"id": "python3", "floor": "3.10.0", "required": True},),
        entrypoints=(
            Entrypoint(
                ident=ENTRYPOINT_CONSOLE,
                kind="command",
                path="bin/astplugin.py",
                interpreter="python3",
                description="lifecycle CLI",
            ),
            Entrypoint(
                ident=ENTRYPOINT_HOOK,
                kind="hook",
                path="hooks/plugin_health.py",
                interpreter="python3",
                description="non-blocking health hook",
            ),
        ),
        deploy_targets=(
            DeployTarget("commands", "commands", "copy"),
            DeployTarget("hooks", "hooks", "copy"),
        ),
        payload_max_bytes=MAX_BYTES,
        payload_max_files=MAX_FILES,
    )


def build(
    repo_root: Path,
    out_dir: Path,
    *,
    version: str = PLUGIN_VERSION,
    stage_root: Path | None = None,
    keep_stage: bool = False,
) -> tuple[BuildResult, Payload]:
    """Stage, select, gate, and write the deterministic package. Returns (result, payload).

    The staging tree is removed on success unless ``keep_stage`` is set: leaving a second copy of
    the payload next to the archive is exactly the "unrelated content" the spec tells us not to
    accumulate, and it would double the size of any published output directory.
    """
    stage_dir = stage_root or (out_dir / "stage")
    stage(repo_root, stage_dir, version=version)
    manifest = manifest_for(version)
    payload = collect(
        stage_dir,
        ALLOW_RULES,
        budget_bytes=manifest.payload_max_bytes,
        budget_files=manifest.payload_max_files,
    )
    unmatched = [rel for rel, _ in payload.rejected]
    if unmatched:
        raise PluginError(
            "E_PAYLOAD",
            f"{len(unmatched)} staged file(s) matched no allowlist rule; the staging tree and the "
            "allowlist disagree",
            context={"first": unmatched[0]},
        )
    allow_doc = allowlist_document(
        ALLOW_RULES,
        budget_bytes=manifest.payload_max_bytes,
        budget_files=manifest.payload_max_files,
    )
    archive = out_dir / f"{manifest.name}-{manifest.version}.zip"
    result = build_archive(payload, manifest, archive, allowlist_doc=allow_doc)
    if not keep_stage and stage_root is None:
        shutil.rmtree(stage_dir, ignore_errors=True)
    return result, payload


def staged_relpaths(stage_dir: Path) -> list[str]:
    return sorted(relposix(stage_dir, f) for f in iter_files(stage_dir))
