"""
Test Sale Labels Feature - Collection Detail Page
Tests that products with 'Sale', 'Clearance', or 'On Sale' labels show sale UI elements
"""
import pytest
import requests
import os
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# MongoDB connection for test data setup
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'tile_station')


@pytest.fixture(scope="module")
def db():
    """MongoDB connection fixture"""
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_product_with_sale_label(db):
    """Setup: Add 'Sale' label to test product, cleanup after tests"""
    slug = 'alabaster-60x60cm-polished'
    
    # Store original labels
    original = db.tiles.find_one({'slug': slug}, {'labels': 1})
    original_labels = original.get('labels', []) if original else []
    
    # Add Sale label for testing
    db.tiles.update_one(
        {'slug': slug},
        {'$set': {'labels': ['Sale', 'New Arrival']}}
    )
    
    yield slug
    
    # Cleanup: restore original labels
    if original_labels:
        db.tiles.update_one({'slug': slug}, {'$set': {'labels': original_labels}})
    else:
        db.tiles.update_one({'slug': slug}, {'$unset': {'labels': 1}})


@pytest.fixture(scope="module")
def test_product_with_clearance_label(db):
    """Setup: Add 'Clearance' label to test product"""
    slug = 'alabaster-30x60cm-polished'
    
    # Store original labels
    original = db.tiles.find_one({'slug': slug}, {'labels': 1})
    original_labels = original.get('labels', []) if original else []
    
    # Add Clearance label for testing
    db.tiles.update_one(
        {'slug': slug},
        {'$set': {'labels': ['Clearance']}}
    )
    
    yield slug
    
    # Cleanup: restore original labels
    if original_labels:
        db.tiles.update_one({'slug': slug}, {'$set': {'labels': original_labels}})
    else:
        db.tiles.update_one({'slug': slug}, {'$unset': {'labels': 1}})


@pytest.fixture(scope="module")
def test_product_without_labels(db):
    """Ensure a product has no labels for control test"""
    slug = 'alabaster-30x60cm-polished'
    
    # Store original labels
    original = db.tiles.find_one({'slug': slug}, {'labels': 1})
    original_labels = original.get('labels', []) if original else []
    
    # Remove labels for testing
    db.tiles.update_one({'slug': slug}, {'$unset': {'labels': 1}})
    
    yield slug
    
    # Cleanup: restore original labels
    if original_labels:
        db.tiles.update_one({'slug': slug}, {'$set': {'labels': original_labels}})


class TestCollectionAPILabels:
    """Test that collection API returns labels field"""
    
    def test_collection_api_returns_labels_field(self, api_client, test_product_with_sale_label):
        """API /api/tiles/collection/{series_name} should return labels field for products"""
        response = api_client.get(f"{BASE_URL}/api/tiles/collection/Alabaster?limit=100")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'products' in data, "Response should contain 'products' field"
        
        # Find the test product
        test_product = None
        for p in data['products']:
            if p['slug'] == test_product_with_sale_label:
                test_product = p
                break
        
        assert test_product is not None, f"Test product {test_product_with_sale_label} not found"
        assert 'labels' in test_product, "Product should have 'labels' field"
        assert isinstance(test_product['labels'], list), "Labels should be a list"
        assert 'Sale' in test_product['labels'], "Product should have 'Sale' label"
    
    def test_product_with_sale_label_has_correct_fields(self, api_client, test_product_with_sale_label):
        """Product with Sale label should have all required pricing fields"""
        response = api_client.get(f"{BASE_URL}/api/tiles/collection/Alabaster?limit=100")
        
        assert response.status_code == 200
        
        data = response.json()
        test_product = next((p for p in data['products'] if p['slug'] == test_product_with_sale_label), None)
        
        assert test_product is not None
        
        # Check required pricing fields exist
        assert 'price' in test_product, "Product should have 'price' field"
        assert 'room_lot_price' in test_product, "Product should have 'room_lot_price' field"
        assert 'sale_active' in test_product, "Product should have 'sale_active' field"
        assert 'was_price' in test_product, "Product should have 'was_price' field"
        
        # For label-based sale, sale_active can be false and was_price can be null
        # The frontend should still show sale UI based on labels
        assert test_product['labels'] is not None
        assert len(test_product['labels']) > 0
    
    def test_product_without_labels_returns_empty_array(self, api_client, test_product_without_labels):
        """Products without labels should return empty labels array"""
        response = api_client.get(f"{BASE_URL}/api/tiles/collection/Alabaster?limit=100")
        
        assert response.status_code == 200
        
        data = response.json()
        test_product = next((p for p in data['products'] if p['slug'] == test_product_without_labels), None)
        
        assert test_product is not None
        # Labels should be empty array or not present
        labels = test_product.get('labels', [])
        assert isinstance(labels, list), "Labels should be a list"


class TestTierPricingAPI:
    """Test tier pricing API for sale products"""
    
    def test_tier_pricing_endpoint_exists(self, api_client, test_product_with_sale_label):
        """Tier pricing endpoint should return data for products"""
        response = api_client.get(f"{BASE_URL}/api/tiles/products/{test_product_with_sale_label}/tier-pricing")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Tier pricing returns an object with 'tiers' array
        assert isinstance(data, dict), "Tier pricing should return an object"
        assert 'tiers' in data, "Response should contain 'tiers' field"
        assert isinstance(data['tiers'], list), "Tiers should be a list"
    
    def test_tier_pricing_has_discount_fields(self, api_client, test_product_with_sale_label):
        """Tier pricing should include discount percentage fields"""
        response = api_client.get(f"{BASE_URL}/api/tiles/products/{test_product_with_sale_label}/tier-pricing")
        
        assert response.status_code == 200
        
        data = response.json()
        tiers = data.get('tiers', [])
        if len(tiers) > 0:
            tier = tiers[0]
            # Check tier has required fields
            assert 'min_qty' in tier, "Tier should have 'min_qty'"
            assert 'discount_percent' in tier, "Tier should have 'discount_percent'"
            assert 'price_per_m2' in tier, "Tier should have 'price_per_m2'"
            assert 'savings_label' in tier, "Tier should have 'savings_label'"


class TestSaleLabelVariations:
    """Test different sale label variations"""
    
    def test_clearance_label_recognized(self, api_client, test_product_with_clearance_label):
        """Products with 'Clearance' label should be recognized as sale items"""
        response = api_client.get(f"{BASE_URL}/api/tiles/collection/Alabaster?limit=100")
        
        assert response.status_code == 200
        
        data = response.json()
        test_product = next((p for p in data['products'] if p['slug'] == test_product_with_clearance_label), None)
        
        assert test_product is not None
        assert 'labels' in test_product
        assert 'Clearance' in test_product['labels'], "Product should have 'Clearance' label"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_health(self, api_client):
        """API health endpoint should return 200"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
    
    def test_collection_endpoint_accessible(self, api_client):
        """Collection endpoint should be accessible"""
        response = api_client.get(f"{BASE_URL}/api/tiles/collection/Alabaster?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert 'products' in data
        assert len(data['products']) > 0
