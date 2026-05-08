"""
PDF Price Editor - Final version with proper white coverage
"""
import fitz
import re

MARKUP = 0.80  # 80% markup

def apply_markup(price_value):
    return round(price_value * (1 + MARKUP), 2)

def process_pdf_final(input_path, output_path):
    """
    Final approach:
    1. Use redaction properly to remove old prices
    2. Insert new prices at exact positions
    """
    doc = fitz.open(input_path)
    
    print(f"Processing {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # ===== STEP 1: Collect all modifications needed =====
        
        # Texts to remove (brand names, £750)
        redact_rects = []
        
        # Find standalone Scudo
        for search_text in ["SCUDO", "Scudo"]:
            rects = page.search_for(search_text)
            for rect in rects:
                clip = fitz.Rect(rect.x0 - 100, rect.y0 - 5, rect.x1 + 100, rect.y1 + 5)
                context = page.get_text("text", clip=clip)
                if "www." not in context.lower() and "@" not in context and ".co.uk" not in context.lower():
                    redact_rects.append(('remove', rect, None))
        
        # Find Harrison Bathrooms
        for search_text in ["Harrison Bathrooms", "HARRISON BATHROOMS"]:
            rects = page.search_for(search_text)
            for rect in rects:
                clip = fitz.Rect(rect.x0 - 100, rect.y0 - 5, rect.x1 + 100, rect.y1 + 5)
                context = page.get_text("text", clip=clip)
                if "@" not in context:
                    redact_rects.append(('remove', rect, None))
        
        # Find £750 minimum
        for search_text in ["£750", "Minimum order", "minimum order", "MIN ORDER", "Min order"]:
            rects = page.search_for(search_text)
            for rect in rects:
                redact_rects.append(('remove', rect, None))
        
        # ===== STEP 2: Find and prepare price replacements =====
        
        blocks = page.get_text("dict")["blocks"]
        price_replacements = []
        
        for block in blocks:
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                        
                    bbox = fitz.Rect(span["bbox"])
                    
                    # Find price like £XX.XX
                    price_match = re.search(r'£(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
                    
                    if price_match:
                        try:
                            price_str = price_match.group(1)
                            original = float(price_str.replace(',', ''))
                            new_price = apply_markup(original)
                            
                            if new_price >= 1000:
                                new_price_text = f"£{new_price:,.2f}"
                            else:
                                new_price_text = f"£{new_price:.2f}"
                            
                            # Full replacement text
                            new_full_text = text.replace(price_match.group(0), new_price_text)
                            
                            price_replacements.append({
                                'rect': bbox,
                                'new_text': new_full_text,
                                'size': span["size"],
                                'color': span.get("color", 0),
                                'font': span.get("font", "helv")
                            })
                        except ValueError:
                            continue
        
        # ===== STEP 3: Apply redactions for removals =====
        for item in redact_rects:
            action, rect, _ = item
            if action == 'remove':
                page.add_redact_annot(rect, fill=(1, 1, 1))
        
        # Apply brand/badge redactions
        page.apply_redactions()
        
        # ===== STEP 4: Replace prices using redaction with text =====
        for pr in price_replacements:
            rect = pr['rect']
            new_text = pr['new_text']
            font_size = pr['size']
            
            # Get color tuple
            c = pr['color']
            if isinstance(c, int):
                r = ((c >> 16) & 255) / 255
                g = ((c >> 8) & 255) / 255
                b = (c & 255) / 255
                text_color = (r, g, b)
            else:
                text_color = (0, 0, 0)
            
            # Add redaction with replacement text
            page.add_redact_annot(
                rect,
                text=new_text,
                fontsize=font_size,
                fill=(1, 1, 1),  # White background
                text_color=text_color,
                align=fitz.TEXT_ALIGN_LEFT
            )
        
        # Apply price redactions
        page.apply_redactions()
        
        print(f"Page {page_num + 1}: {len(price_replacements)} prices, {len(redact_rects)} removals")
    
    # Save with optimization
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"\n✓ Saved: {output_path}")

if __name__ == "__main__":
    process_pdf_final(
        "/app/scripts/original_price_list.pdf",
        "/app/scripts/Feb_Clearance_80_Final.pdf"
    )
