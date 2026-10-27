"""Fix cnf0135_probe1: per-entry semantics (closed/irreducible/refused) + d2 id."""
from pathlib import Path
import ast

un = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1" / "shard4_units.py"
src = un.read_text(encoding="utf-8")

old_loop = '''    for e in entries:
        hist = e.get("history") three-state-placeholder'''
old_loop = '''    for e in entries:
        hist = e.get("history") or []
        pre = [h for h in hist if h.get("event") == "preregistered"]
        closes = [h for h in hist if reassignment-placeholder'''
old_loop = '''    for e in entries:
        hist = e.get("history") or []
        pre = [h for h in hist if h.get("event") == "preregistered"]
        closes = [h for h in hist if h.get("event") == "closed"]
        ok = bool(pre) and bool(closes) and all(
            any(p.get("test_id") == cl.get("test_id") for p in pre) for cl in closes)
        c.check(f"close-preregistered({e.get('claim_id')})", ok)
        c.check(f"close-method-executable({e.get('claim_id')})",
                e.get("close_method") == "executable-test")'''
new_loop = '''    for e in entries:
        hist = e.get("history") or []
        closes = [h for h in entries_placeholder'''
new_loop = '''    for e in entries:
        hist = e.get("history") or []
        closes = [h for h in hist if h.get("event") == "closed"]
        cid = e.get("claim_id")
        if closes:
            pre = [h for h in hist if h.get("event") == "preregistered"]
            ok = bool(pre) and all(
                any(p.get("test_id") == cl.get("test_id") with-placeholder for cl in closes))
            c.check(f"close-preregistered({cid})", ok)
            c.check(f"close-method-executable({cid})",
                    e.get("close_method") == "executable-test")
        elif e.get("close_method") == "irreducible-attestation":
            c.check(f"irreducible-close-representable({cid})",
                    any(h.get("event") == "irreducible" for h in hist))
        else:
            c.check(f"untested-close-refused({cid})",
                    any(h.get("event") == "untested-close-refused" for h in hist)
                    and not closes)'''
new_loop = new_loop.replace(" with-placeholder", "")
new_loop = new_loop.replace(" entries_placeholder", " hist if h.get(\"event\") == \"closed\"]")
un_ok = old_loop in src
assert un_ok, "units: cnf0135 entry loop not found"
src = src.replace(old_loop, new_loop)

old_d2 = '''    d2 = next((e for e in entries if e.get("claim_id") == "SIM-SORT-ORDER"), None)'''
new_d2 = '''    d2 = next((e for e in entries if e.get("claim_id") == "SIM-SORTED-TRIPLET"), None)'''
assert old_d2 in src, "units: d2 id not found"
src = src.replace(old_d2, new_d2)

un.write_text(src, encoding="utf-8", newline="\n")
ast.parse(src)
print("cnf0135 probe1 fixed; syntax valid")
