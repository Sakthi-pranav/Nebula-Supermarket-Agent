from decimal import Decimal
from app.services.gst_service import calculate_item_gst, calculate_bill_totals

def test_gst_5_percent_split():
    """Test 5% GST calculation and CGST/SGST 2.5% split."""
    res = calculate_item_gst(unit_price=Decimal("100.00"), quantity=Decimal("2"), gst_rate=Decimal("5.00"))
    assert res["taxable_amount"] == Decimal("200.00")
    assert res["gst_amount"] == Decimal("10.00")
    assert res["cgst_amount"] == Decimal("5.00")
    assert res["sgst_amount"] == Decimal("5.00")
    assert res["total_amount"] == Decimal("210.00")

def test_gst_12_percent_split():
    """Test 12% GST calculation."""
    res = calculate_item_gst(unit_price=Decimal("58.00"), quantity=Decimal("1"), gst_rate=Decimal("12.00"))
    assert res["taxable_amount"] == Decimal("58.00")
    assert res["gst_amount"] == Decimal("6.96")
    assert res["cgst_amount"] == Decimal("3.48")
    assert res["sgst_amount"] == Decimal("3.48")
    assert res["total_amount"] == Decimal("64.96")

def test_gst_0_percent():
    """Test 0% GST (e.g. Salt, Loose Rice)."""
    res = calculate_item_gst(unit_price=Decimal("28.00"), quantity=Decimal("5"), gst_rate=Decimal("0.00"))
    assert res["taxable_amount"] == Decimal("140.00")
    assert res["gst_amount"] == Decimal("0.00")
    assert res["cgst_amount"] == Decimal("0.00")
    assert res["sgst_amount"] == Decimal("0.00")
    assert res["total_amount"] == Decimal("140.00")

def test_bill_totals_aggregation():
    item1 = calculate_item_gst(unit_price=Decimal("100.00"), quantity=Decimal("1"), gst_rate=Decimal("18.00"))
    item2 = calculate_item_gst(unit_price=Decimal("50.00"), quantity=Decimal("2"), gst_rate=Decimal("5.00"))
    
    totals = calculate_bill_totals([item1, item2])
    assert totals["subtotal"] == Decimal("200.00")
    assert totals["total_cgst"] == Decimal("11.50")
    assert totals["total_sgst"] == Decimal("11.50")
    assert totals["total_tax"] == Decimal("23.00")
    assert totals["grand_total"] == Decimal("223.00")
