#!/usr/bin/env python3
"""
repo_map — a PageRank-over-symbol-references grounding pack.
============================================================

`rules/common/fan-out-contract.md` §A11 PRESCRIBES injecting a shared grounding
pack into every fan-out ("16/25 agents read the same `codex_monitor.py`; one
agent re-read `hub.py` x22"), but nothing in this repo generated one. This is
that generator.

Technique
---------
Aider's repo map (https://aider.chat/2023/10/22/repomap.html):

  1. Extract, per file, the symbols it DEFINES and the symbols it REFERENCES.
  2. Build a directed graph over FILES: an edge ``referencer -> definer`` for
     every identifier one file uses and another defines, weighted by how often
     it is used and by how informative the identifier looks.
  3. Run PageRank over that graph. Central files bubble up.
  4. Distribute each file's rank across its outgoing edges, accumulating rank
     onto ``(definer_file, identifier)`` pairs — so the output ranks SYMBOLS,
     not just files.
  5. Emit the top-ranked definitions, binary-searching the prefix length so the
     rendered digest lands as close under a token budget as possible.

NO embeddings and NO vector store — the rejected class. Nothing is learned,
nothing is persisted, the same tree always produces the same bytes.

Deviation from Aider, stated up front
-------------------------------------
Aider extracts definitions/references with tree-sitter. `tree_sitter` is NOT
importable on this box and its grammars need a compiler toolchain on Windows,
so extraction here is a per-language REGEX + line-comment-stripping
approximation. That is strictly less accurate than a parse, and **the size of
that gap has NOT been measured** (tree_sitter cannot be installed here to
compare against) — see ``README.md`` -> "Accuracy of the regex approximation"
for the known failure modes and the experiment that would settle it. No claim
in this module depends on the gap being small. The graph, ranking, budget and
rendering stages are unaffected by the choice.

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAMPING: float = 0.85
MAX_ITERATIONS: int = 200
TOLERANCE: float = 1e-12

#: Characters per token for the stdlib budget estimator.
#:
#: NOT the folklore 4. MEASURED against tiktoken cl100k_base over 13 digest
#: prefix sizes (1 .. 8,735 definitions) rendered from this repository:
#: 3.142 - 3.875 chars/token, worst case 3.142 on the full digest. A divisor of
#: 4 UNDER-counted every sample by 15-25%, which is the one direction that
#: silently blows a budget, so the divisor is 3 (~4.5% margin at the worst
#: observed point). One corpus, one encoding — a caller with a real tokenizer
#: should pass `--tiktoken <enc>` / `token_counter=` and skip the estimate.
CHARS_PER_TOKEN: int = 3

#: Files larger than this are skipped outright (a generated bundle contributes
#: noise, not structure, and dominates the regex cost).
MAX_FILE_BYTES: int = 1_000_000

#: Longest rendered signature line before truncation.
MAX_SIGNATURE_CHARS: int = 120

#: An identifier defined in more than this many files is dropped from the graph.
#: Two reasons, both measured on this repository: (a) `error`, `session_id`,
#: `read_text` carry no information about STRUCTURE — every module has one — yet
#: they outranked real architecture; (b) an ident defined in D files and
#: referenced by R files creates D*R edges, and these ubiquitous names alone
#: produced 1,005,573 edges out of a 1,386-node graph. Dropping them cut the
#: edge count by ~94% and the wall time by ~4x. Aider only DOWN-WEIGHTS them
#: (x0.1); that was measured here as insufficient — they still ranked top-12.
MAX_DEFINER_FILES: int = 10

#: Identifiers shorter than this never enter the graph. Measured: `a` and `f`
#: ranked in the top 12 of this repository because a file that defines `a` also
#: uses it dozens of times, and that self-reference handed the file's whole
#: rank to a one-letter local.
MIN_IDENT_LENGTH: int = 3

#: Weight multiplier for an edge NOT backed by an import. Bare name-matching is
#: weak evidence — a test double with a `def json` method absorbed every
#: `json.dumps` in this repository. Penalise rather than delete: dynamic
#: dispatch, re-exports and same-package use are real and would be lost.
WEAK_EDGE_FACTOR: float = 0.05

#: Fraction of an identifier's uses that must be ATTRIBUTE access (`x.name`)
#: before a module-level import stops counting as evidence for that symbol.
#: Not 1.0: a single unrelated local named `name` is enough to defeat an
#: all-or-nothing test, and that is exactly what was measured.
ATTRIBUTE_DOMINANCE: float = 0.5

#: Directory names never descended into by the filesystem-walk fallback.
#: (The `git ls-files` path does not need these — .gitignore already covers it.)
EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        "out",
        "vendor",
        "site-packages",
        ".idea",
        ".vscode",
    }
)


# ---------------------------------------------------------------------------
# Language table
# ---------------------------------------------------------------------------

_DEFAULT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
#: PowerShell/shell identifiers may contain hyphens (`Invoke-Thing`).
_HYPHEN_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)*")


#: Import-shape patterns. Group 1 is a module SPECIFIER; where a second group
#: exists it is a comma-separated list of imported NAMES.
_PY_FROM_IMPORT = re.compile(r"^\s*from\s+([.\w]+)\s+import\s+(.+)$")
_PY_IMPORT = re.compile(r"^\s*import\s+([.\w]+(?:\s*,\s*[.\w]+)*)")
_JS_FROM = re.compile(r"""from\s+['"]([^'"]+)['"]""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_BRACE_NAMES = re.compile(r"^\s*(?:import|const|let|var)\s*\{([^}]*)\}")
_JS_DEFAULT_IMPORT = re.compile(r"^\s*import\s+([A-Za-z_$][\w$]*)")
_JS_REQUIRE_BINDING = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:await\s+)?"
    r"(?:require\(|import\()"
)
_NAME_IN_LIST = re.compile(r"[A-Za-z_$][\w$]*")


