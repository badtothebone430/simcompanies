import sys
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import urllib.request
import urllib.parse

import pandas as pd

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QPropertyAnimation, QRect
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QLineEdit, QTableView, QGroupBox, QToolButton, QFrame, QSizePolicy,
    QDialog, QComboBox, QTabWidget
)
from PySide6.QtGui import QFont


PATENT_VALUES = {
    "Plant": 1368.0,
    "Energy": 2160.0,
    "Mining": 2160.0,
    "Electronics": 2592.0,
    "Breeding": 1584.0,
    "Chemistry": 1296.0,
    "Software": 1260.0,
    "Automotive": 1440.0,
    "Fashion": 720.0,
    "Aerospace": 2440.80,
    "Materials": 1800.0,
    "Recipes": 1728.0,
}


class StatementModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if self._df is None else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if self._df is None else self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        row = index.row()
        col = index.column()
        section = self._df.iat[row, 0]
        item = self._df.iat[row, 1]
        val = self._df.iat[row, 2]
        is_header = isinstance(section, str) and section != "" and item == "" and val == ""
        is_sep = isinstance(item, str) and item in ("-", "=")
        is_total = isinstance(item, str) and ("TOTAL" in item or item == "Net income")

        if role == Qt.FontRole and (is_header or is_total):
            font = QFont()
            if font.pointSize() <= 0:
                font.setPointSize(10)
            font.setBold(True)
            return font

        if role == Qt.DisplayRole:
            if is_sep:
                return "-" * 28 if item == "-" else "=" * 28
            if col == 0:
                return str(section)
            if col == 1:
                return str(item)
            if val == "":
                return ""
            try:
                return f"{float(val):,.2f}"
            except Exception:
                return str(val)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if self._df is None or role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


class GenericTableModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if self._df is None else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if self._df is None else self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        if role == Qt.DisplayRole:
            val = self._df.iat[index.row(), index.column()]
            if isinstance(val, (int, float)):
                return f"{float(val):,.2f}"
            return "" if pd.isna(val) else str(val)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if self._df is None or role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


