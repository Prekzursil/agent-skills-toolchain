"""Increment 1 NDJSON event contract tests (``monitorcore.dbx_events``).

Covers the versioned envelope, ``dump_event`` one-line NDJSON emission, the
incremental ``EventReader`` and every tolerance it owes (torn final line,
malformed JSON, duplicate ``event_id``, non-monotonic ``sequence``, unknown
fields, oversize records, invalid UTF-8), the object-level ``redact`` walker,
and a 10,000-event replay held inside an explicit buffer cap.

Both-states discipline: every alarm is asserted to FIRE on the broken input
**and** to stay SILENT on a healthy control, so no detector here is silent in
both states.

The PEM case is PEM-DEFANGED (same convention as ``test_redact.py``): the
private-key markers are assembled from a separate dash run at run time, so the
committed test source carries no contiguous dashed BEGIN-private-key literal
(gitleaks stays green) while ``redact()`` still receives a genuine PEM block.
"""

import json
import os

import pytest

from monitorcore import dbx_events
from monitorcore.dbx_events import (
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    DbxEvent,
    EventReader,
    EventValidationError,
    digest_tool_args,
    dump_event,
    load_event,
    new_event,
    redact,
)

# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

_DASHES = "-" * 5


def _pem(*body: str) -> str:
    head = _DASHES + "BEGIN PRIVATE KEY" + _DASHES
    tail = _DASHES + "END PRIVATE KEY" + _DASHES
    return "\n".join((head, *body, tail))


# The 30 envelope fields the contract requires, spelled out here independently
# of the module so a silent rename in the implementation breaks this test.
_EXPECTED_FIELDS = (
    "schema_version",
    "program_run_id",
    "databricks_run_id",
    "batch_id",
    "logical_unit_id",
    "attempt_id",
    "agent_id",
    "parent_agent_id",
    "sequence",
    "event_id",
    "emitted_at_utc",
    "observed_at_utc",
    "lifecycle_state",
    "liveness_state",
    "progress_kind",
    "message_summary",
    "tool_name",
    "tool_arg_digest",
    "artifact_uri",
    "artifact_bytes",
    "artifact_sha256",
    "sentinel_state",
    "retry_count",
    "error_class",
    "lease_expiry",
    "heartbeat_age_s",
    "source_node",
    "model",
    "reasoning_effort",
    "input_bundle_hash",
)


def _evt(**over) -> DbxEvent:
    """A valid event with clean (non-secret, non-home-path) defaults."""
    base = dict(
        program_run_id="r-20260721T2100Z",
        databricks_run_id="dbx-778812",
        batch_id="b-03",
        logical_unit_id="u-0117",
        attempt_id=1,
        agent_id="a-0117",
        parent_agent_id=None,
        sequence=1,
        event_id="e-000001",
        emitted_at_utc=1784500123.884,
        observed_at_utc=1784500124.101,
        lifecycle_state="RUNNING",
        liveness_state="WORKING",
        progress_kind="tool",
        message_summary="applied the patch",
        tool_name=None,
        artifact_uri=None,
        artifact_bytes=None,
        artifact_sha256=None,
        sentinel_state="ABSENT",
        retry_count=0,
        error_class=None,
        lease_expiry=1784500200.0,
        heartbeat_age_s=1.5,
        source_node="ip-10-0-0-7",
        model="gpt-5.6-sol",
        reasoning_effort="ultra",
        input_bundle_hash="sha256:" + "1c9" * 21 + "a",
    )
    base.update(over)
    return new_event(**base)


def _write_lines(path, events, *, trailing_newline=True):
    body = "\n".join(dump_event(e) for e in events)
    if trailing_newline:
        body += "\n"
    path.write_bytes(body.encode("utf-8"))
    return body


# --------------------------------------------------------------------------
# 1. Envelope + round-trip
# --------------------------------------------------------------------------


def test_valid_event_round_trip():
    evt = _evt(sequence=7, event_id="e-000007")
    line = dump_event(evt)
    assert "\n" not in line

    back = load_event(json.loads(line))
    assert back == evt
    assert back.schema_version == SCHEMA_VERSION
    assert back.sequence == 7
    assert back.event_id == "e-000007"
    assert back.parent_agent_id is None  # nullable field survives as None


def test_dump_event_is_one_ndjson_line():
    evt = _evt(message_summary="one\ntwo\r\nthree four five")
    line = dump_event(evt)

    # ONE NDJSON record: no raw line terminator of any flavour may survive.
    for terminator in ("\n", "\r", " ", " "):
        assert terminator not in line

    back = load_event(json.loads(line))
    assert back.message_summary == "one\ntwo\r\nthree four five"


def test_envelope_carries_every_required_field():
    assert set(REQUIRED_FIELDS) == set(_EXPECTED_FIELDS)
    assert len(REQUIRED_FIELDS) == len(_EXPECTED_FIELDS) == 30

    payload = json.loads(dump_event(_evt()))
    for name in _EXPECTED_FIELDS:
        assert name in payload, name

    # A missing required field is a validation error, never a silent default.
    del payload["lifecycle_state"]
    with pytest.raises(EventValidationError):
        load_event(payload)


def test_future_schema_version_is_rejected():
    payload = json.loads(dump_event(_evt()))

    payload["schema_version"] = SCHEMA_VERSION + 1
    with pytest.raises(EventValidationError):
        load_event(payload)

    # Both-states control: the current version loads cleanly.
    payload["schema_version"] = SCHEMA_VERSION
    assert load_event(payload).schema_version == SCHEMA_VERSION


# --------------------------------------------------------------------------
# 2. Malformed JSON
# --------------------------------------------------------------------------


