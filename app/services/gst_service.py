from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")

def quantize_money(amount: Decimal) -> Decimal:
    """Round Decimal money values to 2 decimal places using standard half-up rounding."""
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def calculate_item_gst(unit_price: Decimal, quantity: Decimal, gst_rate: Decimal) -> dict:
    """
    Calculate GST, CGST, SGST, taxable amount and total for a line item.
    
    Formula:
      taxable_amount = quantize(quantity * unit_price)
      gst_amount = quantize(taxable_amount * (gst_rate / 100))
      cgst_amount = quantize(gst_amount / 2)
      sgst_amount = gst_amount - cgst_amount  (ensures exact sum)
      total_amount = taxable_amount + gst_amount
    """
    if not isinstance(unit_price, Decimal):
        unit_price = Decimal(str(unit_price))
    if not isinstance(quantity, Decimal):
        quantity = Decimal(str(quantity))
    if not isinstance(gst_rate, Decimal):
        gst_rate = Decimal(str(gst_rate))

    taxable_amount = quantize_money(quantity * unit_price)
    
    # Calculate tax based on tax-exclusive MRP or tax rate
    gst_amount = quantize_money(taxable_amount * (gst_rate / Decimal("100.00")))
    cgst_amount = quantize_money(gst_amount / Decimal("2.00"))
    sgst_amount = gst_amount - cgst_amount
    total_amount = taxable_amount + gst_amount

    return {
        "taxable_amount": taxable_amount,
        "gst_rate": gst_rate,
        "gst_amount": gst_amount,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "total_amount": total_amount
    }

def calculate_bill_totals(items_gst_list: list[dict]) -> dict:
    """Aggregate totals for a bill from line item calculations."""
    subtotal = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    
    for item in items_gst_list:
        subtotal += item["taxable_amount"]
        total_cgst += item["cgst_amount"]
        total_sgst += item["sgst_amount"]
        
    total_tax = total_cgst + total_sgst
    grand_total = subtotal + total_tax
    
    return {
        "subtotal": quantize_money(subtotal),
        "total_cgst": quantize_money(total_cgst),
        "total_sgst": quantize_money(total_sgst),
        "total_tax": quantize_money(total_tax),
        "grand_total": quantize_money(grand_total)
    }
