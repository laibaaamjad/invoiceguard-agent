from fastapi import FastAPI, File, UploadFile, HTTPException
from agent.extract import extract_invoice_data
from agent.compare import compare_invoice_to_po
from agent.orchestrator import process_invoice
from agent.draft_email import draft_dispute_email
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from db.storage import init_db, check_duplicate, save_invoice
from agent.validate import validate_math

app = FastAPI(title="InvoiceGuard")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/app")
def serve_frontend():
    return FileResponse("static/index.html")
    
@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/test-extract")
async def test_extract(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        mime_type = file.content_type
        # If mime_type is not provided, we can fallback or raise error, but standard uploads have it
        if not mime_type:
            mime_type = "application/octet-stream"
            
        result = extract_invoice_data(file_bytes, mime_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-validate")
async def test_validate(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        mime_type = file.content_type
        if not mime_type:
            mime_type = "application/octet-stream"
            
        extracted_data = extract_invoice_data(file_bytes, mime_type)
        errors = validate_math(extracted_data)
        
        return {
            "extracted_data": extracted_data,
            "validation_errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-db-init")
def test_db_init():
    init_db()
    return {"status": "db initialized"}


@app.post("/test-save-invoice")
def test_save_invoice(invoice_data: dict):
    save_invoice(invoice_data)
    duplicate_check = check_duplicate(
        vendor_name=invoice_data.get("vendor_name"),
        invoice_number=invoice_data.get("invoice_number"),
        grand_total=invoice_data.get("grand_total"),
    )
    return {
        "saved": True,
        "duplicate_check": duplicate_check
    }

@app.post("/test-compare")
async def test_compare(invoice_file: UploadFile, po_file: UploadFile):
    invoice_bytes = await invoice_file.read()
    po_bytes = await po_file.read()

    invoice_data = extract_invoice_data(invoice_bytes, invoice_file.content_type)
    po_data = extract_invoice_data(po_bytes, po_file.content_type)

    result = compare_invoice_to_po(invoice_data, po_data)

    return {
        "invoice_data": invoice_data,
        "po_data": po_data,
        "comparison": result
    }

@app.post("/test-draft-email")
def test_draft_email(payload: dict):
    email_text = draft_dispute_email(
        vendor_name=payload["vendor_name"],
        invoice_number=payload["invoice_number"],
        discrepancies=payload["discrepancies"],
    )
    return {"draft_email": email_text}

@app.post("/process-invoice")
async def process_invoice_endpoint(invoice_file: UploadFile, po_file: UploadFile):
    invoice_bytes = await invoice_file.read()
    po_bytes = await po_file.read()

    result = process_invoice(
        invoice_bytes=invoice_bytes,
        invoice_mime_type=invoice_file.content_type,
        po_bytes=po_bytes,
        po_mime_type=po_file.content_type,
    )

    return result