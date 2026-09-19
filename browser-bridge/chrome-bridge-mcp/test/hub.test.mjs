// Hermetic unit suite for the hub - the transport broker between MCP server
// instances and the Chrome extension. Everything runs on 127.0.0.1 with an
// ephemeral port and a FAKE extension client that speaks the real wire
// protocol; no Chrome is involved. Follows the mcpapply precedent of gating
// loopback sockets on purpose (measured: every bind and connect on 127.0.0.1).
import test from "node:test";
import assert from "node:assert/strict";
import net from "node:net";
import { WebSocket, WebSocketServer } from "ws";

import { Hub, PROTOCOL_VERSION, HOST } from "../dist/hub.js";

const TOKEN = "unit-test-token";
const EXT_ID = "abcdefghijklmnopabcdefghijklmnop";
const EXT_ORIGIN = `chrome-extension://${EXT_ID}`;

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

const settle = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Collects every inbound frame from construction, so handshake-bundled frames are never lost. */
function trackMessages(socket) {
  socket.__messages = [];
  socket.__waiters = [];
  socket.on("message", (data) => {
    const parsed = JSON.parse(data.toString());
    const waiter = socket.__waiters.shift();
    if (waiter) waiter(parsed);
    else socket.__messages.push(parsed);
  });
  return socket;
}

/** Waits for the next collected frame on a tracked socket. */
function nextMessage(socket, timeoutMs = 3000) {
  if (socket.__messages?.length) return Promise.resolve(socket.__messages.shift());
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("no message within timeout")), timeoutMs);
    socket.__waiters.push((parsed) => {
      clearTimeout(timer);
      resolve(parsed);
    });
    socket.once("close", () => {
      clearTimeout(timer);
      reject(new Error("socket closed while waiting"));
    });
  });
}

async function waitFor(predicate, timeoutMs = 3000, stepMs = 25) {
  const deadline = Date.now() + timeoutMs;
  while (!predicate()) {
    if (Date.now() >= deadline) return false;
    await settle(stepMs);
  }
  return true;
}

function opened(socket, timeoutMs = 3000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connection never opened")), timeoutMs);
    socket.once("open", () => {
      clearTimeout(timer);
      resolve(socket);
    });
    socket.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    socket.once("unexpected-response", (_req, res) => {
      clearTimeout(timer);
      reject(new Error(`handshake rejected: HTTP ${res.statusCode}`));
    });
  });
}

/** Connects a programmable fake Chrome extension to the hub. */
async function connectExtension(port) {
  const socket = trackMessages(
    new WebSocket(`ws://${HOST}:${port}/extension?token=${TOKEN}`, { headers: { Origin: EXT_ORIGIN } }),
  );
  await opened(socket);
  return socket;
}

/** Connects a bare local client (as a guest MCP process would). */
async function connectClient(port, { cid = "cid-1", token = TOKEN, origin } = {}) {
  const socket = trackMessages(
    new WebSocket(`ws://${HOST}:${port}/client?cid=${cid}${token ? `&token=${token}` : ""}`, {
      headers: origin ? { Origin: origin } : {},
    }),
  );
  await opened(socket);
  return socket;
}

test("hub: refuses to start without a token", async () => {
  const hub = new Hub(await freePort());
  await assert.rejects(() => hub.start(), /CHROME_BRIDGE_TOKEN is required/);
});

test("hub: a non-EADDRINUSE listen failure is rethrown, not treated as guest mode", async () => {
  const hub = new Hub(70000, TOKEN, EXT_ID); // port out of range: fails for a reason other than EADDRINUSE
  await assert.rejects(() => hub.start(), (error) => error.code !== "EADDRINUSE");
});

