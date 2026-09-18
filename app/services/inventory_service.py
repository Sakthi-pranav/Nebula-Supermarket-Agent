import uuid
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.db.models import Product

class InventoryError(Exception):
    """Base exception for inventory operations."""
    pass

class InsufficientStockError(InventoryError):
    """Raised when an operation attempts to sell or remove more stock than available."""
    pass

class ProductNotFoundError(InventoryError):
    """Raised when a specified product is not found in database."""
    pass

class AmbiguousProductError(InventoryError):
    """Raised when multiple products match a search query."""
    def __init__(self, message: str, matches: list[Product]):
        super().__init__(message)
        self.matches = matches

def search_products(db: Session, query: str) -> List[Product]:
    """Search products by SKU or fuzzy name match."""
    query = query.strip()
    if not query:
        return db.query(Product).all()
        
    pattern = f"%{query}%"
    return db.query(Product).filter(
        or_(
            Product.name.ilike(pattern),
            Product.sku.ilike(pattern),
            Product.category.ilike(pattern)
        )
    ).all()

def find_single_product(db: Session, identifier: str | int) -> Product:
    """
    Locate a single product by exact ID, exact SKU, or unambiguous name match.
    Raises ProductNotFoundError or AmbiguousProductError if ambiguous.
    """
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        product = db.query(Product).filter(Product.id == int(identifier)).first()
        if product:
            return product

    identifier_str = str(identifier).strip()
    
    # 1. Try exact SKU
    product = db.query(Product).filter(Product.sku.ilike(identifier_str)).first()
    if product:
        return product
        
    # 2. Try exact name match
    product = db.query(Product).filter(Product.name.ilike(identifier_str)).first()
    if product:
        return product
        
    # 3. Try fuzzy search
    matches = search_products(db, identifier_str)
    if not matches:
        raise ProductNotFoundError(f"No product found matching '{identifier_str}'.")
    if len(matches) == 1:
        return matches[0]
        
    # Check if one match is an exact word prefix/match
    exact_matches = [p for p in matches if p.name.lower() == identifier_str.lower()]
    if len(exact_matches) == 1:
        return exact_matches[0]

    names_list = [f"{p.name} ({p.unit})" for p in matches]
    raise AmbiguousProductError(
        f"Multiple products matched '{identifier_str}': {', '.join(names_list)}. Please specify exact product.",
        matches=matches
    )

def add_product(
    db: Session,
    name: str,
    category: str,
    unit: str,
    cost_price: Decimal,
    mrp: Decimal,
    quantity: Decimal = Decimal("0.000"),
    reorder_level: Decimal = Decimal("5.000"),
    hsn_code: str = "1905",
    gst_rate: Decimal = Decimal("5.00"),
    is_loose: bool = False,
    sku: Optional[str] = None
) -> Product:
    """Add a new product to inventory."""
    if not sku:
        sku = f"SKU-{uuid.uuid4().hex[:8].upper()}"
        
    # Check existing SKU
    existing = db.query(Product).filter(Product.sku.ilike(sku)).first()
    if existing:
        raise InventoryError(f"Product with SKU '{sku}' already exists.")
        
    # Check cost vs MRP guardrail (warn or disallow selling below cost if configured)
    if mrp < cost_price:
        raise InventoryError(f"Selling price/MRP (₹{mrp}) cannot be less than cost price (₹{cost_price}).")

    product = Product(
        sku=sku,
        name=name.strip(),
        category=category.strip(),
        unit=unit.strip().lower(),
        is_loose=is_loose,
        cost_price=Decimal(str(cost_price)),
        mrp=Decimal(str(mrp)),
        quantity=Decimal(str(quantity)),
        reorder_level=Decimal(str(reorder_level)),
        hsn_code=hsn_code.strip(),
        gst_rate=Decimal(str(gst_rate))
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def receive_stock(
    db: Session,
    product_identifier: str | int,
    quantity_added: Decimal,
    new_cost_price: Optional[Decimal] = None,
    new_mrp: Optional[Decimal] = None
) -> Product:
    """Receive stock into inventory (increases stock quantity)."""
    product = find_single_product(db, product_identifier)
    
    if Decimal(str(quantity_added)) <= Decimal("0"):
        raise InventoryError("Quantity added must be greater than 0.")
        
    # Lock product row using standard select for update logic or atomic update
    product.quantity += Decimal(str(quantity_added))
    
    if new_cost_price is not None and Decimal(str(new_cost_price)) > Decimal("0"):
        product.cost_price = Decimal(str(new_cost_price))
    if new_mrp is not None and Decimal(str(new_mrp)) > Decimal("0"):
        product.mrp = Decimal(str(new_mrp))
        
    db.commit()
    db.refresh(product)
    return product

def get_stock(db: Session, product_identifier: Optional[str | int] = None) -> List[dict]:
    """Retrieve current stock for one or all products."""
    if product_identifier:
        product = find_single_product(db, product_identifier)
        products = [product]
    else:
        products = db.query(Product).order_by(Product.name.asc()).all()
        
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "is_loose": p.is_loose,
            "cost_price": float(p.cost_price),
            "mrp": float(p.mrp),
            "quantity": float(p.quantity),
            "reorder_level": float(p.reorder_level),
            "is_low_stock": p.quantity <= p.reorder_level,
            "gst_rate": float(p.gst_rate),
            "hsn_code": p.hsn_code
        })
    return result

def get_low_stock(db: Session) -> List[dict]:
    """Find products at or below their reorder level."""
    products = db.query(Product).filter(Product.quantity <= Product.reorder_level).all()
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "quantity": float(p.quantity),
            "reorder_level": float(p.reorder_level),
            "unit": p.unit,
            "mrp": float(p.mrp)
        })
    return result

def atomic_decrement_stock(db: Session, product_id: int, quantity_to_decrement: Decimal) -> Product:
    """
    Atomically validate and decrement product stock inside an active transaction.
    Raises InsufficientStockError if stock would become negative.
    """
    # Fetch latest product state
    product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
    if not product:
        product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ProductNotFoundError(f"Product ID {product_id} not found.")

    qty = Decimal(str(quantity_to_decrement))
    if product.quantity < qty:
        raise InsufficientStockError(
            f"Oversell rejected for '{product.name}'. "
            f"Requested quantity: {qty} {product.unit}, "
            f"Available stock: {product.quantity} {product.unit}."
        )
        
    product.quantity -= qty
    if product.quantity < Decimal("0"):
        raise InsufficientStockError(f"Stock for '{product.name}' cannot be negative.")
        
    return product
