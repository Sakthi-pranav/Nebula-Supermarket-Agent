import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Bill, BillItem, BillStatus, Product, PaymentMode

# Color Theme
PRIMARY_COLOR = RGBColor(26, 54, 93)     # #1A365D Navy
SECONDARY_COLOR = RGBColor(43, 108, 176) # #2B6CB0 Blue
ACCENT_COLOR = RGBColor(221, 107, 32)   # #DD6B20 Orange
TEXT_DARK = RGBColor(45, 55, 72)         # #2D3748 Charcoal
LIGHT_BG = RGBColor(247, 250, 252)       # #F7FAFC

def generate_charts(db: Session, start_date: date, end_date: date) -> Dict[str, Path]:
    """Generate Matplotlib charts for PPTX integration."""
    temp_dir = settings.REPORT_DIR / "charts"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    chart_paths = {}

    # 1. Daily Sales Trend Bar Chart
    current_date = start_date
    daily_labels = []
    daily_sales = []
    
    while current_date <= end_date:
        start_dt = datetime.combine(current_date, datetime.min.time())
        end_dt = datetime.combine(current_date, datetime.max.time())
        
        day_total = db.query(Bill).filter(
            Bill.status == BillStatus.FINALIZED,
            Bill.finalized_at >= start_dt,
            Bill.finalized_at <= end_dt
        ).all()
        
        rev = sum([float(b.grand_total) for b in day_total])
        daily_labels.append(current_date.strftime("%d %b"))
        daily_sales.append(rev)
        current_date += timedelta(days=1)

    fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=200)
    bars = ax.bar(daily_labels, daily_sales, color="#2B6CB0", width=0.55)
    ax.set_title("Daily Sales Revenue (₹)", fontsize=12, fontweight='bold', color="#1A365D", pad=12)
    ax.set_ylabel("Revenue (₹)", fontsize=9, color="#4A5568")
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f"₹{height:,.0f}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, fontweight='bold', color="#2D3748")

    plt.tight_layout()
    chart1_path = temp_dir / "daily_sales.png"
    plt.savefig(chart1_path, bbox_inches='tight')
    plt.close(fig)
    chart_paths["daily_sales"] = chart1_path

    # 2. Top Selling Products Chart
    top_items = db.query(
        BillItem.product_name,
        plt.Column if hasattr(plt, 'Column') else BillItem.product_name
    )
    
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    top_query = db.query(
        BillItem.product_name,
        func.sum(BillItem.quantity).label("total_qty")
    ).join(Bill).filter(
        Bill.status == BillStatus.FINALIZED,
        Bill.finalized_at >= start_dt,
        Bill.finalized_at <= end_dt
    ).group_by(BillItem.product_name).order_by(func.sum(BillItem.quantity).desc()).limit(5).all()

    fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=200)
    if top_query:
        names = [item[0] for item in reversed(top_query)]
        qtys = [float(item[1]) for item in reversed(top_query)]
        bars = ax.barh(names, qtys, color="#DD6B20", height=0.55)
        ax.set_title("Top 5 Products Sold (Units)", fontsize=12, fontweight='bold', color="#1A365D", pad=12)
        ax.set_xlabel("Quantity Sold", fontsize=9, color="#4A5568")
        ax.grid(axis='x', linestyle='--', alpha=0.5)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        for bar in bars:
            width = bar.get_width()
            ax.annotate(f"{width:,.1f}",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(4, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=8, fontweight='bold', color="#2D3748")
    else:
        ax.text(0.5, 0.5, "No Sales Data Recorded", ha='center', va='center', fontsize=12, color="#A0AEC0")
        ax.axis('off')

    plt.tight_layout()
    chart2_path = temp_dir / "top_products.png"
    plt.savefig(chart2_path, bbox_inches='tight')
    plt.close(fig)
    chart_paths["top_products"] = chart2_path

    # 3. Payment Methods Breakdown Donut Chart
    payment_counts = db.query(
        Bill.payment_mode,
        func.sum(Bill.grand_total)
    ).filter(
        Bill.status == BillStatus.FINALIZED,
        Bill.finalized_at >= start_dt,
        Bill.finalized_at <= end_dt
    ).group_by(Bill.payment_mode).all()

    fig, ax = plt.subplots(figsize=(4.5, 3.5), dpi=200)
    if payment_counts and sum([float(p[1]) for p in payment_counts]) > 0:
        labels = [p[0].value for p in payment_counts]
        sizes = [float(p[1]) for p in payment_counts]
        colors_pie = ["#319795", "#3182CE", "#D69E2E", "#E53E3E"]
        
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, autopct='%1.1f%%',
            startangle=140, colors=colors_pie[:len(labels)],
            textprops=dict(color="#2D3748", fontsize=8, fontweight='bold'),
            wedgeprops=dict(width=0.4, edgecolor='w')
        )
        ax.set_title("Payment Method Share", fontsize=11, fontweight='bold', color="#1A365D")
    else:
        ax.text(0.5, 0.5, "No Payment Data", ha='center', va='center', fontsize=11, color="#A0AEC0")
        ax.axis('off')

    plt.tight_layout()
    chart3_path = temp_dir / "payment_methods.png"
    plt.savefig(chart3_path, bbox_inches='tight')
    plt.close(fig)
    chart_paths["payment_methods"] = chart3_path

    return chart_paths

