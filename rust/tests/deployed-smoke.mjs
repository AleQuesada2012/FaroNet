// Light check of a deployed Worker: about ten requests and one synthetic public
// message in a throwaway room (it expires from the feed within 24 hours).
// Usage: npm run smoke -- https://faronet-edge.<subdomain>.workers.dev
import assert from "node:assert/strict";
import { once } from "node:events";
import WebSocket from "ws";

const base = (process.argv[2] || process.env.FARONET_EDGE_URL || "").replace(/\/$/, "");
const url = URL.canParse(base) ? new URL(base) : null;
if (!url || url.protocol !== "https:" || url.pathname !== "/") {
  throw new Error("Pass the deployed https origin, e.g. https://faronet-edge.example.workers.dev");
}
const watchdog = setTimeout(() => { console.error("Smoke test timed out"); process.exit(1); }, 30_000);
watchdog.unref();
const room = `smoke-${Date.now().toString(36)}`;
const text = `synthetic smoke test ${room}`;
const socketUrl = `${base.replace(/^https/, "wss")}/rooms/${room}/ws`;

assert.equal((await fetch(`${base}/health`)).status, 200);
const landing = await fetch(`${base}/`);
assert.equal(landing.status, 200);
assert.match(await landing.text(), /FaroNet edge/);
const page = await fetch(`${base}/rooms`);
assert.equal(page.status, 200, "Public rooms are disabled; deploy with npm run deploy");
assert.match(page.headers.get("content-security-policy"), /frame-ancestors 'none'/);

const denied = new WebSocket(socketUrl, { origin: "https://invalid.example" });
denied.on("error", () => {});
const [, refusal] = await once(denied, "unexpected-response");
assert.equal(refusal.statusCode, 403);
refusal.resume();
denied.terminate();

const ws = new WebSocket(socketUrl, { origin: url.origin });
await once(ws, "open");
const echoed = once(ws, "message");
ws.send(text);
assert.equal((await echoed)[0].toString(), text);
ws.close(1000);

const feed = await fetch(`${base}/rooms/${room}/feed.atom`);
assert.equal(feed.status, 200);
assert.equal(feed.headers.get("content-type"), "application/atom+xml; charset=utf-8");
assert.ok((await feed.text()).includes(text));
console.log(`Deployed smoke test passed for ${url.origin}: health, landing, rooms, origin check, relay, feed.`);
clearTimeout(watchdog);
