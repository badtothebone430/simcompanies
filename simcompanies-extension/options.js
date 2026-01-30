const TARGET_DIR_KEY = "simco_csv_target_dir";

function setStatus(text) {
  const el = document.getElementById("status");
  el.textContent = text;
  setTimeout(() => { el.textContent = ""; }, 2000);
}

async function load() {
  const { targetDir } = await chrome.storage.sync.get({ targetDir: "" });
  document.getElementById("path").textContent = targetDir || "Not set";
}

async function pickFolder() {
  const result = await chrome.runtime.sendMessage({ type: "pickFolder" });
  if (result && result.ok && result.folder) {
    await chrome.storage.sync.set({ targetDir: result.folder });
    document.getElementById("path").textContent = result.folder;
    setStatus("Saved");
    return;
  }
  if (result && result.ok && !result.folder) {
    setStatus("Canceled");
    return;
  }
  setStatus(result?.error || "Failed to pick folder");
}

async function clearFolder() {
  await chrome.storage.sync.set({ targetDir: "" });
  document.getElementById("path").textContent = "Not set";
  setStatus("Cleared");
}

document.getElementById("pick").addEventListener("click", pickFolder);
document.getElementById("clear").addEventListener("click", clearFolder);
load();