def generate_sales_pptx(db: Session, start_date: date, end_date: date, output_path: Optional[Path] = None) -> Path:
    """
    Generate a 5-slide PowerPoint deck for weekly sales analysis with real database metrics & charts.
    """
    if not output_path:
        settings.REPORT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"Sales_Analysis_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pptx"
        output_path = settings.REPORT_DIR / filename

    charts = generate_charts(db, start_date, end_date)

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625) # 16:9 Widescreen aspect ratio
    blank_layout = prs.slide_layouts[6]

    # Calculate overall metrics
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    bills = db.query(Bill).filter(
        Bill.status == BillStatus.FINALIZED,
        Bill.finalized_at >= start_dt,
        Bill.finalized_at <= end_dt
    ).all()

    total_revenue = sum([float(b.grand_total) for b in bills])
    total_tax = sum([float(b.total_tax) for b in bills])
    total_txns = len(bills)

    # -------------------------------------------------------------
    # SLIDE 1: Title Slide
    # -------------------------------------------------------------
    slide1 = prs.slides.add_slide(blank_layout)
    
    # Header Accent bar
    shape = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(10), Inches(0.4))
    shape.fill.solid()
    shape.fill.fore_color.rgb = PRIMARY_COLOR
    shape.line.color.rgb = PRIMARY_COLOR

    # Title & Subtitle Box
    tx_box = slide1.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(8.4), Inches(2.5))
    tf = tx_box.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = "Weekly Supermarket Operations & Sales Analysis"
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_COLOR
    
    p2 = tf.add_paragraph()
    p2.text = f"{settings.STORE_NAME} | Period: {start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}"
    p2.font.size = Pt(14)
    p2.font.color.rgb = SECONDARY_COLOR
    p2.space_before = Pt(10)

    p3 = tf.add_paragraph()
    p3.text = f"Generated by AI Supermarket Ops Agent on {datetime.now().strftime('%d-%b-%Y %H:%M')}"
    p3.font.size = Pt(10)
    p3.font.color.rgb = TEXT_DARK
    p3.space_before = Pt(25)

    # -------------------------------------------------------------
    # SLIDE 2: Executive Summary & KPI Cards
    # -------------------------------------------------------------
    slide2 = prs.slides.add_slide(blank_layout)
    
    title_box = slide2.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(8.8), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "Executive Summary & Performance Highlights"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_COLOR

    # KPI Box 1: Total Revenue
    kpi1 = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.5), Inches(2.7), Inches(1.8))
    kpi1.fill.solid()
    kpi1.fill.fore_color.rgb = LIGHT_BG
    kpi1.line.color.rgb = SECONDARY_COLOR
    tf1 = kpi1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "Total Revenue\n"
    p.font.size = Pt(12)
    p.font.color.rgb = SECONDARY_COLOR
    p_val = tf1.add_paragraph()
    p_val.text = f"₹{total_revenue:,.2f}"
    p_val.font.size = Pt(22)
    p_val.font.bold = True
    p_val.font.color.rgb = PRIMARY_COLOR

    # KPI Box 2: Total Tax Collected
    kpi2 = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(3.65), Inches(1.5), Inches(2.7), Inches(1.8))
    kpi2.fill.solid()
    kpi2.fill.fore_color.rgb = LIGHT_BG
    kpi2.line.color.rgb = SECONDARY_COLOR
    tf2 = kpi2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "Total GST Tax Collected\n"
    p.font.size = Pt(12)
    p.font.color.rgb = SECONDARY_COLOR
    p_val = tf2.add_paragraph()
    p_val.text = f"₹{total_tax:,.2f}"
    p_val.font.size = Pt(22)
    p_val.font.bold = True
    p_val.font.color.rgb = ACCENT_COLOR

    # KPI Box 3: Total Finalized Bills
    kpi3 = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.7), Inches(1.5), Inches(2.7), Inches(1.8))
    kpi3.fill.solid()
    kpi3.fill.fore_color.rgb = LIGHT_BG
    kpi3.line.color.rgb = SECONDARY_COLOR
    tf3 = kpi3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "Completed Bills\n"
    p.font.size = Pt(12)
    p.font.color.rgb = SECONDARY_COLOR
    p_val = tf3.add_paragraph()
    p_val.text = f"{total_txns}"
    p_val.font.size = Pt(22)
    p_val.font.bold = True
    p_val.font.color.rgb = PRIMARY_COLOR

    # Add Payment method donut chart to Slide 2 bottom right
    slide2.shapes.add_picture(str(charts["payment_methods"]), Inches(5.0), Inches(2.3), width=Inches(4.5))

    # Notes Box
    notes_box = slide2.shapes.add_textbox(Inches(0.6), Inches(3.5), Inches(4.2), Inches(1.5))
    tf_notes = notes_box.text_frame
    tf_notes.word_wrap = True
    p = tf_notes.paragraphs[0]
    p.text = "Key Takeaways:"
    p.font.bold = True
    p.font.size = Pt(12)
    p.font.color.rgb = PRIMARY_COLOR
    
    p = tf_notes.add_paragraph()
    p.text = f"• Average Ticket Size: ₹{(total_revenue / total_txns if total_txns > 0 else 0):,.2f} per bill."
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_DARK
    
    p = tf_notes.add_paragraph()
    p.text = f"• All sales transactions recorded with deterministic GST compliance."
    p.font.size = Pt(10)
    p.font.color.rgb = TEXT_DARK

    # -------------------------------------------------------------
    # SLIDE 3: Revenue & Daily Sales Breakdown
    # -------------------------------------------------------------
    slide3 = prs.slides.add_slide(blank_layout)
    
    title_box = slide3.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(8.8), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "Daily Revenue Breakdown"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_COLOR

    slide3.shapes.add_picture(str(charts["daily_sales"]), Inches(1.75), Inches(1.3), width=Inches(6.5))

    # -------------------------------------------------------------
    # SLIDE 4: Product Sales Performance
    # -------------------------------------------------------------
    slide4 = prs.slides.add_slide(blank_layout)
    
    title_box = slide4.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(8.8), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "Top Performing Products"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_COLOR

    slide4.shapes.add_picture(str(charts["top_products"]), Inches(1.75), Inches(1.3), width=Inches(6.5))

    # -------------------------------------------------------------
    # SLIDE 5: Inventory & Reorder Level Health
    # -------------------------------------------------------------
    slide5 = prs.slides.add_slide(blank_layout)
    
    title_box = slide5.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(8.8), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = "Stock Health & Low Inventory Alerts"
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = PRIMARY_COLOR

    low_stock_prods = db.query(Product).filter(Product.quantity <= Product.reorder_level).all()

    # Create table for low stock items
    rows = max(len(low_stock_prods) + 1, 2)
    cols = 5
    table_shape = slide5.shapes.add_table(rows, cols, Inches(0.6), Inches(1.4), Inches(8.8), Inches(3.2))
    table = table_shape.table

    headers = ["SKU", "Product Name", "Available Stock", "Reorder Level", "Status"]
    for col_idx, header in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(10)
            paragraph.font.bold = True
            paragraph.font.color.rgb = RGBColor(255, 255, 255)

    if low_stock_prods:
        for row_idx, prod in enumerate(low_stock_prods, start=1):
            vals = [
                prod.sku,
                prod.name,
                f"{float(prod.quantity)} {prod.unit}",
                f"{float(prod.reorder_level)} {prod.unit}",
                "REORDER NEEDED"
            ]
            for col_idx, val in enumerate(vals):
                cell = table.cell(row_idx, col_idx)
                cell.text = val
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(254, 235, 235) if col_idx == 4 else LIGHT_BG
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.size = Pt(9.5)
                    paragraph.font.color.rgb = RGBColor(197, 48, 48) if col_idx == 4 else TEXT_DARK
    else:
        cell = table.cell(1, 0)
        cell.text = "All inventory levels healthy. No immediate reorders required."
        table.cell(1, 4) # trigger span effect visual
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.size = Pt(11)
            paragraph.font.color.rgb = RGBColor(56, 161, 105)

    prs.save(str(output_path))
    return output_path
