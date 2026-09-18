import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.models import Bill, BillItem, BillStatus, PaymentMode, Payment, Product
from app.services import gst_service, inventory_service, khata_service, preference_service

class BillingError(Exception):
    """Base exception for billing operations."""
    pass

def generate_bill_number() -> str:
    """Generate a readable bill number like INV-20260918-A1B2."""
    today_str = datetime.now().strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:4].upper()
    return f"INV-{today_str}-{short_uuid}"

def get_or_create_draft_bill(db: Session, bill_id: Optional[int] = None, customer_id: Optional[int] = None) -> Bill:
    """
    Get active draft bill by ID or find the latest DRAFT bill for session/customer.
    If none exists, create a new DRAFT bill.
    """
    if bill_id:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillingError(f"Bill ID {bill_id} not found.")
        if bill.status != BillStatus.DRAFT:
            raise BillingError(f"Bill {bill.bill_number} is already {bill.status.value} and cannot be modified.")
        return bill

    # Find open DRAFT bill if customer specified
    if customer_id:
        bill = db.query(Bill).filter(
            Bill.customer_id == customer_id,
            Bill.status == BillStatus.DRAFT
        ).order_by(Bill.created_at.desc()).first()
        if bill:
            return bill

    # Find any latest open DRAFT bill in general
    bill = db.query(Bill).filter(
        Bill.status == BillStatus.DRAFT
    ).order_by(Bill.created_at.desc()).first()
    
    if not bill:
        # Get default payment mode from preference if set
        def_payment_str = preference_service.get_preference(db, "default_payment_mode", "UPI")
        try:
            def_payment = PaymentMode[def_payment_str.upper()]
        except KeyError:
            def_payment = PaymentMode.UPI

        bill = Bill(
            bill_number=generate_bill_number(),
            status=BillStatus.DRAFT,
            customer_id=customer_id,
            payment_mode=def_payment,
            subtotal=Decimal("0.00"),
            total_cgst=Decimal("0.00"),
            total_sgst=Decimal("0.00"),
            total_tax=Decimal("0.00"),
            grand_total=Decimal("0.00")
        )
        db.add(bill)
        db.commit()
        db.refresh(bill)

    return bill

def recalculate_bill(db: Session, bill: Bill) -> Bill:
    """Recalculate subtotal, GST split, and grand total for a draft bill."""
    items = bill.items
    items_gst_data = []
    
    for item in items:
        gst_res = gst_service.calculate_item_gst(item.unit_price, item.quantity, item.gst_rate)
        item.taxable_amount = gst_res["taxable_amount"]
        item.cgst_amount = gst_res["cgst_amount"]
        item.sgst_amount = gst_res["sgst_amount"]
        item.total_amount = gst_res["total_amount"]
        items_gst_data.append(gst_res)
        
    totals = gst_service.calculate_bill_totals(items_gst_data)
    bill.subtotal = totals["subtotal"]
    bill.total_cgst = totals["total_cgst"]
    bill.total_sgst = totals["total_sgst"]
    bill.total_tax = totals["total_tax"]
    bill.grand_total = totals["grand_total"]
    
    db.commit()
    db.refresh(bill)
    return bill

def add_item_to_bill(
    db: Session,
    bill_id: Optional[int],
    product_identifier: str | int,
    quantity: Decimal
) -> Bill:
    """
    Add or increase quantity of a product in a draft bill.
    Note: Does NOT check/decrement inventory here (inventory check happens at finalization).
    """
    bill = get_or_create_draft_bill(db, bill_id)
    product = inventory_service.find_single_product(db, product_identifier)
    
    qty = Decimal(str(quantity))
    if qty <= Decimal("0"):
        raise BillingError("Item quantity must be greater than 0.")
        
    # Check if product is already in bill
    existing_item = None
    for item in bill.items:
        if item.product_id == product.id:
            existing_item = item
            break

    if existing_item:
        existing_item.quantity += qty
    else:
        gst_res = gst_service.calculate_item_gst(product.mrp, qty, product.gst_rate)
        new_item = BillItem(
            bill_id=bill.id,
            product_id=product.id,
            product_name=product.name,
            unit=product.unit,
            quantity=qty,
            unit_price=product.mrp,
            cost_price=product.cost_price,
            hsn_code=product.hsn_code,
            gst_rate=product.gst_rate,
            taxable_amount=gst_res["taxable_amount"],
            cgst_amount=gst_res["cgst_amount"],
            sgst_amount=gst_res["sgst_amount"],
            total_amount=gst_res["total_amount"]
        )
        db.add(new_item)

    return recalculate_bill(db, bill)

def update_bill_item_quantity(
    db: Session,
    bill_id: Optional[int],
    product_identifier: str | int,
    new_quantity: Decimal
) -> Bill:
    """Set exact new quantity for a product in draft bill."""
    bill = get_or_create_draft_bill(db, bill_id)
    product = inventory_service.find_single_product(db, product_identifier)
    
    qty = Decimal(str(new_quantity))
    if qty <= Decimal("0"):
        return remove_item_from_bill(db, bill.id, product.id)
        
    target_item = None
    for item in bill.items:
        if item.product_id == product.id:
            target_item = item
            break

    if not target_item:
        raise BillingError(f"Product '{product.name}' is not in current draft bill.")

    target_item.quantity = qty
    return recalculate_bill(db, bill)

