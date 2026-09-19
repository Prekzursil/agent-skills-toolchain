// Hermetic unit suite for the 21 registered tools. The full loop runs without
// Chrome: a real Hub on an ephemeral loopback port, a PROGRAMMABLE fake
// extension that answers commands over the real wire protocol, and an MCP
// client connected to the real McpServer through an in-memory transport.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import net from "node:net";
import { WebSocket } from "ws";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

import { Hub, HOST } from "../dist/hub.js";
import { registerTools } from "../dist/tools.js";

const TOKEN = "unit-test-token";
const EXT_ID = "abcdefghijklmnopabcdefghijklmnop";
const EXT_ORIGIN = `chrome-extension://${EXT_ID}`;
const settle = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, HOST, () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Fake extension: a routing responder over the real socket.
// ---------------------------------------------------------------------------

class FakeExtension {
  constructor(port) {
    this.socket = null;
    this.commands = [];
    this.routes = [];
    this.port = port;
  }

  /** Adds a route; LAST added wins. match(command) -> result | {__error} | {__blackhole}. */
  on(match, handler) {
    this.routes.unshift({ match, handler });
    return this;
  }

  clearRoutes() {
    this.routes = [];
  }

  async connect() {
    this.socket = new WebSocket(`ws://${HOST}:${this.port}/extension?token=${TOKEN}`, {
      headers: { Origin: EXT_ORIGIN },
    });
    await new Promise((resolve, reject) => {
      this.socket.once("open", resolve);
      this.socket.once("error", reject);
    });
    this.socket.on("message", (data) => this.handle(JSON.parse(data.toString())));
  }

  handle(message) {
    if (message.kind !== "command") return;
    const command = message.command;
    this.commands.push(command);
    const route = this.routes.find((r) => {
      try {
        return r.match(command);
      } catch {
        return false;
      }
    });
    if (!route) {
      this.socket.send(JSON.stringify({ id: message.id, ok: true, result: this.defaultFor(command) }));
      return;
    }
    const outcome =
      typeof route.handler === "function" ? route.handler(command) : route.handler;
    if (outcome && outcome.__blackhole) return; // deliberately never answer
    if (outcome && outcome.__error) {
      this.socket.send(JSON.stringify({ id: message.id, ok: false, error: outcome.__error }));
      return;
    }
    this.socket.send(JSON.stringify({ id: message.id, ok: true, result: outcome ?? {} }));
  }

  /** Stock behaviour for every command the tools issue during happy paths. */
  defaultFor(command) {
    if (command.type === "cdp") return this.cdpDefault(command.method, command.params);
    switch (command.type) {
      case "listTabs":
        return [
          { id: 1, title: "Inbox", url: "https://mail.example", active: true, attached: true },
          { id: 2, title: "", url: "https://blank.example", shared: true },
        ];
      case "attach":
        return { id: 1, title: "Inbox", url: "https://mail.example" };
      case "newTab":
        return { id: 7 };
      case "navState":
        return { startedAt: Date.now() + 60_000, pending: false };
      case "consoleLogs":
        return [];
      default:
        return {};
    }
  }

  cdpDefault(method, params) {
    if (method === "Runtime.evaluate") return this.evaluateDefault(params?.expression ?? "");
    switch (method) {
      case "Page.getFrameTree":
        return { frameTree: { frame: { id: "f0", url: "http://top" }, childFrames: [] } };
      case "Page.getLayoutMetrics":
        return { cssVisualViewport: { clientWidth: 800, clientHeight: 600 } };
      case "Page.getNavigationHistory":
        return { currentIndex: 1, entries: [{ id: 10 }, { id: 11 }, { id: 12 }] };
      case "Page.captureScreenshot":
        return { data: Buffer.from("png").toString("base64") };
      case "DOM.getFrameOwner":
        return { backendNodeId: 5 };
      case "DOM.resolveNode":
        return { object: { objectId: "obj-1" } };
      case "Runtime.callFunctionOn":
        return { result: { value: JSON.stringify({ x: 10, y: 20 }) } };
      default:
        return {};
    }
  }

