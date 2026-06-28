import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams, StdioServerParameters

from agent.extract import extract_invoice_data
from agent.validate import validate_math
from agent.compare import compare_invoice_to_po
from agent.draft_email import draft_dispute_email


# --- Tool wrappers around your existing, already-tested functions ---
# ADK tools must be plain functions with clear docstrings and type hints;
# the agent's LLM reads these to decide when/how to call each one.

def check_invoice_math(invoice_data: dict) -> dict:
    """Validates that an invoice's line items, subtotal, tax, and grand total are mathematically consistent.
    Returns a list of any math errors found."""
    errors = validate_math(invoice_data)
    return {"math_errors": errors}


def compare_to_purchase_order(invoice_data: dict, po_data: dict) -> dict:
    """Compares an invoice's prices, quantities, and line items against the agreed purchase order.
    Returns a list of discrepancies (price mismatches, quantity mismatches, unauthorized items)."""
    return compare_invoice_to_po(invoice_data, po_data)


def draft_vendor_dispute_email(vendor_name: str, invoice_number: str, discrepancies: list) -> dict:
    """Drafts (but does not send) a polite dispute email to a vendor about specific invoice discrepancies."""
    email_text = draft_dispute_email(vendor_name, invoice_number, discrepancies)
    return {"draft_email": email_text}


# --- MCP toolset: connects this agent to the InvoiceGuard Memory Server ---
# This gives the agent access to check_duplicate_invoice and save_invoice_record,
# running as a separate MCP process, via the standard MCP protocol.
memory_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=[os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server", "server.py")],
        ),
        timeout=30,
    )
)


root_agent = Agent(
    model="gemini-2.5-flash",
    name="invoiceguard_agent",
    description="An agent that audits vendor invoices against purchase orders, checks math, detects duplicate billing via memory, and drafts dispute emails.",
    instruction=(
        "You are InvoiceGuard, an accounts-payable auditing agent. "
        "Given an extracted invoice and purchase order, your job is to: "
        "1) check the invoice's math using check_invoice_math, "
        "2) compare it to the purchase order using compare_to_purchase_order, "
        "3) check for duplicate or re-billing using check_duplicate_invoice (from memory), "
        "4) if there are discrepancies, draft a dispute email using draft_vendor_dispute_email, "
        "5) always save the invoice using save_invoice_record so future checks can reference it. "
        "Be precise and only flag real numerical or item mismatches — do not invent issues."
    ),
    tools=[check_invoice_math, compare_to_purchase_order, draft_vendor_dispute_email, memory_toolset],
)