// Run against npm run dev:rooms on this Mac. Only synthetic text is used.
import assert from "node:assert/strict";
import { once } from "node:events";
import WebSocket from "ws";

const base = process.env.FARONET_TEST_URL || "http://127.0.0.1:8787";
const origin = new URL(base).origin;
if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(base).hostname)) {
  throw new Error("This test is restricted to a local Worker");
}
const sockets = [];
const watchdog = setTimeout(() => { console.error("Public-room runtime checks timed out"); process.exit(1); }, 20_000);
watchdog.unref();
const closed = new Map();
const received = new Map();
async function connect(room) {
  const ws = new WebSocket(`${base.replace(/^http/, "ws")}/rooms/${room}/ws`, { origin });
  sockets.push(ws);
  received.set(ws, []);
  closed.set(ws, once(ws, "close"));
  ws.on("message", (data) => received.get(ws).push(data.toString()));
  await once(ws, "open");
  return ws;
}
async function until(predicate) {
  const end = Date.now() + 2000;
  while (!predicate()) {
    if (Date.now() > end) throw new Error("Timed out waiting for room behavior");
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}
try {
  assert.equal((await fetch(`${base}/health`)).status, 200);
  const html = await fetch(`${base}/rooms`);
  assert.equal(html.status, 200);
  assert.match(html.headers.get("content-security-policy"), /frame-ancestors 'none'/);
  assert.equal(html.headers.get("cache-control"), "no-store");
  assert.equal((await fetch(`${base}/rooms.js`)).status, 200);
  assert.equal((await fetch(`${base}/rooms/demo/ws`)).status, 426);
  assert.equal((await fetch(`${base}/rooms/Upper/ws`)).status, 404);
  assert.equal((await fetch(`${base}/rooms/demo/ws?token=forbidden`)).status, 400);
  assert.equal((await fetch(`${base}/rooms`, { method: "POST" })).status, 405);
  assert.equal((await fetch(`${base}/private`)).status, 404);
  // A valid upgrade with a wrong origin must be rejected before object routing.
  const denied = new WebSocket(`${base.replace(/^http/, "ws")}/rooms/demo/ws`, { origin: "https://invalid.example" });
  await new Promise((resolve, reject) => {
    denied.once("unexpected-response", (_request, response) => {
      try { assert.equal(response.statusCode, 403); response.resume(); denied.terminate(); resolve(); }
      catch (error) { reject(error); }
    });
    denied.on("error", () => {});
    denied.once("open", () => reject(new Error("Wrong origin accepted")));
  });
  const suffix = Date.now().toString(36);
  const a = await connect(`same-${suffix}`);
  const b = await connect(`same-${suffix}`);
  const other = await connect(`other-${suffix}`);
  a.send("synthetic public message");
  await until(() => received.get(a).length === 1 && received.get(b).length === 1);
  assert.equal(received.get(b)[0], "synthetic public message");
  assert.equal(received.get(other).length, 0);
  const injection = '<img src=x onerror="alert(1)">';
  b.send(injection);
  await until(() => received.get(a).length === 2);
  assert.equal(received.get(a)[1], injection); // Browser renders textContent.
  const oversize = await connect(`large-${suffix}`);
  oversize.send("x".repeat(1025));
  assert.equal((await closed.get(oversize))[0], 1009);
  const binary = await connect(`binary-${suffix}`);
  binary.send(Buffer.from([1, 2, 3]));
  assert.equal((await closed.get(binary))[0], 1003);
  const empty = await connect(`empty-${suffix}`);
  empty.send(" \t");
  assert.equal((await closed.get(empty))[0], 1008);
  const flood = await connect(`flood-${suffix}`);
  for (let index = 0; index < 6; index++) flood.send(`synthetic ${index}`);
  assert.equal((await closed.get(flood))[0], 1008);
  await until(() => received.get(flood).length === 5);
  const capacity = `capacity-${suffix}`;
  const occupants = [];
  for (let index = 0; index < 16; index++) occupants.push(await connect(capacity));
  const overflow = new WebSocket(`${base.replace(/^http/, "ws")}/rooms/${capacity}/ws`, { origin });
  await new Promise((resolve, reject) => {
    overflow.on("error", () => {});
    overflow.once("unexpected-response", (_request, response) => {
      try { assert.equal(response.statusCode, 503); response.resume(); overflow.terminate(); resolve(); }
      catch (error) { reject(error); }
    });
    overflow.once("open", () => reject(new Error("Room capacity exceeded")));
  });
  occupants[0].close(1000);
  await closed.get(occupants[0]);
  await connect(capacity);
  // Capacity recovers after a clean close; no history is replayed on reconnect.
  b.close(1000);
  await closed.get(b);
  const replacement = await connect(`same-${suffix}`);
  assert.equal(received.get(replacement).length, 0);
  replacement.send("synthetic reconnect");
  await until(() => received.get(a).length === 3);
  assert.equal(received.get(other).length, 0);
  console.log("Public-room runtime checks passed: relay, room isolation, origin, limits, close/reconnect, routes.");
} finally {
  clearTimeout(watchdog);
  for (const socket of sockets) socket.terminate();
}
