from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "register_mcp_server.py"
spec = importlib.util.spec_from_file_location("register_mcp_server", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RegisterMcpServerTests(unittest.TestCase):
    def test_build_json_entry_for_claude_sets_stdio_type(self):
        entry = mod.build_json_entry(
            {"command": "npx", "args": ["-y", "repomix", "--mcp"]}, "claude"
        )
        self.assertEqual(entry["type"], "stdio")

    def test_build_json_entry_for_gemini_sets_trust(self):
        entry = mod.build_json_entry(
            {"command": "npx", "args": ["-y", "repomix", "--mcp"]}, "gemini"
        )
        self.assertTrue(entry["trust"])
        self.assertEqual(entry["command"], "npx")

    def test_upsert_codex_config_replaces_existing_server(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "config.toml"
            config.write_text(
                '[mcp_servers."repomix"]\ncommand = "old"\n\n[mcp_servers.other]\ncommand = "stay"\n',
                encoding="utf-8",
            )
            mod.upsert_codex_config(
                config,
                "repomix",
                {"command": "npx", "args": ["-y", "repomix", "--mcp"]},
            )
            text = config.read_text(encoding="utf-8")
            self.assertIn('command = "npx"', text)
            self.assertIn("[mcp_servers.other]", text)
            self.assertNotIn('command = "old"', text)

    def test_upsert_json_client_creates_mcp_servers(self):
        with tempfile.TemporaryDirectory() as td:
            config = Path(td) / "claude.json"
            config.write_text(json.dumps({"foo": 1}), encoding="utf-8")
            mod.upsert_json_client(
                config,
                "repomix",
                {"command": "npx", "args": ["-y", "repomix", "--mcp"]},
            )
            data = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(data["mcpServers"]["repomix"]["command"], "npx")


if __name__ == "__main__":
    unittest.main()
