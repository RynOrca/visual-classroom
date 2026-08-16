"""Tests for V3 virtual-classroom conversation organizing agent."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.virtual_classroom_conversation import router
from open_notebook.virtual_classroom.conversation import extract_qa_pairs


class _FakeMessage:
    def __init__(self, type: str, content: str):
        self.type = type
        self.content = content


def test_extract_qa_pairs_pairs_human_with_next_ai():
    messages = [
        _FakeMessage("human", "What is a MAC?"),
        _FakeMessage("ai", "A MAC is ..."),
        _FakeMessage("human", "How does AES work?"),
        _FakeMessage("human", "What is AE?"),
        _FakeMessage("ai", "AE combines encryption and MAC."),
    ]

    assert extract_qa_pairs(messages) == [
        ("What is a MAC?", "A MAC is ..."),
        ("What is AE?", "AE combines encryption and MAC."),
    ]


def test_organize_conversation_notes_endpoint():
    app = FastAPI()
    app.include_router(router, prefix="/api")

    class FakeNote:
        def __init__(self, **kwargs):
            self.id = "conversation_note:1"
            self.chat_session = kwargs.get("chat_session")
            self.source = kwargs.get("source")
            self.notebook = kwargs.get("notebook")
            self.knowledge_point = kwargs.get("knowledge_point")
            self.question = kwargs.get("question")
            self.answer = kwargs.get("answer")
            self.note_type = kwargs.get("note_type")
            self.tags = kwargs.get("tags")
            self.created = None

    fake_note = FakeNote(
        chat_session="chat_session:1",
        source="source:1",
        question="What is X?",
        answer="X is ...",
        note_type="definition",
        tags=["x"],
    )

    with patch(
        "api.routers.virtual_classroom_conversation.organize_chat_session",
        new=AsyncMock(return_value=[fake_note]),
    ):
        client = TestClient(app)
        response = client.post(
            "/api/virtual-classroom/conversation-notes/organize",
            json={"chat_session_id": "chat_session:1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["question"] == "What is X?"
    assert payload[0]["answer"] == "X is ..."
    assert payload[0]["note_type"] == "definition"
    assert payload[0]["tags"] == ["x"]