test("hub: binds as host, greets clients with the protocol version", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    assert.equal(await hub.start(), "host");
    const client = await connectClient(hub.port);
    try {
      const hello = await nextMessage(client);
      assert.equal(hello.kind, "hello");
      assert.equal(hello.protocol, PROTOCOL_VERSION);
    } finally {
      client.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: handshake authorization rejects everything it must", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();

    // Wrong token on /client.
    await assert.rejects(() => connectClient(hub.port, { token: "wrong" }), /HTTP 401/);
    // No token at all.
    await assert.rejects(() => connectClient(hub.port, { token: "" }), /HTTP 401/);
    // A web page origin may never control the browser.
    await assert.rejects(() => connectClient(hub.port, { origin: "https://evil.example" }), /HTTP 401/);
    // The extension path without an origin...
    const noOrigin = new WebSocket(`ws://${HOST}:${hub.port}/extension?token=${TOKEN}`);
    await assert.rejects(() => opened(noOrigin), /HTTP 401/);
    // ...with a non-extension origin...
    const webOrigin = new WebSocket(`ws://${HOST}:${hub.port}/extension?token=${TOKEN}`, {
      headers: { Origin: "https://evil.example" },
    });
    await assert.rejects(() => opened(webOrigin), /HTTP 401/);
    // ...and with the WRONG extension origin while an id is pinned.
    const wrongExt = new WebSocket(`ws://${HOST}:${hub.port}/extension?token=${TOKEN}`, {
      headers: { Origin: "chrome-extension://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
    });
    await assert.rejects(() => opened(wrongExt), /HTTP 401/);
  } finally {
    await hub.close();
  }
});

