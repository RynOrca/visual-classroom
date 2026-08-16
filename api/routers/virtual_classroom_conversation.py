"""V3 virtual classroom conversation-organizing agent API."""

import asyncio
import json
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from api.routers._chat_shared import get_session_or_404
from open_notebook.ai.provision import provision_langchain_model
from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.domain.notebook import ChatSession
from open_notebook.graphs.chat import graph as chat_graph
from open_notebook.graphs.source_chat import source_chat_graph
from open_notebook.virtual_classroom.domain import ConversationNote, KnowledgePoint

router = APIRouter()


# ---------- Schemas ----------

class ConversationNoteResponse(BaseModel):
    id: str
    chat_session: Optional[str] = None
    source: Optional[str] = None
    notebook: Optional[str] = None
    knowledge_point: Optional[str] = None
    question: str
    answer: str
    note_type: str = "qa"
    tags: List[str] = []
    created: Optional[str] = None


class OrganizeConversationRequest(BaseModel):
    chat_session_id: str


def _cn_response(note: ConversationNote) -> ConversationNoteResponse:
    return ConversationNoteResponse(
        id=note.id or "",
        chat_session=note.chat_session,
        source=note.source,
        notebook=note.notebook,
        knowledge_point=note.knowledge_point,
        question=note.question,
        answer=note.answer,
        note_type=note.note_type or "qa",
        tags=note.tags or [],
        created=str(note.created) if note.created else None,
    )


async def _resolve_session(
    session_id: str,
) -> Tuple[str, ChatSession, Optional[str], Optional[str], List[Any]]:
    """Resolve a chat session and return its normalized id, model, relations and messages."""
    full_session_id, session = await get_session_or_404(session_id)

    relations = await repo_query(
        "SELECT out FROM refers_to WHERE in = $session_id",
        {"session_id": ensure_record_id(full_session_id)},
    )

    source_id: Optional[str] = None
    notebook_id: Optional[str] = None
    for relation in relations:
        out = relation.get("out")
        if not out:
            continue
        out_str = str(out)
        if out_str.startswith("source:"):
            source_id = out_str
        elif out_str.startswith("notebook:"):
            notebook_id = out_str

    graph = source_chat_graph if source_id else chat_graph
    thread_state = await asyncio.to_thread(
        graph.get_state,
        config=RunnableConfig(configurable={"thread_id": full_session_id}),
    )
    messages: List[Any] = []
    if thread_state and thread_state.values and "messages" in thread_state.values:
        messages = thread_state.values["messages"]

    return full_session_id, session, source_id, notebook_id, messages


def _extract_qa_pairs(messages: List[Any]) -> List[Tuple[str, str]]:
    """Pair each human message with the next AI response."""
    pairs: List[Tuple[str, str]] = []
    pending_question: Optional[str] = None
    for msg in messages:
        msg_type = getattr(msg, "type", None)
        content = getattr(msg, "content", "") or ""
        if not isinstance(content, str):
            content = str(content)
        if msg_type == "human":
            pending_question = content
        elif msg_type == "ai" and pending_question is not None:
            pairs.append((pending_question, content))
            pending_question = None
    return pairs


async def _organize_pair(
    question: str,
    answer: str,
    source_id: Optional[str],
    notebook_id: Optional[str],
) -> dict[str, Any]:
    system_prompt = SystemMessage(
        content=(
            "你是一个课堂对话整理助手。请把一段问答整理成适合复习的知识卡片。\n"
            "要求：\n"
            "1. question 用一句精简的问题/标题概括用户提问\n"
            "2. answer 用 1-3 句话概括核心知识点或结论\n"
            "3. note_type 只能是以下之一：definition、derivation、example、pitfall、application、qa\n"
            "4. tags 给 2-5 个标签\n"
            "5. knowledge_point_title 如果能对应课件知识点就填知识点标题，否则填 null\n"
            "6. 只输出 JSON，不要 Markdown，不要额外文字\n"
            'JSON 格式：{"question":"问题/标题","answer":"核心结论","note_type":"definition","tags":["标签1","标签2"],"knowledge_point_title":null}'
        )
    )
    human_message = HumanMessage(
        content=(
            f"用户问题：\n{question}\n\n"
            f"AI 回答：\n{answer[:4000]}\n\n"
            f"source_id: {source_id or 'null'}\n"
            f"notebook_id: {notebook_id or 'null'}"
        )
    )

    chain = await provision_langchain_model(
        str([system_prompt, human_message]),
        None,
        "chat",
        max_tokens=1024,
    )
    response = await chain.ainvoke([system_prompt, human_message])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse conversation note output: {raw[:200]}",
        )

    note_type = str(data.get("note_type") or "qa")
    if note_type not in {
        "definition",
        "derivation",
        "example",
        "pitfall",
        "application",
        "qa",
    }:
        note_type = "qa"

    return {
        "question": str(data.get("question") or question).strip(),
        "answer": str(data.get("answer") or answer).strip(),
        "note_type": note_type,
        "tags": [str(t) for t in (data.get("tags") or []) if str(t).strip()],
        "knowledge_point_title": (
            str(data.get("knowledge_point_title")).strip()
            if data.get("knowledge_point_title")
            else None
        ),
    }


