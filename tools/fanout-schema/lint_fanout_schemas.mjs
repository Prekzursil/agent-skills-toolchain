#!/usr/bin/env node

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { extname, join } from 'node:path'
import process from 'node:process'

import { lintSource } from './fanout_schema.mjs'

const SOURCE_EXTENSIONS = new Set(['.js', '.mjs'])
const inputs = process.argv.slice(2)

function collectSourcePaths(path, out) {
  const stat = statSync(path)
  if (stat.isFile()) {
    out.push(path)
    return
  }
  if (!stat.isDirectory()) return

  for (const entry of readdirSync(path, { withFileTypes: true })) {
    const child = join(path, entry.name)
    if (entry.isDirectory()) {
      collectSourcePaths(child, out)
    } else if (entry.isFile() && SOURCE_EXTENSIONS.has(extname(entry.name))) {
      out.push(child)
    }
  }
}

if (inputs.length === 0) {
  console.error('usage: node lint_fanout_schemas.mjs <workflow-or-directory> [...]')
  process.exitCode = 2
} else {
  const paths = []
  let inputError = false

  for (const input of inputs) {
    try {
      collectSourcePaths(input, paths)
    } catch (error) {
      // node:fs only ever throws Error subclasses here; .message is the whole contract.
      console.error(`${input}: ${error.message}`)
      inputError = true
    }
  }

  paths.sort()
  let schemaCount = 0
  let violationCount = 0

  for (const path of paths) {
    let source
    try {
      source = readFileSync(path, 'utf8')
    } catch (error) {
      // node:fs only ever throws Error subclasses here; .message is the whole contract.
      console.error(`${path}: ${error.message}`)
      inputError = true
      continue
    }

    const schemas = lintSource(source)
    schemaCount += schemas.length
    for (const schema of schemas) {
      const line = source.slice(0, schema.index).split(/\r?\n/u).length
      for (const violation of schema.violations) {
        const property = violation.property ? ` [${violation.property}]` : ''
        console.error(`${path}:${line}: ${violation.rule}${property}: ${violation.message}`)
        violationCount++
      }
    }
  }

  if (inputError) {
    process.exitCode = 2
  } else if (schemaCount === 0) {
    console.error('fanout-schema lint: FAILED (no object schema literals found)')
    process.exitCode = 1
  } else if (violationCount > 0) {
    console.error(
      `fanout-schema lint: FAILED (${violationCount} violation(s), ${schemaCount} schema(s))`,
    )
    process.exitCode = 1
  } else {
    console.log(`fanout-schema lint: OK (${schemaCount} schema(s), ${paths.length} file(s))`)
  }
}
