# 🛒 Supermarket Ops Agent — Indian Kirana Operations via Telegram

An autonomous, AI-agent-powered Indian kirana and supermarket operations system operated entirely through natural language text messages in Telegram.

Built for the **Nebula KnowLab Engineering Hiring Task**.

---

## 🌟 Key Capabilities & Features

1. **Natural Language Kirana Operations**: Operate stock receiving, product creation, multi-turn billing, customer Khata credit management, daily sales closing, and reporting naturally over Telegram.
2. **Deterministic GST Engine**: Complete intra-state CGST & SGST splitting (0%, 5%, 12%, 18%) with half-up rounding. GST calculations are enforced in python business logic and never delegated to LLM prompts.
3. **Strict Stock Invariants & Oversell Protection**: Stock can NEVER become negative. Draft bill creation and modifications do NOT alter stock. Inventory is decremented ONLY when a bill is finalized atomically inside a database transaction.
4. **Idempotent Finalization**: Repeated bill finalization requests (e.g., from Telegram redelivery) do not duplicate bills or decrement inventory twice.
5. **Customer Khata Credit Ledger**: Natural language customer debt tracking, payment recording, and balance queries with zero-balance settlement validation.
6. **PDF Invoice Generation**: Instant downloadable tax-compliant PDF invoices built using `ReportLab`.
7. **Weekly Sales Analysis PPTX Deck**: Automated 5-slide PowerPoint deck with embedded `Matplotlib` charts (daily revenue trend, top selling items, payment method donut chart, low stock alerts).
8. **Persistent Owner Preferences**: Preferences (e.g., default payment method) stored in SQLite survive application restarts and multi-session conversations.
9. **Ambiguity Resolution**: Agent proactively asks clarifying questions when queries match multiple products instead of making dangerous assumptions.

---

## 🏗️ Architecture & Control Loop

```
Telegram User / Store Owner
          │
          ▼
   Telegram Handler (python-telegram-bot)
          │
          ▼
   SupermarketOpsAgent (ReAct Control Loop)
    ├── OBSERVE: Parse message & history
    ├── REASON: Decide action or clarify ambiguity
    ├── ACT: Call typed service tool via Function Schema
    └── RECEIVE RESULT: Evaluate tool response
          │
          ▼
    Deterministic Service Layer
    ├── InventoryService (Atomic locks & stock rules)
    ├── BillingService (Draft bills, GST, Idempotency)
    ├── KhataService (Customer credit ledger)
    ├── ReportingService (Daily sales & closings)
    └── PreferenceService (SQLite persistent key-values)
          │
          ▼
    Database Layer (SQLAlchemy ORM + SQLite WAL Mode)
          │
          ▼
    Document Generators (ReportLab PDF / python-pptx Deck)
          │
          ▼
   Telegram Response (Text message + Document Attachment)
```

### Agent Architecture Rationale (Interview Explainability)

- **Why an Agent-First Architecture instead of Hardcoded Intent Routers / Regex?**
  Kirana store owners speak fluidly in mixed English/Hindi ("50 packets Maggi came in cost 12 MRP 14", "Make bill 2kg sugar and 4 maggi, actually make maggi 6"). An LLM ReAct agent dynamically parses context, handles multi-turn state, extracts typed function arguments, and calls deterministic tools seamlessly.
- **Why thin typed tools?**
  Business rules (GST splits, inventory checks, debt math) belong in deterministic Python code, not in the LLM prompt. Tools enforce strict validation, transactional atomicity, and return structured JSON back to the agent.
- **Why SQLite with SQLAlchemy?**
  SQLite with Write-Ahead Logging (WAL) mode provides zero-infrastructure setup, single-file local persistence, robust transaction locking, and high performance suitable for Kirana POS terminals.

---

## 🛠️ Technology Stack

- **Language**: Python 3.10+
- **ORM & Database**: SQLAlchemy 2.0 + SQLite (WAL mode enabled)
- **Telegram Bot**: `python-telegram-bot` (v20+)
- **LLM Function Calling**: `openai` SDK (supports OpenAI `gpt-4o-mini`, Gemini OpenAI-compatible endpoint, Groq, Ollama, DeepSeek)
- **Data Validation**: `pydantic` v2 & `pydantic-settings`
- **PDF Generation**: `ReportLab`
- **PPTX Generation**: `python-pptx`
- **Charts & Visualization**: `Matplotlib`
- **Testing**: `pytest` & `pytest-asyncio`

