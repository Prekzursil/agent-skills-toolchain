"""Splice the new payload section into build_shard4.py + lib report-preservation."""
from pathlib import Path
import ast

W1 = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1"
drv = W1 / "build_shard4.py"
src = drv.read_text(encoding="utf-8")

parts = [p.read_text(encoding="utf-8") for p in sorted((Path(__file__).parent / "parts").glob("p*.txt"))]
NEW = "".join(parts)

MARK = "# --- per-unit payloads (report + residual unknowns) -------------------------"
END = "UNITS = {"
i = src.index(MARK)
j = src.index(END)
old_section = src[i:j]
assert "_cc0022_payload" in old_section and "_cc0011_payload" in old_section
src = src[:i] + NEW + "\n\n" + src[j:]

old_call = "    report_payload, residual_unknowns = UNITS[uid](plan)"
new_call = "    report_payload, residual_unknowns = UNITS[uid](plan, U.load_doc(uid))"
assert old_call in src, "driver call not found"
src = src.replace(old_call, new_call)
drv.write_text(src, encoding="utf-8", newline="\n")
ast.parse(src)

# lib: preserve existing report; None payload keeps it
lib = W1 / "lib_shard4.py"
lsrc = lib.read_text(encoding="utf-8")
old_rep = '''    doc["residual_unknowns"] = residual_unknowns
    doc["report"] = report_payload'''
new_rep = '''    doc["residual_unknowns] = None  # placeholder-removed'''
# real edit below
new_rep = '''    doc["residual_unknowns"] = residual_unknowns
    if report_payload is None:
        _old_rep = ext.get("historical_report") or doc.get("report")
        if isinstance(_old_rep, dict) and _old_rep:
            doc["report"] = _old_rep
    else:
        _prev_rep = doc.get("report")
        if isinstance(_prev_rep, dict) and _prev_rep:
            ext["historical_report"] = _prev_rep
        doc["report"] = report_payload'''
assert old_rep in lsrc, "lib report block not found"
lsrc = lsrc.replace(old_rep, new_rep)
lib.write_text(lsrc, encoding="utf-8", newline="\n")
ast.parse(lsrc)
print("splice OK: build_shard4.py + lib_shard4.py rewritten, syntax valid")
