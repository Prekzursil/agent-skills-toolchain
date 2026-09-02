"""Contamination scan: benchmark cases leaking into prompts, fixtures and the corpus (TST-0307).

A benchmark case whose answer already sits in a prompt template, a skill file, a memory
note or a committed fixture is not measuring capability.  This module hashes each case's
task input and expected output, searches a corpus tree for three kinds of leak and
quarantines every contaminated case before scoring:

* ``hash``              - the sha256 digest of the normalised text appears in a file
                          (someone committed the oracle fingerprint itself);
* ``verbatim``          - the normalised text is a substring of the normalised file;
* ``trigram-coverage``  - the share of the case's word trigrams that also occur in the
                          file reaches ``DEFAULT_THRESHOLD`` (token-preserving paraphrase).

The instrument is lexical.  A full semantic rewrite that preserves no trigram is *not*
caught, and ``measure_detector_control`` measures and reports that limit instead of
claiming it away.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

UNIT_ID = "TST-0307"
METHOD = "sha256-normalize + verbatim-substring + word-trigram-coverage"
DEFAULT_THRESHOLD = 0.55
SHINGLE_N = 3
MIN_TOKENS = SHINGLE_N + 2
ALL_METHODS: tuple[str, ...] = ("verbatim", "trigram-coverage", "hash")
NAIVE_METHODS: tuple[str, ...] = ("verbatim",)

ALPHA_ID = "TST0307-ALPHA"
BETA_ID = "TST0307-BETA"
GAMMA_ID = "TST0307-GAMMA"

MAX_FILE_BYTES = 512 * 1024
TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".sh",
        ".ps1",
        ".mjs",
        ".js",
        ".ts",
        ".cfg",
        ".ini",
        ".rst",
        ".csv",
        ".html",
        ".xml",
        ".hook",
    }
)
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        "vendor",
        "deps",
        ".venv",
        "venv",
        "dist",
        "build",
    }
)
# Relative directories (posix) skipped so n_paths is not a moving target and so the case
# files and the probe tree do not trivially match themselves.
SKIP_REL_PREFIXES: tuple[str, ...] = (
    "command-center/p2-wave/probes",
    "command-center/bench/cases",
    "command-center/receipts",
)
LIVE_ROOTS: tuple[str, ...] = (
    "skills",
    "skills-claude-only",
    "agents",
    "commands",
    "hooks",
    "rules",
    "tools",
    "platform",
    "lib",
    "router",
    "plugin",
    "marketplace",
    "workflow_foundry",
    "council",
    "workflows",
    "scripts",
    "docs",
    "guides",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEX64_RE = re.compile(r"[0-9a-f]{64}")


class ContaminationError(ValueError):
    """Raised for malformed cases or an unusable corpus root."""


# --------------------------------------------------------------------------- text model
def normalize(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace to single spaces."""
    return " ".join(_TOKEN_RE.findall(str(text).lower()))


def tokens(text: str) -> list[str]:
    """Normalised word tokens of ``text``."""
    return _TOKEN_RE.findall(str(text).lower())


def digest(text: str) -> str:
    """sha256 of the normalised text (what a leaked oracle fingerprint looks like)."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def shingles(text: str, n: int = SHINGLE_N) -> set[tuple[str, ...]]:
    """Set of word ``n``-grams over the normalised tokens."""
    toks = tokens(text)
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def coverage(needle: str, haystack: str, n: int = SHINGLE_N) -> float:
    """Share of ``needle``'s n-grams that occur in ``haystack`` (1.0 = every trigram present)."""
    need = shingles(needle, n)
    if not need:
        return 0.0
    hay = shingles(haystack, n)
    return len(need & hay) / len(need)


def jaccard(a: str, b: str, n: int = SHINGLE_N) -> float:
    """Symmetric n-gram Jaccard similarity of two texts."""
    sa, sb = shingles(a, n), shingles(b, n)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# --------------------------------------------------------------------------- cases
