"""Both-states control for todo-surfacer's marker count.

RUN THIS AGAINST THE UNFIXED HOOK FIRST. The KNOWN-BROKEN cases below must FAIL before the fix
and pass after; the KNOWN-GOOD cases must pass in BOTH states. A test suite that is green in both
states measures nothing, and this hook's whole defect class is detectors that cannot tell a use
from a mention.

Why this exists: the hook counted markers with a raw regex, so a message *discussing* markers
false-fired. Measured live 2026-08-08 -- and the terminal case is that the hook fires on its OWN
NAME, because "todo-surfacer" contains "todo" followed by a word boundary. That makes the defect
self-sustaining: the defect cannot be described without triggering it.

The fix must be NARROW. The tempting move -- routing through the shared discriminator with
kind="marker" -- inverts the polarity for prose and would silence this hook's own documented
fire_example, trading a false positive for a false NEGATIVE. A silently disarmed guard is worse
than a noisy one, so FIRE_CASES are the load-bearing half of this file.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HOOK = pathlib.Path(__file__).resolve().parent / "hook.py"
spec = importlib.util.spec_from_file_location("todo_surfacer_hook", HOOK)
mod = importlib.util.module_from_spec(spec)
sys.modules["todo_surfacer_hook"] = mod
spec.loader.exec_module(mod)

count = getattr(mod, "_real_marker_count", None)
if count is None:  # unfixed hook: emulate the raw path so the control is meaningful
    def count(text):
        return len(list(mod._PATTERN.finditer(text)))

# MUST FIRE. These are real leftover work. Silencing any of these is a REGRESSION and is
# strictly worse than the false positives this fix targets.
FIRE_CASES = [
    ("spec.json fire_example", "Remaining: TODO wire the API; FIXME handle empty. - [ ] ship it", 3),
    ("bare todo in prose", "TODO: wire this up before merging.", 1),
    ("fixme in a sentence", "FIXME the empty-input path throws.", 1),
    ("unchecked box", "- [ ] ship it", 1),
    ("fenced real marker", "Left in the patch:\n```python\n# TODO implement\n```", 1),
]

# MUST STAY SILENT. Each is a MENTION -- the text discusses a marker rather than leaving one.
SILENT_CASES = [
    ("spec.json silent_example", "All done. Everything shipped and verified."),
    ("the hook's own name", "I patched todo-surfacer and the todo-surfacer defect is closed."),
    ("hyphenated identifier", "See todo-surfacer/hook.py and the fixme-scanner module."),
    ("inline code span", "The fixture is `# TODO` inside a string literal, not a comment."),
    ("quoted marker in prose", "It matched a quoted `TODO` while explaining use-vs-mention."),
]

fails = []
print("=== MUST FIRE (regression guard) ===")
for name, text, want in FIRE_CASES:
    got = count(text)
    ok = got >= 1
    print(f"  {'PASS' if ok else 'FAIL'}  {name:26s} count={got} (want >=1, ideally {want})")
    if not ok:
        fails.append(f"REGRESSION: '{name}' went silent -- the guard was disarmed")

print("\n=== MUST STAY SILENT (the false positives) ===")
for name, text in SILENT_CASES:
    got = count(text)
    ok = got == 0
    print(f"  {'PASS' if ok else 'FAIL'}  {name:26s} count={got} (want 0)")
    if not ok:
        fails.append(f"FALSE POSITIVE: '{name}' fired {got}x")

print()
if fails:
    for f in fails:
        print(f"  {f}")
    print(f"\nFAILED:todo-surfacer-discrimination {len(fails)} case(s)")
    raise SystemExit(1)
print("SUCCESS:todo-surfacer-discrimination real markers still fire, mentions stay silent")
