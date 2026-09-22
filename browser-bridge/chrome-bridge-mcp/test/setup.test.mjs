// Hermetic unit suite for `chrome-bridge-mcp setup`. The module bakes os.homedir()
// paths at import time, so the HOME/USERPROFILE env is pointed at a sandbox
// BEFORE the first import and stays there for the whole file; per-test state is
// the set of config files present under that sandbox at call time. process.exit
// is stubbed (it is a hard process kill under node --test otherwise) and the
// interactive flow is driven through a fake TTY stdin/stdout pair.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { PassThrough } from "node:stream";
import { fileURLToPath } from "node:url";

const PKG_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HOME = await fs.promises.mkdtemp(path.join(os.tmpdir(), "cb-setup-home-"));
process.env.HOME = HOME;
process.env.USERPROFILE = HOME;

const setup = await import("../dist/setup.js");

const home = (...parts) => path.join(HOME, ...parts);
const clean = () => fs.rmSync(home(), { recursive: true, force: true });
const freshHome = () => {
  clean();
  fs.mkdirSync(home(), { recursive: true });
};

/**
 * Fakes TTY stdin (for readline) and captures console output.
 *
 * Terminal-mode readline consumes any line that arrives BEFORE the question is
 * asked (measured: answers written upfront are echoed then lost), so answers
 * are fed one at a time on a stagger, each landing after its prompt rendered.
 * Real terminals send \r; terminal mode is on because both isTTY flags are set
 * (which is exactly what setup's own interactive check requires).
 */
function fakeTty(answers = [], staggerMs = 120) {
  const input_ = new PassThrough();
  input_.isTTY = true;
  input_.setRawMode = () => {};
  const logs = [];
  const realLog = console.log;
  const realError = console.error;
  const realStdin = Object.getOwnPropertyDescriptor(process, "stdin");
  const realStdoutIsTTY = process.stdout.isTTY;
  console.log = (...args) => logs.push(args.map(String).join(" "));
  console.error = (...args) => logs.push(args.map(String).join(" "));
  process.stdout.isTTY = true;
  Object.defineProperty(process, "stdin", { value: input_, configurable: true });
  const feedTimers = answers.map((answer, index) =>
    setTimeout(() => input_.write(`${answer}\r`), staggerMs * (index + 1)),
  );
  return {
    logs,
    restore() {
      for (const timer of feedTimers) clearTimeout(timer);
      console.log = realLog;
      console.error = realError;
      if (realStdoutIsTTY === undefined) delete process.stdout.isTTY;
      else process.stdout.isTTY = realStdoutIsTTY;
      Object.defineProperty(process, "stdin", realStdin);
      input_.destroy();
    },
  };
}

function stubExit(t) {
  const original = process.exit;
  const calls = [];
  process.exit = (code) => {
    calls.push(code);
    throw new Error(`exited:${code}`);
  };
  t.after(() => {
    process.exit = original;
  });
  return calls;
}

test.after(() => clean());

test("setup: exported constants resolve inside the package", () => {
  assert.equal(setup.SERVER_NAME, "chrome-bridge");
  assert.ok(setup.serverEntry.endsWith(path.join("dist", "index.js")));
  assert.ok(fs.existsSync(setup.extensionDir));
  assert.deepEqual(setup.entryFor(), { command: process.execPath, args: [setup.serverEntry] });
});

test("setup: an unknown client exits 1 with the known-client list", async (t) => {
  freshHome();
  const calls = stubExit(t);
  const tty = fakeTty();
  try {
    await assert.rejects(() => setup.runSetup(["--client", "nope"]), /exited:1/);
    assert.deepEqual(calls, [1]);
  } finally {
    tty.restore();
  }
});

test("setup: dry-run prints the plan and writes nothing", async () => {
  freshHome();
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--global", "--dry-run"]);
    const out = tty.logs.join("\n");
    assert.match(out, /Would register/);
    assert.match(out, /Cursor/);
    assert.ok(!fs.existsSync(home(".cursor", "mcp.json")), "dry run must not write");
  } finally {
    tty.restore();
  }
});