class CollapsibleBox(QWidget):
    def __init__(self, title: str, content: QWidget, expanded: bool = True):
        super().__init__()
        self.toggle_button = QToolButton(text=title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.clicked.connect(self.on_toggled)

        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(content)
        self.content_area.setLayout(content_layout)

        self.anim = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.anim.setDuration(120)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)
        self.setLayout(layout)

        self.set_expanded(expanded, animate=False)

    def on_toggled(self, checked: bool):
        self.set_expanded(checked, animate=True)

    def set_expanded(self, expanded: bool, animate: bool):
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        end_height = 16777215 if expanded else 0
        if animate:
            self.anim.stop()
            self.anim.setStartValue(self.content_area.maximumHeight())
            self.anim.setEndValue(end_height)
            self.anim.start()
        else:
            self.content_area.setMaximumHeight(end_height)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimCompanies Income Statement (Proprietary)")
        self.resize(1000, 760)

        self.config_path = os.path.join(os.path.dirname(__file__), "config", "income_beta_paths.json")
        self.config_data = self.load_config()

        self.income_path = QLineEdit()
        self.balance_path = QLineEdit()
        self.account_path = QLineEdit()
        self.resources_dir = QLineEdit()
        self.realm_select = QComboBox()
        self.realm_select.addItem("Magnates (realm 0)", 0)
        self.realm_select.addItem("Entrepreneurs (realm 1)", 1)
        self.realm_select.currentIndexChanged.connect(self.save_realm_selection)

        self.btn_income = QPushButton("Select income.csv")
        self.btn_balance = QPushButton("Select balance.csv")
        self.btn_account = QPushButton("Select account history CSV")
        self.btn_resources = QPushButton("Select resource history folder")
        self.btn_compute = QPushButton("Compute statement")

        self.btn_income.clicked.connect(self.pick_income)
        self.btn_balance.clicked.connect(self.pick_balance)
        self.btn_account.clicked.connect(self.pick_account)
        self.btn_resources.clicked.connect(self.pick_resources_dir)
        self.btn_compute.clicked.connect(self.compute_statement)

        self.btn_export_png = QPushButton("Export statement PNG")
        self.btn_export_png.clicked.connect(self.export_statement_png)

        inputs = QGroupBox("Inputs")
        grid = QGridLayout()
        grid.addWidget(QLabel("Income baseline"), 0, 0)
        grid.addWidget(self.income_path, 0, 1)
        grid.addWidget(self.btn_income, 0, 2)
        grid.addWidget(QLabel("Balance baseline"), 1, 0)
        grid.addWidget(self.balance_path, 1, 1)
        grid.addWidget(self.btn_balance, 1, 2)
        grid.addWidget(QLabel("Account history"), 2, 0)
        grid.addWidget(self.account_path, 2, 1)
        grid.addWidget(self.btn_account, 2, 2)
        grid.addWidget(QLabel("Resource history folder"), 3, 0)
        grid.addWidget(self.resources_dir, 3, 1)
        grid.addWidget(self.btn_resources, 3, 2)
        grid.addWidget(QLabel("Realm"), 4, 0)
        grid.addWidget(self.realm_select, 4, 1)
        grid.addWidget(self.btn_export_png, 5, 1)
        grid.addWidget(self.btn_compute, 5, 2)
        grid.setColumnStretch(1, 1)
        inputs.setLayout(grid)

        self.table = QTableView()
        self.model = StatementModel(pd.DataFrame(columns=["Section", "Item", "Value"]))
        self.table.setModel(self.model)
        self.cashflow_table = QTableView()
        self.cashflow_model = StatementModel(pd.DataFrame(columns=["Section", "Item", "Value"]))
        self.cashflow_table.setModel(self.cashflow_model)
        self.statement_window = None
        self.statement_tabs = None

        root = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(inputs)
        layout.addWidget(CollapsibleBox("Statement", self.table, expanded=True))
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.apply_dark_theme()
        self.apply_saved_paths()

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QWidget { background: #0f1115; color: #e6e6e6; font-size: 12px; }
            QGroupBox { border: 1px solid #2a2f3a; border-radius: 12px; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #aab2c0; }
            QPushButton {
                background: #1b2130; border: 1px solid #2a3142; border-radius: 10px;
                padding: 8px 10px; font-weight: 600;
            }
            QPushButton:hover { background: #222a3c; }
            QLineEdit {
                background: #121620; border: 1px solid #2a3142; border-radius: 10px; padding: 8px 10px;
            }
            QTableView {
                background: #0b0d12; border: 1px solid #2a2f3a; border-radius: 12px;
                gridline-color: #232834;
            }
            QHeaderView::section {
                background: #121620; border: 0; border-bottom: 1px solid #232834;
                padding: 8px; color: #b7c0ce; font-weight: 700;
            }
            QTableView::item { padding: 6px; }
            QTableView::item:selected { background: #2a3142; }
        """)

    def pick_income(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select income.csv", "", "CSV Files (*.csv)")
        if path:
            self.income_path.setText(path)
            self.config_data["income_path"] = path
            self.save_config()

    def pick_balance(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select balance.csv", "", "CSV Files (*.csv)")
        if path:
            self.balance_path.setText(path)
            self.config_data["balance_path"] = path
            self.save_config()

    def pick_account(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select account history CSV", "", "CSV Files (*.csv)")
        if path:
            self.account_path.setText(path)
            self.config_data["account_path"] = path
            self.save_config()

    def pick_resources_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select resource history folder")
        if path:
            self.resources_dir.setText(path)
            self.config_data["resources_dir"] = path
            self.save_config()

    def load_config(self) -> dict:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception:
            pass

    def apply_saved_paths(self):
        base = os.path.dirname(__file__)
        default_income = os.path.join(base, "userdata", "income.csv")
        default_balance = os.path.join(base, "userdata", "balance.csv")
        default_transactions = os.path.join(base, "userdata", "transactions.csv")
        default_resources = os.path.join(base, "userdata", "resources")

        if self.config_data.get("income_path") and os.path.isfile(self.config_data["income_path"]):
            self.income_path.setText(self.config_data["income_path"])
        else:
            self.income_path.setText(default_income)

        if self.config_data.get("balance_path") and os.path.isfile(self.config_data["balance_path"]):
            self.balance_path.setText(self.config_data["balance_path"])
        else:
            self.balance_path.setText(default_balance)

        if self.config_data.get("account_path") and os.path.isfile(self.config_data["account_path"]):
            self.account_path.setText(self.config_data["account_path"])
        else:
            self.account_path.setText(default_transactions)

        if self.config_data.get("resources_dir") and os.path.isdir(self.config_data["resources_dir"]):
            self.resources_dir.setText(self.config_data["resources_dir"])
        else:
            self.resources_dir.setText(default_resources)
        if "realm_id" in self.config_data:
            realm_id = int(self.config_data["realm_id"])
            idx = self.realm_select.findData(realm_id)
            if idx >= 0:
                self.realm_select.setCurrentIndex(idx)

    def save_realm_selection(self):
        self.config_data["realm_id"] = int(self.realm_select.currentData())
        self.save_config()

    def compute_statement(self):
        try:
            cutoff = self.get_income_cutoff()
            account_df = self.load_account_history(cutoff)
            resource_df = self.load_resource_history(cutoff)
            bal_cutoff, bal_allow = self.get_balance_cutoff_and_allowance()
            inventory = self.load_inventory_snapshot()
            valuation_diff = self.compute_valuation_allowance_diff(
                inventory, bal_allow
            )
            statement = self.build_statement(account_df, resource_df, valuation_diff)
            self.model.set_df(statement)
            cashflow = self.build_cashflow(account_df)
            self.cashflow_model.set_df(cashflow)
            self.table.resizeColumnsToContents()
            self.cashflow_table.resizeColumnsToContents()
            self.show_statement_window()
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    def get_income_cutoff(self) -> pd.Timestamp:
        path = self.income_path.text().strip()
        if not path or not os.path.isfile(path):
            raise ValueError("Select income.csv baseline first.")
        df = pd.read_csv(path)
        if "Timestamp" not in df.columns:
            raise ValueError("income.csv missing Timestamp column.")
        ts = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
        cutoff = ts.max()
        if pd.isna(cutoff):
            raise ValueError("Unable to determine cutoff from income.csv.")
        return cutoff

    def get_balance_cutoff_and_allowance(self) -> tuple[pd.Timestamp, float]:
        path = self.balance_path.text().strip()
        if not path or not os.path.isfile(path):
            raise ValueError("Select balance.csv baseline.")
        df = pd.read_csv(path)
        if "Timestamp" not in df.columns:
            raise ValueError("balance.csv missing Timestamp column.")
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
        latest = df["Timestamp"].max()
        if pd.isna(latest):
            raise ValueError("Unable to determine cutoff from balance.csv.")
        row = df.loc[df["Timestamp"] == latest].iloc[0]
        allowance_col = None
        for col in df.columns:
            if "valuation allowance" in col.lower():
                allowance_col = col
                break
        if allowance_col is None:
            raise ValueError("balance.csv missing valuation allowance column.")
        allowance = float(pd.to_numeric(row[allowance_col], errors="coerce") or 0.0)
        return latest, allowance

    def load_inventory_snapshot(self) -> list[dict]:
        base = os.path.dirname(__file__)
        default_path = os.path.join(base, "userdata", "inventory.json")
        path = self.config_data.get("inventory_path", default_path)
        if not os.path.isfile(path):
            raise ValueError("inventory.json not found. Download it via the extension.")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("inventory.json is not a list.")
            return data
        except Exception as e:
            raise ValueError(f"Failed to read inventory.json: {e}")

    def load_account_history(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        path = self.account_path.text().strip()
        if not path or not os.path.isfile(path):
            raise ValueError("Select account history CSV.")
        df = pd.read_csv(path)
        if "Timestamp" not in df.columns:
            raise ValueError("Account history missing Timestamp column.")
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
        df = df[df["Timestamp"] > cutoff]
        if "Money" in df.columns:
            df["Money"] = pd.to_numeric(df["Money"], errors="coerce").fillna(0.0)
        return df

    def load_resource_history(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        folder = self.resources_dir.text().strip()
        if not folder or not os.path.isdir(folder):
            raise ValueError("Select resource history folder.")
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".csv")
        ]
        if not files:
            raise ValueError("No resource history CSVs found.")
        frames = []
        for path in files:
            df = pd.read_csv(path)
            if "Timestamp" not in df.columns:
                continue
            df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
            df = df[df["Timestamp"] > cutoff]
            df["SourceFile"] = os.path.basename(path)
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        for col in [
            "Amount", "Cost labor", "Cost administration", "Cost 3rd party",
            "Cost material 1", "Cost material 2", "Cost material 3",
            "Cost material 4", "Cost material 5",
        ]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
        return out

    @staticmethod
    def sum_costs(df: pd.DataFrame) -> float:
        cols = [
            "Cost labor", "Cost administration", "Cost 3rd party",
            "Cost material 1", "Cost material 2", "Cost material 3",
            "Cost material 4", "Cost material 5",
        ]
        existing = [c for c in cols if c in df.columns]
        if not existing or df.empty:
            return 0.0
        return float(df[existing].sum(axis=1).sum())

    @staticmethod
    def compute_weighted_cogs(resource_df: pd.DataFrame):
        if resource_df is None or resource_df.empty:
            return 0.0, {}

        df = resource_df.copy()
        df = df.sort_values("Timestamp")

        inflow_cats = {"production", "market buy", "contract buy"}
        sell_cats = {"market sell", "contract sell"}

        inventory = {}
        ledger = {}
        cogs_total = 0.0

        for _, row in df.iterrows():
            cat = str(row.get("Category", "")).lower()
            res = str(row.get("Resource", "")).strip()
            amt = float(row.get("Amount", 0.0) or 0.0)
            if not res:
                continue

            if res not in inventory:
                inventory[res] = {"units": 0.0, "cost": 0.0}
                ledger[res] = []

            units = inventory[res]["units"]
            cost = inventory[res]["cost"]
            avg_cost = (cost / units) if units > 0 else 0.0
            row_cost = 0.0

            if cat in inflow_cats and amt > 0:
                for col in [
                    "Cost labor", "Cost administration", "Cost 3rd party",
                    "Cost material 1", "Cost material 2", "Cost material 3",
                    "Cost material 4", "Cost material 5",
                ]:
                    if col in df.columns:
                        row_cost += float(row.get(col, 0.0) or 0.0)
                units += amt
                cost += row_cost
                avg_cost = (cost / units) if units > 0 else 0.0

            if cat in sell_cats and amt < 0:
                sell_units = abs(amt)
                cogs_total += sell_units * avg_cost
                if units <= sell_units:
                    units = 0.0
                    cost = 0.0
                else:
                    units -= sell_units
                    cost -= sell_units * avg_cost
                avg_cost = (cost / units) if units > 0 else 0.0

            inventory[res]["units"] = units
            inventory[res]["cost"] = cost
            ledger[res].append({
                "Timestamp": row.get("Timestamp"),
                "Category": row.get("Category"),
                "Amount": amt,
                "RowCost": row_cost,
                "UnitsAfter": units,
                "CostAfter": cost,
                "AvgCostAfter": avg_cost,
            })

        return cogs_total, ledger

    @staticmethod
    def compute_inventory_avg_costs(resource_df: pd.DataFrame) -> dict[str, float]:
        if resource_df is None or resource_df.empty:
            return {}

        df = resource_df.copy()
        df = df.sort_values("Timestamp")

        inflow_cats = {"production", "market buy", "contract buy"}
        sell_cats = {"market sell", "contract sell"}

        inventory = {}

        for _, row in df.iterrows():
            cat = str(row.get("Category", "")).lower()
            res = str(row.get("Resource", "")).strip()
            amt = float(row.get("Amount", 0.0) or 0.0)
            if not res:
                continue

            if res not in inventory:
                inventory[res] = {"units": 0.0, "cost": 0.0}

            units = inventory[res]["units"]
            cost = inventory[res]["cost"]

            if cat in inflow_cats and amt > 0:
                row_cost = 0.0
                for col in [
                    "Cost labor", "Cost administration", "Cost 3rd party",
                    "Cost material 1", "Cost material 2", "Cost material 3",
                    "Cost material 4", "Cost material 5",
                ]:
                    if col in df.columns:
                        row_cost += float(row.get(col, 0.0) or 0.0)
                units += amt
                cost += row_cost

            if cat in sell_cats and amt < 0:
                sell_units = abs(amt)
                avg_cost = (cost / units) if units > 0 else 0.0
                if units <= sell_units:
                    units = 0.0
                    cost = 0.0
                else:
                    units -= sell_units
                    cost -= sell_units * avg_cost

            inventory[res]["units"] = units
            inventory[res]["cost"] = cost

        avg_costs = {}
        for res, inv in inventory.items():
            units = inv["units"]
            avg_costs[res] = (inv["cost"] / units) if units > 0 else 0.0
        return avg_costs

    @staticmethod
    def parse_details(details):
        if isinstance(details, dict):
            return details
        if isinstance(details, str) and details:
            try:
                return json.loads(details)
            except Exception:
                return {}
        return {}

    def build_statement(self, account_df: pd.DataFrame, resource_df: pd.DataFrame, valuation_diff: float) -> pd.DataFrame:
        sales = 0.0
        exchange_fees = 0.0
        salaries = 0.0
        training = 0.0
        poaching = 0.0
        construction = 0.0
        interest_income = 0.0
        interest_expense = 0.0
        game_income = 0.0
        exec_royalties = 0.0
        gain_on_sale = 0.0
        accounting_overhead = 0.0
        donations = 0.0
        write_offs = 0.0
        defaults = 0.0

        if not account_df.empty:
            cat = account_df["Category"].astype(str).str.lower()
            money = account_df["Money"]
            desc = account_df.get("Description", pd.Series("", index=account_df.index)).astype(str).str.lower()

            sales_mask = cat.isin(["market", "contract"]) & (money > 0)
            sales = float(money[sales_mask].sum())

            fees_mask = cat.eq("fees")
            exchange_fees = float(money[fees_mask].sum())

            construction_mask = cat.eq("construction")
            construction = float(money[construction_mask].sum())

            exec_mask = cat.eq("executive salaries")
            exec_royalties_mask = exec_mask & desc.str.contains("executive royalties", na=False)
            exec_royalties = float(money[exec_royalties_mask].sum())
            salaries = float(money[exec_mask & ~exec_royalties_mask].sum())

            training_mask = cat.eq("executive training")
            training = float(money[training_mask].sum())

            poaching_mask = cat.eq("executive poaching")
            poaching = float(money[poaching_mask].sum())

            interest_mask = cat.eq("interest")
            interest_income = float(money[interest_mask & (money > 0)].sum())
            interest_expense = float(money[interest_mask & (money < 0)].sum())

            game_mask = cat.eq("achievement") | desc.str.contains("achievement", na=False)
            game_income = float(money[game_mask].sum())

            gain_mask = cat.eq("gain on sale") | desc.str.contains("gain on sale", na=False)
            gain_on_sale = float(money[gain_mask].sum())

            overhead_mask = cat.eq("taxes") | desc.str.contains("taxes", na=False)
            accounting_overhead = float(money[overhead_mask].sum())

            donation_mask = cat.eq("donations") | desc.str.contains("donation", na=False)
            donations = float(money[donation_mask].sum())

            writeoff_mask = cat.eq("write offs") | desc.str.contains("write off", na=False)
            write_offs = float(money[writeoff_mask].sum())

            defaults_mask = cat.eq("defaults") | desc.str.contains("default", na=False)
            defaults = float(money[defaults_mask].sum())

        cogs = 0.0
        freight_out = 0.0
        patent_conversion = 0.0

        if not resource_df.empty:
            rcat = resource_df["Category"].astype(str).str.lower()
            rres = resource_df["Resource"].astype(str)

            cogs, _ = self.compute_weighted_cogs(resource_df)
            cogs = -cogs

            transport_mask = (rres.str.lower() == "transport") & (resource_df["Amount"] < 0) & rcat.eq("transport")
            if "Cost 3rd party" in resource_df.columns:
                freight_out = -float(resource_df.loc[transport_mask, "Cost 3rd party"].sum())

            research_mask = rcat.eq("research")
            for _, row in resource_df[research_mask].iterrows():
                details = self.parse_details(row.get("Details", ""))
                patents = details.get("patents")
                if patents:
                    res = str(row.get("Resource", ""))
                    name = res.replace(" research", "").strip().title()
                    value = PATENT_VALUES.get(name, 0.0)
                    row_cost = 0.0
                    for col in [
                        "Cost labor", "Cost administration", "Cost 3rd party",
                        "Cost material 1", "Cost material 2", "Cost material 3",
                        "Cost material 4", "Cost material 5",
                    ]:
                        if col in resource_df.columns:
                            row_cost += float(row.get(col, 0.0) or 0.0)
                    gross_val = float(patents) * value
                    net_val = gross_val - row_cost
                    print(
                        f"Patent conversion: {res} patents={patents} "
                        f"value={value} gross={gross_val:,.2f} "
                        f"row_cost={row_cost:,.2f} net={net_val:,.2f}"
                    )
                    patent_conversion += net_val
        else:
            pass

        gross_profit = sales + cogs + freight_out

        operating_expenses = (
            construction + exchange_fees + salaries + training + poaching
        )

        other_income = (
            game_income
            + exec_royalties
            + gain_on_sale
            + accounting_overhead
            + donations
            + interest_income
            + interest_expense
            + write_offs
            + defaults
            + patent_conversion
        )

        net_income = gross_profit + operating_expenses + other_income
        other_comprehensive_income = valuation_diff
        total_comprehensive_income = net_income + other_comprehensive_income

        rows = [
            ("GROSS PROFIT", "", ""),
            ("", "  Sales", sales),
            ("", "  Cost of goods sold", cogs),
            ("", "  Freight Out", freight_out),
            ("", "-", ""),
            ("", "  GROSS PROFIT TOTAL", gross_profit),
            ("", "=", ""),
            ("OPERATING EXPENSES", "", ""),
            ("", "  Construction costs", construction),
            ("", "  Exchange fees", exchange_fees),
            ("", "  Executives costs", ""),
            ("", "    Salaries", salaries),
            ("", "    Training", training),
            ("", "    Poaching", poaching),
            ("", "-", ""),
            ("", "  OPERATING EXPENSES TOTAL", operating_expenses),
            ("", "=", ""),
            ("OTHER INCOME (LOSS)", "", ""),
            ("", "  Game income", game_income),
            ("", "  Executive royalties", exec_royalties),
            ("", "  Gain on sale", gain_on_sale),
            ("", "  Patent conversion", patent_conversion),
            ("", "  Accounting overhead", accounting_overhead),
            ("", "  Donations", donations),
            ("", "  Interest income", interest_income),
            ("", "  Interest expense", interest_expense),
            ("", "  Write offs", write_offs),
            ("", "  Defaults", defaults),
            ("", "-", ""),
            ("", "  OTHER INCOME (LOSS) TOTAL", other_income),
            ("", "=", ""),
            ("NET INCOME", "", ""),
            ("", "  Net income", net_income),
            ("", "  Other comprehensive income", other_comprehensive_income),
            ("", "  TOTAL COMPREHENSIVE INCOME", total_comprehensive_income),
        ]

        return pd.DataFrame(rows, columns=["Section", "Item", "Value"])

    def build_cashflow(self, account_df: pd.DataFrame) -> pd.DataFrame:
        if account_df.empty:
            rows = [
                ("OPERATING ACTIVITIES", "", ""),
                ("", "  Cash receipts", ""),
                ("", "    From retail", 0.0),
                ("", "    From customers", 0.0),
                ("", "    From exchange", 0.0),
                ("", "    From interest", 0.0),
                ("", "    From poaching", 0.0),
                ("", "    From royalties", 0.0),
                ("", "    From employees", 0.0),
                ("", "  Cash payments", ""),
                ("", "    To suppliers", 0.0),
                ("", "    To exchange", 0.0),
                ("", "    To employees", 0.0),
                ("", "    To executives", 0.0),
                ("", "    For interest", 0.0),
                ("", "    For fees", 0.0),
                ("", "    For accounting", 0.0),
                ("", "    For PA quests", 0.0),
                ("", "-", ""),
                ("", "  OPERATING ACTIVITIES TOTAL", 0.0),
                ("", "=", ""),
                ("INVESTING ACTIVITIES", "", ""),
                ("", "  Investment in bonds", 0.0),
                ("", "=", ""),
                ("FINANCING ACTIVITIES", "", ""),
                ("", "  Bonds", 0.0),
                ("", "  From game", 0.0),
                ("", "-", ""),
                ("", "  FINANCING ACTIVITIES TOTAL", 0.0),
                ("", "=", ""),
                ("TOTAL CHANGE IN CASH", "", ""),
                ("", "  Total change in cash", 0.0),
            ]
            return pd.DataFrame(rows, columns=["Section", "Item", "Value"])

        cat = account_df["Category"].astype(str).str.lower()
        money = account_df["Money"]
        desc = account_df.get("Description", pd.Series("", index=account_df.index)).astype(str).str.lower()

        receipts_retail = float(money[(cat == "retail") & (money > 0)].sum())
        receipts_customers = float(money[(cat == "contract") & (money > 0)].sum())
        receipts_exchange = float(money[(cat.isin(["market", "exchange"])) & (money > 0)].sum())
        receipts_interest = float(money[(cat == "interest") & (money > 0)].sum())
        receipts_poaching = float(money[(cat == "executive poaching") & (money > 0)].sum())
        receipts_royalties = float(
            money[(cat == "executive salaries") & (money > 0) & desc.str.contains("executive royalties", na=False)].sum()
        )
        receipts_employees = float(
            money[(cat == "production") & (money > 0) & desc.str.contains("wages", na=False)].sum()
        )

        payments_suppliers = float(money[(cat == "contract") & (money < 0)].sum())
        payments_exchange = float(money[(cat == "market") & (money < 0)].sum())
        payments_employees = float(
            money[(cat == "production") & (money < 0) & desc.str.contains("wages", na=False)].sum()
        )
        payments_executives = float(
            money[
                (
                    (cat == "executive salaries")
                    | (cat == "executive training")
                    | (cat == "executive poaching")
                )
                & (money < 0)
            ].sum()
        )
        payments_interest = float(money[(cat == "interest") & (money < 0)].sum())
        payments_fees = float(money[(cat == "fees") & (money < 0)].sum())
        payments_accounting = float(money[(cat == "taxes") & (money < 0)].sum())
        payments_pa = float(
            money[
                (cat.str.contains("pa", na=False) | desc.str.contains("pa quest", na=False))
                & (money < 0)
            ].sum()
        )

        operating_total = (
            receipts_retail
            + receipts_customers
            + receipts_exchange
            + receipts_interest
            + receipts_poaching
            + receipts_royalties
            + receipts_employees
            + payments_suppliers
            + payments_exchange
            + payments_employees
            + payments_executives
            + payments_interest
            + payments_fees
            + payments_accounting
            + payments_pa
        )

        investing_bonds = float(money[(cat == "bonds")].sum())
        financing_bonds = float(money[(cat == "own bonds")].sum())
        financing_game = float(money[(cat == "achievement") & (money > 0)].sum())

        financing_total = financing_bonds + financing_game
        total_change = operating_total + investing_bonds + financing_total

        rows = [
            ("OPERATING ACTIVITIES", "", ""),
            ("", "  Cash receipts", ""),
            ("", "    From retail", receipts_retail),
            ("", "    From customers", receipts_customers),
            ("", "    From exchange", receipts_exchange),
            ("", "    From interest", receipts_interest),
            ("", "    From poaching", receipts_poaching),
            ("", "    From royalties", receipts_royalties),
            ("", "    From employees", receipts_employees),
            ("", "  Cash payments", ""),
            ("", "    To suppliers", payments_suppliers),
            ("", "    To exchange", payments_exchange),
            ("", "    To employees", payments_employees),
            ("", "    To executives", payments_executives),
            ("", "    For interest", payments_interest),
            ("", "    For fees", payments_fees),
            ("", "    For accounting", payments_accounting),
            ("", "    For PA quests", payments_pa),
            ("", "-", ""),
            ("", "  OPERATING ACTIVITIES TOTAL", operating_total),
            ("", "=", ""),
            ("INVESTING ACTIVITIES", "", ""),
            ("", "  Investment in bonds", investing_bonds),
            ("", "=", ""),
            ("FINANCING ACTIVITIES", "", ""),
            ("", "  Bonds", financing_bonds),
            ("", "  From game", financing_game),
            ("", "-", ""),
            ("", "  FINANCING ACTIVITIES TOTAL", financing_total),
            ("", "=", ""),
            ("TOTAL CHANGE IN CASH", "", ""),
            ("", "  Total change in cash", total_change),
        ]
        return pd.DataFrame(rows, columns=["Section", "Item", "Value"])

    def export_statement_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export statement PNG", "income_statement.png", "PNG Files (*.png)")
        if not path:
            return
        try:
            table = self.table
            if self.statement_window and self.statement_tabs:
                current = self.statement_tabs.currentWidget()
                candidate = current.findChild(QTableView) if current else None
                if candidate:
                    table = candidate
            header = table.horizontalHeader()
            vheader = table.verticalHeader()
            rows = table.model().rowCount()
            cols = table.model().columnCount()

            width = vheader.width() + sum(table.columnWidth(c) for c in range(cols))
            height = header.height() + sum(table.rowHeight(r) for r in range(rows))

            pix = table.grab(QRect(0, 0, max(1, width), max(1, height)))
            pix.save(path, "PNG")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", "Statement saved successfully.")

    def compute_valuation_allowance_diff(
        self,
        inventory: list[dict],
        baseline_allowance: float,
    ) -> float:
        if not inventory:
            print("Valuation: empty inventory, diff=0")
            return 0.0

        realm_id = int(self.realm_select.currentData())
        today_key, yesterday_key = self.get_financial_day_keys()
        vwap_cache = self.load_vwap_cache()
        total_va = 0.0

        print(f"Valuation: baseline allowance={baseline_allowance:,.2f}")
        print(f"Valuation: financial_day={today_key} yesterday={yesterday_key}")

        for item in inventory:
            resource_id = int(item.get("kind", 0))
            quality = int(item.get("quality", 0))
            amount = float(item.get("amount", 0.0) or 0.0)
            if amount == 0:
                continue

            cost = item.get("cost", {}) or {}
            cost_value = float(
                cost.get("workers", 0.0)
                + cost.get("admin", 0.0)
                + cost.get("material1", 0.0)
                + cost.get("material2", 0.0)
                + cost.get("material3", 0.0)
                + cost.get("material4", 0.0)
                + cost.get("material5", 0.0)
                + cost.get("market", 0.0)
            )

            vwap = self.get_vwap_with_cache(
                realm_id, resource_id, quality, vwap_cache, today_key, yesterday_key
            )
            if vwap is None:
                print(f"Valuation: missing VWAP for resource {resource_id} q{quality}, skip")
                continue

            vwap_adj = vwap * 0.85
            liquidation_value = amount * vwap_adj
            va = cost_value - liquidation_value
            total_va += va

            print(
                f"Valuation item: id={resource_id} q={quality} amount={amount} "
                f"cost={cost_value:,.2f} vwap={vwap:.4f} vwap85={vwap_adj:.4f} "
                f"liquidation={liquidation_value:,.2f} va={va:,.2f}"
            )

        self.save_vwap_cache(vwap_cache)
        diff = total_va - baseline_allowance
        print(f"Valuation: total_va={total_va:,.2f} diff={diff:,.2f}")
        return diff

    @staticmethod
    def get_financial_day_keys() -> tuple[str, str]:
        tz = ZoneInfo("America/Caracas")
        now = datetime.now(tz)
        financial_date = now.date()
        if now.hour < 21:
            financial_date = (now - timedelta(days=1)).date()
        yesterday_date = financial_date - timedelta(days=1)
        return financial_date.isoformat(), yesterday_date.isoformat()

    def load_vwap_cache(self) -> dict:
        path = os.path.join(os.path.dirname(__file__), "config", "vwap_cache.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_vwap_cache(self, cache: dict):
        path = os.path.join(os.path.dirname(__file__), "config", "vwap_cache.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass

    def get_vwap_with_cache(
        self,
        realm_id: int,
        resource_id: int,
        quality: int,
        cache: dict,
        today_key: str,
        yesterday_key: str,
    ) -> float | None:
        key = f"{resource_id}:{quality}"
        if yesterday_key in cache and key in cache[yesterday_key]:
            return cache[yesterday_key][key]

        vwap = self.fetch_yesterday_vwap(realm_id, resource_id, quality)
        if vwap is not None:
            cache.setdefault(today_key, {})[key] = vwap
        return vwap

    @staticmethod
    def fetch_resource_list(realm_id: int) -> list[dict]:
        resources = []
        page = 1
        while True:
            url = f"https://api.simcotools.com/v1/realms/{realm_id}/resources?page={page}"
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            resources.extend(data.get("resources", []))
            meta = data.get("metadata", {})
            if meta.get("currentPage", page) >= meta.get("lastPage", page):
                break
            page += 1
        return resources

    @staticmethod
    def fetch_yesterday_vwap(realm_id: int, resource_id: int, quality: int) -> float | None:
        vwap_url = f"https://api.simcotools.com/v1/realms/{realm_id}/market/vwaps/{resource_id}"
        with urllib.request.urlopen(vwap_url) as resp:
            vwap_data = json.loads(resp.read().decode("utf-8"))
        vwaps = vwap_data.get("vwaps", [])
        if not vwaps:
            return None
        vwap_entry = next((v for v in vwaps if v.get("quality") == quality), vwaps[0])
        return vwap_entry.get("vwap")

    def show_statement_window(self):
        if self.statement_window is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Statements")
            dlg.resize(960, 820)
            tabs = QTabWidget()

            income_page = QWidget()
            income_layout = QVBoxLayout()
            income_table = QTableView()
            income_table.setModel(self.model)
            income_table.setAlternatingRowColors(True)
            income_table.resizeColumnsToContents()
            income_layout.addWidget(income_table)
            income_page.setLayout(income_layout)

            cashflow_page = QWidget()
            cashflow_layout = QVBoxLayout()
            cashflow_table = QTableView()
            cashflow_table.setModel(self.cashflow_model)
            cashflow_table.setAlternatingRowColors(True)
            cashflow_table.resizeColumnsToContents()
            cashflow_layout.addWidget(cashflow_table)
            cashflow_page.setLayout(cashflow_layout)

            tabs.addTab(income_page, "Income")
            tabs.addTab(cashflow_page, "Cashflow")

            lay = QVBoxLayout()
            lay.addWidget(tabs)
            dlg.setLayout(lay)
            self.statement_window = dlg
            self.statement_tabs = tabs
        else:
            for table in self.statement_window.findChildren(QTableView):
                table.resizeColumnsToContents()
        self.statement_window.show()


def main():
    app = QApplication(sys.argv)
    f = app.font()
    if f.pointSize() <= 0:
        f.setPointSize(10)
        app.setFont(f)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
