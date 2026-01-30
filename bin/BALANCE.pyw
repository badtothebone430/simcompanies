import sys
import json
import os
from dataclasses import dataclass
from datetime import datetime, date

import pandas as pd

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QDateEdit, QTableView, QGroupBox, QCheckBox,
    QDialog, QTextEdit, QDialogButtonBox, QSpinBox, QDoubleSpinBox,
    QToolButton, QFrame, QSizePolicy, QScrollArea
)

from PySide6.QtGui import QFont
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.ticker import FuncFormatter, MaxNLocator


# -----------------------------
# Table model
# -----------------------------
class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df
        self._summary = None

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def set_summary(self, summary: dict | None):
        self.beginResetModel()
        self._summary = summary
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if self._df is None:
            return 0
        return len(self._df) + (1 if self._summary is not None else 0)

    def columnCount(self, parent=QModelIndex()):
        return 0 if self._df is None else self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        is_summary = self._summary is not None and index.row() == len(self._df)
        if role == Qt.FontRole and is_summary:
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.DisplayRole:
            if is_summary:
                col = self._df.columns[index.column()]
                return str(self._summary.get(col, ""))
            val = self._df.iat[index.row(), index.column()]
            if pd.isna(val):
                return ""
            col = self._df.columns[index.column()]
            if col in ("Timestamp", "Date"):
                if isinstance(val, (pd.Timestamp, datetime)):
                    return str(val)
                return str(val)
            if isinstance(val, (int, float)):
                return f"{float(val):,.2f}"
            return str(val)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if self._df is None or role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)


# -----------------------------
# Simple KPI card
# -----------------------------
class KpiCard(QGroupBox):
    def __init__(self, title: str):
        super().__init__()
        self.setTitle("")
        self.title_lbl = QLabel(title)
        self.value_lbl = QLabel("0")

        self.title_lbl.setObjectName("kpiTitle")
        self.value_lbl.setObjectName("kpiValue")

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)
        self.setLayout(layout)


# -----------------------------
# Collapsible section
# -----------------------------
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


# -----------------------------
# Matplotlib chart widget
# -----------------------------
class ChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.fig = Figure(figsize=(6, 3.2), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)
        self.setLayout(lay)

    def plot_timeseries(
        self,
        daily_df: pd.DataFrame,
        metric: str,
        show_ma: bool = False,
        ma_window: int = 7,
    ):
        self.ax.clear()

        if (
            daily_df is None
            or daily_df.empty
            or "Date" not in daily_df.columns
            or metric not in daily_df.columns
        ):
            self.ax.set_title("Metric per day")
            self.ax.grid(True, alpha=0.25)
            self.canvas.draw()
            return

        x = pd.to_datetime(daily_df["Date"], errors="coerce")
        y = pd.to_numeric(daily_df[metric], errors="coerce").fillna(0)

        self.ax.plot(x, y, label=metric)
        if show_ma and ma_window > 1:
            ma = y.rolling(window=ma_window, min_periods=1).mean()
            self.ax.plot(x, ma, linestyle="--", linewidth=1.8, label=f"{ma_window}d MA")
        self.ax.set_title(f"{metric} per day")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel(metric)
        locator = AutoDateLocator()
        self.ax.xaxis.set_major_locator(locator)
        self.ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
        self.ax.yaxis.set_major_locator(MaxNLocator(nbins=7))
        self.ax.yaxis.set_major_formatter(FuncFormatter(self.format_money_ticks))
        if show_ma and ma_window > 1:
            self.ax.legend(loc="upper left", frameon=False)
        self.ax.grid(True, alpha=0.25)
        self.fig.autofmt_xdate()
        self.canvas.draw()

    @staticmethod
    def format_money_ticks(value, _pos):
        num = float(value)
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f}B".rstrip("0").rstrip(".")
        if abs_num >= 1_000_000:
            return f"{num/1_000_000:.1f}M".rstrip("0").rstrip(".")
        if abs_num >= 1_000:
            return f"{num/1_000:.1f}K".rstrip("0").rstrip(".")
        return f"{num:g}"


