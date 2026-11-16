"""SQLite persistence. All writes are transactional and use placeholders."""
import sqlite3
from datetime import date
from pathlib import Path
from core import check_date, total_cents

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "invoiceforge.db"

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    email TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    CHECK(due_date >= issue_date)
);
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL CHECK(length(trim(description)) > 0),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_cents INTEGER NOT NULL CHECK(unit_cents > 0)
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    paid_on TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    CHECK(length(paid_on) = 10)
);
CREATE INDEX IF NOT EXISTS ix_invoice_customer ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS ix_payment_invoice ON payments(invoice_id);
"""

class Store:
    def __init__(self, path=DEFAULT_DB):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys=ON")
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    def add_customer(self, name, email="", address=""):
        if not name.strip():
            raise ValueError("Customer name cannot be empty.")
        with self.con:
            cur = self.con.execute(
                "INSERT INTO customers(name,email,address) VALUES(?,?,?)",
                (name.strip(), email.strip(), address.strip()))
        return cur.lastrowid

    def customers(self):
        return self.con.execute("SELECT * FROM customers ORDER BY name, id").fetchall()

    def create_invoice(self, customer_id, issue_date, due_date, items, notes=""):
        issue_date, due_date = check_date(issue_date), check_date(due_date)
        if due_date < issue_date:
            raise ValueError("Due date cannot be before issue date.")
        if not items:
            raise ValueError("Add at least one line item.")
        cleaned = []
        for item in items:
            desc = str(item["description"]).strip()
            if not desc:
                raise ValueError("Line item descriptions cannot be empty.")
            quantity = int(item["quantity"])
            unit = int(item["unit_cents"])
            cleaned.append({"description": desc, "quantity": quantity, "unit_cents": unit})
        total_cents(cleaned)
        with self.con:
            exists = self.con.execute("SELECT 1 FROM customers WHERE id=?", (customer_id,)).fetchone()
            if not exists:
                raise ValueError("Select a valid customer.")
            cur = self.con.execute(
                "INSERT INTO invoices(customer_id,issue_date,due_date,notes) VALUES(?,?,?,?)",
                (customer_id, issue_date, due_date, notes.strip()))
            invoice_id = cur.lastrowid
            self.con.executemany(
                "INSERT INTO invoice_items(invoice_id,description,quantity,unit_cents) VALUES(?,?,?,?)",
                [(invoice_id, item["description"], item["quantity"], item["unit_cents"]) for item in cleaned])
        return invoice_id

    def invoices(self, as_of=None):
        as_of = check_date(as_of or date.today().isoformat())
        return self.con.execute("""
            WITH totals AS (
              SELECT invoice_id, SUM(quantity*unit_cents) AS total
              FROM invoice_items GROUP BY invoice_id
            ), paid AS (
              SELECT invoice_id, SUM(amount_cents) AS paid
              FROM payments WHERE paid_on <= ? GROUP BY invoice_id
            )
            SELECT i.id, printf('INV-%04d', i.id) AS number,
              c.name AS customer, i.issue_date, i.due_date,
              totals.total AS total_cents,
              COALESCE(paid.paid,0) AS paid_cents,
              totals.total-COALESCE(paid.paid,0) AS balance_cents,
              CASE WHEN totals.total-COALESCE(paid.paid,0)=0 THEN 'Paid'
                WHEN i.due_date < ? THEN 'Overdue' ELSE 'Open' END AS status
            FROM invoices i JOIN customers c ON c.id=i.customer_id
            JOIN totals ON totals.invoice_id=i.id
            LEFT JOIN paid ON paid.invoice_id=i.id
            WHERE i.issue_date <= ?
            ORDER BY i.id DESC
        """, (as_of, as_of, as_of)).fetchall()

    def invoice(self, invoice_id):
        row = self.con.execute("""
            SELECT i.*, c.name AS customer, c.email, c.address
            FROM invoices i JOIN customers c ON c.id=i.customer_id
            WHERE i.id=?
        """, (invoice_id,)).fetchone()
        if row is None:
            raise ValueError("Invoice not found.")
        return row

    def items(self, invoice_id):
        return self.con.execute("SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY id", (invoice_id,)).fetchall()

    def payments(self, invoice_id):
        return self.con.execute("SELECT * FROM payments WHERE invoice_id=? ORDER BY paid_on,id", (invoice_id,)).fetchall()

    def record_payment(self, invoice_id, paid_on, amount_cents):
        paid_on = check_date(paid_on)
        amount_cents = int(amount_cents)
        if amount_cents <= 0:
            raise ValueError("Payment must be positive.")
        doc = self.invoice(invoice_id)
        if paid_on < doc["issue_date"]:
            raise ValueError("Payment date cannot be before issue date.")
        # Immediate transaction prevents two writers both accepting an overpayment.
        self.con.execute("BEGIN IMMEDIATE")
        try:
            total = self.con.execute(
                "SELECT SUM(quantity*unit_cents) FROM invoice_items WHERE invoice_id=?",
                (invoice_id,)).fetchone()[0]
            paid = self.con.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE invoice_id=?",
                (invoice_id,)).fetchone()[0]
            if amount_cents > total - paid:
                raise ValueError("Payment exceeds remaining invoice balance.")
            self.con.execute("INSERT INTO payments(invoice_id,paid_on,amount_cents) VALUES(?,?,?)",
                             (invoice_id, paid_on, amount_cents))
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    def summary(self, as_of=None):
        rows = self.invoices(as_of)
        return {"invoiced": sum(r["total_cents"] for r in rows),
                "received": sum(r["paid_cents"] for r in rows),
                "outstanding": sum(r["balance_cents"] for r in rows),
                "overdue": sum(r["balance_cents"] for r in rows if r["status"] == "Overdue")}
