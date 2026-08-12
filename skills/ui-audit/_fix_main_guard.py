"""Repair the symlink-fragile main-module guard in every ui-audit gate script.

BUG: each gate ends with

    const __filename = fileURLToPath(import.meta.url);
    if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) { main() }

`~/.claude/skills` is a JUNCTION to `~/.claude/skills.daily`. Node resolves symlinks
when it loads an ESM module, so `import.meta.url` reports the REAL path
(.../skills.daily/...), while `resolve(process.argv[1])` is purely lexical and keeps
whatever the caller typed (.../skills/...). The two never match, `main()` never runs,
and the gate exits 0 having produced nothing -- a silent no-op with a success code.

That is exactly how the skill is documented to be invoked ("node
~/.claude/skills/ui-audit/capture.mjs ..."), so every gate was dead on the documented
path. Measured: capture.mjs exited 0 with no output and no artifacts; the identical
command against .../skills.daily/... printed SUCCESS:capture and wrote both files.

FIX: compare REAL paths. `realpathSync.native` is used deliberately over `realpathSync`
because only the native variant also collapses Windows 8.3 short names (PREKZU~1).
Falls back to the old lexical compare if realpath throws, so the guard can never become
*more* broken than it already was.

Byte-safe I/O: read_bytes/write_bytes, since a text round-trip rewrites LF as CRLF on
Windows and would churn every line of all seven files.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

OLD = ("if (process.argv[1] && resolve(process.argv[1]) === resolve(__filename)) {")

NEW = """// Junction/symlink-safe main-module check. `~/.claude/skills` is a junction to
// `skills.daily`; Node resolves symlinks for ESM so import.meta.url reports the REAL
// path while resolve(argv[1]) stays lexical. A lexical compare therefore NEVER matched
// on the documented `~/.claude/skills/...` invocation and main() silently never ran
// (exit 0, no output, no artifacts). realpathSync.native also collapses 8.3 short
// names (PREKZU~1), which realpathSync does not.
const __isMain = (a, b) => {
  try { return realpathSync.native(a) === realpathSync.native(b); }
  catch { return resolve(a) === resolve(b); }
};
if (process.argv[1] && __isMain(process.argv[1], __filename)) {"""

IMPORT_LINE = "import { realpathSync } from 'node:fs';\n"


def needs_import(text):
    return "realpathSync" not in text.split(OLD)[0]


def insert_import(text):
    """Put the fs import next to the existing node: imports, else at the top."""
    lines = text.split("\n")
    last_import = -1
    for i, ln in enumerate(lines):
        if ln.startswith("import ") and ";" in ln:
            last_import = i
    if last_import == -1:
        return IMPORT_LINE + text
    lines.insert(last_import + 1, IMPORT_LINE.rstrip("\n"))
    return "\n".join(lines)


def main():
    patched, skipped = [], []
    for p in sorted(HERE.glob("*.mjs")):
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        if OLD not in text:
            skipped.append((p.name, "guard not found"))
            continue
        out = text.replace(OLD, NEW)
        if needs_import(out):
            out = insert_import(out)
        p.write_bytes(out.encode("utf-8"))
        patched.append(p.name)
    print(f"patched {len(patched)}: {', '.join(patched)}")
    for n, why in skipped:
        print(f"  skipped {n}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
