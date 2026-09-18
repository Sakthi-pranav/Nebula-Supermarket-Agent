import sys
from pathlib import Path
from decimal import Decimal

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import init_db, SessionLocal
from app.db.models import Product, OwnerPreference, Customer

SEED_PRODUCTS = [
    {
        "sku": "SKU-ATTA-5KG",
        "name": "Aashirvaad Atta 5kg",
        "category": "Staples",
        "unit": "kg",
        "is_loose": False,
        "cost_price": Decimal("210.00"),
        "mrp": Decimal("245.00"),
        "quantity": Decimal("30.000"),
        "reorder_level": Decimal("5.000"),
        "hsn_code": "1101",
        "gst_rate": Decimal("5.00")
    },
    {
        "sku": "SKU-SALT-1KG",
        "name": "Tata Salt 1kg",
        "category": "Staples",
        "unit": "packet",
        "is_loose": False,
        "cost_price": Decimal("22.00"),
        "mrp": Decimal("28.00"),
        "quantity": Decimal("50.000"),
        "reorder_level": Decimal("10.000"),
        "hsn_code": "2501",
        "gst_rate": Decimal("0.00")
    },
    {
        "sku": "SKU-AMUL-BUTTER-100G",
        "name": "Amul Butter 100g",
        "category": "Dairy",
        "unit": "packet",
        "is_loose": False,
        "cost_price": Decimal("50.00"),
        "mrp": Decimal("58.00"),
        "quantity": Decimal("25.000"),
        "reorder_level": Decimal("5.000"),
        "hsn_code": "0405",
        "gst_rate": Decimal("12.00")
    },
    {
        "sku": "SKU-FORTUNE-OIL-1L",
        "name": "Fortune Sunflower Oil 1L",
        "category": "Edible Oils",
        "unit": "litre",
        "is_loose": False,
        "cost_price": Decimal("125.00"),
        "mrp": Decimal("145.00"),
        "quantity": Decimal("40.000"),
        "reorder_level": Decimal("8.000"),
        "hsn_code": "1512",
        "gst_rate": Decimal("5.00")
    },
    {
        "sku": "SKU-MAGGI-70G",
        "name": "Maggi 70g",
        "category": "Instant Food",
        "unit": "packet",
        "is_loose": False,
        "cost_price": Decimal("11.50"),
        "mrp": Decimal("14.00"),
        "quantity": Decimal("100.000"),
        "reorder_level": Decimal("20.000"),
        "hsn_code": "1902",
        "gst_rate": Decimal("12.00")
    },
    {
        "sku": "SKU-PARLE-G",
        "name": "Parle-G",
        "category": "Snacks",
        "unit": "packet",
        "is_loose": False,
        "cost_price": Decimal("8.20"),
        "mrp": Decimal("10.00"),
        "quantity": Decimal("150.000"),
        "reorder_level": Decimal("25.000"),
        "hsn_code": "1905",
        "gst_rate": Decimal("18.00")
    },
    {
        "sku": "SKU-SURF-EXCEL-1KG",
        "name": "Surf Excel",
        "category": "Household",
        "unit": "packet",
        "is_loose": False,
        "cost_price": Decimal("128.00"),
        "mrp": Decimal("150.00"),
        "quantity": Decimal("20.000"),
        "reorder_level": Decimal("5.000"),
        "hsn_code": "3402",
        "gst_rate": Decimal("18.00")
    },
    {
        "sku": "SKU-LOOSE-SUGAR",
        "name": "loose sugar",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "cost_price": Decimal("38.00"),
        "mrp": Decimal("44.00"),
        "quantity": Decimal("100.000"),
        "reorder_level": Decimal("15.000"),
        "hsn_code": "1701",
        "gst_rate": Decimal("0.00")
    },
    {
        "sku": "SKU-LOOSE-RICE",
        "name": "loose rice",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "cost_price": Decimal("50.00"),
        "mrp": Decimal("60.00"),
        "quantity": Decimal("200.000"),
        "reorder_level": Decimal("30.000"),
        "hsn_code": "1006",
        "gst_rate": Decimal("0.00")
    },
    {
        "sku": "SKU-LOOSE-DAL",
        "name": "loose dal",
        "category": "Staples",
        "unit": "kg",
        "is_loose": True,
        "cost_price": Decimal("100.00"),
        "mrp": Decimal("120.00"),
        "quantity": Decimal("80.000"),
        "reorder_level": Decimal("15.000"),
        "hsn_code": "0713",
        "gst_rate": Decimal("0.00")
    }
]

SEED_CUSTOMERS = [
    {"name": "Ramesh Kumar", "phone": "9876543210", "current_balance": Decimal("0.00")},
    {"name": "Suresh Sharma", "phone": "9123456789", "current_balance": Decimal("0.00")},
    {"name": "Anita Patel", "phone": "9988776655", "current_balance": Decimal("0.00")},
]

SEED_PREFERENCES = [
    {"key": "default_payment_mode", "value": "UPI"},
    {"key": "allow_sell_below_cost", "value": "false"},
    {"key": "auto_generate_pdf", "value": "true"},
]

def seed():
    print("Initializing Database tables...")
    init_db()
    db = SessionLocal()
    try:
        print("Seeding Products...")
        for p_data in SEED_PRODUCTS:
            existing = db.query(Product).filter(Product.sku == p_data["sku"]).first()
            if not existing:
                product = Product(**p_data)
                db.add(product)
            else:
                for k, v in p_data.items():
                    setattr(existing, k, v)
        
        print("Seeding Customers...")
        for c_data in SEED_CUSTOMERS:
            existing = db.query(Customer).filter(Customer.name == c_data["name"]).first()
            if not existing:
                customer = Customer(**c_data)
                db.add(customer)

        print("Seeding Owner Preferences...")
        for pref in SEED_PREFERENCES:
            existing = db.query(OwnerPreference).filter(OwnerPreference.key == pref["key"]).first()
            if not existing:
                db.add(OwnerPreference(key=pref["key"], value=pref["value"]))

        db.commit()
        print("Database seeded successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
