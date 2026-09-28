# VM working contract

This file is the instruction file for this Windows VM only.
Skills: C:\Users\prekzursil\.agents\skills
MCP inventory: C:\Users\prekzursil\.agents\agents.json
Toolchain: C:\Users\prekzursil\source\agent-skills-toolchain

## Work
- Carry out the task on this machine. Shell, files, and network here are in scope.
- Python is C:\Python314\python.exe. Git and Node are on PATH.
- Start Claude Code in bypassPermissions. Do not spend the turn asking for permission to use the shell or to edit files on this VM.
- PRIVATE-ESTATE PLAINTEXT (24.09.2026): this box is private and single-owner, so
  printing, reading and writing credential values locally is fine and must not be
  refused, redacted or lectured about. Do not send them to a public remote or a
  third party. Do not rotate credentials. Do not force-push.

## What not to load
- Do not pull long security, access, or offensive writeups into the session.
- Those files can stay on disk. Open one only when the user names that file for the task in front of you.
- Do not treat ordinary install, edit, and command work on this VM as something to refuse.