  evaluateDefault(expression) {
    // RAW-value replies: settleNavigation and browser_wait_for compare
    // result.value directly (=== 'complete', === true), with no JSON.parse.
    if (expression.includes("document.readyState")) return { result: { value: "complete" } };
    if (expression.includes("try { return !!(") || expression.includes("document.body.innerText")) {
      return { result: { value: true } };
    }
    // The upload handle lookup runs with returnByValue:false - the objectId
    // sits on result itself, not inside a JSON string. Its expression is the
    // ONLY one starting with a `window.__cbref &&` conjunction; every script
    // merely MENTIONS window.__cbref in its helpers.
    if (expression.includes("window.__cbref &&")) return { result: { objectId: "obj-7" } };

    // evalJson replies: result.value is a JSON STRING the caller parses.
    // Order matters: the snapshot script's HELPERS mention innerText in a
    // comment, so the page-kind probes must use unambiguous markers.
    let value;
    if (expression.includes("elementFromPoint")) value = { x: 100, y: 50, tag: "button", type: "", covered: false, coveredBy: "" };
    else if (expression.includes("data-cb-icon")) value = { ok: true };
    else if (expression.includes("isContentEditable")) value = { ok: true, mode: "select" };
    else if (expression.includes("el.options")) value = { selected: ["alpha"] };
    else if (expression.includes("store.map.clear")) value = { url: "https://page", title: "Page", snapshot: '- button "Go" [ref=epoch1-e1]', truncated: false, epoch: "epoch1" };
    else if (expression.includes("clone.innerText")) value = { url: "https://page", title: "Page", text: "body text" };
    else if (expression.includes("location.href")) value = "https://page";
    else value = true;
    return { result: { value: JSON.stringify(value) } };
  }

  close() {
    this.socket?.close();
  }
}

// ---------------------------------------------------------------------------
// Harness: hub + fake extension + MCP client wired through in-memory transport.
// ---------------------------------------------------------------------------

async function startHarness({ pageBadge = true } = {}) {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  const role = await hub.start();
  assert.equal(role, "host");
  const extension = new FakeExtension(hub.port);
  await extension.connect();

  const server = new McpServer({ name: "chrome-bridge-test", version: "0" });
  registerTools(server, hub, { pageBadge });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await server.connect(serverTransport);
  const client = new Client({ name: "test-client", version: "0" }, {});
  await client.connect(clientTransport);

  const call = async (name, args = {}) => {
    const result = await client.callTool({ name, arguments: args });
    return {
      text: (result.content ?? []).filter((c) => c.type === "text").map((c) => c.text).join("\n"),
      isError: result.isError === true,
      images: (result.content ?? []).filter((c) => c.type === "image"),
    };
  };

  return {
    hub,
    extension,
    call,
    async close() {
      await client.close();
      await server.close();
      extension.close();
      await hub.close();
    },
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test("tools: browser_tabs lists tabs with markers and legend", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_tabs");
    assert.equal(r.isError, false);
    assert.match(r.text, /\[1\] \(active\) Inbox/);
    assert.match(r.text, /\[2\] \(untitled\)/);
    assert.match(r.text, /"\+" = also debugged by another client/);
  } finally {
    await h.close();
  }
});

test("tools: browser_tabs with no tabs", async () => {
  const h = await startHarness();
  try {
    h.extension.on((c) => c.type === "listTabs", []);
    const r = await h.call("browser_tabs");
    assert.match(r.text, /No open tabs/);
  } finally {
    await h.close();
  }
});

test("tools: browser_attach snapshots the attached tab", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_attach", { tabId: 3 });
    assert.match(r.text, /Attached to tab 1/);
    assert.match(r.text, /Page snapshot/);
    assert.match(r.text, /ref=epoch1-e1/);
  } finally {
    await h.close();
  }
});

test("tools: browser_new_tab opens and snapshots, background honoured", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_new_tab", { url: "https://example.com", background: true });
    assert.match(r.text, /Opened https:\/\/example\.com in tab 7/);
    const newTab = h.extension.commands.find((c) => c.type === "newTab");
    assert.deepEqual({ url: newTab.url, active: newTab.active }, { url: "https://example.com", active: false });
  } finally {
    await h.close();
  }
});

