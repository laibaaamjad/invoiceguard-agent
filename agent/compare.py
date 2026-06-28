import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

COMPARE_PROMPT = """You are comparing a vendor invoice against a purchase order (PO) to find discrepancies.

Invoice data (what was billed):
{invoice_json}

Purchase order data (what was agreed):
{po_json}

Compare them and identify discrepancies. For each line item in the invoice, check:
1. Does the unit_price match what was agreed in the PO for the same item? (price_mismatch)
2. Does the quantity match what was agreed in the PO? (quantity_mismatch)
3. Is this item present in the PO at all, or was it billed without being ordered? (unauthorized_item)

Return ONLY valid JSON in this exact structure, no other text:
{{
  "discrepancies": [
    {{
      "type": "price_mismatch" | "quantity_mismatch" | "unauthorized_item",
      "description": "human-readable explanation of the issue",
      "severity": "low" | "medium" | "high",
      "invoice_value": "what the invoice shows",
      "po_value": "what the PO shows (or 'not found' if unauthorized_item)"
    }}
  ]
}}

If there are no discrepancies, return {{"discrepancies": []}}.
"""


def compare_invoice_to_po(invoice_data: dict, po_data: dict) -> dict:
    """
    Compares extracted invoice data against extracted PO data using Gemini.
    Returns a dict: {"discrepancies": [...]}
    """
    prompt = COMPARE_PROMPT.format(
        invoice_json=json.dumps(invoice_data, indent=2),
        po_json=json.dumps(po_data, indent=2),
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )

    try:
        result = json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError(f"Gemini did not return valid JSON for comparison: {e}")

    return result