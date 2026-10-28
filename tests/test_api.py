import pytest
import json
from debunkit_app import app
from Core.database import db
from Core.user_model import User


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()


class TestHealthAndPages:
    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"

    def test_landing_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"DEBUNK.IT" in response.data
        assert b"BULLSHIT" in response.data or b"BS-O-METER" in response.data

    def test_scanner_page(self, client):
        response = client.get("/scanner")
        assert response.status_code == 200

    def test_spa_routes(self, client):
        res_h = client.get("/history")
        assert res_h.status_code == 200
        res_a = client.get("/analytics")
        assert res_a.status_code == 200


class TestAnalyzeValidation:
    def test_analyze_empty_body(self, client):
        response = client.post("/analyze", json={})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_analyze_too_short_text(self, client):
        response = client.post("/analyze", json={"text": "ab", "type": "text"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_analyze_invalid_url(self, client):
        response = client.post("/analyze", json={"text": "ftp://bad-url", "type": "url"})
        assert response.status_code == 400
        assert "error" in response.get_json()


class TestAuthEndpoints:
    def test_registration_and_login_flow(self, client):
        # 1. Register a valid user
        reg_payload = {
            "username": "factchecker",
            "email": "tester@example.com",
            "password": "StrongPassword123!"
        }
        reg_res = client.post("/register", json=reg_payload)
        assert reg_res.status_code == 201

        # 2. Duplicate registration should be blocked
        dup_res = client.post("/register", json=reg_payload)
        assert dup_res.status_code == 400

        # 3. Successful login
        login_payload = {
            "email": "tester@example.com",
            "password": "StrongPassword123!"
        }
        login_res = client.post("/login", json=login_payload)
        assert login_res.status_code == 200
        assert login_res.get_json()["status"] == "success"

        # 4. Failed login with wrong password
        bad_login = client.post("/login", json={
            "email": "tester@example.com",
            "password": "WrongPassword999!"
        })
        assert bad_login.status_code == 401

    def test_password_complexity_enforcement(self, client):
        weak_payload = {
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "simplepassword"  # Missing uppercase, number, special char
        }
        res = client.post("/register", json=weak_payload)
        assert res.status_code == 400
        assert "Password must contain" in res.get_json()["error"]


class TestAnalyticsEndpoints:
    def test_guest_can_access_api_stats_as_json(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "total_analyses" in data
        assert "verdict_breakdown" in data
        assert "mode_breakdown" in data
        assert "average_confidence" in data


class TestHistoryEndpoints:
    def test_guest_history_returns_401_json_not_redirect(self, client):
        response = client.get("/api/history")
        assert response.status_code == 401
        assert response.is_json
        data = response.get_json()
        assert data.get("authenticated") is False

    def test_clear_database_returns_json_confirmation(self, client):
        response = client.post("/api/clear-database", json={})
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data.get("status") == "success"
        assert "Database cleared" in data.get("message")
        assert "deleted" in data

    def test_logged_in_user_history_flow(self, client):
        # Register and log in
        reg_payload = {
            "username": "histuser",
            "email": "hist@example.com",
            "password": "StrongPassword123!"
        }
        client.post("/register", json=reg_payload)
        client.post("/login", json={"email": "hist@example.com", "password": "StrongPassword123!"})

        # Fetch history
        res = client.get("/api/history")
        assert res.status_code == 200
        assert res.is_json
        data = res.get_json()
        assert data.get("authenticated") is True
        assert "analyses" in data


class TestUrlAnalysis:
    def test_analyze_url_claim_returns_source_based_report(self, client):
        # Even with a non-existent URL or 404 target, URL analysis returns a full report
        payload = {
            "text": "https://example.com/article",
            "type": "url"
        }
        response = client.post("/analyze", json=payload)
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert "verdict" in data
        assert "confidence" in data
        assert "fact_check" in data
        assert "red_flags" in data
        assert "sources" in data
        assert isinstance(data["confidence"], (int, float))
        assert len(data["sources"]) > 0
        assert any("example.com" in s.get("url", "") or "Submitted" in s.get("title", "") for s in data["sources"])