def test_malformed_json_line_is_skipped_and_counted(tmp_path):
    path = tmp_path / "u.ndjson"
    good_a = dump_event(_evt(sequence=1, event_id="e-1"))
    good_b = dump_event(_evt(sequence=2, event_id="e-2"))
    path.write_bytes(
        (good_a + "\n" + '{"schema_version": 1, "oops"' + "\n" + good_b + "\n").encode(
            "utf-8"
        )
    )

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2"]  # healthy lines survive
    assert reader.stats.parse_errors == 1

    # Both-states control: a clean file records ZERO parse errors.
    clean = tmp_path / "clean.ndjson"
    _write_lines(clean, [_evt(sequence=1, event_id="c-1")])
    clean_reader = EventReader(clean)
    assert len(list(clean_reader.read_new())) == 1
    assert clean_reader.stats.parse_errors == 0


# --------------------------------------------------------------------------
# 3-4. Partial / torn lines
# --------------------------------------------------------------------------


def test_truncated_final_line_then_completed(tmp_path):
    path = tmp_path / "u.ndjson"
    whole = dump_event(_evt(sequence=1, event_id="e-1"))
    torn = dump_event(_evt(sequence=2, event_id="e-2"))
    cut = len(torn) // 2
    path.write_bytes((whole + "\n" + torn[:cut]).encode("utf-8"))

    reader = EventReader(path)
    first = list(reader.read_new())

    assert [e.event_id for e in first] == ["e-1"]
    assert reader.stats.parse_errors == 0  # a torn tail is NOT a parse error
    assert reader.stats.accepted == 1
    assert reader.buffer_bytes > 0  # it IS buffered, not discarded

    with open(path, "ab") as fh:
        fh.write((torn[cut:] + "\n").encode("utf-8"))

    second = list(reader.read_new())
    assert [e.event_id for e in second] == ["e-2"]
    assert reader.stats.accepted == 2
    assert reader.stats.parse_errors == 0
    assert reader.buffer_bytes == 0

    # Yielded exactly once: a third read produces nothing.
    assert list(reader.read_new()) == []


def test_partial_line_completed_by_next_read(tmp_path):
    path = tmp_path / "u.ndjson"
    path.write_bytes(b"")
    raw = (dump_event(_evt(sequence=1, event_id="e-1")) + "\n").encode("utf-8")

    reader = EventReader(path)
    yielded = []
    for i in range(len(raw)):
        with open(path, "ab") as fh:
            fh.write(raw[i : i + 1])
        yielded.extend(reader.read_new())
        # Nothing may be emitted until the terminator lands.
        assert len(yielded) == (1 if i == len(raw) - 1 else 0)

    assert [e.event_id for e in yielded] == ["e-1"]
    assert reader.stats.parse_errors == 0
    assert reader.stats.accepted == 1

    # Both-states control: a COMPLETE line advances fully on the first read, so
    # the reader is not simply always refusing to advance.
    whole = tmp_path / "whole.ndjson"
    _write_lines(whole, [_evt(sequence=1, event_id="w-1")])
    whole_reader = EventReader(whole)
    assert [e.event_id for e in whole_reader.read_new()] == ["w-1"]
    assert whole_reader.buffer_bytes == 0


# --------------------------------------------------------------------------
# 5-6. Sequence monotonicity
# --------------------------------------------------------------------------


def test_duplicate_sequence_is_accepted_and_flagged(tmp_path):
    path = tmp_path / "u.ndjson"
    _write_lines(
        path,
        [
            _evt(sequence=1, event_id="e-1"),
            _evt(sequence=2, event_id="e-2"),
            _evt(sequence=2, event_id="e-3"),  # duplicate seq, distinct event_id
        ],
    )

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2", "e-3"]  # ACCEPTED
    assert reader.stats.monotonic_violations == 1  # but FLAGGED
    assert "e-3" in reader.recent_monotonic_violations

    # Both-states control: strictly ascending sequences flag nothing.
    clean = tmp_path / "clean.ndjson"
    _write_lines(
        clean,
        [_evt(sequence=1, event_id="c-1"), _evt(sequence=2, event_id="c-2")],
    )
    clean_reader = EventReader(clean)
    assert len(list(clean_reader.read_new())) == 2
    assert clean_reader.stats.monotonic_violations == 0


def test_out_of_order_sequence_is_accepted_and_flagged(tmp_path):
    path = tmp_path / "u.ndjson"
    _write_lines(
        path,
        [
            _evt(sequence=1, event_id="e-1"),
            _evt(sequence=5, event_id="e-2"),
            _evt(sequence=3, event_id="e-3"),  # arrives late
            _evt(sequence=6, event_id="e-4"),
        ],
    )

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2", "e-3", "e-4"]  # ACCEPTED
    assert reader.stats.monotonic_violations == 1
    assert "e-3" in reader.recent_monotonic_violations
    assert reader.high_water_sequence("u-0117", 1) == 6

    # A gap (1 -> 5) is not a violation; only regression is.
    assert reader.stats.accepted == 4


# --------------------------------------------------------------------------
# 7. Duplicate event_id
# --------------------------------------------------------------------------


def test_duplicate_event_id_is_rejected_and_counted(tmp_path):
    path = tmp_path / "u.ndjson"
    _write_lines(
        path,
        [
            _evt(sequence=1, event_id="e-1"),
            _evt(sequence=2, event_id="e-2"),
            _evt(sequence=3, event_id="e-1"),  # replayed append
        ],
    )

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2"]  # duplicate REJECTED
    assert reader.stats.duplicates == 1
    assert reader.stats.accepted == 2

    # Both-states control: all-distinct ids count zero duplicates.
    clean = tmp_path / "clean.ndjson"
    _write_lines(
        clean,
        [_evt(sequence=1, event_id="c-1"), _evt(sequence=2, event_id="c-2")],
    )
    clean_reader = EventReader(clean)
    assert len(list(clean_reader.read_new())) == 2
    assert clean_reader.stats.duplicates == 0


# --------------------------------------------------------------------------
# 8. Unknown fields (forward compatibility)
# --------------------------------------------------------------------------


