"""PYTHON side of the parity oracle: drive the shared corpus, emit a byte manifest.

Thin I/O shell by design. All the canonicalisation lives in `agentspec.canonical`, which is
covered at 100% line+branch by the Python package's own gate; this file only builds values from
the corpus DSL, checks them against the declared expectation, and writes the manifest.

The manifest is written in BINARY with explicit LF. That is load-bearing on Windows:
`Path.write_text` translates "\\n" to CRLF, which in the scout probe made a 209,442-case float
fuzz report 209,442 phantom mismatches. Any cross-runtime byte fixture must pin newline
handling on BOTH ends or it produces spectacular false results.

Exit 0 = every case matched its expectation. Exit 1 = at least one disagreed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "agentspec"))

from agentspec.canonical import CanonicalJsonError, dumpb  # noqa: E402

CORPUS = HERE.parent / "fixtures" / "canonical-corpus.json"
NEST_KINDS = ("arr", "obj")


class CorpusError(ValueError):
    """The corpus file or a case is malformed. Distinct from a case FAILING."""


def build_value(node: Any) -> Any:
    """Materialise one value node. Mirrors `buildValue` in src/corpus.mjs."""
    if not isinstance(node, dict):
        raise CorpusError(f"value node must be a tagged object, got {node!r}")
    tags = list(node)
    if len(tags) != 1:
        raise CorpusError(f"value node must have exactly one tag, got {tags!r}")
    tag = tags[0]
    body = node[tag]
    if tag == "str":
        return body
    if tag == "int":
        return int(body)
    if tag == "num":
        return float(body)
    if tag == "bool":
        return body
    if tag == "null":
        return None
    if tag == "arr":
        return [build_value(item) for item in body]
    if tag == "obj":
        return _build_mapping(body)
    if tag == "nest":
        return _build_nest(body)
    raise CorpusError(f"unknown value tag {tag!r}")


def _build_mapping(pairs: Any) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise CorpusError(f"obj entries must be [key, node] pairs, got {pair!r}")
        mapping[pair[0]] = build_value(pair[1])
    return mapping


def _build_nest(body: Any) -> Any:
    kind = body["kind"]
    if kind not in NEST_KINDS:
        raise CorpusError(f"nest kind must be one of {list(NEST_KINDS)}, got {kind!r}")
    value: Any = 1
    for _ in range(body["depth"]):
        value = [value] if kind == "arr" else {"n": value}
    return value


def run_case(entry: dict[str, Any]) -> tuple[str, str]:
    """Return ``(status, payload)`` where payload is hex bytes for OK or the code for RJ."""
    value = build_value(entry["value"])
    try:
        return ("OK", dumpb(value).hex())
    except CanonicalJsonError as exc:
        return ("RJ", exc.code)


def expectation(entry: dict[str, Any]) -> tuple[str, str]:
    expect = entry["expect"]
    if "ok" in expect:
        return ("OK", expect["ok"].encode("utf-8").hex())
    if "reject" in expect:
        return ("RJ", expect["reject"])
    raise CorpusError(f"case {entry['id']}: expect must carry 'ok' or 'reject'")


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    entries = corpus["cases"]
    if not entries:
        raise CorpusError("corpus has no cases; an empty corpus passes vacuously")

    lines: list[str] = []
    failures: list[str] = []
    for entry in entries:
        status, payload = run_case(entry)
        want_status, want_payload = expectation(entry)
        if (status, payload) != (want_status, want_payload):
            failures.append(
                f"{entry['id']}: expected {want_status}/{want_payload!r}, got {status}/{payload!r}"
            )
        lines.append(f"{entry['id']}\t{status}\t{payload}")

    out = Path(sys.argv[1])
    out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    if failures:
        for failure in failures:
            print(f"FAILED:python-corpus {failure}", file=sys.stderr)
        return 1
    print(f"SUCCESS:python-corpus {len(entries)} cases matched the corpus expectation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
