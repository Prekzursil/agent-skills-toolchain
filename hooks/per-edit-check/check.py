#!/usr/bin/env python3
"""PostToolUse(Edit|Write|MultiEdit): per-edit secret gate + fast syntax/lint check.

After each file edit, runs a FAST, time-boxed (~8 s) checker on just the
changed file and injects any failures immediately — addressing them at the
cheapest point in the edit-fix loop.

Write-path secret gate (AGENTS.md §9)
─────────────────────────────────────
Before the linter runs, the changed file is scanned for high-confidence
hardcoded-credential shapes (AWS access key IDs, PEM/PGP private-key armor,
OpenAI / GitHub / Slack / Google / Stripe keys).  A match blocks the write
under a four-part contract: exit 2, the reason on stderr, stdout clean, and
the reason names the credential TYPE and line number without ever echoing the
matched bytes.  All four are asserted by
``test_secrets.py::test_main_blocks_secret_write``, and each was verified by
inverting it in this file and confirming the suite goes red.  The no-echo part
is the load-bearing one: this hook's stderr is injected into agent context, so
a reason that quoted the offending text would print the very credential it
caught.  A credential-shaped string is treated as a placeholder (and allowed)
when a marker such as ``EXAMPLE`` or ``YOUR_KEY`` appears on the same line
WITHIN 24 characters of the match; a marker further away is incidental prose
and does not exempt.

Unlike the linter the secret gate is NOT skipped for scratchpad/temp paths —
a credential written there still lands on disk.  It is skipped for files over
MAX_FILE_BYTES, consistent with the rest of the hook.

Language dispatch
─────────────────
  .py           ruff check <file>   (fast linter; falls back to py_compile
                                     if ruff absent — syntax check only)
  .js/.mjs/.cjs/.jsx  node --check <file>  (syntax only; skip if node absent)
  .ts/.tsx      skipped  — tsc --noEmit too slow; node --check won't parse TS
  .json         pure-Python json.load  (always available)
  .yaml/.yml    yaml.safe_load  (skip silently if pyyaml absent)
  .java         pure-Python delimiter-balance heuristic, ADVISORY only
  .c/.cc/.cpp/.cxx/.h/.hh/.hpp
                pure-Python scan for the constructs rules/cpp/security.md
                forbids (raw new/delete, malloc/free, strcpy/strcat/sprintf,
                reinterpret_cast).  Advisory inject, never a block.  clang-tidy
                and cppcheck are NOT invoked — both need a compile database and
                blow the ~8 s budget.
  .php          pint --test, else php-cs-fixer --dry-run, else php -l (the two
                formatters rules/php/coding-style.md:24 names); when none is on
                PATH, a stdlib PSR-12 subset so a toolless box is not silently
                green.
  .rs           skipped  — cargo check too heavy for a per-edit hook
  everything    skipped, SILENTLY — the catch-all in ``_run_check``.  ``.kt``,
  else          ``.kts``, ``.swift``, ``.dart``, ``.go``, ``.java``, ``.php``,
                ``.pl`` … all return the same ``([], False)`` as the three
                deliberate skips above and as a genuinely clean file.  This
                hook covers the five families listed here and NOTHING else.
                In particular it does NOT implement ``rules/<lang>/hooks.md``:
                those files open with "Configure in ``~/.claude/settings.json``"
                and are portable guidance for whoever operates a project in
                that language, not a specification for this hook.  Adding a
                language means adding a fast, always-available checker here —
                a per-edit hook cannot shell out to tsc / ktlint / swiftlint.
                The write-path secret gate above is the one check that DOES
                run for every extension.

Every other extension (.go, .rb, .cs, .kt, .swift, ...) is a deliberate silent
skip: no checker for it is both always-available and cheap enough here.

Exit protocol (AGENTS.md §6)
─────────────────────────────
  ruff lint issues             → exit 0 + additionalContext inject (soft nudge)
  hardcoded credential         → exit 2 + reason on stderr, stdout clean
  py_compile / node / JSON
    syntax errors              → exit 2 + reason on stderr, stdout clean

  There is NO ``decision:block`` JSON on either exit-2 path and there never
  was: Claude Code ignores stdout at exit 2, so the emit branch writes plain
  text to stderr (see the comment there).  An earlier version of this docstring
  advertised such a payload; it was never emitted (measured: stdout == "").

  AGENTS.md §6 reserves exit 2 for "irreversible/dangerous only — destructive
  git ops, secrets in code, force-push to main".  The credential gate is
  squarely inside that list.  The SYNTAX-error block is NOT, and this is a
  known, unresolved tension rather than a settled reading: ``test_check.py``
  enshrines exit 2 for syntax in five assertions, and
  ``test_python_ruff_e999_syntax_error_blocks`` records that soft-injecting
  E999 was previously classified as a bug ("M2b").  Reconciling the two is a
  policy decision for the contract owner — do not silently flip either side.
  Settling experiment: soft-inject syntax errors behind an env flag for a week
  and measure whether the edit-fix loop degrades.

FAIL-OPEN: every unhandled error → exit 0, no output.
Opt-outs:  env  PER_EDIT_CHECK=off    (any capitalisation) — whole hook
           env  PER_EDIT_SECRETS=off  (any capitalisation) — secret gate only
           file .disabled  (sentinel in this hook directory) — whole hook
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

HOOKDIR = os.path.dirname(os.path.abspath(__file__))
MAX_FILE_BYTES = 512 * 1024  # 512 KB — skip generated/binary-heavy files
TIMEOUT = 8  # seconds — hard cap per subprocess call


# ── write-path secret gate (AGENTS.md §9) ────────────────────────────────────

# Characters within which a placeholder marker on the SAME line exempts a
# credential-shaped match.  Bounded on purpose: a real key sharing a line with
# an unrelated far-away "# example" comment must still block.
MARKER_PROXIMITY = 24

# Lowercase substrings that mark a credential-shaped string as documentation
# or a fill-me-in placeholder rather than a live credential.
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "your_key",
    "your-key",
    "yourkey",
    "your_token",
    "your-token",
    "redacted",
    "dummy",
    "fake",
    "notarealkey",
    "not_a_real_key",
)

# High-confidence credential shapes only.  Every entry must be specific enough
# that a match is almost certainly a real credential — this gate BLOCKS, so a
# false positive costs the user an edit.  Generic "password = ..." heuristics
# are deliberately excluded.
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private key material",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    ),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9_-]{40,}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("Stripe secret key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b")),
)


def _is_placeholder(line: str, start: int, end: int) -> bool:
    """True when a placeholder marker sits within MARKER_PROXIMITY of the match.

    ``start``/``end`` are the match span in *line*.  A marker that overlaps the
    match has gap 0 -- which is the common case for published documentation
    samples, whose own trailing ``EXAMPLE`` is itself one of
    ``PLACEHOLDER_MARKERS``.  The literal sample string is deliberately NOT
    quoted here: the repo SAST rule ``generic-aws-access-key-id`` matches it and
    cannot distinguish a credential from prose about one.  See
    ``test_aws_example_exempt`` for the executable form of this case.
    """
    low = line.lower()
    for marker in PLACEHOLDER_MARKERS:
        pos = low.find(marker)
        while pos != -1:
            gap = max(start - (pos + len(marker)), pos - end, 0)
            if gap <= MARKER_PROXIMITY:
                return True
            pos = low.find(marker, pos + 1)
    return False


def _scan_secrets(fp: str) -> str | None:
    """Scan *fp* for hardcoded-credential shapes.

    Returns a human-readable reason for the FIRST non-placeholder match, or
    ``None`` when the file is clean / too large / unreadable.  The reason names
    the credential type and line number and NEVER echoes the matched bytes.
    Fail-open: any unexpected error → ``None``.
    """
    try:
        if os.path.getsize(fp) > MAX_FILE_BYTES:
            return None
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                for label, pat in SECRET_PATTERNS:
                    for m in pat.finditer(line):
                        if _is_placeholder(line, m.start(), m.end()):
                            continue
                        return f"{label} on line {lineno}"
        return None
    except Exception:
        return None


# ── per-language checkers ────────────────────────────────────────────────────


def _check_python(fp: str) -> tuple[list[str], bool]:
    """Run ruff (preferred) or py_compile (fallback) on *fp*.

    Returns ``(issues, is_syntax_error)``.
    Fail-open: ``([], False)`` on any unexpected error.
    """
    try:
        ruff = shutil.which("ruff")
        if ruff:
            r = subprocess.run(
                [ruff, "check", fp],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
            )
            if r.returncode != 0:
                raw = (r.stdout or "") + (r.stderr or "")
                lines = [
                    ln
                    for ln in raw.splitlines()
                    # strip the "Found N error(s)." summary line — it is noise
                    if ln.strip() and not ln.lstrip().startswith("Found")
                ]
                # E999 is ruff's syntax/parse error code — treat as a hard
                # syntax break so it blocks (exit 2) just like py_compile would.
                is_syntax = any("E999" in ln for ln in lines)
                return (lines or ["lint error"]), is_syntax
            return [], False

        # fallback: py_compile (syntax check only — always available)
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", fp],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
        if r.returncode != 0:
            lines = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
            return (lines or ["syntax error"]), True
        return [], False
    except Exception:
        return [], False


def _check_js(fp: str) -> tuple[list[str], bool]:
    """Run ``node --check`` on *fp* (syntax only).

    Returns ``(issues, is_syntax_error)``.
    Skip silently when node is not on PATH.
    """
    try:
        node = shutil.which("node")
        if not node:
            return [], False
        r = subprocess.run(
            [node, "--check", fp],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
        if r.returncode != 0:
            lines = [ln for ln in (r.stderr or "").splitlines() if ln.strip()]
            # Trust node's OWN error marker, exactly as _check_python trusts ruff's
            # E999. node has no JSX parser, so `node --check x.jsx` exits 1 with
            # `TypeError [ERR_UNKNOWN_FILE_EXTENSION]` and NOT a single SyntaxError
            # line -- an environment/loader failure, not a defect in the file. Classing
            # every nonzero exit as a syntax break hard-BLOCKED every valid JSX edit.
            if not any("SyntaxError" in ln for ln in lines):
                return [], False  # fail-open: loader/environment failure -> silent skip
            return (lines or ["parse error"]), True
        return [], False
    except Exception:
        return [], False


def _check_json(fp: str) -> tuple[list[str], bool]:
    """Attempt json.load on *fp*; report JSONDecodeError.

    Returns ``(issues, is_syntax_error)``.
    """
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            json.load(fh)
        return [], False
    except json.JSONDecodeError as exc:
        return [str(exc)], True
    except Exception:
        return [], False


def _check_yaml(fp: str) -> tuple[list[str], bool]:
    """Attempt yaml.safe_load on *fp*; skip silently if pyyaml is absent.

    Returns ``(issues, is_syntax_error)``.
    """
    try:
        import yaml  # noqa: PLC0415 — conditional import

        with open(fp, encoding="utf-8", errors="replace") as fh:
            yaml.safe_load(fh)
        return [], False
    except ImportError:
        return [], False  # pyyaml not installed — skip
    except Exception as exc:
        return [str(exc)], True


# Java has no checker that is both always-available and cheap enough for a
# per-edit hook: google-java-format, Checkstyle, Maven and Gradle are JVM
# launches that blow the TIMEOUT budget, and `javac` on one file without the
# project classpath false-flags anything importing a sibling class.  What IS
# always available is the structural invariant every valid Java compilation
# unit satisfies -- (), [] and {} balance once comments and literals are
# removed.  A violation means the file cannot compile, so it is worth saying;
# but this is a scanner, not a parser, so it is reported as an ADVISORY
# (exit 0 + inject) and can never reject an edit.
_JAVA_PAIRS = {")": "(", "]": "[", "}": "{"}


def _java_delimiter_error(src: str) -> str | None:
    """Return a message when *src* has unbalanced ``()``/``[]``/``{}``, else None.

    Conservative by construction: any state this scanner cannot resolve
    unambiguously returns ``None`` rather than guessing -- an unterminated
    comment or literal, or the presence of a ``\\u`` escape (Java expands
    unicode escapes *before* lexing, so ``\\u007B`` really is an opening brace).
    """
    if "\\u" in src:
        return None  # a unicode escape can encode a delimiter -- refuse to guess
    stack: list[tuple[str, int]] = []
    i, line, n = 0, 1, len(src)
    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j == -1 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j == -1:
                return None  # unterminated block comment
            line += src.count("\n", i, j)
            i = j + 2
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            if j == -1:
                return None  # unterminated text block
            line += src.count("\n", i, j)
            i = j + 3
        elif ch in ('"', "'"):
            j = i + 1
            while j < n and src[j] != ch:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    return None  # unterminated string / char literal
                j += 1
            if j >= n:
                return None
            i = j + 1
        elif ch in ("(", "[", "{"):
            stack.append((ch, line))
            i += 1
        elif ch in _JAVA_PAIRS:
            if not stack or stack[-1][0] != _JAVA_PAIRS[ch]:
                return f"unmatched closing '{ch}' on line {line}"
            stack.pop()
            i += 1
        else:
            i += 1
    if stack:
        opener, opened_at = stack[0]
        return f"unclosed '{opener}' opened on line {opened_at}"
    return None


def _check_java(fp: str) -> tuple[list[str], bool]:
    """Structural sanity check for *fp* (delimiter balance only).

    Returns ``(issues, is_syntax_error)``.  ``is_syntax_error`` is always
    ``False``: a heuristic must nudge, never block.
    Fail-open: ``([], False)`` on any unexpected error.
    """
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        msg = _java_delimiter_error(src)
        if msg:
            return [f"{msg} - this file cannot compile"], False
        return [], False
    except Exception:
        return [], False


# ── C / C++ memory + buffer policy (rules/cpp/security.md) ───────────────────

C_EXT = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp")

# Each entry: (compiled pattern, message).  Every rule below is a verbatim
# "Never use ..." demand from rules/cpp/security.md:15-32, so a hit is a stated
# policy violation, not a taste call.  clang-tidy/cppcheck are deliberately NOT
# invoked: both need the compile database and blow the ~8 s per-edit budget.
_C_RULES = (
    (re.compile(r"\bnew\s+[A-Za-z_:][\w:<>]*"), "raw `new` — use a smart pointer"),
    (
        re.compile(r"\bdelete\s*(?:\[\s*\])?\s+[A-Za-z_]"),
        "raw `delete` — use a smart pointer",
    ),
    (
        re.compile(r"\b(?:m|c|re)alloc\s*\("),
        "`malloc`/`calloc`/`realloc` — use C++ allocation",
    ),
    (re.compile(r"\bfree\s*\("), "`free` — use C++ allocation"),
    (re.compile(r"\bstrcpy\s*\("), "`strcpy` — use std::string or fmt::format"),
    (re.compile(r"\bstrcat\s*\("), "`strcat` — use std::string or fmt::format"),
    (re.compile(r"\bsprintf\s*\("), "`sprintf` — use std::string or fmt::format"),
    (
        re.compile(r"\breinterpret_cast\s*<"),
        "`reinterpret_cast` — avoid unless unavoidable",
    ),
)

_C_LINE_COMMENT = re.compile(r"//.*$", re.MULTILINE)
_C_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_C_STRING = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")


def _strip_c_noise(line: str) -> str:
    """Blank out string literals and line comments so a mention is not a use.

    `printf("call free() here")` and `// never call strcpy` must not be flagged;
    only real code is scanned.
    """
    return _C_STRING.sub('""', _C_LINE_COMMENT.sub("", line))


def _check_c(fp: str) -> tuple[list[str], bool]:
    """Flag constructs rules/cpp/security.md forbids.  Advisory, never blocking.

    Returns ``(issues, is_syntax_error)`` — ``is_syntax_error`` is always False:
    these are policy findings, so they inject rather than block the write.
    """
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            src = fh.read()
        # Block comments can span lines, so strip them before splitting.
        src = _C_BLOCK_COMMENT.sub("", src)
        issues: list[str] = []
        for lineno, raw in enumerate(src.splitlines(), 1):
            code = _strip_c_noise(raw)
            if not code.strip():
                continue
            for rx, msg in _C_RULES:
                if rx.search(code):
                    issues.append(f"{os.path.basename(fp)}:{lineno}: {msg}")
        return issues, False
    except Exception:
        return [], False


# ── PHP formatting policy (rules/php/coding-style.md, rules/php/hooks.md) ─────

_PHP_HEREDOC_OPEN = re.compile(r"<<<[~'\"]?\s*([A-Za-z_]\w*)")
_PHP_OPEN_TAG = re.compile(r"<\?(?!php\b|=)")


def _check_php_tool(fp: str) -> tuple[list[str], bool] | None:
    """Run Pint / PHP-CS-Fixer / ``php -l`` if present; None when none is.

    rules/php/coding-style.md:24 names Pint and PHP-CS-Fixer by name, so they are
    preferred over the built-in subset check whenever they are actually on PATH.
    """
    for exe, args, hard in (
        ("pint", ["--test", fp], False),
        ("php-cs-fixer", ["fix", "--dry-run", "--diff", fp], False),
        ("php", ["-l", fp], True),
    ):
        found = shutil.which(exe)
        if not found:
            continue
        try:
            r = subprocess.run(
                [found, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
            )
        except Exception:
            return [], False
        if r.returncode == 0:
            return [], False
        out = (r.stdout or "") + (r.stderr or "")
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return (lines[:20] or [f"{exe} reported a problem"]), hard
    return None


def _check_php_psr12(fp: str) -> tuple[list[str], bool]:
    """Stdlib-only PSR-12 subset, so a toolless box is not silently green.

    Only high-confidence, deterministic rules are implemented; heredoc/nowdoc
    bodies and inline-HTML regions are excluded so their formatting is not
    misread as PHP indentation.
    """
    try:
        with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
            raw = fh.read()
    except Exception:
        return [], False

    issues: list[str] = []
    text = raw.replace("\r\n", "\n")
    stripped = text.rstrip()

    if stripped.endswith("?>"):
        issues.append("PSR-12 §2.2: omit the closing `?>` in a PHP-only file")
    if _PHP_OPEN_TAG.search(text):
        issues.append("PSR-12 §2.2: use the long `<?php` open tag, not `<?`")
    # PSR-12 §2.1 (LF line endings) is deliberately NOT checked here: this repo is
    # Windows-primary and .php is not normalised in .gitattributes, so the rule
    # would fire on essentially every local edit. That is noise in an advisory
    # hook, and a real Pint / PHP-CS-Fixer run (preferred above) reports it anyway.

    in_php = False
    heredoc: str | None = None
    bad_indent = 0
    tabbed = 0
    for line in text.split("\n"):
        if heredoc is not None:
            if line.strip().rstrip(";,").strip() == heredoc:
                heredoc = None
            continue
        if not in_php:
            if "<?php" in line or "<?=" in line:
                in_php = True
            else:
                continue
        elif "?>" in line:
            in_php = False
        m = _PHP_HEREDOC_OPEN.search(line)
        if m:
            heredoc = m.group(1)
            continue
        if not line.strip():
            continue
        indent = line[: len(line) - len(line.lstrip())]
        if "\t" in indent:
            tabbed += 1
        elif len(indent) % 4:
            bad_indent += 1
    if tabbed:
        issues.append(f"PSR-12 §2.4: {tabbed} line(s) indent with tabs, not 4 spaces")
    if bad_indent:
        issues.append(
            f"PSR-12 §2.4: {bad_indent} line(s) not indented in multiples of 4 spaces"
        )
    return issues, False


def _check_php(fp: str) -> tuple[list[str], bool]:
    """Prefer the real formatter; fall back to the built-in PSR-12 subset."""
    try:
        via_tool = _check_php_tool(fp)
        if via_tool is not None:
            return via_tool
        return _check_php_psr12(fp)
    except Exception:
        return [], False


def _run_check(fp: str) -> tuple[list[str], bool]:
    """Dispatch to the right checker by extension.

    Returns ``(issues, is_syntax_error)``.
    Unknown / unsupported extensions → ``([], False)`` — silent skip.
    """
    ext = os.path.splitext(fp)[1].lower()
    if ext == ".py":
        return _check_python(fp)
    if ext in (".js", ".mjs", ".cjs", ".jsx"):
        return _check_js(fp)
    if ext in (".ts", ".tsx"):
        return [], False  # tsc too slow; node --check won't parse TS
    if ext == ".json":
        return _check_json(fp)
    if ext in (".yaml", ".yml"):
        return _check_yaml(fp)
    if ext == ".java":
        return _check_java(fp)
    if ext in C_EXT:
        return _check_c(fp)
    if ext == ".php":
        return _check_php(fp)
    if ext == ".rs":
        return [], False  # cargo check too heavy for per-edit
    return [], False


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    try:
        # ── opt-outs ──────────────────────────────────────────────────────────
        if os.environ.get("PER_EDIT_CHECK", "").lower() == "off":
            return 0
        if os.path.exists(os.path.join(HOOKDIR, ".disabled")):
            return 0

        # ── gate: only for file-editing tools ────────────────────────────────
        if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
            return 0

        fp = (data.get("tool_input") or {}).get("file_path")
        if not fp:
            return 0
        if not os.path.isfile(fp):
            return 0

        # ── write-path secret gate (AGENTS.md §9) ────────────────────────────
        # Runs BEFORE the scratchpad skip and the linter: a credential written
        # to a throwaway path still lands on disk, and a hardcoded secret is a
        # higher-severity finding than any lint issue.
        if os.environ.get("PER_EDIT_SECRETS", "").lower() != "off":
            reason = _scan_secrets(fp)
            if reason:
                print(
                    f"[per-edit-check] BLOCKED: {reason} of "
                    f"{os.path.basename(fp)} looks like a hardcoded credential.\n"
                    "Secrets must never be written into source (AGENTS.md §9) — "
                    "read it from an environment variable or a secret manager.\n"
                    "If this is a placeholder, mark the line (EXAMPLE / "
                    "YOUR_KEY / PLACEHOLDER); to override, set "
                    "PER_EDIT_SECRETS=off.",
                    file=sys.stderr,
                )
                return 2

        # ── skip throwaway scratch trees (not deliverables) ──────────────────
        _norm = fp.replace("\\", "/").lower()
        if any(
            seg in _norm for seg in ("/scratchpad/", "/temp/claude/", "/.write-probe")
        ):
            return 0

        # ── skip huge files (generated / data / compiled assets) ─────────────
        try:
            if os.path.getsize(fp) > MAX_FILE_BYTES:
                return 0
        except OSError:
            return 0

        # ── run the checker ──────────────────────────────────────────────────
        issues, is_syntax_err = _run_check(fp)
        if not issues:
            return 0

        # ── format the message ───────────────────────────────────────────────
        fname = os.path.basename(fp)
        n = len(issues)
        preview = issues[:5]
        body = "\n".join(preview)
        if n > 5:
            body += f"\n... and {n - 5} more"
        msg = f"[per-edit-check] found {n} issue(s) in {fname}:\n{body}"

        # ── emit ─────────────────────────────────────────────────────────────
        if is_syntax_err:
            # Hard block: Claude Code reads STDERR on exit 2; any JSON on
            # stdout is silently ignored at that exit code.  Write the
            # human-readable reason to stderr so the user actually sees it.
            print(msg, file=sys.stderr)
            return 2

        # Soft inject: lint issues — nudge without blocking.
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": msg,
                    }
                }
            )
        )
        return 0

    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
