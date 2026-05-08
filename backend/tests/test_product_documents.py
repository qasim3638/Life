"""
Product Documents API Tests
Tests for PDF document upload, management, and retrieval endpoints.
"""
import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_URL = f"{BASE_URL}/api"

# Test credentials
TEST_EMAIL = "qasim@tilestation.co.uk"
TEST_PASSWORD = "Tilestation_9614"

# Test product key
TEST_PRODUCT_KEY = "LEPORCE|||LPT OLYMPIA BLANC 120x120"
TEST_SUPPLIER = "LEPORCE"
TEST_SKU = "LPT OLYMPIA BLANC 120x120"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("token")
    assert token, "No token in response"
    return token


@pytest.fixture
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestPublicEndpoints:
    """Tests for public (no auth required) endpoints."""

    def test_get_document_types_list(self):
        """GET /api/product-documents/types/list - returns list of document types."""
        response = requests.get(f"{API_URL}/product-documents/types/list")
        assert response.status_code == 200
        
        types = response.json()
        assert isinstance(types, list)
        assert len(types) > 0
        assert "Technical Datasheet" in types
        assert "Installation Guide" in types
        assert "Safety Datasheet" in types

    def test_get_documents_for_product(self):
        """GET /api/product-documents/by-product/{supplier}/{sku} - returns documents for a product."""
        response = requests.get(
            f"{API_URL}/product-documents/by-product/{TEST_SUPPLIER}/{TEST_SKU}"
        )
        assert response.status_code == 200
        
        docs = response.json()
        assert isinstance(docs, list)
        # Should have at least the test document
        if len(docs) > 0:
            doc = docs[0]
            assert "id" in doc
            assert "display_name" in doc
            assert "document_type" in doc
            assert "file_size" in doc
            # storage_path should NOT be exposed
            assert "storage_path" not in doc

    def test_get_documents_for_nonexistent_product(self):
        """GET /api/product-documents/by-product/{supplier}/{sku} - returns empty list for nonexistent product."""
        response = requests.get(
            f"{API_URL}/product-documents/by-product/NONEXISTENT/NONEXISTENT-SKU"
        )
        assert response.status_code == 200
        assert response.json() == []