@dataclass(frozen=True)
class Language:
    """Per-language extraction rules."""

    name: str
    definitions: tuple[re.Pattern[str], ...]
    comment_markers: tuple[str, ...]
    keywords: frozenset[str]
    token: re.Pattern[str] = _DEFAULT_TOKEN
    #: Lines matching any of these yield NO definition even if a definition
    #: pattern also matches — e.g. `const thing = require("./thing")` binds an
    #: IMPORT, not a new symbol, and counting it as one made import bindings
    #: outrank real code.
    definition_veto: tuple[re.Pattern[str], ...] = ()


_PY_KEYWORDS = frozenset(
    """
    False None True and as assert async await break class continue def del elif else except
    finally for from global if import in is lambda nonlocal not or pass raise return try while
    with yield self cls super print len str int float bool list dict set tuple type range
    """.split()
)

_JS_KEYWORDS = frozenset(
    """
    async await break case catch class const continue debugger default delete do else enum export
    extends false finally for function if implements import in instanceof interface let new null
    package private protected public return static super switch this throw true try typeof var
    void while with yield of as from type declare namespace readonly console require module
    """.split()
)

_SH_KEYWORDS = frozenset(
    """
    if then else elif fi for while until do done case esac function in select time coproc return
    echo local export readonly declare set unset shift source exit test true false
    """.split()
)

_PS_KEYWORDS = frozenset(
    """
    function param begin process end if elseif else switch foreach for while do until try catch
    finally throw return break continue filter workflow class enum using param Write-Output
    """.split()
)

_GO_KEYWORDS = frozenset(
    """
    break case chan const continue default defer else fallthrough for func go goto if import
    interface map package range return select struct switch type var nil true false iota make new
    len cap append string int int64 float64 bool error
    """.split()
)

_RS_KEYWORDS = frozenset(
    """
    as async await break const continue crate dyn else enum extern false fn for if impl in let
    loop match mod move mut pub ref return self Self static struct super trait true type unsafe
    use where while String Vec Option Result Some None Ok Err
    """.split()
)


LANGUAGES: dict[str, Language] = {}


def _register(extensions: Sequence[str], language: Language) -> None:
    for ext in extensions:
        LANGUAGES[ext] = language


_register(
    [".py", ".pyi"],
    Language(
        name="python",
        definitions=(
            re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"),
            re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),
            # A column-0 binding is a module-level symbol; an indented one is a local.
            re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=(?!=)"),
        ),
        comment_markers=("#",),
        keywords=_PY_KEYWORDS,
    ),
)

_register(
    [".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts"],
    Language(
        name="javascript",
        definitions=(
            re.compile(
                r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)"
            ),
            re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
            # Bindings must start at column 0. Allowing leading whitespace made every
            # `const timeoutMs = ...` INSIDE a function a module symbol, and those
            # locals then dominated the ranking on a real 1,386-file tree.
            re.compile(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"),
            re.compile(
                r"^(?:export\s+)?(?:declare\s+)?(?:interface|type|enum)\s+([A-Za-z_$][\w$]*)"
            ),
        ),
        comment_markers=("//",),
        keywords=_JS_KEYWORDS,
        definition_veto=(_JS_REQUIRE_BINDING,),
    ),
)

