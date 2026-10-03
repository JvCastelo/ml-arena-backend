"""Teste do health check. Única suíte automatizada do repositório até agora.

Com `uv run pytest`. Os testes de runs, upload e worker ainda não estão aqui.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    """Confere que /health responde 200 com {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
