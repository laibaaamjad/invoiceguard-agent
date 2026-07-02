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
    import json
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part
    from agent.adk_agent import root_agent
    from agent.extract import extract_invoice_data

    # Step 1: Extract both documents (perception layer — before agent reasoning)
    invoice_bytes = await invoice_file.read()
    po_bytes = await po_file.read()
    invoice_data = extract_invoice_data(invoice_bytes, invoice_file.content_type)
    po_data = extract_invoice_data(po_bytes, po_file.content_type)

    # Step 2: Hand extracted JSON to the ADK agent for reasoning
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="invoiceguard",
        user_id="web_user",
        session_id="session_001"
    )

    runner = Runner(
        agent=root_agent,
        app_name="invoiceguard",
        session_service=session_service
    )

    prompt = (
        f"Here is an invoice and a purchase order, already extracted. "
        f"Invoice: {json.dumps(invoice_data)}. "
        f"Purchase order: {json.dumps(po_data)}. "
        f"Please audit this invoice following your process."
    )

    user_message = Content(role="user", parts=[Part(text=prompt)])

    agent_response = ""
    try:
        async for event in runner.run_async(
            user_id="web_user",
            session_id="session_001",
            new_message=user_message
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if part.text:
                        agent_response += part.text
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="The AI service is temporarily unavailable due to quota limits. Please try again in a few minutes."
            )
        raise

    return {
        "invoice_data": invoice_data,
        "po_data": po_data,
        "agent_response": agent_response,
        "has_issues": bool(agent_response)
    }