class TestAuthenticatedEndpoints:
    """Tests for authenticated endpoints."""

    def test_get_documents_bulk(self, auth_headers):
        """POST /api/product-documents/by-products - returns documents for multiple products."""
        response = requests.post(
            f"{API_URL}/product-documents/by-products",
            json={"product_keys": [TEST_PRODUCT_KEY]},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        docs = response.json()
        assert isinstance(docs, list)

    def test_get_documents_bulk_no_auth(self):
        """POST /api/product-documents/by-products - requires authentication."""
        # This endpoint requires auth (admin-only functionality)
        response = requests.post(
            f"{API_URL}/product-documents/by-products",
            json={"product_keys": [TEST_PRODUCT_KEY]}
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]


class TestDocumentUploadAndManagement:
    """Tests for document upload, update, attach, detach, and delete."""

    @pytest.fixture
    def test_pdf_content(self):
        """Generate minimal valid PDF content."""
        return b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
0000000101 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
178
%%EOF"""

    def test_upload_document(self, auth_headers, test_pdf_content):
        """POST /api/product-documents/upload - uploads a PDF document."""
        files = {"file": ("test_document.pdf", test_pdf_content, "application/pdf")}
        data = {
            "display_name": f"TEST_Upload_{uuid.uuid4().hex[:8]}",
            "document_type": "Installation Guide",
            "product_keys": json.dumps([TEST_PRODUCT_KEY])
        }
        
        response = requests.post(
            f"{API_URL}/product-documents/upload",
            files=files,
            data=data,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        doc = response.json()
        assert "id" in doc
        assert doc["display_name"].startswith("TEST_Upload_")
        assert doc["document_type"] == "Installation Guide"
        assert TEST_PRODUCT_KEY in doc["product_keys"]
        assert doc["is_deleted"] == False
        
        # Cleanup - delete the test document
        delete_response = requests.delete(
            f"{API_URL}/product-documents/{doc['id']}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200

    def test_upload_non_pdf_rejected(self, auth_headers):
        """POST /api/product-documents/upload - rejects non-PDF files."""
        files = {"file": ("test.txt", b"This is not a PDF", "text/plain")}
        data = {
            "display_name": "Test Non-PDF",
            "document_type": "Technical Datasheet",
            "product_keys": json.dumps([TEST_PRODUCT_KEY])
        }
        
        response = requests.post(
            f"{API_URL}/product-documents/upload",
            files=files,
            data=data,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "PDF" in response.json().get("detail", "")

    def test_upload_no_auth(self, test_pdf_content):
        """POST /api/product-documents/upload - requires authentication."""
        files = {"file": ("test.pdf", test_pdf_content, "application/pdf")}
        data = {
            "display_name": "Test No Auth",
            "document_type": "Technical Datasheet",
            "product_keys": json.dumps([TEST_PRODUCT_KEY])
        }
        
        response = requests.post(
            f"{API_URL}/product-documents/upload",
            files=files,
            data=data
        )
        assert response.status_code in [401, 403]


class TestDocumentDownload:
    """Tests for document download endpoint."""

    def test_download_existing_document(self):
        """GET /api/product-documents/{doc_id}/download - downloads a document."""
        # First get a document ID
        response = requests.get(
            f"{API_URL}/product-documents/by-product/{TEST_SUPPLIER}/{TEST_SKU}"
        )
        docs = response.json()
        
        if len(docs) > 0:
            doc_id = docs[0]["id"]
            download_response = requests.get(
                f"{API_URL}/product-documents/{doc_id}/download"
            )
            assert download_response.status_code == 200
            assert download_response.headers.get("Content-Type") == "application/pdf"
            # Check it's a valid PDF
            assert download_response.content.startswith(b"%PDF")

    def test_download_nonexistent_document(self):
        """GET /api/product-documents/{doc_id}/download - returns 404 for nonexistent document."""
        response = requests.get(
            f"{API_URL}/product-documents/nonexistent-id/download"
        )
        assert response.status_code == 404


class TestDocumentUpdateOperations:
    """Tests for document update, attach, and detach operations."""

    @pytest.fixture
    def test_document(self, auth_headers):
        """Create a test document for update tests."""
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
0000000101 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
178
%%EOF"""
        
        files = {"file": ("test_update.pdf", pdf_content, "application/pdf")}
        data = {
            "display_name": f"TEST_Update_{uuid.uuid4().hex[:8]}",
            "document_type": "Technical Datasheet",
            "product_keys": json.dumps([TEST_PRODUCT_KEY])
        }
        
        response = requests.post(
            f"{API_URL}/product-documents/upload",
            files=files,
            data=data,
            headers=auth_headers
        )
        doc = response.json()
        yield doc
        
        # Cleanup
        requests.delete(
            f"{API_URL}/product-documents/{doc['id']}",
            headers=auth_headers
        )

    def test_update_document_metadata(self, auth_headers, test_document):
        """PATCH /api/product-documents/{doc_id} - updates document metadata."""
        new_name = f"TEST_Updated_{uuid.uuid4().hex[:8]}"
        response = requests.patch(
            f"{API_URL}/product-documents/{test_document['id']}",
            json={"display_name": new_name, "document_type": "Safety Datasheet"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        updated = response.json()
        assert updated["display_name"] == new_name
        assert updated["document_type"] == "Safety Datasheet"

    def test_attach_document_to_products(self, auth_headers, test_document):
        """POST /api/product-documents/{doc_id}/attach - attaches document to more products."""
        new_product_key = "LEPORCE|||LPT OLYMPIA GRIS 120x120"
        response = requests.post(
            f"{API_URL}/product-documents/{test_document['id']}/attach",
            json={"product_keys": [new_product_key]},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        updated = response.json()
        assert new_product_key in updated["product_keys"]
        assert TEST_PRODUCT_KEY in updated["product_keys"]

    def test_detach_document_from_products(self, auth_headers, test_document):
        """POST /api/product-documents/{doc_id}/detach - detaches document from products."""
        # First attach to another product
        new_product_key = "LEPORCE|||LPT OLYMPIA GRIS 120x120"
        requests.post(
            f"{API_URL}/product-documents/{test_document['id']}/attach",
            json={"product_keys": [new_product_key]},
            headers=auth_headers
        )
        
        # Now detach
        response = requests.post(
            f"{API_URL}/product-documents/{test_document['id']}/detach",
            json={"product_keys": [new_product_key]},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        updated = response.json()
        assert new_product_key not in updated["product_keys"]
        assert TEST_PRODUCT_KEY in updated["product_keys"]

    def test_delete_document(self, auth_headers):
        """DELETE /api/product-documents/{doc_id} - soft deletes a document."""
        # Create a document to delete
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000052 00000 n 
0000000101 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
178
%%EOF"""
        
        files = {"file": ("test_delete.pdf", pdf_content, "application/pdf")}
        data = {
            "display_name": f"TEST_Delete_{uuid.uuid4().hex[:8]}",
            "document_type": "Technical Datasheet",
            "product_keys": json.dumps([TEST_PRODUCT_KEY])
        }
        
        upload_response = requests.post(
            f"{API_URL}/product-documents/upload",
            files=files,
            data=data,
            headers=auth_headers
        )
        doc_id = upload_response.json()["id"]
        
        # Delete the document
        delete_response = requests.delete(
            f"{API_URL}/product-documents/{doc_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Document deleted"
        
        # Verify it's no longer accessible via download
        download_response = requests.get(
            f"{API_URL}/product-documents/{doc_id}/download"
        )
        assert download_response.status_code == 404