_register(
    [".sh", ".bash"],
    Language(
        name="shell",
        definitions=(
            re.compile(r"^\s*(?:function\s+)?([A-Za-z_][\w-]*)\s*\(\s*\)\s*\{"),
            re.compile(r"^\s*function\s+([A-Za-z_][\w-]*)"),
        ),
        comment_markers=("#",),
        keywords=_SH_KEYWORDS,
        token=_HYPHEN_TOKEN,
    ),
)

_register(
    [".ps1", ".psm1"],
    Language(
        name="powershell",
        definitions=(
            re.compile(r"^\s*function\s+([A-Za-z_][\w-]*)"),
            re.compile(r"^\s*class\s+([A-Za-z_]\w*)"),
        ),
        comment_markers=("#",),
        keywords=_PS_KEYWORDS,
        token=_HYPHEN_TOKEN,
    ),
)

_register(
    [".go"],
    Language(
        name="go",
        definitions=(
            re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
            re.compile(r"^\s*type\s+([A-Za-z_]\w*)"),
        ),
        comment_markers=("//",),
        keywords=_GO_KEYWORDS,
    ),
)

_register(
    [".rs"],
    Language(
        name="rust",
        definitions=(
            re.compile(
                r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)"
            ),
            re.compile(
                r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|impl|mod)\s+([A-Za-z_]\w*)"
            ),
        ),
        comment_markers=("//",),
        keywords=_RS_KEYWORDS,
    ),
)


def language_for(path: str) -> Language | None:
    """Return the extraction rules for *path*, or ``None`` if unsupported."""
    return LANGUAGES.get(os.path.splitext(path)[1].lower())


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileTags:
    """Symbols a single file defines and references, plus its import evidence."""

    path: str
    definitions: dict[str, list[int]] = field(default_factory=dict)
    references: Counter[str] = field(default_factory=Counter)
    #: The subset of ``references`` that appeared as ATTRIBUTE access (`x.name`).
    #: Resolving those needs a type checker; matching them to any file that
    #: happens to define `def name` is how one-word `@property` accessors —
    #: `name`, `key`, `text` — took over the ranking of the real tree.
    attribute_references: Counter[str] = field(default_factory=Counter)
    signatures: dict[int, str] = field(default_factory=dict)
    #: Symbols pulled in BY NAME (`from core import helper`, `import {helper}`).
    imported_names: set[str] = field(default_factory=set)
    #: Module handles pulled in (`core`, `core.adapters`, `./layout_builders`),
    #: reduced to bare components so they can be matched against a file stem.
    imported_modules: set[str] = field(default_factory=set)

    @property
    def has_import_evidence(self) -> bool:
        """True when this file's imports were parsed at all.

        Absence of a strong edge only means something in a file whose imports we
        could actually read; for a language with no import extraction (shell,
        PowerShell) it means nothing, so the weak-edge penalty must not apply.
        """
        return bool(self.imported_names or self.imported_modules)


@dataclass(frozen=True)
class Definition:
    """One ranked symbol definition."""

    file: str
    name: str
    line: int
    rank: float
    signature: str

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "name": self.name,
            "line": self.line,
            "rank": self.rank,
            "signature": self.signature,
        }


@dataclass(frozen=True)
class RepoMap:
    """The grounding pack: everything ranked, plus the budgeted digest."""

    root: str
    budget_tokens: int
    files_scanned: int
    definitions: list[Definition]
    included: list[Definition]
    digest: str

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(self.digest)

    def as_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "budget_tokens": self.budget_tokens,
            "estimated_tokens": self.estimated_tokens,
            "files_scanned": self.files_scanned,
            "total_definitions": len(self.definitions),
            "definitions": [d.as_dict() for d in self.included],
            "digest": self.digest,
        }


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """
    Estimate the token count of *text* without a tokenizer.

    Ceiling division by :data:`CHARS_PER_TOKEN`. The tool is stdlib-only by
    design, so no BPE table ships with it; the divisor was MEASURED rather than
    assumed (see :data:`CHARS_PER_TOKEN`) and rounds UP, because over-counting
    wastes budget while under-counting silently overruns a subagent's context.

    Callers that DO have a real tokenizer should pass it as ``token_counter``
    to :func:`build_repo_map` / :func:`fit_to_budget` and get exact counts.
    """
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _git_tracked_files(root: Path) -> list[str] | None:
    """Tracked paths under *root* via `git ls-files`, or ``None`` if unavailable."""
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=str(root),
            capture_output=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.decode("utf-8", "replace")
    return [p.replace("\\", "/") for p in raw.split("\0") if p]


