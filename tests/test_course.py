from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.main import app
from app.models.course_model import Course

client = TestClient(app)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_COURSE = Course(id=1, name="Computer Science", code="CS101")

VALID_PAYLOAD = {
    "id": 1,
    "name": "Computer Science",
    "code": "CS101",
}


def override_get_db():
    db = MagicMock()
    yield db


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# GET /api/v1/courses
# ---------------------------------------------------------------------------

@patch("app.repositories.course.CourseRepository.get_all", return_value=[MOCK_COURSE])
def test_get_courses(mock_get_all):
    response = client.get("/api/v1/courses")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Computer Science"
    assert response.json()[0]["code"] == "CS101"


# ---------------------------------------------------------------------------
# GET /api/v1/courses/{course_id}
# ---------------------------------------------------------------------------

@patch("app.repositories.course.CourseRepository.get_by_id", return_value=MOCK_COURSE)
def test_get_course_found(mock_get_by_id):
    response = client.get("/api/v1/courses/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=None)
def test_get_course_not_found(mock_get_by_id):
    response = client.get("/api/v1/courses/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/courses
# ---------------------------------------------------------------------------

@patch("app.repositories.course.CourseRepository.get_by_id", return_value=None)
@patch("app.repositories.course.CourseRepository.get_by_code", return_value=None)
@patch("app.repositories.course.CourseRepository.create", return_value=MOCK_COURSE)
def test_create_course(mock_create, mock_get_by_code, mock_get_by_id):
    response = client.post("/api/v1/courses", json=VALID_PAYLOAD)
    assert response.status_code == 201
    assert response.json()["code"] == "CS101"


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=MOCK_COURSE)
def test_create_course_duplicate_id(mock_get_by_id):
    response = client.post("/api/v1/courses", json=VALID_PAYLOAD)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=None)
@patch("app.repositories.course.CourseRepository.get_by_code", return_value=MOCK_COURSE)
def test_create_course_duplicate_code(mock_get_by_code, mock_get_by_id):
    response = client.post("/api/v1/courses", json=VALID_PAYLOAD)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_create_course_invalid_name_numbers():
    """Course name must contain only letters."""
    response = client.post("/api/v1/courses", json={**VALID_PAYLOAD, "name": "CS101Course"})
    assert response.status_code == 422


def test_create_course_name_too_short():
    response = client.post("/api/v1/courses", json={**VALID_PAYLOAD, "name": ""})
    assert response.status_code == 422


def test_create_course_code_too_long():
    """Code must be max 15 characters."""
    response = client.post("/api/v1/courses", json={**VALID_PAYLOAD, "code": "TOOLONGCOURSECODE"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/courses/{course_id}
# ---------------------------------------------------------------------------

@patch("app.repositories.course.CourseRepository.get_by_id", return_value=MOCK_COURSE)
@patch("app.repositories.course.CourseRepository.get_by_code", return_value=None)
@patch("app.repositories.course.CourseRepository.update", return_value=MOCK_COURSE)
def test_update_course_name(mock_update, mock_get_by_code, mock_get_by_id):
    response = client.patch("/api/v1/courses/1", json={"name": "Data Science"})
    assert response.status_code == 200


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=MOCK_COURSE)
@patch("app.repositories.course.CourseRepository.get_by_code", return_value=MOCK_COURSE)
@patch("app.repositories.course.CourseRepository.update", return_value=MOCK_COURSE)
def test_update_course_same_code(mock_update, mock_get_by_code, mock_get_by_id):
    """Updating with the same code on the same course should succeed."""
    response = client.patch("/api/v1/courses/1", json={"code": "CS101"})
    assert response.status_code == 200


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=None)
def test_update_course_not_found(mock_get_by_id):
    response = client.patch("/api/v1/courses/999", json={"name": "Data Science"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/courses/{course_id}
# ---------------------------------------------------------------------------

@patch("app.repositories.course.CourseRepository.get_by_id", return_value=MOCK_COURSE)
@patch("app.repositories.course.CourseRepository.delete", return_value=None)
def test_delete_course(mock_delete, mock_get_by_id):
    response = client.delete("/api/v1/courses/1")
    assert response.status_code == 204


@patch("app.repositories.course.CourseRepository.get_by_id", return_value=None)
def test_delete_course_not_found(mock_get_by_id):
    response = client.delete("/api/v1/courses/999")
    assert response.status_code == 404