---

## 🚀 Quickstart & Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/your-username/nebula-supermarket-agent.git
cd nebula-supermarket-agent
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Telegram Bot Token (from @BotFather)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# LLM Provider Configuration
LLM_PROVIDER=openai
LLM_API_KEY=your_openai_or_gemini_api_key_here
LLM_MODEL=gpt-4o-mini
```

### 3. Seed Database with Sample Data

Run the database seed script to populate realistic Indian Kirana products (Atta, Salt, Amul Butter, Oil, Maggi, Parle-G, Loose Sugar, Rice, Dal) and initial preferences:

```bash
python app/main.py --seed
```

### 4. Run Automated Tests

Verify that all 24 unit and scenario integration tests pass:

```bash
pytest -v
```

### 5. Launch Telegram Bot

```bash
python app/main.py --bot
```

---

## 🧪 Demo Scenarios Walkthrough

The system fully supports the 9 core hiring assignment scenarios:

### Scenario 1: Receive Stock
- **User**: `"50 packets of Maggi came in, cost ₹12, MRP ₹14"`
- **Agent**: Identifies product, calls `receive_stock`, updates inventory stock atomically, and reports new stock level.

### Scenario 2: Add Product
- **User**: `"New item: Amul Butter 100g, GST 12%, MRP ₹62"`
- **Agent**: Calls `add_product` to create SKU, store cost/MRP, HSN, and GST details in SQLite.

### Scenario 3: Multi-turn Bill
- **User**: `"Make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi"`
- **User**: `"Add 1 Amul butter"`
- **User**: `"Remove the butter and make Maggi 6"`
- **User**: `"UPI"`
- **User**: `"Finalize"`
- **Agent**: Modifies draft bill across turns without touching stock. On `Finalize`, calculates GST, validates stock, decrements stock atomically, and returns bill summary + PDF invoice attachment.

### Scenario 4: Oversell Protection
- **User**: `"Make a bill for 50 Aashirvaad Atta"` (when stock is 30)
- **Agent**: Rejects sale via business service exception, stock remains at 30, and explains available stock gracefully.

### Scenario 5: Khata Customer Ledger
- **User**: `"Put ₹500 on Ramesh's credit"`
- **User**: `"Ramesh paid ₹300"`
- **User**: `"What's Ramesh's balance?"` -> Expected balance: **₹200**

### Scenario 6: Daily Sales & Closing
- **User**: `"Today's sales?"` or `"Close the day"`
- **Agent**: Returns total sales, tax collected, cash/UPI/card/khata breakdown, top items, and persists closing record.

### Scenario 7: PDF Invoice
- **User**: `"Send me that bill as a PDF"`
- **Agent**: Calls `generate_invoice_pdf` and sends PDF file directly in Telegram chat.

### Scenario 8: Weekly Analysis Deck
- **User**: `"Make this week's sales analysis deck"`
- **Agent**: Calls `generate_sales_analysis_pptx`, renders Matplotlib charts, builds `.pptx` presentation, and uploads file to Telegram chat.

### Scenario 9: Persistent Preference
- **User**: `"Always assume UPI unless I say cash."`
- **Agent**: Stores preference in `owner_preferences` table. Survives app restart and new chat sessions.

---

## 🛡️ Business Rules & Security

- **No Negative Stock**: Business logic rejects any attempt to sell more than available quantity.
- **Deterministic Tax Math**: CGST & SGST calculated using `Decimal` half-up rounding.
- **Idempotent Billing**: Finalized bills cannot be re-finalized or modified.
- **Zero Secrets Committed**: `.gitignore` excludes `.env`, `*.db`, and generated `.pdf`/`.pptx` files.

---

## ⚖️ Limitations & Future Improvements

1. **Multi-Store Support**: Currently optimized for single-store kirana operations. Could be expanded to multi-tenant store chains.
2. **Barcode Scanner Integration**: Could support USB/Camera barcode scanning input via Telegram photo uploads.
3. **Real Payment Gateway Integration**: Could integrate Razorpay/PhonePe QR code generation for live UPI payments.
