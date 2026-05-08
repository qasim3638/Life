#!/usr/bin/env python3
"""
Script to add specifications to the Tile Station system.
Checks for duplicates before adding.
"""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from bson import ObjectId

# Database connection
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "tile_station")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Specifications to add
SPECIFICATIONS = {
    "material": {
        "name": "Material",
        "field_name": "material",
        "group_slug": "physical",
        "values": [
            "Porcelain", "Ceramic", "Natural Stone", "Marble", "Travertine", 
            "Slate", "Limestone", "Granite", "Glass", "Terracotta", "Quarry", "Encaustic"
        ]
    },
    "finish": {
        "name": "Finish",
        "field_name": "finish",
        "group_slug": "appearance",
        "values": [
            "Matt", "Gloss", "Polished", "Satin", "Textured", 
            "Honed", "Brushed", "Semi Polish (Sugar)"
        ]
    },
    "edge": {
        "name": "Edge",
        "field_name": "edge",
        "group_slug": "physical",
        "values": [
            "Rectified", "Cushion Edge", "Bevelled", "Pressed Edge", 
            "Natural Edge", "Non Rectified"
        ]
    },
    "slip_rating": {
        "name": "Slip Rating",
        "field_name": "slip_rating",
        "group_slug": "safety",
        "values": [
            "R9", "R10", "R11", "R12", "R13", 
            "PEI 1", "PEI 2", "PEI 3", "PEI 4", "PEI 5"
        ]
    },
    "thickness": {
        "name": "Thickness",
        "field_name": "thickness",
        "group_slug": "physical",
        "values": [
            "6mm", "8mm", "9mm", "10mm", "11mm", "12mm", "14mm", "20mm"
        ]
    },
    "suitability": {
        "name": "Suitability",
        "field_name": "suitability",
        "group_slug": "usage",
        "values": [
            "Wall", "Floor", "Wall & Floor"
        ]
    }
}

# Specification groups to ensure exist
SPEC_GROUPS = [
    {"name": "Physical", "slug": "physical", "icon": "Ruler", "color": "#3b82f6", "display_order": 0},
    {"name": "Appearance", "slug": "appearance", "icon": "Palette", "color": "#8b5cf6", "display_order": 1},
    {"name": "Safety", "slug": "safety", "icon": "Shield", "color": "#ef4444", "display_order": 2},
    {"name": "Usage", "slug": "usage", "icon": "Home", "color": "#22c55e", "display_order": 3},
]

async def ensure_spec_groups():
    """Ensure specification groups exist"""
    print("\n=== Ensuring Specification Groups ===")
    for group in SPEC_GROUPS:
        existing = await db.specification_groups.find_one({"slug": group["slug"]})
        if existing:
            print(f"  ✓ Group '{group['name']}' already exists")
        else:
            group["created_at"] = datetime.now(timezone.utc)
            group["updated_at"] = datetime.now(timezone.utc)
            group["is_active"] = True
            await db.specification_groups.insert_one(group)
            print(f"  ✓ Created group '{group['name']}'")

async def add_specifications():
    """Add specifications with duplicate checking"""
    print("\n=== Adding Specifications ===")
    
    for slug, spec_data in SPECIFICATIONS.items():
        print(f"\n--- {spec_data['name']} ---")
        
        # Check if specification type exists
        spec_type = await db.specification_types.find_one({"slug": slug})
        
        if not spec_type:
            # Create new specification type
            new_spec = {
                "name": spec_data["name"],
                "slug": slug,
                "description": "",
                "group_slug": spec_data["group_slug"],
                "field_name": spec_data["field_name"],
                "display_order": 0,
                "is_active": True,
                "auto_populate": True,
                "values": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            result = await db.specification_types.insert_one(new_spec)
            spec_type = await db.specification_types.find_one({"_id": result.inserted_id})
            print(f"  ✓ Created specification type '{spec_data['name']}'")
        else:
            print(f"  ℹ Specification type '{spec_data['name']}' exists")
        
        # Get existing values
        existing_values = {v.get("value", "").lower(): v for v in spec_type.get("values", [])}
        
        # Add values
        added_count = 0
        skipped_count = 0
        
        for value in spec_data["values"]:
            if value.lower() in existing_values:
                skipped_count += 1
            else:
                # Add new value
                new_value = {
                    "value": value,
                    "label": value,
                    "description": "",
                    "is_active": True
                }
                await db.specification_types.update_one(
                    {"_id": spec_type["_id"]},
                    {
                        "$push": {"values": new_value},
                        "$set": {"updated_at": datetime.now(timezone.utc)}
                    }
                )
                added_count += 1
        
        print(f"  ✓ Added {added_count} values, skipped {skipped_count} duplicates")

async def sync_to_filters():
    """Sync specifications to website filters for Navigation & Structure"""
    print("\n=== Syncing to Website Filters ===")
    
    spec_types = await db.specification_types.find().to_list(100)
    
    for spec in spec_types:
        slug = spec.get("slug")
        name = spec.get("name")
        values = spec.get("values", [])
        
        # Check if filter exists
        existing_filter = await db.website_filters.find_one({"slug": slug})
        
        if existing_filter:
            # Update existing filter with new options
            existing_options = {o.get("value", "").lower(): o for o in existing_filter.get("options", [])}
            new_options = existing_filter.get("options", [])
            
            added = 0
            for val in values:
                if val["value"].lower() not in existing_options:
                    new_options.append({
                        "value": val["value"],
                        "label": val["label"],
                        "count": 0,
                        "is_active": True
                    })
                    added += 1
            
            if added > 0:
                await db.website_filters.update_one(
                    {"_id": existing_filter["_id"]},
                    {"$set": {"options": new_options, "updated_at": datetime.now(timezone.utc)}}
                )
                print(f"  ✓ Updated filter '{name}' - added {added} options")
            else:
                print(f"  ℹ Filter '{name}' already up to date")
        else:
            # Create new filter
            filter_options = [
                {"value": v["value"], "label": v["label"], "count": 0, "is_active": True}
                for v in values
            ]
            
            new_filter = {
                "name": name,
                "slug": slug,
                "description": f"Filter by {name.lower()}",
                "filter_type": "checkbox",
                "options": filter_options,
                "display_order": 0,
                "is_active": True,
                "show_in_sidebar": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            await db.website_filters.insert_one(new_filter)
            print(f"  ✓ Created filter '{name}' with {len(filter_options)} options")

async def main():
    print("=" * 60)
    print("TILE STATION - ADD SPECIFICATIONS")
    print("=" * 60)
    
    # Ensure groups exist
    await ensure_spec_groups()
    
    # Add specifications
    await add_specifications()
    
    # Sync to filters
    await sync_to_filters()
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    
    # Show summary
    spec_count = await db.specification_types.count_documents({})
    filter_count = await db.website_filters.count_documents({})
    
    print(f"\nTotal specification types: {spec_count}")
    print(f"Total website filters: {filter_count}")

if __name__ == "__main__":
    asyncio.run(main())
