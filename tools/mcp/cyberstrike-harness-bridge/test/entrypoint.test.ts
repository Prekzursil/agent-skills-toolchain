import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { describe, it } from "node:test";

import { isDirectEntrypoint } from "../src/entrypoint.ts";

describe("Windows ESM entrypoint detection", () => {
  it("matches canonical file URLs without hand-building file URI slashes", () => {
    const windowsPath = "C:\\Program Files\\CyberStrike Gateway\\src\\cli.ts";
    assert.equal(isDirectEntrypoint(pathToFileURL(windowsPath).href, windowsPath), true);
    assert.equal(
      isDirectEntrypoint(
        pathToFileURL(windowsPath).href,
        "C:\\Program Files\\CyberStrike Gateway\\src\\other.ts",
      ),
      false,
    );
    assert.equal(isDirectEntrypoint(pathToFileURL(windowsPath).href, undefined), false);
  });
});
