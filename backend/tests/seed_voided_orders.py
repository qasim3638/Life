"""Seed a trader with 1 normal online order, 1 normal EPOS invoice, 1 DELETED EPOS invoice."""
import os, sys, asyncio, uuid, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    raw_pwd = "VoidTest123!"
    pwd_hash = bcrypt.hashpw(raw_pwd.encode(), bcrypt.gensalt()).decode()

    cust_id = f"void-test-{uuid.uuid4().hex[:8]}"
    email = f"void-{uuid.uuid4().hex[:6]}@example.com"

    await db.shop_customers.insert_one({
        "id": cust_id, "email": email, "password": pwd_hash,
        "name": "Void Tester", "business_name": "Void Tester Ltd",
        "is_trade": True, "trade_account_number": "T-VOID01",
        "approved": True, "credit_balance": 25.0,
        "total_spent": 200.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 1. Normal online shop order
    online_id = str(uuid.uuid4())
    online_no = f"TS-{uuid.uuid4().hex[:6].upper()}"
    await db.shop_orders.insert_one({
        "id": online_id, "order_number": online_no,
        "customer_id": cust_id, "customer_email": email,
        "customer_name": "Void Tester",
        "delivery_method": "delivery", "delivery_address": "1 Test Lane, London, NW1 1AA",
        "items": [{"product_id": "p1", "name": "Tile", "price": 10.0, "quantity": 5}],
        "subtotal": 50.0, "delivery_fee": 0.0, "total": 60.0,
        "status": "delivered",
        "savings_meta": {"total_saved": 5.0, "lines_with_savings": 1, "percent_off_retail": 10},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 2. Normal live EPOS invoice
    epos_id = str(uuid.uuid4())
    epos_no = f"INV-{uuid.uuid4().hex[:6].upper()}"
    await db.invoices.insert_one({
        "id": epos_id, "invoice_no": epos_no,
        "linked_shop_customer_id": cust_id,
        "customer_name": "Void Tester", "customer_email": email,
        "showroom_name": "Tonbridge Showroom", "staff_name": "Sarah Smith",
        "date": "10/01/2026",
        "subtotal": 100.0, "gross_total": 120.0, "amount_outstanding": 0.0,
        "apply_vat": True, "trade_account_number": "T-VOID01",
        "line_items": [{"product_name": "In-store Tile", "quantity": 10,
                        "due_price": 10.0, "price": 12.0}],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # 3. DELETED EPOS invoice
    del_id = str(uuid.uuid4())
    del_no = f"INV-{uuid.uuid4().hex[:6].upper()}"
    await db.invoices.insert_one({
        "id": del_id, "invoice_no": del_no,
        "linked_shop_customer_id": cust_id,
        "customer_name": "Void Tester", "customer_email": email,
        "showroom_name": "Tonbridge Showroom", "staff_name": "Sarah Smith",
        "date": "05/01/2026",
        "subtotal": 50.0, "gross_total": 60.0, "amount_outstanding": 0.0,
        "apply_vat": True, "trade_account_number": "T-VOID01",
        "line_items": [{"product_name": "Deleted Tile", "quantity": 5,
                        "due_price": 10.0, "price": 12.0}],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_by_name": "Sarah Smith",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    out = {
        "email": email, "password": raw_pwd, "cust_id": cust_id,
        "online_id": online_id, "online_no": online_no,
        "epos_id": epos_id, "epos_no": epos_no,
        "del_id": del_id, "del_no": del_no,
    }
    with open("/tmp/void_seed.json", "w") as f:
        json.dump(out, f)
    print(json.dumps(out))
    client.close()


asyncio.run(main())
