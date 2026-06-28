# 🛡️ InvoiceGuard

**An AI agent that audits vendor invoices against purchase orders — catching price mismatches, math errors, and duplicate billing before they cost a business money.**

Built for the [AI Agents: Intensive Vibe Coding Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project) — **Agents for Business** track.

---

## The Problem

Small businesses process dozens of vendor invoices every month. Someone on the accounts payable team has to manually check each one against the agreed purchase order: do the prices match what was negotiated? Does the math add up? Has this vendor already billed for this exact thing before?

This work is tedious, repetitive, and easy to get wrong, and the mistakes that slip through cost real money. InvoiceGuard automates this entire review process with an AI agent that reasons through it the way a careful accounts payable clerk would, but in seconds.

## The Solution

Upload an invoice and its matching purchase order. InvoiceGuard:

1. **Extracts** structured data from both documents (vendor, line items, totals) using Gemini's multimodal understanding
2. **Validates** the invoice's own math, do quantities × prices add up to the stated totals?
3. **Compares** the invoice against the purchase order, are prices, quantities, and line items what was actually agreed?
4. **Checks memory** has this vendor already billed for this invoice number, or the same amount recently? (Duplicate/re-billing detection)
5. **Drafts** (but never sends) a polite dispute email to the vendor if discrepancies are found
6. **Remembers** saves the invoice so future submissions can be checked against it

A human always reviews and sends the email manually. The agent never takes that action on its own, and this is a deliberate safety guardrail, not a missing feature.

## Why Agents, Specifically

This isn't a single LLM call, it's a genuine multi-step agent because:

- **It reasons across multiple steps**, deciding what to do next based on what the previous step found (clean invoice → stop; discrepancy found → draft an email)
- **It uses tools**, not just language, deterministic math validation (deliberately *not* delegated to the LLM, since LLMs are unreliable at arithmetic), a database lookup tool, and a document-comparison tool
- **It has memory that persists and changes future behavior**, an invoice processed today changes how the agent treats a similar invoice next month
- **It is deliberately constrained**, autonomous enough to draft an action, but gated from executing it without a human

## Architecture

```
                    ┌─────────────────────┐
   Invoice (PDF) ──▶│                      │
                    │   Gemini Extraction  │──▶ structured JSON
   PO (PDF)      ──▶│                      │    (vendor, line items, totals)
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  ADK Agent           │
                    │  (invoiceguard_agent)│
                    │                      │
                    │  Tools:              │
                    │  • check_invoice_math│ (Python, deterministic)
                    │  • compare_to_po     │ (Gemini reasoning)
                    │  • draft_email       │ (Gemini generation)
                    │  • MCP Memory Server │──▶ check_duplicate_invoice
                    │                      │    save_invoice_record
                    └─────────────────────┘    (SQLite, via MCP protocol)
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Discrepancy report  │
                    │   + draft email       │
                    │   (human reviews)      │
                    └─────────────────────┘
```

### Key Concepts Demonstrated

| Concept | Where |
|---|---|
| **Agent (Google ADK)** | `agent/adk_agent.py`, `root_agent` built with `google.adk.agents.Agent`, given tools and a reasoning instruction |
| **MCP Server** | `mcp_server/server.py` a standalone `FastMCP` server exposing `check_duplicate_invoice` and `save_invoice_record` as MCP tools, connected to the ADK agent via `MCPToolset` over stdio |
| **Deployability** | Deployed as a FastAPI web app (see Deployment section below); designed to run anywhere a Python web service can run |

## Tech Stack

- **Gemini API** (`gemini-2.5-flash`) — multimodal document extraction, comparison reasoning, email drafting
- **Google ADK** (`google-adk`) — agent orchestration and tool-calling
- **FastMCP**, MCP server implementation for the memory/duplicate-detection tools
- **FastAPI**, web backend and API
- **SQLite**, persistent invoice memory
- **Vanilla HTML/CSS/JS**, frontend (no framework, kept simple and dependency-free)

## Project Structure

```
invoiceguard/
├── main.py                  # FastAPI app, routes
├── agent/
│   ├── extract.py           # Gemini multimodal document extraction (with retry logic)
│   ├── validate.py          # Deterministic math validation
│   ├── compare.py           # Invoice vs PO comparison via Gemini
│   ├── draft_email.py       # Dispute email drafting via Gemini
│   ├── orchestrator.py      # Direct function-chaining pipeline (non-ADK path)
│   └── adk_agent.py         # ADK Agent definition, wraps the above as tools + MCP toolset
├── mcp_server/
│   └── server.py            # FastMCP server exposing memory tools (duplicate check, save)
├── db/
│   └── storage.py           # SQLite persistence layer
├── static/
│   └── index.html           # Frontend UI
├── requirements.txt
└── .env                      
```

## Setup & Installation

### Prerequisites
- Python 3.10+ 
- A free [Gemini API key](https://aistudio.google.com/app/apikey)

### Steps

```bash
# Clone the repo
git clone https://github.com/laibaaamjad/invoiceguard-agent.git
cd invoiceguard-agent

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Add your API key
echo GEMINI_API_KEY=your_key_here > .env
```

### Run the web app

```bash
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000/app` and upload an invoice + purchase order pair.

### Run the agent directly (CLI, via ADK)

```bash
adk run agent
```

This starts an interactive session with `invoiceguard_agent` directly, useful for testing the agent's reasoning in isolation from the web UI.

## ⚠️ Important Notes

- **No API keys are committed to this repository.** `.env` is gitignored, you must supply your own Gemini API key to run this project.
- **The dispute email is a draft only.** InvoiceGuard never sends emails automatically, a human always reviews and sends manually. This is an intentional human-in-the-loop safety design, not a missing feature.
- **Free-tier Gemini API quota is limited** (commonly ~20 requests/day on `gemini-2.5-flash` at time of writing). A full invoice processing run uses 3–5 API calls. If you hit a `429` error, this is expected on the free tier, so wait for the daily reset or use a paid key.

## Deployment

This app is deployed at: **[https://invoiceguard-agent-production.up.railway.app/app](https://invoiceguard-agent-production.up.railway.app/app)**

To reproduce the deployment (on Railway):
1. Push this repo to GitHub
2. Create a new project on [Railway](https://railway.com), deploying from the GitHub repo
3. Set the custom start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add `GEMINI_API_KEY` as an environment variable in Railway's Variables tab
5. Generate a public domain under Settings → Networking
   
## License

Built for educational purposes as part of the AI Agents Vibe Coding Capstone. Free to use and adapt.