test("setup: --yes --global adds JSON client configs and creates parents", async () => {
  freshHome();
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes", "--global"]);
    const config = JSON.parse(fs.readFileSync(home(".cursor", "mcp.json"), "utf8"));
    assert.deepEqual(config.mcpServers["chrome-bridge"], { command: process.execPath, args: [setup.serverEntry] });
  } finally {
    tty.restore();
  }
});

test("setup: a second run UPDATES the existing entry and leaves a backup", async () => {
  freshHome();
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes"]);
    const first = fs.readFileSync(home(".cursor", "mcp.json"), "utf8");
    await setup.runSetup(["--client", "cursor", "--yes"]);
    // The second run rewrites the same entry (no timestamps in the content, so
    // byte-identical output is correct) and leaves the pre-write state as backup.
    assert.ok(fs.existsSync(home(".cursor", "mcp.json.chrome-bridge-backup")), "backup created");
    assert.equal(fs.readFileSync(home(".cursor", "mcp.json.chrome-bridge-backup"), "utf8"), first, "backup is the pre-write state");
  } finally {
    tty.restore();
  }
});

test("setup: JSON with comments and trailing commas parses (loose) and updates", async () => {
  freshHome();
  fs.mkdirSync(home(".cursor"), { recursive: true });
  fs.writeFileSync(
    home(".cursor", "mcp.json"),
    '{\n  // my comment\n  "other": true,\n}\n',
    "utf8",
  );
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes"]);
    const config = JSON.parse(fs.readFileSync(home(".cursor", "mcp.json"), "utf8"));
    assert.equal(config.other, true, "pre-existing keys survive the loose re-serialize");
    assert.ok(config.mcpServers["chrome-bridge"]);
  } finally {
    tty.restore();
  }
});

test("setup: an unparseable JSON config reports failure without touching the file", async () => {
  freshHome();
  fs.mkdirSync(home(".cursor"), { recursive: true });
  const broken = "{ definitely not json";
  fs.writeFileSync(home(".cursor", "mcp.json"), broken, "utf8");
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes"]);
    const out = tty.logs.join("\n");
    assert.match(out, /unparseable/);
    assert.equal(fs.readFileSync(home(".cursor", "mcp.json"), "utf8"), broken, "broken file untouched");
    assert.ok(!fs.existsSync(home(".cursor", "mcp.json.chrome-bridge-backup")), "no backup for an unparseable file");
  } finally {
    tty.restore();
  }
});

test("setup: toml - absent file is created, present header replaced, absent header appended", async () => {
  freshHome();
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "codex", "--yes"]);
    const created = fs.readFileSync(home(".codex", "config.toml"), "utf8");
    assert.match(created, /\[mcp_servers\.chrome-bridge\]/);
    assert.match(created, /command = /);

    fs.writeFileSync(
      home(".codex", "config.toml"),
      '[other]\nvalue = 1\n\n[mcp_servers.chrome-bridge]\ncommand = "stale"\nargs = ["stale"]\n\n[mcp_servers.another]\nx = 1\n',
      "utf8",
    );
    await setup.runSetup(["--client", "codex", "--yes"]);
    const updated = fs.readFileSync(home(".codex", "config.toml"), "utf8");
    assert.ok(!updated.includes("stale"), "the stale block is replaced");
    assert.match(updated, /args = \[/);
    assert.match(updated, /\[mcp_servers\.another\]/, "sibling tables survive");
    assert.match(updated, /\[other\]/, "earlier tables survive");

    // A file with no trailing newline and no header gets the block appended.
    fs.writeFileSync(home(".codex", "config.toml"), "[root]\nkey = \"value\"", "utf8");
    await setup.runSetup(["--client", "codex", "--yes"]);
    const appended = fs.readFileSync(home(".codex", "config.toml"), "utf8");
    assert.match(appended, /\[root\]/);
    assert.match(appended, /\[mcp_servers\.chrome-bridge\]/);
    assert.equal(appended.indexOf("[mcp_servers.chrome-bridge]") > appended.indexOf("[root]"), true, "appended after existing content");
  } finally {
    tty.restore();
  }
});

