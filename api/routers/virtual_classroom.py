"""V3 virtual classroom API routes.

These routes are intentionally small and focused on the classroom-specific
data model: chapters and knowledge points first, then mistakes/quiz later.
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from open_notebook.ai.provision import provision_langchain_model
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


class ExtractChaptersRequest(BaseModel):
    source_id: str
    notebook_id: Optional[str] = None


class ExtractKnowledgePointsRequest(BaseModel):
    source_id: str
    notebook_id: Optional[str] = None
    chapter_id: Optional[str] = None




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


@router.post("/virtual-classroom/extract-chapters", response_model=List[ChapterResponse])
async def extract_chapters(data: ExtractChaptersRequest):
    """Use the configured LLM to split a source into ordered chapters."""
    await _verify_source(data.source_id)
    await _verify_notebook(data.notebook_id)

    source = await Source.get(data.source_id)
    if not source or not source.full_text:
        raise HTTPException(status_code=400, detail="Source has no text content")

    system_prompt = SystemMessage(
        content=(
            "你是一个课件章节分析助手。请根据课件全文，将其拆分为逻辑章节。\n"
            "要求：\n"
            "1. 章节数量 2-10 个，按课件实际结构拆分\n"
            "2. 每个章节包含 title（简短）、summary（一句话）、order_index（从1开始）、page_start、page_end（如无法判断可给 null）\n"
            "3. 只输出 JSON，不要 Markdown，不要额外文字\n"
            "JSON 格式：\n"
            '{"chapters": [{"title": "章节标题", "summary": "一句话", "order_index": 1, "page_start": 1, "page_end": 3}]}'
        )
    )
    human_message = HumanMessage(content=f"课件全文：\n\n{source.full_text[:12000]}")

    chain = await provision_langchain_model(
        str([system_prompt, human_message]),
        None,
        "chat",
        max_tokens=4096,
    )
    response = await chain.ainvoke([system_prompt, human_message])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        chapters = parsed.get("chapters", [])
    except Exception:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM chapter output: {raw[:200]}")

    saved = []
    for idx, ch in enumerate(chapters):
        chapter = Chapter(
            title=str(ch.get("title", f"第{idx + 1}章")).strip(),
            source=data.source_id,
            notebook=data.notebook_id,
            order_index=int(ch.get("order_index", idx + 1)),
            summary=ch.get("summary"),
            page_start=ch.get("page_start"),
            page_end=ch.get("page_end"),
        )
        await chapter.save()
        saved.append(_chapter_response(chapter))
    return saved


@router.post("/virtual-classroom/extract-knowledge-points", response_model=List[KnowledgePointResponse])
async def extract_knowledge_points(data: ExtractKnowledgePointsRequest):
    """Use the configured LLM to extract knowledge points from a source (optionally within a chapter)."""
    await _verify_source(data.source_id)
    await _verify_notebook(data.notebook_id)

    source = await Source.get(data.source_id)
    if not source or not source.full_text:
        raise HTTPException(status_code=400, detail="Source has no text content")

    system_prompt = SystemMessage(
        content=(
            "你是一个课件知识点提取助手。请根据课件内容提取核心知识点。\n"
            "要求：\n"
            "1. 提取 3-10 个知识点\n"
            "2. 每个知识点包含 title（简短）、summary（一句话）、page_number（如能判断）、tags（2-5个标签）\n"
            "3. 只输出 JSON，不要 Markdown，不要额外文字\n"
            "JSON 格式：\n"
            '{"knowledge_points": [{"title": "知识点", "summary": "一句话", "page_number": 1, "tags": ["标签1", "标签2"]}]}'
        )
    )
    human_message = HumanMessage(content=f"课件全文：\n\n{source.full_text[:12000]}")

    chain = await provision_langchain_model(
        str([system_prompt, human_message]),
        None,
        "chat",
        max_tokens=4096,
    )
    response = await chain.ainvoke([system_prompt, human_message])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        points = parsed.get("knowledge_points", [])
    except Exception:
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM knowledge point output: {raw[:200]}")

    saved = []
    for item in points:
        kp = KnowledgePoint(
            title=str(item.get("title", "未命名知识点")).strip(),
            summary=item.get("summary"),
            source=data.source_id,
            chapter=data.chapter_id,
            notebook=data.notebook_id,
            page_number=item.get("page_number"),
            tags=item.get("tags") or [],
        )
        await kp.save()
        saved.append(_kp_response(kp))
    return saved




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
