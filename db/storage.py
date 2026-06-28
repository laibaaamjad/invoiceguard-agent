import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "invoices.db")


def init_db():
    """Create the invoices table if it doesn't already exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            invoice_date TEXT,
            grand_total REAL NOT NULL,
            line_items_json TEXT,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def check_duplicate(vendor_name: str, invoice_number: str, grand_total: float):
    """
    Returns a dict describing whether this invoice looks like a duplicate.
    Two checks:
      (a) exact same vendor + invoice_number already exists
      (b) same vendor + same grand_total processed in the last 30 days
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, vendor_name, invoice_number, grand_total, processed_at "
        "FROM invoices WHERE vendor_name = ? AND invoice_number = ?",
        (vendor_name, invoice_number)
    )
    exact_match = cursor.fetchone()

    if exact_match:
        conn.close()
        return {
            "is_duplicate": True,
            "reason": "Exact match: same vendor and invoice number already processed.",
            "matched_invoice": {
                "id": exact_match[0],
                "vendor_name": exact_match[1],
                "invoice_number": exact_match[2],
                "grand_total": exact_match[3],
                "processed_at": exact_match[4],
            }
        }

    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    cursor.execute(
        "SELECT id, vendor_name, invoice_number, grand_total, processed_at "
        "FROM invoices WHERE vendor_name = ? AND grand_total = ? AND processed_at >= ?",
        (vendor_name, grand_total, thirty_days_ago)
    )
    near_match = cursor.fetchone()
    conn.close()

    if near_match:
        return {
            "is_duplicate": True,
            "reason": "Possible re-billing: same vendor and same total amount within the last 30 days, under a different invoice number.",
            "matched_invoice": {
                "id": near_match[0],
                "vendor_name": near_match[1],
                "invoice_number": near_match[2],
                "grand_total": near_match[3],
                "processed_at": near_match[4],
            }
        }

    return {"is_duplicate": False, "reason": None, "matched_invoice": None}


def save_invoice(invoice_data: dict):
    """Insert a new invoice record into the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (vendor_name, invoice_number, invoice_date, grand_total, line_items_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            invoice_data.get("vendor_name"),
            invoice_data.get("invoice_number"),
            invoice_data.get("invoice_date"),
            invoice_data.get("grand_total"),
            json.dumps(invoice_data.get("line_items", [])),
        )
    )
    conn.commit()
    conn.close()


init_db()