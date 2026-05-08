"""
PDF Price Editor - Overlay approach
Keeps original layout, overlays new prices on top
"""
import fitz
import re

MARKUP = 0.80  # 80% markup

def apply_markup(price_value):
    return round(price_value * (1 + MARKUP), 2)

def process_pdf_overlay(input_path, output_path):
    """
    Use overlay approach:
    1. Cover old prices with white rectangles
    2. Draw new prices on top
    """
    doc = fitz.open(input_path)
    
    print(f"Processing {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # ===== Remove brand names and £750 badge =====
        texts_to_remove = []
        
        # Find standalone Scudo (not in URLs/emails)
        for search_text in ["SCUDO", "Scudo"]:
            rects = page.search_for(search_text)
            for rect in rects:
                # Check context
                clip = fitz.Rect(rect.x0 - 100, rect.y0 - 5, rect.x1 + 100, rect.y1 + 5)
                context = page.get_text("text", clip=clip)
                if "www." not in context.lower() and "@" not in context and ".co.uk" not in context.lower():
                    texts_to_remove.append(rect)
        
        # Find Harrison Bathrooms (not in emails)
        for search_text in ["Harrison Bathrooms", "HARRISON BATHROOMS"]:
            rects = page.search_for(search_text)
            for rect in rects:
                clip = fitz.Rect(rect.x0 - 100, rect.y0 - 5, rect.x1 + 100, rect.y1 + 5)
                context = page.get_text("text", clip=clip)
                if "@" not in context:
                    texts_to_remove.append(rect)
        
        # Find £750 minimum mentions
        for search_text in ["£750", "Minimum order", "minimum order", "MIN ORDER"]:
            rects = page.search_for(search_text)
            texts_to_remove.extend(rects)
        
        # White out unwanted text
        shape = page.new_shape()
        for rect in texts_to_remove:
            # Expand rect slightly
            expanded = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
            shape.draw_rect(expanded)
        shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
        shape.commit()
        
        # ===== Process prices =====
        # Get text blocks
        blocks = page.get_text("dict")["blocks"]
        
        price_updates = []
        
        for block in blocks:
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    bbox = fitz.Rect(span["bbox"])
                    
                    # Find price pattern
                    price_match = re.search(r'£(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text)
                    
                    if price_match:
                        try:
                            price_str = price_match.group(1)
                            original = float(price_str.replace(',', ''))
                            new_price = apply_markup(original)
                            
                            if new_price >= 1000:
                                new_text = f"£{new_price:,.2f}"
                            else:
                                new_text = f"£{new_price:.2f}"
                            
                            # Store for later processing
                            price_updates.append({
                                'rect': bbox,
                                'old_text': text,
                                'new_text': text.replace(price_match.group(0), new_text),
                                'size': span["size"],
                                'font': span["font"],
                                'color': span.get("color", 0)
                            })
                        except ValueError:
                            continue
        
        # Apply price updates using overlay
        for update in price_updates:
            rect = update['rect']
            
            # Cover old text with white
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
            shape.commit()
            
            # Get color
            c = update['color']
            if isinstance(c, int):
                r = ((c >> 16) & 255) / 255
                g = ((c >> 8) & 255) / 255
                b = (c & 255) / 255
                color = (r, g, b)
            else:
                color = (0, 0, 0)
            
            # Insert new text at same position
            # Adjust y position slightly for baseline
            insert_point = fitz.Point(rect.x0, rect.y1 - 2)
            
            page.insert_text(
                insert_point,
                update['new_text'],
                fontsize=update['size'],
                color=color
            )
        
        print(f"Page {page_num + 1}: {len(price_updates)} prices updated")
    
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"\nSaved: {output_path}")

if __name__ == "__main__":
    process_pdf_overlay(
        "/app/scripts/original_price_list.pdf",
        "/app/scripts/February_Sale_80_Markup.pdf"
    )