def remove_item_from_bill(
    db: Session,
    bill_id: Optional[int],
    product_identifier: str | int
) -> Bill:
    """Remove a product completely from a draft bill."""
    bill = get_or_create_draft_bill(db, bill_id)
    product = inventory_service.find_single_product(db, product_identifier)
    
    target_item = None
    for item in bill.items:
        if item.product_id == product.id:
            target_item = item
            break

    if not target_item:
        raise BillingError(f"Product '{product.name}' is not in current draft bill.")

    db.delete(target_item)
    return recalculate_bill(db, bill)

def set_bill_payment_mode(
    db: Session,
    bill_id: Optional[int],
    payment_mode_str: str,
    reference: Optional[str] = None,
    customer_name_or_id: Optional[str | int] = None
) -> Bill:
    """Set payment mode and optional customer for draft bill."""
    bill = get_or_create_draft_bill(db, bill_id)
    mode_clean = payment_mode_str.strip().upper()
    
    try:
        mode_enum = PaymentMode[mode_clean]
    except KeyError:
        raise BillingError(f"Invalid payment mode '{payment_mode_str}'. Supported modes: CASH, UPI, CARD, KHATA.")

    bill.payment_mode = mode_enum
    if reference:
        bill.payment_ref = reference.strip()

    if customer_name_or_id:
        cust = khata_service.find_or_create_customer(db, str(customer_name_or_id))
        bill.customer_id = cust.id
        bill.customer_name = cust.name

    db.commit()
    db.refresh(bill)
    return bill

def finalize_bill(
    db: Session,
    bill_id: Optional[int] = None,
    idempotency_key: Optional[str] = None
) -> Bill:
    """
    Finalize a draft bill:
    1. Idempotency check: If bill already FINALIZED, return it without re-processing.
    2. Validate items exist.
    3. Validate & decrement inventory atomically inside database transaction (rejects oversell).
    4. Transition status to FINALIZED.
    5. Record Payment transaction.
    6. If payment mode is KHATA, record credit in customer's ledger.
    """
    bill = db.query(Bill).filter(Bill.id == bill_id).first() if bill_id else None
    if not bill:
        bill = get_or_create_draft_bill(db)

    # 1. Idempotency check
    if bill.status == BillStatus.FINALIZED:
        return bill
        
    if idempotency_key:
        existing = db.query(Bill).filter(Bill.idempotency_key == idempotency_key).first()
        if existing and existing.status == BillStatus.FINALIZED:
            return existing
        bill.idempotency_key = idempotency_key

    if not bill.items:
        raise BillingError("Cannot finalize an empty bill with no items.")

    # Recalculate totals before finalization
    bill = recalculate_bill(db, bill)

    # Begin atomic finalization block
    try:
        # 3. Validate & atomic decrement stock for all items
        for item in bill.items:
            inventory_service.atomic_decrement_stock(db, item.product_id, item.quantity)
            
        # 4. Mark bill as FINALIZED
        bill.status = BillStatus.FINALIZED
        bill.finalized_at = datetime.now()

        # 5. Create Payment entry
        payment = Payment(
            bill_id=bill.id,
            mode=bill.payment_mode,
            amount=bill.grand_total,
            reference=bill.payment_ref
        )
        db.add(payment)

        # 6. Handle KHATA payment mode
        if bill.payment_mode == PaymentMode.KHATA:
            if not bill.customer_id:
                raise BillingError("Customer record is required for KHATA (credit) payment.")
            khata_service.add_credit(
                db=db,
                customer_identifier=bill.customer_id,
                amount=bill.grand_total,
                bill_id=bill.id,
                notes=f"Bill #{bill.bill_number} credit"
            )

        db.commit()
        db.refresh(bill)
        return bill
    except Exception:
        db.rollback()
        raise

def format_bill_summary(bill: Bill) -> dict:
    """Format bill details into a clean dictionary representation."""
    items_summary = []
    for item in bill.items:
        items_summary.append({
            "product_id": item.product_id,
            "product_name": item.product_name,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "unit_price": float(item.unit_price),
            "gst_rate": float(item.gst_rate),
            "cgst": float(item.cgst_amount),
            "sgst": float(item.sgst_amount),
            "total": float(item.total_amount)
        })

    return {
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "status": bill.status.value,
        "customer_name": bill.customer_name or "Walk-in Customer",
        "payment_mode": bill.payment_mode.value if bill.payment_mode else "UPI",
        "items": items_summary,
        "item_count": len(items_summary),
        "subtotal": float(bill.subtotal),
        "total_cgst": float(bill.total_cgst),
        "total_sgst": float(bill.total_sgst),
        "total_tax": float(bill.total_tax),
        "grand_total": float(bill.grand_total),
        "created_at": bill.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finalized_at": bill.finalized_at.strftime("%Y-%m-%d %H:%M:%S") if bill.finalized_at else None
    }
