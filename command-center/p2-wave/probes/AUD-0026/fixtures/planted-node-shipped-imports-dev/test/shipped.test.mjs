// Test-only import of the same declared-dev package.
// Probe 2 MUST NOT flag this: test/ is outside package.json "files".
import typescript from "typescript";

export function testControl() {
  return typeof typescript;
}
