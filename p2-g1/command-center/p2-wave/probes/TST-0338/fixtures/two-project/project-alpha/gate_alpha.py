"""Alpha's declared enforcement command. Exits 0 and leaves a marker in ITS cwd."""
import pathlib
pathlib.Path("alpha-marker.txt").write_text("alpha gate ran\n", encoding="utf-8")
print("SUCCESS:alpha-gate exit 0 marker written in cwd")
