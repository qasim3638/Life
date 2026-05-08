"""
Test suite for Showroom Tours feature
Tests the multi-video showroom tours section that is SEPARATE from Video Showroom
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code}")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestShowroomToursBackend:
    """Backend API tests for Showroom Tours feature"""

    def test_get_homepage_returns_showroom_tours_fields(self, api_client, admin_token):
        """GET /api/website-admin/homepage returns showroom_tours_* fields"""
        response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify showroom_tours fields exist (may be null if not set)
        # The fields should be present in the response
        print(f"Homepage data keys: {list(data.keys())}")
        
        # Check if showroom_tours fields are present
        has_tours_visible = 'showroom_tours_visible' in data
        has_tours_title = 'showroom_tours_title' in data
        has_tours_subtitle = 'showroom_tours_subtitle' in data
        has_tours_videos = 'showroom_tours_videos' in data
        
        print(f"showroom_tours_visible present: {has_tours_visible}, value: {data.get('showroom_tours_visible')}")
        print(f"showroom_tours_title present: {has_tours_title}, value: {data.get('showroom_tours_title')}")
        print(f"showroom_tours_videos present: {has_tours_videos}, count: {len(data.get('showroom_tours_videos', []))}")
        
        # At least one field should be present if data was saved
        assert has_tours_visible or has_tours_title or has_tours_videos, \
            "No showroom_tours fields found in homepage response"

    def test_put_homepage_saves_showroom_tours_fields(self, api_client, admin_token):
        """PUT /api/website-admin/homepage saves showroom_tours_* fields with deep merge"""
        # First, get current data
        get_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        original_data = get_response.json()
        
        # Save test data for showroom tours
        test_payload = {
            "showroom_tours_visible": True,
            "showroom_tours_title": "TEST_Explore Our Showrooms",
            "showroom_tours_subtitle": "TEST_Take a virtual tour",
            "showroom_tours_videos": [
                {
                    "id": "test_video_1",
                    "title": "TEST_Tonbridge Showroom",
                    "description": "Tour of our Tonbridge location",
                    "video_url": "https://example.com/test_video.mp4",
                    "thumbnail_url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800",
                    "enabled": True
                }
            ]
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=test_payload
        )
        assert response.status_code == 200, f"PUT failed: {response.status_code} - {response.text}"
        
        # Verify data was saved
        verify_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        saved_data = verify_response.json()
        
        assert saved_data.get("showroom_tours_visible") == True
        assert saved_data.get("showroom_tours_title") == "TEST_Explore Our Showrooms"
        assert saved_data.get("showroom_tours_subtitle") == "TEST_Take a virtual tour"
        assert len(saved_data.get("showroom_tours_videos", [])) >= 1
        
        # Verify first video
        videos = saved_data.get("showroom_tours_videos", [])
        test_video = next((v for v in videos if v.get("id") == "test_video_1"), None)
        assert test_video is not None, "Test video not found in saved data"
        assert test_video.get("title") == "TEST_Tonbridge Showroom"
        
        print("✓ Showroom tours data saved and verified successfully")

    def test_deep_merge_preserves_video_showroom_data(self, api_client, admin_token):
        """Saving showroom_tours data doesn't overwrite video_showroom data (deep merge)"""
        # Get current data
        get_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        original_data = get_response.json()
        
        # Store original video_showroom values
        original_video_showroom_visible = original_data.get("video_showroom_visible")
        original_video_showroom_title = original_data.get("video_showroom_title")
        
        print(f"Original video_showroom_visible: {original_video_showroom_visible}")
        print(f"Original video_showroom_title: {original_video_showroom_title}")
        
        # Save ONLY showroom_tours data
        tours_payload = {
            "showroom_tours_visible": True,
            "showroom_tours_title": "TEST_Deep Merge Check"
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=tours_payload
        )
        assert response.status_code == 200
        
        # Verify video_showroom data is preserved
        verify_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        after_data = verify_response.json()
        
        # Video showroom fields should be unchanged
        assert after_data.get("video_showroom_visible") == original_video_showroom_visible, \
            f"video_showroom_visible changed from {original_video_showroom_visible} to {after_data.get('video_showroom_visible')}"
        
        if original_video_showroom_title:
            assert after_data.get("video_showroom_title") == original_video_showroom_title, \
                f"video_showroom_title changed from {original_video_showroom_title} to {after_data.get('video_showroom_title')}"
        
        print("✓ Deep merge preserved video_showroom data correctly")

    def test_showroom_tours_videos_array_structure(self, api_client, admin_token):
        """Verify showroom_tours_videos array has correct structure"""
        response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        videos = data.get("showroom_tours_videos", [])
        
        if len(videos) > 0:
            video = videos[0]
            # Check expected fields
            expected_fields = ["id", "title", "enabled"]
            for field in expected_fields:
                assert field in video, f"Missing field '{field}' in video object"
            
            print(f"✓ Video structure verified: {list(video.keys())}")
        else:
            print("No videos in showroom_tours_videos array")

    def test_public_homepage_returns_showroom_tours(self, api_client):
        """Public homepage endpoint returns showroom_tours data for customer-facing component"""
        # The public endpoint should be accessible without auth
        response = api_client.get(f"{BASE_URL}/api/website-admin/homepage")
        assert response.status_code == 200, f"Public homepage failed: {response.status_code}"
        
        data = response.json()
        
        # Check if showroom_tours data is present
        if data.get("showroom_tours_visible"):
            print(f"✓ Showroom tours visible: {data.get('showroom_tours_visible')}")
            print(f"✓ Showroom tours title: {data.get('showroom_tours_title')}")
            videos = data.get("showroom_tours_videos", [])
            print(f"✓ Showroom tours videos count: {len(videos)}")
            
            # Check enabled videos
            enabled_videos = [v for v in videos if v.get("enabled")]
            print(f"✓ Enabled videos: {len(enabled_videos)}")
        else:
            print("Showroom tours section is not visible")

    def test_update_showroom_tours_with_multiple_videos(self, api_client, admin_token):
        """Test saving multiple videos in showroom_tours_videos array"""
        test_videos = [
            {
                "id": "multi_test_1",
                "title": "TEST_Tonbridge",
                "description": "Tonbridge showroom tour",
                "video_url": "",
                "thumbnail_url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800",
                "enabled": True
            },
            {
                "id": "multi_test_2",
                "title": "TEST_Gravesend",
                "description": "Gravesend showroom tour",
                "video_url": "",
                "thumbnail_url": "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800",
                "enabled": True
            },
            {
                "id": "multi_test_3",
                "title": "TEST_Chingford",
                "description": "Chingford showroom tour",
                "video_url": "",
                "thumbnail_url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=800",
                "enabled": False  # Disabled video
            }
        ]
        
        response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "showroom_tours_visible": True,
                "showroom_tours_videos": test_videos
            }
        )
        assert response.status_code == 200
        
        # Verify
        verify_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        saved_data = verify_response.json()
        saved_videos = saved_data.get("showroom_tours_videos", [])
        
        # Find our test videos
        test_ids = ["multi_test_1", "multi_test_2", "multi_test_3"]
        found_videos = [v for v in saved_videos if v.get("id") in test_ids]
        
        assert len(found_videos) >= 3, f"Expected 3 test videos, found {len(found_videos)}"
        
        # Check disabled video
        disabled_video = next((v for v in found_videos if v.get("id") == "multi_test_3"), None)
        if disabled_video:
            assert disabled_video.get("enabled") == False, "Disabled video should have enabled=False"
        
        print(f"✓ Multiple videos saved successfully: {len(found_videos)} videos")


