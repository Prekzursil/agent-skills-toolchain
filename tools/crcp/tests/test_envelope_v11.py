"""Schema validation contracts for additive CRCP envelope v1.1."""

from __future__ import annotations

import unittest
import uuid

from envelope_v11 import require_valid, validate_envelope


def valid_envelope() -> dict[str, object]:
    return {
        "schema": "crcp.envelope.v1.1",
        "id": str(uuid.uuid4()),
        "created_at": "2026-07-20T00:00:00+00:00",
        "event_key": "conv-1:100:" + "a" * 64,
        "trace_id": str(uuid.uuid4()),
        "kind": "task.request",
        "from_rail": "chatgpt",
        "to_rail": "codex",
        "intent": "execute",
        "payload_ref": "sha256:" + "b" * 64,
        "capabilities_required": ["python"],
        "meta": {"source": "fixture"},
    }


class EnvelopeV11ContractTests(unittest.TestCase):
    def test_valid_content_addressed_envelope(self) -> None:
        envelope = valid_envelope()
        self.assertEqual(validate_envelope(envelope), [])
        require_valid(envelope)

    def test_identity_fields_are_required(self) -> None:
        envelope = valid_envelope()
        del envelope["event_key"]
        del envelope["trace_id"]
        errors = validate_envelope(envelope)
        self.assertIn("missing required field: event_key", errors)
        self.assertIn("missing required field: trace_id", errors)

    def test_local_payload_path_is_rejected(self) -> None:
        envelope = valid_envelope()
        envelope["payload_ref"] = "/tmp/private/conversation.json"
        self.assertTrue(any("content address" in error for error in validate_envelope(envelope)))

    def test_inline_payload_cannot_accompany_reference(self) -> None:
        envelope = valid_envelope()
        envelope["payload"] = {"text": "duplicate body"}
        self.assertIn("payload and payload_ref are mutually exclusive", validate_envelope(envelope))

    def test_invalid_kind_and_unzoned_timestamp_are_rejected(self) -> None:
        envelope = valid_envelope()
        envelope["kind"] = "mystery"
        envelope["created_at"] = "2026-07-20T00:00:00"
        errors = validate_envelope(envelope)
        self.assertTrue(any("kind must be" in error for error in errors))
        self.assertIn("created_at must include a timezone", errors)

    def test_require_valid_raises_one_actionable_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "envelope must be an object"):
            require_valid([])


if __name__ == "__main__":
    unittest.main()