test("tools: browser_navigate goto happy path", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_navigate", { action: "goto", url: "https://page" });
    assert.match(r.text, /Navigation \(goto\) complete/);
    assert.doesNotMatch(r.text, /did not navigate/);
  } finally {
    await h.close();
  }
});

test("tools: browser_navigate goto without url, and CDP error text", async () => {
  const h = await startHarness();
  try {
    const missing = await h.call("browser_navigate", { action: "goto" });
    assert.equal(missing.isError, true);
    assert.match(missing.text, /`url` is required/);

    h.extension.on((c) => c.type === "cdp" && c.method === "Page.navigate", { errorText: "net::ERR_NAME_NOT_RESOLVED" });
    const failed = await h.call("browser_navigate", { action: "goto", url: "https://missing" });
    assert.equal(failed.isError, true);
    assert.match(failed.text, /Navigation failed: net::ERR_NAME_NOT_RESOLVED/);

    // net::ERR_ABORTED is ignored (it accompanies downloads and cancels).
    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.navigate", { errorText: "net::ERR_ABORTED" });
    const aborted = await h.call("browser_navigate", { action: "goto", url: "https://page" });
    assert.equal(aborted.isError, false);
  } finally {
    await h.close();
  }
});

test("tools: browser_navigate reload / back / forward and missing history entry", async () => {
  const h = await startHarness();
  try {
    assert.match((await h.call("browser_navigate", { action: "reload" })).text, /Navigation \(reload\) complete/);
    assert.match((await h.call("browser_navigate", { action: "back" })).text, /Navigation \(back\) complete/);
    assert.match((await h.call("browser_navigate", { action: "forward" })).text, /Navigation \(forward\) complete/);

    // currentIndex 0, back => entries[-1] missing.
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getNavigationHistory", { currentIndex: 0, entries: [{ id: 10 }] });
    const stuck = await h.call("browser_navigate", { action: "back" });
    assert.equal(stuck.isError, true);
    assert.match(stuck.text, /Cannot go back/);
  } finally {
    await h.close();
  }
});

test("tools: browser_navigate detects a stalled download", async () => {
  const h = await startHarness();
  try {
    // Location never changes and never matches the target URL.
    const r = await h.call("browser_navigate", { action: "goto", url: "https://files.example/report.pdf" });
    assert.equal(r.isError, false);
    assert.match(r.text, /did not navigate/);
    assert.match(r.text, /file download/);
  } finally {
    await h.close();
  }
});

test("tools: browser_snapshot reports an open modal dialog instead of hanging", async () => {
  const h = await startHarness();
  try {
    h.extension.on((c) => c.type === "navState", { dialog: { type: "alert", message: "hello" } });
    const r = await h.call("browser_snapshot");
    assert.match(r.text, /alert dialog is open and blocking the page: "hello"/);
    assert.match(r.text, /browser_handle_dialog/);
  } finally {
    await h.close();
  }
});

test("tools: browser_snapshot retries a still-loading document and marks truncation", async () => {
  const h = await startHarness();
  try {
    let loads = 0;
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("store.map.clear"),
      () => {
        loads += 1;
        return loads < 2
          ? { result: { value: JSON.stringify({ url: "u", title: "t", snapshot: "", truncated: false, loading: true, epoch: "ep2" }) } }
          : { result: { value: JSON.stringify({ url: "u", title: "t", snapshot: "- text \"x\"", truncated: true, epoch: "ep2" }) } };
      },
    );
    const r = await h.call("browser_snapshot");
    assert.match(r.text, /- text "x"/);
    assert.match(r.text, /snapshot truncated/);
    assert.equal(loads, 2, "the loading document was retried exactly once");
  } finally {
    await h.close();
  }
});

