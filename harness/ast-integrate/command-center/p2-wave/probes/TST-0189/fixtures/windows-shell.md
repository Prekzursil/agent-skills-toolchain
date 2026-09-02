# windows-shell.md (TST-0189 regression-seed fixture)

1. Quote revision arguments that contain a caret.
2. Never emit a bare caret under PowerShell.
3. Generated shell scripts are LF-terminated.
4. Route apostrophe-bearing prose through a file, never a command line.
5. Scope MSYS path conversion to revision-shaped arguments.
6. Pass argv as arrays; do not concatenate launcher strings.
7. Prefer a write API over interpolating payload into a shell.
8. Do not use a here-string to materialize a file.
9. A here-string PAYLOAD is scanned as a command: quoting Remove-Item inside @' ... '@ still sits in the script text, so scanners and the parser treat it as code. Write the bytes through a file API instead.
10. Apostrophes break the tool's own quoting when inlined.
