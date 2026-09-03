import { readFile, readdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { censusAgplBoundary } from "../src/agpl-boundary.ts";

const packageRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const sourceRoot = join(packageRoot, "src");
const sourceNames = (await readdir(sourceRoot)).filter((name) => name.endsWith(".ts")).sort();
const sources = await Promise.all(sourceNames.map((name) => readFile(join(sourceRoot, name), "utf8")));
const packageJson = await readFile(join(packageRoot, "package.json"), "utf8");
const violations = censusAgplBoundary({ packageJson, sources });
process.stdout.write(`${JSON.stringify({ scannedSourceFiles: sourceNames.length, violations })}\n`);
if (violations.length > 0) process.exitCode = 1;
