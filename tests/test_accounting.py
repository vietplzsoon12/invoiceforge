import tempfile
import unittest
from pathlib import Path
from core import cents, money, total_cents
from db import Store


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.db")
        self.customer = self.store.add_customer("Acme Client", "billing@example.com")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def create(self):
        return self.store.create_invoice(
            self.customer, "2026-10-01", "2026-10-31",
            [{"description": "Consulting", "quantity": 2, "unit_cents": 12500},
             {"description": "Hosting", "quantity": 1, "unit_cents": 5000}])

    def test_money_rounding(self):
        self.assertEqual(cents("19.995"), 2000)
        self.assertEqual(money(2000), "$20.00")
        with self.assertRaises(ValueError):
            cents("-1")

    def test_invoice_items_and_total(self):
        ident = self.create()
        self.assertEqual(total_cents(self.store.items(ident)), 30000)
        self.assertEqual(self.store.invoices("2026-11-17")[0]["balance_cents"], 30000)

    def test_partial_and_full_payment(self):
        ident = self.create()
        self.store.record_payment(ident, "2026-10-15", 10000)
        row = self.store.invoices("2026-11-17")[0]
        self.assertEqual((row["balance_cents"], row["status"]), (20000, "Overdue"))
        self.store.record_payment(ident, "2026-11-01", 20000)
        self.assertEqual(self.store.invoices("2026-11-17")[0]["status"], "Paid")

    def test_reject_overpayment(self):
        ident = self.create()
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.store.record_payment(ident, "2026-10-15", 30001)
        self.assertEqual(len(self.store.payments(ident)), 0)

    def test_as_of_filters_future_payments(self):
        ident = self.create()
        self.store.record_payment(ident, "2026-11-10", 10000)
        self.assertEqual(self.store.invoices("2026-11-01")[0]["balance_cents"], 30000)
        self.assertEqual(self.store.invoices("2026-11-17")[0]["balance_cents"], 20000)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            self.store.add_customer("   ")
        with self.assertRaises(ValueError):
            self.store.create_invoice(self.customer, "2026-10-31", "2026-10-01", [
                {"description": "Service", "quantity": 1, "unit_cents": 100}])


if __name__ == "__main__":
    unittest.main()
