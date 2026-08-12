"""Rule audit: classify every rule always-on vs lazy, total the token cost, diff the trees.

READ-ONLY with respect to every tree it measures. The ONLY paths this script writes are the
two artifacts under ``docs/rule-audit/`` that it is asked to emit (``--json`` / ``--md``).

Why this exists
---------------
``commands/context-budget.md`` delegates all token accounting to ``skills/context-budget/``,
which does not exist in any of the five skill roots (measured; see RULE-AUDIT.md §3.6). So
there is no prior-art tool for always-on token accounting and this is it.

Classification semantics (MEASURED, not assumed)
------------------------------------------------
Claude Code loads a rule file with NO frontmatter at launch (always-on, CLAUDE.md priority);
a rule WITH a ``paths:`` selector loads lazily when a touched file matches the selector.
Adding ``paths: ["**/*"]`` therefore DEMOTES an always-on rule -- the inverse of the intuition.
This script reports three buckets rather than a binary, because "has frontmatter" and "has a
paths key" are not the same predicate and collapsing them would hide a real case:

    always_on_no_frontmatter   : no ``---`` block at all
    frontmatter_without_paths  : has a ``---`` block but no ``paths:`` key
    lazy_paths_scoped          : has a ``paths:`` selector

Token counts use ``tiktoken``/``cl100k_base``. That is OpenAI's tokenizer, not Anthropic's, so
every total carries an estimator caveat of roughly +/-10-20%. The first-party instrument is
Claude Code's own ``/context``, which prints per-file token counts for loaded memory files.

Windows notes: every read is binary + LF-normalised before hashing/counting, so a CRLF working
tree and an LF blob produce identical numbers.

Usage::

    python docs/rule-audit/rule_audit.py --json out.json --md out.md
    python docs/rule-audit/rule_audit.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()

TREES: dict[str, Path] = {
    "repo": REPO_ROOT / "rules",
    "agent-self": REPO_ROOT / "agent-self" / "config" / "rules",
    "live": HOME / ".claude" / "rules",
}

# Unconditional memory files that sit alongside the always-on rules in every turn-0 prompt.
MEMORY_FILES: dict[str, Path] = {
    "~/.claude/CLAUDE.md": HOME / ".claude" / "CLAUDE.md",
    "~/.claude/AGENTS.md": HOME / ".claude" / "AGENTS.md",
    "~/CLAUDE.md": HOME / "CLAUDE.md",
}

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:[ \t]*(.*)$")


def read_lf(path: Path) -> str:
    """Read a file as text with LF line endings, whatever the working tree holds."""
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", errors="replace")


def parse_frontmatter(text: str) -> tuple[bool, dict[str, object]]:
    """Return ``(has_frontmatter, keys)``. Only the shape we need: scalars and block lists."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return False, {}
    keys: dict[str, object] = {}
    current: str | None = None
    for raw_line in match.group(1).split("\n"):
        line = raw_line.rstrip()
        item = re.match(r"^[ \t]*-[ \t]+(.*)$", line)
        if item and current is not None:
            bucket = keys.setdefault(current, [])
            if isinstance(bucket, list):
                bucket.append(item.group(1).strip())
            else:
                keys[current] = [item.group(1).strip()]
            continue
        keyed = KEY_RE.match(line)
        if keyed:
            current = keyed.group(1)
            value = keyed.group(2).strip()
            keys[current] = value if value else []
    return True, keys


def selectors(keys: dict[str, object]) -> list[str]:
    """Normalise a ``paths:`` value (inline list, block list, or bare scalar) to a list."""
    if "paths" not in keys:
        return []
    value = keys["paths"]
    if isinstance(value, list):
        return [str(v).strip().strip("\"'") for v in value if str(v).strip()]
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip().strip("\"'") for part in text.split(",") if part.strip()]


def classify(has_fm: bool, keys: dict[str, object]) -> str:
    if not has_fm:
        return "always_on_no_frontmatter"
    if "paths" not in keys:
        return "frontmatter_without_paths"
    return "lazy_paths_scoped"


class Counter:
    """Token counter. Reports the encoder actually used so a fallback can never pass as exact."""

    def __init__(self) -> None:
        try:
            import tiktoken

            self._enc = tiktoken.get_encoding("cl100k_base")
            self.name = "tiktoken/cl100k_base"
        except Exception as exc:  # pragma: no cover - only on a box without tiktoken
            self._enc = None
            self.name = f"ESTIMATE chars/4 (tiktoken unavailable: {exc})"

    def count(self, text: str) -> int:
        if self._enc is None:
            return round(len(text) / 4)
        return len(self._enc.encode(text))


