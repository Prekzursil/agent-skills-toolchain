---
name: native-fuzz
description: "Use when writing or running coverage-guided fuzz targets (go test -fuzz, libFuzzer / LibAFL) or building with AddressSanitizer / UBSan / MSan to find memory-safety and undefined-behavior bugs in your OWN code. Not for fuzzing third-party targets you do not own and not for exploit development."
---

# native-fuzz — coverage-guided fuzzing + sanitizer build discipline

Coverage-guided fuzzing plus sanitizer instrumentation is the fastest way to
find memory-safety, undefined-behavior, and parser bugs in native and Go code
*before* an attacker does. This skill promotes the fuzzing and sanitizer
discipline out of the library testing skills (`.agents/library/skills/golang-testing`
`go test -fuzz` section and `.agents/library/skills/cpp-testing` sanitizers
section) into a live, security-facing workflow.

**Framing:** own-code / own-binaries / authorized targets only. The output is a
crash, a corpus, and a fix — **never** an exploit. For crash triage,
exploitability scoring, and CI fuzzing orchestration escalate to
`$vuln-research-loop`; for disassembly of a crashing binary use
`$reverse-engineering-toolkit`.

## When to use

- Adding a fuzz target to a parser, decoder, deserializer, or any function that
  takes untrusted bytes.
- Hardening a native (C/C++/Rust FFI) component with sanitizer builds.
- Turning a one-off crash into a permanent regression case.
- Building the executable half of a **differential** review (feed the same input
  to two implementations and assert equal output — see `$security-review`
  Stage 2).

## When NOT to use

- Fuzzing a target you do not own or are not authorized to test.
- Writing exploits / PoCs from a crash (out of scope — hard ban).
- CI fuzzing-service orchestration (ClusterFuzzLite, OSS-Fuzz-Gen, Atheris,
  CASR) — that is `$vuln-research-loop`; this skill is the local build discipline
  it builds on.

## Go — `go test -fuzz` (built in, 1.18+)

Native, no external engine. A `FuzzXxx(f *testing.F)` seeds a corpus and asserts
a property on random inputs.

```go
func FuzzParseConfig(f *testing.F) {
    f.Add([]byte(`{"port":8080}`)) // seed corpus
    f.Add([]byte(`{}`))
    f.Fuzz(func(t *testing.T, in []byte) {
        cfg, err := ParseConfig(in)
        if err != nil {
            return // rejecting bad input is fine
        }
        // property: parse → serialize → parse round-trips
        out, err := json.Marshal(cfg)
        if err != nil {
            t.Fatalf("marshal after successful parse: %v", err)
        }
        if _, err := ParseConfig(out); err != nil {
            t.Fatalf("re-parse of own output failed: %v", err)
        }
    })
}
```

```bash
go test -fuzz=FuzzParseConfig -fuzztime=30s ./...   # fuzz for 30s
go test -run=FuzzParseConfig ./...                  # replay saved crashers (no -fuzz)
go test -fuzz=FuzzParseConfig -race -fuzztime=60s ./...  # + race detector
```

Discipline:

- A failing input is written to `testdata/fuzz/FuzzParseConfig/` — **commit it**.
  It becomes a permanent regression case that plain `go test` (no `-fuzz`)
  replays forever.
- Assert *properties* (round-trip, invariants, no-panic), not fixed outputs, so
  the fuzzer has room to find surprises.
- Only one `FuzzXxx` can run per `-fuzz` invocation; keep targets small and
  focused.

## C / C++ — libFuzzer harness

A libFuzzer target is one function; the engine drives coverage-guided mutation.

```c
#include <stdint.h>
#include <stddef.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    parse_packet(data, size); // your code; must not crash on any input
    return 0;
}
```

```bash
# build with the fuzzer engine + sanitizers in one shot
clang -g -O1 -fsanitize=fuzzer,address,undefined harness.c parse_packet.c -o fuzz
./fuzz corpus/ -max_total_time=60          # run 60s over a seed corpus dir
./fuzz -minimize_crash=1 -runs=100000 crash-input   # shrink a reproducer
```

- `-fsanitize=fuzzer-no-link` compiles a target that links into an existing
  build; add `LLVMFuzzerInitialize` for one-time setup.
