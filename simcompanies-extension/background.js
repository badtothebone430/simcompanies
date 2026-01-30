const NATIVE_HOST = "com.simcompanies.csv_helper";

function sendNative(message) {
  return new Promise((resolve) => {
    const port = chrome.runtime.connectNative(NATIVE_HOST);
    port.onMessage.addListener((response) => resolve(response));
    port.onDisconnect.addListener(() => {
      if (chrome.runtime.lastError) {
        resolve({ ok: false, error: chrome.runtime.lastError.message });
      }
    });
    port.postMessage(message);
  });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || !msg.type) return;

  if (msg.type === "pickFolder") {
    sendNative({ type: "pickFolder", initialDir: msg.initialDir }).then(sendResponse);
    return true;
  }

  if (msg.type === "saveCsv") {
    sendNative({
      type: "saveCsv",
      targetDir: msg.targetDir,
      filename: msg.filename,
      base64: msg.base64
    }).then(sendResponse);
    return true;
  }
});