@dataclass(frozen=True)
class Case:
    """One benchmark case: what the solver sees and what the oracle expects."""

    case_id: str
    task_input: str
    expected_output: str

    def needles(self) -> list[tuple[str, str]]:
        """(field, text) pairs worth hashing; short fragments cannot leak meaningfully."""
        out: list[tuple[str, str]] = []
        for name, text in (
            ("expected_output", self.expected_output),
            ("task_input", self.task_input),
        ):
            if len(tokens(text)) >= MIN_TOKENS:
                out.append((name, text))
        return out


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def case_from_record(record: Mapping[str, Any]) -> Case:
    """Build a :class:`Case` from a bench case document.

    ``expected_output`` is taken from, in order, ``expected_output``,
    ``known_good_solution``, ``oracle.expected``; ``task_input`` from ``task_input``,
    ``input`` or ``prompt``.  A record without an ``id`` is malformed.
    """
    cid = record.get("id") or record.get("case_id")
    if not cid:
        raise ContaminationError("case record has no id")
    expected: Any = record.get("expected_output")
    if expected is None:
        expected = record.get("known_good_solution")
    if expected is None and isinstance(record.get("oracle"), Mapping):
        expected = record["oracle"].get("expected")
    task = record.get("task_input")
    if task is None:
        task = record.get("input", record.get("prompt"))
    return Case(str(cid), _as_text(task), _as_text(expected))


def load_live_cases(cases_dir: Path) -> list[Case]:
    """Load every case document under ``cases_dir`` (top-level ``*.json`` only)."""
    cases: list[Case] = []
    seen: set[str] = set()
    for path in sorted(cases_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        records: list[Mapping[str, Any]] = []
        if isinstance(doc, Mapping) and doc.get("id"):
            records.append(doc)
        elif isinstance(doc, Mapping) and isinstance(doc.get("cases"), list):
            records.extend(r for r in doc["cases"] if isinstance(r, Mapping))
        for rec in records:
            try:
                case = case_from_record(rec)
            except ContaminationError:
                continue
            if case.case_id in seen or not case.needles():
                continue
            seen.add(case.case_id)
            cases.append(case)
    return cases


# --------------------------------------------------------------------------- corpus walk
def _skip_rel(rel: str) -> bool:
    return any(rel == p or rel.startswith(p + "/") for p in SKIP_REL_PREFIXES)


def iter_corpus_files(
    root: Path, *, rel_base: Path | None = None
) -> Iterable[tuple[str, Path]]:
    """Yield (relative posix path, path) for every scannable text file under ``root``."""
    root = Path(root)
    base = rel_base or root
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES
            and not _skip_rel(Path(dirpath, d).relative_to(base).as_posix())
        )
        for name in sorted(filenames):
            path = Path(dirpath, name)
            if path.suffix.lower() not in TEXT_SUFFIXES and path.suffix != "":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > MAX_FILE_BYTES:
                continue
            yield path.relative_to(base).as_posix(), path


