"""Parser-by-parser resolution table for one duplicate-key JSON fixture (TST-0054).

Every row in the table is produced by actually invoking the parser on the
fixture; nothing is assumed from documentation. Parsers that are not
installed on the host are reported with ``live: False`` and
``resolution: "unavailable"`` rather than an assumed value.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_TOOLS = _HERE.parents[1]
_REPO = _TOOLS.parent
if str(_TOOLS / "lib") not in sys.path:
    sys.path.insert(0, str(_TOOLS / "lib"))

import strict_json as sj  # noqa: E402

FIXTURE = sj.DUPLICATE_KEY_FIXTURE
DUPLICATE_KEY = "name"
FIRST = "first"
SECOND = "second"
RESOLUTIONS = ("first-wins", "last-wins", "error", "unavailable")

_NODE_MODULE = "tools/lib/net-allowlist.mjs"
_JSON_LOADS_RE = re.compile(r"\bjson\.loads?\(")


def independent_pairs_hook(text: str) -> list[list[Any]]:
    """Every member the decoder saw, in order, before any dict collapsing."""
    seen: list[list[Any]] = []

    def hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        seen.extend([k, v] for k, v in pairs)
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return seen


def _classify(value: Any) -> str:
    if value == FIRST:
        return "first-wins"
    if value == SECOND:
        return "last-wins"
    return "error"


def _row(
    parser_id: str,
    module: str,
    kind: str,
    in_pipeline: bool,
    resolution: str,
    resolved_value: Any = None,
    error: str | None = None,
    both_values_on_error: dict[str, Any] | None = None,
    live: bool = True,
) -> dict[str, Any]:
    return {
        "parser_id": parser_id,
        "module": module,
        "kind": kind,
        "in_pipeline": in_pipeline,
        "live": live,
        "assumed": False,
        "resolution": resolution,
        "resolved_value": resolved_value,
        "error": error,
        "both_values_on_error": both_values_on_error,
    }


def _stdlib_rows(text: str) -> list[dict[str, Any]]:
    import io

    rows = []
    loaded = json.loads(text)
    rows.append(
        _row("stdlib.json.loads", "json", "consumer", True,
             _classify(loaded.get(DUPLICATE_KEY)), loaded.get(DUPLICATE_KEY))
    )
    loaded = json.load(io.StringIO(text))
    rows.append(
        _row("stdlib.json.load", "json", "consumer", True,
             _classify(loaded.get(DUPLICATE_KEY)), loaded.get(DUPLICATE_KEY))
    )
    loaded = json.JSONDecoder().decode(text)
    rows.append(
        _row("stdlib.JSONDecoder.decode", "json", "consumer", True,
             _classify(loaded.get(DUPLICATE_KEY)), loaded.get(DUPLICATE_KEY))
    )
    return rows


def _strict_row(text: str) -> dict[str, Any]:
    try:
        loaded = sj.loads_strict(text)
    except sj.DuplicateKeyError as exc:
        return _row(
            "plugin.strict_json.loads_strict",
            "tools.lib.strict_json",
            "producer-reader",
            True,
            "error",
            None,
            f"{type(exc).__name__}: {exc}",
            {"key": exc.key, "first": exc.first, "second": exc.second},
        )
    return _row(
        "plugin.strict_json.loads_strict", "tools.lib.strict_json", "producer-reader",
        True, _classify(loaded.get(DUPLICATE_KEY)), loaded.get(DUPLICATE_KEY),
    )


def _external_row(parser_id: str, module: str, in_pipeline: bool, argv: list[str],
                  stdin: str) -> dict[str, Any]:
    exe = shutil.which(argv[0])
    if exe is None:
        return _row(parser_id, module, "consumer", in_pipeline, "unavailable",
                    None, f"{argv[0]} not on PATH", None, live=False)
    try:
        proc = subprocess.run(
            [exe, *argv[1:]], input=stdin, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _row(parser_id, module, "consumer", in_pipeline, "unavailable",
                    None, f"{type(exc).__name__}: {exc}", None, live=False)
    if proc.returncode != 0:
        return _row(parser_id, module, "consumer", in_pipeline, "error", None,
                    (proc.stderr or proc.stdout).strip()[:500], None)
    out = proc.stdout.strip()
    try:
        value = json.loads(out)
    except json.JSONDecodeError:
        value = out
    return _row(parser_id, module, "consumer", in_pipeline, _classify(value), value)


def pipeline_json_loads_callers(root: Path | None = None) -> list[str]:
    """Pipeline files that call json.load/json.loads (tools/plugin, tools/lib)."""
    base = Path(root) if root is not None else _TOOLS
    callers: list[str] = []
    for sub in ("plugin", "lib"):
        folder = base / sub
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.py")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if _JSON_LOADS_RE.search(text):
                callers.append(path.relative_to(_REPO).as_posix())
    return callers


def producer_duplicate_rejected() -> dict[str, Any]:
    """Both states of the producer: unique pairs emit; duplicate pairs raise."""
    unique = sj.dumps_from_pairs([(DUPLICATE_KEY, "only"), ("keep", True)],
                                 separators=(",", ":"))
    try:
        sj.dumps_from_pairs([(DUPLICATE_KEY, FIRST), (DUPLICATE_KEY, SECOND)])
        fired = False
        both: dict[str, Any] | None = None
        err = None
    except sj.DuplicateKeyError as exc:
        fired = True
        both = {"key": exc.key, "first": exc.first, "second": exc.second}
        err = f"{type(exc).__name__}: {exc}"
    return {
        "unique_emitted": unique,
        "unique_silent": json.loads(unique)[DUPLICATE_KEY] == "only",
        "duplicate_fires": fired,
        "both_values": both,
        "error": err,
    }


def measure_matrix() -> dict[str, Any]:
    text = FIXTURE
    pairs = independent_pairs_hook(text)
    occurrences = sum(1 for k, _v in pairs if k == DUPLICATE_KEY)
    parsers = [
        *_stdlib_rows(text),
        _strict_row(text),
        _external_row(
            "node.JSON.parse", _NODE_MODULE, True,
            ["node", "-e",
             "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
             "process.stdout.write(JSON.stringify(JSON.parse(d).name))})"],
            text,
        ),
        _external_row("jq", "jq", False, ["jq", "-c", ".name"], text),
    ]
    live = [r for r in parsers if r["live"]]
    resolutions = sorted({r["resolution"] for r in live})
    naive = json.loads(text)
    return {
        "unit_id": "TST-0054",
        "fixture": text,
        "duplicate_key": DUPLICATE_KEY,
        "independent_pairs_hook": pairs,
        "duplicate_name_occurrence_count": occurrences,
        "naive_json_loads_hides_duplicate": (
            occurrences > 1 and list(naive).count(DUPLICATE_KEY) == 1
        ),
        "parsers": parsers,
        "resolutions_observed": resolutions,
        "first_wins_parsers": [r["parser_id"] for r in live if r["resolution"] == "first-wins"],
        "last_wins_parsers": [r["parser_id"] for r in live if r["resolution"] == "last-wins"],
        "error_parsers": [r["parser_id"] for r in live if r["resolution"] == "error"],
        "unavailable_parsers": [r["parser_id"] for r in parsers if not r["live"]],
        "pipeline_json_loads_callers": pipeline_json_loads_callers(),
        "producer_duplicate_rejected": producer_duplicate_rejected(),
        "measured_live": True,
        "assumed": False,
    }


def assert_table_is_a_measurement(table: dict[str, Any]) -> dict[str, Any]:
    """Refuse a table whose rows were not produced by live invocation."""
    if not isinstance(table, dict) or table.get("fixture") != FIXTURE:
        raise AssertionError("table does not carry the duplicate-key fixture")
    rows = table.get("parsers") or []
    if not rows:
        raise AssertionError("table has no parser rows")
    for row in rows:
        if row.get("assumed") is not False:
            raise AssertionError(f"row {row.get('parser_id')} is assumed, not measured")
        if row.get("resolution") not in RESOLUTIONS:
            raise AssertionError(f"row {row.get('parser_id')} has an unknown resolution")
        if row.get("live") and row["resolution"] == "unavailable":
            raise AssertionError(f"row {row.get('parser_id')} is live yet unavailable")
    if table.get("duplicate_name_occurrence_count", 0) < 2:
        raise AssertionError("fixture does not repeat the key; the plant is dead")
    live = [r for r in rows if r.get("live") is True]
    if len({r["resolution"] for r in live}) < 2:
        raise AssertionError("a single resolution was observed; divergence not shown")
    callers = table.get("pipeline_json_loads_callers") or []
    return {
        "ok": True,
        "live_rows": len(live),
        "unavailable_rows": len(rows) - len(live),
        "resolutions_observed": sorted({r["resolution"] for r in live}),
        "pipeline_json_loads_caller_count": len(callers),
    }


__all__ = [
    "FIXTURE",
    "assert_table_is_a_measurement",
    "independent_pairs_hook",
    "measure_matrix",
    "pipeline_json_loads_callers",
    "producer_duplicate_rejected",
]
