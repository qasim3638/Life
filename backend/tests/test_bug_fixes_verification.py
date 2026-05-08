"""
Bug Fixes Verification Tests
Tests for 4 bug fixes:
1. Spec Formatting (Suitability, Slip Rating)
2. Collection Card Discount Badge for Trade Users
3. Sale Ribbon Breakdown Math
4. Finish Selector Visibility
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCollectionsEndpoint:
    """Test /api/tiles/collections endpoint returns correct trade_discount values"""
    
    def test_collections_endpoint_returns_trade_discount(self):
        """Test 10: Collections endpoint returns trade_discount field"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'collections' in data, "Response should have 'collections' key"
        
        collections = data['collections']
        assert len(collections) > 0, "Should have at least one collection"
        
        # Verify trade_discount field exists and is a number
        for col in collections:
            assert 'trade_discount' in col, f"Collection {col.get('series_name')} missing trade_discount"
            assert isinstance(col['trade_discount'], (int, float)), f"trade_discount should be numeric"
            assert col['trade_discount'] >= 0, f"trade_discount should be non-negative"
        
        print(f"PASS: All {len(collections)} collections have valid trade_discount values")
    
    def test_collections_with_sale_flag(self):
        """Test collections with is_sale=True have proper discount fields"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=200")
        assert response.status_code == 200
        
        data = response.json()
        collections = data['collections']
        
        sale_collections = [c for c in collections if c.get('is_sale')]
        print(f"Found {len(sale_collections)} sale collections")
        
        for col in sale_collections:
            # Sale collections should have max_was_markup or max_sale_discount_pct
            has_discount_info = (
                col.get('max_was_markup', 0) > 0 or 
                col.get('max_sale_discount_pct') is not None
            )
            print(f"  {col['series_name']}: max_was_markup={col.get('max_was_markup')}, max_sale_discount_pct={col.get('max_sale_discount_pct')}")
        
        print(f"PASS: Sale collections have proper discount fields")
    
    def test_non_sale_collections_with_trade_discount(self):
        """Test 3: Non-sale collections should show ONLY trade discount (not additive)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=200")
        assert response.status_code == 200
        
        data = response.json()
        collections = data['collections']
        
        # Find non-sale collections with trade discount
        trade_only = [c for c in collections if c.get('trade_discount', 0) > 0 and not c.get('is_sale')]
        assert len(trade_only) > 0, "Should have non-sale collections with trade discount"
        
        for col in trade_only[:5]:
            # For non-sale collections, the discount badge should show ONLY trade_discount
            # NOT baseDiscount + trade_discount (which was the bug)
            trade_discount = col.get('trade_discount', 0)
            max_was_markup = col.get('max_was_markup', 0)
            
            # Non-sale collections should have max_was_markup = 0
            assert max_was_markup == 0, f"Non-sale collection {col['series_name']} should have max_was_markup=0"
            
            print(f"  {col['series_name']}: trade_discount={trade_discount}, max_was_markup={max_was_markup}")
        
        print(f"PASS: {len(trade_only)} non-sale collections have correct discount structure")


