from pathlib import Path

p = Path("C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/ARC-0054/emit_failure_modes.py")
text = p.read_text(encoding="utf-8")
SHA = chr(34) + "sha256" + chr(34) + ": " + chr(34) + "149c8f07114e2636b0a3fb7c4677aadb5bec4c4349783cf3ad45d344a4b4104d" + chr(34)
old = "    " + chr(39) + SHA + chr(39)
new = "    " + chr(39) + "     " + SHA + chr(39)
n = text.count(old)
if n != 1:
    print("FAILED:cycle2 match-count=" + str(n))
    raise SystemExit(1)
p.write_text(text.replace(old, new), encoding="utf-8", newline=chr(10))
print("SUCCESS:cycle2 SNIP_A2 pinned to the 5-space occurrence (line 796)")
