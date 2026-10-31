"""Fix PLUGIN-METADATA-OR-IMPLEMENTATION-CHANGED to require real metadata change."""
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\REL-0001\release_bump_linter.py")
t = p.read_text(encoding="utf-8")

old = (
    '    if (not (ok - nk)) and (not (nk - ok)) and op == np_ and oh == nh \\\n'
    '            and not changed_values:\n'
    '        yield ("PLUGIN-METADATA-OR-IMPLEMENTATION-CHANGED", "PATCH",\n'
    '               "only metadata or implementation bytes changed")'
)
new = (
    '    # w4s12 fix (part of the D1-D3 max-rank repair): this rule previously\n'
    '    # fired on ANY structurally-unchanged diff - including ZERO change - so a\n'
    '    # byte-identical rename classified PATCH once max-rank derivation stopped\n'
    '    # masking it. Fire only when manifest metadata (META_KEYS) really changed.\n'
    '    om_meta = {k: old[k] for k in sorted(set(old) & META_KEYS)}\n'
    '    nm_meta = {k: new[k] for k in sorted(set(new) & META_KEYS)}\n'
    '    meta_changed = om_meta != nm_meta\n'
    '    if meta_changed and (not (ok - nk)) and (not (nk - ok)) and op == np_ \\\n'
    '            and oh == nh and not changed_values:\n'
    '        touched = ",".join(sorted(\n'
    '            k for k in set(om_meta) | set(nm_meta)\n'
    '            if om_meta.get(k) != nm_meta.get(k)))\n'
    '        yield ("PLUGIN-METADATA-OR-IMPLEMENTATION-CHANGED", "PATCH",\n'
    '               "manifest metadata changed (structural contract unchanged): " + touched)'
)
assert old in t, "metadata rule block not found"
t = t.replace(old, new)
p.write_text(t, encoding="utf-8", newline="\n")
print("PATCHED", p)
print("DONE")
