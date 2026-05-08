#!/usr/bin/env python3
"""
Script to replace Ultra Tile products with data extracted from Instarmac PDF price list CT1127.
All 81 products - combined bold name + description, no quantity mentions.
"""
import requests
import json
import sys

# All products from PDF - name = "Bold Name - Description" (no quantities)
ULTRA_TILE_PRODUCTS = [
    # Page 1 (13 products)
    {"sku": "ULT-GGI", "name": "GGI - Grip & Grab It All Purpose Adhesive", "cost_price": 5.43, "unit": "Units per PALLET"},
    {"sku": "ULT-INS-MB", "name": "INS MIXING BUCKET - 28 Litre Mixing Bucket", "cost_price": 5.58, "unit": "Units per PALLET"},
    {"sku": "ULT-LIR", "name": "LEVEL IT RENOVATE - Water Based Smoothing Underlayment", "cost_price": 12.08, "unit": "Units per PALLET"},
    {"sku": "ULT-PIG", "name": "PRIME IT GRIT - Prime It Multi-Surface Primer 5LTR", "cost_price": 27.58, "unit": "Units per PALLET"},
    {"sku": "ULT-PP", "name": "PRO-PRIME - Slurry Primer 20KG Bag", "cost_price": 16.85, "unit": "Units per PALLET"},
    {"sku": "ULT-EC", "name": "UT EASY CLEAN - Easy Clean Tile Protector 1L", "cost_price": 6.24, "unit": "Units per PALLET"},
    {"sku": "ULT-GA1L", "name": "UT GROUT AID 1L - UltraTile ProClean Grout Aid 1 Litre", "cost_price": 6.81, "unit": "Units per PALLET"},
    {"sku": "ULT-GH1L", "name": "UT GROUT HAZE 1L - UltraTile ProClean Grout Haze Remover 1 Litre", "cost_price": 5.50, "unit": "Units per PALLET"},
    {"sku": "ULT-PGEC", "name": "UT PG EPOXY CHAR - UT ProGrout Epoxy Charcoal 3kg", "cost_price": 23.46, "unit": "Units per EACH"},
    {"sku": "ULT-PGEG", "name": "UT PG EPOXY GREY - UT ProGrout Epoxy Grey 3kg", "cost_price": 23.46, "unit": "Units per EACH"},
    {"sku": "ULT-PGEJ", "name": "UT PG EPOXY JAS - UT ProGrout Epoxy Jasmine 3kg", "cost_price": 23.46, "unit": "Units per EACH"},
    {"sku": "ULT-PGESG", "name": "UT PG EPOXY SIL-GREY - UT ProGrout Epoxy Silver Grey 3kg", "cost_price": 23.46, "unit": "Units per EACH"},
    {"sku": "ULT-PGEW", "name": "UT PG EPOXY WHITE - UT ProGrout Epoxy White 3kg", "cost_price": 23.46, "unit": "Units per EACH"},
    # Page 2 (13 products)
    {"sku": "ULT-PGFAL3", "name": "UT PG FLEXIBLE AL 3 - UltraTile ProGrout Flexible 3kg Almond", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFBW3", "name": "UT PG FLEXIBLE BW 3 - UltraTile ProGrout Flexible 3kg Brilliant White", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFDG10", "name": "UT PG FLEXIBLE DG 10 - UltraTile ProGrout Flexible 10kg Dark Grey", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFDG3", "name": "UT PG FLEXIBLE DG 3 - UltraTile ProGrout Flexible 3kg Dark Grey", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFI3", "name": "UT PG FLEXIBLE I 3 - UltraTile ProGrout Flexible 3kg Ivory", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFM3", "name": "UT PG FLEXIBLE M 3 - UltraTile ProGrout Flexible 3kg Mocha", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFVW10", "name": "UT PG FLEXIBLE VW 10 - UltraTile ProGrout Flexible 10kg Vintage White", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFVW3", "name": "UT PG FLEXIBLE VW 3 - UltraTile ProGrout Flexible 3kg Vintage White", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFLCH", "name": "UT PG FLOWABLE CH - UT PG Flowable Grout 15KGS Charcoal", "cost_price": 13.84, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFLG", "name": "UT PG FLOWABLE G - UT PG Flowable Grout 15KGS Grey", "cost_price": 13.84, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFLL", "name": "UT PG FLOWABLE L - UT PG Flowable Grout 15KGS Limestone", "cost_price": 13.84, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFLSG", "name": "UT PG FLOWABLE SG - UT PG Flowable Grout 15KGS Silver Grey", "cost_price": 13.84, "unit": "Units per PALLET"},
    {"sku": "ULT-PAS", "name": "UT PRO AQUA SHIELD - Ultra Tile Wetroom Kit Pro Aqua Shield 9kg", "cost_price": 31.96, "unit": "Units per EACH"},
    # Page 3 (13 products)
    {"sku": "ULT-PSG", "name": "UT PRO SUPERGRIP - UltraTileFix ProSuper Grip 15kg/10L", "cost_price": 8.50, "unit": "Units per EURO"},
    {"sku": "ULT-PGFX20G", "name": "UT PROGRIP FX 20 G - FibreGrip Semi-Rapid S1 Fibre Tile Adhesive Grey", "cost_price": 9.45, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFX20W", "name": "UT PROGRIP FX 20 W - FibreGrip Semi-Rapid S1 Fibre Tile Adhesive White", "cost_price": 10.56, "unit": "Units per PALLET"},
    {"sku": "ULT-TGS", "name": "UT TILE AND GROUT SEALER - UltraTile ProClean Tile Guard 1ltr", "cost_price": 12.91, "unit": "Units per PALLET"},
    {"sku": "ULT-TC1L", "name": "UT TILE CLEANER 1L - UT ProClean Porcelain Tile & Stone Cleaner 1L", "cost_price": 5.50, "unit": "Units per PALLET"},
    {"sku": "ULT-TX1L", "name": "UT TILE XTREME 1L - UltraTile ProClean Xtreme Cleaner 1 Litre", "cost_price": 5.50, "unit": "Units per PALLET"},
    {"sku": "ULT-PFSP20G", "name": "UTF PFLEX SPES 20 G - UltraTileFix ProFlex S1 SPES 20kg Grey", "cost_price": 7.94, "unit": "Units per PALLET"},
    {"sku": "ULT-PFSP20W", "name": "UTF PFLEX SPES 20 W - UltraTileFix ProFlex S1 SPES 20kg White", "cost_price": 8.88, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXCH10", "name": "UTF PG FLEX CH 10 - UltraTileFix ProGrout Flexible 10kg Charcoal", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXMG10", "name": "UTF PG FLEX MG 10 - UltraTileFix ProGrout Flexible 10kg Mid Grey", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXBL3", "name": "UTF PG FLEXIBLE BL 3 - UltraTileFix ProGrout Flexible 3kg Black", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXCH3", "name": "UTF PG FLEXIBLE CH 3 - UltraTileFix ProGrout Flexible 3kg Charcoal", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXG10", "name": "UTF PG FLEXIBLE G 10 - UltraTileFix ProGrout Flexible 10kg Grey", "cost_price": 8.20, "unit": "Units per PALLET"},
    # Page 4 (13 products)
    {"sku": "ULT-PGFXG3", "name": "UTF PG FLEXIBLE G 3 - UltraTileFix ProGrout Flexible 3kg Grey", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXJ10", "name": "UTF PG FLEXIBLE J 10 - UltraTileFix ProGrout Flexible 10kg Jasmine", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXJ3", "name": "UTF PG FLEXIBLE J 3 - UltraTileFix ProGrout Flexible 3kg Jasmine", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXL10", "name": "UTF PG FLEXIBLE L 10 - UltraTileFix ProGrout Flexible 10kg Limestone", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXL3", "name": "UTF PG FLEXIBLE L 3 - UltraTileFix ProGrout Flexible 3kg Limestone", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXMG3", "name": "UTF PG FLEXIBLE MG 3 - UltraTileFix ProGrout Flexible 3kg Mid-Grey", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXS10", "name": "UTF PG FLEXIBLE S 10 - UltraTileFix ProGrout Flexible 10kg Silver Grey", "cost_price": 8.20, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXS3", "name": "UTF PG FLEXIBLE S 3 - UltraTileFix ProGrout Flexible 3kg Silver Grey", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PGFXT3", "name": "UTF PG FLEXIBLE T 3 - UltraTileFix ProGrout Flexible 3kg Taupe", "cost_price": 3.75, "unit": "Units per PALLET"},
    {"sku": "ULT-PLF20", "name": "UTF PLEVEL FIBRE 20 - UltraTileFix ProLevel Fibre 20kg", "cost_price": 9.13, "unit": "Units per PALLET"},
    {"sku": "ULT-PLR20", "name": "UTF PLEVEL RAPID 20 - UltraTileFix ProLevel Rapid 20kg", "cost_price": 16.27, "unit": "Units per PALLET"},
    {"sku": "ULT-PSSF20G", "name": "UTF PRO SS FLEX 20 G - UTF Pro Set Standard Set Flexible Tile Adhesive 20kg Grey", "cost_price": 6.95, "unit": "Units per PALLET"},
    {"sku": "ULT-PSSF20W", "name": "UTF PRO SS FLEX 20 W - UTF Pro Set Standard Set Flexible Tile Adhesive 20kg White", "cost_price": 8.01, "unit": "Units per PALLET"},
    # Page 5 (13 products)
    {"sku": "ULT-PSW", "name": "UTF PRO SUPERWHITE - UltraTileFix ProSuper White 15kg/10L Brilliant White", "cost_price": 12.60, "unit": "Units per PALLET"},
    {"sku": "ULT-PFS220G", "name": "UTF PROFLEX S2 20 G - UltraTileFix Fibre Reinforced S2 20kg Grey", "cost_price": 15.97, "unit": "Units per PALLET"},
    {"sku": "ULT-PFS220W", "name": "UTF PROFLEX S2 20 W - UltraTileFix Fibre Reinforced S2 20kg White", "cost_price": 17.05, "unit": "Units per PALLET"},
    {"sku": "ULT-PFSP20G2", "name": "UTF PROFLEX SP 20 G - UltraTileFix ProFlex SP 20kg Grey", "cost_price": 9.45, "unit": "Units per PALLET"},
    {"sku": "ULT-PFSP20W2", "name": "UTF PROFLEX SP 20 W - UltraTileFix ProFlex SP 20kg White", "cost_price": 10.25, "unit": "Units per PALLET"},
    {"sku": "ULT-PL120", "name": "UTF PROLEVEL ONE 20 - UltraTileFix ProLevel One 20kg", "cost_price": 9.32, "unit": "Units per PALLET"},
    {"sku": "ULT-PL2", "name": "UTF PROLEVEL TWO - UltraTileFix ProLevel Two 20kg Bag", "cost_price": 6.96, "unit": "Units per PALLET"},
    {"sku": "ULT-PL2BD", "name": "UTF PROLEVEL TWO BOT DIST - UltraTileFix ProLevel Two 4L", "cost_price": 4.09, "unit": "Units per PALLET"},
    {"sku": "ULT-PPCB", "name": "UTF PROPAVE COSMIC B - UTF ProPave Cosmic Black 15kg", "cost_price": 27.66, "unit": "Units per PALLET"},
    {"sku": "ULT-PPM", "name": "UTF PROPAVE MORTAR - UTF Bedding Mortar Additive 20KG Bag", "cost_price": 8.68, "unit": "Units per PALLET"},
    {"sku": "ULT-PPN", "name": "UTF PROPAVE NATURAL - UTF ProPave Natural Cashmere 15kg", "cost_price": 27.66, "unit": "Units per PALLET"},
    {"sku": "ULT-PPP", "name": "UTF PROPAVE PEBBLE - UTF ProPave Pebble Grey 15KG", "cost_price": 27.66, "unit": "Units per PALLET"},
    {"sku": "ULT-PPPR", "name": "UTF PROPAVE PRIMER - UTF ProPave Primer 17KG Tub", "cost_price": 15.24, "unit": "Units per PALLET"},
    # Page 6 (13 products)
    {"sku": "ULT-PPS", "name": "UTF PROPAVE STORM - UTF ProPave Storm Grey 15kg", "cost_price": 27.66, "unit": "Units per PALLET"},
    {"sku": "ULT-PPR1L", "name": "UTF PROPRIMER 1L - UltraTileFix ProPrimer 1L", "cost_price": 5.29, "unit": "Units per PALLET"},
    {"sku": "ULT-PPR5L", "name": "UTF PROPRIMER 5L - UltraTileFix ProPrimer 5L", "cost_price": 12.77, "unit": "Units per PALLET"},
    {"sku": "ULT-PRRS20G", "name": "UTF PRORAPID RS 20 G - UltraTileFix ProRapid RS 20kg Grey", "cost_price": 7.39, "unit": "Units per PALLET"},
    {"sku": "ULT-PRRS20W", "name": "UTF PRORAPID RS 20 W - UltraTileFix ProRapid RS 20kg White", "cost_price": 9.09, "unit": "Units per PALLET"},
    {"sku": "ULT-PSBLK", "name": "UTF PROSEALER BLACK - UltraTileFix ProSealer 310ml Black", "cost_price": 5.47, "unit": "Units per BOX"},
    {"sku": "ULT-PSCHR", "name": "UTF PROSEALER CHAR - UltraTileFix ProSealer 310ml Charcoal", "cost_price": 5.47, "unit": "Units per BOX"},
    {"sku": "ULT-PSCLR", "name": "UTF PROSEALER CLEAR - UltraTileFix ProSealer 310ml Clear", "cost_price": 5.47, "unit": "Units per BOX"},
    {"sku": "ULT-PSGRY", "name": "UTF PROSEALER GREY - UltraTileFix ProSealer 310ml Grey", "cost_price": 5.47, "unit": "Units per PALLET"},
    {"sku": "ULT-PSJAS", "name": "UTF PROSEALER JASM - UltraTileFix ProSealer 310ml Jasmine", "cost_price": 5.47, "unit": "Units per PALLET"},
    {"sku": "ULT-PSLMS", "name": "UTF PROSEALER LIMES - UltraTileFix ProSealer 310ml Limestone", "cost_price": 5.47, "unit": "Units per BOX"},
    {"sku": "ULT-PSMGR", "name": "UTF PROSEALER MID-GR - UltraTileFix ProSealer 310ml Mid-Grey", "cost_price": 5.47, "unit": "Units per PALLET"},
    {"sku": "ULT-PSSGR", "name": "UTF PROSEALER SIL-GR - UltraTileFix ProSealer 310ml Silver Grey", "cost_price": 5.47, "unit": "Units per BOX"},
    # Page 7 (3 products)
    {"sku": "ULT-PSTPE", "name": "UTF PROSEALER TAUPE - UltraTileFix ProSealer 310ml Taupe", "cost_price": 5.47, "unit": "Units per PALLET"},
    {"sku": "ULT-PSWHT", "name": "UTF PROSEALER WHITE - UltraTileFix ProSealer 310ml White", "cost_price": 5.47, "unit": "Units per BOX"},
    {"sku": "ULT-PSTAPE", "name": "UTF PROSHIELD TAPE - UltraTileFix ProShield Tape Only 10m", "cost_price": 10.34, "unit": "Units per PALLET"},
]

def main():
    if len(sys.argv) < 2:
        print("Usage: python replace_ultra_tile.py <API_URL>")
        print("Example: python replace_ultra_tile.py https://your-production-url.com")
        sys.exit(1)
    
    api_url = sys.argv[1].rstrip("/")
    endpoint = f"{api_url}/api/supplier-sync/replace-ultra-tile-products"
    
    print(f"Total products to import: {len(ULTRA_TILE_PRODUCTS)}")
    print(f"API endpoint: {endpoint}")
    
    # Step 1: Dry run (no confirm)
    print("\n--- DRY RUN ---")
    resp = requests.post(endpoint, json={"products": ULTRA_TILE_PRODUCTS, "confirm": False})
    print(f"Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))
    
    if resp.status_code != 200:
        print("ERROR: Dry run failed. Aborting.")
        sys.exit(1)
    
    dry_run = resp.json()
    print(f"\nWill DELETE {dry_run.get('current_count', '?')} existing products")
    print(f"Will INSERT {dry_run.get('new_count', '?')} new products")
    
    # Step 2: Confirm and execute
    print("\n--- EXECUTING REPLACE ---")
    resp = requests.post(endpoint, json={"products": ULTRA_TILE_PRODUCTS, "confirm": True})
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print(f"\n=== SUCCESS ===")
        print(f"Deleted: {result['deleted']} old products")
        print(f"Inserted: {result['inserted']} new products")
        if result.get('errors', 0) > 0:
            print(f"Errors: {result['errors']}")
            for err in result.get('error_details', []):
                print(f"  - {err}")
    else:
        print(f"\nFAILED: {result.get('message', 'Unknown error')}")

if __name__ == "__main__":
    main()
