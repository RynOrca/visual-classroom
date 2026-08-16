"""Tests for V3 virtual-classroom review route generation."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.virtual_classroom_review import router


def test_generate_review_route_endpoint():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    row = {
        "id": "review_route:1",
        "notebook": None,
        "source": "source:1",
        "data": '{"title":"复习路线","overview":"俯瞰","stages":[]}',
        "status": "done",
    }

    with (
        patch(
            "api.routers.virtual_classroom_review.generate_review_route",
            new=AsyncMock(return_value=row["data"]),
        ),
        patch(
            "api.routers.virtual_classroom_review.repo_query",
            new=AsyncMock(return_value=[row]),
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/api/virtual-classroom/review/generate",
            json={"source_id": "source:1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "review_route:1"
    assert payload["source"] == "source:1"
    assert payload["status"] == "done"
    assert '"overview":"俯瞰"' in payload["data"]