def _walked_files(root: Path) -> list[str]:
    """Every file under *root*, skipping EXCLUDED_DIRS."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in filenames:
            absolute = Path(dirpath) / filename
            found.append(absolute.relative_to(root).as_posix())
    return found


def discover_files(
    root: str | os.PathLike[str],
    *,
    use_git: bool = True,
    exclude: Sequence[str] = (),
) -> list[str]:
    """
    Repo-relative, forward-slashed, sorted paths of the source files to map.

    Prefers ``git ls-files`` (respects .gitignore, lists only tracked content)
    and falls back to a filesystem walk when *root* is not a git checkout, when
    git is unavailable, or when ``use_git=False``. Both paths are then filtered
    to the extensions in :data:`LANGUAGES` and against *exclude* (fnmatch
    globs against the repo-relative path).
    """
    root_path = Path(root)
    candidates = _git_tracked_files(root_path) if use_git else None
    if candidates is None:
        candidates = _walked_files(root_path)

    kept: list[str] = []
    for rel in candidates:
        if language_for(rel) is None:
            continue
        if any(part in EXCLUDED_DIRS for part in rel.split("/")[:-1]):
            continue
        if any(fnmatch.fnmatch(rel, pattern) for pattern in exclude):
            continue
        kept.append(rel)
    return sorted(set(kept))


def read_source(root: str | os.PathLike[str], rel: str) -> str | None:
    """
    Decode one source file, or ``None`` when it must be skipped.

    Skipped: unreadable, oversized, NUL-bearing (binary), or not valid UTF-8.
    Skipping is deliberate — decoding with ``errors="replace"`` would let a
    binary blob contribute garbage identifiers to the graph.
    """
    path = Path(root) / rel
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


def strip_line_comment(line: str, markers: Sequence[str]) -> str:
    """
    Drop a trailing line comment, respecting simple quoting.

    A small quote-aware scanner rather than ``line.split('#')[0]``: the naive
    form truncates at a ``#`` inside a string literal and silently deletes real
    references. It does NOT understand block comments or triple-quoted strings
    — identifiers inside those are still counted as references (documented
    approximation, see README).
    """
    if not markers:
        return line
    quote: str | None = None
    index = 0
    length = len(line)
    while index < length:
        char = line[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        else:
            for marker in markers:
                if line.startswith(marker, index):
                    return line[:index]
        index += 1
    return line


def extract_tags(path: str, text: str) -> FileTags:
    """
    Split one file's identifiers into DEFINITIONS and REFERENCES.

    Definitions come from the language's definition regexes (with 1-based line
    numbers and the source line kept as a signature). References are every
    other identifier occurrence in the comment-stripped body, minus the
    occurrences consumed by this file's own definition sites — which is how the
    regex path approximates tree-sitter's def/ref tag split.
    """
    language = language_for(path)
    tags = FileTags(path=path)
    if language is None:
        return tags

    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        _collect_imports(language, line, tags)
        if any(veto.match(line) for veto in language.definition_veto):
            continue
        for pattern in language.definitions:
            match = pattern.match(line)
            if not match:
                continue
            name = match.group(1)
            if name in language.keywords:
                continue
            tags.definitions.setdefault(name, []).append(number)
            tags.signatures.setdefault(number, _signature(line))
            break

    body = "\n".join(
        strip_line_comment(line, language.comment_markers) for line in lines
    )
    occurrences: Counter[str] = Counter()
    dotted: Counter[str] = Counter()
    for match in language.token.finditer(body):
        name = match.group(0)
        occurrences[name] += 1
        start = match.start()
        if start > 0 and body[start - 1] == ".":
            dotted[name] += 1

    for name, count in occurrences.items():
        if name in language.keywords:
            continue
        remaining = count - len(tags.definitions.get(name, ()))
        if remaining > 0:
            tags.references[name] = remaining
            # Attribute hits are capped at the surviving reference count so the
            # subset invariant holds after the definition sites are subtracted.
            attributes = min(dotted.get(name, 0), remaining)
            if attributes:
                tags.attribute_references[name] = attributes
    return tags


def _module_components(specifier: str) -> set[str]:
    """Reduce an import specifier to the bare handles a file stem could match.

    ``core.adapters`` -> {core, adapters, core.adapters};
    ``./layout_builders.js`` -> {layout_builders}; ``../a/b`` -> {a, b}.
    """
    cleaned = specifier.strip().strip("'\"")
    if not cleaned:
        return set()
    parts: set[str] = {cleaned}
    for chunk in re.split(r"[./\\]", cleaned):
        stem = os.path.splitext(chunk)[0]
        if stem and stem not in {"", "..", "@"}:
            parts.add(stem)
    return parts


def _collect_imports(language: Language, line: str, tags: FileTags) -> None:
    """Record one line's import evidence onto *tags* (best-effort, never raises)."""
    # Cheap substring bail before any regex: an import line always contains one
    # of these words, and this runs once per line of the whole tree.
    if "import" not in line and "require" not in line:
        return
    if language.name == "python":
        match = _PY_FROM_IMPORT.match(line)
        if match:
            tags.imported_modules.update(_module_components(match.group(1)))
            tags.imported_names.update(_NAME_IN_LIST.findall(match.group(2)))
            return
        match = _PY_IMPORT.match(line)
        if match:
            for spec in match.group(1).split(","):
                tags.imported_modules.update(_module_components(spec))
        return

    if language.name == "javascript":
        for pattern in (_JS_FROM, _JS_REQUIRE):
            for spec in pattern.findall(line):
                tags.imported_modules.update(_module_components(spec))
        if "require(" in line or line.lstrip().startswith(("import ", "export ")):
            braces = _JS_BRACE_NAMES.match(line)
            if braces:
                tags.imported_names.update(_NAME_IN_LIST.findall(braces.group(1)))
            default_import = _JS_DEFAULT_IMPORT.match(line)
            if default_import:
                tags.imported_names.add(default_import.group(1))
            binding = _JS_REQUIRE_BINDING.match(line)
            if binding:
                tags.imported_names.add(binding.group(1))


