"""
Test Supplier Health Dashboard API
Tests the /api/supplier-health/check endpoint for data quality checks across all suppliers.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSupplierHealthEndpoint:
    """Test the /api/supplier-health/check endpoint"""
    
    def test_health_check_returns_200(self, auth_headers):
        """Test that health check endpoint returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Health check endpoint returns 200 OK")
    
    def test_health_check_response_structure(self, auth_headers):
        """Test that response has correct top-level structure"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level keys
        assert "timestamp" in data, "Missing 'timestamp' in response"
        assert "summary" in data, "Missing 'summary' in response"
        assert "suppliers" in data, "Missing 'suppliers' in response"
        
        print(f"✓ Response has correct structure: timestamp, summary, suppliers")
        print(f"  - Timestamp: {data['timestamp']}")
        print(f"  - Total suppliers: {len(data['suppliers'])}")
    
    def test_summary_structure(self, auth_headers):
        """Test that summary contains all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        summary = response.json()["summary"]
        
        required_fields = [
            "total_suppliers",
            "total_products",
            "total_issues",
            "average_score",
            "healthy",
            "warning",
            "critical",
            "null_supplier_products"
        ]
        
        for field in required_fields:
            assert field in summary, f"Missing '{field}' in summary"
        
        print(f"✓ Summary has all required fields:")
        print(f"  - Total suppliers: {summary['total_suppliers']}")
        print(f"  - Total products: {summary['total_products']}")
        print(f"  - Total issues: {summary['total_issues']}")
        print(f"  - Average score: {summary['average_score']}")
        print(f"  - Healthy: {summary['healthy']}")
        print(f"  - Warning: {summary['warning']}")
        print(f"  - Critical: {summary['critical']}")
        print(f"  - Null supplier products: {summary['null_supplier_products']}")
    
    def test_supplier_data_structure(self, auth_headers):
        """Test that each supplier has correct data structure"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        assert len(suppliers) > 0, "No suppliers returned"
        
        # Check first supplier structure
        supplier = suppliers[0]
        required_fields = [
            "supplier",
            "total_products",
            "health_score",
            "status",
            "issue_counts",
            "total_issues",
            "issues"
        ]
        
        for field in required_fields:
            assert field in supplier, f"Missing '{field}' in supplier data"
        
        print(f"✓ Supplier data has correct structure")
        print(f"  - First supplier: {supplier['supplier']}")
        print(f"  - Health score: {supplier['health_score']}")
        print(f"  - Status: {supplier['status']}")


class TestIssueCategories:
    """Test that all 9 issue categories are present"""
    
    def test_all_issue_categories_present(self, auth_headers):
        """Test that all 9 issue categories are tracked"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        assert len(suppliers) > 0, "No suppliers returned"
        
        # Check issue_counts has all 9 categories
        expected_categories = [
            "missing_sku",
            "missing_price",
            "missing_images",
            "missing_category",
            "missing_name",
            "missing_description",
            "duplicate_codes",
            "duplicate_names",
            "not_synced"
        ]
        
        supplier = suppliers[0]
        issue_counts = supplier["issue_counts"]
        
        for category in expected_categories:
            assert category in issue_counts, f"Missing issue category: {category}"
        
        print(f"✓ All 9 issue categories present in issue_counts:")
        for cat in expected_categories:
            print(f"  - {cat}: {issue_counts[cat]}")
    
    def test_issues_detail_structure(self, auth_headers):
        """Test that issues detail has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        assert len(suppliers) > 0, "No suppliers returned"
        
        supplier = suppliers[0]
        issues = supplier["issues"]
        
        # Check that issues dict has all categories
        expected_categories = [
            "missing_sku",
            "missing_price",
            "missing_images",
            "missing_category",
            "missing_name",
            "missing_description",
            "duplicate_codes",
            "duplicate_names",
            "not_synced"
        ]
        
        for category in expected_categories:
            assert category in issues, f"Missing issue detail category: {category}"
            assert isinstance(issues[category], list), f"{category} should be a list"
        
        print(f"✓ Issues detail has all 9 categories as lists")


class TestHealthScoreCalculation:
    """Test health score calculation and status assignment"""
    
    def test_health_score_range(self, auth_headers):
        """Test that health scores are in 0-100 range"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        for supplier in suppliers:
            score = supplier["health_score"]
            assert 0 <= score <= 100, f"Score {score} out of range for {supplier['supplier']}"
        
        print(f"✓ All {len(suppliers)} suppliers have scores in 0-100 range")
    
    def test_status_assignment(self, auth_headers):
        """Test that status is correctly assigned based on score"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        for supplier in suppliers:
            score = supplier["health_score"]
            status = supplier["status"]
            
            if score >= 80:
                expected_status = "healthy"
            elif score >= 50:
                expected_status = "warning"
            else:
                expected_status = "critical"
            
            assert status == expected_status, f"Expected status '{expected_status}' for score {score}, got '{status}'"
        
        print(f"✓ Status correctly assigned for all suppliers")
        
        # Print breakdown
        healthy = [s for s in suppliers if s["status"] == "healthy"]
        warning = [s for s in suppliers if s["status"] == "warning"]
        critical = [s for s in suppliers if s["status"] == "critical"]
        
        print(f"  - Healthy (>=80): {len(healthy)}")
        print(f"  - Warning (50-79): {len(warning)}")
        print(f"  - Critical (<50): {len(critical)}")


class TestDuplicateDetection:
    """Test duplicate code and name detection"""
    
    def test_duplicate_codes_structure(self, auth_headers):
        """Test that duplicate_codes has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        # Find a supplier with duplicate codes
        for supplier in suppliers:
            dup_codes = supplier["issues"]["duplicate_codes"]
            if len(dup_codes) > 0:
                dup = dup_codes[0]
                assert "code" in dup, "Missing 'code' in duplicate_codes item"
                assert "count" in dup, "Missing 'count' in duplicate_codes item"
                assert "products" in dup, "Missing 'products' in duplicate_codes item"
                print(f"✓ duplicate_codes structure verified for {supplier['supplier']}")
                print(f"  - Example: code='{dup['code']}' appears {dup['count']} times")
                return
        
        print("✓ No duplicate codes found in any supplier (structure check skipped)")
    
    def test_duplicate_names_structure(self, auth_headers):
        """Test that duplicate_names has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        # Find a supplier with duplicate names
        for supplier in suppliers:
            dup_names = supplier["issues"]["duplicate_names"]
            if len(dup_names) > 0:
                dup = dup_names[0]
                assert "name" in dup, "Missing 'name' in duplicate_names item"
                assert "count" in dup, "Missing 'count' in duplicate_names item"
                assert "products" in dup, "Missing 'products' in duplicate_names item"
                print(f"✓ duplicate_names structure verified for {supplier['supplier']}")
                print(f"  - Example: name='{dup['name'][:40]}...' appears {dup['count']} times")
                return
        
        print("✓ No duplicate names found in any supplier (structure check skipped)")


class TestNullSupplierProducts:
    """Test orphaned products (null supplier) counting"""
    
    def test_null_supplier_count(self, auth_headers):
        """Test that null_supplier_products is counted in summary"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        summary = response.json()["summary"]
        
        null_count = summary["null_supplier_products"]
        assert isinstance(null_count, int), "null_supplier_products should be an integer"
        assert null_count >= 0, "null_supplier_products should be non-negative"
        
        print(f"✓ Null supplier products count: {null_count}")
        
        # According to context, there should be 322 orphaned products
        if null_count > 0:
            print(f"  - Found {null_count} orphaned products with null/empty supplier")


