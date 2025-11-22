from client_interface import ClientInterface
import uuid

class DummyClient(ClientInterface):
    async def create_conversation(self) -> str:
        return str(uuid.uuid4())

    async def delete_conversation(self, conv_id: str) -> bool:
        return True