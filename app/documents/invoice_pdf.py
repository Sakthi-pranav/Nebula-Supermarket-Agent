import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.config import settings
from app.db.models import Bill

def generate_pdf_invoice(bill: Bill, output_path: Path | None = None) -> Path:
    """
    Generate a professional GST-compliant PDF invoice for a finalized or draft bill using ReportLab.
    """
    if not output_path:
        settings.INVOICE_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"Invoice_{bill.bill_number}.pdf"
        output_path = settings.INVOICE_DIR / filename

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1A365D")   # Deep Navy
    SECONDARY = colors.HexColor("#2B6CB0") # Slate Blue
    NEUTRAL_DARK = colors.HexColor("#2D3748")
    NEUTRAL_LIGHT = colors.HexColor("#EDF2F7")
    
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=PRIMARY,
        fontName='Helvetica-Bold'
    )
    
    store_style = ParagraphStyle(
        'StoreInfo',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=NEUTRAL_DARK
    )
    
    header_right = ParagraphStyle(
        'HeaderRight',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2, # Right aligned
        textColor=NEUTRAL_DARK
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=1 # Center
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=11,
        textColor=NEUTRAL_DARK
    )

    table_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=table_cell,
        alignment=1
    )

    table_cell_right = ParagraphStyle(
        'TableCellRight',
        parent=table_cell,
        alignment=2
    )

    elements = []

    # 1. Header Section (Store Info & Invoice Metadata)
    header_data = [
        [
            Paragraph(f"<b>{settings.STORE_NAME}</b><br/>"
                      f"{settings.STORE_ADDRESS}<br/>"
                      f"Phone: {settings.STORE_PHONE}<br/>"
                      f"<b>GSTIN:</b> {settings.STORE_GSTIN}", store_style),
            Paragraph(f"<font color='{PRIMARY.hexval()}'><b>TAX INVOICE</b></font><br/>"
                      f"<b>Invoice #:</b> {bill.bill_number}<br/>"
                      f"<b>Date:</b> {bill.created_at.strftime('%d-%b-%Y %I:%M %p')}<br/>"
                      f"<b>Status:</b> {bill.status.value}", header_right)
        ]
    ]
    
    header_table = Table(header_data, colWidths=[3.25 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=5, spaceAfter=15))

    # 2. Customer & Payment Details
    customer_name = bill.customer_name or (bill.customer.name if bill.customer else "Walk-in Customer")
    cust_phone = bill.customer.phone if bill.customer and bill.customer.phone else "N/A"
    pay_mode = bill.payment_mode.value if bill.payment_mode else "UPI"
    pay_ref = f" (Ref: {bill.payment_ref})" if bill.payment_ref else ""

    info_data = [
        [
            Paragraph(f"<b>Billed To:</b> {customer_name}", store_style),
            Paragraph(f"<b>Contact:</b> {cust_phone}", store_style),
            Paragraph(f"<b>Payment Mode:</b> {pay_mode}{pay_ref}", store_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[2.5 * inch, 2.0 * inch, 2.25 * inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NEUTRAL_LIGHT),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 15))

    # 3. Line Items Table
    headers = ["#", "Item Description", "HSN", "Qty", "Rate (₹)", "GST %", "CGST (₹)", "SGST (₹)", "Total (₹)"]
    table_rows = [[Paragraph(h, table_header) for h in headers]]

    for idx, item in enumerate(bill.items, start=1):
        row = [
            Paragraph(str(idx), table_cell_center),
            Paragraph(item.product_name, table_cell),
            Paragraph(item.hsn_code or "1905", table_cell_center),
            Paragraph(f"{float(item.quantity):.3f} {item.unit}".rstrip('0').rstrip('.'), table_cell_center),
            Paragraph(f"{float(item.unit_price):.2f}", table_cell_right),
            Paragraph(f"{float(item.gst_rate):.1f}%", table_cell_center),
            Paragraph(f"{float(item.cgst_amount):.2f}", table_cell_right),
            Paragraph(f"{float(item.sgst_amount):.2f}", table_cell_right),
            Paragraph(f"{float(item.total_amount):.2f}", table_cell_right),
        ]
        table_rows.append(row)

    col_widths = [0.35*inch, 2.2*inch, 0.6*inch, 0.75*inch, 0.75*inch, 0.6*inch, 0.75*inch, 0.75*inch, 0.9*inch]
    items_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]
    
    # Alternating row colors
    for r in range(1, len(table_rows)):
        if r % 2 == 0:
            t_style.append(('BACKGROUND', (0, r), (-1, r), NEUTRAL_LIGHT))
            
    items_table.setStyle(TableStyle(t_style))
    elements.append(items_table)
    elements.append(Spacer(1, 15))

    # 4. Tax Breakup & Grand Totals Summary
    summary_data = [
        [Paragraph("", store_style), Paragraph("<b>Subtotal (Excl. Tax):</b>", table_cell_right), Paragraph(f"₹{float(bill.subtotal):.2f}", table_cell_right)],
        [Paragraph("", store_style), Paragraph("<b>Central GST (CGST):</b>", table_cell_right), Paragraph(f"₹{float(bill.total_cgst):.2f}", table_cell_right)],
        [Paragraph("", store_style), Paragraph("<b>State GST (SGST):</b>", table_cell_right), Paragraph(f"₹{float(bill.total_sgst):.2f}", table_cell_right)],
        [Paragraph("", store_style), Paragraph("<b>Total Tax Collected:</b>", table_cell_right), Paragraph(f"₹{float(bill.total_tax):.2f}", table_cell_right)],
        [Paragraph("", store_style), Paragraph("<b>Grand Total:</b>", ParagraphStyle('GT', parent=table_cell_right, fontName='Helvetica-Bold', fontSize=10, textColor=PRIMARY)), 
         Paragraph(f"<b>₹{float(bill.grand_total):.2f}</b>", ParagraphStyle('GTVal', parent=table_cell_right, fontName='Helvetica-Bold', fontSize=11, textColor=PRIMARY))]
    ]

    summary_table = Table(summary_data, colWidths=[3.75 * inch, 2.0 * inch, 1.9 * inch])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEABOVE', (1,4), (2,4), 1, PRIMARY),
        ('LINEBELOW', (1,4), (2,4), 1.5, PRIMARY),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(summary_table)

    elements.append(Spacer(1, 25))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceBefore=10, spaceAfter=10))

    # 5. Footer Notes
    footer_text = Paragraph(
        "<font color='#718096' size='8'>Thank you for shopping at Sharma General Supermarket!<br/>"
        "This is a computer-generated tax invoice and requires no signature.</font>",
        ParagraphStyle('Footer', parent=styles['Normal'], alignment=1)
    )
    elements.append(footer_text)

    # Build PDF
    doc.build(elements)
    bill.pdf_path = str(output_path)
    return output_path
