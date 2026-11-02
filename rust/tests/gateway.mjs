// Run against a freshly started `npm run dev:gateway` on this Mac. The secret
// below is a local test value, never a deployed one. Only synthetic data is sent.
import assert from "node:assert/strict";
import { createHash, createHmac, generateKeyPairSync, randomBytes, sign as edSign } from "node:crypto";
import { once } from "node:events";
import WebSocket from "ws";

export const TEST_SECRET = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c4b5a69788796a5b4c3d2e1f0";
const base = process.env.FARONET_TEST_URL || "http://127.0.0.1:8787";
if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(base).hostname)) {
  throw new Error("This test is restricted to a local Worker");
}
const audience = "faronet-edge";
const keyId = "gateway-1";
const watchdog = setTimeout(() => { console.error("Gateway runtime checks timed out"); process.exit(1); }, 20_000);
watchdog.unref();

// RFC FN-1 Section 6, same bytes as python/src/faronet/gateway/auth.py.
function sign({ method, path, body = Buffer.alloc(0), nonce = randomBytes(16).toString("hex"),
                timestamp = Math.floor(Date.now() / 1000), key = keyId, secret = TEST_SECRET }) {
  const digest = createHash("sha256").update(body).digest("hex");
  const input = `FARONET-GATEWAY-HMAC-V1\n${audience}\n${key}\n${method}\n${path}\n${timestamp}\n${nonce}\n${digest}\n`;
  const signature = createHmac("sha256", Buffer.from(secret, "hex")).update(input).digest("hex");
  return {
    method,
    body: method === "GET" ? undefined : body,
    headers: {
      "X-FaroNet-Key": key, "X-FaroNet-Timestamp": String(timestamp),
      "X-FaroNet-Nonce": nonce, "X-FaroNet-Signature": signature,
    },
  };
}

async function send(path, options) {
  const response = await fetch(`${base}${path}`, sign({ path, ...options }));
  return { status: response.status, body: Buffer.from(await response.arrayBuffer()) };
}

const topic = `gw-${randomBytes(4).toString("hex")}`;
const ws = new WebSocket(`${base.replace(/^http/, "ws")}/rooms/${topic}/ws`, { origin: new URL(base).origin });
const received = [];
ws.on("message", (data) => received.push(data.toString()));
try {
  await once(ws, "open");
  const relayPath = `/gateway/rooms/${topic}`;
  const text = Buffer.from("aviso público desde la mesh");

  // Unsigned, malformed, wrong method, query string, unknown route.
  assert.equal((await fetch(`${base}${relayPath}`, { method: "POST", body: text })).status, 400);
  assert.equal((await fetch(`${base}${relayPath}`)).status, 405);
  assert.equal((await fetch(`${base}${relayPath}?x=1`, sign({ method: "POST", path: relayPath, body: text }))).status, 400);
  assert.equal((await fetch(`${base}/gateway/unknown`)).status, 404);

  // Wrong secret, wrong key, stale clock: all 401.
  assert.equal((await send(relayPath, { method: "POST", body: text, secret: "11".repeat(32) })).status, 401);
  assert.equal((await send(relayPath, { method: "POST", body: text, key: "gateway-2" })).status, 401);
  assert.equal((await send(relayPath, { method: "POST", body: text, timestamp: Math.floor(Date.now() / 1000) - 120 })).status, 401);

  // An invalid body is rejected before the nonce is claimed, so the nonce stays usable.
  const nonce = randomBytes(16).toString("hex");
  assert.equal((await send(relayPath, { method: "POST", body: Buffer.from("bad\u0000text"), nonce })).status, 400);
  assert.equal((await send(relayPath, { method: "POST", body: text, nonce })).status, 202);
  const end = Date.now() + 2000;
  while (!received.includes(text.toString()) && Date.now() < end) await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(received, [text.toString()]);
  const feed = await (await fetch(`${base}/rooms/${topic}/feed.atom`)).text();
  assert.match(feed, /aviso público desde la mesh/);

  // Replaying the exact request (same nonce) is refused.
  const replay = sign({ method: "POST", path: relayPath, body: text });
  assert.equal((await fetch(`${base}${relayPath}`, replay)).status, 202);
  assert.equal((await fetch(`${base}${relayPath}`, replay)).status, 409);

  // Dead drop: write once, read once, then gone; size is exact.
  const slot = createHash("sha256").update(randomBytes(32)).digest("hex");
  const dropPath = `/gateway/drop/${slot}`;
  const blob = randomBytes(1024);
  assert.equal((await send(dropPath, { method: "POST", body: randomBytes(1023) })).status, 400);
  assert.equal((await send(dropPath, { method: "GET" })).status, 404);
  assert.equal((await send(dropPath, { method: "POST", body: blob })).status, 201);
  assert.equal((await send(dropPath, { method: "POST", body: randomBytes(1024) })).status, 409);
  const taken = await send(dropPath, { method: "GET" });
  assert.equal(taken.status, 200);
  assert.ok(taken.body.equals(blob));
  assert.equal((await send(dropPath, { method: "GET" })).status, 404);
  assert.equal((await send(`/gateway/drop/${slot.toUpperCase()}`, { method: "GET" })).status, 404);
  // Directory replica: RFC 5.2 entries signed here with Node's Ed25519.
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  const verifyKey = Buffer.from(publicKey.export({ format: "jwk" }).x, "base64url");
  const entry = (issued, alias = "gw-test") => {
    const times = Buffer.alloc(16);
    times.writeBigUInt64BE(BigInt(issued), 0);
    times.writeBigUInt64BE(BigInt(issued + 3600), 8);
    const signed = Buffer.concat([
      Buffer.from("FARONET-DIRECTORY-V1"), createHash("sha256").update(verifyKey).digest().subarray(0, 16),
      verifyKey, randomBytes(32), times, Buffer.from([alias.length]), Buffer.from(alias),
    ]);
    return Buffer.concat([signed, edSign(null, signed, privateKey)]);
  };
  const now = Math.floor(Date.now() / 1000);
  const first = entry(now - 30);
  assert.equal((await send("/gateway/directory", { method: "POST", body: first })).status, 201);
  assert.equal((await send("/gateway/directory", { method: "POST", body: first })).status, 200);
  // Same issue time, different bytes (another box key): refused, first kept.
  assert.equal((await send("/gateway/directory", { method: "POST", body: entry(now - 30) })).status, 409);
  assert.equal((await send("/gateway/directory", { method: "POST", body: entry(now - 60) })).status, 409);
  const tampered = Buffer.from(entry(now));
  tampered[117] ^= 1; // first alias byte, after the fixed 117-byte header
  assert.equal((await send("/gateway/directory", { method: "POST", body: tampered })).status, 400);
  const forged = Buffer.from(entry(now));
  forged[20] ^= 1; // Node ID no longer matches the key
  assert.equal((await send("/gateway/directory", { method: "POST", body: forged })).status, 400);
  const newer = entry(now);
  assert.equal((await send("/gateway/directory", { method: "POST", body: newer })).status, 201);
  const listing = await fetch(`${base}/directory`);
  assert.equal(listing.status, 200);
  const { version, entries } = await listing.json();
  assert.equal(version, 1);
  assert.ok(entries.includes(newer.toString("hex")));
  assert.ok(!entries.includes(first.toString("hex")));
  assert.equal((await fetch(`${base}/directory`, { method: "POST" })).status, 405);
  assert.equal((await fetch(`${base}/gateway/directory`)).status, 405);
  console.log("Gateway runtime checks passed: auth, replay, relay into a topic and its feed, dead drop, directory replica.");
} finally {
  ws.terminate();
}
