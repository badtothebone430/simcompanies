const STORAGE_KEY = "simco_csv_last_update";
const UPDATE_INTERVAL_MS = 24 * 60 * 60 * 1000;
const TARGET_DIR_KEY = "simco_csv_target_dir";

const ENDPOINTS = [
  { name: "income", url: "https://www.simcompanies.com/csv/income-statement/", filename: "income.csv" },
  { name: "balance", url: "https://www.simcompanies.com/csv/balance-sheet/", filename: "balance.csv" },
  { name: "cashflow", url: "https://www.simcompanies.com/csv/cashflow-statement/", filename: "cashflow.csv" }
];

function formatTimestamp(ts) {
  if (!ts) return "Never";
  const d = new Date(ts);
  return d.toLocaleString();
}

function shouldAutoUpdate(lastTs) {
  if (!lastTs) return true;
  return Date.now() - lastTs > UPDATE_INTERVAL_MS;
}

function base64Encode(text) {
  return btoa(unescape(encodeURIComponent(text)));
}

async function fetchCsv(url) {
  const resp = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "upgrade-insecure-requests": "1"
    }
  });
  if (!resp.ok) {
    throw new Error(`Fetch failed (${resp.status})`);
  }
  return resp.text();
}

function setStatus(el, text, cls) {
  el.textContent = text;
  el.classList.remove("simco-ok", "simco-error");
  if (cls) el.classList.add(cls);
}

async function getTargetDir() {
  const { targetDir } = await chrome.storage.sync.get({ targetDir: "" });
  return targetDir || "";
}

async function pickTargetDir() {
  const current = await getTargetDir();
  const result = await chrome.runtime.sendMessage({
    type: "pickFolder",
    initialDir: current || undefined
  });
  if (result && result.ok && result.folder) {
    await chrome.storage.sync.set({ targetDir: result.folder });
    return result.folder;
  }
  if (result && result.ok && !result.folder) {
    throw new Error("Folder selection canceled");
  }
  throw new Error(result?.error || "Failed to pick folder");
}

async function downloadCsvs(statusEl) {
  setStatus(statusEl, "Downloading CSVs...");
  const targetDir = await getTargetDir();
  if (!targetDir) {
    throw new Error("Pick a target folder first");
  }
  for (const endpoint of ENDPOINTS) {
    const csvText = await fetchCsv(endpoint.url);
    const base64 = base64Encode(csvText);
    const result = await chrome.runtime.sendMessage({
      type: "saveCsv",
      targetDir,
      filename: endpoint.filename,
      base64
    });
    if (!result || !result.ok) {
      throw new Error(result?.error || `Save failed for ${endpoint.name}`);
    }
  }
  const now = Date.now();
  localStorage.setItem(STORAGE_KEY, String(now));
  setStatus(statusEl, `Updated: ${formatTimestamp(now)}`, "simco-ok");
}

function createPanel() {
  const panel = document.createElement("div");
  panel.id = "simco-csv-panel";

  const title = document.createElement("h4");
  title.textContent = "SimCompanies CSV";
  panel.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "simco-meta";
  const lastTs = Number(localStorage.getItem(STORAGE_KEY) || 0);
  meta.textContent = `Last update: ${formatTimestamp(lastTs)}`;
  panel.appendChild(meta);

  const dir = document.createElement("div");
  dir.className = "simco-meta";
  dir.textContent = "Target: not set";
  panel.appendChild(dir);

  const pickBtn = document.createElement("button");
  pickBtn.textContent = "Choose Folder";
  panel.appendChild(pickBtn);

  const btn = document.createElement("button");
  btn.textContent = "Update CSVs";
  panel.appendChild(btn);

  const status = document.createElement("div");
  status.className = "simco-status";
  panel.appendChild(status);

  pickBtn.addEventListener("click", async () => {
    pickBtn.disabled = true;
    try {
      const folder = await pickTargetDir();
      dir.textContent = `Target: ${folder}`;
      setStatus(status, "Folder set", "simco-ok");
    } catch (err) {
      setStatus(status, err.message, "simco-error");
    } finally {
      pickBtn.disabled = false;
    }
  });

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await downloadCsvs(status);
      meta.textContent = `Last update: ${formatTimestamp(Date.now())}`;
    } catch (err) {
      setStatus(status, err.message, "simco-error");
    } finally {
      btn.disabled = false;
    }
  });

  return { panel, status, meta, dir };
}

(async () => {
  const { panel, status, meta, dir } = createPanel();
  document.body.appendChild(panel);

  const targetDir = await getTargetDir();
  if (targetDir) {
    dir.textContent = `Target: ${targetDir}`;
  }

  const lastTs = Number(localStorage.getItem(STORAGE_KEY) || 0);
  if (shouldAutoUpdate(lastTs)) {
    try {
      await downloadCsvs(status);
      meta.textContent = `Last update: ${formatTimestamp(Date.now())}`;
    } catch (err) {
      setStatus(status, err.message, "simco-error");
    }
  }
})();