def test_unknown_fields_are_preserved(tmp_path):
    payload = json.loads(dump_event(_evt()))
    payload["future_field"] = {"nested": [1, 2, 3]}
    payload["another_new_one"] = "hello"

    evt = load_event(payload)
    assert evt.extra["future_field"] == {"nested": [1, 2, 3]}
    assert evt.extra["another_new_one"] == "hello"

    # Re-emitting must not drop them.
    again = json.loads(dump_event(evt))
    assert again["future_field"] == {"nested": [1, 2, 3]}
    assert again["another_new_one"] == "hello"

    # And they survive a trip through the reader.
    path = tmp_path / "u.ndjson"
    path.write_bytes((json.dumps(payload) + "\n").encode("utf-8"))
    reader = EventReader(path)
    (got,) = list(reader.read_new())
    assert got.extra["future_field"] == {"nested": [1, 2, 3]}


# --------------------------------------------------------------------------
# 9. Oversize records
# --------------------------------------------------------------------------


def test_oversize_record_is_rejected_and_counted(tmp_path):
    cap = 2048
    path = tmp_path / "u.ndjson"
    small = dump_event(_evt(sequence=1, event_id="e-1"))
    huge = dump_event(_evt(sequence=2, event_id="e-2", message_summary="A" * cap * 3))
    after = dump_event(_evt(sequence=3, event_id="e-3"))
    path.write_bytes(("\n".join((small, huge, after)) + "\n").encode("utf-8"))

    reader = EventReader(path, max_record_bytes=cap, chunk_bytes=256)
    got = list(reader.read_new())

    # Oversize record dropped; the reader RESYNCS to the next line.
    assert [e.event_id for e in got] == ["e-1", "e-3"]
    assert reader.stats.oversize == 1
    # The giant line was never buffered whole - the cap is hard.
    assert reader.buffer_high_water <= cap
    assert reader.buffer_high_water <= reader.max_buffer_bytes

    # Both-states control: under the cap, nothing is rejected.
    clean = tmp_path / "clean.ndjson"
    _write_lines(clean, [_evt(sequence=1, event_id="c-1")])
    clean_reader = EventReader(clean, max_record_bytes=cap, chunk_bytes=256)
    assert len(list(clean_reader.read_new())) == 1
    assert clean_reader.stats.oversize == 0


# --------------------------------------------------------------------------
# 10. Invalid UTF-8
# --------------------------------------------------------------------------


def test_invalid_utf8_is_replaced_not_raised(tmp_path):
    path = tmp_path / "u.ndjson"
    good = dump_event(_evt(sequence=1, event_id="e-1")).encode("utf-8")
    # Structurally valid JSON, invalid UTF-8, and missing every required field.
    bad = b'{"schema_version": 1, "message_summary": "\xff\xfe caf\xe9"}'
    # Valid event whose message_summary carries raw invalid UTF-8 bytes.
    dirty = dump_event(
        _evt(sequence=2, event_id="e-2", message_summary="MARKERBYTE")
    ).encode("utf-8")
    dirty = dirty.replace(b"MARKERBYTE", b"\xff\xfe")

    path.write_bytes(good + b"\n" + bad + b"\n" + dirty + b"\n")

    reader = EventReader(path)
    got = list(reader.read_new())  # must not raise

    assert [e.event_id for e in got] == ["e-1", "e-2"]
    assert reader.stats.parse_errors == 0  # the bad line parses as JSON...
    assert reader.stats.invalid == 1  # ...and dies on validation instead
    # Replaced, never raised:
    assert "�" in got[1].message_summary


# --------------------------------------------------------------------------
# 11. Redaction
# --------------------------------------------------------------------------


def test_secret_shaped_tool_argument_is_redacted():
    secret_key = "sk-" + "A" * 40
    secret_dapi = "dapi" + "0123456789abcdef" * 2
    secret_pem = _pem("MIIBOgIBAAJBAKj34GkxFhD9pcvfNwaaaa")
    secret_entropy = "Zm9vYmFyc2VjcmV0kQ8vN3xP7tR2wY9zL5aH1bJ6cD4eF0gG"

    args = {
        "path": "/tmp/x.txt",
        "api_key": secret_key,
        "auth": {"token": secret_dapi},
        "pem": secret_pem,
        "blob": secret_entropy,
        "note": "plain english, nothing secret here",
    }

    evt = _evt(
        tool_name="Bash",
        tool_args=args,
        message_summary="invoked with " + secret_key,
    )
    line = dump_event(evt)

    for secret in (secret_key, secret_dapi, secret_entropy):
        assert secret not in line
    assert "PRIVATE KEY" not in line

    # Only a digest is emitted - the raw argument object never reaches the wire.
    payload = json.loads(line)
    assert "tool_args" not in payload
    assert payload["tool_arg_digest"].startswith("sha256:")
    assert secret_key not in json.dumps(payload)

    # And redact() alone scrubs the object.
    scrubbed = redact(args)
    blob = json.dumps(scrubbed)
    for secret in (secret_key, secret_dapi, secret_entropy):
        assert secret not in blob
    assert "PRIVATE KEY" not in blob
    assert scrubbed["path"] == "/tmp/x.txt"  # benign value untouched


def test_benign_values_survive_redaction():
    """Both-states control: the redactor is not a blanket that masks everything."""
    benign = {
        "sentence": "sk- is a prefix of an ordinary word here",
        "digest": "3f786850e387550fdab836ed7e6dc881de23001b",  # sha1 hex
        "sha256": "a" * 64,
        "count": 42,
        "flag": True,
        "nothing": None,
        "items": ["alpha", "beta"],
    }
    assert redact(benign) == benign


# --------------------------------------------------------------------------
# 12. Bounded memory over a large replay
# --------------------------------------------------------------------------


