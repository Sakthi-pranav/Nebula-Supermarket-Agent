import pytest
from pathlib import Path
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.services import inventory_service, billing_service
from app.documents import invoice_pdf, sales_pptx

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_pdf_invoice_generation(db_session, tmp_path):
    p = inventory_service.add_product(
        db_session, "Tata Salt 1kg", "Staples", "packet", Decimal("22.00"), Decimal("28.00"), Decimal("50.000")
    )
    bill = billing_service.add_item_to_bill(db_session, None, p.id, Decimal("2"))
    finalized_bill = billing_service.finalize_bill(db_session, bill.id)

    out_file = tmp_path / "test_invoice.pdf"
    res_path = invoice_pdf.generate_pdf_invoice(finalized_bill, out_file)

    assert res_path.exists()
    assert res_path.stat().st_size > 0

def test_pptx_sales_deck_generation(db_session, tmp_path):
    p = inventory_service.add_product(
        db_session, "Aashirvaad Atta 5kg", "Staples", "kg", Decimal("210.00"), Decimal("245.00"), Decimal("30.000")
    )
    bill = billing_service.add_item_to_bill(db_session, None, p.id, Decimal("1"))
    billing_service.finalize_bill(db_session, bill.id)

    today = date.today()
    start_date = today - timedelta(days=7)
    
    out_file = tmp_path / "test_sales_deck.pptx"
    res_path = sales_pptx.generate_sales_pptx(db_session, start_date, today, out_file)

    assert res_path.exists()
    assert res_path.stat().st_size > 0
