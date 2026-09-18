from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import func, Date, cast
from sqlalchemy.orm import Session
from app.db.models import Bill, BillItem, BillStatus, PaymentMode, DailyClosing
from app.services.gst_service import quantize_money

def get_daily_sales(db: Session, target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate sales, taxes, payment mode breakdowns, and top items for a given date.
    Defaults to current UTC/local date.
    """
    if target_date is None:
        target_date = datetime.now().date()
        
    start_dt = datetime.combine(target_date, time.min)
    end_dt = datetime.combine(target_date, time.max)
    
    # Query finalized bills on target_date
    finalized_bills = db.query(Bill).filter(
        Bill.status == BillStatus.FINALIZED,
        Bill.finalized_at >= start_dt,
        Bill.finalized_at <= end_dt
    ).all()
    
    total_sales = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    
    cash_total = Decimal("0.00")
    upi_total = Decimal("0.00")
    card_total = Decimal("0.00")
    khata_total = Decimal("0.00")

    for bill in finalized_bills:
        total_sales += bill.grand_total
        total_tax += bill.total_tax
        total_cgst += bill.total_cgst
        total_sgst += bill.total_sgst
        
        mode = bill.payment_mode
        if mode == PaymentMode.CASH:
            cash_total += bill.grand_total
        elif mode == PaymentMode.UPI:
            upi_total += bill.grand_total
        elif mode == PaymentMode.CARD:
            card_total += bill.grand_total
        elif mode == PaymentMode.KHATA:
            khata_total += bill.grand_total

    # Top selling items
    top_items_query = db.query(
        BillItem.product_name,
        func.sum(BillItem.quantity).label("total_qty"),
        func.sum(BillItem.total_amount).label("total_revenue")
    ).join(Bill).filter(
        Bill.status == BillStatus.FINALIZED,
        Bill.finalized_at >= start_dt,
        Bill.finalized_at <= end_dt
    ).group_by(BillItem.product_name).order_by(func.sum(BillItem.quantity).desc()).limit(5).all()

    top_items = []
    for item_name, qty, rev in top_items_query:
        top_items.append({
            "product_name": item_name,
            "quantity_sold": float(qty),
            "revenue": float(rev)
        })

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "total_bills": len(finalized_bills),
        "total_sales": float(quantize_money(total_sales)),
        "total_tax": float(quantize_money(total_tax)),
        "total_cgst": float(quantize_money(total_cgst)),
        "total_sgst": float(quantize_money(total_sgst)),
        "payment_breakdown": {
            "cash": float(quantize_money(cash_total)),
            "upi": float(quantize_money(upi_total)),
            "card": float(quantize_money(card_total)),
            "khata": float(quantize_money(khata_total))
        },
        "top_selling_items": top_items
    }

def close_day(db: Session, target_date: Optional[date] = None, notes: Optional[str] = None) -> DailyClosing:
    """Perform official daily closing and persist metrics to daily_closings table."""
    if target_date is None:
        target_date = datetime.now().date()
        
    metrics = get_daily_sales(db, target_date)
    
    closing = db.query(DailyClosing).filter(DailyClosing.date == target_date).first()
    if not closing:
        closing = DailyClosing(
            date=target_date,
            total_sales=Decimal(str(metrics["total_sales"])),
            tax_collected=Decimal(str(metrics["total_tax"])),
            cash_total=Decimal(str(metrics["payment_breakdown"]["cash"])),
            upi_total=Decimal(str(metrics["payment_breakdown"]["upi"])),
            card_total=Decimal(str(metrics["payment_breakdown"]["card"])),
            khata_total=Decimal(str(metrics["payment_breakdown"]["khata"])),
            notes=notes or f"Day closed with {metrics['total_bills']} transactions."
        )
        db.add(closing)
    else:
        closing.total_sales = Decimal(str(metrics["total_sales"]))
        closing.tax_collected = Decimal(str(metrics["total_tax"]))
        closing.cash_total = Decimal(str(metrics["payment_breakdown"]["cash"]))
        closing.upi_total = Decimal(str(metrics["payment_breakdown"]["upi"]))
        closing.card_total = Decimal(str(metrics["payment_breakdown"]["card"]))
        closing.khata_total = Decimal(str(metrics["payment_breakdown"]["khata"]))
        closing.notes = notes or f"Day re-closed with {metrics['total_bills']} transactions."

    db.commit()
    db.refresh(closing)
    return closing