def test_ten_thousand_event_replay_stays_bounded(tmp_path):
    n = 10_000
    cap = 8192
    path = tmp_path / "big.ndjson"
    with open(path, "wb") as fh:
        for i in range(n):
            line = dump_event(_evt(sequence=i, event_id=f"e-{i:06d}"))
            fh.write((line + "\n").encode("utf-8"))

    size = path.stat().st_size
    assert size > 20 * cap  # the file dwarfs the buffer cap, or this proves nothing

    reader = EventReader(
        path, max_record_bytes=cap, chunk_bytes=1024, recent_event_ids=256
    )

    seen = 0
    for _ in reader.read_new():
        seen += 1
        # Checked DURING the stream, not only at the end.
        assert reader.buffer_bytes <= cap

    assert seen == n
    assert reader.stats.accepted == n
    assert reader.stats.duplicates == 0
    assert reader.stats.monotonic_violations == 0
    assert reader.stats.parse_errors == 0
    assert reader.stats.bytes_read == size

    # The explicit cap held, and the reader's retained state is bounded by
    # configuration rather than by file length.
    assert reader.buffer_high_water <= cap
    assert reader.buffer_high_water <= reader.max_buffer_bytes
    assert reader.tracked_event_ids <= 256
    assert reader.tracked_units <= reader.max_tracked_units


# --------------------------------------------------------------------------
# 13. Field-level validation: every rejection is TYPED and NAMES the field
#
# A silently-defaulted or silently-coerced field is indistinguishable from a
# measured one, so each wrong shape must raise rather than be repaired.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected"),
    [
        # A non-nullable field carrying null.
        ("source_node", None, "may not be null"),
        # bool is a subclass of int; a boolean sequence number is a defect, not a 1.
        ("sequence", True, "must be an integer"),
        ("attempt_id", False, "must be an integer"),
        # ... and the same trap on the float fields.
        ("emitted_at_utc", True, "must be a number"),
        ("heartbeat_age_s", True, "must be a number"),
        # A string field handed a number must NOT be str()-ed into shape.
        ("source_node", 123, "must be a string"),
        ("program_run_id", 4.5, "must be a string"),
        # An enum field outside its vocabulary.
        ("lifecycle_state", "NOPE", "unknown value"),
        ("liveness_state", "BUSY", "unknown value"),
        ("progress_kind", "chatter", "unknown value"),
        ("sentinel_state", "MAYBE", "unknown value"),
    ],
)
def test_wrong_field_shape_is_rejected_and_names_the_field(
    field_name, bad_value, expected
):
    """Each rejection carries the offending FIELD NAME, so a bad producer is findable."""
    payload = json.loads(dump_event(_evt()))
    payload[field_name] = bad_value

    with pytest.raises(EventValidationError) as excinfo:
        load_event(payload)

    message = str(excinfo.value)
    assert expected in message
    assert field_name in message, "the error must name the field that failed"


def test_nullable_fields_accept_null_but_non_nullable_ones_do_not():
    """Both-states control for the null rule: it is a whitelist, not a blanket ban."""
    payload = json.loads(dump_event(_evt()))

    # Every declared-nullable field genuinely loads as None.
    for name in dbx_events.NULLABLE_FIELDS:
        probe = dict(payload)
        probe[name] = None
        assert getattr(load_event(probe), name) is None, name

    # And nothing outside that set does.
    for name in REQUIRED_FIELDS:
        if name in dbx_events.NULLABLE_FIELDS:
            continue
        probe = dict(payload)
        probe[name] = None
        with pytest.raises(EventValidationError):
            load_event(probe)


def test_new_event_refuses_to_STAMP_a_future_schema_version():
    """The WRITER-side version gate.

    ``test_future_schema_version_is_rejected`` covers the READER (``load_event``).
    This is the other end: a producer cannot mint an event claiming a schema this
    build does not implement, so an unreadable record is never created in the first
    place.
    """
    with pytest.raises(EventValidationError) as excinfo:
        _evt(schema_version=SCHEMA_VERSION + 1)
    assert "unsupported schema_version" in str(excinfo.value)

    # Both-states control: the current version mints cleanly.
    assert _evt(schema_version=SCHEMA_VERSION).schema_version == SCHEMA_VERSION


@pytest.mark.parametrize("payload", ["not a dict", [1, 2, 3], 42, None, 3.5])
def test_a_non_object_payload_is_rejected(payload):
    """A JSON array/scalar is not an envelope. Refused, never coerced."""
    with pytest.raises(EventValidationError) as excinfo:
        load_event(payload)
    assert "must be a JSON object" in str(excinfo.value)


@pytest.mark.parametrize("version", ["1", True, 1.5, None, [1]])
def test_a_non_integer_schema_version_is_rejected(version):
    """The version field gates every other rule, so its own TYPE is checked first.

    ``True`` is the sharp case: ``bool`` is a subclass of ``int``, so a naive
    ``isinstance(v, int)`` would accept ``True`` as version 1 and validate the whole
    record against a version the producer never claimed.
    """
    payload = json.loads(dump_event(_evt()))
    payload["schema_version"] = version

    with pytest.raises(EventValidationError) as excinfo:
        load_event(payload)
    assert "schema_version must be an integer" in str(excinfo.value)


# --------------------------------------------------------------------------
# 14. Redaction: depth cap, unknown types, and the FAIL-CLOSED guarantee
#
# The contract is that a raising redactor NEVER returns the raw text. Each test
# below breaks one rung of the ladder and asserts the masked marker comes out
# instead of the secret.
# --------------------------------------------------------------------------


