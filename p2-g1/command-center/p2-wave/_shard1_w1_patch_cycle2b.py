from pathlib import Path

p = Path("C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/ARC-0055/emit_security.py")
text = p.read_text(encoding="utf-8")
Q = chr(34)
S = chr(39)
old1 = Q + "One generated JSON file per marketplace_entry." + Q
new1 = S + "     " + Q + "notes" + Q + ": " + Q + "One generated JSON file per marketplace_entry." + Q + S
old2 = S + Q + "architecture_name" + Q + ": " + Q + "generated-ssot" + Q + S
new2 = S + "   " + Q + "architecture_class" + Q + ": " + Q + "generated-ssot" + Q + S
for tag, old, new in (("opt1", old1, new1), ("opt2", old2, new2)):
    n = text.count(old)
    if n != 1:
        print("FAILED:cycle2b " + tag + " match-count=" + str(n))
        raise SystemExit(1)
    text = text.replace(old, new)
    print("patched " + tag)
p.write_text(text, encoding="utf-8", newline=chr(10))
print("SUCCESS:cycle2b ARC-0055 emitter anchors pinned to estate-unique lines")
