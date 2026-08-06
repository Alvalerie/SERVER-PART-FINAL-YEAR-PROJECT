from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.main import app
from app.models.student_course_model import StudentCourse

client = TestClient(app)


# Mock data

MOCK_ENROLLMENT = StudentCourse(
    student_id="2021000001",
    course_code="CS101",
    current_year=date(2024, 1, 1),
)

VALID_PAYLOAD = {
    "student_id": "2021000001",
    "course_code": "CS101",
    "current_year": "2024-01-01",
}


def override_get_db():
    db = MagicMock()
    yield db


app.dependency_overrides[get_db] = override_get_db



# GET /api/v1/enrollments

@patch("app.repositories.student_course.StudentCourseRepository.get_all", return_value=[MOCK_ENROLLMENT])
def test_get_all_enrollments(mock_get_all):
    response = client.get("/api/v1/enrollments")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["student_id"] == "2021000001"
    assert response.json()[0]["course_code"] == "CS101"



# GET /api/v1/enrollments/student/{student_id}

@patch("app.repositories.student_course.StudentCourseRepository.get_by_student", return_value=[MOCK_ENROLLMENT])
def test_get_enrollments_by_student(mock_get_by_student):
    response = client.get("/api/v1/enrollments/student/2021000001")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["student_id"] == "2021000001"


@patch("app.repositories.student_course.StudentCourseRepository.get_by_student", return_value=[])
def test_get_enrollments_by_student_empty(mock_get_by_student):
    response = client.get("/api/v1/enrollments/student/2021000099")
    assert response.status_code == 200
    assert response.json() == []



# GET /api/v1/enrollments/course/{course_code}

@patch("app.repositories.student_course.StudentCourseRepository.get_by_course", return_value=[MOCK_ENROLLMENT])
def test_get_enrollments_by_course(mock_get_by_course):
    response = client.get("/api/v1/enrollments/course/CS101")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["course_code"] == "CS101"


@patch("app.repositories.student_course.StudentCourseRepository.get_by_course", return_value=[])
def test_get_enrollments_by_course_empty(mock_get_by_course):
    response = client.get("/api/v1/enrollments/course/CS999")
    assert response.status_code == 200
    assert response.json() == []



# GET /api/v1/enrollments/{student_id}/{course_code}

@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=MOCK_ENROLLMENT)
def test_get_enrollment_found(mock_get_by_id):
    response = client.get("/api/v1/enrollments/2021000001/CS101")
    assert response.status_code == 200
    assert response.json()["student_id"] == "2021000001"
    assert response.json()["course_code"] == "CS101"


@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=None)
def test_get_enrollment_not_found(mock_get_by_id):
    response = client.get("/api/v1/enrollments/2021000001/CS999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()



# POST /api/v1/enrollments

@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=None)
@patch("app.repositories.student_course.StudentCourseRepository.create", return_value=MOCK_ENROLLMENT)
def test_create_enrollment(mock_create, mock_get_by_id):
    response = client.post("/api/v1/enrollments", json=VALID_PAYLOAD)
    assert response.status_code == 201
    assert response.json()["student_id"] == "2021000001"
    assert response.json()["course_code"] == "CS101"


@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=MOCK_ENROLLMENT)
def test_create_enrollment_duplicate(mock_get_by_id):
    response = client.post("/api/v1/enrollments", json=VALID_PAYLOAD)
    assert response.status_code == 409
    assert "already enrolled" in response.json()["detail"].lower()


def test_create_enrollment_invalid_student_id_length():
    """Student ID must be exactly 10 digits."""
    response = client.post("/api/v1/enrollments", json={**VALID_PAYLOAD, "student_id": "20210001"})
    assert response.status_code == 422


def test_create_enrollment_invalid_student_id_prefix():
    """Student ID must start with '20'."""
    response = client.post("/api/v1/enrollments", json={**VALID_PAYLOAD, "student_id": "1921000001"})
    assert response.status_code == 422


def test_create_enrollment_invalid_student_id_letters():
    """Student ID must contain only digits."""
    response = client.post("/api/v1/enrollments", json={**VALID_PAYLOAD, "student_id": "2021ABCDEF"})
    assert response.status_code == 422


def test_create_enrollment_invalid_course_code():
    """Course code must be alphanumeric."""
    response = client.post("/api/v1/enrollments", json={**VALID_PAYLOAD, "course_code": "CS@101"})
    assert response.status_code == 422


def test_create_enrollment_missing_current_year():
    payload = {"student_id": "2021000001", "course_code": "CS101"}
    response = client.post("/api/v1/enrollments", json=payload)
    assert response.status_code == 422



# PATCH /api/v1/enrollments/{student_id}/{course_code}

@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=MOCK_ENROLLMENT)
@patch("app.repositories.student_course.StudentCourseRepository.update", return_value=MOCK_ENROLLMENT)
def test_update_enrollment(mock_update, mock_get_by_id):
    response = client.patch(
        "/api/v1/enrollments/2021000001/CS101",
        json={"current_year": "2025-01-01"},
    )
    assert response.status_code == 200


@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=None)
def test_update_enrollment_not_found(mock_get_by_id):
    response = client.patch(
        "/api/v1/enrollments/2021000001/CS999",
        json={"current_year": "2025-01-01"},
    )
    assert response.status_code == 404


def test_update_enrollment_invalid_date():
    response = client.patch(
        "/api/v1/enrollments/2021000001/CS101",
        json={"current_year": "not-a-date"},
    )
    assert response.status_code == 422



# DELETE /api/v1/enrollments/{student_id}/{course_code}

@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=MOCK_ENROLLMENT)
@patch("app.repositories.student_course.StudentCourseRepository.delete", return_value=None)
def test_delete_enrollment(mock_delete, mock_get_by_id):
    response = client.delete("/api/v1/enrollments/2021000001/CS101")
    assert response.status_code == 204


@patch("app.repositories.student_course.StudentCourseRepository.get_by_id", return_value=None)
def test_delete_enrollment_not_found(mock_get_by_id):
    response = client.delete("/api/v1/enrollments/2021000001/CS999")
    assert response.status_code == 404