def test_deeply_nested_payload_is_capped_not_stack_overflowed():
    """A hostile nest is truncated with a marker rather than exhausting the stack."""
    depth = dbx_events.MAX_REDACT_DEPTH + 8
    deep: dict = {}
    cursor = deep
    for _ in range(depth):
        cursor["a"] = {}
        cursor = cursor["a"]
    cursor["leaf"] = "sentinel-value"

    rendered = json.dumps(redact(deep))

    assert "[REDACTED:max-depth]" in rendered
    # The cap did its job: the payload beyond the limit never surfaced.
    assert "sentinel-value" not in rendered

    # Both-states control: a shallow nest is untouched.
    shallow = {"a": {"b": {"c": "sentinel-value"}}}
    assert redact(shallow) == shallow


def test_an_object_of_unknown_type_is_stringified_then_redacted():
    """No opaque object reaches the wire: it is str()-ed, then run through the ladder."""

    class Opaque:
        def __str__(self) -> str:
            return "plain-object-repr"

    class Secretive:
        def __str__(self) -> str:
            return "sk-" + "A" * 40

    assert redact(Opaque()) == "plain-object-repr"
    # The stringified form is still subject to pattern masking.
    assert "sk-" + "A" * 40 not in json.dumps(redact(Secretive()))


def test_an_object_whose_str_raises_fails_closed():
    """``str()`` blowing up must not propagate, and must not leak the object."""

    class Exploding:
        def __str__(self) -> str:
            raise RuntimeError("str() blew up")

    assert redact(Exploding()) == "[REDACTED:redaction-failed]"


def test_a_raising_pattern_redactor_fails_closed(monkeypatch):
    """If the shared pattern pass throws, the RAW text must never be returned."""
    secret = "hunter2-plaintext-value"

    def boom(_text):
        raise RuntimeError("pattern engine exploded")

    monkeypatch.setattr(dbx_events, "_redact_text", boom)

    assert redact(secret) == "[REDACTED:redaction-failed]"
    assert redact({"note": secret}) == {"note": "[REDACTED:redaction-failed]"}

    # Both-states control: unpatched, the same benign value passes through.
    monkeypatch.undo()
    assert redact(secret) == secret


def test_a_raising_entropy_check_fails_closed(monkeypatch):
    """The entropy rung is the last one; if IT throws, still no raw text escapes."""
    value = "an-ordinary-looking-value"

    def boom(_text):
        raise RuntimeError("entropy math exploded")

    monkeypatch.setattr(dbx_events, "_is_high_entropy", boom)

    assert redact(value) == "[REDACTED:redaction-failed]"

    monkeypatch.undo()
    assert redact(value) == value


def test_a_raising_key_name_matcher_fails_closed(monkeypatch):
    """A broken key-name matcher drops the VALUE rather than passing it through.

    This is the rung that decides "is this key called ``password``?". If it cannot
    answer, the safe answer is to mask, because the alternative is emitting a
    credential on the strength of a detector that just crashed.
    """

    class BrokenMatcher:
        def search(self, _name):
            raise RuntimeError("regex engine exploded")

    monkeypatch.setattr(dbx_events, "_SECRET_KEY_RE", BrokenMatcher())

    out = redact({"anything": "plaintext-value", "nested": {"k": "v"}})

    assert out == {
        "anything": "[REDACTED:redaction-failed]",
        "nested": "[REDACTED:redaction-failed]",
    }
    assert "plaintext-value" not in json.dumps(out)

    # Both-states control: with a working matcher the benign keys survive.
    monkeypatch.undo()
    assert redact({"anything": "plaintext-value"}) == {"anything": "plaintext-value"}


def test_shannon_entropy_of_the_degenerate_inputs():
    """The entropy helper's boundary contract.

    NOTE: the empty-string branch is NOT reachable through the public ``redact()``
    path — ``_is_high_entropy`` short-circuits on ``len(text) < HIGH_ENTROPY_MIN_LEN``
    long before it would divide by zero — so this exercises the helper directly. It
    is still a real contract: the function is documented as returning bits/char, and
    0.0 is the only correct answer for "no information".
    """
    assert dbx_events._shannon_bits("") == 0.0
    # One repeated symbol carries no information either.
    assert dbx_events._shannon_bits("aaaaaaaa") == 0.0
    # Two equiprobable symbols carry exactly one bit per character.
    assert dbx_events._shannon_bits("abababab") == pytest.approx(1.0)
    # Four equiprobable symbols carry exactly two.
    assert dbx_events._shannon_bits("abcdabcd") == pytest.approx(2.0)


def test_tool_arg_digest_survives_an_uncanonicalisable_payload():
    """A payload JSON cannot canonicalise still yields a STABLE digest, never a raise.

    ``sort_keys=True`` cannot order a dict with mixed-type keys (``'<' not supported
    between instances of 'str' and 'int'``), which is exactly the shape a real tool
    call can carry. The digest is the ONLY representation of tool arguments that
    reaches the wire, so failing to produce one would either crash the producer or
    tempt it into emitting raw arguments instead.
    """
    awkward = {1: "a", "b": 2}

    digest = digest_tool_args(awkward)

    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    # Stable across calls — a digest that moves is useless for comparison.
    assert digest == digest_tool_args({1: "a", "b": 2})
    # ...and still discriminating.
    assert digest != digest_tool_args({1: "a", "b": 3})

    # Both-states control: an ordinary payload digests through the normal path.
    ordinary = digest_tool_args({"b": 2, "a": 1})
    assert ordinary.startswith("sha256:")
    assert ordinary == digest_tool_args({"a": 1, "b": 2}), "key order must not matter"


# --------------------------------------------------------------------------
# 15. Reader introspection: the resume cursor a caller persists
# --------------------------------------------------------------------------


