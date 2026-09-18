from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.models import Customer, KhataTransaction, KhataType, PaymentMode
from app.services.gst_service import quantize_money

class KhataError(Exception):
    """Base exception for Khata operations."""
    pass

class CustomerNotFoundError(KhataError):
    """Raised when customer is not found."""
    pass

def find_customer(db: Session, identifier: str | int) -> Optional[Customer]:
    """Find a customer by ID, exact name, or phone number."""
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        customer = db.query(Customer).filter(Customer.id == int(identifier)).first()
        if customer:
            return customer

    identifier_str = str(identifier).strip()
    
    # 1. Exact phone match
    customer = db.query(Customer).filter(Customer.phone == identifier_str).first()
    if customer:
        return customer
        
    # 2. Exact name match
    customer = db.query(Customer).filter(Customer.name.ilike(identifier_str)).first()
    if customer:
        return customer
        
    # 3. Fuzzy name match
    matches = db.query(Customer).filter(Customer.name.ilike(f"%{identifier_str}%")).all()
    if len(matches) == 1:
        return matches[0]
        
    return None

def find_or_create_customer(db: Session, name: str, phone: Optional[str] = None) -> Customer:
    """Find customer by name or create a new customer if not found."""
    name_clean = name.strip()
    customer = find_customer(db, name_clean)
    if not customer:
        customer = Customer(name=name_clean, phone=phone.strip() if phone else None, current_balance=Decimal("0.00"))
        db.add(customer)
        db.commit()
        db.refresh(customer)
    return customer

def add_credit(
    db: Session,
    customer_identifier: str | int,
    amount: Decimal,
    bill_id: Optional[int] = None,
    notes: Optional[str] = None
) -> KhataTransaction:
    """
    Add credit debt to a customer's Khata account.
    Increases current_balance (debt owed to store).
    """
    amount = quantize_money(Decimal(str(amount)))
    if amount <= Decimal("0"):
        raise KhataError("Credit amount must be greater than 0.")
        
    customer = find_customer(db, customer_identifier)
    if not customer:
        if isinstance(customer_identifier, str):
            customer = find_or_create_customer(db, customer_identifier)
        else:
            raise CustomerNotFoundError(f"Customer '{customer_identifier}' not found.")
            
    customer.current_balance += amount
    
    txn = KhataTransaction(
        customer_id=customer.id,
        type=KhataType.CREDIT,
        amount=amount,
        bill_id=bill_id,
        notes=notes or "Khata credit purchase"
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

def record_payment(
    db: Session,
    customer_identifier: str | int,
    amount: Decimal,
    notes: Optional[str] = None
) -> KhataTransaction:
    """
    Record a debt repayment from a customer.
    Decreases current_balance. Rejects invalid payments.
    """
    amount = quantize_money(Decimal(str(amount)))
    if amount <= Decimal("0"):
        raise KhataError("Payment amount must be greater than 0.")
        
    customer = find_customer(db, customer_identifier)
    if not customer:
        raise CustomerNotFoundError(f"Customer '{customer_identifier}' not found.")
        
    if customer.current_balance <= Decimal("0"):
        raise KhataError(f"Customer '{customer.name}' has zero outstanding balance (₹0.00). No pending debt to pay.")

    # Decrement debt balance
    customer.current_balance -= amount
    
    txn = KhataTransaction(
        customer_id=customer.id,
        type=KhataType.PAYMENT,
        amount=amount,
        notes=notes or "Khata debt settlement payment"
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

def get_customer_balance(db: Session, customer_identifier: str | int) -> dict:
    """Query current debt balance and details for a customer."""
    customer = find_customer(db, customer_identifier)
    if not customer:
        raise CustomerNotFoundError(f"Customer '{customer_identifier}' not found.")
        
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "current_balance": float(customer.current_balance),
        "status": "Owes store money" if customer.current_balance > Decimal("0") else "Clear / Advance"
    }

def get_customer_history(db: Session, customer_identifier: str | int) -> dict:
    """Retrieve full transaction history for a customer."""
    customer = find_customer(db, customer_identifier)
    if not customer:
        raise CustomerNotFoundError(f"Customer '{customer_identifier}' not found.")
        
    txns = db.query(KhataTransaction).filter(
        KhataTransaction.customer_id == customer.id
    ).order_by(KhataTransaction.created_at.desc()).all()
    
    history = []
    for t in txns:
        history.append({
            "id": t.id,
            "type": t.type.value,
            "amount": float(t.amount),
            "bill_id": t.bill_id,
            "notes": t.notes,
            "date": t.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "current_balance": float(customer.current_balance),
        "transactions": history
    }
