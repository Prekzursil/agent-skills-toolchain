import fs from 'node:fs'
const src = fs.readFileSync('schemas.js','utf8')
const names = ['LEVELS','COMMON','COMMON_REQ','CMD','GATE_STEP','ROW_STATE','SETUP','CARD','CARD_INDEX','TESTS','BUILD','FINDING','VERDICT','MERGE','REPORT']
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
const ROOTS = ['SETUP','CARD_INDEX','TESTS','BUILD','VERDICT','MERGE','REPORT']
for (const n of ROOTS) { const s = S[n]; if (s.type !== 'object') problems.push(n + ': root not object'); walk(s, n) }
function verdictScan(node, path) {
  if (!node || typeof node !== 'object') return
  for (const [k, v] of Object.entries(node.properties || {})) {
    if (/^(verdict|status|state|mode|verification_level|level|kind|severity|observed|false_claim_red)$/.test(k) && v.type === 'string' && !v.enum) problems.push(path + '.' + k + ': verdict-like string without enum')
    verdictScan(v, path + '.' + k); if (v.items) verdictScan(v.items, path + '.' + k + '[]')
  }
}
for (const n of ROOTS) verdictScan(S[n], n)
console.log('object nodes:', nodes, '| roots:', ROOTS.length); console.log(problems.length ? problems.join('\n') : 'no problems')
// JS ↔ schema field coverage: every `x.<field>` the script reads on a return should be declared somewhere
const js = fs.readFileSync('script.js','utf8')
const declared = new Set(); for (const n of ROOTS) Object.keys(S[n].properties).forEach(k => declared.add(k))
const reads = new Set([...js.matchAll(/\b(?:setup|idx|a|red|b|v|m|cg|rv|fw|jw|chk|ev|vj|s|apiLedger|catalog|res)\.([a-z_]+)\b/g)].map(x => x[1]))
const undeclared = [...reads].filter(k => !declared.has(k) && !['status','reason','id','length','filter','map','some','every','findings','cards','head','state','digest','verdict','why','ok'].includes(k) && !/^__/.test(k))
console.log('fields read by the JS on returns but declared in no schema:', undeclared.join(', ') || 'none')
