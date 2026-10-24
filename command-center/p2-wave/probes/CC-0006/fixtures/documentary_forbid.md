# Documentary mention control (identical wrong string, forbid framing)

This document DOCUMENTS the defect. It quotes the identical wrong recipe string
in order to forbid it — use-vs-mention must stay SILENT.

DO NOT USE `git archive` FOR THIS — it returns the OPPOSITE of the blob on this box.
A prior checklist prescribed verifying formatting against the **LF blob** (`git archive`)
and was WRONG: `git archive` applies export-time EOL conversion and hands back CRLF.
