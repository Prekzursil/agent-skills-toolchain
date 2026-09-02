import { createRequire } from 'node:module';
import { ok } from '@prekzursil/tools-lib';
const require = createRequire(import.meta.url);
console.log('RESOLVED_LIB=' + require.resolve('@prekzursil/tools-lib'));
if (ok() !== 'ok-v2') {
  console.error('SMOKE=fail ok=' + ok());
  process.exit(2);
}
console.log('SMOKE=pass');
