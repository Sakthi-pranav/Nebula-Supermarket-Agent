from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.db.models import OwnerPreference

def get_preference(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve an owner preference by key."""
    key_clean = key.strip().lower()
    pref = db.query(OwnerPreference).filter(OwnerPreference.key == key_clean).first()
    if pref:
        return pref.value
    return default

def set_preference(db: Session, key: str, value: str) -> OwnerPreference:
    """Set or update an owner preference in persistent database."""
    key_clean = key.strip().lower()
    val_clean = value.strip()
    
    pref = db.query(OwnerPreference).filter(OwnerPreference.key == key_clean).first()
    if pref:
        pref.value = val_clean
        pref.updated_at = datetime.now()
    else:
        pref = OwnerPreference(key=key_clean, value=val_clean)
        db.add(pref)
        
    db.commit()
    db.refresh(pref)
    return pref

def get_all_preferences(db: Session) -> Dict[str, str]:
    """Retrieve all persistent owner preferences as a key-value dictionary."""
    prefs = db.query(OwnerPreference).all()
    return {p.key: p.value for p in prefs}