def module_aliases(path: str) -> set[str]:
    """Handles by which *path* could be imported (its stem, and its package dir)."""
    stem = Path(path).stem
    aliases = {stem}
    if stem in {"__init__", "index", "mod"}:
        parent = Path(path).parent.name
        if parent:
            aliases.add(parent)
    return aliases


def _signature(line: str) -> str:
    stripped = line.strip()
    if len(stripped) <= MAX_SIGNATURE_CHARS:
        return stripped
    return stripped[: MAX_SIGNATURE_CHARS - 3] + "..."


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def ident_multiplier(
    ident: str, definer_count: int, mentioned: frozenset[str]
) -> float:
    """
    How much signal one identifier carries, as an edge-weight multiplier.

    Mirrors Aider's heuristic and each factor is a separate, testable claim:
      * explicitly mentioned by the caller      -> x10 (steer the map)
      * long and snake_case/camelCase           -> x10 (domain vocabulary, not `i`/`fn`)
      * leading underscore                      -> x0.1 (private detail)
      * defined in more than five files         -> x0.1 (ubiquitous, so uninformative)
    """
    multiplier = 1.0
    is_snake = "_" in ident and any(c.isalpha() for c in ident)
    is_camel = any(c.isupper() for c in ident[1:]) and any(c.islower() for c in ident)
    if ident in mentioned:
        multiplier *= 10.0
    if (is_snake or is_camel) and len(ident) >= 8:
        multiplier *= 10.0
    if ident.startswith("_"):
        multiplier *= 0.1
    if definer_count > 5:
        multiplier *= 0.1
    return multiplier


@dataclass(frozen=True)
class Edge:
    """A weighted ``referencer -> definer`` edge carrying the linking symbol."""

    source: str
    target: str
    ident: str
    weight: float