test("setup: --project writes project configs; projectless clients fall back to global", async () => {
  freshHome();
  const project = await fs.promises.mkdtemp(path.join(os.tmpdir(), "cb-setup-proj-"));
  try {
    const tty = fakeTty();
    try {
      // codex has no project config -> forced global; cursor has one -> project.
      await setup.runSetup(["--client", "codex", "--project", "--project-dir", project, "--yes"]);
      await setup.runSetup(["--client", "cursor", "--project", "--project-dir", project, "--yes"]);
    } finally {
      tty.restore();
    }
    assert.ok(fs.existsSync(home(".codex", "config.toml")), "codex landed globally (no project config exists)");
    const projConfig = JSON.parse(fs.readFileSync(path.join(project, ".cursor", "mcp.json"), "utf8"));
    assert.ok(projConfig.mcpServers["chrome-bridge"]);
    // Project scope also installs the skill into created skill dirs.
    assert.ok(fs.existsSync(path.join(project, ".claude", "skills", "control-chrome-bridge")));
  } finally {
    await fs.promises.rm(project, { recursive: true, force: true });
  }
});

test("setup: global skills only populate roots the user already has", async () => {
  freshHome();
  fs.mkdirSync(home(".claude", "skills"), { recursive: true }); // .codex/skills deliberately absent
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes", "--global"]);
    assert.ok(fs.existsSync(home(".claude", "skills", "control-chrome-bridge", "SKILL.md")), "existing root populated");
    assert.ok(!fs.existsSync(home(".codex", "skills")), "absent root not created globally");
  } finally {
    tty.restore();
  }
});

/** Captures console output WITHOUT faking a TTY - keeps the non-interactive path. */
function consoleOnly() {
  const logs = [];
  const realLog = console.log;
  const realError = console.error;
  console.log = (...args) => logs.push(args.map(String).join(" "));
  console.error = (...args) => logs.push(args.map(String).join(" "));
  return {
    logs,
    restore() {
      console.log = realLog;
      console.error = realError;
    },
  };
}

test("setup: interactive flow with only projectless clients skips the scope prompt", async () => {
  freshHome();
  fs.mkdirSync(home(".codex"), { recursive: true });
  fs.writeFileSync(home(".codex", "config.toml"), "", "utf8"); // codex detected; it has no project config
  const tty = fakeTty(["1"]); // one answer: the client selection only
  try {
    await setup.runSetup([]);
    const out = tty.logs.join("\n");
    assert.doesNotMatch(out, /Install globally, or for this project/, "no scope prompt for projectless clients");
    assert.match(fs.readFileSync(home(".codex", "config.toml"), "utf8"), /chrome-bridge/, "installed globally");
  } finally {
    tty.restore();
  }
});

test("setup: with no detected clients and no --client, prints the manual snippet and exits cleanly", async () => {
  freshHome();
  const tty = consoleOnly();
  try {
    await setup.runSetup([]);
    const out = tty.logs.join("\n");
    assert.match(out, /No MCP client config files found/);
    assert.match(out, /--client cursor/);
  } finally {
    tty.restore();
  }
});

test("setup: an install error outside the config parser is caught and reported, not thrown", async () => {
  freshHome();
  fs.mkdirSync(home(".cursor"), { recursive: true });
  fs.writeFileSync(home(".cursor", "mcp.json"), "{}", "utf8");
  // Disclosed reach-in: make the final config write fail so the error surfaces
  // in the install LOOP's catch (installJson's own try only guards the parse).
  const realWrite = fs.writeFileSync;
  fs.writeFileSync = (p, ...rest) => {
    if (String(p).includes(".cursor")) throw new Error("EACCES: disk on fire");
    return realWrite(p, ...rest);
  };
  const tty = fakeTty();
  try {
    await setup.runSetup(["--client", "cursor", "--yes"]);
    const out = tty.logs.join("\n");
    assert.match(out, /disk on fire/, "the write error is reported per-client");
    assert.match(out, /!/);
  } finally {
    fs.writeFileSync = realWrite;
    tty.restore();
  }
});

