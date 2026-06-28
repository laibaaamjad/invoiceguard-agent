import sys
import os

# Add the project root (one level up from this file) to Python's import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from db.storage import check_duplicate as _check_duplicate, save_invoice as _save_invoice
mcp = FastMCP("InvoiceGuard Memory Server")


@mcp.tool()
def check_duplicate_invoice(vendor_name: str, invoice_number: str, grand_total: float) -> dict:
    """
    Check whether an invoice looks like a duplicate or re-billing attempt.
    Returns is_duplicate (bool), reason (str or null), and matched_invoice details if found.
    """
    return _check_duplicate(vendor_name, invoice_number, grand_total)


@mcp.tool()
def save_invoice_record(vendor_name: str, invoice_number: str, invoice_date: str,
                         grand_total: float, line_items: list) -> dict:
    """
    Save a processed invoice into long-term memory so future invoices
    can be checked against it for duplicates or re-billing patterns.
    """
    invoice_data = {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "grand_total": grand_total,
        "line_items": line_items,
    }
    _save_invoice(invoice_data)
    return {"status": "saved", "vendor_name": vendor_name, "invoice_number": invoice_number}


if __name__ == "__main__":
    mcp.run()