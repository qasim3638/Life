"""
PDF Price Editor - Remove ALL Scudo and Harrison Bathrooms references
Including emails, URLs, stamps - everything
"""
import fitz
import re

MARKUP = 0.80  # 80% markup

def apply_markup(price_value):
    return round(price_value * (1 + MARKUP), 2)

def process_pdf_final(input_path, output_path):
    doc = fitz.open(input_path)
    
    print(f"Processing {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # ===== STEP 1: Remove ALL Scudo and Harrison references =====
        
        texts_to_remove = [
            # Scudo variations
            "SCUDO",
            "Scudo",
            "scudo",
            "www.scudo.co.uk",
            "scudo.co.uk",
            
            # Harrison Bathrooms variations
            "Harrison Bathrooms",
            "HARRISON BATHROOMS",
            "harrison bathrooms",
            "sales@harrisonbathrooms.com",
            "@harrisonbathrooms.com",
            "harrisonbathrooms.com",
            "harrisonbathrooms",
            
            # £750 minimum
            "£750",
            "Minimum order",
            "minimum order", 
            "MIN ORDER",
            "Min order",
            "Minimum spend",
            "minimum spend",
            
            # Phone if associated with Harrison
            "0330 124 7290",
        ]
        
        # Find and redact all instances
        for search_text in texts_to_remove:
            rects = page.search_for(search_text)
            for rect in rects:
                # Expand rect slightly to ensure full coverage
                expanded = fitz.Rect(
                    rect.x0 - 2, 
                    rect.y0 - 2, 
                    rect.x1 + 2, 
                    rect.y1 + 2
                )
                page.add_redact_annot(expanded, fill=(1, 1, 1))
        
        # Apply all text removals
        page.apply_redactions()
        
        # ===== STEP 2: Replace prices with 80% markup =====
        
        # Reload page after redactions
        page = doc[page_num]
        
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
                            
                            new_full_text = text.replace(price_match.group(0), new_price_text)
                            
                            price_replacements.append({
                                'rect': bbox,
                                'new_text': new_full_text,
                                'size': span["size"],
                                'color': span.get("color", 0),
                            })
                        except ValueError:
                            continue
        
        # Apply price replacements
        for pr in price_replacements:
            rect = pr['rect']
            new_text = pr['new_text']
            font_size = pr['size']
            
            c = pr['color']
            if isinstance(c, int):
                r = ((c >> 16) & 255) / 255
                g = ((c >> 8) & 255) / 255
                b = (c & 255) / 255
                text_color = (r, g, b)
            else:
                text_color = (0, 0, 0)
            
            page.add_redact_annot(
                rect,
                text=new_text,
                fontsize=font_size,
                fill=(1, 1, 1),
                text_color=text_color,
                align=fitz.TEXT_ALIGN_LEFT
            )
        
        page.apply_redactions()
        
        print(f"Page {page_num + 1} done")
    
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"\n✓ Saved: {output_path}")

if __name__ == "__main__":
    process_pdf_final(
        "/app/scripts/original_price_list.pdf",
        "/app/scripts/Feb_Sale_Clean_80.pdf"
    )
