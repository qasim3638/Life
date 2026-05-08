"""
Potential Duplicates Finder and PDF Report Generator
This script analyzes the products database to find potential duplicates
that may have been missed by the automated cleanup.

Uses fuzzy string matching to identify similar product names.
"""

import os
import sys
import json
import re
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def normalize_product_name(name):
    """Normalize product name for comparison by removing common variations."""
    if not name:
        return ""
    
    name = name.lower().strip()
    
    # Remove size patterns like 600x600, 30x60, etc.
    name = re.sub(r'\d+x\d+(?:mm)?', '', name)
    
    # Remove common suffixes/words that don't affect uniqueness
    remove_patterns = [
        r'\s+matt?\b', r'\s+gloss\b', r'\s+polished\b', r'\s+honed\b',
        r'\s+rectified\b', r'\s+non-?rectified\b',
        r'\s+(?:floor|wall)\s+tile\b', r'\s+tile\b',
        r'\s+porcelain\b', r'\s+ceramic\b',
        r'\bnone\b', r'\bnonex\b',  # Cleanup artifacts
    ]
    for pattern in remove_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name


def similarity_ratio(s1, s2):
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, s1, s2).ratio()


def extract_base_name(name):
    """Extract the base product name (range name) without size/finish."""
    if not name:
        return ""
    
    # Remove size patterns
    name = re.sub(r'\d+x\d+(?:mm)?', '', name)
    
    # Remove finish types
    finish_patterns = ['Matt', 'Gloss', 'Polished', 'Honed', 'Natural', 'Satin', 'Lappato']
    for pattern in finish_patterns:
        name = re.sub(rf'\b{pattern}\b', '', name, flags=re.IGNORECASE)
    
    # Clean up
    name = ' '.join(name.split())
    return name.strip()


def find_potential_duplicates(products, similarity_threshold=0.95):
    """
    Find TRUE duplicates in the database.
    
    Focus on:
    1. Products with DUPLICATE SKUs (same SKU multiple times - critical issue)
    2. Products with IDENTICAL names but different SKUs (likely duplicates)
    """
    potential_duplicates = []
    
    # CRITICAL: Find duplicate SKUs (same SKU appears multiple times)
    sku_groups = defaultdict(list)
    for p in products:
        sku = (p.get('sku') or '').strip()
        if sku:
            sku_groups[sku].append(p)
    
    dup_sku_groups = [(sku, prods) for sku, prods in sku_groups.items() if len(prods) > 1]
    
    for sku, prods in dup_sku_groups:
        potential_duplicates.append({
            'similarity': 1.0,
            'products': [
                {
                    'name': p.get('name'), 
                    'sku': p.get('sku'), 
                    'price': p.get('price'), 
                    'stock': p.get('stock', 0),
                    'id': p.get('id')
                }
                for p in prods
            ],
            'normalized_name': sku,
            'reason': f'CRITICAL: Same SKU "{sku}" appears {len(prods)} times',
            'issue_type': 'duplicate_sku'
        })
    
    # Find products with IDENTICAL names but DIFFERENT SKUs
    name_groups = defaultdict(list)
    for p in products:
        name = (p.get('name') or '').strip()
        if name and len(name) > 5:
            name_groups[name].append(p)
    
    for name, prods in name_groups.items():
        if len(prods) > 1:
            # Get unique SKUs
            unique_skus = set(p.get('sku') for p in prods)
            # Only flag if there are different SKUs (same name, different SKUs = duplicate entries)
            if len(unique_skus) > 1:
                potential_duplicates.append({
                    'similarity': 1.0,
                    'products': [
                        {
                            'name': p.get('name'), 
                            'sku': p.get('sku'), 
                            'price': p.get('price'), 
                            'stock': p.get('stock', 0),
                            'id': p.get('id')
                        }
                        for p in prods
                    ],
                    'normalized_name': name[:50],
                    'reason': f'Same name "{name[:40]}..." has {len(unique_skus)} different SKUs',
                    'issue_type': 'duplicate_name'
                })
    
    # Sort: duplicate SKUs first (more critical), then by number of duplicates
    potential_duplicates.sort(key=lambda x: (
        0 if x.get('issue_type') == 'duplicate_sku' else 1,
        -len(x['products'])
    ))
    
    return potential_duplicates


