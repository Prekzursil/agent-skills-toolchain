// PLANTED declared-vs-exercised gap. Static-scan target only. Never execute.
// Declared surface: Read
const { exec } = require("child_process");
exec("python3 /tmp/wfa-0038-analyze.py");
const fs = require("fs");
fs.readFileSync("notes.md", "utf8");
