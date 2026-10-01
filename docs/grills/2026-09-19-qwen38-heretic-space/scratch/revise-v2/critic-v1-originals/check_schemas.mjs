import fs from 'node:fs'
const src = fs.readFileSync('schemas.js','utf8')
const names = ['LEVELS','COMMON','COMMON_REQ','CMD','SETUP','CARD_INDEX','TESTS','BUILD','FINDING','VERDICT','MERGE','REPORT']
const S = new Function(src + '\nreturn {' + names.join(',') + '}')()
const ALLOWED = new Set(['type','enum','required','properties','items','minItems','description'])
let nodes = 0, problems = []
function walk(node, path) {
  if (!node || typeof node !== 'object') return
  for (const k of Object.keys(node)) if (!ALLOWED.has(k)) problems.push(path + ': keyword ' + k)
  if (node.type === 'object') {
    nodes++
    const props = node.properties || {}
    if (!node.properties) problems.push(path + ': object without properties')
    for (const r of node.required || []) if (!(r in props)) problems.push(path + ': required ' + r + ' not in properties')
    if (node.required && new Set(node.required).size !== node.required.length) problems.push(path + ': duplicate required')
    for (const [k, v] of Object.entries(props)) walk(v, path + '.' + k)
  }
  if (node.enum) { if (!node.enum.length) problems.push(path + ': empty enum'); if (new Set(node.enum).size !== node.enum.length) problems.push(path + ': dup enum') }
  if (node.items) walk(node.items, path + '[]')
  if (node.type === 'array' && !node.items) problems.push(path + ': array without items')
}
for (const n of ['SETUP','CARD_INDEX','TESTS','BUILD','VERDICT','MERGE','REPORT']) {
  const s = S[n]; if (s.type !== 'object') problems.push(n + ': root not object'); walk(s, n)
}
// verdict-like string fields without enum
function verdictScan(node, path) {
  if (!node || typeof node !== 'object') return
  for (const [k, v] of Object.entries(node.properties || {})) {
    if (/verdict|status|state|mode|level|kind|severity|observed/.test(k) && v.type === 'string' && !v.enum) problems.push(path + '.' + k + ': verdict-like string without enum')
    verdictScan(v, path + '.' + k); if (v.items) verdictScan(v.items, path + '.' + k + '[]')
  }
}
for (const n of ['SETUP','CARD_INDEX','TESTS','BUILD','VERDICT','MERGE','REPORT']) verdictScan(S[n], n)
console.log('object nodes:', nodes); console.log(problems.length ? problems.join('\n') : 'no problems')
// coverage: which fields does the JS read that the schema does not declare?
const js = fs.readFileSync('script.js','utf8')
const declared = {}
for (const n of ['SETUP','CARD_INDEX','TESTS','BUILD','VERDICT','MERGE','REPORT']) declared[n] = Object.keys(S[n].properties)
console.log(JSON.stringify(declared, null, 0))
