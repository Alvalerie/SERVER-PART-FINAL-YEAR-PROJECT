from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.main import app
from app.models.user_model import User

client = TestClient(app)

MOCK_USER = User(id=1, name="John Doe", email="john@example.com", password="hashed", role="admin")


def override_get_db():
    db = MagicMock()
    yield db


app.dependency_overrides[get_db] = override_get_db


# GET /api/v1/users

@patch("app.repositories.user.UserRepository.get_all", return_value=[MOCK_USER])
def test_get_users(mock_get_all):
    response = client.get("/api/v1/users")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["email"] == "john@example.com"


# GET /api/v1/users/{id}

@patch("app.repositories.user.UserRepository.get_by_id", return_value=MOCK_USER)
def test_get_user_found(mock_get_by_id):
    response = client.get("/api/v1/users/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


@patch("app.repositories.user.UserRepository.get_by_id", return_value=None)
def test_get_user_not_found(mock_get_by_id):
    response = client.get("/api/v1/users/999")
    assert response.status_code == 404


# POST /api/v1/users

VALID_PAYLOAD = {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "password": "Password1!",
    "role": "admin",
}


@patch("app.repositories.user.UserRepository.get_by_email", return_value=None)
@patch("app.repositories.user.UserRepository.create", return_value=MOCK_USER)
def test_create_user(mock_create, mock_get_by_email):
    response = client.post("/api/v1/users", json=VALID_PAYLOAD)
    assert response.status_code == 201


@patch("app.repositories.user.UserRepository.get_by_email", return_value=MOCK_USER)
def test_create_user_duplicate_email(mock_get_by_email):
    response = client.post("/api/v1/users", json=VALID_PAYLOAD)
    assert response.status_code == 409



# DELETE /api/v1/users/{id}

@patch("app.repositories.user.UserRepository.get_by_id", return_value=MOCK_USER)
@patch("app.repositories.user.UserRepository.delete", return_value=None)
def test_delete_user(mock_delete, mock_get_by_id):
    response = client.delete("/api/v1/users/1")
    assert response.status_code == 204