"""V3 virtual classroom review-route API."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.virtual_classroom.domain import ReviewRoute
from open_notebook.virtual_classroom.review import generate_review_route

router = APIRouter()


class ReviewRouteResponse(BaseModel):
    id: str
    notebook: Optional[str] = None
    source: Optional[str] = None
    data: str
    status: str


class GenerateReviewRouteRequest(BaseModel):
    notebook_id: Optional[str] = None
    source_id: Optional[str] = None


def _route_response(route: ReviewRoute) -> ReviewRouteResponse:
    return ReviewRouteResponse(
        id=route.id or "",
        notebook=route.notebook,
        source=route.source,
        data=route.data or "{}",
        status=route.status or "idle",
    )


@router.get("/virtual-classroom/review", response_model=ReviewRouteResponse)
async def get_review_route(
    notebook_id: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
):
    conditions = []
    vars: dict[str, Any] = {}
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if not conditions:
        raise HTTPException(status_code=400, detail="notebook_id or source_id is required")
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM review_route {where} ORDER BY created DESC LIMIT 1",
        vars,
    )
    if not rows:
        return ReviewRouteResponse(id="", notebook=notebook_id, source=source_id, data="{}", status="idle")
    return _route_response(ReviewRoute(**rows[0]))


@router.post("/virtual-classroom/review/generate", response_model=ReviewRouteResponse)
async def generate_review(data: GenerateReviewRouteRequest):
    try:
        await generate_review_route(data.notebook_id, data.source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conditions = []
    vars: dict[str, Any] = {}
    if data.notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(data.notebook_id)
    if data.source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(data.source_id)
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM review_route {where} ORDER BY created DESC LIMIT 1",
        vars,
    )
    if not rows:
        raise HTTPException(status_code=500, detail="Review route was not persisted")
    return _route_response(ReviewRoute(**rows[0]))
