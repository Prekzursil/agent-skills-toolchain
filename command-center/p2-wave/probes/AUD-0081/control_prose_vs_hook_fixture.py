#!/usr/bin/env python3
"""AUD-0081 tests_required control.

Catalog text (verbatim): "control: the classifier must rate an AGENTS.md
containing only prose as inert and one registering a PreToolUse command
as active; assert both on one fixture."

This writes ONE fixture file path, toggles its CONTENT between two
states, and calls _autoload_classifier.classify_hit -- the SAME function
probe 2 uses on real hits, not a reimplementation:

  * bad state (for THIS control, "bad" means "the state the classifier
    must NOT call active"): prose-only AGENTS.md content -> must classify
    "inert".
  * good state: the SAME file path, rewritten to contain a JSON
    "hooks": {"PreToolUse": [...]} registration block -> must classify
    "active".

Both-states semantics for negative_control.fired_on_bad_state /
silent_on_good_state (per platform/schema/receipt.schema.json's
$defs/negative_control): here "fired" means "correctly did NOT call it
active" on the prose-only state, and "silent" means "did NOT incorrectly
call the hook-registering state inert". A negative control fixture
(naive substring-only classifier that flags ANY file containing the
literal word "hooks" as active, ignoring JSON structure) is included so
this control is proven falsifiable rather than vacuously true.

Uses a real temp file on disk (tempfile), never a hand-simulated string,
so the classifier's actual Path.read_text() code path is exercised.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _autoload_classifier as C  # noqa: E402

OUT_JSON = Path(__file__).resolve().parent / "control-prose-vs-hook-fixture.json"
OUT_RAW = Path(__file__).resolve().parent / "control-prose-vs-hook-fixture.raw.txt"

PROSE_ONLY_CONTENT = """# AGENTS.md

This repository contains guidance for coding agents. Please read the
project's README before making changes. Follow existing conventions,
write tests for new code, and keep commits small and focused.

There is no automation registered by this file. It is documentation only.
"""

ACTIVE_HOOK_CONTENT = """# AGENTS.md

This repository contains guidance for coding agents.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "echo pre-tool-use-fired"}]
      }
    ]
  }
}
```
"""


def naive_substring_classifier(text: str) -> str:
    """The known-broken stand-in this control must catch: flags ANY
    content containing the literal word 'hooks' as active, ignoring JSON
    structure entirely -- exactly the false-positive class the catalog's
    'presence alone is not a risk finding' caution warns against."""
    return "active" if "hooks" in text.lower() else "inert"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with tempfile.TemporaryDirectory(prefix="aud0081-control-") as tmpdir:
        fixture_path = Path(tmpdir) / "AGENTS.md"

        fixture_path.write_text(PROSE_ONLY_CONTENT, encoding="utf-8")
        prose_result = C.classify_hit(fixture_path, "AGENTS.md", "file")
        prose_naive = naive_substring_classifier(fixture_path.read_text(encoding="utf-8"))

        fixture_path.write_text(ACTIVE_HOOK_CONTENT, encoding="utf-8")
        hook_result = C.classify_hit(fixture_path, "AGENTS.md", "file")
        hook_naive = naive_substring_classifier(fixture_path.read_text(encoding="utf-8"))

    prose_is_inert = prose_result["classification"] == "inert"
    hook_is_active = hook_result["classification"] == "active"
    real_classifier_passes_control = prose_is_inert and hook_is_active

    # naive classifier's failure mode: it says "active" for the PROSE-ONLY
    # state too, because the control's own second sentence ("There is no
    # automation registered by this file") happens to contain the word
    # "hook"-adjacent text? No -- use a distinct false-positive fixture so
    # the naive classifier's failure is genuine, not a coincidence of this
    # particular prose fixture's wording.
    naive_false_positive_fixture = (
        "# AGENTS.md\n\nThis project uses git hooks for linting. See "
        "scripts/setup-hooks.sh for details.\n"
    )
    naive_false_positive_result = naive_substring_classifier(naive_false_positive_fixture)
    real_classifier_on_same_fixture = C.classify_text_content(naive_false_positive_fixture)
    naive_incorrectly_flags_mention_as_active = naive_false_positive_result == "active"
    real_correctly_rates_mention_as_inert = real_classifier_on_same_fixture[0] == "inert"

    fired_on_bad_state = prose_is_inert  # correctly did NOT call prose-only "active"
    silent_on_good_state = hook_is_active  # correctly did NOT call the real registration "inert"

    out = {
        "ok": bool(real_classifier_passes_control and naive_incorrectly_flags_mention_as_active and real_correctly_rates_mention_as_inert),
        "started_at": started,
        "fixture_path_used_for_both_states": "AGENTS.md (single temp file, content toggled)",
        "prose_only_state": {
            "content_sha256_len": len(PROSE_ONLY_CONTENT),
            "classification": prose_result["classification"],
            "reason": prose_result["reason"],
            "correctly_inert": prose_is_inert,
            "naive_substring_classifier_result": prose_naive,
        },
        "active_hook_state": {
            "content_sha256_len": len(ACTIVE_HOOK_CONTENT),
            "classification": hook_result["classification"],
            "reason": hook_result["reason"],
            "correctly_active": hook_is_active,
            "naive_substring_classifier_result": hook_naive,
        },
        "real_classifier_passes_control": real_classifier_passes_control,
        "mention_only_false_positive_fixture": {
            "content": naive_false_positive_fixture,
            "naive_substring_classifier_result": naive_false_positive_result,
            "naive_incorrectly_flags_mention_as_active": naive_incorrectly_flags_mention_as_active,
            "real_classifier_result": real_classifier_on_same_fixture[0],
            "real_classifier_reason": real_classifier_on_same_fixture[1],
            "real_correctly_rates_mention_as_inert": real_correctly_rates_mention_as_inert,
        },
        "fired_on_bad_state": fired_on_bad_state,
        "silent_on_good_state": silent_on_good_state,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0081-control" if out["ok"] else "FAILED:AUD-0081-control",
        "unit=AUD-0081 control=prose-vs-hook-fixture (single fixture, two states)",
        f"prose_only_state.classification={prose_result['classification']} "
        f"(want inert) correctly_inert={prose_is_inert}",
        f"active_hook_state.classification={hook_result['classification']} "
        f"(want active) correctly_active={hook_is_active}",
        f"real_classifier_passes_control={real_classifier_passes_control}",
        f"naive_substring_classifier: prose={prose_naive} hook={hook_naive} "
        "(informational only; the naive matcher's real false-positive "
        "failure mode is demonstrated below on a DIFFERENT fixture)",
        f"mention_only_false_positive_fixture.naive_result={naive_false_positive_result} "
        f"(naive_incorrectly_flags_mention_as_active={naive_incorrectly_flags_mention_as_active})",
        f"mention_only_false_positive_fixture.real_result={real_classifier_on_same_fixture[0]} "
        f"(real_correctly_rates_mention_as_inert={real_correctly_rates_mention_as_inert})",
        f"all_ok={out['ok']}",
    ]
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
