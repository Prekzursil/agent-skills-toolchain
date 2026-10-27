"""Resume patch 1/3: lib_shard4.py (unit_id, prev-closure reasons, NC merge)."""
from pathlib import Path

W1 = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1"
lib = W1 / "lib_shard4.py"
src = lib.read_text(encoding="utf-8")

old_reason = '''                "reason": ("prior closure's reviewer is this unit's own probe (self-certification, "
                           "no vendor/fresh-context) and its named probe files are absent from this "
                           "worktree; per receipt_core only an independent reviewer may close"),'''
new_reason = '''                "reason": PREV_CLOSURE_REASONS.get(
                    uid,
                    "prior closure's reviewer is this unit's own probe (self-certification, "
                    "no vendor/fresh-context) and its named probe files are absent from this "
                    "worktree; per receipt_core only an independent reviewer may close"),'''
assert old_reason in src, "lib: reason block not found"
src = src.replace(old_reason, new_reason)

anchor = 'NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}'
assert anchor in src, "lib: anchor not found"
lib_add = anchor + '''


# Resume 2026-10-24: per-unit, truthful reason strings for preserving a prior
# closure. Units whose prior reviewer was the unit's own probe get the default
# self-certification text; units with a genuine cross-vendor closure that no
# longer verifies live get an explicit why.
PREV_CLOSURE_REASONS = {
    "BLD-0052": (
        "prior openai/gpt-5.2 C5 closure (2026-08-21) preserved verbatim: it can no longer "
        "verify live - the receipt carries an open P1 defect (plugin-uninstall purge UNARMED "
        "on shipped Python 3.10) and a FAILED sentinel documenting condition-11 live-red, "
        "and receipt_core forbids state=SUCCESS in that state; the independent reviewer "
        "re-closes from the preserved closure."),
    "BLD-0057": (
        "prior openai/gpt-5.2 C5 closure (2026-08-21) preserved verbatim: it can no longer "
        "verify live - the receipt carries an open P1 defect (live R2E scheduler has no "
        "pre-spawn commit/process/handle guard) and lacked downstream_consumers and "
        "manifest_registration; receipt_core forbids state=SUCCESS; the independent "
        "reviewer re-closes from the preserved closure."),
    "CC-0011": (
        "prior openai/gpt-5.2 C5 closure (2026-08-21) preserved verbatim: it can no longer "
        "verify live - the receipt carries an open P0 defect (ten distinct plaintext "
        "credentials reachable in git history and command-center copies; rotation is the "
        "owner's action and has not happened) and a FAILED sentinel documenting "
        "condition-11 live-red; receipt_core forbids state=SUCCESS; the independent "
        "reviewer re-closes from the preserved closure."),
}'''
src = src.replace(anchor, lib_add)

old_uid = '''    doc.setdefault("schema_version", 1)'''
new_uid = '''    doc.setdefault("schema_version", 1)
    doc.setdefault("unit_id", uid)'''
assert old_uid in src, "lib: schema_version anchor not found"
src = src.replace(old_uid, new_uid)

old_nc = '''    doc["tests"] = extra_tests
    doc["negative_controls"] = neg_controls'''
new_nc = '''    doc["tests"] = extra_tests
    # Resume 2026-10-24: MERGE recorded negative controls instead of dropping
    # them - probes assert specific legacy rows (e.g. NC-DISABLED-GUARD on
    # BLD-0057). Only schema-valid legacy rows survive the merge; everything
    # else remains in extensions.historical_negative_controls.
    _NC_KEYS = {"id", "kind", "description", "fired_on_bad_state", "silent_on_good_state",
                "bad_state_output", "good_state_output"}
    _NC_KINDS = {"mutation", "malformed-input", "known-broken-fixture", "absent-input",
                 "adversarial-payload", "other"}
    _old_nc = [
        r for r in (ext.get("historical_negative_controls") or [])
        if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("id")
        and r.get("kind") in _NC_KINDS
        and r.get("fired_on_bad_state") is True and r.get("silent_on_good_state") is True
        and set(r.keys()) <= _NC_KEYS
    ]
    _seen_nc = {r.get("id") for r in neg_controls if isinstance(r, dict)}
    doc["negative_controls"] = list(neg_controls) + [
        r for r in _old_nc if r.get("id") not in _seen_nc]'''
assert old_nc in src, "lib: negative_controls block not found"
src = src.replace(old_nc, new_nc)
lib.write_text(src, encoding="utf-8", newline="\n")
print("patched lib_shard4.py OK")
