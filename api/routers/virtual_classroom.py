"""V3 virtual classroom API routes.

These routes are intentionally small and focused on the classroom-specific
data model: chapters and knowledge points first, then mistakes/quiz later.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.exceptions import NotFoundError
from open_notebook.virtual_classroom.domain import (
    Chapter,
    KnowledgePoint,
)

router = APIRouter()


# ---------- Schemas ----------

class ChapterCreate(BaseModel):
    title: str
    source: str
    notebook: Optional[str] = None
    order_index: int = 0
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    notebook: Optional[str] = None
    order_index: Optional[int] = None
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class ChapterResponse(BaseModel):
    id: str
    title: str
    source: str
    notebook: Optional[str] = None
    order_index: int = 0
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class KnowledgePointCreate(BaseModel):
    title: str
    source: str
    chapter: Optional[str] = None
    notebook: Optional[str] = None
    page_number: Optional[int] = None
    summary: Optional[str] = None
    tags: List[str] = []
    hotness: Optional[float] = 0


class KnowledgePointUpdate(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    chapter: Optional[str] = None
    notebook: Optional[str] = None
    page_number: Optional[int] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    hotness: Optional[float] = None


class KnowledgePointResponse(BaseModel):
    id: str
    title: str
    source: str
    chapter: Optional[str] = None
    notebook: Optional[str] = None
    page_number: Optional[int] = None
    summary: Optional[str] = None
    tags: List[str] = []
    hotness: Optional[float] = 0


def _chapter_response(c: Chapter) -> ChapterResponse:
    return ChapterResponse(
        id=c.id or "",
        title=c.title,
        source=c.source,
        notebook=c.notebook,
        order_index=c.order_index or 0,
        summary=c.summary,
        page_start=c.page_start,
        page_end=c.page_end,
    )


def _kp_response(k: KnowledgePoint) -> KnowledgePointResponse:
    return KnowledgePointResponse(
        id=k.id or "",
        title=k.title,
        source=k.source,
        chapter=k.chapter,
        notebook=k.notebook,
        page_number=k.page_number,
        summary=k.summary,
        tags=k.tags or [],
        hotness=k.hotness,
    )


async def _verify_source(source_id: str) -> None:
    source = await Source.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")


async def _verify_notebook(notebook_id: Optional[str]) -> None:
    if not notebook_id:
        return
    notebook = await Notebook.get(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")


# ---------- Chapters ----------

@router.get("/virtual-classroom/chapters", response_model=List[ChapterResponse])
async def list_chapters(
    source_id: Optional[str] = Query(None, description="Filter by source"),
    notebook_id: Optional[str] = Query(None, description="Filter by notebook"),
):
    conditions = []
    vars = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await repo_query(f"SELECT * FROM chapter {where} ORDER BY order_index ASC", vars)
    return [_chapter_response(Chapter(**row)) for row in rows]


@router.post("/virtual-classroom/chapters", response_model=ChapterResponse)
async def create_chapter(data: ChapterCreate):
    await _verify_source(data.source)
    await _verify_notebook(data.notebook)
    chapter = Chapter(**data.model_dump())
    await chapter.save()
    return _chapter_response(chapter)


@router.get("/virtual-classroom/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(chapter_id: str):
    try:
        chapter = await Chapter.get(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return _chapter_response(chapter)


@router.put("/virtual-classroom/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(chapter_id: str, data: ChapterUpdate):
    try:
        chapter = await Chapter.get(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chapter not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(chapter, key, value)
    if data.source:
        await _verify_source(data.source)
    if data.notebook:
        await _verify_notebook(data.notebook)
    await chapter.save()
    return _chapter_response(chapter)


@router.delete("/virtual-classroom/chapters/{chapter_id}")
async def delete_chapter(chapter_id: str):
    try:
        chapter = await Chapter.get(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Chapter not found")
    await chapter.delete()
    return {"ok": True}


# ---------- Knowledge Points ----------

@router.get("/virtual-classroom/knowledge-points", response_model=List[KnowledgePointResponse])
async def list_knowledge_points(
    source_id: Optional[str] = Query(None, description="Filter by source"),
    chapter_id: Optional[str] = Query(None, description="Filter by chapter"),
    notebook_id: Optional[str] = Query(None, description="Filter by notebook"),
):
    conditions = []
    vars = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if chapter_id:
        conditions.append("chapter = $chapter")
        vars["chapter"] = ensure_record_id(chapter_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await repo_query(f"SELECT * FROM knowledge_point {where} ORDER BY created ASC", vars)
    return [_kp_response(KnowledgePoint(**row)) for row in rows]


@router.post("/virtual-classroom/knowledge-points", response_model=KnowledgePointResponse)
async def create_knowledge_point(data: KnowledgePointCreate):
    await _verify_source(data.source)
    await _verify_notebook(data.notebook)
    kp = KnowledgePoint(**data.model_dump())
    await kp.save()
    return _kp_response(kp)


@router.get("/virtual-classroom/knowledge-points/{kp_id}", response_model=KnowledgePointResponse)
async def get_knowledge_point(kp_id: str):
    try:
        kp = await KnowledgePoint.get(kp_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    return _kp_response(kp)


@router.put("/virtual-classroom/knowledge-points/{kp_id}", response_model=KnowledgePointResponse)
async def update_knowledge_point(kp_id: str, data: KnowledgePointUpdate):
    try:
        kp = await KnowledgePoint.get(kp_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(kp, key, value)
    if data.source:
        await _verify_source(data.source)
    if data.notebook:
        await _verify_notebook(data.notebook)
    await kp.save()
    return _kp_response(kp)


@router.delete("/virtual-classroom/knowledge-points/{kp_id}")
async def delete_knowledge_point(kp_id: str):
    try:
        kp = await KnowledgePoint.get(kp_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    await kp.delete()
    return {"ok": True}
