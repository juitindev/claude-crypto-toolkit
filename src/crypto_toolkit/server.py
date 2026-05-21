"""FastAPI SSE server exposing the orchestrator over HTTP."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Generator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from crypto_toolkit.orchestrator import run_conversation
from crypto_toolkit.streaming import Done, Error, Event, event_to_sse

app = FastAPI(
    title="Claude Crypto Toolkit",
    description="SSE chat endpoint backed by the Claude orchestrator.",
    version="0.1.0",
)


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream a chat completion as Server-Sent Events."""
    return StreamingResponse(_stream(req), media_type="text/event-stream")


def _stream(req: ChatRequest) -> Generator[bytes, None, None]:
    *history_msgs, last = req.messages
    if last.role != "user":
        yield _sse("error", {"message": "Last message must have role='user'"})
        yield _sse("done", {"stop_reason": "error", "usage": {}})
        return

    history = [{"role": m.role, "content": m.content} for m in history_msgs]
    events: queue.Queue[Event | None] = queue.Queue()

    def runner() -> None:
        try:
            run_conversation(
                user_message=last.content,
                history=history,
                on_event=events.put,
            )
        except Exception as exc:  # noqa: BLE001
            events.put(Error(message=str(exc)))
            events.put(Done(stop_reason="error", usage={}))
        finally:
            events.put(None)

    worker = threading.Thread(target=runner, daemon=True)
    worker.start()

    while True:
        event = events.get()
        if event is None:
            break
        name, payload = event_to_sse(event)
        yield _sse(name, payload)


def _sse(event_name: str, payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_name}\ndata: {body}\n\n".encode()
