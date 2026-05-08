"""
Test Hero Image Upload Feature
Tests the /api/upload-image endpoint and related functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://feature-verification-7.preview.emergentagent.com')

class TestHeroImageUpload:
    """Tests for hero carousel image upload functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login and get auth token"""
        # Login to get auth token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "Admin@2026"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_upload_image_endpoint_exists(self):
        """Test that /api/upload-image endpoint exists and requires auth"""
        # Test without auth - should fail
        response = requests.post(f"{BASE_URL}/api/upload-image")
        assert response.status_code in [401, 403, 422], "Endpoint should require authentication"
        print("PASS: Upload endpoint requires authentication")
    
    def test_upload_image_with_valid_file(self):
        """Test uploading a valid image file"""
        import base64
        
        # Create a small test PNG image (1x1 pixel)
        test_image_data = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        )
        
        files = {'file': ('test_image.png', test_image_data, 'image/png')}
        response = requests.post(
            f"{BASE_URL}/api/upload-image",
            headers=self.headers,
            files=files
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert 'url' in data, "Response should contain 'url'"
        assert 'filename' in data, "Response should contain 'filename'"
        assert 'storage' in data, "Response should contain 'storage'"
        
        # Verify URL is from R2 storage
        assert 'images.tilestation.co.uk' in data['url'] or data['storage'] == 'r2', \
            "Image should be uploaded to R2 storage"
        
        print(f"PASS: Image uploaded successfully to {data['storage']}")
        print(f"URL: {data['url']}")
    
    def test_upload_image_invalid_file_type(self):
        """Test that invalid file types are rejected"""
        # Try to upload a text file
        files = {'file': ('test.txt', b'This is not an image', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/upload-image",
            headers=self.headers,
            files=files
        )
        
        assert response.status_code == 400, "Should reject non-image files"
        print("PASS: Invalid file type rejected")
    
    def test_upload_image_jpeg(self):
        """Test uploading a JPEG image"""
        import base64
        
        # Minimal valid JPEG (1x1 pixel red)
        jpeg_data = base64.b64decode(
            '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof'
            'Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh'
            'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR'
            'CAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAA'
            'AAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMB'
            'AAIRAxEAPwCwAB//2Q=='
        )
        
        files = {'file': ('test.jpg', jpeg_data, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/upload-image",
            headers=self.headers,
            files=files
        )
        
        assert response.status_code == 200, f"JPEG upload failed: {response.text}"
        data = response.json()
        assert 'url' in data
        print("PASS: JPEG image uploaded successfully")
    
    def test_upload_image_webp(self):
        """Test uploading a WebP image"""
        import base64
        
        # Minimal valid WebP (1x1 pixel)
        webp_data = base64.b64decode(
            'UklGRlYAAABXRUJQVlA4IEoAAADQAQCdASoBAAEAAUAmJYgCdAEO/hOMAAD++O9P/v3/3/7d'
            '/t3+3f7d/t3+3f7d/t3+3f7d/t3+3f7d/t3+3f7d/t3+3f7d/t3+3f7d/t0A'
        )
        
        files = {'file': ('test.webp', webp_data, 'image/webp')}
        response = requests.post(
            f"{BASE_URL}/api/upload-image",
            headers=self.headers,
            files=files
        )
        
        assert response.status_code == 200, f"WebP upload failed: {response.text}"
        data = response.json()
        assert 'url' in data
        print("PASS: WebP image uploaded successfully")
    
    def test_hero_slides_api_get(self):
        """Test fetching hero slides"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/hero-slides",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to get hero slides: {response.text}"
        data = response.json()
        
        # Should return slides array
        slides = data.get('slides', data) if isinstance(data, dict) else data
        assert isinstance(slides, list), "Should return a list of slides"
        print(f"PASS: Retrieved {len(slides)} hero slides")
    
    def test_hero_slides_api_save(self):
        """Test saving hero slides with uploaded image URL"""
        # First get existing slides
        get_response = requests.get(
            f"{BASE_URL}/api/website-admin/hero-slides",
            headers=self.headers
        )
        assert get_response.status_code == 200
        
        existing_data = get_response.json()
        slides = existing_data.get('slides', existing_data) if isinstance(existing_data, dict) else existing_data
        
        # Save slides back (no changes, just verify save works)
        save_response = requests.post(
            f"{BASE_URL}/api/website-admin/hero-slides",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"slides": slides}
        )
        
        assert save_response.status_code == 200, f"Failed to save hero slides: {save_response.text}"
        print("PASS: Hero slides saved successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