test("hub: accepts the pinned extension and round-trips a cdp call", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    try {
      assert.equal(hub.connected, true, "host with an open extension socket reports connected");

      const roundTrip = hub.call({ type: "cdp", method: "Page.navigate", params: { url: "https://example.com" } });
      const command = await nextMessage(extension);
      assert.equal(command.kind, "command");
      assert.equal(command.command.type, "cdp");
      assert.equal(command.command.method, "Page.navigate");
      assert.ok(command.id, "commands carry a correlation id");
      extension.send(JSON.stringify({ id: command.id, ok: true, result: { frameId: "f1" } }));
      assert.deepEqual(await roundTrip, { frameId: "f1" });
    } finally {
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: a denied CDP command never reaches the extension", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    try {
      await assert.rejects(
        () => hub.call({ type: "cdp", method: "Network.getAllCookies" }),
        /denied \(cookie\/credential exfil\)/,
      );
    } finally {
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: extension error replies reject the caller", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    try {
      const roundTrip = hub.call({ type: "cdp", method: "Page.reload" });
      const command = await nextMessage(extension);
      extension.send(JSON.stringify({ id: command.id, ok: false, error: "no tab attached" }));
      await assert.rejects(() => roundTrip, /no tab attached/);
    } finally {
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: commands time out when the extension never replies, and late replies are dropped", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    try {
      const roundTrip = hub.call({ type: "cdp", method: "Page.reload" }, 150);
      const command = await nextMessage(extension);
      await assert.rejects(() => roundTrip, /timed out after 150ms/);
      // A reply arriving after the timeout must not throw or resurrect anything.
      extension.send(JSON.stringify({ id: command.id, ok: true, result: {} }));
      await settle(50);
    } finally {
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: a second extension replaces the first", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const first = await connectExtension(hub.port);
    const firstClosed = new Promise((resolve) => first.once("close", (code) => resolve(code)));
    const second = await connectExtension(hub.port);
    try {
      assert.equal(await firstClosed, 4000, "replaced extension is closed with code 4000");
    } finally {
      second.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: notifications reach the host, guests, or both, per targeting", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    const guest = await connectClient(hub.port, { cid: "guest-a" });
    try {
      assert.equal((await nextMessage(guest)).kind, "hello", "guest handshake");
      // Targeted at the host only.
      extension.send(JSON.stringify({ kind: "notification", clientIds: [hub.clientId], text: "for host" }));
      await settle(100);
      assert.deepEqual(hub.drainNotifications(), ["for host"]);

      // Targeted at a guest by cid.
      const guestSees = nextMessage(guest);
      extension.send(JSON.stringify({ kind: "notification", clientIds: ["guest-a"], text: "for guest" }));
      assert.equal((await guestSees).text, "for guest");
      await settle(50);
      assert.deepEqual(hub.drainNotifications(), [], "guest-targeted notification is not pushed to the host");

      // Untargeted broadcast reaches both.
      const guestSeesAll = nextMessage(guest);
      extension.send(JSON.stringify({ kind: "notification", text: "broadcast" }));
      assert.equal((await guestSeesAll).text, "broadcast");
      assert.deepEqual(hub.drainNotifications(), ["broadcast"]);

      // A non-array clientIds degrades to a broadcast (so it reaches the host too)...
      const guestSeesDegrade = nextMessage(guest);
      extension.send(JSON.stringify({ kind: "notification", clientIds: "not-an-array", text: "degraded" }));
      assert.equal((await guestSeesDegrade).text, "degraded");
      assert.deepEqual(hub.drainNotifications(), ["degraded"]);
      // ...and empty text is dropped entirely.
      extension.send(JSON.stringify({ kind: "notification", text: "" }));
      await settle(50);
      assert.deepEqual(hub.drainNotifications(), [], "empty text never lands");

      // The ring buffer caps at 50.
      for (let i = 0; i < 55; i++) extension.send(JSON.stringify({ kind: "notification", text: `n${i}` }));
      await settle(150);
      const drained = hub.drainNotifications();
      assert.equal(drained.length, 50);
      assert.equal(drained[0], "n5", "oldest entries are shifted out");
    } finally {
      guest.close();
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: garbage frames and non-call guest messages are ignored", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    const guest = await connectClient(hub.port);
    try {
      extension.send("this is not json");
      guest.send(JSON.stringify({ kind: "hello" }));
      guest.send("also not json");
      // Valid JSON that is not an object must degrade to ignored, not crash the parser.
      extension.send(JSON.stringify(42));
      guest.send(JSON.stringify('"a string"'));
      await settle(100);
      // The hub is still fully functional afterwards.
      const roundTrip = hub.call({ type: "focusTab" });
      const command = await nextMessage(extension);
      extension.send(JSON.stringify({ id: command.id, ok: true, result: null }));
      assert.equal(await roundTrip, null);
    } finally {
      guest.close();
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: an error reply without an error field falls back to the generic message", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    try {
      const roundTrip = hub.call({ type: "cdp", method: "Page.reload" });
      const command = await nextMessage(extension);
      extension.send(JSON.stringify({ id: command.id, ok: false }));
      await assert.rejects(() => roundTrip, /browser command failed/);
    } finally {
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: a cid-less guest relays with an empty clientId", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    const bare = trackMessages(new WebSocket(`ws://${HOST}:${hub.port}/client?token=${TOKEN}`));
    try {
      await opened(bare);
      assert.equal((await nextMessage(bare)).kind, "hello");
      bare.send(JSON.stringify({ kind: "call", id: "b1", command: { type: "focusTab" } }));
      const command = await nextMessage(extension);
      assert.equal(command.clientId, "");
      extension.send(JSON.stringify({ id: command.id, ok: true, result: 1 }));
      const reply = await nextMessage(bare);
      assert.deepEqual(reply, { kind: "reply", id: "b1", ok: true, result: 1 });
    } finally {
      bare.close();
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: the authorize guard still refuses an unconfigured token (defensive-slot probe)", async () => {
  // start() refuses an empty token before any socket can exist, so this branch
  // is unreachable through the public surface; probe the predicate directly to
  // prove the guard still refuses. TS-private members, reached into deliberately.
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  hub["token"] = "";
  assert.equal(hub["authorize"]("/client", undefined, "anything"), "hub token not configured");
});

test("hub: a server-level error after listening is swallowed, not fatal", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    // The post-listening error handler exists so a runtime server error cannot
    // crash the process; emit a synthetic one to prove the swallow. The only
    // route to that handler is the server object itself (TS-private).
    hub["wss"].emit("error", new Error("synthetic post-listening error"));
    await settle(50);
    // Still serving afterwards.
    const client = await connectClient(hub.port);
    client.close();
  } finally {
    await hub.close();
  }
});

test("hub: a guest hub relays calls through the host and back", async () => {
  const port = await freePort();
  const host = new Hub(port, TOKEN, EXT_ID);
  try {
    await host.start();
    const extension = await connectExtension(port);
    const guest = new Hub(port, TOKEN, EXT_ID);
    try {
      assert.equal(await guest.start(), "guest");
      // The upstream socket opens asynchronously after the v2 hello; wait for it.
      assert.equal(await waitFor(() => guest.connected), true, "guest with an open upstream reports connected");

      const roundTrip = guest.call({ type: "cdp", method: "Page.reload" });
      const command = await nextMessage(extension);
      assert.equal(command.command.method, "Page.reload");
      assert.equal(command.clientId, guest.clientId, "relayed commands carry the guest clientId");
      extension.send(JSON.stringify({ id: command.id, ok: true, result: { reloaded: true } }));
      assert.deepEqual(await roundTrip, { reloaded: true });

      // A broadcast notification reaches the guest hub through its upstream socket
      // and lands in the guest's own notification buffer.
      extension.send(JSON.stringify({ kind: "notification", text: "guest-side push" }));
      assert.ok(await waitFor(() => guest.drainNotifications().length > 0));
      assert.deepEqual(guest.drainNotifications(), []);
      await guest.close();
    } finally {
      extension.close();
      await guest.close().catch(() => {});
    }
  } finally {
    await host.close();
  }
});

test("hub: raw guest clients can relay calls, and failures come back as error replies", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(hub.port);
    const guest = await connectClient(hub.port, { cid: "raw-1" });
    try {
      assert.equal((await nextMessage(guest)).kind, "hello", "guest handshake");
      // Success path - no clientId on the message, so the host falls back to the query cid.
      guest.send(JSON.stringify({ kind: "call", id: "g1", command: { type: "cdp", method: "Page.reload" }, timeoutMs: 2000 }));
      const command = await nextMessage(extension);
      assert.equal(command.clientId, "raw-1");
      extension.send(JSON.stringify({ id: command.id, ok: true, result: 7 }));
      const reply = await nextMessage(guest);
      assert.deepEqual(reply, { kind: "reply", id: "g1", ok: true, result: 7 });

      // Failure path - a denied command rejects inside the host and replies ok:false.
      guest.send(JSON.stringify({ kind: "call", id: "g2", command: { type: "cdp", method: "Storage.getCookies" }, timeoutMs: 2000 }));
      const failure = await nextMessage(guest);
      assert.equal(failure.id, "g2");
      assert.equal(failure.ok, false);
      assert.match(failure.error, /denied/);
    } finally {
      guest.close();
      extension.close();
    }
  } finally {
    await hub.close();
  }
});

