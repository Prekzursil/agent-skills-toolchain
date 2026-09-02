# Scratch Phase 12 threat model (control fixture, not a live artifact)

This fixture exists so the UNMODELED control can delete one actor from a
copy and require the classifier to flip that row. It is not registered as a
Phase 12 output_path.

## malicious package publisher
The malicious package publisher ships a plugin that requests undeclared
tools. A typosquat of a popular id is in scope.

## compromised upstream dependency
A compromised upstream dependency (dependency confusion / poisoned
dependency) lands in the lockfile after a registry race.

## hostile marketplace mirror
A hostile marketplace mirror (MITM marketplace / tampered mirror) serves
a payload whose digest does not match the signed catalog.

## malicious workflow / skill contributor
A malicious workflow and a malicious skill contributor (hostile skill)
inject a post-merge hook.

## prompt-injecting artifact author
A prompt-injecting artifact author uses indirect prompt injection so later
stages treat untrusted DATA as instructions.

## compromised or misaligned agent inside our own fan-out
A compromised or misaligned agent inside our own fan-out (operator's own
agent / insider agent) can stage a sibling's files because agents share one
git index. Omitting the operator's own agent makes the model incomplete
by construction.

## curious insider reading artifacts
A curious insider reading artifacts (curious operator) dumps receipts and
transcripts from a shared worktree.

## the host-client vendor itself
The host-client vendor itself (host-application vendor / platform vendor
itself) can rewrite tool results before our code sees them.

## local malware with user-level file access
Local malware with user-level file access reads `accounts.json` and the
session store without elevation.

## thief holding a stale credential
A thief holding a stale credential (stolen token / credential thief)
replays a CI token that was never rotated.
