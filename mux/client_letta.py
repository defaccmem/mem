from typing import Optional, Self, Sequence
from letta_client import AsyncLetta
from letta_client.types.agents.text_content import TextContent
from letta_client.types.agents.text_content_param import TextContentParam
from letta_client.types.agents.image_content import ImageContent
from letta_client.types.agents.letta_assistant_message_content_union import LettaAssistantMessageContentUnion
from letta_client.types.agents.assistant_message import AssistantMessage
from letta_client.types.agents.message_create_params import Message as LettaMessage

from client_interface import ClientInterface, Content, Conversation, Message

# MODEL="openai/gpt-5.1"
# MODEL="openai/dummy-model"
MODEL="lmstudio_openai/gpt-4o-mini"
EMBEDDING_MODEL="openai/text-embedding-3-small"

class LettaClient(ClientInterface):
    def __init__(self):
        self.client = AsyncLetta(
            base_url="http://letta:8283",
            api_key="dummy-letta-key"
        )

    async def __aenter__(self) -> Self:
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def create_conversation(self) -> str:
        agent_state = await self.client.agents.create(
            model=MODEL,
            embedding=EMBEDDING_MODEL,
            memory_blocks=[
                {
                    "label": "human",
                    "value": "You know nothing about the human yet."
                },
                {
                    "label": "persona",
                    "value": "You are a helpful and friendly AI assistant."
                }
            ],
            # tools=["web_search", "run_code"]
        )
        return agent_state.id
    
    async def delete_conversation(self, conv_id: str) -> bool:
        response = await self.client.agents.delete(agent_id=conv_id)
        return True

    async def list_conversations(self) -> list[Conversation]:
        agents = await self.client.agents.list()
        conversations = []
        async for agent in agents:
            conversations.append(
                Conversation(
                    id=agent.id,
                    created_at=str(agent.created_at),
                    topic=agent.description or ""
                )
            )
        return conversations

    async def get_messages(self, conv_id: str) -> tuple[Conversation, list[Message]]:
        agent_state = await self.client.agents.retrieve(agent_id=conv_id)
        messages = await self.client.agents.messages.list(agent_id=conv_id)
        conversation = Conversation(
            id=agent_state.id,
            created_at=str(agent_state.created_at),
            topic=agent_state.description or ""
        )
        message_list = []
        async for msg in messages:
            match msg.message_type:
                case "system_message":
                    message_list.append(
                        Message(
                            message_id=msg.id,
                            role="system",
                            content=_translate_content(msg.content)
                        )
                    )
                case "assistant_message":
                    message_list.append(
                        Message(
                            message_id=msg.id,
                            role="assistant",
                            content=_translate_content(msg.content)
                        )
                    )
                case "user_message":
                    message_list.append(
                        Message(
                            message_id=msg.id,
                            role="user",
                            content=_translate_content(msg.content)
                        )
                    )
        return conversation, message_list
    
    async def post_user_message(self, conv_id: str, content: list[Content]) -> Optional[tuple[str, str]]:
        letta_content: list[TextContentParam] = []
        for c in content:
            letta_content.append(
                {"type":c.type, "text":c.text}
            )
        letta_message: LettaMessage = {
                "role": "user",
                "content": letta_content
            }
        response = await self.client.agents.messages.create(
            agent_id=conv_id,
            messages=[letta_message]
        )
        print("THE RESPONSE WAS:")
        print(response)

        msgs = [m for m in response.messages if isinstance(m, AssistantMessage)]
        if len(msgs) == 0:
            raise Exception("No AssistantMessage in response")
        return f"{msgs[0].id}:request", msgs[0].id

    # async def _complete(self, conv_id: str, messages: list[Message]) -> tuple[str, list[Content]]:
    #     letta_messages: list[LettaMessage] = []
    #     for msg in messages:
    #         letta_messages.append(
    #             {
    #                 "role": msg.role,
    #                 "content": [ {"type": c.type, "text": c.text} for c in msg.content ]
    #             }
    #         )
    #     response = self.client.agents.messages.create(
    #         agent_id="temporary-agent",
    #         messages=letta_messages
    #     ).messages[0]
    #     if not isinstance(response, AssistantMessage):
    #         raise Exception("Expected an AssistantMessage response")
    #     return response.id, _translate_content(response.content)

def _translate_content(content: Sequence[TextContent | ImageContent | LettaAssistantMessageContentUnion] | str) -> list[Content]:
    if isinstance(content, str):
        return [Content(type="text", text=content)]
    result: list[Content] = []
    for part in content:
        match part:
            case TextContent(type="text", text=text):
                result.append(Content(type="text", text=text))
            case _:
                continue
    return result

# response = client.agents.messages.create(
#     agent_id=agent_state.id,
#     messages=[
#         {
#             "role": "user",
#             "content": "Hey, nice to meet you, my name is Brad."
#         }
#     ]
# )

# print(response)

if __name__ == "__main__":
    import asyncio

    async def main():
        async with LettaClient() as client:
            conv_id = await client.create_conversation()
            print(f"Created conversation: {conv_id}")
    asyncio.run(main())