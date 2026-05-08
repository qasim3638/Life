"""
Product Documents API
Upload, manage, and serve PDF documents (datasheets, guides, etc.) attached to products.
Uses Emergent Object Storage for persistent file storage.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import os
import uuid
import logging
import jwt

from services.object_storage import init_storage, put_object, get_object

router = APIRouter(prefix="/product-documents", tags=["product-documents"])
logger = logging.getLogger(__name__)

security = HTTPBearer()
SECRET_KEY = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
APP_NAME = "tile-station"

DOCUMENT_TYPES = [
    "Technical Datasheet",
    "Safety Datasheet",
    "Installation Guide",
    "Product Brochure",
    "Warranty Information",
    "Care & Maintenance",
    "Certificate",
    "Other",
]

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "tile_station")
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        db = get_db()
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class AttachRequest(BaseModel):
    product_keys: List[str]  # ["supplier|||sku", ...]


class UpdateDocRequest(BaseModel):
    display_name: Optional[str] = None
    document_type: Optional[str] = None


@router.post("/upload")
async def upload_product_document(
    file: UploadFile = File(...),
    display_name: str = Form(...),
    document_type: str = Form("Technical Datasheet"),
    product_keys: str = Form(...),  # JSON-encoded list or comma-separated
    current_user: dict = Depends(get_current_user),
):
    """Upload a PDF and attach it to one or more products."""
    db = get_db()

    # Validate extension
    filename = file.filename or "document.pdf"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Read content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    # Parse product keys
    import json
    try:
        keys = json.loads(product_keys)
    except (json.JSONDecodeError, TypeError):
        keys = [k.strip() for k in product_keys.split(",") if k.strip()]

    if not keys:
        raise HTTPException(status_code=400, detail="At least one product must be specified")

    # Upload to object storage
    doc_id = str(uuid.uuid4())
    storage_path = f"{APP_NAME}/product-docs/{doc_id}.pdf"

    try:
        result = put_object(storage_path, content, "application/pdf")
        stored_path = result.get("path", storage_path)
    except Exception as e:
        logger.error(f"Storage upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(e)}")

    # Save to DB
    doc = {
        "id": doc_id,
        "storage_path": stored_path,
        "original_filename": filename,
        "display_name": display_name,
        "document_type": document_type,
        "file_size": len(content),
        "product_keys": keys,
        "uploaded_by": current_user.get("email"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "is_deleted": False,
    }

    await db.product_documents.insert_one(doc)
    doc.pop("_id", None)

    return doc


@router.get("/by-product/{supplier}/{sku}")
async def get_documents_for_product(supplier: str, sku: str):
    """Get all documents attached to a specific product. Public endpoint for shop pages."""
    db = get_db()
    product_key = f"{supplier}|||{sku}"

    docs = await db.product_documents.find(
        {"product_keys": product_key, "is_deleted": {"$ne": True}},
        {"_id": 0, "storage_path": 0},
    ).to_list(100)

    return docs


@router.post("/by-products")
async def get_documents_for_products(
    data: AttachRequest,
    current_user: dict = Depends(get_current_user),
):
    """Get documents for multiple products at once (admin use)."""
    db = get_db()

    docs = await db.product_documents.find(
        {"product_keys": {"$in": data.product_keys}, "is_deleted": {"$ne": True}},
        {"_id": 0, "storage_path": 0},
    ).to_list(500)

    return docs


@router.get("/{doc_id}/download")
async def download_product_document(doc_id: str):
    """Download a product document. Public endpoint — no auth needed."""
    db = get_db()
    doc = await db.product_documents.find_one(
        {"id": doc_id, "is_deleted": {"$ne": True}}
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        data, content_type = get_object(doc["storage_path"])
    except Exception as e:
        logger.error(f"Storage download failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve file")

    filename = doc.get("original_filename", f"{doc['display_name']}.pdf")

    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@router.patch("/{doc_id}")
async def update_product_document(
    doc_id: str,
    data: UpdateDocRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update document metadata (display name, type)."""
    db = get_db()
    doc = await db.product_documents.find_one({"id": doc_id, "is_deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    update = {}
    if data.display_name is not None:
        update["display_name"] = data.display_name
    if data.document_type is not None:
        update["document_type"] = data.document_type

    if update:
        await db.product_documents.update_one({"id": doc_id}, {"$set": update})

    updated = await db.product_documents.find_one({"id": doc_id}, {"_id": 0, "storage_path": 0})
    return updated


@router.post("/{doc_id}/attach")
async def attach_to_products(
    doc_id: str,
    data: AttachRequest,
    current_user: dict = Depends(get_current_user),
):
    """Attach an existing document to additional products."""
    db = get_db()
    doc = await db.product_documents.find_one({"id": doc_id, "is_deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.product_documents.update_one(
        {"id": doc_id},
        {"$addToSet": {"product_keys": {"$each": data.product_keys}}},
    )

    updated = await db.product_documents.find_one({"id": doc_id}, {"_id": 0, "storage_path": 0})
    return updated


@router.post("/{doc_id}/detach")
async def detach_from_products(
    doc_id: str,
    data: AttachRequest,
    current_user: dict = Depends(get_current_user),
):
    """Remove a document from specific products."""
    db = get_db()
    doc = await db.product_documents.find_one({"id": doc_id, "is_deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.product_documents.update_one(
        {"id": doc_id},
        {"$pullAll": {"product_keys": data.product_keys}},
    )

    updated = await db.product_documents.find_one({"id": doc_id}, {"_id": 0, "storage_path": 0})
    return updated


@router.delete("/{doc_id}")
async def delete_product_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a product document."""
    db = get_db()
    doc = await db.product_documents.find_one({"id": doc_id, "is_deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await db.product_documents.update_one(
        {"id": doc_id},
        {"$set": {"is_deleted": True}},
    )

    return {"message": "Document deleted"}


@router.get("/types/list")
async def list_document_types():
    """Return the list of available document types."""
    return DOCUMENT_TYPES



@router.post("/migrate-broken-keys")
async def migrate_broken_keys(
    current_user: dict = Depends(get_current_user),
):
    """
    One-time migration: Fix documents that have broken product_keys like 'Supplier|||undefined'.
    These were created when products had no SKU and the old code didn't fall back to supplier_code.
    This endpoint finds those documents and removes the broken keys.
    """
    db = get_db()
    
    # Find all documents with "undefined" in product_keys
    broken_docs = await db.product_documents.find(
        {"product_keys": {"$regex": "\\|\\|\\|undefined$"}, "is_deleted": {"$ne": True}},
        {"_id": 0, "storage_path": 0},
    ).to_list(1000)
    
    fixed_count = 0
    deleted_count = 0
    
    for doc in broken_docs:
        # Remove the broken keys
        broken_keys = [k for k in doc.get("product_keys", []) if k.endswith("|||undefined")]
        good_keys = [k for k in doc.get("product_keys", []) if not k.endswith("|||undefined")]
        
        if good_keys:
            # Keep the doc but remove broken keys
            await db.product_documents.update_one(
                {"id": doc["id"]},
                {"$set": {"product_keys": good_keys}}
            )
            fixed_count += 1
        else:
            # All keys were broken — soft delete the document
            await db.product_documents.update_one(
                {"id": doc["id"]},
                {"$set": {"is_deleted": True, "product_keys": [], "deletion_reason": "All product_keys were broken (|||undefined)"}}
            )
            deleted_count += 1
    
    return {
        "message": f"Migration complete. Fixed {fixed_count} documents, soft-deleted {deleted_count} documents with only broken keys.",
        "total_broken_found": len(broken_docs),
        "fixed": fixed_count,
        "deleted": deleted_count,
        "broken_docs": [{"id": d["id"], "display_name": d.get("display_name"), "product_keys": d.get("product_keys")} for d in broken_docs]
    }
