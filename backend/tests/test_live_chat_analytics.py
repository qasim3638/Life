"""
Test Live Chat and Website Analytics Features
Tests:
- Live Chat public endpoints (settings, session start, message)
- Live Chat admin endpoints (sessions, stats, reply)
- Website Analytics tracking endpoint
- Website Analytics stats endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "qasim@tilestation.co.uk"
ADMIN_PASSWORD = "Tilestation_9614"


class TestLiveChatPublicEndpoints:
    """Test Live Chat public endpoints (no auth required)"""
    
    def test_get_public_settings(self):
        """Test /api/live-chat/settings/public returns chat widget settings"""
        response = requests.get(f"{BASE_URL}/api/live-chat/settings/public")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields exist
        assert "enabled" in data, "Missing 'enabled' field"
        assert "welcome_message" in data, "Missing 'welcome_message' field"
        assert "theme_color" in data, "Missing 'theme_color' field"
        assert "position" in data, "Missing 'position' field"
        
        # Verify data types
        assert isinstance(data["enabled"], bool), "enabled should be boolean"
        assert isinstance(data["welcome_message"], str), "welcome_message should be string"
        print(f"✓ Public settings returned: enabled={data['enabled']}, theme={data['theme_color']}")
    
    def test_start_chat_session(self):
        """Test /api/live-chat/session/start creates a new session"""
        response = requests.post(
            f"{BASE_URL}/api/live-chat/session/start",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_id" in data, "Missing 'session_id' field"
        assert "messages" in data, "Missing 'messages' field"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        # Store session_id for next test
        TestLiveChatPublicEndpoints.session_id = data["session_id"]
        print(f"✓ Chat session started: {data['session_id'][:16]}...")
        
        # Verify welcome message is present
        if data.get("is_new"):
            assert len(data["messages"]) > 0, "New session should have welcome message"
            print(f"✓ Welcome message present: {data['messages'][0].get('message', '')[:50]}...")
    
    def test_send_visitor_message(self):
        """Test /api/live-chat/message sends a visitor message and gets AI response"""
        # First start a session
        session_response = requests.post(
            f"{BASE_URL}/api/live-chat/session/start",
            headers={"Content-Type": "application/json"}
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]
        
        # Send a message
        message_data = {
            "session_id": session_id,
            "message": "Hello, I'm looking for bathroom tiles",
            "visitor_name": "Test Visitor",
            "visitor_email": "test@example.com"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/live-chat/message",
            json=message_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        assert "message" in data, "Missing 'message' field"
        
        # Verify visitor message was saved
        assert data["message"]["sender"] == "visitor", "Message sender should be 'visitor'"
        assert data["message"]["message"] == message_data["message"], "Message content mismatch"
        
        print(f"✓ Visitor message sent successfully")
        
        # Check if AI response was generated (may be None if AI is disabled)
        if data.get("ai_response"):
            assert data["ai_response"]["sender"] == "ai", "AI response sender should be 'ai'"
            print(f"✓ AI response received: {data['ai_response']['message'][:100]}...")
        else:
            print("ℹ No AI response (AI may be disabled or unavailable)")
    
    def test_get_session_messages(self):
        """Test /api/live-chat/messages/{session_id} returns messages"""
        # First start a session and send a message
        session_response = requests.post(
            f"{BASE_URL}/api/live-chat/session/start",
            headers={"Content-Type": "application/json"}
        )
        session_id = session_response.json()["session_id"]
        
        # Get messages
        response = requests.get(f"{BASE_URL}/api/live-chat/messages/{session_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "messages" in data, "Missing 'messages' field"
        assert isinstance(data["messages"], list), "messages should be a list"
        print(f"✓ Retrieved {len(data['messages'])} messages for session")


class TestLiveChatAdminEndpoints:
    """Test Live Chat admin endpoints (auth required)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    def test_get_chat_sessions(self):
        """Test /api/live-chat/sessions returns chat sessions list"""
        response = requests.get(
            f"{BASE_URL}/api/live-chat/sessions",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "sessions" in data, "Missing 'sessions' field"
        assert isinstance(data["sessions"], list), "sessions should be a list"
        print(f"✓ Retrieved {len(data['sessions'])} chat sessions")
    
    def test_get_chat_sessions_with_filter(self):
        """Test /api/live-chat/sessions with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/live-chat/sessions?status=open",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "sessions" in data, "Missing 'sessions' field"
        
        # Verify all returned sessions have 'open' status
        for session in data["sessions"]:
            assert session.get("status") == "open", f"Expected status 'open', got {session.get('status')}"
        
        print(f"✓ Retrieved {len(data['sessions'])} open chat sessions")
    
    def test_get_chat_stats(self):
        """Test /api/live-chat/stats returns chat statistics"""
        response = requests.get(
            f"{BASE_URL}/api/live-chat/stats",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required stats fields
        assert "total_sessions" in data, "Missing 'total_sessions' field"
        assert "open_sessions" in data, "Missing 'open_sessions' field"
        assert "today_sessions" in data, "Missing 'today_sessions' field"
        assert "total_messages" in data, "Missing 'total_messages' field"
        
        print(f"✓ Chat stats: total={data['total_sessions']}, open={data['open_sessions']}, today={data['today_sessions']}")
    
    def test_get_chat_settings_admin(self):
        """Test /api/live-chat/settings returns full settings for admin"""
        response = requests.get(
            f"{BASE_URL}/api/live-chat/settings",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Missing 'enabled' field"
        assert "ai_enabled" in data, "Missing 'ai_enabled' field"
        assert "welcome_message" in data, "Missing 'welcome_message' field"
        
        print(f"✓ Admin settings: enabled={data['enabled']}, ai_enabled={data['ai_enabled']}")
    
    def test_admin_reply_to_session(self):
        """Test /api/live-chat/reply sends admin reply"""
        # First create a session
        session_response = requests.post(
            f"{BASE_URL}/api/live-chat/session/start",
            headers={"Content-Type": "application/json"}
        )
        session_id = session_response.json()["session_id"]
        
        # Send admin reply
        reply_data = {
            "session_id": session_id,
            "message": "Hello! How can I help you today?"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/live-chat/reply",
            json=reply_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        assert "message" in data, "Missing 'message' field"
        assert data["message"]["sender"] == "admin", "Message sender should be 'admin'"
        
        print(f"✓ Admin reply sent successfully")


class TestWebsiteAnalyticsEndpoints:
    """Test Website Analytics endpoints"""
    
    def test_track_page_view(self):
        """Test /api/website/track logs a page view"""
        track_data = {
            "page_url": "https://example.com/shop/tiles",
            "page_title": "Tiles Collection",
            "referrer": "https://google.com",
            "session_id": f"test-session-{int(time.time())}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/website/track",
            json=track_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True or "visitor_id" in data, "Expected success response"
        print(f"✓ Page view tracked successfully")
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get auth token for admin endpoints"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code == 200:
            self.token = login_response.json().get("token")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = {"Content-Type": "application/json"}
    
    def test_get_live_visitors(self):
        """Test /api/website/live returns live visitors"""
        response = requests.get(
            f"{BASE_URL}/api/website/live",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "count" in data, "Missing 'count' field"
        assert "visitors" in data, "Missing 'visitors' field"
        assert isinstance(data["visitors"], list), "visitors should be a list"
        
        print(f"✓ Live visitors: {data['count']} active")
    
    def test_get_website_stats(self):
        """Test /api/website/stats returns analytics stats"""
        response = requests.get(
            f"{BASE_URL}/api/website/stats?period=today",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify expected fields
        assert "total_views" in data or "period" in data, "Missing expected stats fields"
        
        print(f"✓ Website stats retrieved for period 'today'")
    
    def test_get_website_stats_different_periods(self):
        """Test /api/website/stats with different periods"""
        periods = ["today", "yesterday", "week", "month"]
        
        for period in periods:
            response = requests.get(
                f"{BASE_URL}/api/website/stats?period={period}",
                headers=self.headers
            )
            
            assert response.status_code == 200, f"Expected 200 for period '{period}', got {response.status_code}"
            print(f"✓ Stats retrieved for period '{period}'")
    
    def test_get_top_pages(self):
        """Test /api/website/pages returns top pages"""
        response = requests.get(
            f"{BASE_URL}/api/website/pages?limit=10",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "pages" in data, "Missing 'pages' field"
        assert isinstance(data["pages"], list), "pages should be a list"
        
        print(f"✓ Top pages: {len(data['pages'])} pages returned")
    
    def test_get_recent_visitors(self):
        """Test /api/website/visitors/recent returns recent visitors"""
        response = requests.get(
            f"{BASE_URL}/api/website/visitors/recent?limit=10",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "visitors" in data, "Missing 'visitors' field"
        assert isinstance(data["visitors"], list), "visitors should be a list"
        
        print(f"✓ Recent visitors: {len(data['visitors'])} visitors returned")


class TestIntegrationFlow:
    """Test complete integration flows"""
    
    def test_full_chat_flow(self):
        """Test complete chat flow: start session -> send message -> get AI response"""
        # 1. Start session
        session_response = requests.post(
            f"{BASE_URL}/api/live-chat/session/start",
            headers={"Content-Type": "application/json"}
        )
        assert session_response.status_code == 200
        session_data = session_response.json()
        session_id = session_data["session_id"]
        print(f"1. Session started: {session_id[:16]}...")
        
        # 2. Send visitor message
        message_response = requests.post(
            f"{BASE_URL}/api/live-chat/message",
            json={
                "session_id": session_id,
                "message": "Do you have any porcelain tiles in stock?",
                "visitor_name": "Integration Test"
            },
            headers={"Content-Type": "application/json"}
        )
        assert message_response.status_code == 200
        message_data = message_response.json()
        print(f"2. Message sent: {message_data['message']['message'][:50]}...")
        
        # 3. Check for AI response
        if message_data.get("ai_response"):
            print(f"3. AI responded: {message_data['ai_response']['message'][:100]}...")
        else:
            print("3. No AI response (AI may be disabled)")
        
        # 4. Verify messages are retrievable
        messages_response = requests.get(f"{BASE_URL}/api/live-chat/messages/{session_id}")
        assert messages_response.status_code == 200
        messages = messages_response.json()["messages"]
        print(f"4. Total messages in session: {len(messages)}")
        
        # 5. Login as admin and verify session appears
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json()["token"]
            sessions_response = requests.get(
                f"{BASE_URL}/api/live-chat/sessions",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert sessions_response.status_code == 200
            sessions = sessions_response.json()["sessions"]
            
            # Find our session
            our_session = next((s for s in sessions if s["session_id"] == session_id), None)
            if our_session:
                print(f"5. Session visible to admin: status={our_session['status']}, messages={our_session.get('message_count', 0)}")
            else:
                print("5. Session not found in admin list (may be filtered)")
        
        print("✓ Full chat flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
