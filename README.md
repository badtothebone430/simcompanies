# SimCompanies Analyzer Bundle (DevTech Industries)

This bundle includes:
- `bin/` desktop analyzers (Income, Balance, Cashflow, and Income Beta)
- `simcompanies-extension/` browser extension
- `simcompanies-native-helper/` native helper for folder picker + file writes

Below are full install + usage steps.

---

## 1) Desktop App Setup (BIN)

### Requirements
- Windows 10/11
- Python 3.10+ installed and added to PATH

### Install Python packages
Open PowerShell in the bundle root (right click in folder and select 'Open in Terminal' and run:

```powershell
powershell
python -m pip install --upgrade pip
python -m pip install PySide6 pandas
```

### Run the apps
Notes:
- The apps default to reading CSVs in `bin/userdata/`.
- Paths you select are saved in `bin/config/`.
- Realm selector is available in Income Beta (Magnates / Entrepreneurs).

### Friendly launchers (optional)
Two launchers are included at the bundle root:
- `Income Statement (Beta).bat`
- `Master Analyzer.bat`

Double‑click to run without opening a terminal.

---

## 2) Extension + Native Helper Setup

The extension handles downloading CSVs and `inventory.json` directly into `bin/userdata/` (and resource history into `bin/userdata/resources/`).

### 2.1 Install the Native Helper (folder picker + file write)

1) Go to `simcompanies-native-helper/`.
2) Edit `com.simcompanies.csv_helper.json`:
   - Update `path` to the full path of `native_helper.exe`.
   - Update `allowed_origins` with your extension ID:
     - Open `chrome://extensions` (or `edge://extensions`)
     - Enable Developer mode
     - Find **SimCompanies CSV Helper** and copy the ID
     - Add it to `allowed_origins` like: `chrome-extension://<ID>/`
3) Run the install script:

```powershell
cd .\simcompanies-native-helper
.\install.ps1
```

If prompted by Windows, allow it.

### 2.2 Install the Extension

1) Open Edge or Chrome.
2) Enable **Developer mode** on the Extensions page.
3) Click **Load unpacked** and select `simcompanies-extension/`.
4) Open SimCompanies in the browser.

### 2.3 Use the Extension

1) Click the extension icon.
2) Pick the **userdata** folder (default: `bin/userdata/`).
3) Pick the **resources** folder (default: `bin/userdata/resources/`).
4) Choose realm (Magnates / Entrepreneurs).
5) Click **Download CSVs**.

What it downloads:
- `income.csv`, `balance.csv`, `cashflow.csv`
- `transactions.csv` (account history)
- `inventory.json`
- Resource histories as `{resourceId}.history.csv` into `userdata/resources/`

---

## 3) Program Tutorial (Quick Start)

### Income / Balance / Cashflow
1) Open the app from `bin/`.
2) Confirm file paths (or click Select buttons).
3) Click **Compute**.
4) Use **Export PNG** to save a report.

### Income Beta (Proprietary)
1) Open `INCOME_BETA.pyw`.
2) Ensure paths point to:
   - `bin/userdata/income.csv`
   - `bin/userdata/balance.csv`
   - `bin/userdata/transactions.csv`
   - `bin/userdata/resources/`
   - `bin/userdata/inventory.json` (downloaded by extension)
3) Select realm.
4) Click **Compute statement**.
5) A window opens with **Income** and **Cashflow** tabs.
6) Export the current tab to PNG.

---

## 4) Troubleshooting

### App won’t launch or missing modules
Run:
```powershell
python -m pip install PySide6 pandas
```

### Extension downloads fail
- Make sure the native helper is installed (Step 2.1).
- Make sure you are logged in to SimCompanies in the same browser.
- Reopen the browser and retry.

### Files not updating in the app
Confirm the file paths at the top of each app. Paths are saved in:
- `bin/config/`

---

## Support
DevTech Industries
