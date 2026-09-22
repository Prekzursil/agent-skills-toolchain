# Fresh-context reviewer documentary mention (CC-0006)

Independent review note — text the detector author never saw. This is a
documentary mention of the platform-wrong verification recipe, written to
confirm use-vs-mention stays SILENT when the identical classic string is
quoted under forbid framing.

Independent reviewers: DO NOT USE `git archive` when you need the real
repository bytes for formatter or linter checks. A checklist line that told
operators to verify formatting against the **LF blob** (`git archive`) was WRONG
on this estate: export-time EOL conversion hands back CRLF, which is the
opposite of `git cat-file -p` / `git show <rev>:<path>` / blobread. Prefer those
helpers; treat any remaining `git archive` LF-blob prescription as a live
defect class to extinguish, not a procedure to follow.
