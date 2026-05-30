###  SERVER-PART-FINAL-YEAR-PROJECT

# to run the program
pip install -r requirements.txt
uvicorn app.main:app --reload

# or with Docker
docker compose up --build