def build_graph(
    tags_by_file: Mapping[str, FileTags],
    *,
    mentioned: Iterable[str] = (),
) -> tuple[list[str], list[Edge]]:
    """
    Turn per-file tags into the file-level reference graph.

    Iteration is over SORTED keys throughout so the edge list — and therefore
    every float summation downstream — is identical regardless of the mapping's
    insertion order.
    """
    mentioned_set = frozenset(mentioned)
    nodes = sorted(tags_by_file)

    defines: dict[str, set[str]] = defaultdict(set)
    references: dict[str, Counter[str]] = defaultdict(Counter)
    for path in nodes:
        tags = tags_by_file[path]
        for name in tags.definitions:
            defines[name].add(path)
        for name, count in tags.references.items():
            references[name][path] += count

    idents = sorted(set(defines) & set(references))
    if not idents:
        # Degenerate tree (definitions but no cross-file uses). Aider's fallback:
        # treat each definition as a self-reference so the map is not empty.
        for name, definers in defines.items():
            for definer in definers:
                references[name][definer] += 1
        idents = sorted(set(defines) & set(references))

    edges: list[Edge] = []
    for ident in idents:
        if len(ident) < MIN_IDENT_LENGTH and ident not in mentioned_set:
            continue
        definers = sorted(defines[ident])
        if len(definers) > MAX_DEFINER_FILES and ident not in mentioned_set:
            continue
        multiplier = ident_multiplier(ident, len(definers), mentioned_set)
        for referencer in sorted(references[ident]):
            scaled = math.sqrt(references[ident][referencer])
            referencer_tags = tags_by_file[referencer]
            for definer in definers:
                # No self-edges. A grounding pack is about what the REST of the
                # repo depends on; a symbol used only inside its own file is not
                # shared context. Measured: keeping self-edges let a file hand
                # its entire rank to its own locals, which is how `a` and `f`
                # reached the top 12 of this repository.
                if referencer == definer:
                    continue
                weight = multiplier * scaled
                if not _edge_is_import_backed(referencer_tags, ident, definer):
                    weight *= WEAK_EDGE_FACTOR
                edges.append(
                    Edge(
                        source=referencer,
                        target=definer,
                        ident=ident,
                        weight=weight,
                    )
                )
    return nodes, edges


def _edge_is_import_backed(referencer: FileTags, ident: str, definer: str) -> bool:
    """
    Is this reference plausibly a real dependency on *definer*?

    A bare identifier match is weak evidence: a test class with a ``def json``
    method collected every ``json.dumps`` in the repository and ranked top-12.
    An edge counts as strong when the referencing file imports the symbol by
    name, or imports a module whose handle matches the definer's file stem.

    When the referencing file has NO parsed import evidence at all — a shell
    script, a PowerShell module, any language without import extraction — the
    absence of a strong signal means nothing, so the edge is treated as strong
    rather than penalised for a gap in the tool.

    A module-level match is additionally refused when EVERY occurrence was
    attribute access (``x.name``): importing a module does not tell us that
    ``x`` is one of its classes, and treating it as if it did is what let
    one-word ``@property`` accessors dominate. An explicit by-name import still
    wins, because that is direct evidence about this exact symbol.
    """
    if not referencer.has_import_evidence:
        return True
    if ident in referencer.imported_names:
        return True
    total = referencer.references.get(ident, 0)
    attributes = referencer.attribute_references.get(ident, 0)
    if total and attributes >= total * ATTRIBUTE_DOMINANCE:
        return False
    return bool(module_aliases(definer) & referencer.imported_modules)


# ---------------------------------------------------------------------------
# PageRank (pure stdlib power iteration)
# ---------------------------------------------------------------------------


