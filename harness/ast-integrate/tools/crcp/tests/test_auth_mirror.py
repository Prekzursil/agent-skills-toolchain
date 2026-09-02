from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from crcp import auth_mirror
from crcp.__main__ import _exit_for


def _chrome_timestamp(unix_seconds: int) -> int:
    return (unix_seconds + 11_644_473_600) * 1_000_000


class AuthMirrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temporary.name)
        self.db = self.root / "Cookies"
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                """CREATE TABLE cookies (
                    host_key TEXT, name TEXT, path TEXT, is_secure INTEGER,
                    is_httponly INTEGER, samesite INTEGER, is_persistent INTEGER,
                    expires_utc INTEGER, encrypted_value BLOB
                )"""
            )
            connection.executemany(
                "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        ".chatgpt.com",
                        "_puid",
                        "/",
                        1,
                        0,
                        1,
                        1,
                        _chrome_timestamp(1_800_000_000),
                        b"encrypted-one",
                    ),
                    ("chatgpt.com", "_uasid", "/x", 1, 1, 2, 0, 0, b"encrypted-two"),
                ],
            )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_paths_use_measured_locations(self) -> None:
        with mock.patch.dict(os.environ, {"APPDATA": str(self.root)}):
            user_data = auth_mirror.default_user_data_dir()
        self.assertEqual(user_data, self.root / "Codex" / "web" / "Codex")
        self.assertEqual(
            auth_mirror.cookie_db_paths(user_data),
            [
                user_data / "Default" / "Network" / "Cookies",
                user_data
                / "Default"
                / "Partitions"
                / "codex-browser-app"
                / "Network"
                / "Cookies",
            ],
        )

    def test_inventory_is_metadata_only(self) -> None:
        rows = auth_mirror.inventory_cookies(self.db)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["encrypted_value_len"], len(b"encrypted-one"))
        self.assertEqual(rows[0]["expires_unix"], 1_800_000_000)
        self.assertIsNone(rows[1]["expires_unix"])
        serialized = json.dumps(rows)
        self.assertNotIn("encrypted-one", serialized)
        self.assertNotIn('"value"', serialized)

    def test_summary_honestly_reports_missing_nextauth(self) -> None:
        summary = auth_mirror._summarize(
            [(self.db, auth_mirror.inventory_cookies(self.db))]
        )
        self.assertEqual(summary["status"], "partial_without_nextauth")
        self.assertEqual(summary["cookie_count"], 2)

    def test_decrypt_requires_opt_in_and_is_none_on_linux(self) -> None:
        with self.assertRaises(PermissionError):
            auth_mirror.decrypt_cookie_value(b"anything", self.root / "Local State")
        if os.name != "nt":
            self.assertIsNone(
                auth_mirror.decrypt_cookie_value(
                    b"anything", self.root / "Local State", allow_decrypt=True
                )
            )

    def test_secret_export_guard_and_json(self) -> None:
        cookies = [
            {"host_key": ".chatgpt.com", "name": "x", "path": "/", "value": "secret"}
        ]
        with self.assertRaises(PermissionError):
            auth_mirror.export_cookies_json(cookies, self.root / "blocked.json")
        with mock.patch.object(auth_mirror, "RESULT_DIR", self.root / "results"):
            with self.assertRaises(PermissionError):
                auth_mirror.export_cookies_json(
                    cookies, self.root / "results" / "cookies.json", allow_decrypt=True
                )
        out = self.root / "private" / "cookies.json"
        auth_mirror.export_cookies_json(cookies, out, allow_decrypt=True)
        self.assertEqual(
            json.loads(out.read_text(encoding="utf-8"))[0]["value"], "secret"
        )

    def test_cdp_format(self) -> None:
        formatted = auth_mirror.format_cdp_cookie(
            {
                "host_key": ".chatgpt.com",
                "name": "x",
                "value": b"y",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "samesite": 1,
                "expires_unix": 1_800_000_000,
            }
        )
        self.assertEqual(formatted["domain"], ".chatgpt.com")
        self.assertEqual(formatted["sameSite"], "Lax")
        self.assertEqual(formatted["value"], "y")

    def test_metadata_export_contains_no_values(self) -> None:
        user_data = self.root / "profile"
        target = user_data / "Default" / "Network" / "Cookies"
        target.parent.mkdir(parents=True)
        target.write_bytes(self.db.read_bytes())
        output = self.root / "inventory-output"
        with mock.patch.object(
            auth_mirror, "default_user_data_dir", return_value=user_data
        ):
            report = auth_mirror.run_mirror_export(output, decrypt=False)
        text = (output / "cookie_inventory.json").read_text(encoding="utf-8")
        self.assertEqual(report["status"], "partial_without_nextauth")
        self.assertNotIn("encrypted-one", text)
        self.assertNotIn('"value"', text)

    def _profile_with_nextauth(self, blob: bytes) -> Path:
        user_data = self.root / "profile"
        target = user_data / "Default" / "Network" / "Cookies"
        target.parent.mkdir(parents=True)
        with sqlite3.connect(target) as connection:
            connection.execute(
                """CREATE TABLE cookies (
                    host_key TEXT, name TEXT, path TEXT, is_secure INTEGER,
                    is_httponly INTEGER, samesite INTEGER, is_persistent INTEGER,
                    expires_utc INTEGER, encrypted_value BLOB
                )"""
            )
            connection.execute(
                "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (".chatgpt.com", auth_mirror.NEXTAUTH_COOKIE, "/", 1, 1, 0, 1, 0, blob),
            )
        return user_data

    def test_decrypt_export_refuses_when_session_cookie_undecryptable(self) -> None:
        # Regression for D-wu-47: the pre-decrypt summary reports status "ok"
        # whenever the NextAuth cookie is present by NAME in the inventory. If
        # that cookie cannot be decrypted the export must NOT publish an empty
        # file, must NOT report success, and the CLI must exit non-zero.
        user_data = self._profile_with_nextauth(b"v10-undecryptable")
        output = self.root / "secret-out"
        with mock.patch.object(
            auth_mirror, "default_user_data_dir", return_value=user_data
        ):
            with mock.patch.object(
                auth_mirror, "decrypt_cookie_value", return_value=None
            ):
                with mock.patch.object(auth_mirror, "export_cookies_json") as publisher:
                    report = auth_mirror.run_mirror_export(output, decrypt=True)
        publisher.assert_not_called()
        self.assertEqual(report["status"], "decrypt_incomplete")
        self.assertIs(report["ok"], False)
        self.assertEqual(report["decrypted_count"], 0)
        self.assertEqual(report["decrypt_failed_count"], 1)
        self.assertNotEqual(report["export_kind"], "decrypted_json")
        self.assertNotIn("export_path", report)
        self.assertFalse((output / "cookies.json").exists())
        self.assertEqual(_exit_for(report), 1)

    def test_decrypt_export_publishes_when_session_cookie_decrypts(self) -> None:
        # Guard the success path so the D-wu-47 fix does not over-correct: when
        # the NextAuth cookie decrypts, the export is published and reported ok.
        user_data = self._profile_with_nextauth(b"v10-decryptable")
        output = self.root / "secret-out"
        with mock.patch.object(
            auth_mirror, "default_user_data_dir", return_value=user_data
        ):
            with mock.patch.object(
                auth_mirror, "decrypt_cookie_value", return_value=b"session-value"
            ):
                report = auth_mirror.run_mirror_export(output, decrypt=True)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["export_kind"], "decrypted_json")
        self.assertEqual(report["decrypted_count"], 1)
        self.assertEqual(report["decrypt_failed_count"], 0)
        self.assertEqual(_exit_for(report), 0)
        published = json.loads((output / "cookies.json").read_text(encoding="utf-8"))
        self.assertEqual(published[0]["name"], auth_mirror.NEXTAUTH_COOKIE)
        self.assertEqual(published[0]["value"], "session-value")


if __name__ == "__main__":
    unittest.main()