test("hub: close() rejects in-flight calls and frees the port", async () => {
  const port = await freePort();
  const hub = new Hub(port, TOKEN, EXT_ID);
  try {
    await hub.start();
    const extension = await connectExtension(port);
    try {
      const roundTrip = hub.call({ type: "cdp", method: "Page.reload" }, 60_000);
      await nextMessage(extension); // command arrived; do not answer
      // Attach the rejection assertion BEFORE closing, so the pending promise is
      // never momentarily unhandled when close() rejects it.
      const asserted = assert.rejects(() => roundTrip, /chrome-bridge hub closed/);
      await hub.close();
      await asserted;
    } finally {
      extension.close();
    }

    // The port is free again: a second hub can bind it.
    const successor = new Hub(port, TOKEN, EXT_ID);
    try {
      assert.equal(await successor.start(), "host");
    } finally {
      await successor.close();
    }
  } catch (error) {
    await hub.close().catch(() => {});
    throw error;
  }
});

test("hub: awaitSocket gives up when the hub closes mid-wait", async () => {
  const hub = new Hub(await freePort(), TOKEN, EXT_ID);
  try {
    await hub.start();
    // No extension connected: the call waits for one, and closing interrupts the wait.
    const roundTrip = hub.call({ type: "cdp", method: "Page.reload" });
    await settle(150);
    const closing = hub.close();
    await assert.rejects(() => roundTrip, /Chrome extension is not connected/);
    await closing;
  } catch (error) {
    await hub.close().catch(() => {});
    throw error;
  }
});

