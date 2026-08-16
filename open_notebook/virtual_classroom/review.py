"""Review-route generation for V3 virtual classroom.

Turns a knowledge map (plus knowledge points, conversation notes and mistakes)
into a structured "overview -> drill down" review plan.
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.virtual_classroom.domain import (
    ConversationNote,
    KnowledgeMap,
    KnowledgePoint,
    MistakeBook,
    ReviewRoute,
)


async def _verify_scope(notebook_id: Optional[str], source_id: Optional[str]) -> None:
    if source_id:
        source = await Source.get(source_id)
        if not source:
            raise ValueError("Source not found")
    if notebook_id:
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise ValueError("Notebook not found")


def _as_record_id(value: Optional[str]) -> Any:
    return ensure_record_id(value) if value else None


async def _get_knowledge_map(
    notebook_id: Optional[str], source_id: Optional[str]
) -> Optional[KnowledgeMap]:
    conditions = []
    vars: Dict[str, Any] = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if not conditions:
        return None
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM knowledge_map {where} ORDER BY created DESC LIMIT 1",
        vars,
    )
    if not rows:
        return None
    return KnowledgeMap(**rows[0])


async def _list_knowledge_points(
    notebook_id: Optional[str], source_id: Optional[str]
) -> List[KnowledgePoint]:
    conditions = []
    vars: Dict[str, Any] = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if not conditions:
        return []
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM knowledge_point {where} ORDER BY created ASC",
        vars,
    )
    return [KnowledgePoint(**row) for row in rows]


async def _list_conversation_notes(
    notebook_id: Optional[str], source_id: Optional[str]
) -> List[ConversationNote]:
    conditions = []
    vars: Dict[str, Any] = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if not conditions:
        return []
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM conversation_note {where} ORDER BY created DESC",
        vars,
    )
    return [ConversationNote(**row) for row in rows]


async def _list_mistakes(
    notebook_id: Optional[str], source_id: Optional[str]
) -> List[MistakeBook]:
    conditions = []
    vars: Dict[str, Any] = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if not conditions:
        return []
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM mistake_book {where} ORDER BY created DESC",
        vars,
    )
    return [MistakeBook(**row) for row in rows]


def _build_context(
    knowledge_map: Optional[KnowledgeMap],
    knowledge_points: List[KnowledgePoint],
    conversation_notes: List[ConversationNote],
    mistakes: List[MistakeBook],
) -> str:
    lines: List[str] = []

    if knowledge_map:
        try:
            data = json.loads(knowledge_map.data or "{}")
        except Exception:
            data = {}
        lines.append("## 知识地图")
        lines.append(f"标题：{data.get('title', '')}")
        if data.get("storyline"):
            lines.append(f"总览：{data['storyline']}")
        for stage in data.get("stages", []):
            lines.append(
                f"- 阶段 {stage.get('id', '')}: {stage.get('label', '')}"
                f" | 总结：{stage.get('summary', '')}"
                f" | 引出：{stage.get('bridgeToNext', '')}"
            )
            for concept in stage.get("concepts", []):
                lines.append(f"  - 概念：{concept.get('label', '')} {concept.get('brief', '')}")

    if knowledge_points:
        lines.append("\n## 知识点")
        for kp in knowledge_points:
            lines.append(
                f"- {kp.id}: {kp.title} | {kp.summary or ''} | tags={','.join(kp.tags or [])}"
            )

    if conversation_notes:
        lines.append("\n## 对话笔记")
        for note in conversation_notes:
            lines.append(
                f"- {note.id}: Q={note.question} | A={note.answer} | type={note.note_type}"
                f" | tags={','.join(note.tags or [])} | kp={note.knowledge_point or 'null'}"
            )

    if mistakes:
        lines.append("\n## 错题")
        for mistake in mistakes:
            lines.append(
                f"- {mistake.id}: {mistake.question} | 正确答案={mistake.correct_answer}"
                f" | kp={mistake.knowledge_point or 'null'}"
            )

    return "\n".join(lines)


async def generate_review_route(
    notebook_id: Optional[str], source_id: Optional[str]
) -> str:
    """Generate and persist a review route JSON string."""
    await _verify_scope(notebook_id, source_id)
    if not source_id and not notebook_id:
        raise ValueError("notebook_id or source_id is required")

    knowledge_map = await _get_knowledge_map(notebook_id, source_id)
    knowledge_points = await _list_knowledge_points(notebook_id, source_id)
    conversation_notes = await _list_conversation_notes(notebook_id, source_id)
    mistakes = await _list_mistakes(notebook_id, source_id)

    context = _build_context(
        knowledge_map, knowledge_points, conversation_notes, mistakes
    )
    if not context.strip():
        raise ValueError("No knowledge map or review data available")

    system_prompt = SystemMessage(
        content=(
            "你是一个复习路线规划助手。请根据知识地图、知识点、对话笔记和错题，"
            "生成一份“俯瞰 → 下钻”的复习路线。\n"
            "要求：\n"
            "1. overview 用 3-5 句话讲清章节/阶段的演进逻辑，让学习者先俯瞰全局\n"
            "2. stages 按学习顺序排列，每个 stage 包含 stage_id、stage_label、why、drill\n"
            "3. drill 是该阶段需要下钻复习的知识点/问题，每个包含 title、summary、"
            "knowledge_point_id、conversation_note_ids、mistake_ids\n"
            "4. 尽量引用上下文里给出的真实 id；没有对应 id 就填 null 或 []\n"
            "5. 只输出 JSON，不要 Markdown\n"
            'JSON 格式：{"title":"复习路线标题","overview":"俯瞰总览","stages":[{"stage_id":"stage-1","stage_label":"阶段标题","why":"为什么这样排","drill":[{"title":"知识点/问题","summary":"复习要点","knowledge_point_id":null,"conversation_note_ids":[],"mistake_ids":[]}]}]}'
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
    except Exception as e:
        raise ValueError(f"Failed to parse review route output: {raw[:200]}") from e

    existing = await repo_query(
        "SELECT * FROM review_route WHERE notebook = $notebook AND source = $source ORDER BY created DESC LIMIT 1",
        {
            "notebook": _as_record_id(notebook_id),
            "source": _as_record_id(source_id),
        },
    )
    if existing:
        route = ReviewRoute(**existing[0])
        route.data = raw
        route.status = "done"
        await route.save()
    else:
        route = ReviewRoute(
            notebook=notebook_id,
            source=source_id,
            data=raw,
            status="done",
        )
        await route.save()
    return raw
