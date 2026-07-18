"""Cron-refresh PURE LOGIC (WU-K).

Snapshot-diff, FEP-sentinel skip-check, and sanitize/quarantine of untrusted
external free-text. The CronCreate REGISTRATION (durable schedule) and the live
pipeline invocation are DEFERRED to live-deploy — only the pure logic lives here.
"""

__all__ = ["refresh"]