def test_reader_exposes_its_path_and_advances_its_offset(tmp_path):
    """``offset`` is the resume cursor; it must advance on data and hold on silence."""
    path = tmp_path / "u.ndjson"
    _write_lines(
        path, [_evt(sequence=1, event_id="e-1"), _evt(sequence=2, event_id="e-2")]
    )
    size = path.stat().st_size

    reader = EventReader(path)

    assert reader.path == str(path)
    assert reader.offset == 0, "nothing consumed yet"

    got = list(reader.read_new())
    assert [e.event_id for e in got] == ["e-1", "e-2"]
    assert reader.offset == size, (
        "a fully-consumed newline-terminated file lands on EOF"
    )

    # A read with no new bytes is a no-op: no events, no cursor movement.
    assert list(reader.read_new()) == []
    assert reader.offset == size


# --------------------------------------------------------------------------
# 16. I/O failure is a DETECTOR failure, never an empty feed
#
# The distinction matters operationally: "no events" invites the monitor to
# render a quiet unit, while "could not read" must render as UNREACHABLE.
# --------------------------------------------------------------------------


def test_a_missing_file_counts_an_io_error_rather_than_reporting_silence(tmp_path):
    """``stat`` failing is counted, not swallowed, and never latches."""
    missing = tmp_path / "never-created.ndjson"
    reader = EventReader(missing)

    assert list(reader.read_new()) == []
    assert reader.stats.io_errors == 1
    assert reader.stats.accepted == 0

    # It keeps counting: a still-missing file on the next poll is a SECOND failure,
    # not a remembered one.
    assert list(reader.read_new()) == []
    assert reader.stats.io_errors == 2

    # Both-states control: a readable file records zero I/O errors.
    healthy = tmp_path / "ok.ndjson"
    _write_lines(healthy, [_evt(sequence=1, event_id="h-1")])
    ok_reader = EventReader(healthy)
    assert len(list(ok_reader.read_new())) == 1
    assert ok_reader.stats.io_errors == 0


def test_a_file_deleted_between_stat_and_open_counts_an_io_error(tmp_path, monkeypatch):
    """The documented stat-then-open race.

    ``read_new`` sizes the file and only then opens it. A rotation landing in that
    window makes ``open`` fail on a path that had just reported a size. Simulated by
    faking ONLY this path's ``getsize`` so the sequence is deterministic on every
    platform rather than dependent on winning a real race.
    """
    missing = tmp_path / "vanished.ndjson"
    real_getsize = os.path.getsize

    def fake_getsize(target):
        if str(target) == str(missing):
            return 4096  # the stat that succeeded a moment before the delete
        return real_getsize(target)

    monkeypatch.setattr(dbx_events.os.path, "getsize", fake_getsize)

    reader = EventReader(missing)

    assert list(reader.read_new()) == []
    assert reader.stats.io_errors == 1
    assert reader.stats.bytes_read == 0, "nothing was read, so nothing may be counted"


def test_a_truncated_or_rotated_file_restarts_instead_of_going_silent(tmp_path):
    """A file that SHRANK below the cursor is a new file; seeking past its end would
    leave the reader permanently blind, so it restarts from zero and counts a rotation.
    """
    path = tmp_path / "u.ndjson"
    _write_lines(
        path, [_evt(sequence=1, event_id="e-1"), _evt(sequence=2, event_id="e-2")]
    )
    big_size = path.stat().st_size

    reader = EventReader(path)
    assert [e.event_id for e in reader.read_new()] == ["e-1", "e-2"]
    assert reader.offset == big_size
    assert reader.stats.rotations == 0

    # Rotate: replace the file with a SHORTER one.
    _write_lines(path, [_evt(sequence=1, event_id="e-3")])
    small_size = path.stat().st_size
    assert small_size < big_size, (
        "the fixture must actually shrink, or this proves nothing"
    )

    got = list(reader.read_new())

    assert reader.stats.rotations == 1
    assert [e.event_id for e in got] == ["e-3"], (
        "the post-rotation file is read from byte 0"
    )
    assert reader.offset == small_size

    # Both-states control: ordinary GROWTH is not a rotation.
    with open(path, "ab") as fh:
        fh.write((dump_event(_evt(sequence=2, event_id="e-4")) + "\n").encode("utf-8"))
    assert [e.event_id for e in reader.read_new()] == ["e-4"]
    assert reader.stats.rotations == 1


# --------------------------------------------------------------------------
# 17. Line-level tolerances: blank, oversize-in-one-chunk, and non-object lines
# --------------------------------------------------------------------------


def test_blank_and_whitespace_only_lines_are_benign(tmp_path):
    """Padding is not an anomaly: skipped silently, and no error counter moves."""
    path = tmp_path / "u.ndjson"
    first = dump_event(_evt(sequence=1, event_id="e-1"))
    second = dump_event(_evt(sequence=2, event_id="e-2"))
    path.write_bytes((first + "\n" + "\n" + "   \n" + second + "\n").encode("utf-8"))

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2"]
    assert reader.stats.lines_seen == 4, "the blank lines were seen..."
    assert reader.stats.accepted == 2, "...but only the real records were accepted"
    # A blank line is NOT an error of any kind.
    assert reader.stats.parse_errors == 0
    assert reader.stats.invalid == 0
    assert reader.stats.oversize == 0


def test_an_oversize_line_arriving_whole_in_one_chunk_is_dropped(tmp_path):
    """The other oversize path.

    ``test_oversize_record_is_rejected_and_counted`` feeds a giant record in 256-byte
    chunks, so the cap is enforced while BUFFERING. Here the chunk is larger than the
    record, so the line is already complete when it is handed to the line handler and
    the buffer is never involved at all — a different branch with the same duty.
    """
    cap = 4096
    path = tmp_path / "u.ndjson"
    huge = dump_event(_evt(sequence=1, event_id="e-huge", message_summary="A" * 5000))
    assert len(huge) > cap, "the fixture must exceed the cap, or this proves nothing"
    normal = dump_event(_evt(sequence=2, event_id="e-2"))

    path.write_bytes((huge + "\n" + normal + "\n").encode("utf-8"))

    reader = EventReader(path, max_record_bytes=cap, chunk_bytes=65_536)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-2"], "resynced at the next boundary"
    assert reader.stats.oversize == 1
    assert reader.buffer_high_water == 0, (
        "the record was never buffered — it arrived whole"
    )


