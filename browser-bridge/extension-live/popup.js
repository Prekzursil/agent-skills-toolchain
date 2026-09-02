const $ = (id) => document.getElementById(id);
const LOCKED_PORT = 8790;

async function refresh() {
  const { token } = await chrome.storage.local.get({ token: "" });
  $("port").textContent = String(LOCKED_PORT);
  $("token").value = token;

  chrome.runtime.sendMessage({ type: "getStatus" }, (status) => {
    const connected = !!status?.connected;
    $("dot").classList.toggle("on", connected);
    $("state").textContent = connected ? "Connected to LIVE hub" : "Waiting for LIVE hub…";
    $("attached").textContent = status?.attachedTabId
      ? `Controlling tab ${status.attachedTabId}.`
      : "No tab is being controlled.";
  });
}

$("save").addEventListener("click", async () => {
  await chrome.storage.local.set({
    port: LOCKED_PORT,
    token: $("token").value.trim(),
    enabled: true,
  });
  chrome.runtime.sendMessage({ type: "reconnect" }, () => setTimeout(refresh, 400));
});

refresh();
setInterval(refresh, 1500);