test("tools: browser_snapshot appends frame blocks and browser notifications", async () => {
  const h = await startHarness();
  try {
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getFrameTree", {
      frameTree: {
        frame: { id: "f0", url: "http://top" },
        childFrames: [{ frame: { id: "f1", url: "https://child.example" } }],
      },
    });
    // Push a notification the host will drain into the next tool result.
    h.extension.socket.send(JSON.stringify({ kind: "notification", text: "file downloaded" }));
    await settle(100);
    const r = await h.call("browser_snapshot");
    assert.match(r.text, /- iframe "https:\/\/child\.example"/);
    assert.match(r.text, /  - button "Go" [ref=epoch1-e1]/); // the child frame snapshot, indented under its iframe header
    assert.match(r.text, /\[Browser notifications\]/);
    assert.match(r.text, /file downloaded/);
  } finally {
    await h.close();
  }
});

test("tools: browser_snapshot survives unreachable frames and getFrameTree errors", async () => {
  const h = await startHarness();
  try {
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getFrameTree", { __error: "no frame tree" });
    const r = await h.call("browser_snapshot");
    assert.equal(r.isError, false);
    assert.doesNotMatch(r.text, /iframe/);

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getFrameTree", {
      frameTree: { frame: { id: "f0", url: "http://top" }, childFrames: [{ frame: { id: "f9", url: "https://x" } }] },
    });
    h.extension.on((c) => c.type === "cdp" && c.method === "DOM.resolveNode", { __error: "gone" });
    const unreachable = await h.call("browser_snapshot");
    assert.match(unreachable.text, /content not reachable from this frame/);
  } finally {
    await h.close();
  }
});

test("tools: browser_text truncates over the limit", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_text", { maxChars: 4 });
    assert.match(r.text, /body/);
    assert.match(r.text, /… \(truncated\)/);
    const full = await h.call("browser_text");
    assert.doesNotMatch(full.text, /truncated/);
  } finally {
    await h.close();
  }
});

test("tools: browser_screenshot returns a PNG image, viewport and full page", async () => {
  const h = await startHarness();
  try {
    const viewport = await h.call("browser_screenshot");
    assert.match(viewport.text, /Viewport screenshot:/);
    assert.equal(viewport.images.length, 1);
    const full = await h.call("browser_screenshot", { fullPage: true });
    assert.match(full.text, /Full-page screenshot:/);
  } finally {
    await h.close();
  }
});

test("tools: browser_click by ref warns when overlapped, clicks raw coords otherwise", async () => {
  const h = await startHarness();
  try {
    // Attach first so a frame map epoch exists for the ref.
    await h.call("browser_attach", {});
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("elementFromPoint"),
      { result: { value: JSON.stringify({ x: 5, y: 6, tag: "button", type: "", covered: true, coveredBy: "div#overlay" }) } },
    );
    const overlapped = await h.call("browser_click", { ref: "epoch1-e1" });
    assert.match(overlapped.text, /overlapped by <div#overlay>/);

    h.extension.clearRoutes();
    const raw = await h.call("browser_click", { x: 12, y: 34, doubleClick: true, button: "right" });
    assert.match(raw.text, /Clicked \(12, 34\)/);
    const pressed = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent");
    assert.ok(pressed.some((c) => c.params.clickCount === 2 && c.params.button === "right"), "double right click dispatched");

    const neither = await h.call("browser_click", {});
    assert.equal(neither.isError, true);
    assert.match(neither.text, /Provide either `ref` or both `x` and `y`/);

    const badRef = await h.call("browser_click", { ref: "../../etc" });
    assert.equal(badRef.isError, true);
    assert.match(badRef.text, /Invalid element ref/);
  } finally {
    await h.close();
  }
});

test("tools: browser_click without navigation settles the short way (slow path probe, ~1.2s)", async () => {
  const h = await startHarness();
  try {
    // startedAt 0 + pending false => awaitNavigationStart runs out its 900ms budget.
    h.extension.on((c) => c.type === "navState", { startedAt: 0, pending: false });
    const r = await h.call("browser_click", { x: 1, y: 2 });
    assert.match(r.text, /Clicked/);
  } finally {
    await h.close();
  }
});