def test_a_buffered_partial_that_overruns_the_cap_is_dropped_at_the_boundary(tmp_path):
    """A record split ACROSS reads whose two halves together exceed the cap.

    The first read buffers an under-cap fragment legitimately; only when the
    completing half arrives does the total breach the cap. The reader must drop that
    record at the boundary and carry on, rather than growing the buffer past its
    stated ceiling.
    """
    cap = 4096
    path = tmp_path / "u.ndjson"

    # First read: a 3000-byte fragment with no terminator — under the cap, so buffered.
    path.write_bytes(b"X" * 3000)
    reader = EventReader(path, max_record_bytes=cap, chunk_bytes=65_536)
    assert list(reader.read_new()) == []
    assert reader.buffer_bytes == 3000

    # Second read: 2000 more bytes THEN the terminator -> 5000 total, over the cap.
    good = dump_event(_evt(sequence=1, event_id="e-1"))
    with open(path, "ab") as fh:
        fh.write(b"Y" * 2000 + b"\n" + good.encode("utf-8") + b"\n")

    got = list(reader.read_new())

    assert reader.stats.oversize == 1
    assert [e.event_id for e in got] == ["e-1"], "the reader resynced and kept going"
    assert reader.buffer_bytes == 0
    assert reader.buffer_high_water <= cap, "the ceiling held throughout"


def test_valid_json_that_is_not_an_object_is_a_parse_error(tmp_path):
    """An array or a bare scalar parses as JSON but is not an envelope."""
    path = tmp_path / "u.ndjson"
    first = dump_event(_evt(sequence=1, event_id="e-1"))
    second = dump_event(_evt(sequence=2, event_id="e-2"))
    path.write_bytes(
        (
            first
            + "\n"
            + "[1, 2, 3]"
            + "\n"
            + '"just a string"'
            + "\n"
            + "42"
            + "\n"
            + second
            + "\n"
        ).encode("utf-8")
    )

    reader = EventReader(path)
    got = list(reader.read_new())

    assert [e.event_id for e in got] == ["e-1", "e-2"]
    assert reader.stats.parse_errors == 3
    assert reader.stats.invalid == 0, "these never reached envelope validation"


# --------------------------------------------------------------------------
# 18. The per-unit high-water map is bounded — and says so honestly
# --------------------------------------------------------------------------


def test_tracked_unit_map_evicts_least_recently_used_and_loses_their_history(tmp_path):
    """Memory is bounded by CONFIGURATION, and the cost of that bound is stated.

    Once a unit is evicted its high-water sequence is gone, so a later regression for
    that unit can no longer be detected. That is the documented trade-off, not a bug —
    and the both-states control below proves the detector is otherwise working, so the
    silence is caused by the eviction and nothing else.
    """
    path = tmp_path / "u.ndjson"
    stream = [
        _evt(logical_unit_id="u-A", sequence=5, event_id="e-a1"),
        _evt(logical_unit_id="u-B", sequence=5, event_id="e-b1"),
        _evt(logical_unit_id="u-C", sequence=5, event_id="e-c1"),
        # A regression for u-A, which by now has been evicted.
        _evt(logical_unit_id="u-A", sequence=1, event_id="e-a2"),
    ]
    _write_lines(path, stream)

    reader = EventReader(path, max_tracked_units=2)
    got = list(reader.read_new())

    assert len(got) == 4, "eviction must never drop EVENTS, only remembered history"
    assert reader.tracked_units == 2, "the map is held at its configured ceiling"
    assert reader.tracked_units <= reader.max_tracked_units
    # u-B was the least recently used when u-A re-entered, so it is the one now gone.
    assert reader.high_water_sequence("u-B", 1) is None
    assert reader.high_water_sequence("u-A", 1) == 1
    # The honest cost: u-A's regression went UNFLAGGED because its history was evicted.
    assert reader.stats.monotonic_violations == 0

    # Both-states control: with room to remember, the SAME stream flags the regression.
    roomy = EventReader(path, max_tracked_units=64)
    assert len(list(roomy.read_new())) == 4
    assert roomy.stats.monotonic_violations == 1
    assert roomy.recent_monotonic_violations == ("e-a2",)
    assert roomy.tracked_units == 3


# --------------------------------------------------------------------------
# 12. normalize() — the monitor-adapter mapping (REGRESSION: D-wu-46)
# --------------------------------------------------------------------------


def _wire(**over) -> dict:
    """One event as it actually travels: dumped to NDJSON and decoded back."""
    return json.loads(dump_event(_evt(**over)))


def test_normalize_is_exported_under_the_name_the_adapter_probes_for():
    """REGRESSION (D-wu-46): ``DatabricksSource._normalize`` looks up an attribute
    literally named ``normalize``. It was absent, so every valid envelope reached the
    fold under its native field names and was dropped for having no ``unit_id``."""
    assert callable(getattr(dbx_events, "normalize", None))
    assert "normalize" in dbx_events.__all__


def test_normalize_maps_the_envelope_onto_the_fold_vocabulary():
    got = dbx_events.normalize(
        _wire(
            logical_unit_id="u-1",
            databricks_run_id="run-9",
            observed_at_utc=101.5,
            lifecycle_state="RUNNING",
            progress_kind="heartbeat",
        )
    )
    assert got == {
        "kind": "heartbeat",
        "unit_id": "u-1",
        "run_id": "run-9",
        "ts": 101.5,
    }


