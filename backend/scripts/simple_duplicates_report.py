"""
Simple Duplicate Products Report - Easy to read format
"""

import os
import sys
import json
import requests
from datetime import datetime
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


def main():
    # Production API
    API_URL = "https://tile-station-production.up.railway.app"
    EMAIL = "qasim@tilestation.co.uk"
    PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")
    
    print("Fetching products from production...")
    
    # Login
    login_response = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    token = login_response.json()['token']
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get all products
    products = requests.get(f"{API_URL}/api/products?limit=10000", headers=headers).json()
    print(f"Found {len(products)} products")
    
    # Find duplicates - SIMPLE: same SKU appearing more than once
    sku_count = defaultdict(list)
    for p in products:
        sku = (p.get('sku') or '').strip()
        if sku:
            sku_count[sku].append(p)
    
    # Only keep SKUs that appear more than once
    duplicate_skus = {sku: prods for sku, prods in sku_count.items() if len(prods) > 1}
    
    print(f"Found {len(duplicate_skus)} SKUs that appear multiple times")
    
    # Create simple PDF
    output_path = "/app/duplicate_products_simple.pdf"
    doc = SimpleDocTemplate(output_path, pagesize=A4, 
                           rightMargin=15*mm, leftMargin=15*mm,
                           topMargin=20*mm, bottomMargin=20*mm)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=18, alignment=TA_CENTER, spaceAfter=20)
    subtitle_style = ParagraphStyle('Subtitle', fontSize=12, textColor=colors.grey, spaceAfter=10)
    
    elements = []
    
    # Title
    elements.append(Paragraph("DUPLICATE PRODUCTS", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d %B %Y')}", subtitle_style))
    elements.append(Spacer(1, 10*mm))
    
    # Summary
    total_extra = sum(len(prods) - 1 for prods in duplicate_skus.values())
    summary = f"""
    <b>SUMMARY</b><br/><br/>
    • <b>{len(duplicate_skus)}</b> SKU codes appear more than once<br/>
    • <b>{total_extra}</b> extra entries that can be deleted<br/><br/>
    <b>HOW TO READ THIS REPORT:</b><br/>
    Each row shows a SKU that appears multiple times.<br/>
    You need to keep ONE and delete the extras.
    """
    elements.append(Paragraph(summary, styles['Normal']))
    elements.append(Spacer(1, 10*mm))
    
    # Simple table - one row per duplicate SKU
    table_data = [['SKU', 'Times Found', 'Product Name', 'Price']]
    
    # Sort by count (most duplicates first)
    sorted_dups = sorted(duplicate_skus.items(), key=lambda x: -len(x[1]))
    
    for sku, prods in sorted_dups:
        count = len(prods)
        name = prods[0].get('name', '')[:45]
        if len(prods[0].get('name', '')) > 45:
            name += '...'
        price = f"£{prods[0].get('price', 0):.2f}"
        
        table_data.append([sku, f"{count}x", name, price])
    
    # Create table
    col_widths = [100, 50, 280, 60]
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        
        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        
        # Alternating rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f9ff')]),
    ]))
    
    elements.append(table)
    
    # Build PDF
    doc.build(elements)
    print(f"\nReport saved: {output_path}")
    
    # Copy to frontend for download
    import shutil
    shutil.copy(output_path, "/app/frontend/public/duplicate_products_simple.pdf")
    print("Report copied to frontend for download")
    
    # Print top 20 for quick view
    print("\n" + "="*60)
    print("TOP 20 DUPLICATES (Most Repeated)")
    print("="*60)
    print(f"{'SKU':<20} {'Count':<8} {'Name':<40}")
    print("-"*60)
    for sku, prods in sorted_dups[:20]:
        name = prods[0].get('name', '')[:38]
        print(f"{sku:<20} {len(prods)}x      {name}")


if __name__ == "__main__":
    main()
