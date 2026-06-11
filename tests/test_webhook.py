import hmac
import hashlib
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_webhook_missing_signature():
    # Enforce a secret temporarily for the test
    settings.GITHUB_WEBHOOK_SECRET = "test_secret"
    
    response = client.post(
        "/webhook",
        json={"action": "opened"},
        headers={"X-GitHub-Event": "pull_request"}
    )
    assert response.status_code == 403
    assert "missing" in response.json()["detail"]

def test_webhook_invalid_signature():
    settings.GITHUB_WEBHOOK_SECRET = "test_secret"
    
    response = client.post(
        "/webhook",
        json={"action": "opened"},
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=invalidhash"
        }
    )
    assert response.status_code == 403
    assert "didn't match" in response.json()["detail"]

def test_webhook_valid_signature():
    settings.GITHUB_WEBHOOK_SECRET = "test_secret"
    payload = b'{"action": "opened"}'
    
    hash_object = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    response = client.post(
        "/webhook",
        content=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": expected_signature,
            "Content-Type": "application/json"
        }
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
