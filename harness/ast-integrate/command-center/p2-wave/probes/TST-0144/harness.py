"""Shared TST-0144 probe helpers: strict cache + reducer condition 4 + mutant."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from completion.parse_cache import (  # noqa: E402
    ArtifactParseCache,
    DownstreamConsumer,
    ParseFailure,
)
from completion.reducer import Observation, judge  # noqa: E402

FIX = HERE / "fixtures"
COMPLETE_PATH = FIX / "complete.json"
TRUNCATED_PATH = FIX / "truncated.json"
SCHEMA_PATH = FIX / "artifact.schema.json"
COMPLETE_ID = "art-0144-complete"
TRUNCATED_ID = "art-0144-truncated"

# Mid-string cut after HELLO so required object fields are already closed.
COMPLETE_TEXT = (
    '{"id":"art-0144-complete","ok":true,'
    '"payload":{"label":"complete-value","n":42},'
    '"notes":"HELLO-FULL-NOTE"}\n'
)
CUT = COMPLETE_TEXT.index("HELLO") + len("HELLO")
TRUNCATED_TEXT = COMPLETE_TEXT[:CUT]


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def ensure_fixtures() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    if not COMPLETE_PATH.is_file():
        COMPLETE_PATH.write_text(COMPLETE_TEXT, encoding="utf-8", newline="\n")
    if not TRUNCATED_PATH.is_file():
        TRUNCATED_PATH.write_text(TRUNCATED_TEXT, encoding="utf-8", newline="\n")


def condition4(schema_ok: bool | None, artifact_path: Path, downstream_ok: bool) -> dict[str, Any]:
    obs = Observation(
        site="tst-0144-local",
        exit_code=0,
        state="SUCCESS",
        artifact_path=str(artifact_path),
        repo_root=str(REPO),
        min_bytes=1,
        sentinel="",
        schema_ok=schema_ok,
        evidence_anchor_count=1,
        tests_passed=True,
        negative_controls_ok=True,
        reviewer_verdict="PASS",
        open_p0_p1=0,
        registered=True,
        downstream_read_ok=downstream_ok,
    )
    verdict = judge(obs)
    row = next(c for c in verdict.conditions if c.n == 4)
    return {
        "basis": row.basis,
        "condition_4": row.outcome,
        "failing_condition_ids": list(verdict.failing_condition_ids),
        "verdict": verdict.verdict,
    }


def run_strict_both_states() -> dict[str, Any]:
    ensure_fixtures()
    schema = load_schema()
    complete_raw = COMPLETE_PATH.read_bytes()
    truncated_raw = TRUNCATED_PATH.read_bytes()
    if len(complete_raw) <= 0 or len(truncated_raw) <= 0:
        raise RuntimeError("fixtures must be non-empty")
    if truncated_raw == complete_raw:
        raise RuntimeError("truncated fixture must differ from complete")
    try:
        json.loads(truncated_raw.decode("utf-8"))
        raise RuntimeError("truncated fixture unexpectedly parsed")
    except json.JSONDecodeError:
        pass

    cache = ArtifactParseCache()
    consumer = DownstreamConsumer(cache)
    complete_obj = cache.parse(COMPLETE_ID, complete_raw, schema)
    consumer.ingest(COMPLETE_ID)
    complete_c4 = condition4(True, COMPLETE_PATH, cache.has(COMPLETE_ID))

    trunc_fail: dict[str, Any] | None = None
    try:
        cache.parse(TRUNCATED_ID, truncated_raw, schema)
        raised = False
    except ParseFailure as exc:
        raised = True
        trunc_fail = exc.as_dict()
    consumer.ingest(TRUNCATED_ID)
    trunc_inspect = cache.inspect(TRUNCATED_ID)
    trunc_c4 = condition4(
        False if raised else True,
        TRUNCATED_PATH,
        cache.has(TRUNCATED_ID),
    )

    ok = (
        cache.has(COMPLETE_ID) is True
        and consumer.holds(COMPLETE_ID) is True
        and complete_c4["condition_4"] == "SATISFIED"
        and raised is True
        and trunc_fail is not None
        and int(trunc_fail["byte_offset"]) >= 0
        and trunc_fail["kind"] == "json-decode"
        and cache.has(TRUNCATED_ID) is False
        and cache.get(TRUNCATED_ID) is None
        and consumer.holds(TRUNCATED_ID) is False
        and trunc_inspect["present"] is False
        and trunc_inspect["value"] is None
        and trunc_c4["condition_4"] == "UNSATISFIED"
        and 4 in trunc_c4["failing_condition_ids"]
        and complete_obj.get("id") == "art-0144-complete"
    )
    return {
        "complete": {
            "bytes": len(complete_raw),
            "cached": cache.has(COMPLETE_ID),
            "condition_4": complete_c4,
            "consumer_holds": consumer.holds(COMPLETE_ID),
            "id": COMPLETE_ID,
        },
        "ok": bool(ok),
        "truncated": {
            "bytes": len(truncated_raw),
            "cached": cache.has(TRUNCATED_ID),
            "condition_4": trunc_c4,
            "consumer_holds": consumer.holds(TRUNCATED_ID),
            "failure": trunc_fail,
            "id": TRUNCATED_ID,
            "inspect": trunc_inspect,
        },
    }


def repair_truncated_json(text: str) -> str:
    """Mutant: close an open string, then close unmatched braces/brackets."""
    s = text
    in_str = False
    escape = False
    for ch in s:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
    if in_str:
        s += '"'
    stack: list[str] = []
    in_str = False
    escape = False
    for ch in s:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack:
            stack.pop()
    return s + "".join(reversed(stack))


class LenientParseCache(ArtifactParseCache):
    """Negative-control mutant: repairs truncated JSON then caches the result."""

    def parse(
        self,
        artifact_id: str,
        raw: bytes | str,
        schema: Any = None,
    ) -> Any:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            return super().parse(artifact_id, text, schema)
        except ParseFailure:
            repaired = repair_truncated_json(text)
            return super().parse(artifact_id, repaired, schema)


def truncated_contract_holds(cache: ArtifactParseCache) -> dict[str, Any]:
    """Assertions this unit requires of a truncated artifact.

    Returns pass=True only when condition 4 fails AND the cache/consumer
    hold no entry. A repairing parser that caches a partial object fails.
    """
    ensure_fixtures()
    schema = load_schema()
    raw = TRUNCATED_PATH.read_bytes()
    consumer = DownstreamConsumer(cache)
    fail: dict[str, Any] | None = None
    try:
        cache.parse(TRUNCATED_ID, raw, schema)
        parsed = True
    except ParseFailure as exc:
        parsed = False
        fail = exc.as_dict()
    consumer.ingest(TRUNCATED_ID)
    inspect = cache.inspect(TRUNCATED_ID)
    c4 = condition4(
        False if not parsed else True,
        TRUNCATED_PATH,
        cache.has(TRUNCATED_ID),
    )
    holds = (
        parsed is False
        and fail is not None
        and int(fail.get("byte_offset", -1)) >= 0
        and cache.has(TRUNCATED_ID) is False
        and cache.get(TRUNCATED_ID) is None
        and consumer.holds(TRUNCATED_ID) is False
        and inspect["present"] is False
        and c4["condition_4"] == "UNSATISFIED"
    )
    return {
        "byte_offset": None if fail is None else fail.get("byte_offset"),
        "cached": cache.has(TRUNCATED_ID),
        "condition_4": c4["condition_4"],
        "consumer_holds": consumer.holds(TRUNCATED_ID),
        "failure": fail,
        "parsed": parsed,
        "pass": bool(holds),
    }