test("setup: a missing dist build refuses to continue (defensive-slot probe)", async (t) => {
  freshHome();
  const calls = stubExit(t);
  // serverEntry is baked at import to the real package path, so the only way to
  // exercise the missing-build guard in-process is to make the existence probe
  // lie once - disclosed reach-in, restored immediately.
  const realExists = fs.existsSync;
  fs.existsSync = (p) => (p === setup.serverEntry ? false : realExists(p));
  const tty = consoleOnly();
  try {
    await assert.rejects(() => setup.runSetup(["--client", "cursor", "--yes"]), /exited:1/);
    assert.deepEqual(calls, [1]);
    assert.match(tty.logs.join("\n"), /is missing\./);
  } finally {
    fs.existsSync = realExists;
    tty.restore();
  }
});

test("setup: interactive flow - numbered selection plus global scope", async (t) => {
  freshHome();
  fs.writeFileSync(home(".claude.json"), "{}", "utf8"); // claude-code detected
  const tty = fakeTty(["1", "1"]);
  try {
    await setup.runSetup([]);
    const out = tty.logs.join("\n");
    assert.match(out, /detected/);
    const config = JSON.parse(fs.readFileSync(home(".claude.json"), "utf8"));
    assert.ok(config.mcpServers["chrome-bridge"], "selected client was configured");
  } finally {
    tty.restore();
  }
  t.after(() => freshHome());
});

test("setup: interactive flow - 'all' selects every client; 'none' aborts", async () => {
  freshHome();
  fs.writeFileSync(home(".claude.json"), "{}", "utf8");
  fs.mkdirSync(home(".cursor"), { recursive: true });
  fs.writeFileSync(home(".cursor", "mcp.json"), "{}", "utf8");
  fs.mkdirSync(home(".codex"), { recursive: true });
  fs.writeFileSync(home(".codex", "config.toml"), "", "utf8");

  const all = fakeTty(["all", "1"]);
  try {
    await setup.runSetup([]);
    assert.ok(JSON.parse(fs.readFileSync(home(".claude.json"), "utf8")).mcpServers["chrome-bridge"]);
    assert.ok(JSON.parse(fs.readFileSync(home(".cursor", "mcp.json"), "utf8")).mcpServers["chrome-bridge"]);
    assert.match(fs.readFileSync(home(".codex", "config.toml"), "utf8"), /chrome-bridge/);
  } finally {
    all.restore();
  }

  freshHome();
  fs.writeFileSync(home(".claude.json"), "{}", "utf8");
  const none = fakeTty(["none"]);
  try {
    await setup.runSetup([]);
    const out = none.logs.join("\n");
    assert.match(out, /Nothing selected/);
    assert.equal(JSON.parse(fs.readFileSync(home(".claude.json"), "utf8")).mcpServers, undefined, "nothing written on 'none'");
  } finally {
    none.restore();
  }
});

test("setup: interactive scope prompt understands project, and out-of-range numbers select nothing", async () => {
  freshHome();
  fs.writeFileSync(home(".claude.json"), "{}", "utf8");
  const project = await fs.promises.mkdtemp(path.join(os.tmpdir(), "cb-setup-scope-"));
  try {
    const tty = fakeTty(["1", "2"]);
    try {
      await setup.runSetup(["--project-dir", project]);
      // claude-code HAS a project config (.mcp.json), so scope 2 lands there.
      assert.ok(JSON.parse(fs.readFileSync(path.join(project, ".mcp.json"), "utf8")).mcpServers["chrome-bridge"]);
    } finally {
      tty.restore();
    }
  } finally {
    await fs.promises.rm(project, { recursive: true, force: true });
  }

  freshHome();
  fs.writeFileSync(home(".claude.json"), "{}", "utf8");
  const junk = fakeTty(["999"]);
  try {
    await setup.runSetup([]);
    const out = junk.logs.join("\n");
    assert.match(out, /Nothing selected/);
  } finally {
    junk.restore();
  }
});