test("tools: navigation settling rides out a pending navigation and a loading document", async () => {
  const h = await startHarness();
  try {
    // navState: pending once, then done -> awaitNavigationEnd loops once through its 150ms sleep.
    let navPolls = 0;
    h.extension.on(
      (c) => c.type === "navState",
      () => {
        navPolls += 1;
        return navPolls <= 2 ? { pending: true, startedAt: Date.now() + 60_000 } : { pending: false, startedAt: Date.now() + 60_000 };
      },
    );
    // readyState: first evaluate throws (catch), then "loading", then "complete".
    let readyPolls = 0;
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("document.readyState"),
      () => {
        readyPolls += 1;
        if (readyPolls === 1) return { __error: "context swapped" };
        return readyPolls === 2 ? { result: { value: "loading" } } : { result: { value: "complete" } };
      },
    );
    const r = await h.call("browser_click", { x: 5, y: 5 });
    assert.equal(r.isError, false, r.text);
    assert.ok(readyPolls >= 3, "the settle loop rode out an error and a loading state");
  } finally {
    await h.close();
  }
});

test("tools: evalJson exception fallbacks - text only, and a bare exceptionDetails", async () => {
  const h = await startHarness();
  try {
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && !c.params?.expression.includes("try"),
      () => ({ result: { value: null }, exceptionDetails: { text: "Evaluation crashed" } }),
    );
    const textOnly = await h.call("browser_evaluate", { expression: "1" });
    assert.match(textOnly.text, /Evaluation crashed/);

    h.extension.clearRoutes();
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate",
      () => ({ result: { value: null }, exceptionDetails: {} }),
    );
    // browser_text goes through evalJson, whose own fallback wording is asserted here.
    const bare = await h.call("browser_text");
    assert.match(bare.text, /page script failed/);
  } finally {
    await h.close();
  }
});

test("tools: an input dispatch whose CDP call REJECTS settles via the catch, and a late dialog poll sleeps", async () => {
  const h = await startHarness();
  try {
    // First click: the CDP input call rejects outright (settled via .catch, no dialog needed).
    h.extension.on((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent", { __error: "input channel gone" });
    const rejected = await h.call("browser_click", { x: 1, y: 1 });
    assert.match(rejected.text, /Clicked/);

    // Second click: the input call blackholes and the dialog only appears on the SECOND poll,
    // exercising the 250ms poll sleep between attempts.
    h.extension.clearRoutes();
    let polls = 0;
    h.extension.on((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent", { __blackhole: true });
    h.extension.on(
      (c) => c.type === "navState",
      () => {
        polls += 1;
        return polls === 1 ? { pending: false, startedAt: 0 } : { dialog: { type: "alert", message: "late" } };
      },
    );
    const late = await h.call("browser_click", { x: 2, y: 2 });
    assert.match(late.text, /alert dialog is open/);
    assert.ok(polls >= 2, "the dialog was found on a later poll");
  } finally {
    await h.close();
  }
});

test("tools: browser_type with ref, clear, perKey and submit", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    const r = await h.call("browser_type", { text: "hi", ref: "epoch1-e1", clear: true, perKey: true, submit: true });
    assert.match(r.text, /Typed into ref=epoch1-e1 and submitted/);
    const keys = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchKeyEvent");
    // Control+a, Delete, 'h', 'i', Enter => keyDown+keyUp each => 10 events.
    assert.ok(keys.length >= 10, `expected per-key events, saw ${keys.length}`);
    assert.ok(keys.some((c) => c.params.key === "a" && c.params.modifiers === 2), "select-all shortcut");
    assert.ok(keys.some((c) => c.params.key === "Enter"));

    const insert = await h.call("browser_type", { text: "bulk" });
    assert.match(insert.text, /Typed into the focused element/);
    assert.ok(h.extension.commands.some((c) => c.type === "cdp" && c.method === "Input.insertText"));
  } finally {
    await h.close();
  }
});

test("tools: browser_press_key descriptor variants and modifier text suppression", async () => {
  const h = await startHarness();
  try {
    for (const key of ["Enter", "Escape", "a", "5", "/", "~", "FancyKey"]) {
      const r = await h.call("browser_press_key", { key });
      assert.match(r.text, new RegExp(`Pressed ${key}`), key);
    }
    const withCtrl = await h.call("browser_press_key", { key: "a", modifiers: ["Control"] });
    assert.match(withCtrl.text, /Pressed Control\+a/);
    const events = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchKeyEvent");
    // Ctrl+a down must be a rawKeyDown (text suppressed so shortcuts are not typed).
    assert.ok(events.some((c) => c.params.key === "a" && c.params.type === "rawKeyDown"));
    assert.ok(events.some((c) => c.params.key === "Enter" && c.params.type === "keyDown"), "plain Enter types its text");
  } finally {
    await h.close();
  }
});

test("tools: browser_scroll by ref and by viewport centre, metrics fallbacks", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    const byRef = await h.call("browser_scroll", { ref: "epoch1-e1", deltaY: -300 });
    assert.match(byRef.text, /Scrolled/);
    const wheel = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent" && c.params.type === "mouseWheel");
    assert.equal(wheel.at(-1).params.deltaY, -300);

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getLayoutMetrics", { cssLayoutViewport: { clientWidth: 0, clientHeight: 0 } });
    await h.call("browser_scroll", { deltaX: 5 });
    const fallbackWheel = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent" && c.params.type === "mouseWheel").find((c) => c.params.deltaX === 5);
    assert.deepEqual({ x: fallbackWheel.params.x, y: fallbackWheel.params.y }, { x: 0, y: 0 }, "layout-viewport fallback used");

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getLayoutMetrics", { __error: "no metrics" });
    await h.call("browser_scroll", {});
    const defaultWheel = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent" && c.params.type === "mouseWheel").at(-1);
    assert.deepEqual({ x: defaultWheel.params.x, y: defaultWheel.params.y }, { x: 400, y: 300 }, "hard-coded centre on metrics failure");
  } finally {
    await h.close();
  }
});

