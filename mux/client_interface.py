from abc import ABC, abstractmethod
from pydantic import BaseModel

class ClientInterface(ABC):
    @abstractmethod
    async def create_conversation(self) -> str:
        ...

    @abstractmethod
    async def delete_conversation(self, conv_id: str) -> bool:
        ...

# class Conversation(BaseModel):
#     id: str
#     created_at: datetime
#     topic: Optional[str] = None
