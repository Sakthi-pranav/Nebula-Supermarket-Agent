import pytest
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services import (
    inventory_service,
    billing_service,
    khata_service,
    reporting_service,
    preference_service
)
from app.documents import invoice_pdf, sales_pptx

@pytest.fixture
def seeded_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed products
    inventory_service.add_product(db, "Aashirvaad Atta 5kg", "Staples", "kg", Decimal("210.00"), Decimal("245.00"), Decimal("30.000"), sku="SKU-ATTA")
    inventory_service.add_product(db, "Tata Salt 1kg", "Staples", "packet", Decimal("22.00"), Decimal("28.00"), Decimal("50.000"), sku="SKU-SALT", gst_rate=Decimal("0.00"))
    inventory_service.add_product(db, "Maggi 70g", "Instant", "packet", Decimal("11.50"), Decimal("14.00"), Decimal("100.000"), sku="SKU-MAGGI", gst_rate=Decimal("12.00"))
    inventory_service.add_product(db, "loose sugar", "Staples", "kg", Decimal("38.00"), Decimal("44.00"), Decimal("100.000"), sku="SKU-SUGAR", gst_rate=Decimal("0.00"), is_loose=True)
    
    yield db
    db.close()

def test_scenario_1_receive_stock(seeded_db):
    """Scenario 1: Receive Stock"""
    prod = inventory_service.receive_stock(
        db=seeded_db,
        product_identifier="Maggi 70g",
        quantity_added=Decimal("50"),
        new_cost_price=Decimal("12.00"),
        new_mrp=Decimal("14.00")
    )
    assert prod.quantity == Decimal("150.000")
    assert prod.cost_price == Decimal("12.00")

def test_scenario_2_add_product(seeded_db):
    """Scenario 2: Add New Product"""
    prod = inventory_service.add_product(
        db=seeded_db,
        name="Amul Butter 100g",
        category="Dairy",
        unit="packet",
        cost_price=Decimal("50.00"),
        mrp=Decimal("62.00"),
        gst_rate=Decimal("12.00")
    )
    assert prod.name == "Amul Butter 100g"
    assert prod.mrp == Decimal("62.00")
    assert prod.gst_rate == Decimal("12.00")

def test_scenario_3_multi_turn_bill(seeded_db):
    """Scenario 3: Multi-turn Bill flow"""
    # 1. "Make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi"
    bill = billing_service.add_item_to_bill(seeded_db, None, "loose sugar", Decimal("2"))
    bill = billing_service.add_item_to_bill(seeded_db, bill.id, "Aashirvaad Atta 5kg", Decimal("1"))
    bill = billing_service.add_item_to_bill(seeded_db, bill.id, "Maggi 70g", Decimal("4"))

    # 2. "Add 1 Amul butter"
    p_butter = inventory_service.add_product(seeded_db, "Amul Butter 100g", "Dairy", "packet", Decimal("50.00"), Decimal("62.00"), Decimal("20.00"))
    bill = billing_service.add_item_to_bill(seeded_db, bill.id, p_butter.id, Decimal("1"))
    assert len(bill.items) == 4

    # 3. "Remove the butter and make Maggi 6"
    bill = billing_service.remove_item_from_bill(seeded_db, bill.id, p_butter.id)
    bill = billing_service.update_bill_item_quantity(seeded_db, bill.id, "Maggi 70g", Decimal("6"))
    assert len(bill.items) == 3

    # 4. "UPI"
    bill = billing_service.set_bill_payment_mode(seeded_db, bill.id, "UPI")
    assert bill.payment_mode.value == "UPI"

    # 5. "Finalize"
    finalized = billing_service.finalize_bill(seeded_db, bill.id)
    assert finalized.status.value == "FINALIZED"
    
    # Check stock decremented correctly ONCE
    assert inventory_service.find_single_product(seeded_db, "Maggi 70g").quantity == Decimal("94.000")

def test_scenario_4_oversell(seeded_db):
    """Scenario 4: Oversell rejection"""
    # Stock of Atta is 30. Try to sell 50
    bill = billing_service.add_item_to_bill(seeded_db, None, "Aashirvaad Atta 5kg", Decimal("50"))
    with pytest.raises(inventory_service.InsufficientStockError):
        billing_service.finalize_bill(seeded_db, bill.id)
        
    # Stock must remain 30
    assert inventory_service.find_single_product(seeded_db, "Aashirvaad Atta 5kg").quantity == Decimal("30.000")

def test_scenario_5_khata(seeded_db):
    """Scenario 5: Khata Customer Ledger"""
    # 1. "Put ₹500 on Ramesh's credit"
    khata_service.add_credit(seeded_db, "Ramesh", Decimal("500.00"))
    
    # 2. "Ramesh paid ₹300"
    khata_service.record_payment(seeded_db, "Ramesh", Decimal("300.00"))

    # 3. "What's Ramesh's balance?" -> Expected balance ₹200
    res = khata_service.get_customer_balance(seeded_db, "Ramesh")
    assert res["current_balance"] == 200.0

def test_scenario_6_daily_close(seeded_db):
    """Scenario 6: Daily Sales & Close"""
    # Create a finalized bill
    bill = billing_service.add_item_to_bill(seeded_db, None, "Maggi 70g", Decimal("10"))
    billing_service.finalize_bill(seeded_db, bill.id)

    sales = reporting_service.get_daily_sales(seeded_db)
    assert sales["total_bills"] == 1
    assert sales["total_sales"] > 0
    assert "payment_breakdown" in sales

def test_scenario_7_pdf_invoice(seeded_db, tmp_path):
    """Scenario 7: PDF Invoice generation"""
    bill = billing_service.add_item_to_bill(seeded_db, None, "Maggi 70g", Decimal("5"))
    finalized = billing_service.finalize_bill(seeded_db, bill.id)

    out_pdf = tmp_path / "scenario_invoice.pdf"
    pdf_path = invoice_pdf.generate_pdf_invoice(finalized, out_pdf)
    assert pdf_path.exists()

def test_scenario_8_sales_pptx(seeded_db, tmp_path):
    """Scenario 8: Sales Analysis PPTX deck generation"""
    bill = billing_service.add_item_to_bill(seeded_db, None, "Maggi 70g", Decimal("5"))
    billing_service.finalize_bill(seeded_db, bill.id)

    out_pptx = tmp_path / "scenario_deck.pptx"
    today = date.today()
    pptx_path = sales_pptx.generate_sales_pptx(seeded_db, today - timedelta(days=7), today, out_pptx)
    assert pptx_path.exists()

def test_scenario_9_persistent_preference(seeded_db):
    """Scenario 9: Owner preference persistence"""
    # 1. User: "Always assume UPI unless I say cash."
    preference_service.set_preference(seeded_db, "default_payment_mode", "UPI")

    # 2. Simulate new session querying preference
    val = preference_service.get_preference(seeded_db, "default_payment_mode")
    assert val == "UPI"
