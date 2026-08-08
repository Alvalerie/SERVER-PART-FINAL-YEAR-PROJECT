# SERVER-PART-FINAL-YEAR-PROJECT

## Folder Structure

```
project/
│
├── app/
│ ├── **init**.py
│ ├── main.py
│ ├── config/
│ │ ├── **init**.py
│ │ └── settings.py
│ ├── models/
│ │ ├── **init**.py
│ │ └── user.py
│ ├── schemas/
│ │ ├── **init**.py
│ │ └── user.py
│ ├── services/
│ │ ├── **init**.py
│ │ └── user.py
│ ├── repositories/
│ │ ├── **init**.py
│ │ └── user.py
│ ├── routers/
│ │ ├── **init**.py
│ │ └── user.py
│ ├── dependencies/
│ │ ├── **init**.py
│ │ └── auth.py
│ └── utils/
│ ├── **init**.py
│ └── helpers.py
│
├── tests/
│ ├── **init**.py
│ ├── test_main.py
│ └── test_user.py
│
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Structure Breakdown

- app: The main application directory.
  - config: Configuration files.
  - models: Database models.
  - schemas: Pydantic schemas for request/response validation.
  - services: Business logic.
  - repositories: Data access layer (for database interactions).
  - routers: API routes. (similar to contollers)
  - dependencies: Dependencies used across the application.
  - utils: Utility functions.
- tests: Unit tests and integration tests.
- requirements.txt: Project dependencies.
- Dockerfile and docker-compose.yml: Docker configuration.

## Prerequisites
- install and setup PGvector 

## To run the program

1. In windows terminal
   * `python -m venv venv` 
   * `venv\Sripts\activate`
   * `pip install -r requirements.txt`
   * `uvicorn app.main:app --reload`

2. or with Docker
   * `docker compose up --build`

## to run the tests
  * `pytest tests/`
