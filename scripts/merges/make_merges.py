"""Produce the MERGED copies of the two held files that need a hand reconcile.

Generated from the REPO copy (never re-typed by hand, so nothing drifts in transcription).
Writes into scripts/merges/<repo-relative-path> so the tree can be copied straight across.

Held file 1 -- .agents/skills/multi-agent-quickstart/SKILL.md
    RE-MEASURED: live is a STRICT SUBSET of repo (diff = 5 deletions, 0 additions). There is
    no live-only content, so this is staleness in live, not bidirectional divergence. The
    merged content is therefore the repo copy byte-for-byte; the reconcile is a repo -> live
    deploy, not a merge.

Held file 2 -- audit_quality_zero_platform.py
    GENUINELY bidirectional. Repo holds find_python_with_yaml(); live holds a
    `pwsh ConvertFrom-Yaml` fallback. Both are preserved, ordered by measured reliability.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = REPO / "scripts" / "merges"

SKILL_REL = ".agents/skills/multi-agent-quickstart/SKILL.md"
AUDIT_REL = (
    ".agents/skills/quality-zero-platform-control-plane/scripts/"
    "audit_quality_zero_platform.py"
)

# --------------------------------------------------------------- held file 1: verbatim copy
src = REPO / SKILL_REL
dst = OUT / SKILL_REL
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, dst)
assert dst.read_bytes() == src.read_bytes()
print(f"SKILL.md      : copied verbatim from repo ({len(src.read_bytes())} bytes) -> {dst}")

# --------------------------------------------------------------- held file 2: real merge
src = REPO / AUDIT_REL
raw = src.read_bytes()
# Determine the file's newline convention from the BYTES, then work on a \n-normalised
# string and restore the convention on write. Reading with read_text() collapses CRLF to \n
# (universal newlines), so matching a CRLF-expanded pattern against it never hits -- the
# guard below caught exactly that on the first run.
crlf = raw.count(b"\r\n")
lf = raw.count(b"\n")
if crlf and crlf != lf:
    sys.exit(f"FAILED: mixed line endings in {src} (crlf={crlf} lf={lf}); refusing to guess")
nl = "\r\n" if crlf else "\n"
text = raw.decode("utf-8").replace("\r\n", "\n")

OLD = '''def yaml_load(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        interpreter = find_python_with_yaml()
        if interpreter:
            stdout = run_command(
                [
                    *interpreter,
                    "-c",
                    (
                        "import json, sys, yaml; "
                        "print(json.dumps(yaml.safe_load(sys.stdin.read())))"
                    ),
                ],
                input_text=text,
            )
            return json.loads(stdout)
        raise RuntimeError(
            "PyYAML is required to parse controller configuration. "
            "Install PyYAML or set CODEX_PYTHON_WITH_YAML to an interpreter that has it."
        )
    return yaml.safe_load(text)
'''

NEW = '''def yaml_load(text: str) -> Any:
    """Parse YAML, degrading through every fallback either copy of this file ever had.

    MERGED 2026-07-18 (unit B7). The repo copy and the live copy had DIFFERENT fallbacks for
    "PyYAML is not importable in this interpreter", and each side was missing the other's.
    Overwriting in either direction would have silently deleted a working escape hatch, which
    is why the file sat on sync-from-live.ps1's repo-owned hold list. Both are kept here,
    ordered by reliability measured on this box 2026-07-18:

      1. `import yaml` in-process.        Works today: the default python carries PyYAML 6.0.3.
      2. find_python_with_yaml()          REPO-side. Finds another interpreter that has PyYAML,
                                          honouring $CODEX_PYTHON_WITH_YAML, then sys.executable,
                                          python / py -3 / python3, then any %LOCALAPPDATA%
                                          Python install. Real YAML semantics.
      3. pwsh ConvertFrom-Yaml            LIVE-side. Kept LAST and deliberately so: it is NOT a
                                          built-in cmdlet, it ships with the `powershell-yaml`
                                          module, and that module is NOT installed on this
                                          machine (measured -- Get-Module -ListAvailable returns
                                          nothing), so here it always raises. It earns its place
                                          only on a box that has powershell-yaml but exactly one
                                          Python without PyYAML.

    The live copy called the pwsh path with check=True and no guard, so a missing module
    surfaced as a bare CalledProcessError. Here every fallback failure falls through to the
    actionable RuntimeError instead.
    """
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        yaml = None  # type: ignore[assignment]
    if yaml is not None:
        return yaml.safe_load(text)

    interpreter = find_python_with_yaml()
    if interpreter:
        stdout = run_command(
            [
                *interpreter,
                "-c",
                (
                    "import json, sys, yaml; "
                    "print(json.dumps(yaml.safe_load(sys.stdin.read())))"
                ),
            ],
            input_text=text,
        )
        return json.loads(stdout)

    try:
        stdout = run_command(
            [
                "pwsh",
                "-NoProfile",
                "-Command",
                "$input | ConvertFrom-Yaml | ConvertTo-Json -Depth 100",
            ],
            input_text=text,
        )
        return json.loads(stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        pass

    raise RuntimeError(
        "PyYAML is required to parse controller configuration. Install PyYAML, or point "
        "CODEX_PYTHON_WITH_YAML at an interpreter that has it, or install the powershell-yaml "
        "module so the `pwsh ConvertFrom-Yaml` fallback can run."
    )
'''

if OLD not in text:
    sys.exit("FAILED: repo-side yaml_load() block not found verbatim; refusing to guess")

merged = text.replace(OLD, NEW, 1).replace("\n", nl)

# Both sides' unique content must survive.
must_keep = [
    "def find_python_with_yaml",          # repo-only
    "CODEX_PYTHON_WITH_YAML",             # repo-only
    "ConvertFrom-Yaml",                   # live-only
    "import os",                          # repo-only (live deleted it)
    "import sys",                         # repo-only (live deleted it)
]
for token in must_keep:
    if token not in merged:
        sys.exit(f"FAILED: merged file lost required content {token!r}")

dst = OUT / AUDIT_REL
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_bytes(merged.encode("utf-8"))
print(f"audit_*.py    : merged ({len(raw)} -> {len(merged.encode('utf-8'))} bytes) -> {dst}")
print("both sides' unique content verified present:", ", ".join(must_keep))
