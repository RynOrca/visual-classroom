"""V3 virtual classroom conversation-organizing agent API."""

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from open_notebook.database.repository import ensure_record_id, repo_query
from open_notebook.virtual_classroom.conversation import organize_chat_session
from open_notebook.virtual_classroom.domain import ConversationNote

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
    try:
        notes = await organize_chat_session(data.chat_session_id)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not notes:
        raise HTTPException(
            status_code=400,
            detail="No Q&A pairs found in this chat session",
        )
    return [_cn_response(note) for note in notes]
