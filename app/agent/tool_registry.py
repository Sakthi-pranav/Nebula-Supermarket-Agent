import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.services import (
    inventory_service,
    billing_service,
    khata_service,
    reporting_service,
    preference_service
)
from app.documents import invoice_pdf, sales_pptx

class ToolRegistry:
    """Registry for converting application service functions into LLM Function Calling tools."""
    
    def __init__(self):
        self.tools_map: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []
        self._register_all_tools()

    def register(self, name: str, description: str, parameters: Dict[str, Any], func: Callable):
        """Register a function tool with OpenAI/LLM schema format."""
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }
        self.schemas.append(schema)
        self.tools_map[name] = func

    def _register_all_tools(self):
        # ------------------- INVENTORY TOOLS -------------------
        self.register(
            name="search_products",
            description="Search inventory for products by name, SKU, or category.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term (e.g. 'Maggi', 'Atta', 'Salt')"}
                },
                "required": ["query"]
            },
            func=self._tool_search_products
        )

        self.register(
            name="add_product",
            description="Add a new product to store inventory.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Full product name"},
                    "category": {"type": "string", "description": "Category e.g. Staples, Dairy, Snacks"},
                    "unit": {"type": "string", "description": "Unit: kg, g, litre, ml, packet, dozen, piece"},
                    "cost_price": {"type": "number", "description": "Cost price in INR (₹)"},
                    "mrp": {"type": "number", "description": "Selling price / MRP in INR (₹)"},
                    "quantity": {"type": "number", "description": "Initial stock quantity", "default": 0.0},
                    "reorder_level": {"type": "number", "description": "Reorder alert threshold", "default": 5.0},
                    "hsn_code": {"type": "string", "description": "HSN Code", "default": "1905"},
                    "gst_rate": {"type": "number", "description": "GST rate percentage e.g. 0, 5, 12, 18", "default": 5.0},
                    "is_loose": {"type": "boolean", "description": "True if sold loose by weight/volume", "default": False},
                    "sku": {"type": "string", "description": "Optional unique SKU code"}
                },
                "required": ["name", "category", "unit", "cost_price", "mrp"]
            },
            func=self._tool_add_product
        )

        self.register(
            name="receive_stock",
            description="Record incoming stock for an existing product (increases stock quantity).",
            parameters={
                "type": "object",
                "properties": {
                    "product_identifier": {"type": "string", "description": "Product name or SKU or ID"},
                    "quantity_added": {"type": "number", "description": "Quantity received"},
                    "new_cost_price": {"type": "number", "description": "Updated cost price (optional)"},
                    "new_mrp": {"type": "number", "description": "Updated MRP/selling price (optional)"}
                },
                "required": ["product_identifier", "quantity_added"]
            },
            func=self._tool_receive_stock
        )

        self.register(
            name="get_stock",
            description="Get current stock levels for a specific product or all products.",
            parameters={
                "type": "object",
                "properties": {
                    "product_identifier": {"type": "string", "description": "Product name, SKU or ID (optional)"}
                },
                "required": []
            },
            func=self._tool_get_stock
        )

        self.register(
            name="get_low_stock",
            description="List all products that are at or below their reorder level.",
            parameters={"type": "object", "properties": {}},
            func=self._tool_get_low_stock
        )

        # ------------------- BILLING TOOLS -------------------
        self.register(
            name="get_draft_bill",
            description="View contents and totals of the current active draft bill.",
            parameters={
                "type": "object",
                "properties": {
                    "bill_id": {"type": "integer", "description": "Optional specific bill ID"}
                }
            },
            func=self._tool_get_draft_bill
        )

        self.register(
            name="add_bill_item",
            description="Add an item or add quantity to an item in the current draft bill. (Does NOT decrement stock yet).",
            parameters={
                "type": "object",
                "properties": {
                    "product_identifier": {"type": "string", "description": "Product name, SKU or ID"},
                    "quantity": {"type": "number", "description": "Quantity to add"},
                    "bill_id": {"type": "integer", "description": "Optional draft bill ID"}
                },
                "required": ["product_identifier", "quantity"]
            },
            func=self._tool_add_bill_item
        )

        self.register(
            name="update_bill_item",
            description="Change the quantity of an item in the current draft bill.",
            parameters={
                "type": "object",
                "properties": {
                    "product_identifier": {"type": "string", "description": "Product name, SKU or ID"},
                    "new_quantity": {"type": "number", "description": "Exact new quantity to set"},
                    "bill_id": {"type": "integer", "description": "Optional draft bill ID"}
                },
                "required": ["product_identifier", "new_quantity"]
            },
            func=self._tool_update_bill_item
        )

        self.register(
            name="remove_bill_item",
            description="Remove a product item completely from the current draft bill.",
            parameters={
                "type": "object",
                "properties": {
                    "product_identifier": {"type": "string", "description": "Product name, SKU or ID"},
                    "bill_id": {"type": "integer", "description": "Optional draft bill ID"}
                },
                "required": ["product_identifier"]
            },
            func=self._tool_remove_bill_item
        )

        self.register(
            name="set_bill_payment",
            description="Set payment method (CASH, UPI, CARD, KHATA) and customer for draft bill.",
            parameters={
                "type": "object",
                "properties": {
                    "payment_mode": {"type": "string", "description": "Payment mode: CASH, UPI, CARD, or KHATA"},
                    "reference": {"type": "string", "description": "Optional payment transaction ref"},
                    "customer_name": {"type": "string", "description": "Customer name (required for KHATA credit)"},
                    "bill_id": {"type": "integer", "description": "Optional draft bill ID"}
                },
                "required": ["payment_mode"]
            },
            func=self._tool_set_bill_payment
        )

        self.register(
            name="finalize_bill",
            description="Finalize draft bill: checks stock, decrements inventory atomically, records payment, and creates bill.",
            parameters={
                "type": "object",
                "properties": {
                    "bill_id": {"type": "integer", "description": "Optional draft bill ID"},
                    "idempotency_key": {"type": "string", "description": "Optional idempotency key"}
                }
            },
            func=self._tool_finalize_bill
        )

        # ------------------- KHATA TOOLS -------------------
        self.register(
            name="add_khata_credit",
            description="Add credit debt to a customer's Khata ledger (e.g. 'Put ₹500 on Ramesh credit').",
            parameters={
                "type": "object",
                "properties": {
                    "customer_name_or_id": {"type": "string", "description": "Customer name or phone/ID"},
                    "amount": {"type": "number", "description": "Credit amount in INR (₹)"},
                    "notes": {"type": "string", "description": "Optional notes"}
                },
                "required": ["customer_name_or_id", "amount"]
            },
            func=self._tool_add_khata_credit
        )

        self.register(
            name="record_khata_payment",
            description="Record a debt repayment from a customer (e.g. 'Ramesh paid ₹300').",
            parameters={
                "type": "object",
                "properties": {
                    "customer_name_or_id": {"type": "string", "description": "Customer name or phone/ID"},
                    "amount": {"type": "number", "description": "Repayment amount in INR (₹)"},
                    "notes": {"type": "string", "description": "Optional notes"}
                },
                "required": ["customer_name_or_id", "amount"]
            },
            func=self._tool_record_khata_payment
        )

        self.register(
            name="get_customer_balance",
            description="Get current outstanding Khata debt balance for a customer.",
            parameters={
                "type": "object",
                "properties": {
                    "customer_name_or_id": {"type": "string", "description": "Customer name or phone/ID"}
                },
                "required": ["customer_name_or_id"]
            },
            func=self._tool_get_customer_balance
        )

        # ------------------- REPORTING & DOCUMENTS -------------------
        self.register(
            name="get_daily_sales",
            description="Query sales total, taxes, payment mode breakdown, and top items for a day.",
            parameters={
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "description": "YYYY-MM-DD date string (defaults to today)"}
                }
            },
            func=self._tool_get_daily_sales
        )

        self.register(
            name="close_day",
            description="Close out daily sales and persist closing summary.",
            parameters={
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "description": "YYYY-MM-DD date string"},
                    "notes": {"type": "string", "description": "Optional closing notes"}
                }
            },
            func=self._tool_close_day
        )

        self.register(
            name="generate_invoice_pdf",
            description="Generate a downloadable GST-correct PDF invoice for a bill.",
            parameters={
                "type": "object",
                "properties": {
                    "bill_id": {"type": "integer", "description": "Optional bill ID (defaults to latest finalized bill)"}
                }
            },
            func=self._tool_generate_invoice_pdf
        )

        self.register(
            name="generate_sales_analysis_pptx",
            description="Generate a weekly PowerPoint (.pptx) sales analysis deck with charts.",
            parameters={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD start date (default 7 days ago)"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD end date (default today)"}
                }
            },
            func=self._tool_generate_sales_analysis_pptx
        )

        # ------------------- PREFERENCE TOOLS -------------------
        self.register(
            name="get_preference",
            description="Retrieve persistent owner preference setting.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key e.g. default_payment_mode"}
                },
                "required": ["key"]
            },
            func=self._tool_get_preference
        )

        self.register(
            name="set_preference",
            description="Set persistent owner preference (survives app restart & sessions).",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Preference key e.g. default_payment_mode"},
                    "value": {"type": "string", "description": "Preference value e.g. UPI, CASH"}
                },
                "required": ["key", "value"]
            },
            func=self._tool_set_preference
        )

    # ------------------- TOOL IMPLEMENTATIONS -------------------

    def execute_tool(self, name: str, arguments: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Execute a registered tool with exception handling."""
        if name not in self.tools_map:
            return {"status": "error", "message": f"Unknown tool '{name}'."}
        try:
            return self.tools_map[name](db, **arguments)
        except inventory_service.AmbiguousProductError as e:
            return {
                "status": "ambiguous",
                "message": str(e),
                "matches": [f"{p.name} ({p.unit})" for p in e.matches]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # Inventory Handlers
    def _tool_search_products(self, db: Session, query: str) -> Dict[str, Any]:
        prods = inventory_service.search_products(db, query)
        return {
            "status": "success",
            "count": len(prods),
            "products": [
                {
                    "id": p.id,
                    "sku": p.sku,
                    "name": p.name,
                    "unit": p.unit,
                    "mrp": float(p.mrp),
                    "quantity": float(p.quantity),
                    "gst_rate": float(p.gst_rate)
                } for p in prods
            ]
        }

    def _tool_add_product(self, db: Session, **kwargs) -> Dict[str, Any]:
        prod = inventory_service.add_product(db, **kwargs)
        return {
            "status": "success",
            "message": f"Successfully created product '{prod.name}' with SKU '{prod.sku}'.",
            "product": {
                "id": prod.id,
                "sku": prod.sku,
                "name": prod.name,
                "mrp": float(prod.mrp),
                "gst_rate": float(prod.gst_rate),
                "quantity": float(prod.quantity)
            }
        }

    def _tool_receive_stock(self, db: Session, product_identifier: str, quantity_added: float, new_cost_price: float = None, new_mrp: float = None) -> Dict[str, Any]:
        prod = inventory_service.receive_stock(
            db, product_identifier, Decimal(str(quantity_added)),
            Decimal(str(new_cost_price)) if new_cost_price else None,
            Decimal(str(new_mrp)) if new_mrp else None
        )
        return {
            "status": "success",
            "message": f"Received {quantity_added} {prod.unit} of '{prod.name}'. New stock level: {float(prod.quantity)} {prod.unit}.",
            "product_name": prod.name,
            "new_quantity": float(prod.quantity)
        }

    def _tool_get_stock(self, db: Session, product_identifier: str = None) -> Dict[str, Any]:
        stock_list = inventory_service.get_stock(db, product_identifier)
        return {"status": "success", "stock": stock_list}

    def _tool_get_low_stock(self, db: Session) -> Dict[str, Any]:
        low_list = inventory_service.get_low_stock(db)
        return {"status": "success", "count": len(low_list), "low_stock_items": low_list}

    # Billing Handlers
    def _tool_get_draft_bill(self, db: Session, bill_id: int = None) -> Dict[str, Any]:
        bill = billing_service.get_or_create_draft_bill(db, bill_id)
        return {"status": "success", "bill": billing_service.format_bill_summary(bill)}

    def _tool_add_bill_item(self, db: Session, product_identifier: str, quantity: float, bill_id: int = None) -> Dict[str, Any]:
        bill = billing_service.add_item_to_bill(db, bill_id, product_identifier, Decimal(str(quantity)))
        return {"status": "success", "message": f"Added {quantity} of '{product_identifier}' to draft bill.", "bill": billing_service.format_bill_summary(bill)}

    def _tool_update_bill_item(self, db: Session, product_identifier: str, new_quantity: float, bill_id: int = None) -> Dict[str, Any]:
        bill = billing_service.update_bill_item_quantity(db, bill_id, product_identifier, Decimal(str(new_quantity)))
        return {"status": "success", "message": f"Updated '{product_identifier}' quantity to {new_quantity}.", "bill": billing_service.format_bill_summary(bill)}

    def _tool_remove_bill_item(self, db: Session, product_identifier: str, bill_id: int = None) -> Dict[str, Any]:
        bill = billing_service.remove_item_from_bill(db, bill_id, product_identifier)
        return {"status": "success", "message": f"Removed '{product_identifier}' from draft bill.", "bill": billing_service.format_bill_summary(bill)}

    def _tool_set_bill_payment(self, db: Session, payment_mode: str, reference: str = None, customer_name: str = None, bill_id: int = None) -> Dict[str, Any]:
        bill = billing_service.set_bill_payment_mode(db, bill_id, payment_mode, reference, customer_name)
        return {"status": "success", "message": f"Set payment mode to {bill.payment_mode.value}.", "bill": billing_service.format_bill_summary(bill)}

    def _tool_finalize_bill(self, db: Session, bill_id: int = None, idempotency_key: str = None) -> Dict[str, Any]:
        bill = billing_service.finalize_bill(db, bill_id, idempotency_key)
        # Generate PDF invoice automatically
        pdf_path = invoice_pdf.generate_pdf_invoice(bill)
        summary = billing_service.format_bill_summary(bill)
        summary["pdf_file_path"] = str(pdf_path)
        return {"status": "success", "message": f"Bill #{bill.bill_number} finalized successfully.", "bill": summary}

    # Khata Handlers
    def _tool_add_khata_credit(self, db: Session, customer_name_or_id: str, amount: float, notes: str = None) -> Dict[str, Any]:
        txn = khata_service.add_credit(db, customer_name_or_id, Decimal(str(amount)), notes=notes)
        bal = khata_service.get_customer_balance(db, customer_name_or_id)
        return {
            "status": "success",
            "message": f"Added ₹{amount:.2f} credit to {bal['name']}'s account.",
            "customer": bal
        }

    def _tool_record_khata_payment(self, db: Session, customer_name_or_id: str, amount: float, notes: str = None) -> Dict[str, Any]:
        txn = khata_service.record_payment(db, customer_name_or_id, Decimal(str(amount)), notes=notes)
        bal = khata_service.get_customer_balance(db, customer_name_or_id)
        return {
            "status": "success",
            "message": f"Recorded ₹{amount:.2f} payment from {bal['name']}.",
            "customer": bal
        }

    def _tool_get_customer_balance(self, db: Session, customer_name_or_id: str) -> Dict[str, Any]:
        bal = khata_service.get_customer_balance(db, customer_name_or_id)
        return {"status": "success", "customer": bal}

    # Reporting Handlers
    def _tool_get_daily_sales(self, db: Session, target_date: str = None) -> Dict[str, Any]:
        t_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else None
        res = reporting_service.get_daily_sales(db, t_date)
        return {"status": "success", "daily_sales": res}

    def _tool_close_day(self, db: Session, target_date: str = None, notes: str = None) -> Dict[str, Any]:
        t_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else None
        closing = reporting_service.close_day(db, t_date, notes)
        return {
            "status": "success",
            "message": f"Closed sales for {closing.date}. Total Sales: ₹{float(closing.total_sales):.2f}, Tax: ₹{float(closing.tax_collected):.2f}.",
            "date": str(closing.date),
            "total_sales": float(closing.total_sales)
        }

    def _tool_generate_invoice_pdf(self, db: Session, bill_id: int = None) -> Dict[str, Any]:
        if bill_id:
            bill = db.query(billing_service.Bill).filter(billing_service.Bill.id == bill_id).first()
        else:
            bill = db.query(billing_service.Bill).order_by(billing_service.Bill.created_at.desc()).first()
            
        if not bill:
            return {"status": "error", "message": "No bill found to generate PDF."}

        pdf_path = invoice_pdf.generate_pdf_invoice(bill)
        return {
            "status": "success",
            "message": f"Generated PDF invoice for Bill #{bill.bill_number}.",
            "bill_number": bill.bill_number,
            "pdf_file_path": str(pdf_path)
        }

    def _tool_generate_sales_analysis_pptx(self, db: Session, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else datetime.utcnow().date()
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (e_date - timedelta(days=7))
        
        pptx_path = sales_pptx.generate_sales_pptx(db, s_date, e_date)
        return {
            "status": "success",
            "message": f"Generated Weekly Sales Analysis Presentation deck for period {s_date} to {e_date}.",
            "pptx_file_path": str(pptx_path)
        }

    # Preferences Handlers
    def _tool_get_preference(self, db: Session, key: str) -> Dict[str, Any]:
        val = preference_service.get_preference(db, key)
        return {"status": "success", "key": key, "value": val}

    def _tool_set_preference(self, db: Session, key: str, value: str) -> Dict[str, Any]:
        pref = preference_service.set_preference(db, key, value)
        return {"status": "success", "message": f"Preference '{key}' set to '{value}'.", "key": pref.key, "value": pref.value}

tool_registry = ToolRegistry()
