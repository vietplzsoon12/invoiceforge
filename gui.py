"""PySide6 desktop UI; the database and PDF code live in separate modules."""
from datetime import date, timedelta
from pathlib import Path
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget
)
from core import cents, money
from pdf_export import export_invoice

STYLE = """
QWidget { background: #f4f7fb; color: #233247; font-size: 13px; }
QMainWindow { background: #f4f7fb; }
QLabel#heading { font-size: 25px; font-weight: bold; color: #15253b; }
QLabel#metric { font-size: 20px; font-weight: bold; color: #167f78; }
QPushButton { background: #176b8a; color: white; padding: 8px 13px; border-radius: 5px; }
QPushButton:hover { background: #12536d; }
QLineEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox, QTableWidget {
    background: white; border: 1px solid #d4dce6; border-radius: 4px; padding: 5px;
}
QHeaderView::section { background: #e5edf5; padding: 7px; border: 0; font-weight: bold; }
QTabBar::tab { padding: 11px 20px; background: #e1e9f2; }
QTabBar::tab:selected { background: white; color: #176b8a; font-weight: bold; }
"""


def date_input(when):
    field = QDateEdit()
    field.setCalendarPopup(True)
    field.setDisplayFormat("yyyy-MM-dd")
    field.setDate(QDate(when.year, when.month, when.day))
    return field


def read_date(widget):
    return widget.date().toString("yyyy-MM-dd")


class CustomerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New customer")
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.address = QTextEdit()
        self.address.setFixedHeight(70)
        form = QFormLayout(self)
        form.addRow("Name*", self.name)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class InvoiceDialog(QDialog):
    def __init__(self, customers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create invoice")
        self.resize(750, 500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.customer = QComboBox()
        for row in customers:
            self.customer.addItem(row["name"], row["id"])
        self.issued = date_input(date.today())
        self.due = date_input(date.today() + timedelta(days=30))
        self.notes = QLineEdit()
        form.addRow("Customer", self.customer)
        form.addRow("Issue date", self.issued)
        form.addRow("Due date", self.due)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)
        layout.addWidget(QLabel("Line items — enter price in dollars"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Description", "Quantity", "Unit price ($)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        bar = QHBoxLayout()
        add = QPushButton("+ Add item")
        remove = QPushButton("Remove selected")
        add.clicked.connect(self.add_row)
        remove.clicked.connect(self.remove_row)
        bar.addWidget(add)
        bar.addWidget(remove)
        bar.addStretch()
        layout.addLayout(bar)
        self.add_row()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for column, value in enumerate(("", "1", "0.00")):
            self.table.setItem(r, column, QTableWidgetItem(value))

    def remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def values(self):
        items = []
        for r in range(self.table.rowCount()):
            def cell(c):
                item = self.table.item(r, c)
                return item.text().strip() if item else ""
            try:
                qty = int(cell(1))
            except ValueError:
                raise ValueError(f"Row {r+1}: quantity must be a whole number.") from None
            items.append({"description": cell(0), "quantity": qty,
                          "unit_cents": cents(cell(2))})
        return (self.customer.currentData(), read_date(self.issued),
                read_date(self.due), items, self.notes.text())


class PaymentDialog(QDialog):
    def __init__(self, max_cents, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record payment")
        form = QFormLayout(self)
        self.amount = QLineEdit(f"{max_cents/100:.2f}")
        self.paid_on = date_input(date.today())
        form.addRow(f"Amount (maximum {money(max_cents)})", self.amount)
        form.addRow("Payment date", self.paid_on)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle("InvoiceForge — Invoicing Studio")
        self.resize(1100, 700)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        title = QLabel("INVOICEFORGE")
        title.setObjectName("heading")
        outer.addWidget(title)
        outer.addWidget(QLabel("Customers • invoices • payments • PDF export"))
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        self.build_invoices_tab()
        self.build_customers_tab()
        self.refresh_all()

    def build_invoices_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        metrics = QGridLayout()
        self.metric_labels = {}
        for i, (key, title) in enumerate((("invoiced", "TOTAL INVOICED"),
                                         ("received", "PAYMENTS RECEIVED"),
                                         ("outstanding", "OUTSTANDING"),
                                         ("overdue", "OVERDUE"))):
            box = QVBoxLayout()
            box.addWidget(QLabel(title))
            label = QLabel("$0.00")
            label.setObjectName("metric")
            self.metric_labels[key] = label
            box.addWidget(label)
            metrics.addLayout(box, 0, i)
        layout.addLayout(metrics)
        bar = QHBoxLayout()
        new_btn = QPushButton("+ New invoice")
        new_btn.clicked.connect(self.new_invoice)
        pay_btn = QPushButton("Record payment")
        pay_btn.clicked.connect(self.pay_invoice)
        export_btn = QPushButton("Export PDF")
        export_btn.clicked.connect(self.export_pdf)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_all)
        self.filter = QComboBox()
        self.filter.addItems(["All", "Open", "Overdue", "Paid"])
        self.filter.currentTextChanged.connect(self.refresh_invoices)
        for widget in (new_btn, pay_btn, export_btn, refresh_btn):
            bar.addWidget(widget)
        bar.addStretch()
        bar.addWidget(QLabel("Status:"))
        bar.addWidget(self.filter)
        layout.addLayout(bar)
        self.invoice_table = QTableWidget(0, 7)
        self.invoice_table.setHorizontalHeaderLabels(
            ["Invoice", "Customer", "Issued", "Due", "Total", "Balance", "Status"])
        self.invoice_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.invoice_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.invoice_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.invoice_table)
        self.tabs.addTab(tab, "Invoices")

    def build_customers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        add = QPushButton("+ Add customer")
        add.clicked.connect(self.new_customer)
        layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignLeft)
        self.customer_table = QTableWidget(0, 3)
        self.customer_table.setHorizontalHeaderLabels(["Name", "Email", "Address"])
        self.customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.customer_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.customer_table)
        self.tabs.addTab(tab, "Customers")

    def show_error(self, exc):
        QMessageBox.warning(self, "Could not complete action", str(exc))

    def selected_invoice(self):
        row = self.invoice_table.currentRow()
        if row < 0:
            raise ValueError("Select an invoice row first.")
        return int(self.invoice_table.item(row, 0).data(Qt.ItemDataRole.UserRole))

    def refresh_all(self):
        self.refresh_customers()
        self.refresh_invoices()

    def refresh_customers(self):
        records = self.store.customers()
        self.customer_table.setRowCount(len(records))
        for r, customer in enumerate(records):
            for c, field in enumerate(("name", "email", "address")):
                self.customer_table.setItem(r, c, QTableWidgetItem(customer[field]))

    def refresh_invoices(self):
        rows = [r for r in self.store.invoices() if self.filter.currentText() in ("All", r["status"])]
        self.invoice_table.setRowCount(len(rows))
        for r, inv in enumerate(rows):
            fields = (inv["number"], inv["customer"], inv["issue_date"],
                      inv["due_date"], money(inv["total_cents"]),
                      money(inv["balance_cents"]), inv["status"])
            for c, value in enumerate(fields):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, inv["id"])
                self.invoice_table.setItem(r, c, item)
        for key, value in self.store.summary().items():
            self.metric_labels[key].setText(money(value))

    def new_customer(self):
        dlg = CustomerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.add_customer(dlg.name.text(), dlg.email.text(),
                                        dlg.address.toPlainText())
                self.refresh_all()
            except Exception as exc:
                self.show_error(exc)

    def new_invoice(self):
        customers = self.store.customers()
        if not customers:
            QMessageBox.information(self, "Add a customer", "Add a customer before creating an invoice.")
            self.tabs.setCurrentIndex(1)
            return
        dlg = InvoiceDialog(customers, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                args = dlg.values()
                self.store.create_invoice(*args)
                self.filter.setCurrentText("All")
                self.refresh_all()
            except Exception as exc:
                self.show_error(exc)

    def pay_invoice(self):
        try:
            inv_id = self.selected_invoice()
            row = next(r for r in self.store.invoices() if r["id"] == inv_id)
            if row["balance_cents"] == 0:
                raise ValueError("This invoice is already fully paid.")
            dlg = PaymentDialog(row["balance_cents"], self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.store.record_payment(inv_id, read_date(dlg.paid_on),
                                          cents(dlg.amount.text()))
                self.refresh_all()
        except (ValueError, StopIteration) as exc:
            self.show_error(exc)

    def export_pdf(self):
        try:
            inv_id = self.selected_invoice()
            suggested = str(Path.home() / f"INV-{inv_id:04d}.pdf")
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save invoice PDF", suggested, "PDF files (*.pdf)")
            if filename:
                export_invoice(self.store, inv_id, filename)
                QMessageBox.information(self, "Exported", f"Saved invoice to:\n{filename}")
        except (ValueError, OSError) as exc:
            self.show_error(exc)