async def _match_knowledge_point(
    title: Optional[str],
    source_id: Optional[str],
    notebook_id: Optional[str],
) -> Optional[str]:
    if not title:
        return None
    conditions = []
    vars: dict[str, Any] = {}
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
        f"SELECT * FROM knowledge_point {where} ORDER BY created ASC",
        vars,
    )
    normalized = title.lower().strip()
    for row in rows:
        kp = KnowledgePoint(**row)
        kp_title = (kp.title or "").lower().strip()
        if not kp_title:
            continue
        if (
            kp_title == normalized
            or normalized in kp_title
            or kp_title in normalized
        ):
            return kp.id
    return None


async def _delete_existing_notes(session_id: str) -> None:
    await repo_query(
        "DELETE conversation_note WHERE chat_session = $chat_session",
        {"chat_session": ensure_record_id(session_id)},
    )


# ---------- Routes ----------

@router.get(
    "/virtual-classroom/conversation-notes",
    response_model=List[ConversationNoteResponse],
)
async def list_conversation_notes(
    source_id: Optional[str] = Query(None),
    notebook_id: Optional[str] = Query(None),
    chat_session_id: Optional[str] = Query(None),
):
    conditions = []
    vars: dict[str, Any] = {}
    if source_id:
        conditions.append("source = $source")
        vars["source"] = ensure_record_id(source_id)
    if notebook_id:
        conditions.append("notebook = $notebook")
        vars["notebook"] = ensure_record_id(notebook_id)
    if chat_session_id:
        conditions.append("chat_session = $chat_session")
        vars["chat_session"] = ensure_record_id(chat_session_id)
    if not conditions:
        raise HTTPException(
            status_code=400,
            detail="source_id, notebook_id or chat_session_id is required",
        )
    where = "WHERE " + " AND ".join(conditions)
    rows = await repo_query(
        f"SELECT * FROM conversation_note {where} ORDER BY created DESC",
        vars,
    )
    return [_cn_response(ConversationNote(**row)) for row in rows]


@router.post(
    "/virtual-classroom/conversation-notes/organize",
    response_model=List[ConversationNoteResponse],
)
async def organize_conversation_notes(data: OrganizeConversationRequest):
    """Turn a chat session's Q&A pairs into structured conversation notes."""
    (
        full_session_id,
        _session,
        source_id,
        notebook_id,
        messages,
    ) = await _resolve_session(data.chat_session_id)

    pairs = _extract_qa_pairs(messages)
    if not pairs:
        raise HTTPException(
            status_code=400,
            detail="No Q&A pairs found in this chat session",
        )

    await _delete_existing_notes(full_session_id)

    saved_notes = []
    for question, answer in pairs:
        organized = await _organize_pair(
            question, answer, source_id, notebook_id
        )
        knowledge_point_id = await _match_knowledge_point(
            organized["knowledge_point_title"], source_id, notebook_id
        )
        note = ConversationNote(
            chat_session=full_session_id,
            source=source_id,
            notebook=notebook_id,
            knowledge_point=knowledge_point_id,
            question=organized["question"],
            answer=organized["answer"],
            note_type=organized["note_type"],
            tags=organized["tags"],
        )
        await note.save()
        saved_notes.append(_cn_response(note))

    return saved_notes
