# InvoiceForge — Desktop Invoicing Studio

A Python desktop invoicing application using **PySide6 + SQLite + ReportLab**. Built as an educational portfolio project.

## Features
- Save customers (name, email, address)
- Create numbered invoices with multiple line items
- Store exact monetary values as integer cents
- Record partial or full payments with overpayment protection
- View Paid, Open and Overdue invoices
- Dashboard: invoiced, received, outstanding and overdue totals
- Export individual invoices to PDF
- Automated tests for accounting and database logic

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Tests
```powershell
python -m unittest discover -s tests -v
```

## File structure
- `main.py` — GUI entry point
- `gui.py` — windows, tabs, dialogs, tables and button callbacks
- `db.py` — database schema and SQL queries
- `core.py` — date and money validations
- `pdf_export.py` — PDF generation
- `tests/` — automated tests

## Try it
1. Open **Customers** and add a customer.
2. Open **Invoices**, select **New invoice**, and add one or more line items.
3. Select the new invoice row and choose **Record payment**.
4. Filter by status; select an invoice and **Export PDF**.

## Accounting notes
- Default currency display is dollars, intended for AUD demo records.
- No sales tax / GST or multi-currency support; add tax and localisation before real use.
- This is a simplified invoicing tracker, not double-entry accounting or tax-compliant software.
- Financial data lives in `data/invoiceforge.db` on your own computer and is ignored by Git.
- The basic PDF layout supports up to 15 items; pagination is an extension challenge.
- The GUI uses your computer's current date for dashboard status. The database layer supports historic `as_of` reports.

## Next improvements
- Tax / GST handling and invoice metadata
- Edit or void invoices with audit trail
- Invoice PDF pagination
- Date range filtering and export to CSV
- Database backup and restore
- Windows executable packaging with PyInstaller
