"""
Clean PDF editing - preserve layout, only modify specific elements
"""
import fitz
import re

MARKUP = 0.80  # 80% markup

def apply_markup(price_value):
    """Apply 80% markup to a price"""
    return round(price_value * (1 + MARKUP), 2)

def process_pdf_clean(input_path, output_path):
    """
    Process PDF by:
    1. Finding price text and replacing with marked-up prices IN PLACE
    2. Removing specific brand text
    3. NOT disrupting layout
    """
    doc = fitz.open(input_path)
    
    print(f"Processing {len(doc)} pages...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # ===== STEP 1: Remove brand names using redaction (white out) =====
        # Only remove standalone brand mentions, not in URLs/emails
        
        # Find "Scudo" as standalone word (not in URLs)
        for text in ["SCUDO", "Scudo"]:
            instances = page.search_for(text)
            for rect in instances:
                # Get surrounding text to check if it's in a URL
                # Expand rect slightly to get context
                expanded = fitz.Rect(rect.x0 - 50, rect.y0, rect.x1 + 50, rect.y1)
                surrounding_text = page.get_text("text", clip=expanded)
                
                # Skip if it's part of a URL or email
                if "www." in surrounding_text.lower() or "@" in surrounding_text or ".co.uk" in surrounding_text.lower():
                    continue
                    
                # Redact with white
                page.add_redact_annot(rect, fill=(1, 1, 1))
        
        # Find "Harrison Bathrooms" standalone
        for text in ["Harrison Bathrooms", "HARRISON BATHROOMS"]:
            instances = page.search_for(text)
            for rect in instances:
                expanded = fitz.Rect(rect.x0 - 50, rect.y0, rect.x1 + 50, rect.y1)
                surrounding_text = page.get_text("text", clip=expanded)
                
                # Skip if it's part of email
                if "@" in surrounding_text:
                    continue
                
                page.add_redact_annot(rect, fill=(1, 1, 1))
        
        # Remove £750 minimum spend mentions
        for text in ["£750", "Minimum order", "minimum order", "MIN ORDER", "Min order", 
                     "Minimum spend", "minimum spend"]:
            instances = page.search_for(text)
            for rect in instances:
                page.add_redact_annot(rect, fill=(1, 1, 1))
        
        # Apply redactions for brand/badge removal
        page.apply_redactions()
        
        # ===== STEP 2: Update prices using text replacement (not redaction) =====
        # This preserves layout better
        
        # Reload page content after redactions
        page = doc[page_num]
        
        # Get all text with detailed position info
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        
        for block in blocks:
            if "lines" not in block:
                continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    original_text = span["text"]
                    bbox = fitz.Rect(span["bbox"])
                    
                    # Find prices like £XX.XX or £X,XXX.XX
                    price_pattern = r'£(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
                    
                    if re.search(price_pattern, original_text):
                        new_text = original_text
                        
                        for match in re.finditer(price_pattern, original_text):
                            try:
                                price_str = match.group(1)
                                original_price = float(price_str.replace(',', ''))
                                new_price = apply_markup(original_price)
                                
                                # Format price
                                if new_price >= 1000:
                                    formatted = f"£{new_price:,.2f}"
                                else:
                                    formatted = f"£{new_price:.2f}"
                                
                                # Replace in text
                                old_full = match.group(0)  # e.g., "£47.00"
                                new_text = new_text.replace(old_full, formatted, 1)
                            except ValueError:
                                continue
                        
                        if new_text != original_text:
                            # Get font properties
                            font_size = span["size"]
                            font_name = span["font"]
                            
                            # Convert color
                            c = span.get("color", 0)
                            if isinstance(c, int):
                                r = ((c >> 16) & 255) / 255
                                g = ((c >> 8) & 255) / 255
                                b = (c & 255) / 255
                                color = (r, g, b)
                            else:
                                color = (0, 0, 0)
                            
                            # Use add_redact_annot with text parameter to replace
                            page.add_redact_annot(
                                bbox,
                                text=new_text,
                                fontsize=font_size,
                                fill=(1, 1, 1),
                                text_color=color
                            )
        
        # Apply price redactions (with new text)
        page.apply_redactions()
        
        print(f"Page {page_num + 1} done")
    
    # Save
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    print(f"\nSaved: {output_path}")

if __name__ == "__main__":
    process_pdf_clean(
        "/app/scripts/original_price_list.pdf",
        "/app/scripts/February_Clearance_Final.pdf"
    )