def read_text_file(path: Path) -> str | None:
    """Return decoded text, or ``None`` for binary / undecodable content."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


# --------------------------------------------------------------------------- scanning
@dataclass
class Hit:
    """One (case, path) contamination finding."""

    case_id: str
    path: str
    methods: list[str]
    field: str
    coverage: float


@dataclass
class ScanReport:
    """Result of one corpus scan."""

    method: str
    threshold: float
    shingle_n: int
    methods_enabled: list[str]
    paths_searched: list[str] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)

    @property
    def n_paths_searched(self) -> int:
        return len(self.paths_searched)

    def contaminated(self) -> list[dict[str, Any]]:
        """One row per contaminated case: paths and methods in first-seen order."""
        rows: dict[str, dict[str, Any]] = {}
        for hit in self.hits:
            row = rows.setdefault(
                hit.case_id,
                {
                    "case_id": hit.case_id,
                    "paths": [],
                    "methods": [],
                    "max_coverage": 0.0,
                },
            )
            if hit.path not in row["paths"]:
                row["paths"].append(hit.path)
            for m in hit.methods:
                if m not in row["methods"]:
                    row["methods"].append(m)
            row["max_coverage"] = max(row["max_coverage"], hit.coverage)
        return [rows[k] for k in rows]

    def quarantine_ids(self) -> list[str]:
        return [row["case_id"] for row in self.contaminated()]

    def hash_hits(self) -> int:
        return sum(1 for h in self.hits if "hash" in h.methods)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "threshold": self.threshold,
            "shingle_n": self.shingle_n,
            "methods_enabled": list(self.methods_enabled),
            "n_paths_searched": self.n_paths_searched,
            "paths_searched": list(self.paths_searched),
            "hits": [asdict(h) for h in self.hits],
            "contaminated": self.contaminated(),
            "quarantine_ids": self.quarantine_ids(),
            "hash_hits": self.hash_hits(),
        }


def match_case_in_text(
    case: Case,
    text: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    shingle_n: int = SHINGLE_N,
    methods: Sequence[str] = ALL_METHODS,
) -> tuple[list[str], str, float]:
    """Return (methods that fired, field that fired, best coverage) for one file."""
    norm_text = normalize(text)
    lower_text = text.lower()
    fired: list[str] = []
    best_field = ""
    best_cov = 0.0
    file_shingles: set[tuple[str, ...]] | None = None
    for name, needle in case.needles():
        norm_needle = normalize(needle)
        if "verbatim" in methods and norm_needle and norm_needle in norm_text:
            if "verbatim" not in fired:
                fired.append("verbatim")
            best_field = best_field or name
        if "trigram-coverage" in methods:
            need = shingles(needle, shingle_n)
            if need:
                if file_shingles is None:
                    file_shingles = shingles(text, shingle_n)
                cov = len(need & file_shingles) / len(need)
                if cov > best_cov:
                    best_cov, best_field = cov, name
                if cov >= threshold and "trigram-coverage" not in fired:
                    fired.append("trigram-coverage")
        if "hash" in methods and digest(needle) in lower_text:
            if "hash" not in fired:
                fired.append("hash")
            best_field = best_field or name
    return fired, best_field, round(best_cov, 4)


def scan(
    cases: Sequence[Case],
    root: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    shingle_n: int = SHINGLE_N,
    methods: Sequence[str] = ALL_METHODS,
    rel_base: Path | None = None,
    extra_roots: Sequence[Path] = (),
) -> ScanReport:
    """Search ``root`` (and ``extra_roots``) for every case's input/output leaks."""
    if not (0.0 < float(threshold) <= 1.0):
        raise ContaminationError(f"threshold must be in (0, 1], got {threshold!r}")
    unknown = [m for m in methods if m not in ALL_METHODS]
    if unknown:
        raise ContaminationError(f"unknown scan methods: {unknown}")
    root = Path(root)
    if not root.is_dir() and not extra_roots:
        raise ContaminationError(f"corpus root is not a directory: {root}")
    report = ScanReport(METHOD, float(threshold), int(shingle_n), list(methods))
    roots = [root, *extra_roots]
    for r in roots:
        for rel, path in iter_corpus_files(r, rel_base=rel_base or root):
            text = read_text_file(path)
            if text is None:
                continue
            report.paths_searched.append(rel)
            for case in cases:
                fired, fld, cov = match_case_in_text(
                    case,
                    text,
                    threshold=threshold,
                    shingle_n=shingle_n,
                    methods=methods,
                )
                if fired:
                    report.hits.append(Hit(case.case_id, rel, fired, fld, cov))
    return report


def naive_scan(cases: Sequence[Case], root: Path, **kwargs: Any) -> ScanReport:
    """Verbatim-only baseline: the detector a hurried author would have written."""
    kwargs.pop("methods", None)
    return scan(cases, root, methods=NAIVE_METHODS, **kwargs)


