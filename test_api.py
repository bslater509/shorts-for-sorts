from fastapi.testclient import TestClient
from gui.server import app

client = TestClient(app)
response = client.post("/api/youtube/search", json={"query": "test"})
print(response.status_code)
print(response.json())
