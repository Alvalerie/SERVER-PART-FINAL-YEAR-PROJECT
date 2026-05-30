from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.main import app
from app.models.student_model import Student

client = TestClient(app)


# Mock data

MOCK_STUDENT = Student(student_no="2021000001", name="John Doe")

VALID_PAYLOAD = {
    "student_no": 2021000001,
    "name": "John Doe",
}


def override_get_db():
    db = MagicMock()
    yield db


app.dependency_overrides[get_db] = override_get_db


# GET /api/v1/students

@patch("app.repositories.student.StudentRepository.get_all", return_value=[MOCK_STUDENT])
def test_get_students(mock_get_all):
    response = client.get("/api/v1/students")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "John Doe"


# GET /api/v1/students/{student_id}

@patch("app.repositories.student.StudentRepository.get_by_id", return_value=MOCK_STUDENT)
def test_get_student_found(mock_get_by_id):
    response = client.get("/api/v1/students/2021000001")
    assert response.status_code == 200
    assert response.json()["student_no"] == 2021000001


@patch("app.repositories.student.StudentRepository.get_by_id", return_value=None)
def test_get_student_not_found(mock_get_by_id):
    response = client.get("/api/v1/students/2021000099")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# POST /api/v1/students

@patch("app.repositories.student.StudentRepository.get_by_id", return_value=None)
@patch("app.repositories.student.StudentRepository.create", return_value=MOCK_STUDENT)
def test_create_student(mock_create, mock_get_by_id):
    response = client.post("/api/v1/students", json=VALID_PAYLOAD)
    assert response.status_code == 201
    assert response.json()["name"] == "John Doe"


@patch("app.repositories.student.StudentRepository.get_by_id", return_value=MOCK_STUDENT)
def test_create_student_duplicate(mock_get_by_id):
    response = client.post("/api/v1/students", json=VALID_PAYLOAD)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_student_invalid_student_no_length():
    """Student number must be exactly 10 digits."""
    response = client.post("/api/v1/students", json={**VALID_PAYLOAD, "student_no": 12345})
    assert response.status_code == 422


def test_create_student_invalid_student_no_prefix():
    """Student number must start with '20'."""
    response = client.post("/api/v1/students", json={**VALID_PAYLOAD, "student_no": 1921000001})
    assert response.status_code == 422


def test_create_student_invalid_name_numbers():
    """Name must contain only letters."""
    response = client.post("/api/v1/students", json={**VALID_PAYLOAD, "name": "John123"})
    assert response.status_code == 422


def test_create_student_name_too_short():
    response = client.post("/api/v1/students", json={**VALID_PAYLOAD, "name": ""})
    assert response.status_code == 422



# PATCH /api/v1/students/{student_id}

@patch("app.repositories.student.StudentRepository.get_by_id", return_value=MOCK_STUDENT)
@patch("app.repositories.student.StudentRepository.update", return_value=MOCK_STUDENT)
def test_update_student_name(mock_update, mock_get_by_id):
    response = client.patch("/api/v1/students/2021000001", json={"name": "Jane Doe"})
    assert response.status_code == 200
    assert response.json()["name"] == "John Doe"  # mock always returns MOCK_STUDENT


@patch("app.repositories.student.StudentRepository.get_by_id", return_value=None)
def test_update_student_not_found(mock_get_by_id):
    response = client.patch("/api/v1/students/2021000099", json={"name": "Jane Doe"})
    assert response.status_code == 404



# DELETE /api/v1/students/{student_id}

@patch("app.repositories.student.StudentRepository.get_by_id", return_value=MOCK_STUDENT)
@patch("app.repositories.student.StudentRepository.delete", return_value=None)
def test_delete_student(mock_delete, mock_get_by_id):
    response = client.delete("/api/v1/students/2021000001")
    assert response.status_code == 204


@patch("app.repositories.student.StudentRepository.get_by_id", return_value=None)
def test_delete_student_not_found(mock_get_by_id):
    response = client.delete("/api/v1/students/2021000099")
    assert response.status_code == 404