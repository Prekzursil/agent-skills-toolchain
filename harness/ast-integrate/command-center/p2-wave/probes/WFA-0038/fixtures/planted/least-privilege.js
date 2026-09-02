// Least-privilege control. Static-scan target only. Never execute.
// Declared surface: Read, Grep
const fs = require("fs");
const text = fs.readFileSync("notes.md", "utf8");
if (text.includes("TODO")) {
  // grep-like scan of already-read bytes; no shell, no network
}
