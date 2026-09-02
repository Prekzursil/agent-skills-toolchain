import { pathToFileURL } from "node:url";

const mjs = process.argv[2];
const argv = JSON.parse(process.argv[3]);
const { invokeArgv } = await import(pathToFileURL(mjs).href);
const result = invokeArgv(argv);
if (result.error) {
  process.stderr.write(String(result.error));
  process.exit(1);
}
process.stdout.write(result.stdout || Buffer.alloc(0));
process.stderr.write(result.stderr || Buffer.alloc(0));
process.exit(result.status === 0 ? 0 : result.status ?? 1);