test("hub: a guest takes over when the host exits", async () => {
  const port = await freePort();
  const host = new Hub(port, TOKEN, EXT_ID);
  await host.start();
  const guest = new Hub(port, TOKEN, EXT_ID);
  try {
    assert.equal(await guest.start(), "guest");
    await host.close();
    await settle(800); // recover() runs 500ms after the upstream closes
    // The guest is now the host: with no extension attached its calls fail with
    // the HOST-side message, proving the promotion happened.
    await assert.rejects(() => guest.call({ type: "cdp", method: "Page.reload" }), /Chrome extension is not connected/);
  } finally {
    await guest.close().catch(() => {});
  }
});

test("hub: an incompatible (protocol v1) holder makes calls fail with the takeover hint", async () => {
  const port = await freePort();
  // A fake host whose FIRST greeting lacks the protocol field entirely (an even
  // older shape) and whose reconnects speak protocol 1 - both mismatch paths.
  let connections = 0;
  const fakeHost = new WebSocketServer({ host: HOST, port });
  fakeHost.on("connection", (socket) => {
    connections += 1;
    socket.send(JSON.stringify(connections === 1 ? { kind: "hello" } : { kind: "hello", protocol: 1 }));
  });
  const guest = new Hub(port, TOKEN, EXT_ID);
  try {
    assert.equal(await guest.start(), "guest");
    await assert.rejects(() => guest.call({ type: "cdp", method: "Page.reload" }), /incompatible \(older\) chrome-bridge-mcp/);
  } finally {
    await guest.close().catch(() => {});
    await new Promise((resolve) => fakeHost.close(() => resolve()));
  }
});

test("hub: a SILENT older holder (no hello at all) is detected by the 2s timer", async () => {
  const port = await freePort();
  // A fake host that accepts the connection and never says a word.
  const fakeHost = new WebSocketServer({ host: HOST, port });
  fakeHost.on("connection", () => {});
  const guest = new Hub(port, TOKEN, EXT_ID);
  try {
    assert.equal(await guest.start(), "guest");
    await assert.rejects(() => guest.call({ type: "cdp", method: "Page.reload" }), /incompatible \(older\) chrome-bridge-mcp/);
  } finally {
    await guest.close().catch(() => {});
    await new Promise((resolve) => fakeHost.close(() => resolve()));
  }
});

test("hub: a silent upstream yields the not-connected error", async () => {
  const port = await freePort();
  // An occupier that rejects every client handshake: the guest can never open an upstream.
  const occupier = new WebSocketServer({
    host: HOST,
    port,
    verifyClient: (_info, done) => done(false, 401, "no"),
  });
  const guest = new Hub(port, TOKEN, EXT_ID);
  try {
    assert.equal(await guest.start(), "guest");
    await assert.rejects(() => guest.call({ type: "cdp", method: "Page.reload" }), /Not connected to the chrome-bridge hub/);
  } finally {
    await guest.close().catch(() => {});
    await new Promise((resolve) => occupier.close(() => resolve()));
  }
});
