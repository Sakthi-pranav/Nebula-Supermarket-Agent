import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.services import preference_service

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_persistent_preferences(db_session):
    # Set preference
    preference_service.set_preference(db_session, "default_payment_mode", "UPI")
    
    # Retrieve preference
    val = preference_service.get_preference(db_session, "default_payment_mode")
    assert val == "UPI"
    
    # Update preference
    preference_service.set_preference(db_session, "default_payment_mode", "CASH")
    val_updated = preference_service.get_preference(db_session, "default_payment_mode")
    assert val_updated == "CASH"
