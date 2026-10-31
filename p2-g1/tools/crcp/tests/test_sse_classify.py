"""Complete, truncated, malformed, and explicit-error SSE fixtures."""

from __future__ import annotations

import unittest

from sse_contract import COMPLETE, ERROR, UNCERTAIN_ACCEPTED, classify_sse, parse_sse


COMPLETE_FIXTURE = """data: {"message":{"status":"in_progress"}}

data: {"message":{"status":"finished_successfully","end_turn":true}}

data: [DONE]

"""
TRUNCATED_FIXTURE = """data: {"message":{"status":"in_progress"}}

data: {"delta":"partial output"}

"""
ERROR_FIXTURE = """event: error
data: {"error":{"message":"upstream failed"}}

"""


class SseClassificationContractTests(unittest.TestCase):
    def test_complete_fixture_requires_terminal_evidence(self) -> None:
        self.assertEqual(classify_sse(200, COMPLETE_FIXTURE), COMPLETE)

    def test_truncated_http_200_is_uncertain(self) -> None:
        self.assertEqual(classify_sse(200, TRUNCATED_FIXTURE), UNCERTAIN_ACCEPTED)

    def test_explicit_error_fixture_is_error(self) -> None:
        self.assertEqual(classify_sse(200, ERROR_FIXTURE), ERROR)

    def test_http_error_is_error_even_with_done_marker(self) -> None:
        self.assertEqual(classify_sse(503, "data: [DONE]\n\n"), ERROR)

    def test_malformed_data_is_error(self) -> None:
        self.assertEqual(classify_sse(200, "data: {not-json}\n\n"), ERROR)

    def test_done_marker_is_sufficient_terminal_evidence(self) -> None:
        self.assertEqual(classify_sse(200, "data: [DONE]\r\n\r\n"), COMPLETE)

    def test_parser_joins_multiline_data(self) -> None:
        records = parse_sse('data: {"status":\ndata: "complete"}\n\n')
        self.assertEqual(records[0]["data"], {"status": "complete"})


if __name__ == "__main__":
    unittest.main()