- Seed the `corpus/` directory with valid sample inputs — coverage grows far
  faster from real seeds.

## Sanitizer build discipline (ASan / UBSan / MSan / TSan)

Sanitizers are the detectors; the fuzzer is the driver. Build with them even for
normal test runs.

| Sanitizer | Catches | Key flags | Notes |
|-----------|---------|-----------|-------|
| **ASan** | heap/stack overflow, use-after-free, leaks | `-fsanitize=address -fno-omit-frame-pointer` | `ASAN_OPTIONS=detect_leaks=1`; pairs with UBSan |
| **UBSan** | integer overflow, misaligned access, other UB | `-fsanitize=undefined -fno-sanitize-recover=all` | `-fno-sanitize-recover=all` makes UB abort (fuzzable); pairs with ASan |
| **MSan** | reads of uninitialized memory | `-fsanitize=memory -fno-omit-frame-pointer` | clang-only; needs **all** deps (incl. libc++) instrumented; **mutually exclusive with ASan** |
| **TSan** | data races | `-fsanitize=thread` | separate build; cannot combine with ASan/MSan |

Discipline:

- Standard fuzz build = **ASan + UBSan together** (`-fsanitize=fuzzer,address,undefined`).
- Run **MSan** and **TSan** as *separate* builds — each is incompatible with ASan.
- Always `-O1 -g -fno-omit-frame-pointer` so stacks symbolize; ensure
  `llvm-symbolizer` is on `PATH`.
- Set `*_OPTIONS` for CI: e.g. `UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1`,
  `ASAN_OPTIONS=abort_on_error=1:detect_leaks=1`.
- Go has `-race` (a TSan-based race detector) built in — run fuzzing with
  `-race` where the target is concurrent.

## Engine choice + licensing (wrap-don't-vendor)

Default to permissively-licensed engines so nothing viral enters the tree:

- **libFuzzer** — ships with Clang (LLVM license). Zero extra dependency; the
  first reach for C/C++.
- **LibAFL** — MIT / Apache-2.0, actively developed Rust fuzzing framework; it
  can rebuild libFuzzer-style targets and is the permissive successor now that
  upstream libFuzzer is in maintenance mode. Prefer it when you outgrow plain
  libFuzzer.
- **honggfuzz** — Apache-2.0, a permissive alternative engine.

**Avoid AFL++ v5 as the default or a vendored dependency: it is AGPL-3.0**
(viral copyleft). If a specific campaign truly needs it, run it as an **external
tool** on a separate box — **wrap, don't vendor**: never link or copy AFL++ into
this repository. (This mirrors the suite's G17 licensing posture: LibAFL /
libFuzzer over AFL++ v5.)

## Crash → fix → regression (own code only)

1. **Reproduce** deterministically: Go replays `testdata/fuzz/...`; libFuzzer
   re-runs the crash input file.
2. **Minimize** the reproducer (`go test` shrinks automatically; libFuzzer
   `-minimize_crash=1`).
3. **Triage** exploitability with `$vuln-research-loop` (CASR / crash-severity),
   and disassemble with `$reverse-engineering-toolkit` if needed — no exploit
   development.
4. **Fix** the root cause, commit the crasher as a regression test, and add a
   `$security-review` Stage-3 variant rule so the bug class can't return.

## CI integration

- **Go:** nightly `go test -fuzz=... -fuzztime=<budget>`; commit any new
  corpus entries and crashers. Keep a short `-fuzztime` smoke in PR CI.
- **C/C++:** the ClusterFuzzLite / OSS-Fuzz-Gen orchestration lives in
  `$vuln-research-loop`; this skill supplies the sanitizer-instrumented harness
  those services run.

## Related

- Source material promoted here: `.agents/library/skills/golang-testing`
  (`go test -fuzz`) and `.agents/library/skills/cpp-testing` (sanitizers /
  libFuzzer appendix).
- `$vuln-research-loop` — crash triage, exploitability, CI fuzzing orchestration.
- `$security-review` — differential fuzzing feeds Stage 2; variant rules close Stage 3.
- `$reverse-engineering-toolkit`, `$malware-analysis-triage` — disassemble / diff a crashing binary.
