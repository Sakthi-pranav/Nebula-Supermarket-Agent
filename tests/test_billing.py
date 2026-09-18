import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import BillStatus
from app.services import inventory_service, billing_service

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_draft_bill_multi_turn_editing(db_session):
    # Add seed products
    p_sugar = inventory_service.add_product(
        db_session, "loose sugar", "Staples", "kg", Decimal("38.00"), Decimal("44.00"), Decimal("100.000")
    )
    p_maggi = inventory_service.add_product(
        db_session, "Maggi 70g", "Instant", "packet", Decimal("11.50"), Decimal("14.00"), Decimal("50.000")
    )
    p_butter = inventory_service.add_product(
        db_session, "Amul Butter 100g", "Dairy", "packet", Decimal("50.00"), Decimal("58.00"), Decimal("20.000")
    )

    # 1. User: "Make a bill: 2kg sugar and 4 Maggi"
    bill = billing_service.add_item_to_bill(db_session, None, p_sugar.id, Decimal("2"))
    bill = billing_service.add_item_to_bill(db_session, bill.id, p_maggi.id, Decimal("4"))
    assert len(bill.items) == 2
    
    # Verify stock has NOT decremented on draft
    assert inventory_service.find_single_product(db_session, p_sugar.id).quantity == Decimal("100.000")

    # 2. User: "Add 1 Amul butter"
    bill = billing_service.add_item_to_bill(db_session, bill.id, p_butter.id, Decimal("1"))
    assert len(bill.items) == 3

    # 3. User: "Remove butter and make Maggi 6"
    bill = billing_service.remove_item_from_bill(db_session, bill.id, p_butter.id)
    bill = billing_service.update_bill_item_quantity(db_session, bill.id, p_maggi.id, Decimal("6"))
    assert len(bill.items) == 2
    
    maggi_item = [i for i in bill.items if i.product_id == p_maggi.id][0]
    assert maggi_item.quantity == Decimal("6.000")

def test_oversell_rejection(db_session):
    p_maggi = inventory_service.add_product(
        db_session, "Maggi 70g", "Instant", "packet", Decimal("11.50"), Decimal("14.00"), Decimal("6.000")
    )

    # Try to sell 10 Maggi when stock is only 6
    bill = billing_service.add_item_to_bill(db_session, None, p_maggi.id, Decimal("10"))
    
    with pytest.raises(inventory_service.InsufficientStockError) as exc_info:
        billing_service.finalize_bill(db_session, bill.id)
        
    assert "Oversell rejected" in str(exc_info.value)
    
    # Stock must remain unchanged at 6
    assert inventory_service.find_single_product(db_session, p_maggi.id).quantity == Decimal("6.000")

def test_finalization_and_idempotency(db_session):
    p_rice = inventory_service.add_product(
        db_session, "loose rice", "Staples", "kg", Decimal("50.00"), Decimal("60.00"), Decimal("50.000")
    )
    
    bill = billing_service.add_item_to_bill(db_session, None, p_rice.id, Decimal("5"))
    
    # Finalize bill 1st time
    finalized_bill = billing_service.finalize_bill(db_session, bill.id, idempotency_key="TEST-KEY-123")
    assert finalized_bill.status == BillStatus.FINALIZED
    
    # Stock decrements from 50 to 45
    assert inventory_service.find_single_product(db_session, p_rice.id).quantity == Decimal("45.000")

    # Repeat finalize operation (simulating Telegram redelivery)
    repeated_bill = billing_service.finalize_bill(db_session, bill.id, idempotency_key="TEST-KEY-123")
    assert repeated_bill.id == finalized_bill.id
    
    # Stock MUST NOT decrement twice (still 45)
    assert inventory_service.find_single_product(db_session, p_rice.id).quantity == Decimal("45.000")
