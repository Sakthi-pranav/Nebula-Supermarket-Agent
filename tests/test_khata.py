import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.services import khata_service

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_khata_credit_and_repayment(db_session):
    cust = khata_service.find_or_create_customer(db_session, "Ramesh Kumar", "9876543210")
    assert cust.current_balance == Decimal("0.00")

    # 1. "Put ₹500 on Ramesh's credit"
    khata_service.add_credit(db_session, cust.id, Decimal("500.00"))
    bal = khata_service.get_customer_balance(db_session, cust.id)
    assert bal["current_balance"] == 500.0

    # 2. "Ramesh paid ₹300"
    khata_service.record_payment(db_session, cust.id, Decimal("300.00"))
    bal = khata_service.get_customer_balance(db_session, cust.id)
    assert bal["current_balance"] == 200.0

def test_invalid_khata_settlement(db_session):
    cust = khata_service.find_or_create_customer(db_session, "Suresh", "9123456789")
    
    # Customer balance is 0. Attempting to record payment must fail
    with pytest.raises(khata_service.KhataError) as exc_info:
        khata_service.record_payment(db_session, cust.id, Decimal("100.00"))
        
    assert "zero outstanding balance" in str(exc_info.value)
