#!/usr/bin/env python
"""cmd-rewrite/msys_pathconv.py — MSYS/Git-Bash argv path-conversion ENFORCEMENT.

WHY
===
On Windows, Claude Code's Bash tool runs under MSYS/Git-Bash (MINGW64).  MSYS
rewrites arguments that *look* like POSIX paths into Windows paths before the
callee's argv is built.  For a NATIVE (non-msys-2.0.dll-linked) callee this is
often correct — but for several measured shapes it silently produces an argv
that denotes nothing:

    git show origin/main:.github/workflows
        -> argv 'origin\\main;.github\\workflows'      fatal: ambiguous argument
    wsl -- fstrim /mnt/docker-desktop-disk
        -> argv 'C:/Program Files/Git/mnt/docker-desktop-disk'
    adb ... /sdcard/SAVE_DATA
        -> argv 'C:/Program Files/Git/sdcard/SAVE_DATA'   (the 2026-05-27 wipe)

This module is the ENFORCEMENT half.  It does not warn; it rewrites the command
so the child process receives the bytes the caller intended.

THE ENFORCEMENT PRIMITIVE — and why it is NOT `MSYS_NO_PATHCONV=1`
==================================================================
`MSYS_NO_PATHCONV=1` is process-wide and all-or-nothing: it suppresses
conversion for EVERY argument of that command.  That breaks the legitimate
cases, e.g.

    git commit -F /tmp/msg.txt

where `/tmp/msg.txt` -> `C:/Users/../Temp/msg.txt` is exactly what native git
needs.  Suppressing it hands native git a literal `/tmp/msg.txt` it cannot open.
It is also presence-checked, so `MSYS_NO_PATHCONV=0` suppresses just as hard.

We therefore enforce with `MSYS2_ARG_CONV_EXCL`, which is **value-checked and
per-argument**: its value is a `;`-separated list of raw-argument-text PREFIXES,
and only arguments matching a prefix are exempted.  Siblings still convert:

    MSYS2_ARG_CONV_EXCL='/mnt/protected' probe /mnt/protected /srv/unprotected
      ARG0 '/mnt/protected'   ARG1 'C:/Program Files/Git/srv/unprotected'

We emit the FULL effective token as the prefix, never a short prefix, because
the match is a pure string-prefix test on raw argument text and is NOT
path-component aware (`/mn` protects `/mnope/a`, a different directory).

THE TWO GATES (measured, not assumed)
=====================================
GATE A — the callee must be a NATIVE binary.  Callees linked against
         msys-2.0.dll (coreutils, ssh, bash) never see a converted argv;
         `MSYS_NO_PATHCONV=1 ls -d /usr/bin` is byte-identical to the bare form.
GATE B — the argument must match one of four measured shapes
         (leading-slash / flag-form / delimiter-form / colon-path-list),
         and must not carry a glob metacharacter (which suppresses conversion
         entirely, across every shape).

Both gates must hold.  A locally-mounted root (`/tmp`, `/c`, `/usr`, ...)
rewrites back to the SAME object, so it is harmless for a non-bridge callee and
is deliberately NOT protected — that is the primary false-positive discriminator.

STATIC EXPANSION (the four recovered false-negative classes)
============================================================
MSYS converts the POST-EXPANSION argv, so a detector reading literal token text
misses every indirection.  We resolve, conservatively and statically:

    E1  V=/mnt/x; wsl ls "$V"            literal assignment -> constant prop
    E2  wsl ls "$(echo /mnt/x)"          whitelisted side-effect-free $(echo …)
    E4  PRE=/mnt; wsl ls "$PRE/evade"    assignment + concatenation
    E5  eval 'wsl ls /mnt/x'             single-quoted literal eval body

Anything we cannot resolve to a literal is reported UNRESOLVABLE and left
alone — we never guess.  See COVERAGE_GAPS below.

CONTRACT
========
Pure stdlib.  No import-time side effects.  Never blocks, never raises out of
`plan()`.  Non-Windows is a hard no-op.  Explicit opt-out honoured.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import time
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────── documented gaps

COVERAGE_GAPS: tuple[str, ...] = (
    "A token whose value comes from a non-whitelisted command substitution "
    "($(git rev-parse --show-toplevel)) cannot be resolved statically; the "
    "outer argument is left unprotected. The substitution's OWN arguments are "
    "still analysed.",
    "A token whose value comes from the ambient environment ($HOME, $PWD, an "
    "exported var set in an earlier Bash tool call) is unresolvable: this hook "
    "sees only the command string, never the shell's live environment.",
    "Arithmetic/parameter expansion with operators (${V:-/mnt/x}, ${V#/a}) is "
    "not modelled and is treated as unresolvable.",
    "A path constructed inside a script file that the command merely invokes "
    "(bash ./deploy.sh) is invisible — only the command line is analysed.",
    "The colon-path-list predicate is inferred from 14 measured forms, not from "
    "MSYS's determine_type() source. A form outside that sample could be "
    "mis-predicted in either direction.",
)

# ───────────────────────────────────────────────────────────────── callee tiers

# Linked against msys-2.0.dll -> conversion provably never reaches them.
MSYS_IMMUNE: frozenset[str] = frozenset({
    "ls", "cat", "grep", "egrep", "fgrep", "rm", "cp", "mv", "mkdir", "rmdir",
    "find", "sed", "awk", "gawk", "tar", "head", "tail", "sort", "uniq", "wc",
    "cut", "tr", "chmod", "chown", "ln", "touch", "stat", "du", "df", "diff",
    "patch", "xargs", "basename", "dirname", "readlink", "realpath", "tee",
    "bash", "sh", "dash", "env", "which", "file", "md5sum", "sha1sum",
    "sha256sum", "base64", "gzip", "gunzip", "zcat", "less", "more", "vi",
    "vim", "nano", "ssh", "scp", "sftp", "ssh-keygen", "ssh-add", "gpg",
    "gpg2", "rsync", "wget", "unzip", "zip", "printf", "echo", "test", "expr",
    "seq", "date", "sleep", "true", "false", "yes", "nl", "split", "comm",
    "join", "paste", "tsort", "od", "strings", "nohup", "timeout", "getopt",
    "id", "whoami", "uname", "hostname", "ps", "kill",
})

# Native, and conversion is DOING THE RIGHT THING: these want a Windows path.
WINDOWS_WANTS: frozenset[str] = frozenset({
    "notepad", "notepad++", "explorer", "start", "cmd", "code", "devenv",
    "msbuild", "reg", "regedit", "powershell", "pwsh", "wscript", "cscript",
    "rundll32", "mspaint", "write",
})

# Native AND a bridge into a POSIX world -> the far side needs the LITERAL
# path, so EVERY leading-slash argument is wrong, even a locally-mounted one.
POSIX_BRIDGE: frozenset[str] = frozenset({
    "wsl", "bash.exe", "docker", "docker-compose", "podman", "kubectl", "helm",
    "adb", "fastboot", "scrcpy", "vagrant", "multipass", "qemu-img", "busybox",
})

# Native, unix-looking, and the measured killer is the `rev:path` colon form.
GIT_LIKE: frozenset[str] = frozenset({"git", "git-lfs", "scalar"})

SHELL_BUILTINS: frozenset[str] = frozenset({
    "cd", "export", "local", "readonly", "declare", "typeset", "set", "unset",
    "source", ".", "read", "shift", "return", "exit", "trap", "wait", "alias",
    "unalias", "let", "getopts", "hash", "type", "ulimit", "umask", "pushd",
    "popd", "dirs", "jobs", "bg", "fg", "disown", "history", "mapfile",
    "readarray", "complete", "compgen", "shopt", "caller", "[", "[[", "help",
    "logout", "suspend", "times", "builtin", "enable",
})
SHELL_KEYWORDS: frozenset[str] = frozenset({
    "if", "then", "elif", "else", "fi", "while", "until", "for", "do", "done",
    "case", "esac", "in", "function", "select", "{", "}", "!", "coproc",
})
# The real callee is the NEXT token; advance past these.
PREFIX_WRAPPERS: frozenset[str] = frozenset({
    "sudo", "env", "time", "nohup", "command", "exec", "xargs", "timeout",
    "stdbuf", "nice", "ionice", "setsid", "doas", "watch", "strace", "ltrace",
})
# Word-list keywords: bash expands them itself, no process is ever spawned.
WORDLIST_KEYWORDS: frozenset[str] = frozenset({"for", "select", "case"})

# First path component that denotes a REAL local mount on this box, so the
# rewrite resolves back to the same object.  Derived from the measured mount
# table (`/` -> C:/Program Files/Git, /bin, /tmp, /c, /d) intersected with the
# directories that exist under the MSYS root.  Deliberately excludes /var,
# /home, /opt, /lib, /sbin, /proc, /mnt, /srv, /sdcard, /data, /api, /mcp.
HARMLESS_ROOTS: frozenset[str] = frozenset({
    "tmp", "bin", "usr", "etc", "dev", "cmd", "mingw64",
})

# ────────────────────────────────────────────────────────────────── shape rules

# A glob metacharacter suppresses conversion ENTIRELY, across every shape —
# MSYS declines to rewrite anything it reads as a pattern rather than a path.
# `[` counts even UNBALANCED: measured `/mnt/a[b` stays literal while
# `/mnt/plain` converts.  (`[` was missing from the inherited grammar and was
# caught by the argv-oracle fuzz as a false positive.)
_GLOB = re.compile(r"[?*\[]")

# MSYS virtual mounts that are NEVER converted.  Measured: `/proc`, `/proc/x`
# stay literal and `/proc/self/fd` is resolved BY MSYS to `/proc/<pid>/fd`,
# while `/procX`, `/procfs/a`, `/proc-thing/x` and `/PROC/x` all convert — so
# the match is on an EXACT, case-sensitive first component.
NEVER_CONVERTED_ROOTS: frozenset[str] = frozenset({"proc"})
_REDIR = re.compile(r"^\d*(?:>>|>|<<<|<|>&|&>)$")
_ENV_ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
_SUPPRESSOR_NAMES = ("MSYS_NO_PATHCONV", "MSYS2_ARG_CONV_EXCL")
# NOTE: there is deliberately no URL regex here. A URL contains `:`, and the
# measured colon rule already makes every colon-bearing token unconvertible
# unless it satisfies the path-list predicate. A separate scheme rule would be
# dead code — mutation-checked.


def _drive_or_root(p: str) -> str:
    """Leading-slash conversion, including the single-char drive sub-rule."""
    body = p[1:]
    first = body.split("/", 1)[0]
    if len(first) == 1 and first.isalpha():
        rest = body[2:] if len(body) > 1 else ""
        return f"{first.upper()}:/{rest}"
    return f"<GIT-ROOT>/{body}"


def _root_is_harmless(tok: str) -> bool:
    first = tok[1:].split("/", 1)[0]
    if len(first) == 1 and first.isalpha():
        return True
    return first.lower() in HARMLESS_ROOTS


def shape_leading_slash(tok: str):
    if tok.startswith("/") and not tok.startswith("//"):
        return _drive_or_root(tok), "leading-slash"
    return None


def shape_flag_form(tok: str):
    # Measured width between `-` and `/` is EXACTLY ONE character:
    #   -/x -> silent (0) · -p/mcp -> CONVERTS (1) · -ab/mcp, -Ipath/to -> silent
    if re.match(r"^-[^/]/", tok):
        i = tok.index("/")
        return tok[:i] + _drive_or_root(tok[i:]), "flag-form"
    return None


def shape_delimiter(tok: str):
    # A delimiter immediately before `/` triggers; a bare alphanumeric does not
    # (`origin/main`, `mnt/x` are untouched).  `--print-to-pdf=C:/Users/x` does
    # NOT match: the char before `/` is `:`, not `=`.
    m = re.search(r"[=@,](/)", tok)
    if m:
        i = m.start(1)
        if not tok[i:].startswith("//"):
            return tok[:i] + _drive_or_root(tok[i:]), "delimiter-form"
    return None


def shape_colon_list(tok: str):
    """>=2 colon-separated elements, every element contains `/`, and at least
    one NON-FIRST element starts with `/` or with `.` (excluding ./ and ../).
    The first-element asymmetry is real: `/a/b:c/d` is SILENT, `c/d:/a/b` is not.
    A `//` at the head of ANY element exempts the WHOLE token."""
    if ":" not in tok:
        return None
    parts = tok.split(":")
    if len(parts) < 2 or not all("/" in p for p in parts):
        return None
    if any(p.startswith("//") for p in parts):
        return None
    for p in parts[1:]:
        if p.startswith("/") or (p.startswith(".") and not re.match(r"^\.\.?/", p)):
            return tok.replace("/", "\\").replace(":", ";"), "colon-path-list"
    return None


def predict_conversion(tok: str):
    """-> (predicted_argv, shape_kind) or None if MSYS leaves this token alone.

    Rule order is measured, not arbitrary:
      1. a glob metachar suppresses every shape;
      2. an MSYS virtual mount (/proc) is never converted;
      3. a token containing `:` can ONLY convert via the colon-path-list
         predicate — measured across all four shapes:
             --out=/mcp   -> converts     --out=/mcp:x  -> SILENT
             -p/mcp       -> converts     -p/mcp:x      -> SILENT
             @/mcp        -> converts     @/mcp:x       -> SILENT
             /mnt/x       -> converts     /mnt/x:y      -> SILENT
             /mnt/x:/y    -> converts (qualifies as a path list)
         This subsumes the URL case (`http://…` contains `:`) and the
         already-Windows case (`C:/Users/x`).
    """
    if not tok:
        return None
    if _GLOB.search(tok):
        return None
    if tok.startswith("/") and tok[1:].split("/", 1)[0] in NEVER_CONVERTED_ROOTS:
        return None
    if ":" in tok:
        return shape_colon_list(tok)
    for shape in (shape_leading_slash, shape_flag_form, shape_delimiter):
        hit = shape(tok)
        if hit:
            return hit
    return None


# ───────────────────────────────────────────────────────── quote-aware splitter


@dataclass(frozen=True)
class Segment:
    start: int
    end: int
    text: str


def split_segments(cmd: str) -> list[Segment]:
    """Split on `;` `&&` `||` `|` and newline at depth 0, outside quotes.

    `$( … )` is NOT a separator here (unlike a pure detector): keeping it intact
    is what lets the E2 class be resolved.  Backslash-escapes, single quotes and
    double quotes are all tracked.
    """
    segs: list[Segment] = []
    i, n = 0, len(cmd)
    start = 0
    in_s = in_d = False
    depth = 0
    while i < n:
        c = cmd[i]
        if c == "\\" and i + 1 < n and not in_s:
            i += 2
            continue
        if c == "'" and not in_d:
            in_s = not in_s
            i += 1
            continue
        if c == '"' and not in_s:
            in_d = not in_d
            i += 1
            continue
        if in_s or in_d:
            i += 1
            continue
        if cmd.startswith("$(", i):
            depth += 1
            i += 2
            continue
        if c == ")" and depth > 0:
            depth -= 1
            i += 1
            continue
        if depth == 0:
            hit = None
            for op in ("&&", "||", ";", "|", "\n"):
                if cmd.startswith(op, i):
                    hit = op
                    break
            if hit is not None:
                segs.append(Segment(start, i, cmd[start:i]))
                i += len(hit)
                start = i
                continue
        i += 1
    segs.append(Segment(start, n, cmd[start:n]))
    return [s for s in segs if s.text.strip()]


def strip_heredocs(cmd: str) -> str:
    """Blank out heredoc BODIES.  They become stdin, never argv, so they are
    structurally immune — and scanning them is pure false-positive surface
    (the markdown/prose class).  Line count is preserved so spans stay valid."""
    lines = cmd.split("\n")
    out = list(lines)
    i = 0
    while i < len(lines):
        m = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", lines[i])
        i += 1
        if m:
            delim = m.group(2)
            while i < len(lines) and lines[i].strip() != delim:
                out[i] = ""
                i += 1
            if i < len(lines):
                i += 1
    return "\n".join(out)


# ────────────────────────────────────────────────────── static expansion (E1/2/4/5)

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_ECHO_SUBST = re.compile(r"\$\(\s*echo\s+([^\s()|;&<>$`\"']+)\s*\)")
_BACKTICK_ECHO = re.compile(r"`\s*echo\s+([^\s()|;&<>$`\"']+)\s*`")
_UNRESOLVED = re.compile(r"[$`]")


def resolve_token(tok: str, env: dict[str, str]) -> str | None:
    """Statically resolve a token to its post-expansion literal, or None.

    Handles: ${VAR}/$VAR against literal assignments seen earlier in the SAME
    command string, and side-effect-free `$(echo <literal>)` / backtick form.
    Returns None the moment anything unmodelled remains — we never guess.
    """
    out = _ECHO_SUBST.sub(lambda m: m.group(1), tok)
    out = _BACKTICK_ECHO.sub(lambda m: m.group(1), out)

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1) or m.group(2)
        if name in env:
            return env[name]
        raise KeyError(name)

    try:
        out = _VAR_RE.sub(_sub, out)
    except KeyError:
        return None
    if _UNRESOLVED.search(out):
        return None
    return out


# ─────────────────────────────────────────────────────────────────── decisions


@dataclass(frozen=True)
class Finding:
    segment_index: int
    callee: str
    tier: str
    token: str            # token as written in the command
    effective: str        # post-static-expansion value MSYS will actually see
    predicted: str        # what argv would become without enforcement
    kind: str
    severity: str
    reason: str
    resolution: str       # "literal" | "expanded"


@dataclass(frozen=True)
class Decision:
    action: str                       # see ACTIONS
    rewritten: str | None = None
    findings: tuple[Finding, ...] = ()
    unresolvable: tuple[str, ...] = ()
    reason: str = ""
    protected: tuple[str, ...] = ()
    elapsed_us: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


ACTIONS = ("noop", "protect", "optout", "not-windows", "unsafe-shape", "error")

_OPTOUT_ENV = "CLAUDE_MSYS_ENFORCE"
_TELEMETRY_ENV = "CLAUDE_MSYS_TELEMETRY"
_OPTOUT_MARKER = re.compile(r"#\s*msys:\s*(off|allow|no-enforce)\b", re.I)


def _is_windows(env: dict[str, str]) -> bool:
    forced = env.get("CLAUDE_MSYS_FORCE_PLATFORM")
    if forced:
        return forced.lower() in ("nt", "windows", "win32")
    return os.name == "nt"


def _basename(tok: str) -> str:
    base = os.path.basename(tok.replace("\\", "/")).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base


def classify_callee(tok: str):
    """-> (tier, severity, reason, is_bridge) or None when the callee is immune."""
    base = _basename(tok)
    if base in SHELL_BUILTINS or base in SHELL_KEYWORDS:
        return None
    if base in MSYS_IMMUNE:
        return None
    if base in WINDOWS_WANTS:
        return None
    if base in POSIX_BRIDGE:
        return ("posix-bridge", "high",
                f"`{base}` bridges to a POSIX filesystem; the far side needs "
                f"the literal path", True)
    if base in GIT_LIKE:
        return ("git-like", "high",
                f"`{base}` links msvcrt, not msys — fully exposed despite "
                f"living in /mingw64/bin", False)
    return ("native-unknown", "medium",
            f"`{base}` is not a known msys-linked callee", False)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _segment_is_simple(toks: list[str], raw: str) -> bool:
    """Only splice an env prefix onto a SIMPLE command.  A compound (`if …`,
    `( … )`, `{ … }`, a bare redirect) would become a syntax error."""
    if not toks:
        return False
    stripped = raw.lstrip()
    if stripped[:1] in ("(", "{", "&", ">", "<"):
        return False
    first = _basename(toks[0])
    if first in SHELL_KEYWORDS or first in WORDLIST_KEYWORDS:
        return False
    return True


def plan(command: str, env: dict[str, str] | None = None) -> Decision:
    """Decide what, if anything, to do about MSYS path conversion in *command*.

    Never raises. Returns a Decision whose `rewritten` is None unless
    action == "protect".
    """
    t0 = time.perf_counter()
    env = dict(os.environ) if env is None else dict(env)
    try:
        return _plan_inner(command, env, t0)
    except Exception as exc:                       # pragma: no cover - fail-open
        return Decision(action="error", reason=f"{type(exc).__name__}: {exc}",
                        elapsed_us=int((time.perf_counter() - t0) * 1e6))


def _plan_inner(command: str, env: dict[str, str], t0: float) -> Decision:
    def done(**kw) -> Decision:
        kw.setdefault("elapsed_us", int((time.perf_counter() - t0) * 1e6))
        return Decision(**kw)

    if not _is_windows(env):
        return done(action="not-windows",
                    reason="os.name != 'nt' — MSYS conversion cannot occur")
    if env.get(_OPTOUT_ENV, "").strip() in ("0", "off", "false", "no"):
        return done(action="optout",
                    reason=f"{_OPTOUT_ENV} disables enforcement")
    if _OPTOUT_MARKER.search(command):
        return done(action="optout",
                    reason="in-command `# msys:off` marker")
    if not command.strip():
        return done(action="noop", reason="empty command")

    scanned = strip_heredocs(command)
    segments = split_segments(scanned)

    shell_env: dict[str, str] = {}
    findings: list[Finding] = []
    unresolvable: list[str] = []
    notes: list[str] = []
    # segment index -> ordered, de-duplicated EXCL prefixes
    per_segment: dict[int, list[str]] = {}
    suppressed_globally = False

    for si, seg in enumerate(segments):
        raw = seg.text
        try:
            toks = shlex.split(raw, posix=True)
        except ValueError:
            notes.append(f"segment {si}: unbalanced quoting — skipped")
            continue
        if not toks:
            continue

        # ── leading env assignments: record literals, detect suppressors ──
        idx = 0
        local_suppressed = False
        while idx < len(toks):
            m = _ENV_ASSIGN.match(toks[idx])
            if not m:
                break
            name, value = m.group(1), m.group(2)
            if name in _SUPPRESSOR_NAMES:
                local_suppressed = True
            else:
                resolved = resolve_token(value, shell_env)
                if resolved is not None:
                    shell_env[name] = resolved
            idx += 1

        # A bare `VAR=x` / `export VAR=x` statement: pure assignment, no callee.
        if idx >= len(toks):
            if local_suppressed:
                suppressed_globally = True
            continue
        if _basename(toks[idx]) == "export":
            for t in toks[idx + 1:]:
                m = _ENV_ASSIGN.match(t)
                if not m:
                    continue
                if m.group(1) in _SUPPRESSOR_NAMES:
                    suppressed_globally = True
                else:
                    resolved = resolve_token(m.group(2), shell_env)
                    if resolved is not None:
                        shell_env[m.group(1)] = resolved
            continue

        if local_suppressed:
            continue          # explicit per-command opt-out already present
        if suppressed_globally:
            continue          # an earlier `export MSYS_NO_PATHCONV=…` covers us

        # ── resolve the real callee past wrappers ──
        while idx < len(toks) and _basename(toks[idx]) in PREFIX_WRAPPERS:
            idx += 1
        if idx >= len(toks):
            continue
        callee_tok = toks[idx]
        callee = _basename(callee_tok)

        if callee in WORDLIST_KEYWORDS:
            continue

        # ── E5: `eval '<literal>'` — recurse into the literal body ──
        if callee == "eval":
            body_parts = [t for t in toks[idx + 1:]]
            if len(body_parts) == 1 and not _UNRESOLVED.search(body_parts[0]):
                sub = _plan_inner(body_parts[0], dict(env), t0)
                if sub.findings:
                    for f in sub.findings:
                        findings.append(Finding(
                            segment_index=si, callee=f.callee, tier=f.tier,
                            token=f.token, effective=f.effective,
                            predicted=f.predicted, kind=f.kind,
                            severity=f.severity, reason=f.reason,
                            resolution="expanded"))
                    if _segment_is_simple(toks, raw):
                        bucket = per_segment.setdefault(si, [])
                        for p in sub.protected:
                            if p not in bucket:
                                bucket.append(p)
            elif body_parts:
                unresolvable.append(f"eval body not a single literal: {raw[:80]}")
            continue

        verdict = classify_callee(callee_tok)
        if verdict is None:
            continue
        tier, severity, reason, is_bridge = verdict

        skip_next = False
        for tok in toks[idx + 1:]:
            if skip_next:
                skip_next = False
                continue
            if _REDIR.match(tok):
                skip_next = True     # redirect TARGET — bash resolves it, not argv
                continue

            effective = resolve_token(tok, shell_env)
            if effective is None:
                if _UNRESOLVED.search(tok):
                    unresolvable.append(tok)
                    # The substitution's OWN arguments are still analysable.
                    inner = re.findall(r"\$\((.+?)\)", tok)
                    for body in inner:
                        sub = _plan_inner(body, dict(env), t0)
                        findings.extend(sub.findings)
                continue

            hit = predict_conversion(effective)
            if hit is None:
                continue
            predicted, kind = hit
            # A locally-mounted root rewrites back to the SAME object, so the
            # command still works — unless the callee bridges to a POSIX world.
            if kind == "leading-slash" and not is_bridge and _root_is_harmless(effective):
                continue

            findings.append(Finding(
                segment_index=si, callee=callee, tier=tier, token=tok,
                effective=effective, predicted=predicted, kind=kind,
                severity=severity, reason=reason,
                resolution="literal" if effective == tok else "expanded"))

            if _segment_is_simple(toks, raw):
                bucket = per_segment.setdefault(si, [])
                if effective not in bucket:
                    bucket.append(effective)
            else:
                notes.append(f"segment {si}: not a simple command — not rewritten")

    if not findings:
        return done(action="noop", unresolvable=tuple(unresolvable),
                    reason="no harmful conversion predicted",
                    notes=tuple(notes))
    if not per_segment:
        return done(action="unsafe-shape", findings=tuple(findings),
                    unresolvable=tuple(unresolvable), notes=tuple(notes),
                    reason="conversion predicted but no segment was safe to rewrite")

    # ── splice `MSYS2_ARG_CONV_EXCL='…' ` at each affected segment's head ──
    protected: list[str] = []
    edits: list[tuple[int, str]] = []
    for si, prefixes in sorted(per_segment.items()):
        seg = segments[si]
        offset = len(seg.text) - len(seg.text.lstrip())
        value = ";".join(prefixes)
        edits.append((seg.start + offset,
                      f"MSYS2_ARG_CONV_EXCL={_shell_quote(value)} "))
        protected.extend(prefixes)

    out = command
    for pos, ins in sorted(edits, reverse=True):
        out = out[:pos] + ins + out[pos:]

    return done(action="protect", rewritten=out, findings=tuple(findings),
                unresolvable=tuple(unresolvable), protected=tuple(protected),
                notes=tuple(notes),
                reason=f"protected {len(protected)} argument(s) from MSYS "
                       f"path conversion via per-argument MSYS2_ARG_CONV_EXCL")


# ─────────────────────────────────────────────────────────────────── telemetry

_SECRETISH = re.compile(
    r"(?i)(?:ghp_|gho_|github_pat_|sk-|xox[baprs]-|AKIA)[A-Za-z0-9_\-]{6,}")
_MAX_BYTES = 512 * 1024


def _redact(text: str, limit: int = 160) -> str:
    return _SECRETISH.sub("<REDACTED>", text)[:limit]


def telemetry_path(env: dict[str, str] | None = None) -> str | None:
    """Resolve the telemetry sink, or None when telemetry is off.

    OPT-IN BY DESIGN. An earlier revision defaulted to
    `$USERPROFILE/.claude/state/msys-pathconv/decisions.jsonl`, which meant
    merely RUNNING this hook — including from the sibling `test_hooks.py`
    suite, which inherits the ambient environment — silently created and wrote
    to a live state directory for a hook that is not even installed. Measured:
    27 records across 3 test runs. A not-yet-installed component must not write
    to live state, so the default is now OFF and the installer supplies the path.
    """
    env = os.environ if env is None else env
    override = (env.get(_TELEMETRY_ENV) or "").strip()
    if not override or override.lower() in ("0", "off", "false", "no"):
        return None
    return override


def record(decision: Decision, command: str,
           env: dict[str, str] | None = None) -> str | None:
    """Append one bounded JSONL decision record. Returns the path, or None."""
    try:
        path = telemetry_path(env)
        if not path:
            return None
        record_obj = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "action": decision.action,
            "reason": decision.reason,
            "elapsed_us": decision.elapsed_us,
            "protected": [_redact(p) for p in decision.protected],
            "unresolvable": len(decision.unresolvable),
            "findings": [
                {"callee": f.callee, "tier": f.tier, "kind": f.kind,
                 "severity": f.severity, "resolution": f.resolution,
                 "token": _redact(f.token), "effective": _redact(f.effective),
                 "predicted": _redact(f.predicted)}
                for f in decision.findings
            ],
            "command_len": len(command),
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.getsize(path) > _MAX_BYTES:
                os.replace(path, path + ".1")
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record_obj, ensure_ascii=False) + "\n")
        return path
    except Exception:
        return None


def explain(decision: Decision) -> str:
    """Actionable, human-readable reason string (goes into additionalContext)."""
    if decision.action != "protect":
        return decision.reason
    lines = ["[msys-pathconv] ENFORCED — MSYS would have rewritten these "
             "arguments before the program saw them:"]
    for f in decision.findings:
        via = "" if f.resolution == "literal" else f"  (via expansion of `{f.token}`)"
        lines.append(f"  `{f.effective}`{via}")
        lines.append(f"    would become  `{f.predicted}`   [{f.kind}, {f.severity}]")
        lines.append(f"    why: {f.reason}")
    lines.append("  FIX APPLIED: per-argument MSYS2_ARG_CONV_EXCL prefix "
                 "(siblings still convert normally).")
    if decision.unresolvable:
        lines.append(f"  NOT CHECKED (unresolvable statically): "
                     f"{len(decision.unresolvable)} token(s).")
    return "\n".join(lines)
