#!/usr/bin/env python3
"""Named probe 1: every planted payload class is caught; mention is not.

Classes: role-spoof, ignore-previous-instructions, base64-exec, bundled
.claude and .codex agent config. A documentation quote of those strings
must stay silent. Neutralisation must keep the source file and its
mechanism/stage tokens.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_injection_gate.consumer import extract_tokens  # noqa: E402
from wfa_injection_gate.corpus import (  # noqa: E402
    PAYLOAD_CLASSES,
    write_corpus,
)
from wfa_injection_gate.gate import (  # noqa: E402
    is_bundled_agent_config,
    mention_spans,
    neutralise_text,
    neutralise_tree,
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0121-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wfa0121-p1-") as raw:
        root = Path(raw)
        src = root / "src"
        dest = root / "gated"
        paths = write_corpus(src)
        rows = {r.relpath: r for r in neutralise_tree(src, dest)}

        caught: set[str] = set()
        for result in rows.values():
            caught.update(result.classes)
        missing = [c for c in PAYLOAD_CLASSES if c not in caught]
        if missing:
            return fail(f"uncaught payload classes {missing}; caught={sorted(caught)}")

        role_rel = paths["role-spoof"].relative_to(src).as_posix()
        if "role-spoof" not in rows[role_rel].classes:
            return fail(f"role-spoof missed on {role_rel}: {rows[role_rel].classes}")

        ign_rel = paths["ignore-previous"].relative_to(src).as_posix()
        if "ignore-previous" not in rows[ign_rel].classes:
            return fail(f"ignore-previous missed on {ign_rel}")

        b64_rel = paths["base64-exec"].relative_to(src).as_posix()
        if "base64-exec" not in rows[b64_rel].classes:
            return fail(f"base64-exec missed on {b64_rel}")

        claude_rel = paths["bundled-claude"].relative_to(src).as_posix()
        codex_rel = paths["bundled-codex"].relative_to(src).as_posix()
        if not is_bundled_agent_config(claude_rel):
            return fail(".claude path not classified as bundled agent config")
        if not is_bundled_agent_config(codex_rel):
            return fail(".codex path not classified as bundled agent config")
        if "bundled-agent-config" not in rows[claude_rel].classes:
            return fail("bundled .claude settings.json not caught")
        if "bundled-agent-config" not in rows[codex_rel].classes:
            return fail("bundled .codex config.toml not caught")

        mention_text = paths["mention"].read_text(encoding="utf-8")
        mention = neutralise_text(mention_text, "mention-docs/README.md")
        if mention.findings:
            return fail(f"use-versus-mention failed: {mention.findings}")
        if mention.neutralised_text != mention_text:
            return fail("mention document was rewritten")
        if not mention_spans(mention_text):
            return fail("mention-span detector was silent on the documentation fixture")

        for path in paths.values():
            if not path.is_file() or path.stat().st_size <= 0:
                return fail(f"source deleted (not neutralization): {path}")

        for result in rows.values():
            if result.deleted:
                return fail(f"deleted=True on {result.relpath}")
            orig = (src / result.relpath).read_text(encoding="utf-8")
            gated = (dest / result.relpath).read_text(encoding="utf-8")
            o_mechs, o_stages = extract_tokens(orig)
            g_mechs, g_stages = extract_tokens(gated)
            if o_mechs and o_mechs != g_mechs:
                return fail(
                    f"mechanism tokens dropped in {result.relpath}: "
                    f"{o_mechs} -> {g_mechs}"
                )
            if o_stages and o_stages != g_stages:
                return fail(
                    f"stage tokens dropped in {result.relpath}: "
                    f"{o_stages} -> {g_stages}"
                )

        report = {
            "probe": "probe1-payload-classes",
            "unit_id": "WFA-0121",
            "pass": True,
            "caught_classes": sorted(caught),
            "bundled_claude": True,
            "bundled_codex": True,
            "mention_flagged": False,
            "source_files_preserved": True,
            "content_preserved": True,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        print(
            "caught="
            + ",".join(sorted(caught))
            + " mention_silent=True files_kept=True content_kept=True"
        )
        print(
            "SUCCESS:WFA-0121-probe1 planted classes caught; "
            "mention silent; content preserved"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
