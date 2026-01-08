from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

def test_read_main():
    # Mock init_firestore to prevent actual DB connection during tests
    with patch("app.main.init_firestore"):
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert response.json() == {"message": "Vink Backend API"}
