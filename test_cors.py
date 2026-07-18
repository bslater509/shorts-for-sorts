from fastapi.testclient import TestClient
from gui.server import app

client = TestClient(app)
response = client.options("/api/youtube/search")
print(f"Status: {response.status_code}")
print(f"Content: {response.text}")
