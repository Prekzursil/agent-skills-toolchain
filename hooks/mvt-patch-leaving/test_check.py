#!/usr/bin/env python3
"""Deterministic tests for the MVT patch-leaving hook (stdlib unittest)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


THIS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mvt_patch_leaving_check", THIS / "check.py")
assert SPEC and SPEC.loader
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def _human(text: str, uuid: str = "turn-1") -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": text}],
        },
    }


def _assistant(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        },
    }


class PatchLeavingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mvt-patch-test-")
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.work = self.root / "work"
        self.work.mkdir()
        self.old_state = hook.STATE_DIR
        hook.STATE_DIR = self.state

    def tearDown(self) -> None:
        hook.STATE_DIR = self.old_state
        self.tmp.cleanup()

    def transcript(
        self,
        request: str = "Please update app.py to return the new behavior.",
        final: str = "Implemented the requested change in app.py.",
        uuid: str = "turn-1",
    ) -> Path:
        path = self.root / f"{uuid}.jsonl"
        events = [_human(request, uuid), _assistant(final)]
        path.write_text(
            "\n".join(json.dumps(event) for event in events), encoding="utf-8"
        )
        return path

    def run_hook(self, mode: str, payload: dict | str) -> tuple[int, str]:
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        out = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(raw)), redirect_stdout(out):
            code = hook.main([mode])
        return code, out.getvalue().strip()

    def base(self, transcript: Path, sid: str = "session-1") -> dict:
        return {
            "session_id": sid,
            "transcript_path": str(transcript),
            "cwd": str(self.work),
        }

    def test_failed_patch_is_reported_only_at_stop(self) -> None:
        transcript = self.transcript(final="The patch still needs attention.")
        post = {
            **self.base(transcript),
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": {
                "is_error": True,
                "content": "error: patch failed: app.py:1",
            },
        }
        code, output = self.run_hook("posttool", post)
        self.assertEqual(0, code)
        self.assertEqual("", output)

        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        message = json.loads(output)
        self.assertEqual("Stop", message["hookSpecificOutput"]["hookEventName"])
        self.assertIn("unapplied patch", message["hookSpecificOutput"]["additionalContext"])
        self.assertIn("app.py", message["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("decision", message)

    def test_plain_text_patch_error_is_detected_without_is_error_flag(self) -> None:
        transcript = self.transcript(final="The patch still needs attention.")
        post = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": "Error: patch does not apply",
        }
        self.run_hook("posttool", post)
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("unapplied patch", output)

    def test_failed_edit_needs_intent_and_completion_claim(self) -> None:
        target = self.work / "app.py"
        target.write_text("return 'old'\n", encoding="utf-8")
        transcript = self.transcript()
        failed_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "return 'missing'",
                "new_string": "return 'new'",
            },
            "tool_response": {"is_error": True, "content": "old_string not found"},
        }
        self.assertEqual((0, ""), self.run_hook("posttool", failed_edit))
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("intended change did not land", output)
        self.assertIn("app.py", output)

        # Same failed edit, but an honest non-completion final answer stays silent.
        transcript2 = self.transcript(
            final="I could not update app.py because the expected text was absent.",
            uuid="turn-2",
        )
        failed_edit2 = {**failed_edit, **self.base(transcript2, "session-2")}
        self.run_hook("posttool", failed_edit2)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript2, "session-2")))

    def test_successful_non_git_write_is_landed(self) -> None:
        target = self.work / "notes.txt"
        content = "landed outside git\n"
        target.write_text(content, encoding="utf-8")
        transcript = self.transcript(
            request="Please write notes.txt with the result.",
            final="Wrote notes.txt with the requested result.",
        )
        post = {
            **self.base(transcript),
            "tool_name": "Write",
            "tool_input": {"file_path": str(target), "content": content},
            "tool_result": {"success": True},
        }
        self.assertEqual((0, ""), self.run_hook("posttool", post))
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_explicit_commit_intent_without_commit_is_flagged(self) -> None:
        target = self.work / "app.py"
        target.write_text("new\n", encoding="utf-8")
        transcript = self.transcript(
            request="Update app.py and commit the changes.",
            final="Updated app.py with the requested behavior.",
        )
        landed_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old",
                "new_string": "new",
            },
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", landed_edit)
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("uncommitted intended change", output)
        self.assertIn("explicit commit request", output)
        self.assertIn(
            "no commit is inferred unless the user explicitly requested it", output
        )

    def test_successful_later_commit_resolves_commit_intent(self) -> None:
        target = self.work / "app.py"
        target.write_text("new\n", encoding="utf-8")
        transcript = self.transcript(
            request="Update app.py and commit the changes.",
            final="Updated and committed app.py.",
        )
        landed_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old",
                "new_string": "new",
            },
            "tool_result": {"success": True},
        }
        committed = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -am 'implement behavior'"},
            "tool_result": {"exit_code": 0, "content": "[main abc123] implement"},
        }
        self.run_hook("posttool", landed_edit)
        self.run_hook("posttool", committed)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_failed_or_dry_run_commit_does_not_satisfy_commit_intent(self) -> None:
        for suffix, command, result in (
            (
                "failed",
                "git commit -am 'implement behavior'",
                {"exit_code": 1, "content": "error: commit failed"},
            ),
            (
                "dry-run",
                "git commit --dry-run",
                {"exit_code": 0, "content": "Changes to be committed"},
            ),
            (
                "noop",
                "git commit -am 'implement behavior'",
                {"exit_code": 0, "content": "nothing to commit, working tree clean"},
            ),
        ):
            with self.subTest(suffix=suffix):
                sid = f"commit-{suffix}"
                target = self.work / f"{suffix}.py"
                target.write_text("new\n", encoding="utf-8")
                transcript = self.transcript(
                    request=f"Update {suffix}.py and commit the changes.",
                    final=f"Updated {suffix}.py.",
                    uuid=f"turn-{suffix}",
                )
                landed_edit = {
                    **self.base(transcript, sid),
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": str(target),
                        "old_string": "old",
                        "new_string": "new",
                    },
                    "tool_result": {"success": True},
                }
                commit_attempt = {
                    **self.base(transcript, sid),
                    "tool_name": "Bash",
                    "tool_input": {"command": command},
                    "tool_result": result,
                }
                self.run_hook("posttool", landed_edit)
                self.run_hook("posttool", commit_attempt)
                code, output = self.run_hook("stop", self.base(transcript, sid))
                self.assertEqual(0, code)
                self.assertIn("uncommitted intended change", output)

    def test_edit_after_successful_commit_is_still_uncommitted(self) -> None:
        transcript = self.transcript(
            request="Update app.py and commit the changes.",
            final="Updated and committed the work.",
        )
        first = self.work / "first.py"
        later = self.work / "later.py"
        first.write_text("new\n", encoding="utf-8")
        later.write_text("new\n", encoding="utf-8")

        def edit_payload(path: Path) -> dict:
            return {
                **self.base(transcript),
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(path),
                    "old_string": "old",
                    "new_string": "new",
                },
                "tool_result": {"success": True},
            }

        committed = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git -C . commit -am 'first change'"},
            "tool_result": {"exit_code": 0, "content": "[main abc123] first change"},
        }
        self.run_hook("posttool", edit_payload(first))
        self.run_hook("posttool", committed)
        self.run_hook("posttool", edit_payload(later))
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("uncommitted intended change", output)
        self.assertIn("later.py", output)

    def test_no_or_negated_commit_request_stays_silent(self) -> None:
        for suffix, request in (
            ("none", "Update app.py with the new behavior."),
            ("negated", "Update app.py but do not commit the changes."),
            ("message", "Update app.py and suggest a commit message."),
            ("lead-message", "Commit message for the app.py update."),
        ):
            with self.subTest(suffix=suffix):
                sid = f"no-commit-{suffix}"
                target = self.work / f"{suffix}.py"
                target.write_text("new\n", encoding="utf-8")
                transcript = self.transcript(
                    request=request,
                    final="Updated app.py.",
                    uuid=f"turn-no-commit-{suffix}",
                )
                landed_edit = {
                    **self.base(transcript, sid),
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": str(target),
                        "old_string": "old",
                        "new_string": "new",
                    },
                    "tool_result": {"success": True},
                }
                self.run_hook("posttool", landed_edit)
                self.assertEqual(
                    (0, ""), self.run_hook("stop", self.base(transcript, sid))
                )

    def test_later_success_same_target_resolves_failed_edit(self) -> None:
        target = self.work / "app.py"
        target.write_text("old\n", encoding="utf-8")
        transcript = self.transcript()
        base_post = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old",
                "new_string": "new",
            },
        }
        self.run_hook(
            "posttool",
            {**base_post, "tool_result": {"is_error": True, "content": "failed"}},
        )
        target.write_text("new\n", encoding="utf-8")
        self.run_hook(
            "posttool",
            {**base_post, "tool_result": {"success": True, "content": "updated"}},
        )
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_later_edit_resolves_failed_inline_patch_for_same_target(self) -> None:
        target = self.work / "app.py"
        target.write_text("old\n", encoding="utf-8")
        transcript = self.transcript()
        failed_patch = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {
                "command": "apply_patch <<'PATCH'\n*** Begin Patch\n*** Update File: app.py\n@@\n-old\n+new\n*** End Patch\nPATCH"
            },
            "tool_result": {"is_error": True, "content": "Invalid Context"},
        }
        self.run_hook("posttool", failed_patch)
        target.write_text("new\n", encoding="utf-8")
        landed_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old",
                "new_string": "new",
            },
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", landed_edit)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_referenced_patch_target_is_not_resolved_by_unrelated_edit(self) -> None:
        patch_file = self.work / "change.patch"
        patch_file.write_text(
            "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n",
            encoding="utf-8",
        )
        other = self.work / "other.py"
        other.write_text("new\n", encoding="utf-8")
        transcript = self.transcript()
        failed_patch = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": {"is_error": True, "content": "patch failed"},
        }
        self.run_hook("posttool", failed_patch)
        unrelated_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(other),
                "old_string": "old",
                "new_string": "new",
            },
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", unrelated_edit)
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("unapplied patch", output)
        self.assertIn("app.py", output)

    def test_change_plus_explanation_is_still_change_intent(self) -> None:
        target = self.work / "app.py"
        target.write_text("old\n", encoding="utf-8")
        transcript = self.transcript(
            request="Update app.py and explain the change.",
            final="Updated app.py and explained the implementation.",
        )
        post = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "missing",
                "new_string": "new",
            },
            "tool_result": "Error: old_string not found",
        }
        self.run_hook("posttool", post)
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("intended change did not land", output)

    def test_dry_run_patch_failure_is_not_an_unapplied_change(self) -> None:
        transcript = self.transcript(
            request="Check whether change.patch applies cleanly; do not apply it.",
            final="The dry-run check found a conflict.",
        )
        post = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply --check change.patch"},
            "tool_result": {"is_error": True, "content": "patch does not apply"},
        }
        self.run_hook("posttool", post)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_patch_artifact_creation_alone_is_not_flagged(self) -> None:
        artifact = self.work / "review.diff"
        content = "--- a/app.py\n+++ b/app.py\n"
        artifact.write_text(content, encoding="utf-8")
        transcript = self.transcript(
            request="Create review.diff for the reviewer; do not apply it.",
            final="Created the requested review.diff artifact.",
        )
        post = {
            **self.base(transcript),
            "tool_name": "Write",
            "tool_input": {"file_path": str(artifact), "content": content},
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", post)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_implementation_claim_with_unapplied_patch_artifact_is_flagged(self) -> None:
        artifact = self.work / "change.patch"
        content = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        artifact.write_text(content, encoding="utf-8")
        transcript = self.transcript(
            request="Implement the new behavior in app.py, but do not change the public API.",
            final="Implemented the requested behavior in app.py.",
        )
        post = {
            **self.base(transcript),
            "tool_name": "Write",
            "tool_input": {"file_path": str(artifact), "content": content},
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", post)
        code, output = self.run_hook("stop", self.base(transcript))
        self.assertEqual(0, code)
        self.assertIn("patch artifact", output)
        self.assertIn("change.patch", output)
        self.assertIn("app.py", output)

    def test_later_successful_apply_resolves_patch_artifact(self) -> None:
        artifact = self.work / "change.patch"
        content = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        artifact.write_text(content, encoding="utf-8")
        transcript = self.transcript(
            request="Implement the new behavior in app.py.",
            final="Implemented the requested behavior in app.py.",
        )
        write = {
            **self.base(transcript),
            "tool_name": "Write",
            "tool_input": {"file_path": str(artifact), "content": content},
            "tool_result": {"success": True},
        }
        applied = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": {"exit_code": 0, "content": ""},
        }
        self.run_hook("posttool", write)
        self.run_hook("posttool", applied)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_later_direct_edit_resolves_patch_artifact_target(self) -> None:
        artifact = self.work / "change.patch"
        content = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        artifact.write_text(content, encoding="utf-8")
        target = self.work / "app.py"
        target.write_text("new\n", encoding="utf-8")
        transcript = self.transcript(
            request="Implement the new behavior in app.py.",
            final="Implemented the requested behavior in app.py.",
        )
        write = {
            **self.base(transcript),
            "tool_name": "Write",
            "tool_input": {"file_path": str(artifact), "content": content},
            "tool_result": {"success": True},
        }
        landed_edit = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old",
                "new_string": "new",
            },
            "tool_result": {"success": True},
        }
        self.run_hook("posttool", write)
        self.run_hook("posttool", landed_edit)
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_state_directory_retention_is_bounded_and_ttl_pruned(self) -> None:
        self.state.mkdir(parents=True)
        now = 20_000.0
        stale = self.state / "stale.jsonl"
        stale.write_text("{}\n", encoding="utf-8")
        os.utime(stale, (now - 1000, now - 1000))
        for index in range(5):
            path = self.state / f"recent-{index}.jsonl"
            path.write_text("{}\n", encoding="utf-8")
            os.utime(path, (now - index, now - index))
        with (
            mock.patch.object(hook, "STATE_TTL_SECONDS", 100),
            mock.patch.object(hook, "MAX_STATE_FILES", 2),
        ):
            hook._prune_state_dir(now=now)
        remaining = sorted(self.state.glob("*.jsonl"))
        self.assertNotIn(stale, remaining)
        self.assertLessEqual(len(remaining), 2)

    def test_unrelated_existing_changes_are_ignored(self) -> None:
        # Deliberately resembles a dirty worktree, but this hook must never scan it.
        (self.work / ".git").mkdir()
        (self.work / "unrelated-user-change.py").write_text("dirty = True\n", encoding="utf-8")
        transcript = self.transcript(
            request="Explain how this module works.",
            final="Here is the explanation; I made no changes.",
        )
        self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_stop_hook_active_is_silent(self) -> None:
        transcript = self.transcript(final="Patch still needs attention.")
        post = {
            **self.base(transcript),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": {"is_error": True, "content": "patch failed"},
        }
        self.run_hook("posttool", post)
        payload = {**self.base(transcript), "stop_hook_active": True}
        self.assertEqual((0, ""), self.run_hook("stop", payload))

    def test_wrong_turn_state_is_not_replayed(self) -> None:
        first = self.transcript(uuid="turn-old")
        post = {
            **self.base(first),
            "tool_name": "Bash",
            "tool_input": {"command": "git apply change.patch"},
            "tool_result": {"is_error": True, "content": "patch failed"},
        }
        self.run_hook("posttool", post)
        current = self.transcript(
            request="Explain the current code.",
            final="Here is the explanation.",
            uuid="turn-new",
        )
        self.assertEqual((0, ""), self.run_hook("stop", self.base(current)))

    def test_malformed_input_and_injected_errors_fail_open(self) -> None:
        self.assertEqual((0, ""), self.run_hook("posttool", "{not-json"))
        self.assertEqual((0, ""), self.run_hook("stop", "{not-json"))

        transcript = self.transcript()
        post = {
            **self.base(transcript),
            "tool_name": "Edit",
            "tool_input": {"file_path": str(self.work / "app.py")},
            "tool_result": {"is_error": True, "content": "failed"},
        }
        with mock.patch.object(hook, "_append_record", side_effect=OSError("disk full")):
            self.assertEqual((0, ""), self.run_hook("posttool", post))
        with mock.patch.object(hook, "_load_records", side_effect=OSError("unreadable")):
            self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))
        with mock.patch.object(hook, "_turn_context", side_effect=ValueError("bad transcript")):
            self.assertEqual((0, ""), self.run_hook("stop", self.base(transcript)))

    def test_cli_malformed_input_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(THIS / "check.py"), "stop"],
            input="{bad-json",
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(0, proc.returncode)
        self.assertEqual("", proc.stdout)
        self.assertEqual("", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
