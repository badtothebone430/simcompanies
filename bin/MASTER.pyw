import sys
import os
import importlib.util

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget


def load_module(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module: {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MasterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SimCompanies Master Analyzer")
        self.resize(1300, 820)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        income_path = os.path.join(base_dir, "INCOME.pyw")
        balance_path = os.path.join(base_dir, "BALANCE.pyw")
        cashflow_path = os.path.join(base_dir, "CASHFLOW.pyw")

        income_mod = load_module("sim_income_statement_analyser", income_path)
        balance_mod = load_module("sim_balance_sheet_analyser", balance_path)
        cashflow_mod = load_module("sim_cashflow_statement_analyser", cashflow_path)

        self.income_window = income_mod.MainWindow()
        self.balance_window = balance_mod.MainWindow()
        self.cashflow_window = cashflow_mod.MainWindow()

        tabs = QTabWidget()
        tabs.addTab(self.income_window, "Income")
        tabs.addTab(self.balance_window, "Balance")
        tabs.addTab(self.cashflow_window, "Cash Flow")

        self.setCentralWidget(tabs)


def main():
    app = QApplication(sys.argv)
    f = app.font()
    if f.pointSize() <= 0:
        f.setPointSize(10)
        app.setFont(f)

    win = MasterWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
