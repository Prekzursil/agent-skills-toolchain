"""Insert a REFUTED-IN-ROUND-3 banner at the top of the round-1 and round-2 reports.

Recording the refutation rather than deleting the wording is the point: a reader who lands on the
older report must see, before the first claim, which sentences round 3 disproved. Idempotent -- it
refuses to insert a second copy.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
MARK = "REFUTED IN ROUND 3"

BANNER = """
> ## REFUTED IN ROUND 3 — read this before citing anything below
>
> An adversarial verifier executed the round-2 fix and broke it, and I reproduced both defects with
> its own probes (`command-center/p2-wave/_av2_tmp/`) before changing a line:
>
> 1. **The vacuous-contract fallback was a ONE-KEY bypass.** `looks_like_schema_doc` checked for a
>    `$schema`/`$id` key plus `check_schema`, and `check_schema` accepts unknown keywords — so
>    adding one key to arbitrary garbage returned `delivered=True`, including for a bare
>    `{"$schema": ...}` of 59 bytes and for a 2,000-x blob. `BYPASS_PROVEN = True`. 23 units declare
>    a contract that cannot fail and were one key from a false green.
> 2. **The control shipped with that fix was silent in both states.** Its docstring claimed
>    two-sidedness against `{"type": 123, "required": "not-an-array"}` — a document carrying neither
>    key, so the KEY check rejected it and `check_schema` was never exercised by the control at all.
> 3. **Every non-`.json` artifact skipped the gate entirely** (`return True, "non-json-present"`),
>    so a 2,000-x file named `.md` was DELIVERED while the identical bytes named `.json` were
>    rejected. 120 units sit behind that branch — 0 of their artifacts exist, so the hole was latent
>    and no delivered count was ever wrong because of it.
> 4. **"Each delivered unit executable-proven against its declared contract" was wider than its
>    evidence.** IMP-0433's declared contract is a meta-schema that accepts arbitrary JSON, measured
>    0/12 garbage documents rejected. Its receipt is proven against `receipt.schema.json`, which is
>    discriminating — but NOT against the contract its own catalog row names.
>
> All four are fixed or correctly re-scoped in
> [`P2-BUILD-ROUND3.md`](P2-BUILD-ROUND3.md). The wording above is left in place deliberately.

"""

for name in ("P2-BUILD-ROUND1.md", "P2-BUILD-ROUND2.md"):
    p = REPO / "command-center/p2-wave" / name
    text = p.read_text(encoding="utf-8")
    if MARK in text:
        print(f"  {name}: banner already present, not duplicated")
        continue
    lines = text.split("\n")
    out = "\n".join([lines[0], BANNER.rstrip("\n"), ""] + lines[1:])
    p.write_text(out, encoding="utf-8", newline="\n")
    print(f"  {name}: banner inserted after line 1 ({p.stat().st_size} B)")

print("SUCCESS:r3-annotate")
