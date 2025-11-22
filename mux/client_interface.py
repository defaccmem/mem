from abc import ABC, abstractmethod
from typing import Optional, Self
from pydantic import BaseModel

class Conversation(BaseModel):
    id: str
    created_at: str
    topic: Optional[str] = None

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
