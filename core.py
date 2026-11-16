"""Accounting calculations and input validation; no GUI dependencies."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def cents(value):
    """Convert a positive dollar amount to integer cents."""
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid monetary amount.") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded <= 0:
        raise ValueError("Amount must be at least $0.01.")
    return int(rounded * 100)


def money(value_cents):
    return f"${Decimal(value_cents) / Decimal(100):,.2f}"


def check_date(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError("Date must be a real date in YYYY-MM-DD format.") from None


def total_cents(items):
    total = 0
    for item in items:
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        unit_cents = int(item["unit_cents"])
        if unit_cents <= 0:
            raise ValueError("Unit price must be positive.")
        total += quantity * unit_cents
    return total