@pytest.mark.parametrize(
    ("lifecycle", "progress", "kind"),
    [
        ("PENDING", "lifecycle", "queued"),
        ("ADMITTED", "lifecycle", "queued"),
        ("STARTING", "lifecycle", "start"),
        ("RETRYABLE", "lifecycle", "retry"),
        ("CANCELLED", "lifecycle", "cancel"),
        ("QUARANTINED", "lifecycle", "error"),
        ("SEVERED", "lifecycle", "error"),
        # executing states are NOT transitions — progress_kind decides
        ("RUNNING", "heartbeat", "heartbeat"),
        ("QUIET", "artifact", "artifact"),
        ("STALLED", "error", "error"),
        ("RUNNING", "terminal", "done"),
        ("RUNNING", "reasoning", "event"),
        ("RUNNING", "message", "event"),
        ("RUNNING", "lifecycle", "event"),
        # a tool event deliberately does NOT become tool_start (see below)
        ("RUNNING", "tool", "event"),
    ],
)
def test_normalize_kind_matrix(lifecycle, progress, kind):
    got = dbx_events.normalize(_wire(lifecycle_state=lifecycle, progress_kind=progress))
    assert got is not None and got["kind"] == kind


def test_normalize_never_synthesises_a_tool_call_it_cannot_close():
    """The envelope has no start/end discriminator for a tool call.

    Emitting ``tool_start`` from it would set ``tool_active`` with nothing able to
    clear it, pinning the unit ``TOOL_ACTIVE`` and making it permanently ineligible
    for ``STALLED`` — the monitor would go blind on the unit that needs attention.
    """
    got = dbx_events.normalize(
        _wire(lifecycle_state="RUNNING", progress_kind="tool", tool_name="Bash")
    )
    assert got is not None
    assert got["kind"] == "event"
    assert "tool_start" not in got.values()


def test_normalize_carries_the_kind_specific_payload():
    start = dbx_events.normalize(
        _wire(lifecycle_state="STARTING", program_run_id="prog-A")
    )
    assert start is not None and start["attempt_token"] == "prog-A"

    done = dbx_events.normalize(_wire(lifecycle_state="DONE"))
    assert done is not None and done["status"] == "SUCCESS"

    # progress_kind=terminal without a DONE lifecycle is terminal-but-unlabelled
    terminated = dbx_events.normalize(
        _wire(lifecycle_state="RUNNING", progress_kind="terminal")
    )
    assert terminated is not None and terminated["status"] == "TERMINATED"

    failed = dbx_events.normalize(
        _wire(lifecycle_state="FAILED", error_class="TimeoutError")
    )
    assert failed is not None and failed["message"] == "TimeoutError"

    # a failure with no error_class still names something actionable
    bare = dbx_events.normalize(_wire(lifecycle_state="FAILED", error_class=None))
    assert bare is not None and bare["message"] == "FAILED"

    grew = dbx_events.normalize(
        _wire(lifecycle_state="QUIET", progress_kind="artifact", artifact_bytes=4096)
    )
    assert grew is not None and grew["bytes"] == 4096

    empty = dbx_events.normalize(
        _wire(lifecycle_state="QUIET", progress_kind="artifact", artifact_bytes=None)
    )
    assert empty is not None and empty["bytes"] == 0


@pytest.mark.parametrize(
    "rec",
    [
        pytest.param(
            {"kind": "heartbeat", "ts": 1.0, "unit_id": "u1", "run_id": "r1"},
            id="legacy-adapter-record",
        ),
        pytest.param({"schema_version": 1}, id="no-logical-unit-id"),
        pytest.param({"logical_unit_id": "u-1"}, id="no-schema-version"),
        pytest.param({"schema_version": 1, "logical_unit_id": ""}, id="blank-unit-id"),
        pytest.param(["not", "a", "dict"], id="not-a-dict"),
    ],
)
def test_normalize_declines_anything_that_is_not_a_v1_envelope(rec):
    """Declining with ``None`` is load-bearing: ``DatabricksSource._normalize`` falls
    back to the RAW record, so the adapter's own schema keeps working unchanged."""
    assert dbx_events.normalize(rec) is None


def test_normalize_tolerates_a_non_numeric_timestamp():
    rec = _wire()
    rec["observed_at_utc"] = "not-a-number"
    got = dbx_events.normalize(rec)
    assert got is not None and got["ts"] == 0.0

    rec["observed_at_utc"] = True  # a bool is not a timestamp
    assert dbx_events.normalize(rec)["ts"] == 0.0


def test_valid_envelope_now_reaches_the_databricks_adapter_as_a_unit():
    """REGRESSION (D-wu-46), end to end through the real adapter.

    Measured BEFORE the fix, with the exact same input: ``events_seen=1``,
    ``unit_count=0``, ``state=idle``, ``reachable=True``, ``stale=False``,
    ``error=None`` — one valid heartbeat acknowledged, its unit silently discarded,
    and the row painted healthy. The adapter is constructed on its AUTO sibling seam
    (no ``events_mod`` kwarg), which is the production path.
    """
    from monitorcore.databricks_source import DatabricksSource
    from monitorcore.databricks_source import Liveness as _Liveness

    now = 1784500200.0
    stream = [
        _wire(
            logical_unit_id="u-1",
            sequence=1,
            event_id="e-1",
            lifecycle_state="STARTING",
            progress_kind="lifecycle",
            observed_at_utc=now - 60,
        ),
        _wire(
            logical_unit_id="u-1",
            sequence=2,
            event_id="e-2",
            lifecycle_state="RUNNING",
            progress_kind="heartbeat",
            observed_at_utc=now - 5,
        ),
    ]
    src = DatabricksSource(reader=lambda: iter(stream), clock=lambda: now)
    snap = src.poll()

    assert snap.payload.events_seen == 2
    (unit,) = snap.payload.units  # was () before the fix
    assert unit.unit_id == "u-1"
    assert unit.run_id == "dbx-778812"
    assert unit.heartbeat_ts == now - 5
    assert unit.liveness is _Liveness.THINKING
    assert unit.busy is True
    assert snap.age_s == 5.0  # was None — nothing had been attributed at all