def pagerank(
    nodes: Sequence[str],
    out_edges: Mapping[str, Sequence[tuple[str, float]]],
    *,
    damping: float = DAMPING,
    personalization: Mapping[str, float] | None = None,
    max_iterations: int = MAX_ITERATIONS,
    tolerance: float = TOLERANCE,
) -> dict[str, float]:
    """
    Weighted, personalised PageRank by power iteration.

    Semantics deliberately match ``networkx.pagerank``: outgoing weights are
    normalised per node, dangling nodes redistribute along the personalisation
    vector, and the L1 convergence test is ``err < N * tolerance``. The suite
    asserts agreement with networkx to 1e-9 when networkx is installed (that
    test SKIPS in CI).

    On non-convergence the last iterate is returned rather than raising — a
    grounding pack degrading to a slightly-off ranking beats a crash.
    """
    node_list = sorted(set(nodes))
    count = len(node_list)
    if count == 0:
        return {}

    if personalization is None:
        vector = {node: 1.0 / count for node in node_list}
    else:
        total = sum(personalization.values())
        if total <= 0:
            vector = {node: 1.0 / count for node in node_list}
        else:
            vector = {
                node: personalization.get(node, 0.0) / total for node in node_list
            }

    known = set(node_list)
    normalised: dict[str, list[tuple[str, float]]] = {}
    dangling: list[str] = []
    for node in node_list:
        outs = [
            (dst, w) for dst, w in out_edges.get(node, ()) if dst in known and w > 0
        ]
        total_weight = sum(w for _dst, w in outs)
        if total_weight <= 0:
            dangling.append(node)
            normalised[node] = []
        else:
            normalised[node] = [(dst, w / total_weight) for dst, w in outs]

    ranks = {node: 1.0 / count for node in node_list}
    for _ in range(max_iterations):
        previous = ranks
        ranks = {node: 0.0 for node in node_list}
        dangling_mass = damping * sum(previous[node] for node in dangling)
        for node in node_list:
            share = damping * previous[node]
            for target, weight in normalised[node]:
                ranks[target] += share * weight
        for node in node_list:
            ranks[node] += dangling_mass * vector[node] + (1.0 - damping) * vector[node]
        error = sum(abs(ranks[node] - previous[node]) for node in node_list)
        if error < count * tolerance:
            break
    return ranks


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_definitions(
    tags_by_file: Mapping[str, FileTags],
    *,
    focus: Iterable[str] = (),
    mentioned: Iterable[str] = (),
) -> list[Definition]:
    """
    Rank every definition the graph can reach, most-central first.

    Each file's PageRank is split across its outgoing edges in proportion to
    edge weight and accumulated onto the ``(definer, ident)`` pair the edge
    travelled over — so a symbol many central files call outranks a symbol one
    peripheral file calls, even inside the same file.

    *focus* biases the random-surfer teleport vector toward those paths (the
    "what I'm working on right now" knob); *mentioned* multiplies the weight of
    those identifiers wherever they appear.
    """
    nodes, edges = build_graph(tags_by_file, mentioned=mentioned)
    if not nodes:
        return []

    focus_set = {f.replace("\\", "/") for f in focus}
    personalization: dict[str, float] | None = None
    if focus_set & set(nodes):
        personalization = {node: (1.0 if node in focus_set else 0.0) for node in nodes}

    out_edges: dict[str, list[tuple[str, float]]] = {node: [] for node in nodes}
    grouped: dict[str, list[Edge]] = {node: [] for node in nodes}
    for edge in edges:
        out_edges[edge.source].append((edge.target, edge.weight))
        grouped[edge.source].append(edge)

    ranks = pagerank(nodes, out_edges, personalization=personalization)

    accumulated: dict[tuple[str, str], float] = defaultdict(float)
    for node in nodes:
        outgoing = grouped[node]
        total_weight = sum(edge.weight for edge in outgoing)
        if total_weight <= 0:
            continue
        source_rank = ranks[node]
        for edge in outgoing:
            accumulated[(edge.target, edge.ident)] += (
                source_rank * edge.weight / total_weight
            )

    definitions: list[Definition] = []
    for (path, ident), rank in accumulated.items():
        tags = tags_by_file.get(path)
        if tags is None:
            continue
        lines = tags.definitions.get(ident)
        if not lines:
            continue
        line = lines[0]
        definitions.append(
            Definition(
                file=path,
                name=ident,
                line=line,
                rank=rank,
                signature=tags.signatures.get(line, ident),
            )
        )
    definitions.sort(key=lambda d: (-d.rank, d.file, d.name, d.line))
    return definitions


# ---------------------------------------------------------------------------
# Rendering + budgeting
# ---------------------------------------------------------------------------


def render(definitions: Sequence[Definition]) -> str:
    """
    Render ranked definitions as a compact, LF-only digest.

    Files appear in the order their highest-ranked symbol appears, and lines
    within a file in source order. Rendering a longer prefix therefore only
    ever APPENDS to an existing group or adds a new one — the monotonicity the
    budget binary search depends on. An empty selection renders as the empty
    string so the budget invariant is satisfiable at any budget, including 0.
    """
    if not definitions:
        return ""
    order: list[str] = []
    by_file: dict[str, list[Definition]] = {}
    for definition in definitions:
        if definition.file not in by_file:
            by_file[definition.file] = []
            order.append(definition.file)
        by_file[definition.file].append(definition)

    chunks: list[str] = []
    for path in order:
        chunks.append(path)
        for definition in sorted(by_file[path], key=lambda d: (d.line, d.name)):
            chunks.append(f"{definition.line:>5}: {definition.signature}")
    return "\n".join(chunks) + "\n"


