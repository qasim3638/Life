"""
Barcode Scanner Support - Scan products using SKU/barcode
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from config import get_db

router = APIRouter(prefix="/barcode", tags=["Barcode Scanner"])


@router.get("/lookup/{code}")
async def lookup_barcode(
    code: str,
    showroom_id: Optional[str] = None
):
    """
    Look up a product by barcode/SKU/supplier code.
    Searches in order: barcode → SKU → supplier_code → original_supplier_code
    """
    db = get_db()
    
    code = code.strip().upper()
    
    # Search fields in priority order
    search_fields = [
        {"barcode": code},
        {"sku": code},
        {"sku": code.lower()},  # Try lowercase
        {"supplier_code": code},
        {"original_supplier_code": code}
    ]
    
    product = None
    matched_field = None
    
    # Try products collection first
    for query in search_fields:
        product = await db.products.find_one(query, {"_id": 0})
        if product:
            matched_field = list(query.keys())[0]
            break
    
    # If not found, try supplier_products
    if not product:
        for query in search_fields:
            product = await db.supplier_products.find_one(query, {"_id": 0})
            if product:
                matched_field = list(query.keys())[0]
                break
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Product not found",
                "code": code,
                "suggestion": "Check if the barcode is correct or add the product to the system"
            }
        )
    
    # Get showroom-specific stock if requested
    if showroom_id and product.get("showroom_stock"):
        product["showroom_specific_stock"] = product["showroom_stock"].get(showroom_id, 0)
    
    return {
        "product": product,
        "matched_by": matched_field,
        "scanned_code": code,
        "lookup_time": datetime.now(timezone.utc).isoformat()
    }


@router.get("/search")
async def search_by_barcode(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50)
):
    """
    Search products by partial barcode/SKU match.
    Useful for autocomplete while typing barcode.
    """
    db = get_db()
    
    q = q.strip()
    
    # Search pattern - starts with or contains
    pattern = {"$regex": f"^{q}", "$options": "i"}
    
    query = {
        "$or": [
            {"barcode": pattern},
            {"sku": pattern},
            {"supplier_code": pattern}
        ]
    }
    
    products = await db.products.find(query, {"_id": 0}).limit(limit).to_list(limit)
    
    # Also search supplier_products
    supplier_products = await db.supplier_products.find(query, {"_id": 0}).limit(limit).to_list(limit)
    
    # Merge results (avoid duplicates)
    seen_ids = {p["id"] for p in products}
    for sp in supplier_products:
        if sp["id"] not in seen_ids:
            products.append(sp)
    
    return {
        "results": products[:limit],
        "query": q,
        "count": len(products[:limit])
    }


@router.post("/assign/{product_id}")
async def assign_barcode(
    product_id: str,
    barcode: str
):
    """Assign a barcode to a product"""
    db = get_db()
    
    barcode = barcode.strip().upper()
    
    # Check if barcode is already assigned
    existing = await db.products.find_one({"barcode": barcode})
    if not existing:
        existing = await db.supplier_products.find_one({"barcode": barcode})
    
    if existing and existing.get("id") != product_id:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Barcode already assigned to another product",
                "existing_product": existing.get("name"),
                "existing_sku": existing.get("sku")
            }
        )
    
    # Try to update in products
    result = await db.products.update_one(
        {"id": product_id},
        {"$set": {"barcode": barcode, "updated_at": datetime.now(timezone.utc)}}
    )
    
    if result.matched_count == 0:
        # Try supplier_products
        result = await db.supplier_products.update_one(
            {"id": product_id},
            {"$set": {"barcode": barcode, "updated_at": datetime.now(timezone.utc)}}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {
        "message": "Barcode assigned",
        "product_id": product_id,
        "barcode": barcode
    }


@router.get("/validate/{barcode}")
async def validate_barcode_format(barcode: str):
    """
    Validate barcode format.
    Supports: EAN-13, EAN-8, UPC-A, Code 128
    """
    barcode = barcode.strip()
    
    validations = {
        "is_numeric": barcode.isdigit(),
        "length": len(barcode),
        "format": None,
        "valid": False
    }
    
    if barcode.isdigit():
        if len(barcode) == 13:
            validations["format"] = "EAN-13"
            validations["valid"] = validate_ean13_checksum(barcode)
        elif len(barcode) == 12:
            validations["format"] = "UPC-A"
            validations["valid"] = validate_upc_checksum(barcode)
        elif len(barcode) == 8:
            validations["format"] = "EAN-8"
            validations["valid"] = validate_ean8_checksum(barcode)
        else:
            validations["format"] = "Custom numeric"
            validations["valid"] = True
    else:
        # Alphanumeric - could be Code 128 or custom SKU
        if len(barcode) >= 3 and len(barcode) <= 50:
            validations["format"] = "Code 128 / Custom SKU"
            validations["valid"] = True
    
    return validations


def validate_ean13_checksum(barcode: str) -> bool:
    """Validate EAN-13 checksum"""
    if len(barcode) != 13 or not barcode.isdigit():
        return False
    
    total = 0
    for i, digit in enumerate(barcode[:12]):
        if i % 2 == 0:
            total += int(digit)
        else:
            total += int(digit) * 3
    
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(barcode[12])


def validate_ean8_checksum(barcode: str) -> bool:
    """Validate EAN-8 checksum"""
    if len(barcode) != 8 or not barcode.isdigit():
        return False
    
    total = 0
    for i, digit in enumerate(barcode[:7]):
        if i % 2 == 0:
            total += int(digit) * 3
        else:
            total += int(digit)
    
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(barcode[7])


def validate_upc_checksum(barcode: str) -> bool:
    """Validate UPC-A checksum"""
    if len(barcode) != 12 or not barcode.isdigit():
        return False
    
    total = 0
    for i, digit in enumerate(barcode[:11]):
        if i % 2 == 0:
            total += int(digit) * 3
        else:
            total += int(digit)
    
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(barcode[11])