test("tools: browser_select_option happy path and every failure shape", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    const r = await h.call("browser_select_option", { ref: "epoch1-e1", values: ["alpha"] });
    assert.match(r.text, /Selected \["alpha"\] in ref=epoch1-e1/);

    h.extension.on((c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("el.options"),
      () => ({ result: { value: JSON.stringify({ error: "That ref is a <div>, not a <select>." }) } }));
    const notSelect = await h.call("browser_select_option", { ref: "epoch1-e1", values: ["x"] });
    assert.equal(notSelect.isError, true);
    assert.match(notSelect.text, /not a <select>/);

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("el.options"),
      () => ({ result: { value: JSON.stringify({ selected: [] }) } }));
    const noMatch = await h.call("browser_select_option", { ref: "epoch1-e1", values: ["zzz"] });
    assert.equal(noMatch.isError, true);
    assert.match(noMatch.text, /None of \["zzz"\] matched/);

    const badRef = await h.call("browser_select_option", { ref: "nope", values: ["x"] });
    assert.match(badRef.text, /Invalid element ref/);
  } finally {
    await h.close();
  }
});

test("tools: browser_hover by ref, by coordinates, and the missing-target error", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    assert.match((await h.call("browser_hover", { ref: "epoch1-e1" })).text, /Hovered ref=epoch1-e1/);
    assert.match((await h.call("browser_hover", { x: 3, y: 4 })).text, /Hovered \(3, 4\)/);
    const neither = await h.call("browser_hover", {});
    assert.equal(neither.isError, true);
    assert.match(neither.text, /Provide either `ref` or both/);
  } finally {
    await h.close();
  }
});

test("tools: browser_upload validates paths and resolves the input handle", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    const file = path.join(os.tmpdir(), `cb-upload-${Date.now()}.txt`);
    fs.writeFileSync(file, "x", "utf8");
    try {
      const relative = await h.call("browser_upload", { ref: "epoch1-e1", files: ["data.txt"] });
      assert.equal(relative.isError, true);
      assert.match(relative.text, /must be absolute/);

      const missing = await h.call("browser_upload", { ref: "epoch1-e1", files: [path.join(os.tmpdir(), "no-such-file.cb")] });
      assert.equal(missing.isError, true);
      assert.match(missing.text, /No such file/);

      const r = await h.call("browser_upload", { ref: "epoch1-e1", files: [file] });
      assert.match(r.text, /Attached 1 file\(s\) to ref=epoch1-e1/);
      assert.ok(h.extension.commands.some((c) => c.type === "cdp" && c.method === "DOM.setFileInputFiles"));

      h.extension.on((c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("__cbref"),
        () => ({ result: {} }));
      const noHandle = await h.call("browser_upload", { ref: "epoch1-e1", files: [file] });
      assert.equal(noHandle.isError, true);
      assert.match(noHandle.text, /Unknown ref\. Take a fresh browser_snapshot/);
    } finally {
      fs.rmSync(file, { force: true });
    }
  } finally {
    await h.close();
  }
});

