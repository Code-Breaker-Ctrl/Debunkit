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
