#!/usr/bin/env python3
"""cs_wiring_check -- the STATIC integration gate for the Claude Science toolset.

WHY THIS FILE EXISTS. Rounds 1-3 of this lane fixed the tool; every one of those fixes was
reachable only because a human happened to run the right command afterwards. The recurring defect
class in this directory is not a bug in the tool, it is a BROKEN WIRE: a long-lived reference that
points at a tree which is stale, disposable, or simply not there.

  * ROUND 2 / D1 -- all four slash-command files invoked
    `~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1`, a detached-HEAD checkout
    holding the pre-fix doctor. `/claude-science doctor` printed `0 FAIL, 1 WARN, 9 PASS` from the
    code the lane had just replaced, in the same minute that `cs doctor` printed 13 rows.
  * ROUND 3 / R1 -- the always-on watchdog task was registered against a script inside a linked
    git WORKTREE. `git worktree remove` would have deleted the supervisor, and Task Scheduler
    reports a missing `-File` target as a task that RAN.
  * ROUND 3 / R2 -- `cs-deploy.sh` hardcoded SRC to that same stale checkout, so running it
    DOWNGRADED the WSL side and silently deployed neither `cs-lib.sh` nor `cs.conf`.
  * ROUND 4 (this file) -- `SKILL.md` tells the operator to run
    `python ~/.local/bin/test-cs-backup-readonly.py`, and `install.ps1` never deployed that file.
    It works on this box only because it was hand-copied; a fresh install leaves the documented
    falsification recipe pointing at nothing.

Every one of those is decidable from the repository alone -- no daemon, no WSL, no scheduled task,
no Windows. So they belong in a check that CI can run on every pull request, which is what this is.
`cs doctor`'s "Slash-command route" row is the RUNTIME half of the same idea; it can only speak
about the box it runs on, and nothing runs it automatically.

CONTRACT
    exit 0  every wire is intact          (prints OK + the invariant count)
    exit 1  at least one wire is broken   (prints one line per violation, code first)
    exit 2  could not measure             (root is not the toolchain repo) -- NOT a pass.

Exit 2 is deliberate and is the same rule the doctor now follows: a check that cannot find its
input must say so and must never render green.

USE-VS-MENTION. A document that NAMES a bad path is not wired to it. Every rule below reads a
FIELD -- a fenced command line, a `foreach` list, a TOML value -- never the prose. That is why
`commands/claude-science.md` can (and should) keep describing the D1 defect in its body without
tripping W1.

BOTH-STATES. Each rule is paired with a mutation in `ci/tests/test_cs_wiring.py` that breaks
exactly one wire in a scratch copy of the tree and asserts THIS code fires. A rule with no red
proof is a rule that measures nothing; the suite fails if a code is unreachable.

Run:
    python scripts/claude-science/cs_wiring_check.py [--root <repo>] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DISPATCHER = "~/.local/bin/cs.ps1"
SCRIPTS_REL = "scripts/claude-science"
SKILL_DIRS = (".agents/skills/claude-science-local", "skills/claude-science-local")
MONITOR_TOMLS = (
    ".agents/skills/monitor-launcher/monitors.toml",
    "skills/monitor-launcher/monitors.toml",
)
COMMAND_TWINS = (
    ("commands/claude-science.md", "agent-self/config/commands/claude-science.md"),
    ("commands/cs.md", "agent-self/config/commands/cs.md"),
)
# The config seam. These three files are ALLOWED to carry the literals; everything else in
# scripts/claude-science must read them through the seam. cs.conf is the SSOT and the two libs
# carry matching fallbacks so a missing cs.conf degrades to the shipped values, not to empty
# strings -- that duplication is deliberate and is pinned by the harness's parity assertion.
SEAM_FILES = frozenset({"cs.conf", "cs-lib.ps1", "cs-lib.sh"})
CODE_SUFFIXES = frozenset({".ps1", ".sh", ".py"})
# This file is excluded from W9 for one specific reason: its BYPASS_PATTERNS table has to CONTAIN
# the literals it hunts, so scanning itself is the "process probe matched its own command line"
# failure -- measured here, on the first run, where W9 flagged its own regex table. The exclusion
# is narrow and safe: this checker is CI-side instrumentation, install.ps1 never deploys it, and
# it never runs against the daemon. Everything else in the directory stays in scope, including the
# scripts install.ps1 does not deploy (cs-deploy.sh, cs-tailscale-serve.ps1).
SELF_NAME = "cs_wiring_check.py"
# Literals that must not appear in code outside the seam.
BYPASS_PATTERNS = (
    ("port", re.compile(r"(?<![\w.])8000(?![\w])")),
    ("distro", re.compile(r"\bUbuntu\b")),
    ("backup_root", re.compile(r"/mnt/[a-z]/Backups/claude-science")),
)
# Sourced BY NAME from the shell scripts, so install.ps1 must deploy them without stripping the
# extension. A deploy that omits either leaves commands on PATH that die at the moment they run.
SEAM_DEPLOY_REQUIRED = ("cs-lib.sh", "cs.conf")

LOCAL_BIN_TOKEN = re.compile(r"~/\.local/bin/([A-Za-z0-9._-]+)")
FENCE = re.compile(r"^\s*```")
# A script SOURCES the seam only if it dots it in or assigns its path. Testing for the bare string
# "cs-lib.sh" is a use-vs-mention error and it fired on the very first run of this file:
# cs-deploy.sh NAMES cs-lib.sh six times because it DEPLOYS it, and the mention-test therefore
# demanded that the deployer be deployed by the thing it deploys. Count the FIELD, not the document.
SOURCES_SEAM = re.compile(
    r"(?m)^\s*(?:_cs_lib=.*cs-lib\.sh|(?:\.|source)\s+.*cs-lib\.sh)"
)


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class CannotMeasure(Exception):
    """The root is not a usable toolchain checkout. Never a pass."""


def _read(path: Path) -> str:
    # newline="" would preserve CRLF and make every \n-anchored pattern miss; universal newlines
    # is what makes this identical on a Windows worktree and a Linux CI checkout.
    return path.read_text(encoding="utf-8", errors="replace")


def _strip_comments(text: str, suffix: str) -> str:
    """Drop comment tails so a literal quoted in prose is not read as a bypass.

    `#` is the comment character in all three scanned languages. A `#` inside a string literal is
    over-stripped rather than under-stripped, which biases this rule toward FALSE NEGATIVES -- the
    safe direction for a gate, and the reason the paired mutation test plants its literal in code.
    """
    del suffix  # single comment syntax across .ps1/.sh/.py; kept for future divergence
    out: list[str] = []
    for line in text.splitlines():
        idx = line.find("#")
        out.append(line if idx < 0 else line[:idx])
    return "\n".join(out)


def _foreach_lists(install_text: str) -> dict[str, list[str]]:
    """Parse install.ps1's three deploy loops, classified by what their BODY does.

    Classifying by position would silently mis-read a reordered file; classifying by body means a
    loop that stops stripping extensions is reclassified rather than mis-trusted. An unclassifiable
    loop is reported (W5) instead of ignored.
    """
    lines = install_text.splitlines()
    found: dict[str, list[str]] = {}
    unknown: list[str] = []
    for i, line in enumerate(lines):
        m = re.match(r"\s*foreach\s*\(\s*\$f\s+in\s+(.+?)\)\s*\{", line)
        if not m:
            continue
        names = re.findall(r"'([^']+)'", m.group(1))
        if not names:
            continue
        body: list[str] = []
        for nxt in lines[i + 1 :]:
            if re.match(r"^\}", nxt):
                break
            body.append(nxt)
        blob = "\n".join(body)
        if "Copy-Item" in blob:
            kind = "win"
        elif "GetFileNameWithoutExtension" in blob:
            kind = "wsl_strip"
        elif "~/.local/bin/$f" in blob:
            kind = "wsl_keep"
        else:
            unknown.append(",".join(names))
            continue
        found.setdefault(kind, []).extend(names)
    if unknown:
        found["__unknown__"] = unknown
    return found


def _deployed_names(lists: dict[str, list[str]]) -> set[str]:
    """The set of basenames that exist under ~/.local/bin after a full install."""
    out: set[str] = set()
    out.update(lists.get("win", []))
    out.update(lists.get("wsl_keep", []))
    for name in lists.get("wsl_strip", []):
        out.add(name.rsplit(".", 1)[0])  # the loop strips the extension on purpose
    return out


# --------------------------------------------------------------------------------------------
# W1 -- the slash commands must invoke the INSTALLED dispatcher, never a checkout.
# --------------------------------------------------------------------------------------------
def _check_route(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel, twin in COMMAND_TWINS:
        for candidate in (rel, twin):
            path = root / candidate
            if not path.is_file():
                out.append(Violation("W1-route", f"{candidate} is missing"))
                continue
            invocations = 0
            in_fence = False
            for n, line in enumerate(_read(path).splitlines(), start=1):
                if FENCE.match(line):
                    in_fence = not in_fence
                    continue
                if not in_fence or "cs.ps1" not in line:
                    continue
                invocations += 1
                if DISPATCHER not in line:
                    out.append(
                        Violation(
                            "W1-route",
                            f"{candidate}:{n} runs a cs.ps1 that is not {DISPATCHER} -- {line.strip()}",
                        )
                    )
            if invocations == 0:
                out.append(
                    Violation(
                        "W1-route",
                        f"{candidate} has no fenced cs.ps1 invocation at all "
                        "(a command that runs nothing cannot be said to work)",
                    )
                )
    return out


# --------------------------------------------------------------------------------------------
# W2 -- the dual-written twins must be byte-identical.
# --------------------------------------------------------------------------------------------
def _check_twins(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel, twin in COMMAND_TWINS:
        a, b = root / rel, root / twin
        if not a.is_file() or not b.is_file():
            out.append(Violation("W2-twin", f"{rel} / {twin}: one side is missing"))
            continue
        if a.read_bytes() != b.read_bytes():
            out.append(Violation("W2-twin", f"{rel} and {twin} differ"))
    canon, proj = root / SKILL_DIRS[0], root / SKILL_DIRS[1]
    if not canon.is_dir() or not proj.is_dir():
        out.append(
            Violation(
                "W2-twin", f"skill twin missing: {SKILL_DIRS[0]} / {SKILL_DIRS[1]}"
            )
        )
        return out
    names = {p.name for p in canon.iterdir() if p.is_file()} | {
        p.name for p in proj.iterdir() if p.is_file()
    }
    for name in sorted(names):
        a, b = canon / name, proj / name
        if not a.is_file() or not b.is_file():
            out.append(
                Violation("W2-twin", f"skill file {name} exists on only one side")
            )
        elif a.read_bytes() != b.read_bytes():
            out.append(
                Violation("W2-twin", f"skill file {name} differs between the two roots")
            )
    return out


# --------------------------------------------------------------------------------------------
# W3 -- both commands must carry a frontmatter description (the auto-pick surface).
# --------------------------------------------------------------------------------------------
def _check_description(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel, twin in COMMAND_TWINS:
        for candidate in (rel, twin):
            path = root / candidate
            if not path.is_file():
                continue  # W1 already reported it
            lines = _read(path).splitlines()
            if not lines or lines[0].strip() != "---":
                out.append(
                    Violation("W3-description", f"{candidate} has no YAML frontmatter")
                )
                continue
            desc = ""
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                m = re.match(r"description:\s*(.*)$", line)
                if m:
                    desc = m.group(1).strip()
            if not desc:
                out.append(
                    Violation(
                        "W3-description",
                        f"{candidate} frontmatter has no non-empty description "
                        "(a command with no description cannot be picked from the listing)",
                    )
                )
    return out


# --------------------------------------------------------------------------------------------
# W4 -- every ~/.local/bin path the docs tell an operator to run must actually be deployed.
# --------------------------------------------------------------------------------------------
def _check_docs_vs_deploy(root: Path, deployed: set[str]) -> list[Violation]:
    out: list[Violation] = []
    docs = [rel for pair in COMMAND_TWINS for rel in pair]
    docs += [f"{d}/SKILL.md" for d in SKILL_DIRS]
    docs.append(f"{SCRIPTS_REL}/README.md")
    for rel in docs:
        path = root / rel
        if not path.is_file():
            out.append(Violation("W4-docs-deploy", f"{rel} is missing"))
            continue
        for n, line in enumerate(_read(path).splitlines(), start=1):
            for name in LOCAL_BIN_TOKEN.findall(line):
                if name not in deployed:
                    out.append(
                        Violation(
                            "W4-docs-deploy",
                            f"{rel}:{n} tells the operator to run ~/.local/bin/{name}, "
                            "which install.ps1 never deploys",
                        )
                    )
    return out


# --------------------------------------------------------------------------------------------
# W5 -- every name install.ps1 deploys must exist in the source directory.
# --------------------------------------------------------------------------------------------
def _check_install_sources(root: Path, lists: dict[str, list[str]]) -> list[Violation]:
    out: list[Violation] = []
    for blob in lists.get("__unknown__", []):
        out.append(
            Violation(
                "W5-install-src",
                f"install.ps1 has a deploy loop this checker cannot classify ({blob}); "
                "refusing to guess what it installs",
            )
        )
    scripts = root / SCRIPTS_REL
    for kind in ("win", "wsl_strip", "wsl_keep"):
        if kind not in lists:
            out.append(
                Violation("W5-install-src", f"install.ps1 has no '{kind}' deploy loop")
            )
            continue
        for name in lists[kind]:
            if not (scripts / name).is_file():
                out.append(
                    Violation(
                        "W5-install-src",
                        f"install.ps1 deploys '{name}' but {SCRIPTS_REL}/{name} does not exist "
                        "(the copy is guarded by Test-Path, so the omission would be silent)",
                    )
                )
    return out


# --------------------------------------------------------------------------------------------
# W6 -- the seam files must be deployed with their names preserved, and every shell script that
#       sources cs-lib.sh must itself be deployed.
# --------------------------------------------------------------------------------------------
def _check_seam_deploy(root: Path, lists: dict[str, list[str]]) -> list[Violation]:
    out: list[Violation] = []
    keep = set(lists.get("wsl_keep", []))
    for name in SEAM_DEPLOY_REQUIRED:
        if name not in keep:
            out.append(
                Violation(
                    "W6-seam-deploy",
                    f"{name} is not in install.ps1's name-preserving loop; it is sourced by name, "
                    "so a stripped or missing copy breaks every shell script that reads the config",
                )
            )
    shipped = {n.rsplit(".", 1)[0] for n in lists.get("wsl_strip", [])}
    scripts = root / SCRIPTS_REL
    if scripts.is_dir():
        for sh in sorted(scripts.glob("*.sh")):
            if sh.name in SEAM_FILES:
                continue
            if not SOURCES_SEAM.search(_strip_comments(_read(sh), ".sh")):
                continue
            if sh.name.rsplit(".", 1)[0] not in shipped:
                out.append(
                    Violation(
                        "W6-seam-deploy",
                        f"{sh.name} sources cs-lib.sh but install.ps1 never deploys it",
                    )
                )
    return out


# --------------------------------------------------------------------------------------------
# W7 -- cs-deploy.sh must derive its source from its own location, not a hardcoded checkout.
# --------------------------------------------------------------------------------------------
def _check_deploy_src(root: Path) -> list[Violation]:
    path = root / SCRIPTS_REL / "cs-deploy.sh"
    if not path.is_file():
        return [Violation("W7-deploy-src", f"{SCRIPTS_REL}/cs-deploy.sh is missing")]
    out: list[Violation] = []
    code = _strip_comments(_read(path), ".sh")
    for n, line in enumerate(code.splitlines(), start=1):
        m = re.match(r'\s*SRC=(?:"?)([^"\s]+)', line)
        if not m:
            continue
        value = m.group(1)
        if "BASH_SOURCE" in value or "${CS_SRC" in value:
            continue
        out.append(
            Violation(
                "W7-deploy-src",
                f"cs-deploy.sh:{n} pins SRC to a fixed path ({value}); it must derive from "
                "BASH_SOURCE so it can never install a stale checkout",
            )
        )
    if "BASH_SOURCE" not in code:
        out.append(
            Violation("W7-deploy-src", "cs-deploy.sh never references BASH_SOURCE")
        )
    return out


# --------------------------------------------------------------------------------------------
# W8 -- the monitor register must carry exactly one csmon entry, pointing at a file that exists.
# --------------------------------------------------------------------------------------------
def _check_monitor(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for rel in MONITOR_TOMLS:
        path = root / rel
        if not path.is_file():
            out.append(Violation("W8-monitor", f"{rel} is missing"))
            continue
        text = _read(path)
        stanzas = re.findall(r"(?m)^\[csmon\]\s*$", text)
        if len(stanzas) != 1:
            out.append(
                Violation(
                    "W8-monitor",
                    f"{rel} has {len(stanzas)} [csmon] stanzas, expected exactly 1",
                )
            )
            continue
        body = text.split("[csmon]", 1)[1]
        body = re.split(r"(?m)^\[", body)[0]
        d = re.search(r'(?m)^\s*dir\s*=\s*"([^"]+)"', body)
        e = re.search(r'(?m)^\s*entry\s*=\s*"([^"]+)"', body)
        if not d or not e:
            out.append(Violation("W8-monitor", f"{rel} [csmon] is missing dir/entry"))
            continue
        skills_root = (
            path.parent.parent
        )  # <root>/{.agents/skills|skills}/monitor-launcher/..
        target = skills_root / d.group(1) / e.group(1)
        if not target.is_file():
            out.append(
                Violation(
                    "W8-monitor",
                    f"{rel} [csmon] points at {d.group(1)}/{e.group(1)}, which does not exist "
                    f"under {skills_root.name}",
                )
            )
    return out


# --------------------------------------------------------------------------------------------
# W9 -- no code outside the seam may hardcode the port, the distro or the backup root.
# --------------------------------------------------------------------------------------------
def _check_config_bypass(root: Path) -> list[Violation]:
    out: list[Violation] = []
    scripts = root / SCRIPTS_REL
    if not scripts.is_dir():
        return [Violation("W9-config-bypass", f"{SCRIPTS_REL} is missing")]
    for path in sorted(scripts.iterdir()):
        if not path.is_file() or path.suffix not in CODE_SUFFIXES:
            continue
        if path.name in SEAM_FILES or path.name == SELF_NAME:
            continue
        code = _strip_comments(_read(path), path.suffix)
        for label, pattern in BYPASS_PATTERNS:
            for n, line in enumerate(code.splitlines(), start=1):
                if pattern.search(line):
                    out.append(
                        Violation(
                            "W9-config-bypass",
                            f"{path.name}:{n} hardcodes the {label} outside the seam "
                            f"({', '.join(sorted(SEAM_FILES))}) -- {line.strip()[:100]}",
                        )
                    )
    return out


# --------------------------------------------------------------------------------------------
# W10 -- shell scripts must be LF, and .gitattributes must keep them that way.
# --------------------------------------------------------------------------------------------
def _check_shell_eol(root: Path) -> list[Violation]:
    out: list[Violation] = []
    scripts = root / SCRIPTS_REL
    attrs = scripts / ".gitattributes"
    if not attrs.is_file():
        out.append(Violation("W10-sh-eol", f"{SCRIPTS_REL}/.gitattributes is missing"))
    elif not re.search(r"(?m)^\s*\*\.sh\b.*\beol=lf\b", _read(attrs)):
        out.append(
            Violation(
                "W10-sh-eol",
                f"{SCRIPTS_REL}/.gitattributes does not pin *.sh to eol=lf",
            )
        )
    if scripts.is_dir():
        for sh in sorted(scripts.glob("*.sh")):
            if b"\r" in sh.read_bytes():
                out.append(
                    Violation(
                        "W10-sh-eol",
                        f"{sh.name} contains CR bytes; real WSL bash rejects CRLF (`then\\r`)",
                    )
                )
    return out


CHECKS = (
    "W1-route",
    "W2-twin",
    "W3-description",
    "W4-docs-deploy",
    "W5-install-src",
    "W6-seam-deploy",
    "W7-deploy-src",
    "W8-monitor",
    "W9-config-bypass",
    "W10-sh-eol",
)


def check(root: Path) -> list[Violation]:
    """Run every invariant. Raises CannotMeasure if the root is not a toolchain checkout."""
    scripts = root / SCRIPTS_REL
    install = scripts / "install.ps1"
    if not scripts.is_dir() or not install.is_file():
        raise CannotMeasure(
            f"{root} has no {SCRIPTS_REL}/install.ps1 -- this is not the toolchain repo"
        )
    lists = _foreach_lists(_read(install))
    deployed = _deployed_names(lists)
    violations: list[Violation] = []
    violations += _check_route(root)
    violations += _check_twins(root)
    violations += _check_description(root)
    violations += _check_docs_vs_deploy(root, deployed)
    violations += _check_install_sources(root, lists)
    violations += _check_seam_deploy(root, lists)
    violations += _check_deploy_src(root)
    violations += _check_monitor(root)
    violations += _check_config_bypass(root)
    violations += _check_shell_eol(root)
    return violations


def _default_root() -> Path:
    # <root>/scripts/claude-science/cs_wiring_check.py
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Static integration gate for the Claude Science toolset."
    )
    ap.add_argument(
        "--root",
        default=None,
        help="repository root (default: two levels above this file)",
    )
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else _default_root()
    try:
        violations = check(root)
    except CannotMeasure as exc:
        if args.json:
            print(
                json.dumps(
                    {"ok": False, "measured": False, "error": str(exc)}, indent=2
                )
            )
        else:
            print(f"NOT-CHECKED:cs-wiring {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not violations,
                    "measured": True,
                    "root": str(root),
                    "invariants": len(CHECKS),
                    "violations": [
                        {"code": v.code, "detail": v.detail} for v in violations
                    ],
                },
                indent=2,
            )
        )
    elif violations:
        for v in violations:
            print(f"  - {v}")
        print(
            f"FAILED:cs-wiring {len(violations)} broken wire(s) across {len(CHECKS)} invariants"
        )
    else:
        print(f"SUCCESS:cs-wiring all {len(CHECKS)} wiring invariants intact ({root})")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