test("tools: browser_wait_for - immediate, by text, by textGone, expression guard, timeout", async () => {
  const h = await startHarness();
  try {
    const none = await h.call("browser_wait_for", {});
    assert.equal(none.isError, true);
    assert.match(none.text, /Provide one of/);

    const unsafe = await h.call("browser_wait_for", { expression: "document.cookie" });
    assert.equal(unsafe.isError, true);
    assert.match(unsafe.text, /page script refused/);

    assert.match((await h.call("browser_wait_for", { expression: "window.ok" })).text, /Condition met/);
    assert.match((await h.call("browser_wait_for", { text: "body" })).text, /Condition met/);

    // textGone: the raw-value probe returns false (text still present) until it returns true.
    let gone = false;
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("document.body.innerText"),
      () => ({ result: { value: gone } }),
    );
    const vanish = h.call("browser_wait_for", { textGone: "spinner" });
    await settle(150);
    gone = true;
    assert.match((await vanish).text, /Condition met/);

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Runtime.evaluate", () => ({ result: { value: false } }));
    const timedOut = await h.call("browser_wait_for", { text: "never", timeoutMs: 1 });
    assert.equal(timedOut.isError, true);
    assert.match(timedOut.text, /Timed out after 1ms waiting for text "never" to appear/);
  } finally {
    await h.close();
  }
});

test("tools: browser_evaluate refuses credentials, surfaces exceptions, stringifies null", async () => {
  const h = await startHarness();
  try {
    const unsafe = await h.call("browser_evaluate", { expression: "localStorage.length" });
    assert.equal(unsafe.isError, true);
    assert.match(unsafe.text, /page script refused/);

    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate",
      () => ({ result: { value: null }, exceptionDetails: { exception: { description: "TypeError: boom" } } }),
    );
    const exception = await h.call("browser_evaluate", { expression: "null.x" });
    assert.equal(exception.isError, true);
    assert.match(exception.text, /TypeError: boom/);

    h.extension.clearRoutes();
    h.extension.on((c) => c.type === "cdp" && c.method === "Runtime.evaluate", () => ({ result: { value: null } }));
    const nullValue = await h.call("browser_evaluate", { expression: "document.title" });
    assert.match(nullValue.text, /\bnull\b/);
  } finally {
    await h.close();
  }
});

test("tools: browser_console formats entries and empty output", async () => {
  const h = await startHarness();
  try {
    assert.match((await h.call("browser_console")).text, /No console output/);
    h.extension.on((c) => c.type === "consoleLogs", [
      { level: "error", text: "boom", url: "https://page/app.js" },
      { level: "log", text: "hi" },
    ]);
    const r = await h.call("browser_console", { limit: 5 });
    assert.match(r.text, /\[error\] boom \(https:\/\/page\/app\.js\)/);
    assert.match(r.text, /\[log\] hi$/m);
  } finally {
    await h.close();
  }
});

test("tools: browser_cdp passes allowlisted methods through and denies the rest", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_cdp", { method: "Page.getLayoutMetrics" });
    assert.equal(r.isError, false);
    assert.match(r.text, /clientWidth/);

    const denied = await h.call("browser_cdp", { method: "Network.getCookies" });
    assert.equal(denied.isError, true);
    assert.match(denied.text, /denied/);
  } finally {
    await h.close();
  }
});

