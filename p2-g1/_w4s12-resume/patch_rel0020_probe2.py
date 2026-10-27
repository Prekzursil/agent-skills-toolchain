"""REL-0020 probe2: read the isolation-profile facts from the preserved
extensions location (receipt_core profile is a string slug since the
2026-10-26 w4s12 envelope normalization; the dict moved verbatim)."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\REL-0020\probe2_version_trap.py")
t = p.read_text(encoding="utf-8")

old = ('        profile = rec.get("profile") or {}\n'
       '        if profile.get("fresh_per_attempt") is not True or profile.get("destroyed_after") is not True:\n'
       '            return fail("receipt-profile-drift")')
new = ('        # w4s12: receipt_core.profile is a string slug; the isolation-profile\n'
       '        # facts moved verbatim to extensions.execution_profile_preserved\n'
       '        profile = rec.get("profile")\n'
       '        if not isinstance(profile, dict):\n'
       '            profile = (rec.get("extensions") or {}).get("execution_profile_preserved") or {}\n'
       '        if profile.get("fresh_per_attempt") is not True or profile.get("destroyed_after") is not True:\n'
       '            return fail("receipt-profile-drift")')

assert old in t, "profile pin block not found"
t = t.replace(old, new)
p.write_text(t, encoding="utf-8", newline="\n")
print("PATCHED", p)
print("DONE")
