"""Offline parser and dispatch tests for the CRCP auth CLI wiring."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


def _load_candidate():
    """Load the delivered __main__.py in the installed crcp package context."""
    import crcp  # noqa: F401 - establishes the package for relative imports

    # Prefer package __main__; fall back to a sibling copy if present.
    package_main = Path(__file__).resolve().parents[1] / "crcp" / "__main__.py"
    path = package_main if package_main.is_file() else Path(__file__).with_name("__main__.py")
    spec = importlib.util.spec_from_file_location("crcp._auth_cli_wire", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load CLI candidate: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cli = _load_candidate()


class ParserRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = cli.build_parser()

    def test_mirror_options_are_registered(self) -> None:
        args = self.parser.parse_args([
            "auth", "mirror", "--user-data", "profile", "--json",
            "--export", "cookies", "--decrypt",
        ])
        self.assertIs(args.func, cli.cmd_auth_mirror)
        self.assertEqual(args.user_data, "profile")
        self.assertEqual(args.export, "cookies")
        self.assertTrue(args.decrypt)

    def test_deeplink_commands_are_registered(self) -> None:
        built = self.parser.parse_args([
            "auth", "deeplink", "build", "--path", "chat",
            "--query", "conversation_id=abc", "--query", "mode=desktop",
        ])
        opened = self.parser.parse_args(["auth", "deeplink", "open", "codex://open"])
        status = self.parser.parse_args(["auth", "deeplink", "status"])
        self.assertIs(built.func, cli.cmd_auth_deeplink_build)
        self.assertEqual(built.query, ["conversation_id=abc", "mode=desktop"])
        self.assertIs(opened.func, cli.cmd_auth_deeplink_open)
        self.assertIs(status.func, cli.cmd_auth_deeplink_status)

    def test_sso_commands_and_options_are_registered(self) -> None:
        login = self.parser.parse_args([
            "auth", "sso", "login", "--redirect-uri", "http://127.0.0.1:8765/callback",
            "--print-url", "--code", "opaque-code", "--timeout", "12",
        ])
        preview = self.parser.parse_args([
            "auth", "sso", "authorize-url", "--redirect-uri", "http://localhost:8765/callback",
        ])
        self.assertIs(login.func, cli.cmd_auth_sso_login)
        self.assertEqual(login.timeout, 12)
        self.assertTrue(login.print_url)
        self.assertIs(preview.func, cli.cmd_auth_sso_authorize_url)

    def test_existing_commands_remain_registered(self) -> None:
        cases = (
            (["auth", "status"], cli.cmd_auth_status),
            (["auth", "watch", "--once"], cli.cmd_auth_watch),
            (["health", "--json"], cli.cmd_health),
            (["chatgpt", "list"], cli.cmd_chatgpt_list),
            (["chatgpt", "fetch", "--latest", "2"], cli.cmd_chatgpt_fetch),
            (["chatgpt", "live", "--once"], cli.cmd_chatgpt_live),
            (["chatgpt", "send", "hello"], cli.cmd_chatgpt_send),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertIs(self.parser.parse_args(argv).func, expected)

    def test_auth_help_lists_new_and_existing_commands(self) -> None:
        output = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stdout(output):
            self.parser.parse_args(["auth", "--help"])
        self.assertEqual(raised.exception.code, 0)
        for name in ("status", "watch", "mirror", "deeplink", "sso"):
            self.assertIn(name, output.getvalue())


class DispatchSafetyTests(unittest.TestCase):
    def test_missing_sibling_is_json_config_error(self) -> None:
        output = io.StringIO()
        with mock.patch.object(cli, "_auth_import", side_effect=cli.AuthCliConfigError("missing sibling")):
            with contextlib.redirect_stdout(output):
                exit_code = cli.main(["auth", "deeplink", "status"])
        self.assertEqual(exit_code, 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["error"]["kind"], "config")

    def test_sensitive_result_fields_and_url_query_are_redacted(self) -> None:
        result = {
            "access_token": "do-not-print",
            "nested": {"refresh-token": "also-secret"},
            "authorize_url": "https://example.test/cb?code=secret&state=metadata",
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cli._print_json(result)
        rendered = output.getvalue()
        self.assertNotIn("do-not-print", rendered)
        self.assertNotIn("also-secret", rendered)
        self.assertNotIn("code=secret", rendered)
        self.assertIn("state=metadata", rendered)

    def test_invalid_query_is_hard_config_error(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli.main(["auth", "deeplink", "build", "--query", "missing-separator"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(output.getvalue())["error"]["kind"], "config")


if __name__ == "__main__":
    unittest.main()
