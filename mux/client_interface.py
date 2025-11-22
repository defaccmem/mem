from abc import ABC, abstractmethod
from typing import Literal, Optional, Self
from pydantic import BaseModel

class Conversation(BaseModel):
    id: str
    created_at: str
    topic: Optional[str] = None

class Content(BaseModel):
    type: Literal["text"]
    text: str

class Message(BaseModel):
    message_id: str
    role: str
    content: list[Content]

class ClientInterface(ABC):
    @abstractmethod
    async def __aenter__(self) -> Self:
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_value, traceback):
        ...

    @abstractmethod
    async def create_conversation(self) -> str:
        ...

    @abstractmethod
    async def delete_conversation(self, conv_id: str) -> bool:
        ...

    @abstractmethod
    async def list_conversations(self) -> list[Conversation]:
        ...

    @abstractmethod
    async def get_messages(self, conv_id: str) -> tuple[Conversation, list[Message]]:
        ...