import enum
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Numeric, Boolean, DateTime, Date,
    ForeignKey, Text, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.db.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class BillStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    CANCELLED = "CANCELLED"

class PaymentMode(str, enum.Enum):
    CASH = "CASH"
    UPI = "UPI"
    CARD = "CARD"
    KHATA = "KHATA"

class KhataType(str, enum.Enum):
    CREDIT = "CREDIT"
    PAYMENT = "PAYMENT"

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), index=True, nullable=False)
    category = Column(String(50), nullable=False, default="General")
    unit = Column(String(20), nullable=False, default="piece")  # kg, g, L, ml, packet, dozen, piece
    is_loose = Column(Boolean, default=False, nullable=False)
    
    cost_price = Column(Numeric(10, 2), nullable=False)
    mrp = Column(Numeric(10, 2), nullable=False)  # Selling price / MRP
    quantity = Column(Numeric(10, 3), nullable=False, default=Decimal("0.000"))
    reorder_level = Column(Numeric(10, 3), nullable=False, default=Decimal("5.000"))
    
    hsn_code = Column(String(20), nullable=False, default="1905")
    gst_rate = Column(Numeric(5, 2), nullable=False, default=Decimal("5.00"))  # 0, 5, 12, 18
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    bill_items = relationship("BillItem", back_populates="product")

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    phone = Column(String(20), nullable=True, index=True)
    current_balance = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))  # Positive means owes money
    created_at = Column(DateTime, default=utc_now, nullable=False)

    bills = relationship("Bill", back_populates="customer")
    khata_transactions = relationship("KhataTransaction", back_populates="customer", order_by="KhataTransaction.created_at.desc()")

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    bill_number = Column(String(50), unique=True, index=True, nullable=False)
    status = Column(SQLEnum(BillStatus), default=BillStatus.DRAFT, nullable=False, index=True)
    
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(100), nullable=True)
    
    payment_mode = Column(SQLEnum(PaymentMode), nullable=True, default=PaymentMode.UPI)
    payment_ref = Column(String(100), nullable=True)
    
    subtotal = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_cgst = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_sgst = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_tax = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    grand_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)
    pdf_path = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    finalized_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="bills")
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="bill", cascade="all, delete-orphan")

class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    product_name = Column(String(150), nullable=False)
    unit = Column(String(20), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)  # Selling price at bill creation
    cost_price = Column(Numeric(10, 2), nullable=False)  # Cost price for margin analysis
    
    hsn_code = Column(String(20), nullable=False)
    gst_rate = Column(Numeric(5, 2), nullable=False)
    
    taxable_amount = Column(Numeric(10, 2), nullable=False)
    cgst_amount = Column(Numeric(10, 2), nullable=False)
    sgst_amount = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)

    bill = relationship("Bill", back_populates="items")
    product = relationship("Product", back_populates="bill_items")

class KhataTransaction(Base):
    __tablename__ = "khata_transactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    type = Column(SQLEnum(KhataType), nullable=False)  # CREDIT (increases balance), PAYMENT (reduces balance)
    amount = Column(Numeric(10, 2), nullable=False)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    customer = relationship("Customer", back_populates="khata_transactions")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    mode = Column(SQLEnum(PaymentMode), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    reference = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    bill = relationship("Bill", back_populates="payments")

class OwnerPreference(Base):
    __tablename__ = "owner_preferences"

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

class DailyClosing(Base):
    __tablename__ = "daily_closings"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    total_sales = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    tax_collected = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    cash_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    upi_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    card_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    khata_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    closed_at = Column(DateTime, default=utc_now, nullable=False)
    notes = Column(Text, nullable=True)
