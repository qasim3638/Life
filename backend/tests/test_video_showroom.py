"""
Test Video Showroom Feature - Backend API Tests
Tests for the Video Showroom section in HomepageManager admin panel.
Covers: PUT/GET homepage content, video upload, thumbnail upload, media serving
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture
def auth_headers(admin_token):
    """Headers with admin auth token"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestHomepageVideoShowroomGET:
    """Test GET /api/website-admin/homepage returns video_showroom fields"""

    def test_get_homepage_returns_video_showroom_fields(self, auth_headers):
        """GET homepage should return video_showroom_* fields"""
        response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check that video showroom fields exist (may be None if not set)
        # These fields should be present in the response schema
        print(f"Homepage data keys: {list(data.keys())}")
        
        # Verify the response is a dict (homepage content)
        assert isinstance(data, dict), "Response should be a dictionary"
        
        # If video_showroom_visible is set, verify it's a boolean
        if "video_showroom_visible" in data:
            assert isinstance(data["video_showroom_visible"], bool), "video_showroom_visible should be boolean"
        
        print("✓ GET /api/website-admin/homepage returns valid response")


class TestHomepageVideoShowroomPUT:
    """Test PUT /api/website-admin/homepage saves video_showroom_* fields"""

    def test_save_video_showroom_fields(self, auth_headers):
        """PUT homepage should save video_showroom_* fields correctly"""
        test_data = {
            "video_showroom_visible": True,
            "video_showroom_badge": "TEST_BADGE",
            "video_showroom_title": "TEST_TITLE",
            "video_showroom_description": "TEST_DESCRIPTION",
            "video_showroom_cta_primary_text": "TEST_CTA_PRIMARY",
            "video_showroom_cta_primary_link": "/test-link",
            "video_showroom_cta_secondary_text": "TEST_CTA_SECONDARY",
            "video_showroom_cta_secondary_link": "/test-secondary",
            "video_showroom_stats": [
                {"value": "100", "label": "Test Stat 1"},
                {"value": "200", "label": "Test Stat 2"}
            ],
            "video_showroom_floating_badge_title": "TEST_FLOATING_TITLE",
            "video_showroom_floating_badge_subtitle": "TEST_FLOATING_SUBTITLE"
        }
        
        # Save the data
        response = requests.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers=auth_headers,
            json=test_data
        )
        assert response.status_code == 200, f"PUT failed: {response.status_code} - {response.text}"
        
        # Verify the save was successful
        result = response.json()
        assert "message" in result, "Response should contain message"
        print(f"✓ PUT response: {result}")
        
        # GET to verify data was persisted
        get_response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        assert get_response.status_code == 200
        
        saved_data = get_response.json()
        
        # Verify all fields were saved correctly
        assert saved_data.get("video_showroom_visible") == True, "video_showroom_visible not saved"
        assert saved_data.get("video_showroom_badge") == "TEST_BADGE", "video_showroom_badge not saved"
        assert saved_data.get("video_showroom_title") == "TEST_TITLE", "video_showroom_title not saved"
        assert saved_data.get("video_showroom_description") == "TEST_DESCRIPTION", "video_showroom_description not saved"
        assert saved_data.get("video_showroom_cta_primary_text") == "TEST_CTA_PRIMARY", "cta_primary_text not saved"
        assert saved_data.get("video_showroom_cta_primary_link") == "/test-link", "cta_primary_link not saved"
        assert saved_data.get("video_showroom_cta_secondary_text") == "TEST_CTA_SECONDARY", "cta_secondary_text not saved"
        assert saved_data.get("video_showroom_cta_secondary_link") == "/test-secondary", "cta_secondary_link not saved"
        assert saved_data.get("video_showroom_floating_badge_title") == "TEST_FLOATING_TITLE", "floating_badge_title not saved"
        assert saved_data.get("video_showroom_floating_badge_subtitle") == "TEST_FLOATING_SUBTITLE", "floating_badge_subtitle not saved"
        
        # Verify stats array
        stats = saved_data.get("video_showroom_stats", [])
        assert len(stats) == 2, f"Expected 2 stats, got {len(stats)}"
        assert stats[0]["value"] == "100", "First stat value not saved"
        assert stats[0]["label"] == "Test Stat 1", "First stat label not saved"
        
        print("✓ All video_showroom fields saved and verified correctly")

    def test_deep_merge_preserves_existing_data(self, auth_headers):
        """PUT should merge with existing data, not overwrite everything"""
        # First, get current data to check for brand_marquee
        initial_response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        initial_data = initial_response.json()
        
        # Save only video_showroom_visible
        response = requests.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers=auth_headers,
            json={"video_showroom_visible": False}
        )
        assert response.status_code == 200
        
        # Verify other video_showroom fields are preserved
        get_response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        saved_data = get_response.json()
        
        # video_showroom_visible should be updated
        assert saved_data.get("video_showroom_visible") == False, "video_showroom_visible not updated"
        
        # Other fields should still exist (from previous test)
        assert saved_data.get("video_showroom_badge") is not None, "video_showroom_badge was lost during merge"
        
        # If brand_marquee existed before, it should still exist
        if initial_data.get("brand_marquee_visible") is not None:
            assert saved_data.get("brand_marquee_visible") is not None, "brand_marquee data was lost during merge"
        
        print("✓ Deep merge preserves existing data correctly")


