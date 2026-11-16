"""Printable PDF invoices using ReportLab."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from core import money


def export_invoice(store, invoice_id, destination):
    invoice = store.invoice(invoice_id)
    items = store.items(invoice_id)
    if len(items) > 15:
        raise ValueError("PDF layout supports up to 15 items; extend pagination as a challenge.")
    total = sum(r["quantity"] * r["unit_cents"] for r in items)
    paid = sum(r["amount_cents"] for r in store.payments(invoice_id))
    c = canvas.Canvas(str(destination), pagesize=A4)
    w, h = A4
    c.setTitle(f"Invoice INV-{invoice_id:04d}")
    c.setFillColor(colors.HexColor("#15253b"))
    c.rect(0, h-125, w, 125, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(45, h-65, "INVOICEFORGE")
    c.setFont("Helvetica", 11)
    c.drawRightString(w-45, h-55, f"INV-{invoice_id:04d}")
    c.drawRightString(w-45, h-75, f"Issued: {invoice['issue_date']}")
    c.drawRightString(w-45, h-93, f"Due: {invoice['due_date']}")
    y = h-165
    c.setFillColor(colors.HexColor("#15253b"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(45, y, "BILL TO")
    c.setFont("Helvetica", 11)
    y -= 22
    for line in [invoice["customer"], invoice["email"]] + invoice["address"].splitlines():
        for segment in simpleSplit(line, "Helvetica", 10, w-100):
            c.drawString(45, y, segment)
            y -= 16
    y = min(y-30, h-275)
    c.setFillColor(colors.HexColor("#dce8f2"))
    c.rect(45, y-8, w-90, 28, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#15253b"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(55, y+2, "DESCRIPTION")
    c.drawRightString(365, y+2, "QTY")
    c.drawRightString(445, y+2, "UNIT")
    c.drawRightString(w-55, y+2, "AMOUNT")
    y -= 38
    c.setFont("Helvetica", 10)
    for item in items:
        description = item["description"].replace("\n", " ")
        c.drawString(55, y, description[:44])
        c.drawRightString(365, y, str(item["quantity"]))
        c.drawRightString(445, y, money(item["unit_cents"]))
        c.drawRightString(w-55, y, money(item["quantity"]*item["unit_cents"]))
        y -= 27
    y -= 12
    c.line(350, y+10, w-45, y+10)
    c.drawRightString(445, y-12, "Total")
    c.drawRightString(w-55, y-12, money(total))
    c.drawRightString(445, y-34, "Paid")
    c.drawRightString(w-55, y-34, money(paid))
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(445, y-58, "Balance")
    c.drawRightString(w-55, y-58, money(total-paid))
    if invoice["notes"]:
        c.setFont("Helvetica", 9)
        c.drawString(45, max(90, y-95), "Notes: " + invoice["notes"][:95])
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(45, 40, "Demo invoice - add your business details and tax rules before real use.")
    c.save()
