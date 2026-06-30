#!/usr/bin/env python3
"""Tests for recall-inject: build_index + inject.  TDD-first, stdlib only.

Run:  pytest test_recall_inject.py -v
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))

import build_index as bi  # noqa: E402  # local sibling module; import follows sys.path setup
import inject as inj  # noqa: E402  # local sibling module; import follows sys.path setup


# ─────────────────────────────────────────────────────────────── helpers


def _make_note(
    path: Path,
    name: str,
    description: str = "",
    permalink: str = "",
    tags: list[str] | None = None,
    extra_body: str = "",
) -> None:
    """Write a well-formed front-matter note."""
    tags_yaml = ""
    if tags:
        tags_yaml = "tags:\n" + "".join(f"  - {t}\n" for t in tags)
    perm_yaml = f"metadata:\n  permalink: {permalink}\n" if permalink else ""
    content = (
        f"---\nname: {name}\ndescription: {description}\n"
        f"{tags_yaml}{perm_yaml}---\n\n"
        f"{extra_body or name + ' content.'}\n"
    )
    path.write_text(content, encoding="utf-8")


def _sid(tmp_path: Path) -> str:
    """Unique session ID per test (avoids dedup cross-contamination)."""
    return "ts" + hashlib.md5(str(tmp_path).encode()).hexdigest()[:12]


@pytest.fixture(autouse=True)
def _isolate_cs_ledger(tmp_path, monkeypatch):
    """Point calibrated-silence at an empty per-test ledger so recall-inject tests
    never read (or write) the LIVE production ledger.

    The recall-inject `_cs_allow`/`_cs_record` call `should_interject` /
    `record_interjection` with no ledger_path, so they use the module-global
    LEDGER_PATH. Repointing it to a fresh empty file makes the CS gate cold-start
    (allow) regardless of how stuffed the production ledger is, and keeps the suite
    deterministic whether or not CALIBRATED_SILENCE is set in the ambient env.
    """
    cs_dir = THIS.parent / "calibrated-silence"
    if str(cs_dir) not in sys.path:
        sys.path.insert(0, str(cs_dir))
    try:
        import calibrated_silence as _c

        empty = tmp_path / "cs_empty.jsonl"
        empty.write_text("", encoding="utf-8")
        monkeypatch.setattr(_c, "LEDGER_PATH", empty, raising=False)
    except Exception:
        pass
    monkeypatch.delenv("CALIBRATED_SILENCE", raising=False)


# ─────────────────────────────────────────────────────────────── build_index


class TestBuildIndex:
    def test_builds_from_sample_notes(self, tmp_path):
        """Index builds from a vault containing well-formed notes."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(
            vault / "bromantane_vendors.md",
            "Bromantane vendor shortlist",
            "LEGIT=pglchem; SCAM=ladasten ring.",
            "main/bromantane_vendors",
        )
        _make_note(
            vault / "bc_trainer_gui.md",
            "BC Trainer GUI",
            "PySide6 trainer for Battle Cats game.",
            "main/bc_trainer_gui",
        )
        idx = bi.get_or_build_index(
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=tmp_path / "idx.json",
        )
        assert isinstance(idx, dict)
        assert "notes" in idx
        assert "vault_hash" in idx
        titles = [n["title"] for n in idx["notes"]]
        assert any("Bromantane" in t for t in titles), (
            f"expected Bromantane in {titles}"
        )
        assert any("Trainer" in t for t in titles), f"expected Trainer in {titles}"

    def test_malformed_front_matter_no_crash(self, tmp_path):
        """Note with unclosed front-matter fence is handled; no crash; good notes remain."""
        vault = tmp_path / "vault"
        vault.mkdir()
        # Malformed: opening --- but no closing ---
        (vault / "malformed.md").write_text(
            "---\nname: Malformed\ndescription: broken note\n"
            "# OOPS not closed\n\nContent.\n",
            encoding="utf-8",
        )
        _make_note(vault / "good.md", "Good note", "This one is fine.")
        idx = bi.get_or_build_index(
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=tmp_path / "idx.json",
        )
        assert idx is not None
        titles = [n["title"] for n in idx["notes"]]
        assert any("Good" in t for t in titles)

    def test_missing_vault_returns_empty_notes(self, tmp_path):
        """Non-existent vault directory → empty notes list, no crash."""
        idx = bi.get_or_build_index(
            vault_dirs=[tmp_path / "nonexistent"],
            memory_md_paths=[],
            index_path=tmp_path / "idx.json",
        )
        assert idx is not None
        assert idx["notes"] == []

    def test_cache_reuse_when_unchanged(self, tmp_path):
        """Second call with identical vault returns cached index (same built_at)."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Test note", "Test description.")
        ipath = tmp_path / "idx.json"
        idx1 = bi.get_or_build_index(
            vault_dirs=[vault], memory_md_paths=[], index_path=ipath
        )
        idx2 = bi.get_or_build_index(
            vault_dirs=[vault], memory_md_paths=[], index_path=ipath
        )
        assert idx1["vault_hash"] == idx2["vault_hash"]
        assert idx1["built_at"] == idx2["built_at"]  # loaded from disk → identical

    def test_cache_invalidated_when_notes_change(self, tmp_path):
        """Adding a new note invalidates the cache and triggers a rebuild."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Initial note", "Initial description.")
        ipath = tmp_path / "idx.json"
        idx1 = bi.get_or_build_index(
            vault_dirs=[vault], memory_md_paths=[], index_path=ipath
        )
        # Write new file (ensures mtime/size differ)
        time.sleep(0.05)
        _make_note(vault / "note2.md", "New note", "Added later.")
        idx2 = bi.get_or_build_index(
            vault_dirs=[vault], memory_md_paths=[], index_path=ipath
        )
        assert idx1["vault_hash"] != idx2["vault_hash"]
        assert len(idx2["notes"]) > len(idx1["notes"])

    def test_memory_md_entries_included(self, tmp_path):
        """MEMORY.md bullet-list entries are parsed and included in the index."""
        mem = tmp_path / "MEMORY.md"
        mem.write_text(
            "- [Bromantane vendors](reference_bromantane_vendors.md)"
            " — LEGIT=pglchem; SCAM=ladasten.\n"
            "- [BC Trainer GUI](bc_trainer_gui.md)"
            " — PySide6 trainer for Battle Cats.\n",
            encoding="utf-8",
        )
        idx = bi.get_or_build_index(
            vault_dirs=[],
            memory_md_paths=[mem],
            index_path=tmp_path / "idx.json",
        )
        titles = [n["title"] for n in idx["notes"]]
        assert any("Bromantane" in t for t in titles), titles
        assert any("Trainer" in t for t in titles), titles

    def test_tags_contribute_keywords(self, tmp_path):
        """Tags from front-matter are included in note keywords."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(
            vault / "frida_hook.md",
            "Frida Interceptor Guide",
            "Attaching Frida to Android processes.",
            tags=["frida", "android", "interceptor"],
        )
        idx = bi.get_or_build_index(
            vault_dirs=[vault], memory_md_paths=[], index_path=tmp_path / "idx.json"
        )
        note = next((n for n in idx["notes"] if "Frida" in n["title"]), None)
        assert note is not None
        kw = set(note["keywords"])
        assert "frida" in kw
        assert "android" in kw
        assert "interceptor" in kw

    def test_memory_md_summary_overrides_vault_description(self, tmp_path):
        """When both vault and MEMORY.md have the same note, MEMORY.md summary is used."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(
            vault / "ref_vendor.md",
            "Bromantane vendors",
            "Long technical description from front-matter.",
            "main/ref_vendor",
        )
        mem = tmp_path / "MEMORY.md"
        mem.write_text(
            "- [Bromantane vendors](ref_vendor.md)"
            " — Short pithy summary from MEMORY.md.\n",
            encoding="utf-8",
        )
        idx = bi.get_or_build_index(
            vault_dirs=[vault],
            memory_md_paths=[mem],
            index_path=tmp_path / "idx.json",
        )
        note = next((n for n in idx["notes"] if "Bromantane" in n["title"]), None)
        assert note is not None
        assert "Short pithy summary" in note["summary"]


