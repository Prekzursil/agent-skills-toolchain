#!/usr/bin/env python3
"""Regression tests for the bounded OATS selection-event emitter.

Run: python test_emitter.py
"""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True


HERE = Path(__file__).resolve().parent
HOOK = HERE / "emitter.py"
EVENT_KEYS = {
    "seq",
    "schema",
    "event_id",
    "ts",
    "kind",
    "query",
    "query_hash",
    "query_source",
    "query_evidence",
    "chosen_tool",
    "success",
    "session_hash",
    "tool_use_id",
}


def user_event(text: str, uuid: str = "user-1") -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "message": {"role": "user", "content": text},
    }


def tool_use_event(tool_use_id: str, name: str = "Read") -> dict:
    return {
        "type": "assistant",
        "uuid": "assistant-1",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": {"file_path": "C:/not-recorded.txt"},
                }
            ],
        },
    }


def tool_result_event(tool_use_id: str) -> dict:
    return {
        "type": "user",
        "uuid": "tool-result-1",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": "this is tool output, not a user query",
                }
            ],
        },
    }


def internal_notification_event(text: str) -> dict:
    return {
        "type": "user",
        "uuid": "internal-notification",
        "promptSource": "system",
        "origin": {"kind": "task-notification"},
        "message": {"role": "user", "content": text},
    }


class EmitterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="selection-events-test-")
        self.root = Path(self.temp.name)
        self.ledger_root = self.root / "ledger"
        self.state_root = self.root / "state"
        self.cwd = self.root / "project"
        self.cwd.mkdir()
        self.env = os.environ.copy()
        self.env["EVENT_LEDGER_ROOT"] = str(self.ledger_root)
        self.env["SELECTION_EVENT_STATE_ROOT"] = str(self.state_root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_hook(self, payload: dict | None = None, *, raw: str | None = None,
                 env: dict | None = None) -> subprocess.CompletedProcess[str]:
        body = raw if raw is not None else json.dumps(payload or {})
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=body,
            text=True,
            capture_output=True,
            timeout=10,
            env=env or self.env,
            check=False,
        )

    def transcript(self, *events: dict) -> Path:
        path = self.root / f"transcript-{len(list(self.root.glob('transcript-*')))}.jsonl"
        path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        return path

    def events(self) -> list[dict]:
        files = list(self.ledger_root.glob("*/events.jsonl"))
        if not files:
            return []
        self.assertEqual(1, len(files), files)
        return [
            json.loads(line)
            for line in files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def post_payload(self, transcript: Path | str, tool_use_id: str,
                     *, event: str = "PostToolUse", session: str = "session-A",
                     tool: str = "mcp__exa__web_search_exa") -> dict:
        payload = {
            "session_id": session,
            "transcript_path": str(transcript),
            "cwd": str(self.cwd),
            "hook_event_name": event,
            "tool_name": tool,
            "tool_input": {"query": "must not be persisted"},
            "tool_use_id": tool_use_id,
        }
        if event == "PostToolUse":
            payload["tool_response"] = {"success": True, "private": "not persisted"}
        else:
            payload["error"] = "private failure details are not persisted"
        return payload

    def test_transcript_correlates_exact_tool_use_to_real_user_query(self) -> None:
        transcript = self.transcript(
            user_event("Find the primary documentation for this API.", "human-abc"),
            tool_use_event("toolu-1", "mcp__exa__web_search_exa"),
        )
        result = self.run_hook(self.post_payload(transcript, "toolu-1"))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        events = self.events()
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual(EVENT_KEYS, set(event))
        self.assertEqual("selection.v1", event["schema"])
        self.assertEqual("selection", event["kind"])
        self.assertEqual("Find the primary documentation for this API.", event["query"])
        self.assertEqual("transcript", event["query_source"])
        self.assertEqual("mcp__exa__web_search_exa", event["chosen_tool"])
        self.assertIs(event["success"], True)
        self.assertEqual(1, event["seq"])
        event_file = next(self.ledger_root.glob("*/events.jsonl"))
        state = json.loads((event_file.parent / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(1, state["seq"])
        serialized = json.dumps(event)
        self.assertNotIn("must not be persisted", serialized)
        self.assertNotIn("private", serialized)
        self.assertNotIn(str(transcript), serialized)
        self.assertNotIn(str(self.cwd), serialized)

    def test_tool_result_user_event_is_not_mistaken_for_query(self) -> None:
        transcript = self.transcript(
            user_event("Inspect the repository.", "human-1"),
            tool_use_event("toolu-first", "Read"),
            tool_result_event("toolu-first"),
            tool_use_event("toolu-second", "Bash"),
        )
        result = self.run_hook(
            self.post_payload(transcript, "toolu-second", tool="Bash")
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("Inspect the repository.", self.events()[0]["query"])

    def test_tool_use_id_must_match_transcript_evidence(self) -> None:
        prompt = {
            "session_id": "session-A",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Cached text must not override contradictory transcript evidence.",
        }
        self.assertEqual(0, self.run_hook(prompt).returncode)
        transcript = self.transcript(
            user_event("This is real but belongs to another tool."),
            tool_use_event("toolu-other"),
        )
        result = self.run_hook(self.post_payload(transcript, "toolu-missing"))
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.events())

    def test_internal_task_notification_is_not_a_query_or_fallback_boundary(self) -> None:
        prompt = {
            "session_id": "session-A",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Earlier genuine prompt must not leak across an internal boundary.",
        }
        self.assertEqual(0, self.run_hook(prompt).returncode)
        transcript = self.transcript(
            user_event("Earlier genuine prompt must not leak across an internal boundary."),
            internal_notification_event(
                "<task-notification>Background agent completed.</task-notification>"
            ),
            tool_use_event("toolu-internal", "Read"),
        )
        result = self.run_hook(
            self.post_payload(transcript, "toolu-internal", tool="Read")
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.events())

    def test_user_prompt_submit_rejects_internal_task_notification(self) -> None:
        genuine = {
            "session_id": "session-A",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Keep this genuine user request as fallback evidence.",
        }
        self.assertEqual(0, self.run_hook(genuine).returncode)
        cache = next((self.state_root / "prompts").glob("*.json"))
        before = cache.read_text(encoding="utf-8")

        notification = {
            "session_id": "session-A",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": (
                "<task-notification>\n"
                "<task-id>background-1</task-id>\n"
                "<status>completed</status>\n"
                "<summary>Background command completed</summary>\n"
                "</task-notification>"
            ),
        }
        result = self.run_hook(notification)
        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual(before, cache.read_text(encoding="utf-8"))

    def test_user_prompt_submit_is_bounded_fallback_evidence(self) -> None:
        prompt = {
            "session_id": "fallback-session",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Use the local verifier for this task.",
        }
        first = self.run_hook(prompt)
        self.assertEqual(0, first.returncode)
        self.assertEqual("", first.stdout)
        self.assertEqual([], self.events())

        post = self.post_payload(
            self.root / "missing-transcript.jsonl",
            "toolu-fallback",
            session="fallback-session",
            tool="verification-tool",
        )
        second = self.run_hook(post)
        self.assertEqual(0, second.returncode)
        event = self.events()[0]
        self.assertEqual("Use the local verifier for this task.", event["query"])
        self.assertEqual("user_prompt_submit", event["query_source"])

    def test_tampered_prompt_cache_cannot_fabricate_query(self) -> None:
        prompt = {
            "session_id": "tamper-session",
            "cwd": str(self.cwd),
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Use the real cached query.",
        }
        self.assertEqual(0, self.run_hook(prompt).returncode)
        cache_path = next((self.state_root / "prompts").glob("*.json"))
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache["query"] = "Fabricated telemetry"
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        post = self.post_payload(
            self.root / "missing-transcript.jsonl",
            "toolu-tampered-cache",
            session="tamper-session",
            tool="verification-tool",
        )
        self.assertEqual(0, self.run_hook(post).returncode)
        self.assertEqual([], self.events())

    def test_no_proven_query_or_missing_tool_use_id_emits_nothing(self) -> None:
        no_query = self.post_payload(self.root / "missing.jsonl", "toolu-no-query")
        self.assertEqual(0, self.run_hook(no_query).returncode)
        missing_id = self.post_payload(self.root / "missing.jsonl", "")
        self.assertEqual(0, self.run_hook(missing_id).returncode)
        self.assertEqual([], self.events())

    def test_failure_event_is_negative_selection(self) -> None:
        transcript = self.transcript(
            user_event("Run the test suite."),
            tool_use_event("toolu-fail", "Bash"),
        )
        payload = self.post_payload(
            transcript,
            "toolu-fail",
            event="PostToolUseFailure",
            tool="Bash",
        )
        result = self.run_hook(payload)
        self.assertEqual(0, result.returncode)
        event = self.events()[0]
        self.assertIs(event["success"], False)
        self.assertNotIn("error", event)

    def test_obvious_secrets_are_redacted_and_query_is_bounded(self) -> None:
        secret = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        database_url = "postgres://alice:DatabasePassword@db.example/private"
        query = (
            f"password=SuperSecret123 token: {secret} DATABASE_URL={database_url} "
            + ("x" * 4000)
        )
        transcript = self.transcript(
            user_event(query),
            tool_use_event("toolu-secret", "Read"),
        )
        result = self.run_hook(
            self.post_payload(transcript, "toolu-secret", tool="Read")
        )
        self.assertEqual(0, result.returncode)
        stored = self.events()[0]["query"]
        self.assertNotIn("SuperSecret123", stored)
        self.assertNotIn(secret, stored)
        self.assertNotIn("DatabasePassword", stored)
        self.assertIn("[REDACTED]", stored)
        self.assertLessEqual(len(stored), 2000)

    def test_duplicate_dispatch_of_same_tool_use_is_idempotent(self) -> None:
        transcript = self.transcript(
            user_event("Read one file."),
            tool_use_event("toolu-duplicate", "Read"),
        )
        payload = self.post_payload(transcript, "toolu-duplicate", tool="Read")
        self.assertEqual(0, self.run_hook(payload).returncode)
        self.assertEqual(0, self.run_hook(payload).returncode)
        self.assertEqual(1, len(self.events()))

    def test_claim_transition_cannot_reopen_after_prior_owner_finishes(self) -> None:
        emitter = runpy.run_path(str(HOOK), run_name="selection_emitter_claim_test")
        emitter["_claim_event"].__globals__["STATE_ROOT"] = self.state_root
        claims = self.state_root / "claims"
        claims.mkdir(parents=True)
        (claims / ".gc-stamp").touch()
        event_id = "a" * 32
        done = claims / f"{event_id}.done"
        pending = claims / f"{event_id}.pending"
        real_open = os.open

        def transition_open(path, flags, mode=0o777):
            if Path(path) == pending:
                done.write_text("done\n", encoding="utf-8")
            return real_open(path, flags, mode)

        with mock.patch.object(emitter["os"], "open", side_effect=transition_open):
            claimed = emitter["_claim_event"](event_id)
        self.assertIsNone(claimed)
        self.assertTrue(done.is_file())
        self.assertFalse(pending.exists())

    def test_parallel_duplicate_dispatch_is_single_append_with_valid_state(self) -> None:
        transcript = self.transcript(
            user_event("Read one file in parallel-safe fashion."),
            tool_use_event("toolu-parallel", "Read"),
        )
        payload = self.post_payload(transcript, "toolu-parallel", tool="Read")
        body = json.dumps(payload)
        processes = [
            subprocess.Popen(
                [sys.executable, str(HOOK)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                env=self.env,
            )
            for _ in range(12)
        ]
        for process in processes:
            assert process.stdin is not None
            process.stdin.write(body)
            process.stdin.close()
        for process in processes:
            self.assertEqual(0, process.wait(timeout=30))
        events = self.events()
        self.assertEqual(1, len(events))
        self.assertEqual(1, events[0]["seq"])
        event_file = next(self.ledger_root.glob("*/events.jsonl"))
        state = json.loads((event_file.parent / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(1, state["seq"])

    def test_parallel_distinct_tools_preserve_every_event_and_monotonic_seq(self) -> None:
        count = 32
        transcript = self.transcript(
            user_event("Run a parallel batch of independent reads."),
            {
                "type": "assistant",
                "uuid": "assistant-parallel-batch",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"toolu-batch-{index}",
                            "name": "Read",
                            "input": {"file_path": f"C:/private-{index}.txt"},
                        }
                        for index in range(count)
                    ],
                },
            },
        )
        processes = [
            subprocess.Popen(
                [sys.executable, str(HOOK)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                env=self.env,
            )
            for _ in range(count)
        ]
        for index, process in enumerate(processes):
            payload = self.post_payload(
                transcript, f"toolu-batch-{index}", tool="Read"
            )
            assert process.stdin is not None
            process.stdin.write(json.dumps(payload))
            process.stdin.close()
        for process in processes:
            self.assertEqual(0, process.wait(timeout=30))
        events = self.events()
        self.assertEqual(count, len(events))
        self.assertEqual(list(range(1, count + 1)), sorted(e["seq"] for e in events))
        event_file = next(self.ledger_root.glob("*/events.jsonl"))
        state = json.loads((event_file.parent / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(count, state["seq"])

    def test_existing_oats_consumer_sees_selection_record(self) -> None:
        transcript = self.transcript(
            user_event("Choose the appropriate verifier."),
            tool_use_event("toolu-oats", "verification-tool"),
        )
        payload = self.post_payload(
            transcript, "toolu-oats", tool="verification-tool"
        )
        self.assertEqual(0, self.run_hook(payload).returncode)
        oats = HERE.parent / "event-ledger" / "oats.py"
        status = subprocess.run(
            [sys.executable, str(oats), "--status"],
            text=True,
            capture_output=True,
            timeout=10,
            env=self.env,
            check=False,
        )
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertIn("1 selection events", status.stdout)

    def test_malformed_unknown_and_storage_errors_are_fail_open(self) -> None:
        malformed = self.run_hook(raw="{not-json")
        self.assertEqual(0, malformed.returncode)
        self.assertEqual("", malformed.stdout)
        unknown = self.run_hook({"hook_event_name": "PreToolUse"})
        self.assertEqual(0, unknown.returncode)
        oversized = self.run_hook(raw="x" * (2 * 1024 * 1024 + 1))
        self.assertEqual(0, oversized.returncode)
        self.assertEqual("", oversized.stdout)

        blocked = self.root / "not-a-directory"
        blocked.write_text("blocked", encoding="utf-8")
        state_env = self.env.copy()
        state_env["SELECTION_EVENT_STATE_ROOT"] = str(blocked)
        prompt_error = self.run_hook(
            {
                "session_id": "state-error",
                "cwd": str(self.cwd),
                "hook_event_name": "UserPromptSubmit",
                "prompt": "This write cannot complete.",
            },
            env=state_env,
        )
        self.assertEqual(0, prompt_error.returncode)
        self.assertEqual("", prompt_error.stdout)

        env = self.env.copy()
        env["EVENT_LEDGER_ROOT"] = str(blocked)
        transcript = self.transcript(
            user_event("A proven query."),
            tool_use_event("toolu-storage-error"),
        )
        storage_error = self.run_hook(
            self.post_payload(transcript, "toolu-storage-error"), env=env
        )
        self.assertEqual(0, storage_error.returncode)
        self.assertEqual("", storage_error.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
