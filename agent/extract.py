import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types, errors
from pydantic import BaseModel, Field
from typing import List, Optional

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None

class InvoiceData(BaseModel):
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    line_items: List[LineItem] = []
    subtotal: Optional[float] = None
    tax_or_fees: Optional[float] = 0.0
    grand_total: Optional[float] = None

def extract_invoice_data(file_bytes: bytes, mime_type: str) -> dict:
    """
    Extracts structured invoice data from the provided file bytes using Gemini 2.5 Flash.
    
    Args:
        file_bytes: The raw bytes of the invoice file (PDF or image).
        mime_type: The MIME type of the file (e.g., 'application/pdf', 'image/png').
        
    Returns:
        A dictionary containing the extracted invoice data.
        
    Raises:
        ValueError: If GEMINI_API_KEY is missing, or if the API returns invalid JSON.
        RuntimeError: If the Gemini API call fails.
    """
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
        
    # Initialize the Google GenAI Client
    client = genai.Client(api_key=api_key)
    
    # Prepare the file part from raw bytes
    file_part = types.Part.from_bytes(
        data=file_bytes,
        mime_type=mime_type,
    )
    
    prompt = (
        "Extract vendor_name, invoice_number, invoice_date, line_items "
        "(each with description, quantity, unit_price, line_total), subtotal "
        "(sum of line items before tax/fees), tax_or_fees (any tax, shipping, or fee "
        "amount shown separately, default to 0 if none), and grand_total from this invoice."
    )
    
    max_retries = 3
    backoff_delays = [2, 4, 8]
    
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[file_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InvoiceData,
                ),
            )
            break
        except errors.APIError as e:
            is_client_error = (e.code is not None and 400 <= e.code < 500) or isinstance(e, errors.ClientError)
            if is_client_error:
                raise ValueError(f"Gemini API client error (HTTP {e.code}): {e.message}")
            if attempt == max_retries:
                raise RuntimeError(f"Gemini API call failed after {max_retries} retries: HTTP {e.code} - {e.message}")
            delay = backoff_delays[attempt]
            print(f"[Retry {attempt + 1}/{max_retries}] Transient Gemini API error {e.code}: {e.message}. Retrying in {delay}s...")
            time.sleep(delay)
        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(f"Gemini API call failed after {max_retries} retries with unexpected error: {str(e)}")
            delay = backoff_delays[attempt]
            print(f"[Retry {attempt + 1}/{max_retries}] Unexpected error: {str(e)}. Retrying in {delay}s...")
            time.sleep(delay)
        
    text = response.text
    if not text:
        raise ValueError("Gemini API returned an empty response.")
        
    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini response was not valid JSON: {str(e)}. Raw response: {text}")