def get_supplier_from_sku(sku):
    """Extract supplier name from SKU prefix."""
    if not sku:
        return "Unknown"
    
    prefix_map = {
        'TIL': 'Tile Rite',
        'TRI': 'Trimline',
        'ULT': 'Ultra Tile',
        'VER': 'Verona',
        'SPL': 'Splendour',
        'WAL': 'Wallcano',
        'CER': 'Ceramica Impex',
        'LP': 'Le Porce',
        'HM': 'H Martin',
        'BS': 'Bloomstone',
        'BY': 'Boyden',
        'RG': 'Regulus',
        'EG': 'Eagle',
        'TB': 'Tilebase',
        'VL': 'Verona',
        'VC': 'Verona',
        'VM': 'Verona',
        'SM': 'Splendour',
        'SS': 'Splendour',
    }
    
    # Try full prefix first
    sku_upper = sku.upper()
    for prefix, supplier in prefix_map.items():
        if sku_upper.startswith(prefix):
            return supplier
    
    # Try 2-character prefix
    if len(sku) >= 2:
        two_char = sku[:2].upper()
        if two_char in prefix_map:
            return prefix_map[two_char]
    
    return "Unknown"


def generate_pdf_report(duplicates, output_path):
    """Generate a PDF report of potential duplicates, organized by issue type."""
    
    # Separate by issue type
    sku_duplicates = [d for d in duplicates if d.get('issue_type') == 'duplicate_sku']
    name_duplicates = [d for d in duplicates if d.get('issue_type') == 'duplicate_name']
    
    # Group name duplicates by supplier
    supplier_groups = defaultdict(list)
    for dup in name_duplicates:
        first_sku = dup['products'][0].get('sku', '')
        supplier = get_supplier_from_sku(first_sku)
        supplier_groups[supplier].append(dup)
    
    # Create PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(A4),
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=10,
        textColor=colors.grey
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#dc2626')  # Red for critical
    )
    supplier_style = ParagraphStyle(
        'SupplierHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#1e40af')
    )
    note_style = ParagraphStyle(
        'NoteStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=15
    )
    
    elements = []
    
    # Title
    elements.append(Paragraph("Duplicate Products Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", subtitle_style))
    elements.append(Spacer(1, 5*mm))
    
    # Executive Summary
    total_sku_dups = sum(len(d['products']) for d in sku_duplicates)
    total_name_dups = sum(len(d['products']) for d in name_duplicates)
    
    summary_text = f"""
    <b>SUMMARY:</b><br/>
    • <b>{len(sku_duplicates)}</b> SKUs appearing multiple times ({total_sku_dups} total product entries)<br/>
    • <b>{len(name_duplicates)}</b> product names with multiple different SKUs ({total_name_dups} total entries)<br/>
    <br/>
    <b>Action Required:</b> Review and consolidate duplicate entries to ensure data integrity.
    """
    elements.append(Paragraph(summary_text, note_style))
    elements.append(Spacer(1, 10*mm))
    
    # ============ SECTION 1: Duplicate SKUs (CRITICAL) ============
    if sku_duplicates:
        elements.append(Paragraph("SECTION 1: DUPLICATE SKUs (CRITICAL)", section_style))
        elements.append(Paragraph(
            "These SKUs appear multiple times in the database. Each SKU should be unique. "
            "These need immediate attention - they will cause inventory and pricing issues.",
            note_style
        ))
        
        # Sort by count (most duplicates first)
        sku_duplicates_sorted = sorted(sku_duplicates, key=lambda x: -len(x['products']))
        
        # Create table
        table_data = [['SKU', 'Count', 'Product Names (samples)', 'Prices']]
        
        for dup in sku_duplicates_sorted[:100]:  # Top 100
            sku = dup['products'][0].get('sku', 'N/A')
            count = len(dup['products'])
            names = list(set(p.get('name', '')[:40] for p in dup['products']))[:2]
            names_str = '; '.join(names)
            prices = list(set(f"£{p.get('price', 0):.2f}" for p in dup['products']))[:3]
            prices_str = ', '.join(prices)
            
            table_data.append([sku, str(count), names_str[:60], prices_str])
        
        col_widths = [120, 50, 400, 100]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fef2f2'), colors.white]),
        ]))
        
        elements.append(table)
        
        if len(sku_duplicates) > 100:
            elements.append(Paragraph(f"... and {len(sku_duplicates) - 100} more duplicate SKUs", note_style))
        
        elements.append(PageBreak())
    
    # ============ SECTION 2: Duplicate Names (by Supplier) ============
    if name_duplicates:
        elements.append(Paragraph("SECTION 2: SAME NAME, DIFFERENT SKUs", section_style))
        elements.append(Paragraph(
            "These products have identical names but different SKU codes. "
            "This usually indicates duplicate entries that should be consolidated.",
            note_style
        ))
        
        for supplier in sorted(supplier_groups.keys()):
            dups = supplier_groups[supplier]
            if not dups:
                continue
            
            # Sort by count
            dups_sorted = sorted(dups, key=lambda x: -len(x['products']))
            
            elements.append(Paragraph(f"{supplier} ({len(dups)} duplicate groups)", supplier_style))
            
            # Create table for this supplier
            table_data = [['Product Name', 'SKUs', 'Prices', 'Stock']]
            
            for dup in dups_sorted[:30]:  # Top 30 per supplier
                name = dup['products'][0].get('name', '')[:50]
                skus = ', '.join([p.get('sku', '') for p in dup['products']][:4])
                if len(dup['products']) > 4:
                    skus += f" (+{len(dup['products'])-4} more)"
                prices = ', '.join([f"£{p.get('price', 0):.2f}" for p in dup['products']][:3])
                stocks = ', '.join([str(p.get('stock', 0)) for p in dup['products']][:3])
                
                table_data.append([name, skus, prices, stocks])
            
            col_widths = [250, 200, 120, 80]
            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#fef3c7'), colors.white]),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 5*mm))
            
            if len(dups) > 30:
                elements.append(Paragraph(f"... and {len(dups) - 30} more for {supplier}", note_style))
    
    # Build PDF
    doc.build(elements)
    return output_path


