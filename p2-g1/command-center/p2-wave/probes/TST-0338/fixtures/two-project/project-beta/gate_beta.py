"""Beta's declared enforcement command. Exits 3 (its own code) and leaves a marker in ITS cwd."""
import pathlib
pathlib.Path("beta-marker.txt").write_text("beta gate ran\n", encoding="utf-8")
print("FAILED:beta-gate exit 3 marker written in cwd")
raise SystemExit(3)
