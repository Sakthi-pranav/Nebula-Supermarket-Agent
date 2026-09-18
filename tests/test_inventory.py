import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.services import inventory_service

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_add_product(db_session):
    prod = inventory_service.add_product(
        db=db_session,
        name="Test Tea 250g",
        category="Beverages",
        unit="packet",
        cost_price=Decimal("90.00"),
        mrp=Decimal("110.00"),
        quantity=Decimal("20.000"),
        reorder_level=Decimal("5.000"),
        hsn_code="0902",
        gst_rate=Decimal("5.00")
    )
    assert prod.id is not None
    assert prod.name == "Test Tea 250g"
    assert prod.quantity == Decimal("20.000")

def test_receive_stock(db_session):
    prod = inventory_service.add_product(
        db=db_session,
        name="Maggi 70g",
        category="Instant",
        unit="packet",
        cost_price=Decimal("11.50"),
        mrp=Decimal("14.00"),
        quantity=Decimal("10.000")
    )
    
    updated_prod = inventory_service.receive_stock(
        db=db_session,
        product_identifier=prod.id,
        quantity_added=Decimal("50.000")
    )
    assert updated_prod.quantity == Decimal("60.000")

def test_stock_query_and_low_stock(db_session):
    p1 = inventory_service.add_product(
        db=db_session,
        name="Low Stock Item",
        category="Misc",
        unit="piece",
        cost_price=Decimal("10.00"),
        mrp=Decimal("15.00"),
        quantity=Decimal("2.000"),
        reorder_level=Decimal("5.000")
    )
    p2 = inventory_service.add_product(
        db=db_session,
        name="High Stock Item",
        category="Misc",
        unit="piece",
        cost_price=Decimal("10.00"),
        mrp=Decimal("15.00"),
        quantity=Decimal("50.000"),
        reorder_level=Decimal("5.000")
    )

    low_items = inventory_service.get_low_stock(db_session)
    assert len(low_items) == 1
    assert low_items[0]["name"] == "Low Stock Item"
