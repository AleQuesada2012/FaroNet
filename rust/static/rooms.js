"use strict";
const byId = (id) => document.getElementById(id);
let socket;
function connected(value) {
  byId("message").disabled = byId("send").disabled = byId("disconnect").disabled = !value;
  byId("connect").disabled = byId("room").disabled = value;
}
byId("join").addEventListener("submit", (event) => {
  event.preventDefault();
  if (socket && socket.readyState < WebSocket.CLOSING) return;
  const room = byId("room").value;
  if (!/^[a-z0-9-]{1,32}$/.test(room)) return;
  const candidate = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/rooms/${room}/ws`);
  socket = candidate;
  byId("status").textContent = "Connecting…";
  candidate.addEventListener("open", () => {
    connected(true);
    byId("messages").replaceChildren();
    byId("status").textContent = `Connected to public room: ${room}`;
  });
  candidate.addEventListener("message", (event) => {
    const row = document.createElement("li");
    row.textContent = event.data;
    byId("messages").append(row);
    if (byId("messages").children.length > 100) byId("messages").firstElementChild.remove();
    row.scrollIntoView({ block: "nearest" });
  });
  candidate.addEventListener("close", (event) => {
    connected(false);
    byId("status").textContent = `Disconnected (${event.code}). Connect again to resume.`;
  });
  candidate.addEventListener("error", () => { byId("status").textContent = "Connection failed."; });
});
byId("disconnect").addEventListener("click", () => socket?.close(1000, "Leaving"));
byId("publish").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = byId("message").value;
  if (!socket || socket.readyState !== WebSocket.OPEN) return;
  if (!text.trim() || new TextEncoder().encode(text).length > 1024) {
    byId("status").textContent = "Use 1–1,024 UTF-8 bytes of public text.";
    return;
  }
  socket.send(text);
  byId("message").value = "";
});
