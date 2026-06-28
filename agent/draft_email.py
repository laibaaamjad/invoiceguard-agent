import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

DRAFT_EMAIL_PROMPT = """You are an assistant helping a small business draft a polite, professional email to a vendor disputing specific invoice discrepancies.

Vendor name: {vendor_name}
Invoice number: {invoice_number}

Discrepancies found:
{discrepancies_text}

Write a short, polite, professional email to the vendor:
- Reference the invoice number
- Clearly but courteously list each discrepancy and what was expected vs. billed
- Request a corrected invoice or clarification
- Sign off generically as "Accounts Payable Team" (no specific name)

Return ONLY the email text (subject line + body), no extra commentary.
"""


def draft_dispute_email(vendor_name: str, invoice_number: str, discrepancies: list) -> str:
    """
    Drafts a dispute email based on found discrepancies.
    This is a DRAFT ONLY — it is never sent automatically.
    Returns the email text as a string.
    """
    if not discrepancies:
        return ""

    print(f"[DEBUG draft_dispute_email] received discrepancies: {discrepancies}")

    def format_discrepancy(d):
        if isinstance(d, dict):
            return (
                f"- {d.get('type', 'issue')}: {d.get('description', 'No description provided.')} "
                f"(Invoice shows: {d.get('invoice_value', 'N/A')}, "
                f"Agreed/PO shows: {d.get('po_value', 'N/A')}, "
                f"Severity: {d.get('severity', 'unspecified')})"
            )
        else:
            # The agent sometimes hands off discrepancies as plain summary strings
            # rather than structured dicts -- handle that gracefully too.
            return f"- {d}"

    discrepancies_text = "\n".join(format_discrepancy(d) for d in discrepancies)

    prompt = DRAFT_EMAIL_PROMPT.format(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        discrepancies_text=discrepancies_text,
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text