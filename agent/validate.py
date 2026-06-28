def validate_math(invoice_data: dict) -> list:
    """
    Validates the mathematical calculations in the extracted invoice data:
    1. quantity * unit_price == line_total (for each line item, with 1 cent tolerance)
    2. sum(line_total) == subtotal (with 1 cent tolerance)
    3. subtotal + tax_or_fees == grand_total (with 1 cent tolerance)
    
    Args:
        invoice_data: Dictionary representing the extracted invoice data.
        
    Returns:
        A list of dictionaries containing any validation errors found.
        Each error dict has: check_name, expected_value, actual_value, message.
        Returns an empty list if all calculations are correct.
    """
    errors = []
    
    line_items = invoice_data.get("line_items", [])
    if not isinstance(line_items, list):
        line_items = []
        
    # 1. Verify line item calculations (quantity * unit_price == line_total)
    for idx, item in enumerate(line_items):
        desc = item.get("description", f"Item {idx + 1}")
        qty = item.get("quantity")
        price = item.get("unit_price")
        total = item.get("line_total")
        
        if qty is not None and price is not None and total is not None:
            expected_total = qty * price
            if abs(expected_total - total) > 0.01:
                errors.append({
                    "check_name": f"line_item_{idx}_total",
                    "expected_value": round(expected_total, 2),
                    "actual_value": round(total, 2),
                    "message": f"Line item '{desc}' at index {idx} has total {total:.2f}, but expected {expected_total:.2f} based on quantity {qty} and unit price {price:.2f}."
                })
                
    # 2. Verify subtotal (sum of all line_total values == subtotal)
    # Sum up all non-None line totals. If a line total is missing, treat it as 0.0
    sum_line_totals = sum(item.get("line_total") for item in line_items if item.get("line_total") is not None)
    subtotal = invoice_data.get("subtotal")
    
    if subtotal is not None:
        if abs(sum_line_totals - subtotal) > 0.01:
            errors.append({
                "check_name": "subtotal_match",
                "expected_value": round(sum_line_totals, 2),
                "actual_value": round(subtotal, 2),
                "message": f"Invoice subtotal is {subtotal:.2f}, but expected {sum_line_totals:.2f} (sum of all line totals)."
            })
            
    # 3. Verify grand total (subtotal + tax_or_fees == grand_total)
    tax_or_fees = invoice_data.get("tax_or_fees")
    if tax_or_fees is None:
        tax_or_fees = 0.0
        
    grand_total = invoice_data.get("grand_total")
    
    if subtotal is not None and grand_total is not None:
        expected_grand_total = subtotal + tax_or_fees
        if abs(expected_grand_total - grand_total) > 0.01:
            errors.append({
                "check_name": "grand_total_match",
                "expected_value": round(expected_grand_total, 2),
                "actual_value": round(grand_total, 2),
                "message": f"Invoice grand total is {grand_total:.2f}, but expected {expected_grand_total:.2f} (subtotal {subtotal:.2f} + tax_or_fees {tax_or_fees:.2f})."
            })
            
    return errors
