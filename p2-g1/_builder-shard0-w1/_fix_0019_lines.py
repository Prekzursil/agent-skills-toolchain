"""Line-indexed fixer for the two quoting-broken lines in probe2_second_resolver.py."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0019/probe2_second_resolver.py"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

fixed = 0
for i, line in enumerate(lines):
    if line.lstrip().startswith("+ '; do loc="):
        # bash fragment: ; do loc=$(command -v -- "$n" 2>/dev/null) && printf '%s\t%s\n' "$n" "$loc"; done
        # with LITERAL backslash-t / backslash-n for printf; composed without any
        # backslash characters in this source file.
        lines[i] = (
            '        + "; do loc=$(command -v -- " '
            '+ chr(34) + "$n" + chr(34) '
            '+ " 2>/dev/null) && printf " '
            "+ chr(39) + \"%s\" + chr(92) + \"t%s\" + chr(92) + \"n\" + chr(39) "
            '+ " " + chr(34) + "$n" + chr(34) + " " + chr(34) + "$loc" + chr(34) '
            '+ "; done"\n'
        )
        fixed += 1
    if "Write-Output ($n +" in line:
        # PowerShell: tab as [char]9, no embedded double quotes needed.
        lines[i] = (
            '        "Write-Output ($n + [string][char]9 + $s) } }"\n'
        )
        fixed += 1

p.write_text("".join(lines), encoding="utf-8")
print("fixed lines:", fixed)
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("syntax OK")