def scan_tree(root: Path, counter: Counter) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = read_lf(path)
        has_fm, keys = parse_frontmatter(text)
        out[rel] = {
            "path": path.as_posix(),
            "has_frontmatter": has_fm,
            "frontmatter_keys": sorted(keys),
            "selectors": selectors(keys),
            "load": classify(has_fm, keys),
            "tokens": counter.count(text),
            "bytes_lf": len(text.encode("utf-8")),
            "sha256_lf": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    return out


def diff_trees(a: dict[str, dict], b: dict[str, dict]) -> dict[str, list[str]]:
    """Byte-level (LF-normalised) comparison plus a load-semantics comparison."""
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    shared = sorted(set(a) & set(b))
    return {
        "only_in_first": only_a,
        "only_in_second": only_b,
        "content_differs": [
            r for r in shared if a[r]["sha256_lf"] != b[r]["sha256_lf"]
        ],
        "load_semantics_differs": [r for r in shared if a[r]["load"] != b[r]["load"]],
    }


def build(counter: Counter | None = None) -> dict:
    counter = counter or Counter()
    trees = {name: scan_tree(root, counter) for name, root in TREES.items()}
    report: dict = {
        "tokenizer": counter.name,
        "tokenizer_is_anthropic": False,
        "roots": {
            name: {"path": root.as_posix(), "exists": root.is_dir()}
            for name, root in TREES.items()
        },
        "trees": trees,
        "summary": {},
        "diffs": {},
        "memory_files": {},
    }

    for name, files in trees.items():
        buckets: dict[str, list[str]] = {
            "always_on_no_frontmatter": [],
            "frontmatter_without_paths": [],
            "lazy_paths_scoped": [],
        }
        for rel, info in files.items():
            buckets[info["load"]].append(rel)
        always_on = (
            buckets["always_on_no_frontmatter"] + buckets["frontmatter_without_paths"]
        )
        report["summary"][name] = {
            "files": len(files),
            "counts": {k: len(v) for k, v in buckets.items()},
            "always_on_files": sorted(always_on),
            "always_on_tokens": sum(files[r]["tokens"] for r in always_on),
            "lazy_tokens": sum(
                files[r]["tokens"] for r in buckets["lazy_paths_scoped"]
            ),
            "all_tokens": sum(info["tokens"] for info in files.values()),
        }

    report["diffs"]["repo_vs_live"] = diff_trees(trees["repo"], trees["live"])
    report["diffs"]["repo_vs_agent_self"] = diff_trees(
        trees["repo"], trees["agent-self"]
    )

    floor = report["summary"].get("live", {}).get("always_on_tokens", 0)
    for label, path in MEMORY_FILES.items():
        if path.is_file():
            tokens = counter.count(read_lf(path))
            report["memory_files"][label] = tokens
            floor += tokens
        else:
            report["memory_files"][label] = None
    report["always_on_floor_tokens"] = floor
    return report


def render_md(report: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add("<!-- GENERATED by docs/rule-audit/rule_audit.py -- do not hand-edit. -->")
    add("")
    add(
        f"Tokenizer: `{report['tokenizer']}` (NOT Anthropic's; treat totals as +/-10-20% estimates)."
    )
    add("")
    add("## Tree totals")
    add("")
    add(
        "| tree | root | files | always-on | fm-no-paths | lazy | always-on tok | lazy tok | all tok |"
    )
    add("|---|---|---|---|---|---|---|---|---|")
    for name, summary in report["summary"].items():
        counts = summary["counts"]
        add(
            f"| {name} | `{report['roots'][name]['path']}` | {summary['files']} | "
            f"{counts['always_on_no_frontmatter']} | {counts['frontmatter_without_paths']} | "
            f"{counts['lazy_paths_scoped']} | {summary['always_on_tokens']:,} | "
            f"{summary['lazy_tokens']:,} | {summary['all_tokens']:,} |"
        )
    add("")
    add("## Always-on set, per tree (measured frontmatter absence)")
    add("")
    for name, summary in report["summary"].items():
        files = report["trees"][name]
        add(
            f"**{name}** -- {len(summary['always_on_files'])} files, {summary['always_on_tokens']:,} tok"
        )
        add("")
        add("| file | tok |")
        add("|---|---|")
        for rel in sorted(
            summary["always_on_files"], key=lambda r: -files[r]["tokens"]
        ):
            add(f"| `{rel}` | {files[rel]['tokens']:,} |")
        add("")
    add("## Always-on floor (live rules + unconditional memory files)")
    add("")
    add("| layer | tok |")
    add("|---|---|")
    add(f"| live always-on rules | {report['summary']['live']['always_on_tokens']:,} |")
    for label, tokens in report["memory_files"].items():
        add(f"| `{label}` | {'ABSENT' if tokens is None else format(tokens, ',')} |")
    add(f"| **floor total** | **{report['always_on_floor_tokens']:,}** |")
    add("")
    add("## Drift")
    add("")
    add(
        "| comparison | only in first | only in second | content differs | load semantics differs |"
    )
    add("|---|---|---|---|---|")
    for label, diff in report["diffs"].items():
        add(
            f"| {label} | {len(diff['only_in_first'])} | {len(diff['only_in_second'])} | "
            f"{len(diff['content_differs'])} | {len(diff['load_semantics_differs'])} |"
        )
    add("")
    add("## Full classification (every rule, every tree)")
    add("")
    add("| file | repo | agent-self | live |")
    add("|---|---|---|---|")
    short = {
        "always_on_no_frontmatter": "ALWAYS-ON",
        "frontmatter_without_paths": "always-on(fm)",
        "lazy_paths_scoped": "lazy",
        None: "-",
    }
    every = sorted(set().union(*(set(files) for files in report["trees"].values())))
    for rel in every:
        cells = []
        for name in ("repo", "agent-self", "live"):
            info = report["trees"][name].get(rel)
            cells.append(short[info["load"]] if info else "-")
        add(f"| `{rel}` | {cells[0]} | {cells[1]} | {cells[2]} |")
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Detector controls. Every claim this script makes must be shown to FAIL on a broken input,
# otherwise its silence measures nothing (single-signal-verification.md rule 3b/3c).
# --------------------------------------------------------------------------------------


def self_test() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(
            f"  {'PASS' if ok else 'FAIL'}  {name}{(' -- ' + detail) if detail else ''}"
        )
        if not ok:
            failures.append(name)

    print("control 1: classifier flips between the two states (both-states)")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "bare.md").write_text("# no frontmatter\n", encoding="utf-8")
        (root / "scoped.md").write_text(
            '---\npaths: ["**/*.py"]\n---\n# body\n', encoding="utf-8"
        )
        (root / "fm_no_paths.md").write_text(
            "---\nname: x\n---\n# body\n", encoding="utf-8"
        )
        (root / "blocklist.md").write_text(
            "---\npaths:\n  - '**/hooks/**'\n  - '**/*.json'\n---\n# body\n",
            encoding="utf-8",
        )
        (root / "crlf.md").write_text("", encoding="utf-8")
        (root / "crlf.md").write_bytes(b'---\r\npaths: ["**/*"]\r\n---\r\n# body\r\n')
        scan = scan_tree(root, Counter())
        check(
            "bare.md -> always_on",
            scan["bare.md"]["load"] == "always_on_no_frontmatter",
            scan["bare.md"]["load"],
        )
        check(
            "scoped.md -> lazy",
            scan["scoped.md"]["load"] == "lazy_paths_scoped",
            scan["scoped.md"]["load"],
        )
        check(
            "fm_no_paths.md -> frontmatter_without_paths",
            scan["fm_no_paths.md"]["load"] == "frontmatter_without_paths",
            scan["fm_no_paths.md"]["load"],
        )
        check(
            "block-list selectors parsed",
            scan["blocklist.md"]["selectors"] == ["**/hooks/**", "**/*.json"],
            repr(scan["blocklist.md"]["selectors"]),
        )
        check(
            "CRLF frontmatter still parses as lazy",
            scan["crlf.md"]["load"] == "lazy_paths_scoped",
            scan["crlf.md"]["load"],
        )
        check(
            "inline-list selectors parsed",
            scan["scoped.md"]["selectors"] == ["**/*.py"],
            repr(scan["scoped.md"]["selectors"]),
        )

    print(
        "control 2: drift detector FIRES on a synthetic divergence and is silent on a clone"
    )
    with tempfile.TemporaryDirectory() as tmp:
        a_root, b_root = Path(tmp) / "a", Path(tmp) / "b"
        a_root.mkdir()
        b_root.mkdir()
        (a_root / "same.md").write_text("# identical\n", encoding="utf-8")
        (b_root / "same.md").write_text("# identical\n", encoding="utf-8")
        counter = Counter()
        clean = diff_trees(scan_tree(a_root, counter), scan_tree(b_root, counter))
        check("clone -> no content diff", clean["content_differs"] == [], repr(clean))
        (b_root / "same.md").write_text("# CHANGED\n", encoding="utf-8")
        (b_root / "extra.md").write_text("# only in b\n", encoding="utf-8")
        (a_root / "flip.md").write_text("# always on\n", encoding="utf-8")
        (b_root / "flip.md").write_text(
            '---\npaths: ["**/*"]\n---\n# demoted\n', encoding="utf-8"
        )
        dirty = diff_trees(scan_tree(a_root, counter), scan_tree(b_root, counter))
        # flip.md legitimately lands in BOTH buckets: adding frontmatter changes the bytes as
        # well as the load semantics. An assertion of ["same.md"] alone was my error, not the
        # detector's -- recorded here so the next reader does not "fix" the detector to match it.
        check(
            "divergence -> content diff fires",
            dirty["content_differs"] == ["flip.md", "same.md"],
            repr(dirty),
        )
        check(
            "extra file -> only_in_second fires",
            dirty["only_in_second"] == ["extra.md"],
            repr(dirty),
        )
        check(
            "frontmatter added -> load_semantics_differs fires",
            dirty["load_semantics_differs"] == ["flip.md"],
            repr(dirty),
        )

    print(
        "control 3: CRLF and LF of the same content produce identical hash and token count"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        body = "# heading\n\nsome body text that is long enough to tokenise.\n"
        (root / "lf.md").write_bytes(body.encode("utf-8"))
        (root / "crlf.md").write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
        scan = scan_tree(root, Counter())
        check(
            "CRLF == LF sha", scan["lf.md"]["sha256_lf"] == scan["crlf.md"]["sha256_lf"]
        )
        check("CRLF == LF tokens", scan["lf.md"]["tokens"] == scan["crlf.md"]["tokens"])

    print("control 4: the token counter is the real encoder, not a silent fallback")
    counter = Counter()
    check(
        "encoder is tiktoken/cl100k_base",
        counter.name == "tiktoken/cl100k_base",
        counter.name,
    )
    check(
        "known string -> known count",
        counter.count("hello world") == 2,
        str(counter.count("hello world")),
    )
    check("longer text costs more", counter.count("a" * 400) > counter.count("a" * 40))

    print("control 5: an empty scan is reported as empty, never as parity")
    with tempfile.TemporaryDirectory() as tmp:
        empty = scan_tree(Path(tmp), Counter())
        check("empty dir -> 0 files", empty == {}, repr(empty))
        check("missing dir -> 0 files", scan_tree(Path(tmp) / "nope", Counter()) == {})

    print("")
    if failures:
        print(
            f"FAILED:rule_audit-self-test {len(failures)} control(s) failed: {failures}"
        )
        return 1
    print("SUCCESS:rule_audit-self-test all controls passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", type=Path, help="write the machine-readable report here"
    )
    parser.add_argument(
        "--md", type=Path, help="write the generated markdown tables here"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run the detector controls and exit"
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    report = build()

    # Fail closed: an empty walk is a broken detector, never "the trees agree".
    if not report["trees"]["repo"]:
        print(
            "FAILED:rule_audit repo rules/ tree scanned to zero files -- detector broken"
        )
        return 1

    if args.json:
        args.json.write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
    if args.md:
        args.md.write_text(render_md(report), encoding="utf-8", newline="\n")

    for name, summary in report["summary"].items():
        counts = summary["counts"]
        print(
            f"{name:11s} files={summary['files']:3d} "
            f"always-on={len(summary['always_on_files']):2d} "
            f"(no-fm={counts['always_on_no_frontmatter']}, fm-no-paths={counts['frontmatter_without_paths']}) "
            f"lazy={counts['lazy_paths_scoped']:3d} "
            f"always-on-tok={summary['always_on_tokens']:6,d} all-tok={summary['all_tokens']:7,d}"
        )
    for label, diff in report["diffs"].items():
        print(
            f"{label}: content_differs={len(diff['content_differs'])} "
            f"only_first={len(diff['only_in_first'])} only_second={len(diff['only_in_second'])} "
            f"load_semantics_differs={len(diff['load_semantics_differs'])}"
        )
    print(
        f"always-on floor (live rules + memory files) = {report['always_on_floor_tokens']:,} tok"
    )
    print("SUCCESS:rule_audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
