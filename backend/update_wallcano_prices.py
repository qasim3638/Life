#!/usr/bin/env python3
"""
Update Wallcano product prices from February 2025 UK Price List.
Prices extracted from the PDF video provided by user.
"""

from pymongo import MongoClient
from datetime import datetime, timezone

# Price data extracted from Wallcano UK Price List February 2025
# Format: SKU -> {'room_lot': price_per_sqm, 'pallet': pallet_price_per_sqm}
# Prices are in GBP (£)

WALLCANO_PRICES = {
    # Feature Tiles 30x45 CM
    "FEA3045A1": {"room_lot": 12.99, "pallet": 9.99},  # HARD ROCK BLACK & WHITE
    "FEA3045A2": {"room_lot": 12.99, "pallet": 9.99},  # HARD ROCK WHITE
    "FEA3045A3": {"room_lot": 12.99, "pallet": 9.99},  # MOONSTONE GRIS
    "FEA3045A4": {"room_lot": 12.99, "pallet": 9.99},  # MOONSTONE COTTA
    "FEA3045A5": {"room_lot": 12.99, "pallet": 9.99},  # MOONSTONE GREY
    "FEA3045A6": {"room_lot": 12.99, "pallet": 9.99},  # MOONSTONE WHITE
    
    # Feature Tiles 30x60 CM
    "FEA3060A1": {"room_lot": 13.49, "pallet": 10.49},  # BRICKSTONE GREY
    "FEA3060A2": {"room_lot": 13.49, "pallet": 10.49},  # BRICKSTONE NATURAL
    "FEA3060A3": {"room_lot": 13.49, "pallet": 10.49},  # JAISALMER BEIGE
    "FEA3060A4": {"room_lot": 13.49, "pallet": 10.49},  # STONEAGE DARK GREY
    "FEA3060A5": {"room_lot": 13.49, "pallet": 10.49},  # STONEAGE LIGHT GREY
    "FEA3060A6": {"room_lot": 13.49, "pallet": 10.49},  # KANDLA GREY
    "FEA3060A7": {"room_lot": 13.49, "pallet": 10.49},  # SANDSTONE NATURAL
    "FEA3060A8": {"room_lot": 13.49, "pallet": 10.49},  # SPLITFACE PINK
    "FEA3060A9": {"room_lot": 13.49, "pallet": 10.49},  # SPLITFACE MINT
    
    # Polished 30x60 CM
    "POL3060A1": {"room_lot": 14.99, "pallet": 11.99},  # ETERNAL SATVARIO
    "POL3060A3": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA BIANCO
    "POL3060A4": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA BROWN
    "POL3060A5": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA GRISS
    "POL3060A6": {"room_lot": 14.99, "pallet": 11.99},  # ONYX WHITE
    
    # Matt 30x60 CM
    "MAT3060A1": {"room_lot": 14.99, "pallet": 11.99},  # ETERNAL SATVARIO
    
    # Polished 60x60 CM
    "POL6060A2": {"room_lot": 14.99, "pallet": 11.99},  # ETERNAL SATVARIO
    "POL6060A3": {"room_lot": 14.99, "pallet": 11.99},  # ALLURE GREY
    "POL6060A4": {"room_lot": 14.99, "pallet": 11.99},  # ONDULATO GREY
    "POL6060A5": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA BIANCO
    "POL6060A6": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA GRISS
    "POL6060A7": {"room_lot": 14.99, "pallet": 11.99},  # SPECTRA BROWN
    "POL6060A8": {"room_lot": 14.99, "pallet": 11.99},  # RUBY ONYX SKY
    "POL6060A10": {"room_lot": 14.99, "pallet": 11.99}, # SPLENDOR GOLD
    "POL6060A11": {"room_lot": 14.99, "pallet": 11.99}, # ONYX WHITE
    
    # Matt 60x60 CM
    "MAT6060A1": {"room_lot": 14.99, "pallet": 11.99},  # ETERNAL SATUARIO
    "MAT6060A2": {"room_lot": 14.99, "pallet": 11.99},  # SPANISH PUNCH
    "MAT6060A3": {"room_lot": 14.99, "pallet": 11.99},  # RUBY ONYX SKY
    "MAT6060A4": {"room_lot": 14.99, "pallet": 11.99},  # SPELNDOR GOLD
    
    # Carving 60x60 CM
    "CRV6060A1": {"room_lot": 14.99, "pallet": 11.99},  # VEINS GREY
    "CRV6060A2": {"room_lot": 14.99, "pallet": 11.99},  # DAPPLED GREY
    
    # Polished 60x120 CM - Standard
    "POL60120A3": {"room_lot": 14.99, "pallet": 11.99}, # ALLURE GREY
    "POL60120A4": {"room_lot": 14.99, "pallet": 11.99}, # RUBY ONYX SKY
    "POL60120A5": {"room_lot": 14.99, "pallet": 11.99}, # SPLENDOR GOLD
    "POL60120A9": {"room_lot": 14.99, "pallet": 11.99}, # ETERNAL SATVARIO
    "POL60120A16": {"room_lot": 14.99, "pallet": 11.99}, # ONYX WHITE
    
    # Polished 60x120 CM - Premium
    "POL60120A6": {"room_lot": 15.49, "pallet": 12.49}, # PACIFIC AQUA
    "POL60120A7": {"room_lot": 15.49, "pallet": 12.49}, # RUBY ONYX PINK
    "POL60120A8": {"room_lot": 15.49, "pallet": 12.49}, # SPLENDOR GREEN
    
    # Matt 60x120 CM - Standard
    "MAT60120A5": {"room_lot": 14.99, "pallet": 11.99}, # RUBY ONYX SKY
    "MAT60120A7": {"room_lot": 14.99, "pallet": 11.99}, # ONYX WHITE
    "MAT60120A12": {"room_lot": 14.99, "pallet": 11.99}, # SPLENDOR GOLD
    
    # Matt 60x120 CM - Premium
    "MAT60120A1": {"room_lot": 15.49, "pallet": 12.49}, # SPANISH PUNCH
    "MAT60120A4": {"room_lot": 15.49, "pallet": 12.49}, # RUBY ONYX PINK
    
    # Carving 60x120 CM
    "CRV60120A1": {"room_lot": 15.99, "pallet": 12.99}, # DAPPLED GREY
    "CRV60120A2": {"room_lot": 15.99, "pallet": 12.99}, # GOLDEN VEINS
    "CRV60120A7": {"room_lot": 15.99, "pallet": 12.99}, # VEINS GREY
    
    # Polished 80x80 CM
    "POL8080A1": {"room_lot": 15.49, "pallet": 12.49}, # REAL SATVARIO
    "POL8080A2": {"room_lot": 15.49, "pallet": 12.49}, # ALLURE GREY
    
    # Carving 80x80 CM
    "CRV8080A1": {"room_lot": 15.49, "pallet": 12.49}, # DAPPLED GREY
    
    # Polished 80x120 CM
    "POL80120A1": {"room_lot": 16.99, "pallet": 13.99}, # ELEGANT STATUARIO
    "POL80120A2": {"room_lot": 16.99, "pallet": 13.99}, # ONYX PEARL
    "POL80120A3": {"room_lot": 16.99, "pallet": 13.99}, # ONYX WHITE
    "POL80120A4": {"room_lot": 16.99, "pallet": 13.99}, # IMPERIAL BEIGE
    "POL80120A5": {"room_lot": 16.99, "pallet": 13.99}, # EMERALD GREY
    
    # Matt 80x120 CM
    "MAT80120A1": {"room_lot": 16.99, "pallet": 13.99}, # ELEGANT STATUARIO
    "MAT80120A2": {"room_lot": 16.99, "pallet": 13.99}, # CONCRETE BIANCO
    
    # Carving 80x120 CM
    "CAR80120A1": {"room_lot": 17.99, "pallet": 14.99}, # ASTONISHED GREY
    
    # High Gloss 60x120 CM
    "HG60120A1": {"room_lot": 15.49, "pallet": 13.99}, # CLASSIC BLUE
    "HG60120A3": {"room_lot": 15.49, "pallet": 13.99}, # MAGIC GOLD
    "HG60120A4": {"room_lot": 15.49, "pallet": 13.99}, # BLACK THUNDER
    "HG60120A5": {"room_lot": 15.49, "pallet": 13.99}, # ONYX BLUE
}