class TestShowroomToursIndependence:
    """Tests to verify Showroom Tours is independent from Video Showroom"""

    def test_both_sections_can_be_enabled_independently(self, api_client, admin_token):
        """Both Video Showroom and Showroom Tours can be enabled at the same time"""
        # Enable both sections
        response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "video_showroom_visible": True,
                "showroom_tours_visible": True
            }
        )
        assert response.status_code == 200
        
        # Verify both are enabled
        verify_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = verify_response.json()
        
        assert data.get("video_showroom_visible") == True, "Video Showroom should be enabled"
        assert data.get("showroom_tours_visible") == True, "Showroom Tours should be enabled"
        
        print("✓ Both sections can be enabled independently")

    def test_disabling_one_section_doesnt_affect_other(self, api_client, admin_token):
        """Disabling Showroom Tours doesn't affect Video Showroom and vice versa"""
        # First enable both
        api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "video_showroom_visible": True,
                "showroom_tours_visible": True
            }
        )
        
        # Disable only Showroom Tours
        response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "showroom_tours_visible": False
            }
        )
        assert response.status_code == 200
        
        # Verify Video Showroom is still enabled
        verify_response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = verify_response.json()
        
        assert data.get("video_showroom_visible") == True, "Video Showroom should still be enabled"
        assert data.get("showroom_tours_visible") == False, "Showroom Tours should be disabled"
        
        print("✓ Disabling one section doesn't affect the other")


class TestCleanup:
    """Cleanup test data"""

    def test_restore_original_showroom_tours_data(self, api_client, admin_token):
        """Restore original showroom tours data (remove TEST_ prefixed data)"""
        # Get current data
        response = api_client.get(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        
        # Filter out TEST_ prefixed videos
        videos = data.get("showroom_tours_videos", [])
        clean_videos = [v for v in videos if not v.get("title", "").startswith("TEST_") and not v.get("id", "").startswith("test_") and not v.get("id", "").startswith("multi_test_")]
        
        # Restore original title if it was changed
        original_title = data.get("showroom_tours_title", "")
        if original_title.startswith("TEST_"):
            original_title = "Explore Our Showrooms"
        
        original_subtitle = data.get("showroom_tours_subtitle", "")
        if original_subtitle.startswith("TEST_"):
            original_subtitle = "Take a virtual tour of each location"
        
        # Save cleaned data
        cleanup_response = api_client.put(
            f"{BASE_URL}/api/website-admin/homepage",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "showroom_tours_visible": True,
                "showroom_tours_title": original_title,
                "showroom_tours_subtitle": original_subtitle,
                "showroom_tours_videos": clean_videos if clean_videos else data.get("showroom_tours_videos", [])
            }
        )
        assert cleanup_response.status_code == 200
        print("✓ Test data cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
