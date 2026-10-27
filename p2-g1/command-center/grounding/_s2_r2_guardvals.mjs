// ROUND 2 / R6 premise check: which invocation spellings actually break the
// LEXICAL main-guard?  Prints the two values the guard compares, plus both
// verdicts, so the both-states probe is built on a measured premise rather than
// an assumed one.  (The first attempt assumed an 8.3 short path would break the
// compare; it did not, because Node kept the short form on BOTH sides.)
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';
import { resolve } from 'node:path';

const argv1 = process.argv[1] ?? '';
const self = fileURLToPath(import.meta.url);
const lexical = resolve(argv1) === resolve(self);
let real = null;
try { real = realpathSync.native(argv1) === realpathSync.native(self); } catch { real = 'throw'; }

console.log('argv[1]      :', argv1);
console.log('import.meta  :', self);
console.log('LEXICAL match:', lexical, '  <- what the old guard uses');
console.log('REALPATH match:', real, '  <- what the fixed guard uses');
console.log(lexical ? 'GUARD-WOULD-RUN' : 'GUARD-WOULD-SILENTLY-SKIP');
