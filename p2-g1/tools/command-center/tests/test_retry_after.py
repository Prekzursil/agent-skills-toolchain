#!/usr/bin/env python3
"""Retry-After both wire formats, past/malformed, property edges, window."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retry_after import (  # noqa: E402
    DEFAULT_EPOCH,
    FakeClock,
    format_http_date,
    in_window,
    parse_retry_after,
    wait_seconds,
)

FALLBACK = 0.25
EPOCH = DEFAULT_EPOCH


class DeltaSecondsTests(unittest.TestCase):
    def test_plain_integer(self) -> None:
        p = parse_retry_after("5", now=EPOCH)
        self.assertEqual(p.kind, "delta-seconds")
        self.assertEqual(p.wait_seconds, 5.0)
        self.assertEqual(wait_seconds("5", now=EPOCH, fallback=FALLBACK), 5.0)

    def test_zero(self) -> None:
        p = parse_retry_after("0", now=EPOCH)
        self.assertEqual(p.kind, "delta-seconds")
        self.assertEqual(p.wait_seconds, 0.0)

    def test_huge(self) -> None:
        p = parse_retry_after(str(10**9), now=EPOCH)
        self.assertEqual(p.kind, "delta-seconds")
        self.assertEqual(p.wait_seconds, float(10**9))


class HttpDateTests(unittest.TestCase):
    def test_imf_fixdate_future(self) -> None:
        header = format_http_date(EPOCH + timedelta(seconds=5))
        p = parse_retry_after(header, now=EPOCH)
        self.assertEqual(p.kind, "http-date")
        self.assertEqual(p.wait_seconds, 5.0)
        self.assertEqual(header, "Mon, 24 Aug 2026 18:00:05 GMT")

    def test_past_is_immediate(self) -> None:
        header = format_http_date(EPOCH - timedelta(hours=2))
        p = parse_retry_after(header, now=EPOCH)
        self.assertEqual(p.kind, "http-date")
        self.assertEqual(p.wait_seconds, 0.0)
        self.assertEqual(
            wait_seconds(header, now=EPOCH, fallback=FALLBACK),
            0.0,
        )
        self.assertEqual(header, "Mon, 24 Aug 2026 16:00:00 GMT")

    def test_canonical_past_imf(self) -> None:
        header = "Wed, 21 Oct 2015 07:28:00 GMT"
        p = parse_retry_after(header, now=EPOCH)
        self.assertEqual(p.kind, "http-date")
        self.assertEqual(p.wait_seconds, 0.0)

    def test_rfc850(self) -> None:
        header = "Sunday, 06-Nov-94 08:49:37 GMT"
        p = parse_retry_after(header, now=EPOCH)
        self.assertEqual(p.kind, "http-date")
        self.assertEqual(p.wait_seconds, 0.0)


class MalformedTests(unittest.TestCase):
    def test_fallback_and_no_crash(self) -> None:
        bad = [
            None,
            "",
            "   ",
            "-1",
            "+12",
            "1.5",
            "1e3",
            "retry-later",
            "<<<bad>>>",
            "NaN",
            "inf",
            "1 2",
            "0x10",
            "Retry-After: 5",
            "definitely-not-a-retry-after",
        ]
        for header in bad:
            with self.subTest(header=header):
                p = parse_retry_after(header, now=EPOCH)
                self.assertEqual(p.kind, "malformed")
                self.assertEqual(
                    wait_seconds(header, now=EPOCH, fallback=FALLBACK),
                    FALLBACK,
                )


class WindowAndClockTests(unittest.TestCase):
    def test_in_window_exact(self) -> None:
        self.assertTrue(in_window(5.0, 5.0, slack_abs=1e-9))
        self.assertFalse(in_window(1.0, 5.0, slack_abs=1e-9))
        self.assertTrue(in_window(1.05, 1.0, slack_abs=0.20, slack_rel=0.25))

    def test_fake_clock_honors_wait(self) -> None:
        clock = FakeClock(epoch=EPOCH)
        wait = wait_seconds("5", now=clock.datetime_now(), fallback=FALLBACK)
        t0 = clock.now()
        clock.sleep(wait)
        self.assertEqual(clock.now() - t0, 5.0)

    def test_ignore_backoff_misses_window(self) -> None:
        expected = wait_seconds("5", now=EPOCH, fallback=FALLBACK)
        ignore = 1.0
        self.assertFalse(in_window(ignore, expected, slack_abs=1e-9))
        self.assertTrue(in_window(expected, expected, slack_abs=1e-9))


class SeedParseKindTests(unittest.TestCase):
    def test_probe2_seed_kinds(self) -> None:
        headers = [
            "-1",
            "0",
            "1000000000",
            "",
            "retry-later",
            "1.5",
            "+12",
            "1e3",
            "3",
            format_http_date(EPOCH + timedelta(seconds=9)),
            "Wed, 21 Oct 2015 07:28:00 GMT",
            "Sunday, 06-Nov-94 08:49:37 GMT",
        ]
        kinds = [parse_retry_after(h, now=EPOCH).kind for h in headers]
        self.assertEqual(
            kinds,
            [
                "malformed",
                "delta-seconds",
                "delta-seconds",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "malformed",
                "delta-seconds",
                "http-date",
                "http-date",
                "http-date",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
