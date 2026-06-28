from agent.extract import extract_invoice_data
from agent.validate import validate_math
from agent.compare import compare_invoice_to_po
from agent.draft_email import draft_dispute_email
from db.storage import check_duplicate, save_invoice


def process_invoice(invoice_bytes: bytes, invoice_mime_type: str,
                     po_bytes: bytes, po_mime_type: str) -> dict:
    """
    Runs the full InvoiceGuard pipeline:
    1. Extract invoice and PO data
    2. Validate invoice math
    3. Compare invoice against PO
    4. Check for duplicate billing in memory
    5. If any discrepancies exist, draft a dispute email (never sent)
    6. Save this invoice to memory for future duplicate checks
    Returns one combined result dict with all findings.
    """

    # Step 1: Extract
    invoice_data = extract_invoice_data(invoice_bytes, invoice_mime_type)
    po_data = extract_invoice_data(po_bytes, po_mime_type)

    # Step 2: Validate math
    math_errors = validate_math(invoice_data)

    # Step 3: Compare against PO
    comparison_result = compare_invoice_to_po(invoice_data, po_data)
    discrepancies = comparison_result.get("discrepancies", [])

    # Step 4: Check for duplicates in memory
    duplicate_check = check_duplicate(
        vendor_name=invoice_data.get("vendor_name"),
        invoice_number=invoice_data.get("invoice_number"),
        grand_total=invoice_data.get("grand_total"),
    )

    # Step 5: Draft dispute email if there are any issues at all
    all_issues = discrepancies.copy()
    if duplicate_check.get("is_duplicate"):
        all_issues.append({
            "type": "duplicate_billing",
            "description": duplicate_check.get("reason"),
            "severity": "high",
            "invoice_value": invoice_data.get("invoice_number"),
            "po_value": "N/A",
        })

    draft_email = ""
    if discrepancies:  # only draft for price/quantity/unauthorized issues, not duplicates
        draft_email = draft_dispute_email(
            vendor_name=invoice_data.get("vendor_name"),
            invoice_number=invoice_data.get("invoice_number"),
            discrepancies=discrepancies,
        )

    # Step 6: Save to memory (always save, so future invoices can be checked against this one)
    save_invoice(invoice_data)

    return {
        "invoice_data": invoice_data,
        "po_data": po_data,
        "math_errors": math_errors,
        "discrepancies": discrepancies,
        "duplicate_check": duplicate_check,
        "draft_email": draft_email,
        "has_issues": bool(math_errors or discrepancies or duplicate_check.get("is_duplicate")),
    }