test("tools: browser_handle_dialog accepts and dismisses", async () => {
  const h = await startHarness();
  try {
    assert.match((await h.call("browser_handle_dialog", {})).text, /Dialog accepted/);
    assert.match((await h.call("browser_handle_dialog", { accept: false, promptText: "no" })).text, /Dialog dismissed/);
    const handled = h.extension.commands.filter((c) => c.type === "handleDialog");
    assert.deepEqual(handled.map((c) => c.accept), [true, false]);
  } finally {
    await h.close();
  }
});

test("tools: browser_close_tab with and without tabId (badge restore)", async () => {
  const h = await startHarness();
  try {
    await h.call("browser_attach", {});
    assert.match((await h.call("browser_close_tab", { tabId: 9 })).text, /Tab closed/);
    // Without tabId the favicon badge is restored while the page is still reachable.
    assert.match((await h.call("browser_close_tab", {})).text, /Tab closed/);
    const badgeRestores = h.extension.commands.filter(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("data-cb-icon") && c.params.expression.includes("!false"),
    );
    assert.equal(badgeRestores.length, 1, "badge restored exactly once, on the tabId-less close");
  } finally {
    await h.close();
  }
});

test("tools: browser_detach restores the badge and detaches", async () => {
  const h = await startHarness();
  try {
    const r = await h.call("browser_detach");
    assert.match(r.text, /Detached\. Chrome is no longer being controlled/);
    assert.ok(h.extension.commands.some((c) => c.type === "cdp" && (c.params?.expression ?? "").includes("data-cb-icon")), "badge restored before detach");
    assert.ok(h.extension.commands.some((c) => c.type === "detach"));
  } finally {
    await h.close();
  }
});

test("tools: pageBadge=false skips every favicon interaction", async () => {
  const h = await startHarness({ pageBadge: false });
  try {
    await h.call("browser_attach", {});
    await h.call("browser_close_tab", {});
    await h.call("browser_detach");
    const badges = h.extension.commands.filter((c) => c.type === "cdp" && (c.params?.expression ?? "").includes("data-cb-icon"));
    assert.equal(badges.length, 0, "no badge scripts issued with pageBadge disabled");
  } finally {
    await h.close();
  }
});

test("tools: a click on a ref inside a child frame applies the frame offset", async () => {
  const h = await startHarness();
  try {
    // Snapshot a page with one child frame so the frame map gets an epoch entry.
    h.extension.on((c) => c.type === "cdp" && c.method === "Page.getFrameTree", {
      frameTree: {
        frame: { id: "f0", url: "http://top" },
        childFrames: [{ frame: { id: "f1", url: "https://child.example" } }],
      },
    });
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && (c.params?.expression ?? "").includes("store.map.clear"),
      () => ({ result: { value: JSON.stringify({ url: "u", title: "t", snapshot: "", truncated: false, epoch: "top1" }) } }),
    );
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Page.createIsolatedWorld",
      { executionContextId: 42 },
    );
    // The child frame's own snapshot reports epoch 'chld1'; refs inside it resolve
    // in the same isolated world - distinguished by expression, not just contextId.
    h.extension.on(
      (c) => c.type === "cdp" && c.method === "Runtime.evaluate" && c.params?.contextId === 42,
      (command) => {
        const expression = command.params?.expression ?? "";
        if (expression.includes("elementFromPoint")) {
          return { result: { value: JSON.stringify({ x: 100, y: 50, tag: "button", type: "", covered: false, coveredBy: "" }) } };
        }
        return { result: { value: JSON.stringify({ url: "u", title: "t", snapshot: '- button "in-frame" [ref=chld1-e3]', truncated: false, epoch: "chld1" }) } };
      },
    );
    const snap = await h.call("browser_snapshot");
    assert.match(snap.text, /ref=chld1-e3/);

    // Click the in-frame ref: resolve returns frame-relative 100/50, owner rect adds 10/20.
    const r = await h.call("browser_click", { ref: "chld1-e3" });
    assert.equal(r.isError, false, r.text);
    const press = h.extension.commands.filter((c) => c.type === "cdp" && c.method === "Input.dispatchMouseEvent" && c.params.type === "mousePressed").at(-1);
    assert.deepEqual({ x: press.params.x, y: press.params.y }, { x: 110, y: 70 }, "frame offset added to the resolved point");
  } finally {
    await h.close();
  }
});