def update_wallcano_prices():
    """Update Wallcano prices in the database"""
    client = MongoClient('mongodb://localhost:27017')
    db = client['tile_station']
    
    updated_count = 0
    not_found = []
    already_updated = []
    
    print("=" * 60)
    print("Wallcano Price Update - February 2025 UK Price List")
    print("=" * 60)
    
    for sku, prices in WALLCANO_PRICES.items():
        result = db.supplier_products.update_one(
            {'supplier_name': 'Wallcano', 'supplier_code': sku},
            {
                '$set': {
                    'room_lot_price': prices['room_lot'],
                    'pallet_price': prices['pallet'],
                    'price_updated_at': datetime.now(timezone.utc),
                    'price_source': 'February 2025 UK Price List PDF'
                }
            }
        )
        
        if result.matched_count > 0:
            if result.modified_count > 0:
                updated_count += 1
                print(f"✓ Updated {sku}: Room lot £{prices['room_lot']}, Pallet £{prices['pallet']}")
            else:
                already_updated.append(sku)
        else:
            not_found.append(sku)
    
    print("\n" + "=" * 60)
    print(f"SUMMARY")
    print("=" * 60)
    print(f"Total prices in list: {len(WALLCANO_PRICES)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Already up to date: {len(already_updated)}")
    print(f"Not found in database: {len(not_found)}")
    
    if not_found:
        print(f"\nSKUs not found: {not_found}")
    
    # Verify remaining products with zero prices
    zero_price = list(db.supplier_products.find(
        {'supplier_name': 'Wallcano', 'room_lot_price': 0.0},
        {'supplier_code': 1, 'name': 1, '_id': 0}
    ))
    
    if zero_price:
        print(f"\n⚠️  {len(zero_price)} products still have £0.00 price:")
        for p in zero_price:
            print(f"   - {p.get('supplier_code')}: {p.get('name')}")
    else:
        print(f"\n✅ All Wallcano products now have prices!")
    
    client.close()
    return updated_count


if __name__ == '__main__':
    update_wallcano_prices()
