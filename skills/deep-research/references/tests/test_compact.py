"""Keep-latest-3 compaction tests (Lens 12 find 4; pure, deterministic, no LLM)."""

from research_harness.compact import (
    COMPACTION_TRIGGER_TOKENS,
    KEEP_LATEST,
    Digest,
    ToolOutput,
    compact_ledger,
    compact_outputs,
    digest_sources,
    digest_text,
    should_compact,
    working_context_tokens,
)
from research_harness.grading import Source, grade_source

RAW = (
    "Solid-state batteries reached 500 Wh/kg in a 2026 pilot line. "
    "See https://a.example/report and https://b.example/paper for details.\n"
    "Second paragraph with more words that should not survive the digest.\n"
    "Third line https://a.example/report repeats a URL."
)


def _outputs(n):
    return [
        ToolOutput(
            index=i % 2, provider=f"p{i}", query_hash=f"h{i}", text=f"payload {i} " * 20
        )
        for i in range(n)
    ]


def test_defaults_match_the_lens():
    assert KEEP_LATEST == 3
    assert COMPACTION_TRIGGER_TOKENS == 32_000


def test_digest_text_is_deterministic_and_bounded():
    first = digest_text(RAW)
    assert first == digest_text(RAW)
    assert len(first) <= 320
    # Lead sentence, size facts and the DISTINCT URLs survive; the rest does not.
    assert "Solid-state batteries reached 500 Wh/kg" in first
    assert "3 lines" in first
    assert "2 URLs" in first
    assert "https://a.example/report" in first
    assert "https://b.example/paper" in first
    assert "Second paragraph" not in first


def test_digest_text_of_empty_or_whitespace_is_explicit():
    assert digest_text("") == "[digest] empty output"
    assert digest_text("   \n  ") == "[digest] empty output"


def test_compact_outputs_keeps_last_three_raw_and_digests_older():
    outputs = _outputs(5)
    compacted = compact_outputs(outputs)
    assert len(compacted) == 5
    assert all(isinstance(item, Digest) for item in compacted[:2])
    assert all(isinstance(item, ToolOutput) for item in compacted[2:])
    assert compacted[2:] == tuple(outputs[2:])
    digest = compacted[0]
    assert digest.provider == "p0" and digest.query_hash == "h0" and digest.index == 0
    assert digest.original_chars == len(outputs[0].text)
    assert digest.text.startswith("[digest p0 qh=h0]")
    assert len(digest.text) <= len(outputs[0].text)


def test_digest_is_never_longer_than_the_output_it_replaces():
    long_output = ToolOutput(0, "exa.web_search_exa", "h", RAW * 20)
    assert len(compact_outputs([long_output], keep_latest=0)[0].text) < len(RAW)
    tiny = ToolOutput(0, "p", "h", "short.")
    digest = compact_outputs([tiny], keep_latest=0)[0]
    assert isinstance(digest, Digest)
    assert len(digest.text) <= len(tiny.text)


def test_compact_outputs_with_three_or_fewer_is_identity():
    outputs = _outputs(3)
    assert compact_outputs(outputs) == tuple(outputs)
    assert compact_outputs([]) == ()


def test_compact_outputs_honours_a_custom_keep_latest():
    outputs = _outputs(4)
    compacted = compact_outputs(outputs, keep_latest=1)
    assert [type(item) for item in compacted] == [Digest, Digest, Digest, ToolOutput]


def test_compact_ledger_reads_tool_output_records_and_skips_other_events():
    records = [
        {"event": "plan"},
        {
            "event": "tool_output",
            "index": 0,
            "provider": "p0",
            "query_hash": "h0",
            "text": "a" * 50,
        },
        {"event": "subq_done", "index": 0},
        {
            "event": "tool_output",
            "index": 1,
            "provider": "p1",
            "query_hash": "h1",
            "text": "b" * 50,
        },
        {
            "event": "tool_output",
            "index": 1,
            "provider": "p2",
            "query_hash": "h2",
            "text": "c" * 50,
        },
        {
            "event": "tool_output",
            "index": 2,
            "provider": "p3",
            "query_hash": "h3",
            "text": "d" * 50,
        },
    ]
    compacted = compact_ledger(records)
    assert len(compacted) == 4
    assert isinstance(compacted[0], Digest) and compacted[0].query_hash == "h0"
    assert [item.query_hash for item in compacted[1:]] == ["h1", "h2", "h3"]


def test_should_compact_triggers_on_the_estimated_token_total():
    small = _outputs(2)
    assert not should_compact(small)
    big = [ToolOutput(0, "p", "h", "x" * (COMPACTION_TRIGGER_TOKENS * 4 + 4))]
    assert should_compact(big)
    assert working_context_tokens(big) > COMPACTION_TRIGGER_TOKENS
    assert should_compact(small, trigger_tokens=10)


def test_digest_sources_is_one_line_per_source_with_url_tier_grade_and_sentence():
    src_a = Source(
        "Pilot line report", "https://doi.org/10.1/aaa", "scholarly-access", 2026
    )
    src_b = Source("Forum thread", "https://forum.example/bbb", "unknown", 2020)
    grades = [
        grade_source(src_a, corroboration_count=2, reference_year=2026),
        grade_source(src_b, corroboration_count=1, reference_year=2026),
    ]
    text = digest_sources(
        [src_a, src_b],
        grades,
        evidence={"https://doi.org/10.1/aaa": "Reached 500 Wh/kg on the pilot line."},
    )
    lines = text.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("- https://doi.org/10.1/aaa | tier A | High")
    assert "[A.corrob x2.2026]" in lines[0]
    assert lines[0].endswith("Reached 500 Wh/kg on the pilot line.")
    assert "tier C | Low" in lines[1]
    assert "UNVERIFIED" in lines[1]


def test_digest_sources_caps_lines():
    sources = [Source(f"t{i}", f"https://x.example/{i}", "exa") for i in range(6)]
    grades = [grade_source(s, reference_year=2026) for s in sources]
    text = digest_sources(sources, grades, max_lines=4)
    lines = text.splitlines()
    assert len(lines) == 4
    assert lines[-1] == "- ... 3 more sources (in cache)"
