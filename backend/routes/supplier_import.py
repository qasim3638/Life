"""
One-time supplier product import routes for RSA Tiles and ThermoSphere.
These endpoints allow importing pre-defined product data into the database,
useful when deploying to new environments (e.g., production).
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/supplier-import", tags=["Supplier Import"])


def get_db():
    import os
    from pymongo import MongoClient
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is required")
    client = MongoClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'tile_station')]


def _build_rsa_tiles():
    """Return list of RSA Tiles product dicts."""
    raw = [
        ("TSHT612CM", "Houston Taupe 60x120cm Carving Matt", "Houston Taupe", "Houston Taupe - 60x120cm Carving Matt", "Carving Matt", "60x120", "9mm", 6.5),
        ("TSBG612CM", "Boston Grey 60x120cm Carving Matt", "Boston Grey", "Boston Grey - 60x120cm Carving Matt", "Carving Matt", "60x120", "9mm", 6.5),
        ("TSAB612P", "Alanya Brown 60x120cm Polished", "Alanya Brown", "Alanya Brown - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSAW612P", "Alanya White 60x120cm Polished", "Alanya White", "Alanya White - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSBBI612SP", "Barrisa Blanco 60x120cm Semi Polished (Sugar)", "Barrisa Blanco", "Barrisa Blanco - 60x120cm Semi Polished (Sugar)", "Semi Polished (Sugar)", "60x120", "9mm", 6.5),
        ("TSBS612SP", "Barrisa Silver 60x120cm Semi Polished (Sugar)", "Barrisa Silver", "Barrisa Silver - 60x120cm Semi Polished (Sugar)", "Semi Polished (Sugar)", "60x120", "9mm", 6.5),
        ("TSBB612SP", "Barrisa Beige 60x120cm Semi Polished (Sugar)", "Barrisa Beige", "Barrisa Beige - 60x120cm Semi Polished (Sugar)", "Semi Polished (Sugar)", "60x120", "9mm", 6.5),
        ("TSBC612P", "Bulgaria Crema 60x120cm Polished", "Bulgaria Crema", "Bulgaria Crema - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSBW612P", "Bulgaria White 60x120cm Polished", "Bulgaria White", "Bulgaria White - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSFO612P", "Fida Onyx 60x120cm Polished", "Fida Onyx", "Fida Onyx - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSIOB66P", "Italian Onyx Blue 60x60cm Polished", "Italian Onyx Blue", "Italian Onyx Blue - 60x60cm Polished", "Polished", "60x60", "9mm", 6.0),
        ("TSIOB612P", "Italian Onyx Blue 60x120cm Polished", "Italian Onyx Blue", "Italian Onyx Blue - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSIOG66P", "Italian Onyx Gold 60x60cm Polished", "Italian Onyx Gold", "Italian Onyx Gold - 60x60cm Polished", "Polished", "60x60", "9mm", 6.0),
        ("TSIOG612P", "Italian Onyx Gold 60x120cm Polished", "Italian Onyx Gold", "Italian Onyx Gold - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSMG612M", "Merino Gris 60x120cm Matt", "Merino Gris", "Merino Gris - 60x120cm Matt", "Matt", "60x120", "9mm", 6.0),
        ("TSMC36P", "Modis Calacatta 30x60cm Polished", "Modis Calacatta", "Modis Calacatta - 30x60cm Polished", "Polished", "30x60", "9mm", 6.0),
        ("TSMC36M", "Modis Calacatta 30x60cm Matt", "Modis Calacatta", "Modis Calacatta - 30x60cm Matt", "Matt", "30x60", "9mm", 6.0),
        ("TSMC66P", "Modis Callacata 60x60cm Polished", "Modis Callacata", "Modis Callacata - 60x60cm Polished", "Polished", "60x60", "9mm", 6.0),
        ("TSMC66M", "Modis Calacatta 60x60cm Matt", "Modis Calacatta", "Modis Calacatta - 60x60cm Matt", "Matt", "60x60", "9mm", 6.0),
        ("TSMC612P", "Modis Callacata 60x120cm Polished", "Modis Callacata", "Modis Callacata - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSMC612M", "Modis Calacatta 60x120cm Matt", "Modis Calacatta", "Modis Calacatta - 60x120cm Matt", "Matt", "60x120", "9mm", 6.0),
        ("TSMC612SP", "Modis Callacata 60x120cm Semi Polished (Sugar)", "Modis Callacata", "Modis Callacata - 60x120cm Semi Polished (Sugar)", "Semi Polished (Sugar)", "60x120", "9mm", 6.5),
        ("TSMM612M", "Moldova Mist 60x120cm Matt", "Moldova Mist", "Moldova Mist - 60x120cm Matt", "Matt", "60x120", "9mm", 6.0),
        ("TSOP612P", "Onyx Pearl 60x120cm Polished", "Onyx Pearl", "Onyx Pearl - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSPI612P", "Pulpis Ice 60x120cm Polished", "Pulpis Ice", "Pulpis Ice - 60x120cm Polished", "Polished", "60x120", "9mm", 6.0),
        ("TSRBS612M", "Romano Beige Stone 60x120cm Matt", "Romano Beige Stone", "Romano Beige Stone - 60x120cm Matt", "Matt", "60x120", "9mm", 6.0),
        ("TSEOG612HP", "Everest Onyx Green 60x120cm High Polished", "Everest Onyx Green", "Everest Onyx Green - 60x120cm High Polished", "High Polished", "60x120", "9mm", 6.5),
        ("TSTBS612M", "Tracia Beige Stone 60x120cm Matt", "Tracia Beige Stone", "Tracia Beige Stone - 60x120cm Matt", "Matt", "60x120", "9mm", 6.0),
    ]
    now = datetime.now(timezone.utc).isoformat()
    products = []
    for code, name, prod_name, disp_name, finish, size, thickness, price in raw:
        products.append({
            "supplier_code": code,
            "supplier": "RSA Tiles",
            "supplier_name": "RSA Tiles",
            "name": name,
            "product_name": prod_name,
            "display_name": disp_name,
            "original_supplier_name": name,
            "display_code": code,
            "material": "Porcelain",
            "finish": finish,
            "size": size,
            "thickness": thickness,
            "category": "",
            "images": [],
            "in_products_db": False,
            "show_on_website": False,
            "stock_status": "In Stock",
            "stock_sqm": 0,
            "pieces_per_sqm": 0.0,
            "boxes_per_pallet": 0,
            "pallet_price": 0.0,
            "cost_price": price,
            "cost_m2": price,
            "price": price,
            "trade_price": price,
            "room_lot_price": price,
            "visibility": "online",
            "always_in_stock": False,
            "extra_data": {"category": "Wall & Floor Tiles", "source": "RSA Tiles Spreadsheet Import"},
            "attributes": {"size": size, "finish": finish.lower(), "color": None, "material": "Porcelain", "original_name": name},
            "updated_at": now,
            "synced_at": now,
        })
    return products


def _build_thermosphere():
    """Return list of ThermoSphere product dicts."""
    VAT_RATE = 0.20
    DISCOUNT = 0.60
    now = datetime.now(timezone.utc).isoformat()
    products = []

    def add(sku, name, category, ex_vat_price, specs=None):
        ex_vat = float(str(ex_vat_price).replace(',', ''))
        inc_vat = round(ex_vat * (1 + VAT_RATE), 2)
        cost = round(ex_vat * (1 - DISCOUNT), 2)
        products.append({
            "supplier_code": sku.strip(),
            "supplier": "ThermoSphere",
            "supplier_name": "ThermoSphere",
            "name": name.strip(),
            "display_name": name.strip(),
            "product_name": name.strip(),
            "original_supplier_name": name.strip(),
            "material": "Underfloor Heating",
            "category": category,
            "finish": "",
            "size": specs.get("size", "") if specs else "",
            "thickness": "",
            "cost_price": cost,
            "cost_m2": cost,
            "cost_each": cost,
            "trade_price": cost,
            "price": inc_vat,
            "retail_price": inc_vat,
            "list_price": inc_vat,
            "size_unit": "each",
            "stock_status": "In Stock",
            "stock_quantity": 0,
            "stock_m2": 0,
            "images": [],
            "extra_data": {
                "ex_vat_list_price": ex_vat,
                "inc_vat_list_price": inc_vat,
                "discount_percent": 60,
                "source": "ThermoSphere Brochure PDF Import",
                **(specs or {})
            },
            "in_products_db": False,
            "show_on_website": False,
            "display_code": sku.strip(),
            "visibility": "online",
            "always_in_stock": False,
            "product_group": "underfloor-heating",
            "updated_at": now,
            "synced_at": now,
        })

    # Mesh 100W/m²
    for sku, area, watts, ohms, price in [
        ("TSM-100-0100", "1.0", 100, 530, 68.20), ("TSM-100-0150", "1.5", 150, 353, 96.00),
        ("TSM-100-0200", "2.0", 200, 265, 124.00), ("TSM-100-0250", "2.5", 250, 212, 155.00),
        ("TSM-100-0300", "3.0", 300, 176, 186.00), ("TSM-100-0350", "3.5", 350, 151, 219.00),
        ("TSM-100-0400", "4.0", 400, 132, 248.00), ("TSM-100-0500", "5.0", 500, 106, 310.00),
        ("TSM-100-0600", "6.0", 600, 88, 372.00), ("TSM-100-0800", "8.0", 800, 66, 496.00),
        ("TSM-100-1000", "10.0", 1000, 53, 620.00), ("TSM-100-1200", "12.0", 1200, 44, 744.00),
    ]:
        add(sku, f"Self-adhesive Mesh 100W ({area}m2)", "Mesh 100W/m2", price,
            {"area_m2": area, "output_watts": watts, "resistance_ohms": ohms, "wattage": "100W/m2"})

    # Mesh 150W/m²
    for sku, area, watts, ohms, price in [
        ("TSM-150-0100", "1.0", 150, 353, 81.00), ("TSM-150-0150", "1.5", 225, 235, 104.50),
        ("TSM-150-0200", "2.0", 300, 176, 126.00), ("TSM-150-0250", "2.5", 375, 141, 157.00),
        ("TSM-150-0300", "3.0", 450, 118, 188.00), ("TSM-150-0350", "3.5", 525, 101, 219.00),
        ("TSM-150-0400", "4.0", 600, 88, 252.00), ("TSM-150-0450", "4.5", 675, 78, 283.00),
        ("TSM-150-0500", "5.0", 750, 71, 314.00), ("TSM-150-0600", "6.0", 900, 59, 375.00),
        ("TSM-150-0700", "7.0", 1050, 50, 438.00), ("TSM-150-0800", "8.0", 1200, 44, 500.00),
        ("TSM-150-0900", "9.0", 1350, 39, 562.00), ("TSM-150-1000", "10.0", 1500, 35, 626.00),
        ("TSM-150-1200", "12.0", 1800, 29, 749.00), ("TSM-150-1400", "14.0", 2100, 25, 873.00),
        ("TSM-150-1600", "16.0", 2400, 22, 998.00), ("TSM-150-2000", "20.0", 3000, 18, 1240.00),
        ("TSM-150-2400", "24.0", 3600, 15, 1488.00),
    ]:
        add(sku, f"Self-adhesive Mesh 150W ({area}m2)", "Mesh 150W/m2", price,
            {"area_m2": area, "output_watts": watts, "resistance_ohms": ohms, "wattage": "150W/m2"})

    # Mesh 200W/m²
    for sku, area, watts, ohms, price in [
        ("TSM-200-0100", "1.0", 200, 265, 91.00), ("TSM-200-0150", "1.5", 300, 176, 117.50),
        ("TSM-200-0200", "2.0", 400, 132, 138.00), ("TSM-200-0250", "2.5", 500, 106, 167.50),
        ("TSM-200-0300", "3.0", 600, 88, 201.00), ("TSM-200-0350", "3.5", 700, 76, 234.50),
        ("TSM-200-0400", "4.0", 800, 66, 268.00), ("TSM-200-0450", "4.5", 900, 58, 301.50),
        ("TSM-200-0500", "5.0", 1000, 53, 335.00), ("TSM-200-0600", "6.0", 1200, 44, 402.00),
        ("TSM-200-0700", "7.0", 1400, 38, 469.00), ("TSM-200-0800", "8.0", 1600, 33, 536.00),
        ("TSM-200-0900", "9.0", 1800, 29, 603.00), ("TSM-200-1000", "10.0", 2000, 26, 670.00),
        ("TSM-200-1200", "12.0", 2400, 22, 804.00),
    ]:
        add(sku, f"Self-adhesive Mesh 200W ({area}m2)", "Mesh 200W/m2", price,
            {"area_m2": area, "output_watts": watts, "resistance_ohms": ohms, "wattage": "200W/m2"})

    # Ultimate Heating Cable 130W/m²
    for sku, length, watts, ohms, price in [
        ("HDMC-012-0150J", 12, 150, 352, 77.18), ("HDMC-018-0225J", 18, 225, 235, 114.66),
        ("HDMC-025-0300J", 25, 300, 176, 153.25), ("HDMC-031-0375J", 31, 375, 141, 190.73),
        ("HDMC-037-0450J", 37, 450, 117, 229.32), ("HDMC-042-0525J", 42, 525, 100, 257.99),
        ("HDMC-050-0600J", 50, 600, 88, 305.39), ("HDMC-055-0675J", 55, 675, 78, 337.37),
        ("HDMC-061-0750J", 61, 750, 70, 381.47), ("HDMC-075-0900J", 75, 900, 58, 457.54),
        ("HDMC-090-1080J", 90, 1080, 48, 550.15), ("HDMC-100-1200J", 100, 1200, 44, 610.79),
        ("HDMC-125-1500J", 125, 1500, 35, 762.93), ("HDMC-150-1800J", 150, 1800, 29, 916.18),
        ("HDMC-175-2100J", 175, 2100, 25, 1069.43), ("HDMC-200-2400J", 200, 2400, 22, 1221.57),
    ]:
        add(sku, f"Ultimate Heating Cable ({length}lm) {watts}W", "Ultimate Heating Cable 130W/m2", price,
            {"cable_length_m": length, "output_watts": watts, "resistance_ohms": ohms, "wattage": "130W/m2"})

    # Ultimate Low Wattage Cable
    for sku, length, watts, ohms, price in [
        ("HDMC-5-012", 12, 68, 778, 77.18), ("HDMC-5-018", 18, 102, 519, 114.66),
        ("HDMC-5-025", 25, 128, 415, 153.25), ("HDMC-5-031", 31, 162, 328, 190.73),
        ("HDMC-5-037", 37, 196, 271, 229.32), ("HDMC-5-050", 50, 264, 201, 305.39),
        ("HDMC-5-061", 61, 323, 164, 381.47), ("HDMC-5-075", 75, 391, 135, 457.54),
        ("HDMC-5-100", 100, 527, 100, 610.79), ("HDMC-5-125", 125, 655, 81, 762.93),
        ("HDMC-5-150", 150, 782, 68, 916.18), ("HDMC-5-200", 200, 1046, 51, 1221.57),
    ]:
        add(sku, f"Ultimate Low Wattage Heating Cable ({length}lm) {watts}W", "Ultimate Low Wattage Cable", price,
            {"cable_length_m": length, "output_watts": watts, "resistance_ohms": ohms, "wattage": "57W/85W per m2"})

    # Membrane Mat
    for sku, name, price in [
        ("HDM-001", "Decoupling Membrane Mat (1m2)", 25.65),
        ("HDM-005", "Decoupling Membrane Mat (5m2)", 126.69),
        ("HDM-015", "Decoupling Membrane Mat (15m2)", 370.80),
        ("HDM-SA-001", "Self-adhesive Decoupling Membrane Mat (1m2)", 32.96),
        ("HDM-SA-015", "Self-adhesive Decoupling Membrane Mat (15m2)", 478.95),
    ]:
        add(sku, name, "Membrane Mat", price)

    # Foil 140W/m²
    for sku, area, watts, ohms, price in [
        ("WCVF-140-0100", "1.0", 140, 337, 165.17), ("WCVF-140-0150", "1.5", 210, 251, 211.37),
        ("WCVF-140-0200", "2.0", 280, 188, 248.33), ("WCVF-140-0250", "2.5", 350, 151, 276.05),
        ("WCVF-140-0300", "3.0", 420, 126, 321.09), ("WCVF-140-0400", "4.0", 560, 94, 399.63),
        ("WCVF-140-0500", "5.0", 700, 75, 490.88), ("WCVF-140-0600", "6.0", 840, 63, 548.63),
        ("WCVF-140-0700", "7.0", 980, 53, 617.93), ("WCVF-140-0800", "8.0", 1120, 47, 622.55),
        ("WCVF-140-0900", "9.0", 1260, 41, 723.03), ("WCVF-140-1000", "10.0", 1400, 37, 753.06),
        ("WCVF-140-1200", "12.0", 1680, 31, 803.88),
    ]:
        add(sku, f"Heating Foil 140W ({area}m2)", "Foil 140W/m2", price,
            {"area_m2": area, "output_watts": watts, "resistance_ohms": ohms, "wattage": "140W/m2"})

    # Underlay & Overlay
    for sku, name, price in [
        ("WCVF-CUSHU-01", "Cushioning Underlay (single)", 10.40),
        ("WCVF-CUSHU", "Cushioning Underlay (pack of 10)", 84.89),
        ("WCVF-HFCO-01", "Cushioning Overlay 1m2", 19.06),
        ("WCVF-HFCO-10", "Cushioning Overlay 10m2", 135.14),
    ]:
        add(sku, name, "Underlay & Overlay", price)

    # Foil Kit 140W/m²
    for sku, area, watts, ohms, price in [
        ("HFK-140-0100", "1.0", 140, 337, 86.94), ("HFK-140-0150", "1.5", 210, 251, 130.41),
        ("HFK-140-0200", "2.0", 280, 188, 173.88), ("HFK-140-0250", "2.5", 350, 151, 217.35),
        ("HFK-140-0300", "3.0", 420, 126, 260.82), ("HFK-140-0400", "4.0", 560, 94, 347.76),
        ("HFK-140-0500", "5.0", 700, 75, 434.70), ("HFK-140-0600", "6.0", 840, 63, 521.64),
        ("HFK-140-0700", "7.0", 980, 53, 608.58), ("HFK-140-0800", "8.0", 1120, 47, 695.52),
        ("HFK-140-0900", "9.0", 1260, 41, 782.46), ("HFK-140-1000", "10.0", 1400, 37, 869.40),
        ("HFK-140-1200", "12.0", 1680, 31, 1043.28),
    ]:
        add(sku, f"Foil Kit 140W ({area}m2)", "Foil Kit 140W/m2", price,
            {"area_m2": area, "output_watts": watts, "resistance_ohms": ohms, "wattage": "140W/m2"})

    # Overlay Board
    add("WCVF-HDFO", "HDF Overlay Board (2.88m2)", "Overlay Board", 183.65, {"size": "1.2 x 0.6 x 7mm"})
    add("WCVF-CBHO", "Cement Overlay Board (0.72m2)", "Overlay Board", 86.05, {"size": "1.2 x 0.6 x 12mm"})

    # Screed Cable
    for sku, watts, length, ohms, price in [
        ("SC-011-0200", 200, 11.0, 264, 86.94), ("SC-016-0300", 300, 16.5, 176, 98.12),
        ("SC-022-0400", 400, 22.0, 132, 124.58), ("SC-027-0500", 500, 27.5, 105, 148.84),
        ("SC-033-0600", 600, 33.0, 88, 177.50), ("SC-039-0700", 700, 39.0, 75, 203.96),
        ("SC-045-0850", 850, 45.0, 62, 224.91), ("SC-055-1000", 1000, 55.0, 52, 262.40),
        ("SC-069-1250", 1250, 69.0, 42, 334.06), ("SC-076-1375", 1375, 76.0, 38, 391.39),
        ("SC-094-1700", 1700, 94.0, 31, 450.92), ("SC-116-2100", 2100, 116.0, 25, 487.31),
        ("SC-144-2600", 2600, 144.0, 20, 658.19), ("SC-183-3300", 3300, 183.0, 16, 943.74),
    ]:
        add(sku, f"Screed Cable {watts}W ({length}m)", "Screed Cable", price,
            {"cable_length_m": length, "output_watts": watts, "resistance_ohms": ohms})

    # Screed Cable Accessories
    add("SC-STA-0600", "Screed Cable Staples (pk 600)", "Screed Cable Accessories", 133.40)
    add("SC-STG", "Screed Cable Staple Gun", "Screed Cable Accessories", 611.89)
    add("SC-GFP-025", "Screed Cable Fixing Profile (25m)", "Screed Cable Accessories", 84.89)
    add("PIF-50-050", "Perimeter Insulation Foam (50m)", "Screed Cable Accessories", 80.30)

    # Cable Kit
    for sku, area, length, watts, ohms, price in [
        ("TCK-014-0185", "1.0", 14, 185, 286, 199.50), ("TCK-022-0300", "2.0", 22, 300, 176, 250.95),
        ("TCK-033-0450", "3.0", 33, 450, 118, 303.45), ("TCK-044-0600", "4.0", 44, 600, 88, 376.95),
        ("TCK-055-0750", "5.0", 55, 750, 71, 450.45), ("TCK-066-0900", "6.0", 66, 900, 59, 565.95),
        ("TCK-086-1200", "8.0", 86, 1200, 44, 660.45),
    ]:
        add(sku, f"Cable Kit ({area}m2) {watts}W", "Cable Kit", price,
            {"area_m2": area, "cable_length_m": length, "output_watts": watts, "resistance_ohms": ohms})

    return products


@router.post("/import-rsa-tiles")
def import_rsa_tiles():
    """Import RSA Tiles products into the database."""
    try:
        db = get_db()
        products = _build_rsa_tiles()
        inserted = 0
        updated = 0
        for p in products:
            result = db.supplier_products.update_one(
                {"supplier_code": p["supplier_code"], "supplier": "RSA Tiles"},
                {"$set": p},
                upsert=True
            )
            if result.upserted_id:
                inserted += 1
            elif result.modified_count > 0:
                updated += 1
        total = db.supplier_products.count_documents({"supplier": "RSA Tiles"})
        return {"success": True, "supplier": "RSA Tiles", "inserted": inserted, "updated": updated, "total": total}
    except Exception as e:
        logger.error(f"RSA Tiles import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-thermosphere")
def import_thermosphere():
    """Import ThermoSphere products into the database."""
    try:
        db = get_db()
        products = _build_thermosphere()
        inserted = 0
        updated = 0
        for p in products:
            result = db.supplier_products.update_one(
                {"supplier_code": p["supplier_code"], "supplier": "ThermoSphere"},
                {"$set": p},
                upsert=True
            )
            if result.upserted_id:
                inserted += 1
            elif result.modified_count > 0:
                updated += 1
        total = db.supplier_products.count_documents({"supplier": "ThermoSphere"})
        return {"success": True, "supplier": "ThermoSphere", "inserted": inserted, "updated": updated, "total": total}
    except Exception as e:
        logger.error(f"ThermoSphere import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-all")
def import_all_new_suppliers():
    """Import all new supplier products (RSA Tiles + ThermoSphere) in one call."""
    results = {}
    results["rsa_tiles"] = import_rsa_tiles()
    results["thermosphere"] = import_thermosphere()
    return {"success": True, "results": results}