# -----------------------------
# Main app
# -----------------------------
@dataclass
class AppState:
    df_raw: pd.DataFrame | None = None
    df_view: pd.DataFrame | None = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimCompanies Balance Sheet Analyzer")
        self.resize(1250, 760)

        self.state = AppState()
        self.date_min = None
        self.date_max = None
        self.last_daily = pd.DataFrame()
        self.config_data = self.load_config()

        # Top buttons
        self.btn_open = QPushButton("Open CSV")
        self.btn_export = QPushButton("Export filtered CSV")
        self.btn_export_chart = QPushButton("Export chart PNG")
        self.btn_export.setEnabled(False)
        self.btn_export_chart.setEnabled(False)

        self.btn_open.clicked.connect(self.open_csv)
        self.btn_export.clicked.connect(self.export_csv)
        self.btn_export_chart.clicked.connect(self.export_chart_png)

        topbar = QHBoxLayout()
        topbar.addWidget(self.btn_open)
        topbar.addWidget(self.btn_export)
        topbar.addWidget(self.btn_export_chart)
        topbar.addStretch(1)

        # Filters
        self.metric_combo = QComboBox()
        self.metric_combo.currentIndexChanged.connect(self.apply_filters)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")

        self.btn_last7 = QPushButton("Last 7d")
        self.btn_last30 = QPushButton("Last 30d")
        self.btn_last90 = QPushButton("Last 90d")
        self.btn_reset_filters = QPushButton("Reset filters")
        self.btn_last7.clicked.connect(lambda: self.apply_preset_range(7))
        self.btn_last30.clicked.connect(lambda: self.apply_preset_range(30))
        self.btn_last90.clicked.connect(lambda: self.apply_preset_range(90))
        self.btn_reset_filters.clicked.connect(self.reset_filters)

        self.date_from.dateChanged.connect(self.apply_filters)
        self.date_to.dateChanged.connect(self.apply_filters)

        filters_box = QGroupBox("Filters")
        fl = QGridLayout()
        fl.addWidget(QLabel("Metric"), 0, 0)
        fl.addWidget(self.metric_combo, 0, 1)
        fl.addWidget(QLabel("From"), 0, 2)
        fl.addWidget(self.date_from, 0, 3)
        fl.addWidget(QLabel("To"), 0, 4)
        fl.addWidget(self.date_to, 0, 5)
        fl.addWidget(QLabel("Quick range"), 1, 0)
        quick_range = QWidget()
        quick_range_layout = QHBoxLayout()
        quick_range_layout.setContentsMargins(0, 0, 0, 0)
        quick_range_layout.addWidget(self.btn_last7)
        quick_range_layout.addWidget(self.btn_last30)
        quick_range_layout.addWidget(self.btn_last90)
        quick_range_layout.addWidget(self.btn_reset_filters)
        quick_range_layout.addStretch(1)
        quick_range.setLayout(quick_range_layout)
        fl.addWidget(quick_range, 1, 1, 1, 5)
        fl.setColumnStretch(1, 2)
        fl.setColumnStretch(3, 1)
        fl.setColumnStretch(5, 1)
        filters_box.setLayout(fl)

        # Column toggles
        columns_box = QGroupBox("Columns")
        self.columns_layout = QGridLayout()
        self.col_toggles = {}
        columns_box.setLayout(self.columns_layout)

        # KPI cards
        self.kpi_net = KpiCard("Balance today")
        self.kpi_income = KpiCard("Balance start")
        self.kpi_expense = KpiCard("Net change")
        self.kpi_count = KpiCard("Rows")

        kpis = QHBoxLayout()
        kpis.addWidget(self.kpi_net)
        kpis.addWidget(self.kpi_income)
        kpis.addWidget(self.kpi_expense)
        self.kpi_count.hide()

        # Projection box
        proj_box = QGroupBox("Projection")
        proj_layout = QGridLayout()
        self.proj_days = QSpinBox()
        self.proj_days.setRange(1, 3650)
        self.proj_days.setValue(30)
        self.proj_value_lbl = QLabel("0.00")

        self.proj_target = QDoubleSpinBox()
        self.proj_target.setRange(-1_000_000_000_000, 1_000_000_000_000)
        self.proj_target.setDecimals(2)
        self.proj_target.setValue(100000.00)
        self.proj_needed_lbl = QLabel("N/A")

        self.proj_avg_lbl = QLabel("0.00/day")

        self.proj_days.valueChanged.connect(self.update_projection)
        self.proj_target.valueChanged.connect(self.update_projection)

        proj_layout.addWidget(QLabel("Avg per day"), 0, 0)
        proj_layout.addWidget(self.proj_avg_lbl, 0, 1)
        proj_layout.addWidget(QLabel("Project value in"), 1, 0)
        proj_layout.addWidget(self.proj_days, 1, 1)
        proj_layout.addWidget(QLabel("days"), 1, 2)
        proj_layout.addWidget(QLabel("Projected value"), 1, 3)
        proj_layout.addWidget(self.proj_value_lbl, 1, 4)
        proj_layout.addWidget(QLabel("Target value"), 2, 0)
        proj_layout.addWidget(self.proj_target, 2, 1)
        proj_layout.addWidget(QLabel("Days needed"), 2, 3)
        proj_layout.addWidget(self.proj_needed_lbl, 2, 4)
        proj_layout.setColumnStretch(4, 1)
        proj_box.setLayout(proj_layout)

        # Chart + totals table
        self.chart = ChartWidget()
        self.ma_checkbox = QCheckBox("Show 7-day moving average")
        self.ma_checkbox.setChecked(False)
        self.ma_checkbox.toggled.connect(self.refresh_chart)

        self.item_totals = QTableView()
        self.item_totals.setMinimumWidth(420)
        self.item_totals.setAlternatingRowColors(True)

        chart_row = QHBoxLayout()
        left_panel = QVBoxLayout()
        chart_controls = QHBoxLayout()
        chart_controls.addWidget(self.ma_checkbox)
        chart_controls.addStretch(1)
        left_panel.addLayout(chart_controls)
        left_panel.addWidget(self.chart, 1)
        left_panel_wrap = QWidget()
        left_panel_wrap.setLayout(left_panel)
        chart_row.addWidget(left_panel_wrap, 2)
        right_panel = QVBoxLayout()
        right_panel.addWidget(self.item_totals, 1)
        right_panel_wrap = QWidget()
        right_panel_wrap.setLayout(right_panel)
        chart_row.addWidget(right_panel_wrap, 1)
        chart_row_wrap = QWidget()
        chart_row_wrap.setLayout(chart_row)

        # Main table
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        self.model = PandasModel(pd.DataFrame())
        self.table.setModel(self.model)

        # Layout root
        root = QWidget()
        layout = QVBoxLayout()
        layout.addLayout(topbar)
        layout.addWidget(CollapsibleBox("Filters", filters_box, expanded=True))
        layout.addWidget(CollapsibleBox("Columns", columns_box, expanded=False))
        layout.addWidget(CollapsibleBox("KPIs", self.wrap_layout(kpis), expanded=True))
        layout.addWidget(CollapsibleBox("Projection", proj_box, expanded=False))
        layout.addWidget(CollapsibleBox("Chart + totals", chart_row_wrap, expanded=True))
        tx_wrap = QWidget()
        tx_layout = QVBoxLayout()
        tx_layout.setContentsMargins(0, 0, 0, 0)
        tx_layout.addWidget(QLabel("Income statement"))
        tx_layout.addWidget(self.table)
        tx_wrap.setLayout(tx_layout)
        layout.addWidget(CollapsibleBox("Rows", tx_wrap, expanded=True))

        root.setLayout(layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(root)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        self.apply_dark_theme()
        self.load_last_file_on_startup()

    @staticmethod
    def wrap_layout(layout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def apply_dark_theme(self):
        # Clean dark theme with subtle borders
        self.setStyleSheet("""
            QWidget { background: #0f1115; color: #e6e6e6; font-size: 12px; }
            QGroupBox { border: 1px solid #2a2f3a; border-radius: 12px; margin-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #aab2c0; }
            QPushButton {
                background: #1b2130; border: 1px solid #2a3142; border-radius: 10px;
                padding: 10px 14px; font-weight: 600;
            }
            QPushButton:hover { background: #222a3c; }
            QPushButton:disabled { color: #6b7280; background: #121620; border-color: #1e2431; }
            QLineEdit, QComboBox, QDateEdit {
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
            QLabel#kpiTitle { color: #aab2c0; font-weight: 700; }
            QLabel#kpiValue { font-size: 20px; font-weight: 800; }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 6px 4px 6px 0;
            }
            QScrollBar::handle:vertical {
                background: #2a3142;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #343c52; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

    # -----------------------------
    # CSV load + parsing
    # -----------------------------
    def config_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "config", "sim_balance_analyser_config.json")

    def load_config(self) -> dict:
        try:
            with open(self.config_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return data
        except Exception:
            return {}

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_path()), exist_ok=True)
        try:
            with open(self.config_path(), "w", encoding="utf-8") as f:
                json.dump(self.config_data, f)
        except Exception:
            pass

    def load_last_file_on_startup(self):
        last_path = self.load_last_path()
        if not last_path or not os.path.isfile(last_path):
            last_path = self.default_csv_path()
        if not last_path or not os.path.isfile(last_path):
            return
        try:
            df = pd.read_csv(last_path)
            df = self.normalize_df(df)
        except Exception:
            return
        self.state.df_raw = df
        self.btn_export.setEnabled(True)
        self.btn_export_chart.setEnabled(True)

        self.populate_metric_combo(df)
        self.build_column_toggles(df)

        dmin = df["Date"].min()
        dmax = df["Date"].max()
        if pd.notna(dmin) and pd.notna(dmax):
            self.date_min = dmin.to_pydatetime().date()
            self.date_max = dmax.to_pydatetime().date()
            self.set_date_range(self.date_min, self.date_max, apply=False)

        self.apply_filters()

    def default_csv_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "userdata", "balance.csv")

    def load_last_path(self) -> str | None:
        return self.config_data.get("last_csv_path")

    def save_last_path(self, path: str):
        self.config_data["last_csv_path"] = path
        self.save_config()

    def open_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = pd.read_csv(path)
            df = self.normalize_df(df)
        except Exception as e:
            QMessageBox.critical(self, "Failed to load CSV", str(e))
            return

        self.state.df_raw = df
        self.btn_export.setEnabled(True)
        self.btn_export_chart.setEnabled(True)
        self.save_last_path(path)

        self.populate_metric_combo(df)
        self.build_column_toggles(df)

        dmin = df["Date"].min()
        dmax = df["Date"].max()
        if pd.notna(dmin) and pd.notna(dmax):
            self.date_min = dmin.to_pydatetime().date()
            self.date_max = dmax.to_pydatetime().date()
            self.set_date_range(self.date_min, self.date_max, apply=False)

        self.apply_filters()

    def normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        needed = {"Timestamp"}
        missing = needed - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        out = df.copy()

        # Parse Timestamp with timezone support
        out["Timestamp"] = pd.to_datetime(out["Timestamp"], errors="coerce", utc=True)
        out["Date"] = out["Timestamp"].dt.date
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")

        # Numeric columns
        for col in out.columns:
            if col in ("Timestamp", "Date"):
                continue
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

        def sum_columns(cols: list[str]) -> float:
            existing = [c for c in cols if c in out.columns]
            if not existing:
                return 0.0
            return out[existing].sum(axis=1)

        # Custom metrics
        required = {"Retained Earnings", "Contributed Capital"}
        if required.issubset(out.columns) and "Company Value" not in out.columns:
            out["Company Value"] = (
                out["Retained Earnings"] + out["Contributed Capital"]
            )

        if "Current Assets" not in out.columns:
            current_cols = [
                "Cash",
                "Accounts Receivable",
                "Inventory - materials",
                "Inventory - research",
                "Inventory - work in process",
                "Inventory - finished goods",
                "Inventory - valuation allowance",
            ]
            if any(c in out.columns for c in current_cols):
                out["Current Assets"] = sum_columns(current_cols)

        if "Non-Current Assets" not in out.columns:
            non_current_cols = [
                "Deposits",
                "Investment in bonds",
                "Buildings",
                "Construction in progress",
                "Patents",
            ]
            if any(c in out.columns for c in non_current_cols):
                out["Non-Current Assets"] = sum_columns(non_current_cols)

        if "Total Assets" not in out.columns:
            total_cols = ["Current Assets", "Non-Current Assets"]
            if any(c in out.columns for c in total_cols):
                out["Total Assets"] = sum_columns(total_cols)

        # Reorder columns: Timestamp, Date, then rest
        cols = ["Timestamp", "Date"]
        rest = [c for c in out.columns if c not in cols]
        if "Company Value" in rest:
            rest.remove("Company Value")
            rest.append("Company Value")
        for metric in ("Current Assets", "Non-Current Assets", "Total Assets"):
            if metric in rest:
                rest.remove(metric)
                rest.append(metric)
        cols.extend(rest)
        out = out[cols].sort_values("Timestamp", ascending=False).reset_index(drop=True)
        return out

    def populate_metric_combo(self, df: pd.DataFrame):
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        numeric_cols = [c for c in df.columns if c not in ("Timestamp", "Date")]
        if "Company Value" in numeric_cols:
            numeric_cols = ["Company Value"] + [c for c in numeric_cols if c != "Company Value"]
        self.metric_combo.addItems(numeric_cols)
        if "Company Value" in numeric_cols:
            self.metric_combo.setCurrentText("Company Value")
        elif numeric_cols:
            self.metric_combo.setCurrentText(numeric_cols[0])
        self.metric_combo.blockSignals(False)
    
    def current_metric(self, view: pd.DataFrame) -> str:
        metric = self.metric_combo.currentText()
        if metric and metric in view.columns:
            return metric
        numeric_cols = [c for c in view.columns if c not in ("Timestamp", "Date")]
        if "Company Value" in numeric_cols:
            return "Company Value"
        return numeric_cols[0] if numeric_cols else "Company Value"

    def build_column_toggles(self, df: pd.DataFrame):
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.col_toggles = {}

        cols = list(df.columns)
        cols_per_row = 4
        row = 0
        col = 0
        for name in cols:
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_column_visibility)
            self.col_toggles[name] = cb
            self.columns_layout.addWidget(cb, row, col)
            col += 1
            if col >= cols_per_row:
                col = 0
                row += 1
        self.columns_layout.setColumnStretch(cols_per_row, 1)

    # -----------------------------
    # Filtering + summaries
    # -----------------------------
    def apply_filters(self):
        df = self.state.df_raw
        if df is None or df.empty:
            self.state.df_view = pd.DataFrame()
            self.model.set_df(self.state.df_view)
            self.update_summaries()
            return

        dfrom = self.date_from.date().toPython()
        dto = self.date_to.date().toPython()

        view = df.copy()
        view = view[(view["Date"].dt.date >= dfrom) & (view["Date"].dt.date <= dto)]

        self.state.df_view = view.reset_index(drop=True)
        self.model.set_df(self.state.df_view)
        self.update_summaries()

    def apply_preset_range(self, days: int):
        if self.date_max is None:
            return
        dto = self.date_max
        dfrom = dto - pd.Timedelta(days=days - 1)
        if isinstance(dfrom, datetime):
            dfrom = dfrom.date()
        elif isinstance(dfrom, pd.Timestamp):
            dfrom = dfrom.date()
        self.set_date_range(dfrom, dto, apply=True)

    def reset_filters(self):
        if self.date_min and self.date_max:
            self.set_date_range(self.date_min, self.date_max, apply=False)
        self.apply_filters()

    def set_date_range(self, dfrom: date, dto: date, apply: bool = True):
        self.date_from.blockSignals(True)
        self.date_to.blockSignals(True)
        self.date_from.setDate(dfrom)
        self.date_to.setDate(dto)
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(False)
        if apply:
            self.apply_filters()

    def refresh_chart(self):
        metric = self.current_metric(self.state.df_view if self.state.df_view is not None else pd.DataFrame())
        daily = self.last_daily
        if daily is None or daily.empty:
            self.chart.plot_timeseries(pd.DataFrame(), metric)
            return
        self.chart.plot_timeseries(
            daily,
            metric,
            show_ma=self.ma_checkbox.isChecked(),
            ma_window=7,
        )

    def update_summaries(self):
        view = self.state.df_view
        if view is None or view.empty:
            self.kpi_net.value_lbl.setText("0.00")
            self.kpi_income.value_lbl.setText("0.00")
            self.kpi_expense.value_lbl.setText("0.00")
            self.item_totals.setModel(PandasModel(pd.DataFrame()))
            self.model.set_summary(None)
            self.last_daily = pd.DataFrame()
            self.refresh_chart()
            self.update_projection()
            return

        numeric_cols = [c for c in view.columns if c not in ("Timestamp", "Date")]
        net_metric = self.current_metric(view)

        balance_daily = self.build_balance_daily(view, net_metric)

        if not balance_daily.empty and net_metric in balance_daily.columns:
            balance_start = float(balance_daily.iloc[0][net_metric])
            balance_today = float(balance_daily.iloc[-1][net_metric])
            net_change = balance_today - balance_start
        else:
            balance_start = 0.0
            balance_today = 0.0
            net_change = 0.0

        self.kpi_net.value_lbl.setText(f"{balance_today:,.2f}")
        self.kpi_income.value_lbl.setText(f"{balance_start:,.2f}")
        self.kpi_expense.value_lbl.setText(f"{net_change:,.2f}")

        metric = self.current_metric(view)
        daily = self.build_balance_daily(view, metric)

        self.last_daily = daily
        self.refresh_chart()
        self.update_projection()

        summary = {col: "" for col in view.columns}
        if "Timestamp" in summary:
            summary["Timestamp"] = "Totals"
        if "Date" in summary:
            summary["Date"] = ""
        for col in numeric_cols:
            summary[col] = f"{float(view[col].sum()):,.2f}"
        self.model.set_summary(summary)
        self.update_column_visibility()

        totals_rows = []
        day_count = max(1, len(view["Date"].dropna().unique()))
        latest_row = view.sort_values("Timestamp", ascending=False).iloc[0]
        for col in numeric_cols:
            total = float(latest_row[col])
            avg = float(view[col].sum()) / day_count
            totals_rows.append({"Item": col, "Total": total, "Avg/Day": avg})
        totals_df = pd.DataFrame(totals_rows).sort_values("Total", ascending=False).reset_index(drop=True)

        totals_model = PandasModel(totals_df)
        self.item_totals.setModel(totals_model)
        self.item_totals.resizeColumnsToContents()

    def update_projection(self):
        view = self.state.df_view if self.state.df_view is not None else pd.DataFrame()
        metric = self.current_metric(view)
        daily = self.build_balance_daily(view, metric)
        if daily is None or daily.empty or metric not in daily.columns:
            self.proj_avg_lbl.setText("0.00/day")
            self.proj_value_lbl.setText("0.00")
            self.proj_needed_lbl.setText("N/A")
            return

        diffs = pd.to_numeric(daily[metric], errors="coerce").fillna(0).diff()
        avg = float(diffs.dropna().mean() if len(diffs) > 1 else 0.0)
        self.proj_avg_lbl.setText(f"{avg:,.2f}/day")

        days = int(self.proj_days.value())
        proj_val = avg * days
        self.proj_value_lbl.setText(f"{proj_val:,.2f}")

        target = float(self.proj_target.value())
        if target == 0:
            self.proj_needed_lbl.setText("0")
        elif avg == 0:
            self.proj_needed_lbl.setText("N/A")
        else:
            needed = target / avg
            self.proj_needed_lbl.setText(f"{needed:,.1f} days")

    @staticmethod
    def build_balance_daily(view: pd.DataFrame, metric: str) -> pd.DataFrame:
        if "Date" in view.columns and metric in view.columns:
            return (
                view.dropna(subset=["Date"])
                .sort_values(["Date", "Timestamp"])
                .groupby("Date", as_index=False)[metric]
                .last()
                .sort_values("Date")
            )
        return pd.DataFrame(columns=["Date", metric])

    # -----------------------------
    # Export
    # -----------------------------
    def export_csv(self):
        view = self.state.df_view
        if view is None or view.empty:
            QMessageBox.information(self, "Nothing to export", "No rows match your filters.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export filtered CSV", "filtered.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            view.to_csv(path, index=False)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", "Filtered CSV saved successfully.")

    def export_chart_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export chart PNG", "chart.png", "PNG Files (*.png)")
        if not path:
            return
        try:
            self.chart.fig.savefig(path, dpi=150, bbox_inches="tight")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", "Chart saved successfully.")

    def update_column_visibility(self):
        if self.state.df_view is None or self.state.df_view.empty:
            return
        for col_name, cb in self.col_toggles.items():
            if col_name in self.state.df_view.columns:
                col_index = list(self.state.df_view.columns).index(col_name)
                self.table.setColumnHidden(col_index, not cb.isChecked())


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
