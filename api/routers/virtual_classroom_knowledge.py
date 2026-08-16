"""V3 virtual classroom knowledge map API."""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.virtual_classroom.domain import (
    Chapter,
    KnowledgeMap,
    KnowledgePoint,
)

router = APIRouter()


class GenerateKnowledgeMapRequest(BaseModel):
    notebook_id: Optional[str] = None
    source_id: Optional[str] = None


class KnowledgeMapResponse(BaseModel):
    id: str
    notebook: Optional[str] = None
    source: Optional[str] = None
    data: str
    status: str


def _map_response(m: KnowledgeMap) -> KnowledgeMapResponse:
    return KnowledgeMapResponse(
        id=m.id or "",
        notebook=m.notebook,
        source=m.source,
        data=m.data or "{}",
        status=m.status or "idle",
    )


async def _gather_context(notebook_id: Optional[str], source_id: Optional[str]) -> str:
    lines = []

    if source_id:
        source = await Source.get(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        lines.append(f"课件：{source.title or source_id}")

        chapter_rows = await repo_query(
            "SELECT * FROM chapter WHERE source = $source ORDER BY order_index ASC",
            {"source": ensure_record_id(source_id)},
        )
        kp_rows = await repo_query(
            "SELECT * FROM knowledge_point WHERE source = $source ORDER BY created ASC",
            {"source": ensure_record_id(source_id)},
        )
    elif notebook_id:
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
        lines.append(f"科目：{notebook.name}")

        chapter_rows = await repo_query(
            "SELECT * FROM chapter WHERE notebook = $notebook ORDER BY order_index ASC",
            {"notebook": ensure_record_id(notebook_id)},
        )
        kp_rows = await repo_query(
            "SELECT * FROM knowledge_point WHERE notebook = $notebook ORDER BY created ASC",
            {"notebook": ensure_record_id(notebook_id)},
        )
    else:
        raise HTTPException(status_code=400, detail="notebook_id or source_id is required")

    if chapter_rows:
        lines.append("\n## 章节")
        for row in chapter_rows:
            chapter = Chapter(**row)
            lines.append(
                f"- {chapter.order_index}. {chapter.title}"
                + (f"：{chapter.summary}" if chapter.summary else "")
            )
    if kp_rows:
        lines.append("\n## 知识点")
        for row in kp_rows:
            kp = KnowledgePoint(**row)
            lines.append(f"- {kp.title}" + (f"：{kp.summary}" if kp.summary else ""))

    return "\n".join(lines)


@router.get("/virtual-classroom/knowledge-map", response_model=KnowledgeMapResponse)
async def get_knowledge_map(
    notebook_id: Optional[str] = Query(None),
    source_id: Optional[str] = Query(None),
):
    conditions = []
    vars = {}
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
        f"SELECT * FROM knowledge_map {where} ORDER BY created DESC LIMIT 1",
        vars,
    )
    if not rows:
        return KnowledgeMapResponse(id="", notebook=notebook_id, source=source_id, data="{}", status="idle")
    return _map_response(KnowledgeMap(**rows[0]))


@router.post("/virtual-classroom/knowledge-map/generate", response_model=KnowledgeMapResponse)
async def generate_knowledge_map(data: GenerateKnowledgeMapRequest):
    """Generate a chapter-evolution knowledge map using the configured LLM."""
    context = await _gather_context(data.notebook_id, data.source_id)
    if not context.strip():
        raise HTTPException(status_code=400, detail="No chapters or knowledge points to build a map")

    system_prompt = SystemMessage(
        content=(
            "你是一个学科脉络大师。请根据提供的章节和知识点，生成“章节演进知识地图”。\n"
            "要求：\n"
            "1. 先写一段 storyline 总览，讲清楚整个课件/科目的演进逻辑\n"
            "2. stages 按章节顺序排列，每个 stage 包含：label、summary、bridgeToNext、concepts\n"
            "3. bridgeToNext 解释“为什么要学下一章/下一阶段”\n"
            "4. concepts 从知识点中提炼 2-5 个，每个含 label 和 brief\n"
            "5. 只输出 JSON，不要 Markdown\n"
            'JSON 格式：{"title":"标题","storyline":"总览","stages":[{"id":"stage-1","label":"阶段标题","summary":"解决什么问题","bridgeToNext":"为什么引出下一阶段","concepts":[{"label":"概念","brief":"一句话"}]}]}'
        )
    )
    human_message = HumanMessage(content=context)
    chain = await provision_langchain_model(
        str([system_prompt, human_message]),
        None,
        "chat",
        max_tokens=8192,
    )
    response = await chain.ainvoke([system_prompt, human_message])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        json.loads(raw)
    except Exception:
        raise HTTPException(status_code=500, detail=f"Failed to parse knowledge map output: {raw[:200]}")

    existing = await repo_query(
        "SELECT * FROM knowledge_map WHERE notebook = $notebook AND source = $source ORDER BY created DESC LIMIT 1",
        {
            "notebook": ensure_record_id(data.notebook_id) if data.notebook_id else None,
            "source": ensure_record_id(data.source_id) if data.source_id else None,
        },
    )
    if existing:
        km = KnowledgeMap(**existing[0])
        km.data = raw
        km.status = "done"
        await km.save()
    else:
        km = KnowledgeMap(
            notebook=data.notebook_id,
            source=data.source_id,
            data=raw,
            status="done",
        )
        await km.save()
    return _map_response(km)
