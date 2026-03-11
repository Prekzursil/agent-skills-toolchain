const assert = require('assert');
const ext = require('../extension.js');

const sample = [
  'Implement the feature without opening a browser.',
  'Keep the code block intact.',
  'Return a checklist.',
  '```js',
  'console.log(1);',
  '```'
].join('\n');

const output = ext.optimizePrompt(sample, 'Codex task');
assert(output.includes('# Optimized Prompt'));
assert(output.includes('## Objective'));
assert(output.includes('## Preserved Code / Structured Content'));
assert(output.includes('console.log(1);'));
assert(!output.includes('platform.openai.com/chat/edit'));
console.log('prompt-optimizer-button smoke test passed');
