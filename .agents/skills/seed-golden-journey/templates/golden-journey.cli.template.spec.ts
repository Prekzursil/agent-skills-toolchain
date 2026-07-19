// golden-journey.cli.template.spec.ts — CLI variant of the keystone acceptance test.
//
// Fill in every << PLACEHOLDER >>. For a CLI, the "money journey" is: run the REAL
// command on a REAL fixture and assert it produced a REAL, VALID output file — never
// just "exit code 0 and something was printed". Same assertion ladder as the GUI spec.
//
// Runner-agnostic: shown with @playwright/test's `test`/`expect`, but the body is plain
// Node — swap to jest/vitest by changing only the import.

import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, statSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const OUT = join(tmpdir(), `<<TOOL>>-golden-${Date.now()}.<<EXT>>`);

test.afterAll(() => {
  try { rmSync(OUT, { force: true }); } catch { /* best-effort cleanup */ }
});

test('<<TOOL>> produces a real <<ARTIFACT>> from a real input (golden journey)', () => {
  test.setTimeout(240_000);

  // A — run the REAL command on a REAL fixture, writing to a fresh temp path.
  //     stdio:'inherit' surfaces the tool's own errors; a non-zero exit throws here,
  //     which is a faithful red-repro (do NOT swallow it).
  execFileSync(
    '<<TOOL_BIN>>',                                   // e.g. 'node', './dist/cli.js', 'mytool'
    ['<<SUBCOMMAND>>', '--in', '<<FIXTURE_PATH>>', '--out', OUT /*, ...flags */],
    { stdio: 'inherit', timeout: 200_000 },
  );

  // B — the assertion ladder on the PRODUCED file (climb every rung):
  // Rung 1 — exists.
  expect(existsSync(OUT), `artifact exists on disk: ${OUT}`).toBe(true);
  // Rung 2 — non-empty (a 0-byte file is a silent failure).
  expect(statSync(OUT).size, `artifact is non-empty: ${OUT}`).toBeGreaterThan(0);
  // Rung 3 — structurally valid: it actually opens/parses/decodes. Pick ONE:
  //   media:  const dims = execFileSync('ffprobe', ['-v','error','-select_streams','v:0',
  //             '-show_entries','stream=width,height','-of','csv=p=0', OUT]).toString().trim();
  //           expect(dims, `ffprobe decoded ${OUT}`).toMatch(/^\d+,\d+$/);
  //   json:   const data = JSON.parse(readFileSync(OUT, 'utf8'));   // throws if malformed
  //   archive:execFileSync('unzip', ['-t', OUT]);                   // throws if corrupt
  // Rung 4 — semantically correct: assert the promise of the journey (the row count, the
  //   dimensions, the expected keys) — not merely that a file appeared.
  // expect(<<SEMANTIC_CHECK>>).toBe(<<EXPECTED>>);
});

/*
Python equivalent (pytest), same ladder:

    import subprocess, os, json
    def test_tool_produces_real_artifact(tmp_path):
        out = tmp_path / "out.<<EXT>>"
        subprocess.run(
            ["<<TOOL_BIN>>", "<<SUBCOMMAND>>", "--in", "<<FIXTURE_PATH>>", "--out", str(out)],
            check=True, timeout=200,                     # non-zero exit → faithful red-repro
        )
        assert out.exists()                              # rung 1
        assert out.stat().st_size > 0                    # rung 2
        # rung 3 — structurally valid (ffprobe / json.loads / zipfile.testzip)
        # rung 4 — semantically correct (assert the promised values)
*/
