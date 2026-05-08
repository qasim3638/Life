"""
Test Homepage Image Management Features
- GET /api/filters/homepage-styles/all - returns all style filter values for admin
- PATCH /api/filters/homepage-styles/update-value - toggle show_on_homepage and update image_url
- PUT /api/website-admin/categories/{id} - update image_url for a category
- POST /api/website-admin/upload-image - image file upload
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')


class TestHomepageStylesAPI:
    """Test the homepage styles endpoints for Shop by Styles section"""
    
    def test_get_all_styles_for_admin(self):
        """GET /api/filters/homepage-styles/all returns list of all style filter values"""
        response = requests.get(f"{BASE_URL}/api/filters/homepage-styles/all")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If there are styles, verify structure
        if len(data) > 0:
            style = data[0]
            assert "filter_id" in style, "Style should have filter_id"
            assert "filter_slug" in style, "Style should have filter_slug"
            assert "value" in style, "Style should have value"
            assert "label" in style, "Style should have label"
            assert "show_on_homepage" in style, "Style should have show_on_homepage"
            print(f"SUCCESS: Found {len(data)} styles. First style: {style['label']} (show_on_homepage={style['show_on_homepage']})")
        else:
            print("INFO: No styles found in database - this is OK for a fresh setup")
    
    def test_get_homepage_styles_public(self):
        """GET /api/filters/homepage-styles returns only styles marked for homepage"""
        response = requests.get(f"{BASE_URL}/api/filters/homepage-styles")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # All returned styles should have show_on_homepage=True (implicitly)
        print(f"SUCCESS: Found {len(data)} homepage styles")
        for style in data:
            assert "name" in style, "Style should have name"
            assert "link" in style, "Style should have link"
    
    def test_update_style_homepage_toggle(self):
        """PATCH /api/filters/homepage-styles/update-value can toggle show_on_homepage"""
        # First get all styles to find one to test with
        all_styles_res = requests.get(f"{BASE_URL}/api/filters/homepage-styles/all")
        
        if all_styles_res.status_code != 200:
            pytest.skip("Cannot get styles list")
        
        styles = all_styles_res.json()
        if len(styles) == 0:
            pytest.skip("No styles available to test with")
        
        # Pick the first style
        test_style = styles[0]
        original_show = test_style.get("show_on_homepage", False)
        
        # Toggle the show_on_homepage value
        update_response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={
                "filter_id": test_style["filter_id"],
                "value": test_style["value"],
                "show_on_homepage": not original_show
            }
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        result = update_response.json()
        assert "message" in result, "Response should have message"
        print(f"SUCCESS: Toggled {test_style['label']} show_on_homepage from {original_show} to {not original_show}")
        
        # Revert the change
        revert_response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={
                "filter_id": test_style["filter_id"],
                "value": test_style["value"],
                "show_on_homepage": original_show
            }
        )
        assert revert_response.status_code == 200, "Revert should succeed"
        print(f"SUCCESS: Reverted {test_style['label']} back to show_on_homepage={original_show}")
    
    def test_update_style_image_url(self):
        """PATCH /api/filters/homepage-styles/update-value can update image_url"""
        # First get all styles
        all_styles_res = requests.get(f"{BASE_URL}/api/filters/homepage-styles/all")
        
        if all_styles_res.status_code != 200:
            pytest.skip("Cannot get styles list")
        
        styles = all_styles_res.json()
        if len(styles) == 0:
            pytest.skip("No styles available to test with")
        
        test_style = styles[0]
        original_image = test_style.get("image_url", "")
        test_image_url = "https://example.com/test-style-image.jpg"
        
        # Update the image URL
        update_response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={
                "filter_id": test_style["filter_id"],
                "value": test_style["value"],
                "image_url": test_image_url
            }
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        print(f"SUCCESS: Updated {test_style['label']} image_url to {test_image_url}")
        
        # Verify the update by fetching again
        verify_res = requests.get(f"{BASE_URL}/api/filters/homepage-styles/all")
        verify_styles = verify_res.json()
        updated_style = next((s for s in verify_styles if s["value"] == test_style["value"] and s["filter_id"] == test_style["filter_id"]), None)
        
        if updated_style:
            assert updated_style.get("image_url") == test_image_url, f"Image URL should be updated. Got: {updated_style.get('image_url')}"
            print(f"SUCCESS: Verified image_url was persisted correctly")
        
        # Revert the change
        revert_response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={
                "filter_id": test_style["filter_id"],
                "value": test_style["value"],
                "image_url": original_image
            }
        )
        assert revert_response.status_code == 200, "Revert should succeed"
    
    def test_update_style_validation(self):
        """PATCH /api/filters/homepage-styles/update-value validates required fields"""
        # Missing filter_id
        response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={"value": "test", "show_on_homepage": True}
        )
        assert response.status_code == 400, "Should fail without filter_id"
        
        # Missing value
        response = requests.patch(
            f"{BASE_URL}/api/filters/homepage-styles/update-value",
            json={"filter_id": "123", "show_on_homepage": True}
        )
        assert response.status_code == 400, "Should fail without value"
        
        print("SUCCESS: Validation works correctly for missing required fields")


class TestCategoryImageUpdate:
    """Test category image update via PUT /api/website-admin/categories/{id}"""
    
    def test_get_categories(self):
        """GET /api/website-admin/categories returns list of categories"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"SUCCESS: Found {len(data)} categories")
        
        if len(data) > 0:
            cat = data[0]
            assert "name" in cat, "Category should have name"
            assert "slug" in cat, "Category should have slug"
            print(f"First category: {cat['name']} (slug: {cat['slug']})")
    
    def test_get_homepage_categories(self):
        """GET /api/website-admin/categories/homepage returns homepage categories"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/homepage")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"SUCCESS: Found {len(data)} homepage categories")
        
        for cat in data:
            assert "name" in cat, "Category should have name"
            assert "slug" in cat, "Category should have slug"
    
    def test_update_category_image_url(self):
        """PUT /api/website-admin/categories/{id} can update image_url"""
        # First get categories
        categories_res = requests.get(f"{BASE_URL}/api/website-admin/categories")
        
        if categories_res.status_code != 200:
            pytest.skip("Cannot get categories list")
        
        categories = categories_res.json()
        if len(categories) == 0:
            pytest.skip("No categories available to test with")
        
        # Find a category with an id
        test_cat = None
        for cat in categories:
            if cat.get("id") or cat.get("_id"):
                test_cat = cat
                break
        
        if not test_cat:
            pytest.skip("No category with ID found")
        
        cat_id = test_cat.get("id") or test_cat.get("_id")
        original_image = test_cat.get("image_url", "")
        test_image_url = "https://example.com/test-category-image.jpg"
        
        # Update the category with new image URL
        update_data = {
            "name": test_cat["name"],
            "slug": test_cat["slug"],
            "description": test_cat.get("description", ""),
            "image_url": test_image_url,
            "is_active": test_cat.get("is_active", True),
            "show_on_homepage": test_cat.get("show_on_homepage", False)
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/website-admin/categories/{cat_id}",
            json=update_data
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        print(f"SUCCESS: Updated category '{test_cat['name']}' image_url")
        
        # Verify the update
        verify_res = requests.get(f"{BASE_URL}/api/website-admin/categories/{cat_id}")
        if verify_res.status_code == 200:
            updated_cat = verify_res.json()
            assert updated_cat.get("image_url") == test_image_url, f"Image URL should be updated. Got: {updated_cat.get('image_url')}"
            print(f"SUCCESS: Verified image_url was persisted: {test_image_url}")
        
        # Revert the change
        update_data["image_url"] = original_image
        revert_response = requests.put(
            f"{BASE_URL}/api/website-admin/categories/{cat_id}",
            json=update_data
        )
        assert revert_response.status_code == 200, "Revert should succeed"
        print(f"SUCCESS: Reverted category image_url back to original")


class TestImageUpload:
    """Test image upload endpoint POST /api/website-admin/upload-image"""
    
    def test_upload_image_endpoint_exists(self):
        """POST /api/website-admin/upload-image endpoint exists and validates input"""
        # Test without file - should return 422 (validation error)
        response = requests.post(f"{BASE_URL}/api/website-admin/upload-image")
        
        # Should fail with validation error (no file provided)
        assert response.status_code in [400, 422], f"Expected 400 or 422 without file, got {response.status_code}"
        print(f"SUCCESS: Upload endpoint exists and validates input (status: {response.status_code})")
    
    def test_upload_image_with_test_file(self):
        """POST /api/website-admin/upload-image accepts image file upload"""
        # Create a simple test image (1x1 pixel PNG)
        import base64
        
        # Minimal valid PNG (1x1 transparent pixel)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        
        files = {
            'file': ('test_image.png', png_data, 'image/png')
        }
        data = {
            'folder': 'test'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/upload-image",
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "url" in result, "Response should contain url"
        assert "filename" in result, "Response should contain filename"
        
        print(f"SUCCESS: Image uploaded successfully")
        print(f"  URL: {result['url']}")
        print(f"  Filename: {result['filename']}")
        print(f"  Storage: {result.get('storage', 'unknown')}")
    
    def test_upload_invalid_file_type(self):
        """POST /api/website-admin/upload-image rejects invalid file types"""
        # Try to upload a text file
        files = {
            'file': ('test.txt', b'This is not an image', 'text/plain')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/upload-image",
            files=files
        )
        
        # Should reject non-image files
        assert response.status_code == 400, f"Expected 400 for invalid file type, got {response.status_code}"
        print("SUCCESS: Invalid file type correctly rejected")


class TestHomepageCategoriesDisplay:
    """Test that homepage categories show unique images"""
    
    def test_homepage_categories_have_images(self):
        """Verify homepage categories can have unique images"""
        response = requests.get(f"{BASE_URL}/api/website-admin/categories/homepage")
        
        assert response.status_code == 200
        
        categories = response.json()
        
        if len(categories) == 0:
            print("INFO: No homepage categories configured")
            return
        
        # Check that categories have image_url field
        images = []
        for cat in categories:
            image = cat.get("image_url", "")
            images.append(image)
            print(f"  {cat['name']}: {image[:50] if image else '(no image)'}...")
        
        # Check for unique images (not all identical)
        unique_images = set(img for img in images if img)
        if len(unique_images) > 1:
            print(f"SUCCESS: Found {len(unique_images)} unique images across {len(categories)} categories")
        elif len(unique_images) == 1:
            print(f"WARNING: All {len(categories)} categories have the same image")
        else:
            print(f"INFO: No images set for homepage categories")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
