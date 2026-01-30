const STORAGE_LAST = "simco_csv_last_update";
const STORAGE_LAST_DATA = "simco_csv_last_data_ts";
const STORAGE_STATEMENTS_DIR = "simco_csv_statements_dir";
const STORAGE_RESOURCES_DIR = "simco_csv_resources_dir";
const STORAGE_REALM = "simco_csv_realm_id";
const UPDATE_INTERVAL_MS = 24 * 60 * 60 * 1000;

const STATEMENT_ENDPOINTS = [
  { name: "income", url: "https://www.simcompanies.com/csv/income-statement/", filename: "income.csv" },
  { name: "balance", url: "https://www.simcompanies.com/csv/balance-sheet/", filename: "balance.csv" },
  { name: "cashflow", url: "https://www.simcompanies.com/csv/cashflow-statement/", filename: "cashflow.csv" }
];

function formatTimestamp(ts) {
  if (!ts) return "Never";
  const d = new Date(ts);
  return d.toLocaleString();
}

function setStatus(text, cls) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.classList.remove("ok", "err");
  if (cls) el.classList.add(cls);
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

async function fetchJson(url) {
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) {
    throw new Error(`Fetch failed (${resp.status})`);
  }
  return resp.json();
}

function base64Encode(text) {
  return btoa(unescape(encodeURIComponent(text)));
}

function extractMaxTimestamp(csvText) {
  const lines = csvText.trim().split(/\r?\n/);
  if (lines.length < 2) return 0;
  const header = lines[0].split(",");
  const tsIndex = header.indexOf("Timestamp");
  if (tsIndex === -1) return 0;
  let maxTs = 0;
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    const raw = cols[tsIndex];
    if (!raw) continue;
    const ts = Date.parse(raw);
    if (!Number.isNaN(ts) && ts > maxTs) {
      maxTs = ts;
    }
  }
  return maxTs;
}

async function getStatementsDir() {
  const { statementsDir } = await chrome.storage.sync.get({ statementsDir: "" });
  return statementsDir || "";
}

async function getResourcesDir() {
  const { resourcesDir } = await chrome.storage.sync.get({ resourcesDir: "" });
  return resourcesDir || "";
}

async function setStatementsDir(statementsDir) {
  await chrome.storage.sync.set({ statementsDir });
}

async function setResourcesDir(resourcesDir) {
  await chrome.storage.sync.set({ resourcesDir });
}

async function getRealmId() {
  const { realmId } = await chrome.storage.sync.get({ realmId: 0 });
  return Number(realmId) || 0;
}

async function setRealmId(realmId) {
  await chrome.storage.sync.set({ realmId });
}

async function pickFolder(initialDir) {
  return chrome.runtime.sendMessage({
    type: "pickFolder",
    initialDir: initialDir || undefined
  });
}

async function saveFile(targetDir, filename, csvText) {
  const base64 = base64Encode(csvText);
  return chrome.runtime.sendMessage({
    type: "saveCsv",
    targetDir,
    filename,
    base64
  });
}

async function fetchResourceList(realmId) {
  let page = 1;
  const resources = [];
  while (true) {
    const url = `https://api.simcotools.com/v1/realms/${realmId}/resources?page=${page}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Resource list fetch failed (${resp.status})`);
    const data = await resp.json();
    resources.push(...(data.resources || []));
    const meta = data.metadata || {};
    if ((meta.currentPage || page) >= (meta.lastPage || page)) break;
    page += 1;
  }
  return resources;
}

async function fetchCompanyIds() {
  return fetchJson("https://www.simcompanies.com/api/v2/players/me/companies/");
}

async function getCompanyIdForRealm(realmId) {
  const companies = await fetchCompanyIds();
  const match = (companies || []).find((c) => Number(c.realmId) === Number(realmId));
  if (match && match.id) return match.id;
  if (companies && companies.length) return companies[0].id;
  throw new Error("No company id found");
}

async function saveStatementCsvs(statementsDir, companyId) {
  let latestDataTs = 0;
  const endpoints = [
    ...STATEMENT_ENDPOINTS,
    { name: "transactions", url: `https://www.simcompanies.com/csv/account-history/${companyId}/`, filename: "transactions.csv" }
  ];
  for (const endpoint of endpoints) {
    const csvText = await fetchCsv(endpoint.url);
    const dataTs = extractMaxTimestamp(csvText);
    if (dataTs > latestDataTs) {
      latestDataTs = dataTs;
    }
    const result = await saveFile(statementsDir, endpoint.filename, csvText);
    if (!result || !result.ok) {
      throw new Error(result?.error || `Save failed for ${endpoint.name}`);
    }
  }
  if (latestDataTs > 0) {
    await chrome.storage.local.set({ [STORAGE_LAST_DATA]: latestDataTs });
  }
}

async function saveInventoryJson(statementsDir, companyId) {
  const data = await fetchJson(`https://www.simcompanies.com/api/v3/resources/${companyId}/`);
  const result = await saveFile(statementsDir, "inventory.json", JSON.stringify(data, null, 2));
  if (!result || !result.ok) {
    throw new Error(result?.error || "Save failed for inventory.json");
  }
}

