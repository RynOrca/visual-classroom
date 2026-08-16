"""Domain models for the V3 virtual classroom extension.

These models extend Open Notebook's core data model with chapter-level
organization, knowledge points, mistakes, quiz sessions, and conversation notes.
"""

from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import Field, field_validator
from surrealdb import RecordID

from open_notebook.database.repository import ensure_record_id
from open_notebook.domain.base import ObjectModel


def _ensure_record(value: Optional[str]) -> Optional[RecordID]:
    if value is None or value == "":
        return None
    return ensure_record_id(value)


class Chapter(ObjectModel):
    table_name: ClassVar[str] = "chapter"
    title: str
    source: str
    notebook: Optional[str] = None
    order_index: int = 0
    summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    @field_validator("source", "notebook", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        if data.get("source"):
            data["source"] = _ensure_record(data["source"])
        if data.get("notebook"):
            data["notebook"] = _ensure_record(data["notebook"])
        return data


class KnowledgePoint(ObjectModel):
    table_name: ClassVar[str] = "knowledge_point"
    title: str
    summary: Optional[str] = None
    source: str
    chapter: Optional[str] = None
    notebook: Optional[str] = None
    page_number: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    hotness: Optional[float] = 0

    @field_validator("source", "chapter", "notebook", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        for key in ("source", "chapter", "notebook"):
            if data.get(key):
                data[key] = _ensure_record(data[key])
        return data


class MistakeBook(ObjectModel):
    table_name: ClassVar[str] = "mistake_book"
    source: str
    notebook: Optional[str] = None
    knowledge_point: Optional[str] = None
    page_number: Optional[int] = None
    quiz_type: str = "single_choice"
    question: str
    options: Optional[List[str]] = None
    correct_answer: str
    user_answer: str
    is_correct: bool = False
    tags: List[str] = Field(default_factory=list)
    mastered_at: Optional[datetime] = None

    @field_validator("source", "notebook", "knowledge_point", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        for key in ("source", "notebook", "knowledge_point"):
            if data.get(key):
                data[key] = _ensure_record(data[key])
        return data


class QuizSession(ObjectModel):
    table_name: ClassVar[str] = "quiz_session"
    notebook: Optional[str] = None
    source: Optional[str] = None
    total_questions: int = 0
    correct_count: int = 0
    score: float = 0
    details: Optional[str] = None

    @field_validator("notebook", "source", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        for key in ("notebook", "source"):
            if data.get(key):
                data[key] = _ensure_record(data[key])
        return data


class ConversationNote(ObjectModel):
    table_name: ClassVar[str] = "conversation_note"
    chat_session: Optional[str] = None
    source: Optional[str] = None
    notebook: Optional[str] = None
    knowledge_point: Optional[str] = None
    question: str
    answer: str
    note_type: str = "qa"
    tags: List[str] = Field(default_factory=list)

    @field_validator("chat_session", "source", "notebook", "knowledge_point", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        for key in ("chat_session", "source", "notebook", "knowledge_point"):
            if data.get(key):
                data[key] = _ensure_record(data[key])
        return data


class KnowledgeMap(ObjectModel):
    table_name: ClassVar[str] = "knowledge_map"
    notebook: Optional[str] = None
    source: Optional[str] = None
    data: str = "{}"
    status: str = "idle"

    @field_validator("notebook", "source", mode="before")
    @classmethod
    def normalize_record_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, RecordID):
            return str(value)
        return value

    def _prepare_save_data(self) -> Dict[str, Any]:
        data = super()._prepare_save_data()
        for key in ("notebook", "source"):
            if data.get(key):
                data[key] = _ensure_record(data[key])
        return data
