import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const repositoryRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../..");
const workspacePath = "tools/mcp/cyberstrike-harness-bridge";

describe("root workspace wiring", () => {
  it("runs the private gateway in the root test workspace and locks the local link", async () => {
    const rootPackage = JSON.parse(
      await readFile(resolve(repositoryRoot, "package.json"), "utf8"),
    );
    const rootLock = JSON.parse(
      await readFile(resolve(repositoryRoot, "package-lock.json"), "utf8"),
    );

    assert.equal(rootPackage.workspaces.includes(workspacePath), true);
    assert.equal(rootLock.packages[""].workspaces.includes(workspacePath), true);
    assert.deepEqual(rootLock.packages["node_modules/@prekzursil/cyberstrike-gateway"], {
      resolved: workspacePath,
      link: true,
    });
    assert.equal(
      rootLock.packages[workspacePath].name,
      "@prekzursil/cyberstrike-gateway",
    );
  });
});