async function saveResourceCsvs(resourcesDir, realmId) {
  const resources = await fetchResourceList(realmId);
  const concurrency = 6;
  let index = 0;
  let completed = 0;

  async function worker() {
    while (index < resources.length) {
      const current = resources[index++];
      const url = `https://www.simcompanies.com/csv/resource-history/${current.id}/`;
      const csvText = await fetchCsv(url);
      const filename = `${current.id}.history.csv`;
      const result = await saveFile(resourcesDir, filename, csvText);
      if (!result || !result.ok) {
        throw new Error(result?.error || `Save failed for resource ${current.id}`);
      }
      completed += 1;
      setStatus(`Resources: ${completed}/${resources.length}`, "");
    }
  }

  const workers = Array.from({ length: concurrency }, () => worker());
  await Promise.all(workers);
}

async function updateCsvs() {
  const statementsDir = await getStatementsDir();
  const resourcesDir = await getResourcesDir();
  const realmId = await getRealmId();
  if (!statementsDir) throw new Error("Choose a statements folder first");
  if (!resourcesDir) throw new Error("Choose a resources folder first");

  const companyId = await getCompanyIdForRealm(realmId);

  await saveStatementCsvs(statementsDir, companyId);
  await saveInventoryJson(statementsDir, companyId);
  await saveResourceCsvs(resourcesDir, realmId);

  const now = Date.now();
  await chrome.storage.local.set({ [STORAGE_LAST]: now });
  return now;
}

async function loadUi() {
  const { [STORAGE_LAST]: lastTs, [STORAGE_LAST_DATA]: lastDataTs } = await chrome.storage.local.get({
    [STORAGE_LAST]: 0,
    [STORAGE_LAST_DATA]: 0
  });
  const statementsDir = await getStatementsDir();
  const resourcesDir = await getResourcesDir();
  const realmId = await getRealmId();
  document.getElementById("last").textContent = `Last update: ${formatTimestamp(lastTs)}`;
  document.getElementById("targetStatements").textContent = statementsDir ? `Statements target: ${statementsDir}` : "Statements target: Not set";
  document.getElementById("targetResources").textContent = resourcesDir ? `Resources target: ${resourcesDir}` : "Resources target: Not set";
  document.getElementById("realm").value = String(realmId);
  return { lastTs, lastDataTs, statementsDir, resourcesDir, realmId };
}

async function maybeAutoUpdate(lastDataTs, statementsDir, resourcesDir) {
  if (!statementsDir || !resourcesDir) return;
  if (!lastDataTs || Date.now() - lastDataTs > UPDATE_INTERVAL_MS) {
    try {
      setStatus("Auto updating...", "");
      const ts = await updateCsvs();
      document.getElementById("last").textContent = `Last update: ${formatTimestamp(ts)}`;
      setStatus("Updated", "ok");
    } catch (err) {
      setStatus(err.message || "Update failed", "err");
    }
  }
}

(async () => {
  const { lastDataTs, statementsDir, resourcesDir } = await loadUi();
  await maybeAutoUpdate(lastDataTs, statementsDir, resourcesDir);

  document.getElementById("realm").addEventListener("change", async (e) => {
    await setRealmId(Number(e.target.value));
    setStatus("Realm saved", "ok");
  });

  document.getElementById("pickStatements").addEventListener("click", async () => {
    try {
      const result = await pickFolder(statementsDir);
      if (result && result.ok && result.folder) {
        await setStatementsDir(result.folder);
        document.getElementById("targetStatements").textContent = `Statements target: ${result.folder}`;
        setStatus("Statements folder set", "ok");
        return;
      }
      if (result && result.ok && !result.folder) {
        setStatus("Canceled", "");
        return;
      }
      setStatus(result?.error || "Folder pick failed", "err");
    } catch (err) {
      setStatus(err.message || "Folder pick failed", "err");
    }
  });

  document.getElementById("pickResources").addEventListener("click", async () => {
    try {
      const result = await pickFolder(resourcesDir);
      if (result && result.ok && result.folder) {
        await setResourcesDir(result.folder);
        document.getElementById("targetResources").textContent = `Resources target: ${result.folder}`;
        setStatus("Resources folder set", "ok");
        return;
      }
      if (result && result.ok && !result.folder) {
        setStatus("Canceled", "");
        return;
      }
      setStatus(result?.error || "Folder pick failed", "err");
    } catch (err) {
      setStatus(err.message || "Folder pick failed", "err");
    }
  });

  document.getElementById("update").addEventListener("click", async () => {
    try {
      setStatus("Updating...", "");
      const ts = await updateCsvs();
      document.getElementById("last").textContent = `Last update: ${formatTimestamp(ts)}`;
      setStatus("Updated", "ok");
    } catch (err) {
      setStatus(err.message || "Update failed", "err");
    }
  });
})();