def fit_to_budget(
    definitions: Sequence[Definition],
    budget_tokens: int,
    token_counter: Callable[[str], int] = estimate_tokens,
) -> tuple[list[Definition], str]:
    """
    Largest prefix of *definitions* whose rendering fits *budget_tokens*.

    Binary search on prefix length. Unlike Aider's variant — which accepts a
    15%-over result to terminate early — this NEVER returns a rendering above
    budget: a grounding pack that silently overruns is what blows a subagent's
    context, so ``token_counter(digest) <= budget_tokens`` is unconditional and
    is asserted by the suite.

    The search assumes *token_counter* is non-decreasing in prefix length,
    which :func:`render` guarantees for a length-based counter. If a caller
    supplies a counter that is NOT monotonic the search may miss the true
    maximum prefix, but the returned digest still satisfies the budget
    invariant — only an accepted (measured-under-budget) prefix is ever kept.
    """
    if budget_tokens <= 0 or not definitions:
        return [], ""

    low, high = 0, len(definitions)
    best_count, best_text = 0, ""
    while low <= high:
        middle = (low + high) // 2
        text = render(definitions[:middle])
        if token_counter(text) <= budget_tokens:
            best_count, best_text = middle, text
            low = middle + 1
        else:
            high = middle - 1
    return list(definitions[:best_count]), best_text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_repo_map(
    root: str | os.PathLike[str],
    *,
    budget_tokens: int = 1024,
    focus: Iterable[str] = (),
    mentioned: Iterable[str] = (),
    use_git: bool = True,
    exclude: Sequence[str] = (),
    token_counter: Callable[[str], int] = estimate_tokens,
) -> RepoMap:
    """Discover, extract, rank, and budget — the whole pipeline in one call."""
    root_path = Path(root)
    files = discover_files(root_path, use_git=use_git, exclude=exclude)

    tags_by_file: dict[str, FileTags] = {}
    for rel in files:
        text = read_source(root_path, rel)
        if text is None:
            continue
        tags_by_file[rel] = extract_tags(rel, text)

    definitions = rank_definitions(tags_by_file, focus=focus, mentioned=mentioned)
    included, digest = fit_to_budget(definitions, budget_tokens, token_counter)
    return RepoMap(
        root=str(root_path),
        budget_tokens=budget_tokens,
        files_scanned=len(tags_by_file),
        definitions=definitions,
        included=included,
        digest=digest,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo_map",
        description=(
            "Emit a PageRank-ranked repo map for use as a fan-out grounding pack "
            "(rules/common/fan-out-contract.md §A11)."
        ),
    )
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument(
        "--budget",
        type=int,
        default=1024,
        help="token budget for the digest (default: 1024)",
    )
    parser.add_argument(
        "--focus",
        action="append",
        default=[],
        metavar="PATH",
        help="bias ranking toward this file; repeatable",
    )
    parser.add_argument(
        "--mention",
        action="append",
        default=[],
        metavar="IDENT",
        help="boost this identifier's edge weight; repeatable",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip repo-relative paths matching this glob; repeatable",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="walk the filesystem instead of using `git ls-files`",
    )
    parser.add_argument(
        "--tiktoken",
        metavar="ENCODING",
        help=(
            "count tokens exactly with this tiktoken encoding (e.g. cl100k_base) "
            "instead of the stdlib estimator; requires tiktoken to be installed"
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--out", metavar="FILE", help="also write the output to FILE")
    return parser


def _resolve_token_counter(encoding: str | None) -> Callable[[str], int]:
    """Exact tiktoken counter when asked for, else the stdlib estimator."""
    if not encoding:
        return estimate_tokens
    import tiktoken  # noqa: PLC0415 -- optional, imported only when requested

    encoder = tiktoken.get_encoding(encoding)
    return lambda text: len(encoder.encode(text))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_repo_map(
        args.root,
        budget_tokens=args.budget,
        focus=args.focus,
        mentioned=args.mention,
        use_git=not args.no_git,
        exclude=args.exclude,
        token_counter=_resolve_token_counter(args.tiktoken),
    )
    payload = (
        json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n"
        if args.json
        else result.digest
    )
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8", newline="\n")
    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