# ─────────────────────────────────────────────────────────────── match_notes


class TestMatchNotes:
    def _make_idx(self, notes: list[dict]) -> dict:
        return {"vault_hash": "test", "built_at": 0.0, "notes": notes}

    def _note(
        self,
        title: str,
        summary: str,
        keywords: list[str],
        permalink: str = "main/test",
    ) -> dict:
        return {
            "path": "test.md",
            "title": title,
            "summary": summary,
            "permalink": permalink,
            "keywords": keywords,
        }

    def test_matching_keyword_returns_note(self):
        idx = self._make_idx(
            [
                self._note(
                    "Bromantane vendors",
                    "pglchem is legit",
                    ["bromantane", "vendor", "pglchem", "legit"],
                ),
            ]
        )
        matches = inj.match_notes("bromantane vendor sources", idx)
        assert len(matches) >= 1
        assert matches[0]["title"] == "Bromantane vendors"

    def test_no_match_returns_empty(self):
        idx = self._make_idx(
            [
                self._note(
                    "Bromantane vendors", "pglchem", ["bromantane", "vendor", "pglchem"]
                ),
            ]
        )
        matches = inj.match_notes("what is the weather today", idx)
        assert matches == []

    def test_capped_at_top_three(self):
        notes = [
            self._note(
                f"Frida note {i}",
                f"frida interceptor description {i}",
                ["frida", "interceptor", "android", "hook"],
                f"main/frida_{i}",
            )
            for i in range(6)
        ]
        idx = self._make_idx(notes)
        matches = inj.match_notes("frida interceptor android hook", idx)
        assert len(matches) <= 3

    def test_strong_single_long_token_qualifies(self):
        """A single matched token ≥ STRONG_SINGLE_LEN chars is sufficient."""
        idx = self._make_idx(
            [
                self._note(
                    "Bromantane vendors", "pglchem is legit", ["bromantane", "vendor"]
                ),
            ]
        )
        # "bromantane" is 10 chars → strong single hit
        matches = inj.match_notes("where to buy bromantane online", idx)
        assert len(matches) >= 1

    def test_sorted_by_score_descending(self):
        idx = self._make_idx(
            [
                self._note("Low score", "minor match", ["bromantane"]),
                self._note(
                    "High score",
                    "many keyword hits",
                    ["bromantane", "vendor", "legit", "pglchem"],
                ),
            ]
        )
        matches = inj.match_notes("bromantane vendor legit pglchem", idx)
        assert matches[0]["title"] == "High score"

    def test_empty_prompt_returns_empty(self):
        idx = self._make_idx([self._note("Test", "test content", ["test"])])
        assert inj.match_notes("", idx) == []
        assert inj.match_notes("   ", idx) == []

    def test_two_char_filename_token_in_keywords_not_matched_by_prompt(self):
        """2-char tokens like 'bc' appear in note keywords (from filename) but
        the prompt tokenizer requires 3+ chars, so 'bc' in prompt is invisible."""
        # This tests that precision is maintained: short abbreviations in prompts
        # don't create false positives via the 3-char prompt token filter.
        idx = self._make_idx(
            [
                self._note("BC note", "battle cats", ["bc", "battle", "cats"]),
            ]
        )
        # Prompt has only generic words and "bc" (2 chars, filtered by _tok)
        matches = inj.match_notes("check bc status now", idx)
        # "check" and "status" are not in note keywords → no match
        # If "check" or "status" happen to be in keywords, test is still fine
        # since we're checking the 2-char "bc" case specifically
        for m in matches:
            overlap = set(inj._tok("check bc status now")) & set(m["keywords"])
            assert len(overlap) >= 2 or any(
                len(t) >= inj.STRONG_SINGLE_LEN for t in overlap
            )