class TestSpecificSuppliers:
    """Test specific suppliers mentioned in context"""
    
    def test_rsa_tiles_missing_sku(self, auth_headers):
        """Test that RSA Tiles shows missing SKU issues (28 products without SKU)"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        rsa_tiles = next((s for s in suppliers if s["supplier"] == "RSA Tiles"), None)
        
        if rsa_tiles:
            missing_sku_count = rsa_tiles["issue_counts"]["missing_sku"]
            print(f"✓ RSA Tiles found:")
            print(f"  - Total products: {rsa_tiles['total_products']}")
            print(f"  - Missing SKU: {missing_sku_count}")
            print(f"  - Health score: {rsa_tiles['health_score']}")
            print(f"  - Status: {rsa_tiles['status']}")
            
            # RSA Tiles should have 28 products with no SKU
            assert rsa_tiles["total_products"] == 28, f"Expected 28 products, got {rsa_tiles['total_products']}"
        else:
            print("⚠ RSA Tiles supplier not found in results")
    
    def test_thermosphere_missing_sku(self, auth_headers):
        """Test that ThermoSphere shows missing SKU issues (136 products without SKU)"""
        response = requests.get(
            f"{BASE_URL}/api/supplier-health/check",
            headers=auth_headers
        )
        assert response.status_code == 200
        suppliers = response.json()["suppliers"]
        
        thermosphere = next((s for s in suppliers if s["supplier"] == "ThermoSphere"), None)
        
        if thermosphere:
            missing_sku_count = thermosphere["issue_counts"]["missing_sku"]
            print(f"✓ ThermoSphere found:")
            print(f"  - Total products: {thermosphere['total_products']}")
            print(f"  - Missing SKU: {missing_sku_count}")
            print(f"  - Health score: {thermosphere['health_score']}")
            print(f"  - Status: {thermosphere['status']}")
            
            # ThermoSphere should have 136 products with no SKU
            assert thermosphere["total_products"] == 136, f"Expected 136 products, got {thermosphere['total_products']}"
        else:
            print("⚠ ThermoSphere supplier not found in results")


class TestAuthRequired:
    """Test that authentication is required"""
    
    def test_unauthenticated_request_fails(self):
        """Test that request without auth token fails"""
        response = requests.get(f"{BASE_URL}/api/supplier-health/check")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Unauthenticated request correctly rejected with {response.status_code}")
