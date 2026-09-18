# 🎬 Supermarket Ops Agent — 4–5 Minute Demo Script & Interview Guide

This guide provides a step-by-step demonstration walkthrough for the **Nebula KnowLab Supermarket Ops Agent**. Follow this script during your interview presentation or screen recording.

---

## ⏱️ Video / Live Demo Schedule (Total Time: ~4.5 Minutes)

| Segment | Topic / Scenario | Time | Key Takeaway |
| :--- | :--- | :---: | :--- |
| **00:00 - 00:30** | Introduction & Agent Architecture | 30s | Agent-first tool loop, GST engine, SQLite transaction locks |
| **00:30 - 01:00** | Scenario 1: Receive Stock & Stock Query | 30s | Stock receiving updates cost/MRP & increases quantity |
| **01:00 - 02:00** | Scenario 2: Multi-Turn Draft Bill & Editing | 60s | Multi-turn bill context; stock is NOT touched during draft edits |
| **02:00 - 02:30** | Scenario 3: Oversell Rejection Guardrail | 30s | Business-layer stock rejection; non-negative stock invariant |
| **02:30 - 03:00** | Scenario 4: Customer Khata Ledger | 30s | Credit addition, debt repayment, and balance checking |
| **03:00 - 03:30** | Scenario 5: Document Generation (PDF & PPTX) | 30s | Real ReportLab PDF invoice and python-pptx sales deck generation |
| **03:30 - 04:15** | Scenario 6: Persistent Owner Preferences | 45s | Preference saved & surviving session resets |
| **04:15 - 04:30** | Wrap-Up & Test Verification | 15s | 24/24 passing pytest suite & clean architecture |

---

## 🗣️ Step-by-Step Script

### 🎙️ Segment 1: Introduction (00:00 - 00:30)
> **Speaker**: *"Hi! Today I am presenting the Supermarket Ops Agent, built for Indian Kirana store operations over Telegram. Unlike basic chatbots or regex command routers, this system uses an autonomous ReAct control loop. All business rules — like GST calculations, stock validation, and debt ledger math — are strictly enforced in deterministic Python services rather than LLM prompt text."*

---

### 🎙️ Segment 2: Receive Stock (00:30 - 01:00)
- **Prompt**:
  ```text
  50 packets of Maggi came in, cost ₹12, MRP ₹14
  ```
- **Expected Agent Action**: Calls tool `receive_stock(product_identifier="Maggi 70g", quantity_added=50, new_cost_price=12, new_mrp=14)`.
- **Agent Response**: *"Successfully received 50 packets of Maggi 70g. Updated stock level is now 150 packets."*

---

### 🎙️ Segment 3: Multi-Turn Bill & Editing (01:00 - 02:00)
- **Step 3A (Create Bill)**:
  ```text
  Make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi
  ```
  - **Agent Action**: Calls `add_bill_item` for sugar, atta, and maggi. Shows draft bill summary with subtotal and GST split.
  - **Highlight**: *"Notice that creating a draft bill does NOT decrement stock."*

- **Step 3B (Add Item)**:
  ```text
  Add 1 Amul butter
  ```
  - **Agent Action**: Calls `add_bill_item` for Amul Butter. Updates draft bill.

- **Step 3C (Edit Item & Remove Item)**:
  ```text
  Remove the butter and make Maggi 6
  ```
  - **Agent Action**: Calls `remove_bill_item` and `update_bill_item`. Recalculates CGST & SGST.

- **Step 3D (Set Payment & Finalize)**:
  ```text
  UPI
  ```
  Followed by:
  ```text
  Finalize
  ```
  - **Agent Action**: Calls `set_bill_payment(payment_mode="UPI")` then `finalize_bill`.
  - **Highlight**: *"At finalization, the system checks inventory, decrements stock atomically, records payment, and automatically generates a GST-compliant PDF invoice."*

---

### 🎙️ Segment 4: Oversell Protection Guardrail (02:00 - 02:30)
- **Prompt**:
  ```text
  Make a bill for 50 Aashirvaad Atta
  ```
  Followed by:
  ```text
  Finalize
  ```
- **Expected Agent Action**: `finalize_bill` attempts atomic stock check. Stock available is 29 kg, requested is 50 kg. Business layer raises `InsufficientStockError`.
- **Agent Response**: *"⚠️ Cannot finalize bill: Oversell rejected for 'Aashirvaad Atta 5kg'. Requested quantity is 50 kg, but available stock is 29 kg."*
- **Highlight**: *"Stock was never allowed to become negative."*

---

### 🎙️ Segment 5: Customer Khata Ledger (02:30 - 03:00)
- **Prompt 1**:
  ```text
  Put ₹500 on Ramesh's credit
  ```
  - **Action**: Calls `add_khata_credit`. Customer balance becomes ₹500.

- **Prompt 2**:
  ```text
  Ramesh paid ₹300
  ```
  - **Action**: Calls `record_khata_payment`. Debt balance decreases.

- **Prompt 3**:
  ```text
  What's Ramesh's balance?
  ```
  - **Agent Response**: *"Ramesh Kumar's current balance is ₹200.00 (Owes store money)."*

---

### 开启 Segment 6: PDF & PPTX Generation (03:00 - 03:30)
- **Prompt 1**:
  ```text
  Send me that bill as a PDF
  ```
  - **Action**: Calls `generate_invoice_pdf`. Telegram bot sends `Invoice_INV-20260918-XXXX.pdf`.

- **Prompt 2**:
  ```text
  Make this week's sales analysis deck
  ```
  - **Action**: Calls `generate_sales_analysis_pptx`. Renders Matplotlib charts and uploads `Sales_Analysis_20260911_20260918.pptx`.

---

### 🎙️ Segment 7: Persistent Owner Preferences & New Session (03:30 - 04:15)
- **Prompt 1 (Set Preference)**:
  ```text
  Always assume UPI unless I say cash.
  ```
  - **Action**: Calls `set_preference(key="default_payment_mode", value="UPI")`.

- **Prompt 2 (Simulate New Session)**:
  Run `/reset` command in Telegram (or restart local CLI session).
  ```text
  Make a bill for 2 Maggi.
  ```
  - **Agent Response**: Uses stored `UPI` preference from SQLite `owner_preferences` table without asking user.

---

### 🎙️ Segment 8: Conclusion & Testing (04:15 - 04:30)
> **Speaker**: *"All 24 automated unit and scenario integration tests pass in under 5 seconds using pytest. The repository is completely clean, container-ready with Docker, and contains no hardcoded secrets."*

---

## 🛠️ Commands for Quick Demonstration

```bash
# Option A: Run interactive terminal demo
python app/main.py --cli

# Option B: Launch real Telegram Bot
python app/main.py --bot

# Option C: Run full automated test suite
pytest -v
```