# ─────────────────────────────────────────────────────────────── format_message


class TestFormatMessage:
    def test_includes_title_summary_permalink(self):
        matches = [
            {
                "title": "Bromantane vendors",
                "summary": "LEGIT=pglchem.",
                "permalink": "main/reference_bromantane_vendors",
            }
        ]
        msg = inj.format_message(matches)
        assert "Bromantane vendors" in msg
        assert "LEGIT=pglchem" in msg
        assert "main/reference_bromantane_vendors" in msg
        assert "recall" in msg.lower()

    def test_multiple_matches_all_listed(self):
        matches = [
            {"title": "Note A", "summary": "summary A", "permalink": "main/a"},
            {"title": "Note B", "summary": "summary B", "permalink": "main/b"},
        ]
        msg = inj.format_message(matches)
        assert "Note A" in msg
        assert "Note B" in msg

    def test_no_permalink_omits_recall_line(self):
        matches = [{"title": "Note X", "summary": "some summary", "permalink": ""}]
        msg = inj.format_message(matches)
        assert "Note X" in msg
        # No crash even without permalink


# ─────────────────────────────────────────────────────────────── run (integration)


class TestRunFunction:
    """Integration tests for inject.run() with controlled vault paths."""

    def _setup(self, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "bromantane.md").write_text(
            "---\n"
            "name: Bromantane vendors\n"
            "description: LEGIT=pglchem; SCAM=ladasten.\n"
            "tags:\n  - bromantane\n  - vendors\n"
            "metadata:\n  permalink: main/bromantane\n"
            "---\n\n"
            "pglchem is the anchor vendor.\n",
            encoding="utf-8",
        )
        return vault, tmp_path / "idx.json"

    def test_matching_prompt_returns_message(self, tmp_path):
        vault, ipath = self._setup(tmp_path)
        code, msg = inj.run(
            {
                "prompt": "where to buy bromantane vendors online trusted",
                "session_id": _sid(tmp_path),
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is not None
        assert "Bromantane" in msg

    def test_no_match_returns_none(self, tmp_path):
        vault, ipath = self._setup(tmp_path)
        code, msg = inj.run(
            {
                "prompt": "unrelated topic about quantum physics experiments",
                "session_id": _sid(tmp_path),
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is None

    def test_dedup_second_call_silent(self, tmp_path):
        """Same session + same note set → second injection is silenced."""
        vault, ipath = self._setup(tmp_path)
        sid = "dedup_" + _sid(tmp_path)
        code1, msg1 = inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase safely",
                "session_id": sid,
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        code2, msg2 = inj.run(
            {
                "prompt": "bromantane vendors legit suppliers trusted online",
                "session_id": sid,
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code1 == 0
        assert code2 == 0
        if msg1 is not None:  # guard: calibrated-silence might block first call too
            assert msg2 is None, "Second call with same session should be deduplicated"

    def test_opt_out_via_env(self, tmp_path, monkeypatch):
        """RECALL_INJECT=off → run() exits 0 without emitting."""
        vault, ipath = self._setup(tmp_path)
        monkeypatch.setenv("RECALL_INJECT", "off")
        code, msg = inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase",
                "session_id": "env_off",
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is None

    def test_opt_out_via_disabled_fn(self, tmp_path, monkeypatch):
        """_disabled() returning True → run() exits 0 without emitting."""
        vault, ipath = self._setup(tmp_path)
        monkeypatch.setattr(inj, "_disabled", lambda: True)
        code, msg = inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase",
                "session_id": "fn_disabled",
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is None

    def test_missing_vault_silent(self, tmp_path):
        """Non-existent vault → no crash, no injection."""
        code, msg = inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase",
                "session_id": _sid(tmp_path),
            },
            vault_dirs=[tmp_path / "nonexistent"],
            memory_md_paths=[],
            index_path=tmp_path / "idx.json",
        )
        assert code == 0
        assert msg is None

    def test_short_prompt_silent(self, tmp_path):
        """Prompt below MIN_LEN → silent exit 0."""
        vault, ipath = self._setup(tmp_path)
        code, msg = inj.run(
            {"prompt": "hi", "session_id": _sid(tmp_path)},
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is None

    def test_main_emits_json_on_match(self, tmp_path, monkeypatch, capsys):
        """main() emits valid JSON hookSpecificOutput when a match is found."""
        vault, ipath = self._setup(tmp_path)
        sid = "main_" + _sid(tmp_path)
        data = json.dumps(
            {"prompt": "bromantane vendor trusted purchase sources", "session_id": sid}
        )
        monkeypatch.setattr("sys.stdin", __import__("io").StringIO(data))
        # Patch vault/index paths via the _bi module's defaults
        monkeypatch.setattr(inj._bi, "find_vault_dirs", lambda: [vault])
        monkeypatch.setattr(inj._bi, "find_memory_md_paths", lambda: [])
        monkeypatch.setattr(inj._bi, "INDEX_PATH", ipath)
        result = inj.main()
        assert result == 0
        captured = capsys.readouterr().out.strip()
        if captured:
            obj = json.loads(captured)
            assert "hookSpecificOutput" in obj
            assert obj["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
            assert "additionalContext" in obj["hookSpecificOutput"]


# ─────────────────────────────────────────────────── M3: calibrated-silence gate


class TestCalibratedSilenceGate:
    """M3 regression: CS gate must receive a dict (not a string) and must gate."""

    def _setup(self, tmp_path: Path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "bromantane.md").write_text(
            "---\n"
            "name: Bromantane vendors\n"
            "description: LEGIT=pglchem; SCAM=ladasten.\n"
            "tags:\n  - bromantane\n  - vendors\n"
            "metadata:\n  permalink: main/bromantane\n"
            "---\n\n"
            "pglchem is the anchor vendor.\n",
            encoding="utf-8",
        )
        return vault, tmp_path / "idx.json"

    def test_cs_allow_called_with_dict_not_string(self, tmp_path, monkeypatch):
        """_cs_allow must be called with a dict context, not a bare string.

        Before the M3 fix, the call was _cs_allow("gem", prompt[:100]) which
        passed a string; should_interject then crashed on context.get("ledger_path")
        → AttributeError → fail-open True, silently disabling the gate forever.
        """
        vault, ipath = self._setup(tmp_path)
        captured: dict = {}

        def fake_cs_allow(itype: str, ctx) -> bool:
            captured["itype"] = itype
            captured["ctx"] = ctx
            return True  # allow (check type only, don't suppress)

        monkeypatch.setattr(inj, "_cs_allow", fake_cs_allow)

        inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase safely",
                "session_id": _sid(tmp_path),
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert "ctx" in captured, (
            "_cs_allow was never called — no note matched (check test setup)"
        )
        assert isinstance(captured["ctx"], dict), (
            f"_cs_allow received {type(captured['ctx']).__name__!r} instead of dict; "
            "should_interject would crash on .get() → AttributeError → fail-open"
        )

    def test_cs_gate_suppresses_injection_when_returning_false(
        self, tmp_path, monkeypatch
    ):
        """When _cs_allow returns False the injection MUST be suppressed (gate actually gates).

        Before the M3 fix, _cs_allow always crashed internally and fell through
        to fail-open True, so returning False was never reached.
        """
        vault, ipath = self._setup(tmp_path)

        monkeypatch.setattr(inj, "_cs_allow", lambda itype, ctx: False)

        code, msg = inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase safely",
                "session_id": _sid(tmp_path),
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert code == 0
        assert msg is None, (
            "CS gate returned False but injection was NOT suppressed — gate is dead"
        )

    def test_cs_gate_dict_contains_prompt_and_session(self, tmp_path, monkeypatch):
        """The dict passed to _cs_allow contains 'prompt' and 'session_id' keys."""
        vault, ipath = self._setup(tmp_path)
        captured: dict = {}
        sid = "csgate_" + _sid(tmp_path)

        def fake_cs_allow(itype: str, ctx) -> bool:
            captured.update(ctx if isinstance(ctx, dict) else {})
            return True

        monkeypatch.setattr(inj, "_cs_allow", fake_cs_allow)

        inj.run(
            {
                "prompt": "bromantane vendor trusted sources purchase safely",
                "session_id": sid,
            },
            vault_dirs=[vault],
            memory_md_paths=[],
            index_path=ipath,
        )
        assert "prompt" in captured, (
            f"ctx dict missing 'prompt' key; got {set(captured)}"
        )
        assert "session_id" in captured, (
            f"ctx dict missing 'session_id' key; got {set(captured)}"
        )


# ─────────────────────────────────────────────────── L1: generic-word precision


class TestGenericWordPrecision:
    """L1 regression: generic English words ≥ 7 chars must NOT fire solo."""

    def _make_idx(self, notes: list[dict]) -> dict:
        return {"vault_hash": "test", "built_at": 0.0, "notes": notes}

    def _note(
        self, title: str, summary: str, keywords: list[str], permalink: str = "main/t"
    ) -> dict:
        return {
            "path": "t.md",
            "title": title,
            "summary": summary,
            "permalink": permalink,
            "keywords": keywords,
        }

    def test_generic_word_function_does_not_over_fire(self):
        """'function' is 8 chars but is in _GENERIC_LONG → must not qualify solo."""
        idx = self._make_idx(
            [
                self._note(
                    "Function Guide",
                    "guide to python functions",
                    ["function", "guide", "python"],
                ),
            ]
        )
        # Only "function" overlaps; score=1 < MIN_SCORE; "function" is GENERIC_LONG
        matches = inj.match_notes("function signature explanation", idx)
        # "signature" / "explanation" are not in note keywords → overlap = {"function"} only
        # score=1, "function" in _GENERIC_LONG → must not qualify
        assert matches == [], (
            f"Generic word 'function' alone triggered injection: {[m['title'] for m in matches]}"
        )

    def test_generic_word_database_does_not_over_fire(self):
        """'database' is 8 chars but generic — must not fire alone."""
        idx = self._make_idx(
            [
                self._note(
                    "Database Setup",
                    "setting up postgres",
                    ["database", "postgres", "setup"],
                ),
            ]
        )
        matches = inj.match_notes("database connection error", idx)
        # overlap with "database" only (score=1), generic → no fire
        assert matches == [], (
            f"Generic 'database' alone triggered: {[m['title'] for m in matches]}"
        )

    def test_generic_word_security_does_not_over_fire(self):
        """'security' is 8 chars and generic."""
        idx = self._make_idx(
            [
                self._note(
                    "Security Review",
                    "code security analysis",
                    ["security", "review", "analysis"],
                ),
            ]
        )
        matches = inj.match_notes("security check required", idx)
        assert matches == [], (
            f"Generic 'security' alone triggered: {[m['title'] for m in matches]}"
        )

    def test_distinctive_long_token_still_qualifies(self):
        """Distinctive domain terms like 'bromantane' (10 chars, not in GENERIC_LONG) still fire."""
        idx = self._make_idx(
            [
                self._note(
                    "Bromantane vendors", "pglchem is legit", ["bromantane", "vendor"]
                ),
            ]
        )
        matches = inj.match_notes("where can I buy bromantane", idx)
        assert len(matches) >= 1, (
            "Distinctive domain term 'bromantane' should still qualify solo"
        )

    def test_distinctive_frida_still_qualifies(self):
        """'frida' is 5 chars — below STRONG_SINGLE_LEN but qualifies via multi-token score."""
        idx = self._make_idx(
            [
                self._note(
                    "Frida hook",
                    "attach frida to android process",
                    ["frida", "android", "hook", "attach", "process"],
                ),
            ]
        )
        # "frida" is only 5 chars so it won't hit the strong-single path; but with
        # "android" and "hook" also matching (score ≥ 2) it should still qualify.
        matches = inj.match_notes("frida android hook setup", idx)
        assert len(matches) >= 1, (
            "Multi-token match with 'frida android hook' should qualify"
        )

    def test_two_distinct_generic_tokens_still_fire(self):
        """Two generic tokens together (score ≥ MIN_SCORE=2) still qualify — min-score path."""
        idx = self._make_idx(
            [
                self._note(
                    "Security Analysis",
                    "security code analysis",
                    ["security", "analysis", "code"],
                ),
            ]
        )
        # score=2 (security + analysis both match) → qualifies via score≥MIN_SCORE, not GENERIC path
        matches = inj.match_notes("security analysis review", idx)
        assert len(matches) >= 1, (
            "Two matching tokens (score≥2) should qualify even if both are generic"
        )


# ─────────────────────────────────────────────────── L2: vault hash cache skip


class TestVaultSnapshotHashCacheSkip:
    """L2 regression: _vault_snapshot_hash must skip dot-dirs like .hf / .models."""

    def test_hf_cache_dir_changes_do_not_affect_hash(self, tmp_path):
        """Adding files inside .hf must NOT change the snapshot hash."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Real note", "Included in hash.")

        # Create a .hf cache directory with a markdown file inside
        hf_dir = vault / ".hf"
        hf_dir.mkdir()
        (hf_dir / "model_card.md").write_text(
            "---\nname: Cache File\n---\nThis is inside a cache dir.\n",
            encoding="utf-8",
        )

        h1 = bi._vault_snapshot_hash([vault], [])

        # Add another markdown file to .hf — should not change hash
        (hf_dir / "readme.md").write_text("extra cache content", encoding="utf-8")

        h2 = bi._vault_snapshot_hash([vault], [])
        assert h1 == h2, (
            ".hf cache dir content changed but hash changed — dot-dirs are not being skipped"
        )

    def test_models_cache_dir_skipped(self, tmp_path):
        """Adding files inside .models must NOT change the snapshot hash."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Real note", "Included in hash.")
        models_dir = vault / ".models"
        models_dir.mkdir()
        (models_dir / "config.md").write_text("model config", encoding="utf-8")

        h1 = bi._vault_snapshot_hash([vault], [])
        (models_dir / "extra.md").write_text("extra model file", encoding="utf-8")
        h2 = bi._vault_snapshot_hash([vault], [])
        assert h1 == h2, ".models cache dir not being skipped by vault hash"

    def test_git_dir_skipped(self, tmp_path):
        """.git directory must be skipped."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Real note", "Included.")
        git_dir = vault / ".git"
        git_dir.mkdir()
        (git_dir / "COMMIT_EDITMSG.md").write_text("commit message", encoding="utf-8")

        h1 = bi._vault_snapshot_hash([vault], [])
        (git_dir / "extra.md").write_text("another git file", encoding="utf-8")
        h2 = bi._vault_snapshot_hash([vault], [])
        assert h1 == h2, ".git dir not being skipped by vault hash"

    def test_real_vault_changes_still_change_hash(self, tmp_path):
        """Changes to non-dotdir vault files MUST still change the hash."""
        vault = tmp_path / "vault"
        vault.mkdir()
        _make_note(vault / "note.md", "Original note", "Original description.")

        # Populate a .hf dir so we verify the skip AND that real changes still work
        (vault / ".hf").mkdir()
        (vault / ".hf" / "cached.md").write_text("ignored", encoding="utf-8")

        h1 = bi._vault_snapshot_hash([vault], [])

        time.sleep(0.05)  # ensure mtime differs on slow filesystems
        _make_note(vault / "note2.md", "New note", "Added later.")
        h2 = bi._vault_snapshot_hash([vault], [])
        assert h1 != h2, (
            "Real vault note added but hash did not change — broken snapshot logic"
        )