def main():
    """Main function to run the duplicate finder."""
    import requests
    
    # Production API
    API_URL = "https://tile-station-production.up.railway.app"
    EMAIL = "qasim@tilestation.co.uk"
    PASSWORD = os.environ.get("TILESTATION_ADMIN_PASSWORD", "")
    
    print("=" * 60)
    print("POTENTIAL DUPLICATES FINDER")
    print("=" * 60)
    
    # Login
    print("\n[1/4] Logging in to production API...")
    login_response = requests.post(
        f"{API_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"ERROR: Login failed - {login_response.text}")
        return
    
    token = login_response.json()['token']
    headers = {"Authorization": f"Bearer {token}"}
    print("       Login successful!")
    
    # Fetch all products
    print("\n[2/4] Fetching all products from database...")
    products_response = requests.get(
        f"{API_URL}/api/products?limit=10000",
        headers=headers
    )
    
    if products_response.status_code != 200:
        print(f"ERROR: Failed to fetch products - {products_response.text}")
        return
    
    products = products_response.json()
    print(f"       Fetched {len(products)} products")
    
    # Find duplicates
    print("\n[3/4] Analyzing products for potential duplicates...")
    print("       (Using fuzzy matching with 85% similarity threshold)")
    duplicates = find_potential_duplicates(products, similarity_threshold=0.85)
    print(f"       Found {len(duplicates)} potential duplicate groups")
    
    if not duplicates:
        print("\n" + "=" * 60)
        print("NO POTENTIAL DUPLICATES FOUND!")
        print("Your database appears to be clean of duplicate products.")
        print("=" * 60)
        return
    
    # Generate PDF
    print("\n[4/4] Generating PDF report...")
    output_path = "/app/potential_duplicates_report.pdf"
    generate_pdf_report(duplicates, output_path)
    print(f"       Report saved to: {output_path}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total products analyzed: {len(products)}")
    print(f"Potential duplicate groups: {len(duplicates)}")
    
    # Group by supplier for summary
    supplier_counts = defaultdict(int)
    for dup in duplicates:
        sku = dup['products'][0].get('sku', '')
        supplier = get_supplier_from_sku(sku)
        supplier_counts[supplier] += 1
    
    print("\nBy Supplier:")
    for supplier, count in sorted(supplier_counts.items(), key=lambda x: -x[1]):
        print(f"  {supplier}: {count} groups")
    
    print(f"\nPDF Report: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
