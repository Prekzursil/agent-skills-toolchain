# Upstream notes — vuln-research-loop

All tools are **installed on the host and wrapped**, never vendored into this
repo. Use only on code/binaries you own or are explicitly licensed to test.
Prefer permissive-licensed engines (G17). Configure secrets/paths by env NAME.

## Method / framing

- Naptime — Project Zero, "Project Naptime: Evaluating Offensive Security
  Capabilities of Large Language Models" (`https://googleprojectzero.blogspot.com/2024/06/project-naptime.html`).
- Big Sleep — follow-on agentic bug-finding
  (`https://googleprojectzero.blogspot.com/2025/07/from-naptime-to-big-sleep.html`).
  This skill adapts the *find-and-fix* loop only; it does not adopt any
  exploitation step.

## Coverage-guided fuzzers

- ClusterFuzzLite — `https://google.github.io/clusterfuzzlite/` (CI fuzzing;
  runs your libFuzzer/AFL++ harnesses on PRs + batch).
- Atheris — `https://github.com/google/atheris` (Python/libFuzzer;
  `pip install atheris`). Fuzz your own Python and MCP-server surfaces.
- libFuzzer / AFL++ / LibAFL — the actual engines; build + sanitizer recipes live
  in the `$native-fuzz` skill, not here.

## Crash triage

- CASR — `https://github.com/ispras/casr` (Crash Analysis and Severity Report;
  `casr-san`, `casr-gdb`, `casr-libfuzzer`, `casr-dedup`, `casr-cluster`).
  Used for deduplication + defect-severity prioritization only.

## Harness synthesis

- OSS-Fuzz-Gen — `https://github.com/google/oss-fuzz-gen` (LLM-assisted fuzz
  harness generation). Review generated harnesses before running.

## Windows closed-source (owner-owned binaries only)

- Jackalope — `https://github.com/googleprojectzero/Jackalope` (distributed
  coverage-guided fuzzer for black-box binaries).
- TinyInst — `https://github.com/googleprojectzero/TinyInst` (lightweight dynamic
  instrumentation, DynamoRIO-family) used as Jackalope's coverage source.

## Patch-diff / variant hunting

- ghidriff — headless Ghidra diff to markdown; driven via `$malware-analysis-triage`.
- BinDiff / BinExport — driven via `$bindiff` and `$binexport`.

## Sanitizers

- ASan / UBSan / MSan build flags and `go test -fuzz` discipline: see the
  `$native-fuzz` skill (parent/W-upgrades owned). Do not duplicate here.