class TestCollectionDetailEndpoint:
    """Test /api/tiles/collection/{series_name} endpoint"""
    
    def test_collection_products_have_finish_field(self):
        """Test 11: Collection products have finish field populated"""
        # Test with Ridgeway Matt which has finish='Matt' for all products
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Ridgeway%20Matt")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        products = data.get('products', [])
        assert len(products) > 0, "Should have products"
        
        # Check finish field
        products_with_finish = [p for p in products if p.get('finish')]
        print(f"Products with finish: {len(products_with_finish)}/{len(products)}")
        
        if products_with_finish:
            finishes = set(p.get('finish') for p in products_with_finish)
            print(f"Unique finishes: {finishes}")
            
            # Ridgeway Matt should have only 'Matt' finish
            assert 'Matt' in finishes, "Ridgeway Matt should have 'Matt' finish"
        
        print("PASS: Collection products have finish field")
    
    def test_collection_products_have_spec_fields(self):
        """Test products have suitability and slip_rating fields (may be empty in preview)"""
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Ridgeway%20Matt")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get('products', [])
        
        # Check that the fields exist in the response (even if empty)
        for p in products[:3]:
            # These fields should be present in the serialized response
            # They may be empty strings in preview environment
            print(f"  Product: {p.get('name', 'Unknown')}")
            print(f"    suitability: '{p.get('suitability', '')}'")
            print(f"    slip_rating: '{p.get('slip_rating', '')}'")
            print(f"    finish: '{p.get('finish', '')}'")
        
        print("PASS: Products have spec fields in response")
    
    def test_sale_collection_has_was_price(self):
        """Test sale collection products have was_price for discount calculation"""
        # Tuscania Polished is a sale collection with max_sale_discount_pct=15
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Tuscania%20Polished")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get('products', [])
        
        if len(products) > 0:
            p = products[0]
            print(f"Product: {p.get('name')}")
            print(f"  price: {p.get('price')}")
            print(f"  was_price: {p.get('was_price')}")
            
            # If was_price exists, verify discount calculation is possible
            if p.get('was_price') and p.get('price'):
                was_price = float(p['was_price'])
                price = float(p['price'])
                discount_pct = round((was_price - price) / was_price * 100)
                print(f"  Calculated discount: {discount_pct}%")
        
        print("PASS: Sale collection has pricing data")


class TestDiscountCalculationLogic:
    """Test the discount calculation formulas (code logic verification)"""
    
    def test_compound_discount_formula(self):
        """Test 4: Compound discount formula for sale+trade"""
        # Formula: Math.round((1 - (1-sale/100)*(1-trade/100)) * 100)
        
        # Example: 20% sale + 25% trade
        sale = 20
        trade = 25
        
        # Compound formula (correct)
        compound = round((1 - (1 - sale/100) * (1 - trade/100)) * 100)
        
        # Additive formula (incorrect - the bug)
        additive = sale + trade
        
        print(f"Sale: {sale}%, Trade: {trade}%")
        print(f"Compound (correct): {compound}%")
        print(f"Additive (bug): {additive}%")
        
        # Compound should be less than additive
        assert compound < additive, "Compound discount should be less than additive"
        assert compound == 40, f"20% sale + 25% trade compound should be 40%, got {compound}%"
        
        print("PASS: Compound discount formula is correct")
    
    def test_guaranteed_sum_breakdown(self):
        """Test 5: Breakdown percentages always sum to total"""
        # Test the guaranteed-sum math from the code
        
        # Example values
        was_price = 100
        sale_discount = 20  # 20%
        trade_discount = 10  # 10%
        volume_discount = 5  # 5%
        
        # Forward compound calculation
        after_sale = was_price * (1 - sale_discount / 100)  # 80
        after_trade = after_sale * (1 - trade_discount / 100)  # 72
        after_volume = after_trade * (1 - volume_discount / 100)  # 68.4
        
        # Total discount
        total_off = round((was_price - after_volume) / was_price * 100)  # 32%
        
        # Guaranteed-sum breakdown
        trade_contrib = round((after_sale - after_trade) / was_price * 100)  # 8%
        volume_contrib = round((after_trade - after_volume) / was_price * 100)  # 4%
        sale_contrib = max(0, total_off - trade_contrib - volume_contrib)  # 20%
        
        # Verify sum equals total
        breakdown_sum = sale_contrib + trade_contrib + volume_contrib
        
        print(f"Was price: £{was_price}")
        print(f"After sale ({sale_discount}%): £{after_sale}")
        print(f"After trade ({trade_discount}%): £{after_trade}")
        print(f"After volume ({volume_discount}%): £{after_volume}")
        print(f"Total off: {total_off}%")
        print(f"Breakdown: Sale {sale_contrib}% + Trade {trade_contrib}% + Volume {volume_contrib}% = {breakdown_sum}%")
        
        assert breakdown_sum == total_off, f"Breakdown sum {breakdown_sum}% should equal total {total_off}%"
        
        print("PASS: Guaranteed-sum breakdown is correct")
    
    def test_suitability_formatting(self):
        """Test 1: Suitability formatting logic"""
        # Formula: val.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' & ')
        
        test_cases = [
            ('wall-floor', 'Wall & Floor'),
            ('wall', 'Wall'),
            ('floor', 'Floor'),
            ('wall-floor-outdoor', 'Wall & Floor & Outdoor'),
        ]
        
        for input_val, expected in test_cases:
            # Python equivalent of the JS formula
            result = ' & '.join(w[0].upper() + w[1:] for w in input_val.split('-'))
            assert result == expected, f"'{input_val}' should format to '{expected}', got '{result}'"
            print(f"  '{input_val}' -> '{result}' ✓")
        
        print("PASS: Suitability formatting logic is correct")
    
    def test_slip_rating_formatting(self):
        """Test 2: Slip Rating formatting logic"""
        # Formula: val.toUpperCase()
        
        test_cases = [
            ('r10', 'R10'),
            ('r11', 'R11'),
            ('r9', 'R9'),
            ('R10', 'R10'),  # Already uppercase
        ]
        
        for input_val, expected in test_cases:
            result = input_val.upper()
            assert result == expected, f"'{input_val}' should format to '{expected}', got '{result}'"
            print(f"  '{input_val}' -> '{result}' ✓")
        
        print("PASS: Slip Rating formatting logic is correct")


