from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.main import app
from app.models.refresh_token_model import RefreshToken
from app.models.user_model import User

client = TestClient(app)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_USER = User(
    id=1,
    name="John Doe",
    email="john@example.com",
    password="$2b$12$hashedpassword",
    role="admin",
)

MOCK_REFRESH_TOKEN = RefreshToken(
    id=1,
    user_id=1,
    token="valid.refresh.token",
    expires_at=datetime.now(UTC) + timedelta(days=7),
    created_at=datetime.now(UTC),
    is_revoked=False,
)

REVOKED_TOKEN = RefreshToken(
    id=2,
    user_id=1,
    token="revoked.refresh.token",
    expires_at=datetime.now(UTC) + timedelta(days=7),
    created_at=datetime.now(UTC),
    is_revoked=True,
)

EXPIRED_TOKEN = RefreshToken(
    id=3,
    user_id=1,
    token="expired.refresh.token",
    expires_at=datetime.now(UTC) - timedelta(days=1),
    created_at=datetime.now(UTC),
    is_revoked=False,
)

VALID_LOGIN = {"email": "john@example.com", "password": "Password1!"}


def override_get_db():
    db = MagicMock()
    yield db


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------

@patch("app.services.auth.AuthService._get_user_by_email", return_value=MOCK_USER)
@patch("app.services.auth.verify_password", return_value=True)
@patch("app.repositories.refresh_token.RefreshTokenRepository.create", return_value=MOCK_REFRESH_TOKEN)
def test_login_success(mock_create, mock_verify, mock_get_user):
    response = client.post("/api/v1/auth/login", json=VALID_LOGIN)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert response.json()["token_type"] == "bearer"


@patch("app.services.auth.AuthService._get_user_by_email", return_value=None)
def test_login_wrong_email(mock_get_user):
    response = client.post("/api/v1/auth/login", json=VALID_LOGIN)
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


@patch("app.services.auth.AuthService._get_user_by_email", return_value=MOCK_USER)
@patch("app.services.auth.verify_password", return_value=False)
def test_login_wrong_password(mock_verify, mock_get_user):
    response = client.post("/api/v1/auth/login", json=VALID_LOGIN)
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


def test_login_invalid_email_format():
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "Password1!"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

@patch("app.services.auth.decode_refresh_token", return_value=1)
@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=MOCK_REFRESH_TOKEN)
@patch("app.services.auth.AuthService._get_user_by_id", return_value=MOCK_USER)
@patch("app.repositories.refresh_token.RefreshTokenRepository.revoke", return_value=None)
@patch("app.repositories.refresh_token.RefreshTokenRepository.create", return_value=MOCK_REFRESH_TOKEN)
def test_refresh_success(mock_create, mock_revoke, mock_get_user, mock_get_token, mock_decode):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "valid.refresh.token"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" not in response.json()
    assert response.json()["token_type"] == "bearer"


@patch("app.utils.helpers.decode_refresh_token", return_value=None)
def test_refresh_invalid_jwt(mock_decode):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage.token"})
    assert response.status_code == 401
    assert "invalid or expired" in response.json()["detail"].lower()


@patch("app.services.auth.decode_refresh_token", return_value=1)
@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=None)
def test_refresh_token_not_in_db(mock_get_token, mock_decode):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "unknown.token"})
    assert response.status_code == 401
    assert "not recognised" in response.json()["detail"].lower()


@patch("app.services.auth.decode_refresh_token", return_value=1)
@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=REVOKED_TOKEN)
@patch("app.repositories.refresh_token.RefreshTokenRepository.revoke_all_for_user", return_value=None)
def test_refresh_revoked_token_triggers_full_revoke(mock_revoke_all, mock_get_token, mock_decode):
    """Reusing a revoked token should revoke all sessions."""
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "revoked.refresh.token"})
    assert response.status_code == 401
    assert "all sessions" in response.json()["detail"].lower()
    mock_revoke_all.assert_called_once_with(REVOKED_TOKEN.user_id)


@patch("app.utils.helpers.decode_refresh_token", return_value=1)
@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=EXPIRED_TOKEN)
def test_refresh_expired_token(mock_get_token, mock_decode):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "expired.refresh.token"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------

@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=MOCK_REFRESH_TOKEN)
@patch("app.repositories.refresh_token.RefreshTokenRepository.revoke", return_value=None)
def test_logout_success(mock_revoke, mock_get_token):
    response = client.post("/api/v1/auth/logout", json={"refresh_token": "valid.refresh.token"})
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()


@patch("app.repositories.refresh_token.RefreshTokenRepository.get_by_token", return_value=None)
def test_logout_unknown_token_still_succeeds(mock_get_token):
    """Logout should not leak whether a token existed."""
    response = client.post("/api/v1/auth/logout", json={"refresh_token": "unknown.token"})
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout-all
# ---------------------------------------------------------------------------

@patch("app.utils.helpers.decode_access_token", return_value=1)
@patch("app.repositories.refresh_token.RefreshTokenRepository.revoke_all_for_user", return_value=None)
def test_logout_all_success(mock_revoke_all, mock_decode):
    with patch("app.dependencies.auth.decode_access_token", return_value=1), \
         patch("app.dependencies.auth.get_db", return_value=iter([MagicMock()])):

        # Mock the DB query inside get_current_user
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MOCK_USER

        def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        response = client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": "Bearer valid.access.token"},
        )
        assert response.status_code == 200
        assert "all devices" in response.json()["message"].lower()

    # Restore original override
    app.dependency_overrides[get_db] = override_get_db