# --------------------------------------------------------------------------- scoring
def score_cases(
    cases: Sequence[Case],
    passed: Mapping[str, bool],
    quarantine_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Score oracle outcomes, excluding quarantined cases; one point per pass.

    ``excluded_points`` shows how much of the dirty score came from contaminated cases,
    so both states (with and without quarantine) stay visible side by side.
    """
    q = set(quarantine_ids)
    scored_ids: list[str] = []
    excluded_ids: list[str] = []
    points = 0.0
    excluded_points = 0.0
    for case in cases:
        ok = bool(passed.get(case.case_id, False))
        if case.case_id in q:
            excluded_ids.append(case.case_id)
            excluded_points += 1.0 if ok else 0.0
            continue
        scored_ids.append(case.case_id)
        points += 1.0 if ok else 0.0
    n_scored = len(scored_ids)
    return {
        "n_scored": n_scored,
        "n_pass": int(points),
        "points": points,
        "accuracy": (points / n_scored) if n_scored else 0.0,
        "scored_ids": scored_ids,
        "excluded_ids": excluded_ids,
        "excluded_points": excluded_points,
    }


# --------------------------------------------------------------------------- control tree
CONTROL_CASES: tuple[Case, ...] = (
    Case(
        ALPHA_ID,
        "How should the API gateway handle a transient upstream failure on an idempotent request?",
        "The gateway retries idempotent requests three times with exponential backoff and jitter "
        "before returning a 503 to the caller with a Retry-After header.",
    ),
    Case(
        BETA_ID,
        "Describe the signing key rotation policy for the token service.",
        "Rotate the signing key every ninety days, publish the new public key to the JWKS endpoint, "
        "and keep the previous key valid for one overlap window so cached tokens still verify.",
    ),
    Case(
        GAMMA_ID,
        "How should the metrics endpoint be exposed on the observability host?",
        "Bind the metrics listener to localhost only and expose it through the authenticated "
        "reverse proxy with the scrape allowlist enforced at the proxy.",
    ),
)

# BETA paraphrase: same vocabulary, one substitution and one clause reorder.  Verbatim
# matching fails on it; word-trigram coverage stays far above the threshold.
BETA_PARAPHRASE = (
    "Rotate the signing key every ninety days, publish the new public key to the JWKS endpoint, "
    "and keep the old key valid for one overlap window so cached tokens still verify."
)
# ALPHA full semantic rewrite: shares no word trigram with any control needle.
ALPHA_REWRITE = (
    "Transient errors from upstream on safely repeatable calls are retried thrice, spacing "
    "attempts out geometrically plus noise; only afterwards does the edge respond service "
    "unavailable and hint when to come back."
)

CONTROL_FILES: dict[str, str] = {
    "prompts/system-prompt.md": (
        "# Assistant system prompt\n\n"
        "You are the on-call helper. When asked about gateway behaviour, answer:\n\n"
        f"> {CONTROL_CASES[0].expected_output}\n\n"
        "Keep answers short.\n"
    ),
    "skills/planted-skill.md": (
        "---\nname: planted-skill\ndescription: fixture skill for the contamination control\n---\n\n"
        "Reference fingerprint for the gateway answer: "
        f"sha256:{digest(CONTROL_CASES[0].expected_output)}\n"
    ),
    "fixtures/memory-note.txt": (
        f"Memory note from a previous session.\n\n{BETA_PARAPHRASE}\n"
    ),
    "memory/session-note.md": (f"# Session note\n\n{ALPHA_REWRITE}\n"),
    "clean/README.md": (
        "# Clean fixtures\n\n"
        "This directory holds unrelated fixtures for the isolated contamination control. "
        "Nothing in here mirrors a benchmark case.\n"
    ),
}


def build_control_tree(root: Path) -> Path:
    """Write the isolated control corpus under ``root/corpus`` and return that path."""
    corpus = Path(root) / "corpus"
    for rel, text in CONTROL_FILES.items():
        target = corpus / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return corpus


def _found(report: ScanReport, case_id: str) -> bool:
    return case_id in report.quarantine_ids()


def _path_coverage(report_root: Path, rel: str, case: Case, shingle_n: int) -> float:
    text = read_text_file(report_root / rel) or ""
    return round(
        max((coverage(n, text, shingle_n) for _, n in case.needles()), default=0.0), 4
    )


def measure_detector_control(
    work_dir: Path | None = None,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    shingle_n: int = SHINGLE_N,
) -> dict[str, Any]:
    """Plant ALPHA (verbatim + hash) and BETA (paraphrase), leave GAMMA clean, then scan.

    Runs the full scanner and the naive verbatim-only scanner over a fresh isolated tree,
    recomputes the score with and without quarantine, and reports both states.  A
    temporary directory is used (and removed) unless ``work_dir`` is given.
    """
    cleanup = work_dir is None
    base = (
        Path(work_dir)
        if work_dir is not None
        else Path(tempfile.mkdtemp(prefix="tst0307-"))
    )
    try:
        corpus = build_control_tree(base / "isolated-control")
        cases = list(CONTROL_CASES)
        full = scan(cases, corpus, threshold=threshold, shingle_n=shingle_n)
        naive = naive_scan(cases, corpus, threshold=threshold, shingle_n=shingle_n)
        alpha, beta, gamma = CONTROL_CASES
        paraphrase_cov = _path_coverage(
            corpus, "fixtures/memory-note.txt", beta, shingle_n
        )
        rewrite_cov = _path_coverage(corpus, "memory/session-note.md", alpha, shingle_n)
        rewrite_caught = any(h.path == "memory/session-note.md" for h in full.hits)
        quarantine = full.quarantine_ids()
        passed = {
            c.case_id: True for c in cases
        }  # every control case is an oracle PASS
        dirty = score_cases(cases, passed, ())
        clean = score_cases(cases, passed, quarantine)
        delta = dirty["points"] - clean["points"]
        alpha_found = _found(full, ALPHA_ID)
        beta_found = _found(full, BETA_ID)
        gamma_found = _found(full, GAMMA_ID)
        naive_alpha = _found(naive, ALPHA_ID)
        naive_beta = _found(naive, BETA_ID)
        passed_all = (
            alpha_found
            and beta_found
            and not gamma_found
            and naive_alpha
            and not naive_beta
            and full.hash_hits() >= 1
            and dirty["n_scored"] == 3
            and clean["n_scored"] == 1
            and delta == 2.0
        )
        scope = (
            "lexical-trigram-coverage catches token-preserving paraphrase "
            f"(coverage={paraphrase_cov:.4f}, threshold={threshold}); full semantic rewrite "
            f"is NOT caught (coverage={rewrite_cov:.4f}). This instrument does not claim "
            "semantic detection."
        )
        return {
            "unit_id": UNIT_ID,
            "pass": bool(passed_all),
            "method": METHOD,
            "threshold": float(threshold),
            "shingle_n": int(shingle_n),
            "near_match_scope": scope,
            "n_paths_searched": full.n_paths_searched,
            "alpha_found": alpha_found,
            "beta_found": beta_found,
            "gamma_found": gamma_found,
            "naive_alpha": naive_alpha,
            "naive_beta": naive_beta,
            "paraphrase_caught": beta_found and not naive_beta,
            "paraphrase_coverage": paraphrase_cov,
            # legacy key read by the receipt emitter; carries the coverage ratio above
            "paraphrase_jaccard": paraphrase_cov,
            "rewrite_caught": rewrite_caught,
            "rewrite_coverage": rewrite_cov,
            "rewrite_jaccard": rewrite_cov,
            "hash_hits": full.hash_hits(),
            "contaminated": full.contaminated(),
            "quarantine_ids": quarantine,
            "score_without_quarantine": dirty,
            "score_with_quarantine": clean,
            "quarantine_changes_score": dirty != clean,
            "points_delta": delta,
            "full": full.to_dict(),
            "naive": naive.to_dict(),
        }
    finally:
        if cleanup:
            shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------------- live scan
def repo_root() -> Path:
    """The ast-integrate tree this module lives in (tools/bench/contamination.py)."""
    return Path(__file__).resolve().parents[2]


def measure_live(
    root: Path | None = None, *, threshold: float = DEFAULT_THRESHOLD
) -> dict[str, Any]:
    """Scan the live program corpus and harness trees for the real bench cases."""
    repo = Path(root) if root is not None else repo_root()
    cases_dir = repo / "command-center" / "bench" / "cases"
    cases = load_live_cases(cases_dir) if cases_dir.is_dir() else []
    roots = [repo / r for r in LIVE_ROOTS if (repo / r).is_dir()]
    if cases and roots:
        report = scan(
            cases, roots[0], threshold=threshold, rel_base=repo, extra_roots=roots[1:]
        )
        report_doc = report.to_dict()
    else:
        report_doc = ScanReport(
            METHOD, float(threshold), SHINGLE_N, list(ALL_METHODS)
        ).to_dict()
    return {
        "cases_present": cases_dir.is_dir() and bool(cases),
        "n_cases": len(cases),
        "case_ids": [c.case_id for c in cases],
        "roots": [r.relative_to(repo).as_posix() for r in roots],
        "n_paths_searched": report_doc["n_paths_searched"],
        "paths_searched_sample": report_doc["paths_searched"][:16],
        "contaminated_ids": report_doc["quarantine_ids"],
        "contaminated": report_doc["contaminated"],
        "method": METHOD,
        "threshold": float(threshold),
        "note": (
            "Live scan hashes each case's task_input and known_good_solution/expected_output "
            "and searches program-corpus and harness trees. p2-wave/probes, bench/cases, "
            "receipts and vendor/deps trees are skipped so n_paths is not a moving target."
        ),
    }


def measure(root: Path | None = None) -> dict[str, Any]:
    """Detector control plus live scan; ``pass`` is the control verdict."""
    control = measure_detector_control()
    live = measure_live(root)
    return {
        "unit_id": UNIT_ID,
        "method": METHOD,
        "threshold": DEFAULT_THRESHOLD,
        "shingle_n": SHINGLE_N,
        "control": control,
        "live": live,
        "pass": bool(control["pass"]),
    }


__all__ = [
    "ALL_METHODS",
    "ALPHA_ID",
    "BETA_ID",
    "CONTROL_CASES",
    "Case",
    "ContaminationError",
    "DEFAULT_THRESHOLD",
    "GAMMA_ID",
    "Hit",
    "METHOD",
    "NAIVE_METHODS",
    "SHINGLE_N",
    "ScanReport",
    "build_control_tree",
    "case_from_record",
    "coverage",
    "digest",
    "jaccard",
    "load_live_cases",
    "match_case_in_text",
    "measure",
    "measure_detector_control",
    "measure_live",
    "naive_scan",
    "normalize",
    "scan",
    "score_cases",
    "shingles",
    "tokens",
]
