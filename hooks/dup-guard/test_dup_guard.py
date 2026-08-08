#!/usr/bin/env python3
"""Direct-invocation tests for dup-guard/guard.py.

Proves: writing a NEW file whose basename/symbol already exists FIRES; a genuinely
new name stays SILENT; overwrites and recurring basenames stay SILENT; throttle works.

Run:  python test_dup_guard.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

HOOK = str(Path(__file__).resolve().parent / "guard.py")


def _guard_module():
    """Import ``guard.py`` under a unique name (several hook dirs ship a ``guard.py``)."""
    spec = importlib.util.spec_from_file_location("dupguard_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_symbol_lookup_treats_a_prose_declaration_as_a_mention():
    """L03: a declaration-SHAPED line in a non-source file is a MENTION, not a definition.

    ``_symbol_defined_elsewhere`` greps for declaration-shaped TEXT; it parses nothing, so a
    Markdown code fence, a design doc or a JSON fixture matches exactly like real code.
    Measured at 27fb388 with the production function against this repo: writing a new
    ``probe_only_data_version_control.py`` containing ``class DataVersionControl:`` returned
    ``.agents/skills/llm-security/rules/data-poisoning.md`` -- prose the agent was then told to
    "extend / import", which is impossible.

    ``subprocess.run`` is stubbed so the assertions are deterministic and need no ripgrep on
    PATH.  Three directions, because a one-directional test cannot tell a working filter from
    a blanket disarm:
      1. a prose-only hit yields None (the defect),
      2. a prose hit FOLLOWED by a real source hit still yields the source file -- the loop
         must keep scanning rather than stop at the first line (the non-disarm control), and
      3. the rg argv carries source-extension globs, so the filter is enforced twice.
    """
    guard = _guard_module()
    canned = {"stdout": ""}
    seen: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        seen.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, canned["stdout"], "")

    original = guard.subprocess.run
    try:
        guard.subprocess.run = fake_run

        canned["stdout"] = "docs/notes.md\n"
        assert (
            guard._symbol_defined_elsewhere(".", "DataVersionControl", "src/dvc.py")
            is None
        ), "a Markdown-only hit must not be reported as an existing definition"

        canned["stdout"] = "docs/notes.md\nsrc/real_dvc.py\n"
        assert (
            guard._symbol_defined_elsewhere(".", "DataVersionControl", "src/dvc.py")
            == "src/real_dvc.py"
        ), "a real source definition after a prose hit must still be found"

        canned["stdout"] = "CHANGELOG\nnotes.txt\ndata.json\n"
        assert (
            guard._symbol_defined_elsewhere(".", "DataVersionControl", "src/dvc.py")
            is None
        ), "extensionless / text / data files are not definition sites either"
    finally:
        guard.subprocess.run = original

    assert seen, "the stub must have been invoked, otherwise this test measured nothing"
    for argv in seen:
        assert "*.py" in argv and "*.ts" in argv, (
            f"rg must be scoped to source extensions: {argv}"
        )


_TEMPLATE_MENTION = '''"""A migration script: it INJECTS this block into other files."""

BLOCK = \'\'\'
def is_real_occurrence(*_a, **_kw):
    return True
\'\'\'
'''
_REAL_DECL = "def is_real_occurrence(text, span, ctx):\n    return True\n"


def _decl_repo(files: dict) -> Path:
    """A temp dir holding REAL files, so the discriminator has bytes to judge."""
    root = Path(tempfile.gettempdir()) / f"dg-decl-{uuid.uuid4().hex[:10]}"
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return root


def _canned_rg(guard, stdout: str):
    """Replace guard.subprocess.run with a stub returning `stdout` (restore via .close())."""
    original = guard.subprocess.run

    def fake_run(argv, **_kwargs):
        return subprocess.CompletedProcess(list(argv), 0, stdout, "")

    guard.subprocess.run = fake_run
    return original


def test_symbol_lookup_is_wired_to_the_shared_discriminator():
    """2026-08-08: rg reports declaration-SHAPED text; only the discriminator judges role.

    Recorded fire: writing ``run_uvm_gate.py`` was told the symbol ``is_real_occurrence``
    "is already defined at build/B1/proofs/make_migrations.py" -- line 42 of that file,
    inside a triple-quoted CODE TEMPLATE the script injects elsewhere. Not importable, so
    the hook's own "extend / import the existing one" was impossible to follow.

    Four directions, because a one-directional test cannot tell a working filter from a
    blanket disarm:
      1. a string-literal-only hit yields None,
      2. a genuine declaration is still reported (the non-disarm control),
      3. a mention FOLLOWED by a real definition still yields the real one, and
      4. exceeding the candidate cap sets ``_SCAN_TRUNCATED`` so the NOT-CHECKED banner
         fires -- a truncated scan must never be byte-identical to a clean pass.
    """
    guard = _guard_module()
    repo = _decl_repo(
        {
            "a_template.py": _TEMPLATE_MENTION,
            "z_real_impl.py": _REAL_DECL,
            **{
                f"m{i}/t.py": _TEMPLATE_MENTION
                for i in range(guard._DISCRIM_MAX_CANDIDATES + 2)
            },
        }
    )
    target = str(repo / "brand_new.py")
    mention = str(repo / "a_template.py")
    real = str(repo / "z_real_impl.py")

    original = _canned_rg(guard, mention + "\n")
    try:
        guard._SCAN_TRUNCATED = False
        assert (
            guard._symbol_defined_elsewhere(str(repo), "is_real_occurrence", target)
            is None
        ), "a declaration inside a string-literal code template is a MENTION"
        assert guard._SCAN_TRUNCATED is False, "one candidate is not a truncated scan"

        guard.subprocess.run = lambda argv, **kw: subprocess.CompletedProcess(
            list(argv), 0, real + "\n", ""
        )
        guard._SCAN_TRUNCATED = False
        assert (
            guard._symbol_defined_elsewhere(str(repo), "is_real_occurrence", target)
            == real
        ), "a GENUINE declaration must still be reported -- otherwise this is a disarm"

        guard.subprocess.run = lambda argv, **kw: subprocess.CompletedProcess(
            list(argv), 0, mention + "\n" + real + "\n", ""
        )
        guard._SCAN_TRUNCATED = False
        assert (
            guard._symbol_defined_elsewhere(str(repo), "is_real_occurrence", target)
            == real
        ), "the loop must skip the mention and keep scanning"

        overflow = "\n".join(
            str(repo / f"m{i}" / "t.py")
            for i in range(guard._DISCRIM_MAX_CANDIDATES + 2)
        )
        guard.subprocess.run = lambda argv, **kw: subprocess.CompletedProcess(
            list(argv), 0, overflow + "\n", ""
        )
        guard._SCAN_TRUNCATED = False
        assert (
            guard._symbol_defined_elsewhere(str(repo), "is_real_occurrence", target)
            is None
        )
        assert guard._SCAN_TRUNCATED is True, (
            "hitting the candidate cap must set _SCAN_TRUNCATED so main() emits "
            "NOT CHECKED -- silence here would read as a pass"
        )
    finally:
        guard.subprocess.run = original
        shutil.rmtree(repo, ignore_errors=True)


def test_missing_discriminator_leaves_behaviour_unchanged():
    """FAIL-OPEN: no shared module -> exactly the pre-wiring answer, never a disarm."""
    guard = _guard_module()
    repo = _decl_repo({"a_template.py": _TEMPLATE_MENTION})
    target = str(repo / "brand_new.py")
    mention = str(repo / "a_template.py")

    original = _canned_rg(guard, mention + "\n")
    original_loader = guard._load_discriminator
    try:
        guard._load_discriminator = lambda: (None, None)
        guard._SCAN_TRUNCATED = False
        assert (
            guard._symbol_defined_elsewhere(str(repo), "is_real_occurrence", target)
            == mention
        ), "without a discriminator the guard must keep its old (noisier) answer"
    finally:
        guard._load_discriminator = original_loader
        guard.subprocess.run = original
        shutil.rmtree(repo, ignore_errors=True)


def run(payload, env_extra=None):
    env = dict(os.environ)
    env.setdefault(
        "DUP_GUARD_ROOT", str(Path(tempfile.gettempdir()) / f"dg-{uuid.uuid4().hex}")
    )
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert p.returncode == 0, f"must exit 0: {p.stderr}"
    return p.stdout.strip()


def fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


def setup_repo() -> Path:
    repo = Path(tempfile.gettempdir()) / f"dg-repo-{uuid.uuid4().hex}"
    (repo / "src" / "components").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "components" / "widget.py").write_text(
        "class Widget:\n    def render(self):\n        return 1\n", encoding="utf-8"
    )
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    return repo


def test_second_swift_package_manifest_is_silent() -> None:
    """`Package.swift` recurs once per package -- a 2nd one is NOT a duplicate.

    Collected by the ``pytest hooks/`` step already named in
    ``.github/workflows/quality.yml`` (no new CI step needed).  ``.swift`` is in
    ``_SRC_EXT``, so before ``package.swift`` joined ``_RECUR`` this fired
    "extend / import the existing one" at every additional Swift package in a
    monorepo.  Observed RED before the guard change, GREEN after.
    """
    repo = Path(tempfile.gettempdir()) / f"dg-swift-{uuid.uuid4().hex}"
    (repo / "PackageA").mkdir(parents=True, exist_ok=True)
    (repo / "PackageA" / "Package.swift").write_text(
        "// swift-tools-version:5.9\nimport PackageDescription\n", encoding="utf-8"
    )
    out = run(
        {
            "session_id": "swift-pkg",
            "tool_name": "Write",
            "cwd": str(repo),
            "tool_input": {
                "file_path": str(repo / "PackageB" / "Package.swift"),
                "content": "// swift-tools-version:5.9\nimport PackageDescription\n",
            },
        }
    )
    assert not fired(out), (
        "a second Swift package manifest must not be reported as a duplicate; "
        f"guard emitted: {out!r}"
    )


def main() -> int:
    repo = setup_repo()
    cwd = str(repo)
    cases = []
    sroot = str(Path(tempfile.gettempdir()) / f"dg-shared-{uuid.uuid4().hex}")
    env = {"DUP_GUARD_ROOT": sroot}

    # 1. New file, SAME basename elsewhere -> FIRES
    out = run(
        {
            "session_id": "d1",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "lib" / "widget.py"),
                "content": "x=1\n",
            },
        },
        env,
    )
    cases.append(("new file w/ existing basename -> fires", fired(out), True, out))

    # 2. Throttle: same basename again (same session) -> SILENT
    out = run(
        {
            "session_id": "d1",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "other" / "widget.py"),
                "content": "y=2\n",
            },
        },
        env,
    )
    cases.append(("throttle: 2nd same-basename -> silent", fired(out), False, out))

    # 3. Genuinely NEW basename -> SILENT
    out = run(
        {
            "session_id": "d2",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "lib" / "sprocket_xyz.py"),
                "content": "z=3\n",
            },
        },
        env,
    )
    cases.append(("brand-new basename -> silent", fired(out), False, out))

    # 4. Primary-SYMBOL collision (different filename, same class) -> FIRES
    out = run(
        {
            "session_id": "d3",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "lib" / "thing.py"),
                "content": "class Widget:\n    pass\n",
            },
        },
        env,
    )
    cases.append(("symbol collision (class Widget) -> fires", fired(out), True, out))

    # 5. Overwrite of an EXISTING path -> SILENT
    out = run(
        {
            "session_id": "d4",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "src" / "components" / "widget.py"),
                "content": "class Widget:\n    pass\n",
            },
        },
        env,
    )
    cases.append(("overwrite existing path -> silent", fired(out), False, out))

    # 6. Recurring basename __init__.py in a new dir -> SILENT
    out = run(
        {
            "session_id": "d5",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "pkg" / "__init__.py"),
                "content": "\n",
            },
        },
        env,
    )
    cases.append(("__init__.py recurring -> silent", fired(out), False, out))

    # 7. DUP_GUARD=off -> SILENT even on a collision
    out = run(
        {
            "session_id": "d6",
            "tool_name": "Write",
            "cwd": cwd,
            "tool_input": {
                "file_path": str(repo / "z" / "widget.py"),
                "content": "x=1\n",
            },
        },
        {"DUP_GUARD": "off", **env},
    )
    cases.append(("DUP_GUARD=off -> silent", fired(out), False, out))

    ok = True
    for name, got, want, out in cases:
        status = "PASS" if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"[{status}] {name}: fired={got} expected={want}")
        if got != want:
            print(f"         output={out!r}")
    print("\nFIRED-sample (case 1):")
    print(
        run(
            {
                "session_id": "demo",
                "tool_name": "Write",
                "cwd": cwd,
                "tool_input": {
                    "file_path": str(repo / "demo" / "widget.py"),
                    "content": "x=1\n",
                },
            },
            {
                "DUP_GUARD_ROOT": str(
                    Path(tempfile.gettempdir()) / f"dg-demo-{uuid.uuid4().hex}"
                )
            },
        )
    )
    print(
        "SILENT-sample (case 3): "
        + repr(
            run(
                {
                    "session_id": "demo2",
                    "tool_name": "Write",
                    "cwd": cwd,
                    "tool_input": {
                        "file_path": str(repo / "demo" / "totallynew.py"),
                        "content": "x=1\n",
                    },
                },
                {
                    "DUP_GUARD_ROOT": str(
                        Path(tempfile.gettempdir()) / f"dg-demo2-{uuid.uuid4().hex}"
                    )
                },
            )
        )
    )
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