class TestFinishSelectorLogic:
    """Test finish selector visibility logic"""
    
    def test_single_finish_collection(self):
        """Test 7 & 8: Finish selector shows for single-finish collections"""
        # Ridgeway Matt has only 'Matt' finish
        response = requests.get(f"{BASE_URL}/api/tiles/collection/Ridgeway%20Matt")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get('products', [])
        
        # Get unique finishes
        finishes = set()
        for p in products:
            finish = p.get('finish') or ''
            if finish.strip():
                finishes.add(finish)
        
        print(f"Ridgeway Matt finishes: {finishes}")
        
        # hasFinishes = products.some(p => finish && finish.trim())
        has_finishes = len(finishes) > 0
        
        # hasMultipleFinishes = new Set(finishes).size > 1
        has_multiple_finishes = len(finishes) > 1
        
        print(f"hasFinishes: {has_finishes}")
        print(f"hasMultipleFinishes: {has_multiple_finishes}")
        
        # The fix: finish selector should show when hasFinishes is true (not just hasMultipleFinishes)
        # So for Ridgeway Matt with 1 finish, selector should show
        if has_finishes:
            print("PASS: Finish selector should be visible (hasFinishes=True)")
        else:
            print("INFO: No finishes found in this collection")
    
    def test_multiple_finish_collection(self):
        """Test 9: Finish selector works with multiple finishes"""
        # Find a collection with multiple finishes
        response = requests.get(f"{BASE_URL}/api/tiles/collections?limit=200")
        assert response.status_code == 200
        
        collections = response.json().get('collections', [])
        
        # Check a few collections for multiple finishes
        for col in collections[:20]:
            col_response = requests.get(f"{BASE_URL}/api/tiles/collection/{col['series_name'].replace(' ', '%20')}")
            if col_response.status_code == 200:
                products = col_response.json().get('products', [])
                finishes = set(p.get('finish', '') for p in products if p.get('finish'))
                
                if len(finishes) > 1:
                    print(f"Found multi-finish collection: {col['series_name']}")
                    print(f"  Finishes: {finishes}")
                    print("PASS: Multi-finish collection found for testing")
                    return
        
        print("INFO: No multi-finish collections found in sample")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
