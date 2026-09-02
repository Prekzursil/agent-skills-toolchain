import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
console.log('RESOLVED_LIB=' + require.resolve('@prekzursil/tools-lib'));
const mod = await import('@prekzursil/tools-lib');
if (typeof mod.legacyPing !== 'function') {
  console.error('SMOKE=fail missing legacyPing (changed copy exercised)');
  process.exit(2);
}
console.log('SMOKE=pass unexpected legacyPing=' + mod.legacyPing());