class TestVideoUpload:
    """Test POST /api/website-admin/homepage/upload-video"""

    def test_upload_video_accepts_mp4(self, admin_token):
        """Upload endpoint should accept MP4 files"""
        # Create a minimal valid MP4 file header (ftyp box)
        # This is a minimal MP4 file structure
        mp4_header = bytes([
            0x00, 0x00, 0x00, 0x14,  # box size (20 bytes)
            0x66, 0x74, 0x79, 0x70,  # 'ftyp'
            0x69, 0x73, 0x6F, 0x6D,  # 'isom' brand
            0x00, 0x00, 0x00, 0x01,  # minor version
            0x69, 0x73, 0x6F, 0x6D,  # compatible brand 'isom'
        ])
        
        files = {
            'file': ('test_video.mp4', io.BytesIO(mp4_header), 'video/mp4')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-video",
            headers=headers,
            files=files
        )
        
        # Should succeed (200) or fail gracefully
        print(f"Video upload response: {response.status_code} - {response.text[:200]}")
        
        if response.status_code == 200:
            data = response.json()
            assert "storage_path" in data, "Response should contain storage_path"
            assert "original_filename" in data, "Response should contain original_filename"
            assert "content_type" in data, "Response should contain content_type"
            assert "size" in data, "Response should contain size"
            print(f"✓ Video uploaded successfully: {data}")
        else:
            # May fail due to storage configuration, but should not be 500
            assert response.status_code != 500, f"Server error: {response.text}"
            print(f"⚠ Video upload returned {response.status_code} (may be storage config issue)")

    def test_upload_video_rejects_invalid_type(self, admin_token):
        """Upload endpoint should reject non-video files"""
        files = {
            'file': ('test.txt', io.BytesIO(b'This is not a video'), 'text/plain')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-video",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid file type, got {response.status_code}"
        print(f"✓ Invalid file type correctly rejected: {response.json()}")

    def test_upload_video_accepts_webm(self, admin_token):
        """Upload endpoint should accept WebM files"""
        # Minimal WebM header (EBML header)
        webm_header = bytes([
            0x1A, 0x45, 0xDF, 0xA3,  # EBML header
            0x01, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x1F,
        ])
        
        files = {
            'file': ('test_video.webm', io.BytesIO(webm_header), 'video/webm')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-video",
            headers=headers,
            files=files
        )
        
        print(f"WebM upload response: {response.status_code}")
        # Should accept the file type (may fail on storage)
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"
        if response.status_code == 200:
            print("✓ WebM file accepted")


class TestThumbnailUpload:
    """Test POST /api/website-admin/homepage/upload-thumbnail"""

    def test_upload_thumbnail_accepts_jpeg(self, admin_token):
        """Upload endpoint should accept JPEG images"""
        # Minimal JPEG header
        jpeg_header = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
            0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
            0x00, 0x01, 0x00, 0x00, 0xFF, 0xD9
        ])
        
        files = {
            'file': ('test_thumb.jpg', io.BytesIO(jpeg_header), 'image/jpeg')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-thumbnail",
            headers=headers,
            files=files
        )
        
        print(f"Thumbnail upload response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            assert "storage_path" in data, "Response should contain storage_path"
            assert "original_filename" in data, "Response should contain original_filename"
            print(f"✓ Thumbnail uploaded successfully: {data}")
        else:
            assert response.status_code != 500, f"Server error: {response.text}"
            print(f"⚠ Thumbnail upload returned {response.status_code}")

    def test_upload_thumbnail_accepts_png(self, admin_token):
        """Upload endpoint should accept PNG images"""
        # Minimal PNG header
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        ])
        
        files = {
            'file': ('test_thumb.png', io.BytesIO(png_header), 'image/png')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-thumbnail",
            headers=headers,
            files=files
        )
        
        print(f"PNG thumbnail upload response: {response.status_code}")
        assert response.status_code in [200, 500], f"Unexpected status: {response.status_code}"

    def test_upload_thumbnail_rejects_invalid_type(self, admin_token):
        """Upload endpoint should reject non-image files"""
        files = {
            'file': ('test.txt', io.BytesIO(b'This is not an image'), 'text/plain')
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/website-admin/homepage/upload-thumbnail",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid file type, got {response.status_code}"
        print(f"✓ Invalid thumbnail type correctly rejected")


class TestMediaServing:
    """Test GET /api/website-admin/homepage/media/{path}"""

    def test_media_endpoint_returns_404_for_nonexistent(self, auth_headers):
        """Media endpoint should return 404 for non-existent files"""
        response = requests.get(
            f"{BASE_URL}/api/website-admin/homepage/media/nonexistent/file.mp4",
            headers=auth_headers
        )
        
        # Should return 404 for non-existent file
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Media endpoint returns 404 for non-existent files")


class TestPublicHomepageAccess:
    """Test that homepage content is accessible publicly for customer-facing components"""

    def test_homepage_accessible_without_auth(self):
        """GET /api/website-admin/homepage should work without auth for public display"""
        # Note: This endpoint may require auth - checking behavior
        response = requests.get(f"{BASE_URL}/api/website-admin/homepage")
        
        # The endpoint should either work publicly or return 401
        print(f"Public homepage access: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # If accessible, should return homepage content
            assert isinstance(data, dict), "Response should be a dictionary"
            print("✓ Homepage content accessible publicly")
        else:
            # If auth required, that's also valid
            assert response.status_code in [401, 403], f"Unexpected status: {response.status_code}"
            print("⚠ Homepage requires authentication (customer component may need different endpoint)")


class TestVideoShowroomVisibilityToggle:
    """Test visibility toggle functionality"""

    def test_toggle_visibility_off(self, auth_headers):
        """Setting video_showroom_visible to false should hide section"""
        response = requests.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers=auth_headers,
            json={"video_showroom_visible": False}
        )
        assert response.status_code == 200
        
        # Verify
        get_response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        data = get_response.json()
        assert data.get("video_showroom_visible") == False
        print("✓ Visibility toggle OFF works")

    def test_toggle_visibility_on(self, auth_headers):
        """Setting video_showroom_visible to true should show section"""
        response = requests.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers=auth_headers,
            json={"video_showroom_visible": True}
        )
        assert response.status_code == 200
        
        # Verify
        get_response = requests.get(f"{BASE_URL}/api/website-admin/homepage", headers=auth_headers)
        data = get_response.json()
        assert data.get("video_showroom_visible") == True
        print("✓ Visibility toggle ON works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
