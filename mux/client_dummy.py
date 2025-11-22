from sqlite3 import connect
from typing import Optional, Self
from client_interface import ClientInterface, Content, Conversation, Message
import uuid
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionContentPartParam

class DummyClient(ClientInterface):
    def __init__(self):
        self.conn = None
        self.client = AsyncOpenAI(
            api_key="dummy-key",
            base_url="http://dummy_litellm:4000/v1",
        )

    async def __aenter__(self) -> Self:
        self.conn = connect('conversations.db')
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dummy_conversations (
                conv_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                topic TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dummy_messages (
                message_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                conv_id TEXT,
                role TEXT,
                content TEXT
            )
        ''')
        cursor.execute('''
            INSERT OR REPLACE INTO dummy_conversations (conv_id, topic)
            VALUES ('tc', 'Test Conversation 1')
        ''')
        self.conn.commit()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.conn:
            self.conn.close()

    async def create_conversation(self) -> str:
        if not self.conn:
            raise Exception("Database connection is not established.")
        conv_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO dummy_conversations (conv_id, topic) VALUES (?, ?)", (conv_id, ""))
        self.conn.commit()
        return conv_id

    async def delete_conversation(self, conv_id: str) -> bool:
        if not self.conn:
            raise Exception("Database connection is not established.")
        cursor = self.conn.cursor()
        response = cursor.execute("DELETE FROM dummy_conversations WHERE conv_id = ?", (conv_id,))
        self.conn.commit()
        return response.rowcount != 0
    
    async def list_conversations(self) -> list[Conversation]:
        if not self.conn:
            raise Exception("Database connection is not established.")
        cursor = self.conn.cursor()
        cursor.execute("SELECT conv_id, created_at, topic FROM dummy_conversations")
        return [
            Conversation(id=row[0], created_at=row[1], topic=row[2]) for row in cursor.fetchall()
        ]

    async def get_messages(self, conv_id: str) -> tuple[Conversation, list[Message]]:
        if not self.conn:
            raise Exception("Database connection is not established.")
        cursor = self.conn.cursor()
        cursor.execute("SELECT conv_id, created_at, topic FROM dummy_conversations WHERE conv_id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            raise Exception("Conversation not found.")
        conversation = Conversation(id=conv_row[0], created_at=conv_row[1], topic=conv_row[2])
        messages = await self._get_messages(conv_id)
        return conversation, messages
        
    async def _get_messages(self, conv_id: str) -> list[Message]:
        if not self.conn:
            raise Exception("Database connection is not established.")
        cursor = self.conn.cursor()
        cursor.execute("SELECT message_id, role, content FROM dummy_messages WHERE conv_id = ? ORDER BY created_at", (conv_id,))
        messages = [
            Message(
                message_id=row[0],
                role=row[1],
                content=[Content(type="text", text=row[2])]
            ) for row in cursor.fetchall()
        ]
        
        return messages
    
    async def _complete(self, messages: list[Message]) -> tuple[str, list[Content]]:
        oai_messages:list[ChatCompletionMessageParam] = []
        for msg in messages:
            match msg.role:
                case "system":
                    oai_messages.append(
                        {
                            "role": msg.role,
                            "content": [{"type": c.type, "text": c.text} for c in msg.content]
                        }
                    )
                case "user":
                    oai_messages.append(
                        {
                            "role": msg.role,
                            "content": [{"type": c.type, "text": c.text} for c in msg.content]
                        }
                    
                    )
                case "assistant":
                    oai_messages.append({
                        "role": msg.role,
                        "content": [{"type": c.type, "text": c.text} for c in msg.content]
                    })
        response = await self.client.chat.completions.create(
            model="dummy-model",
            messages=oai_messages
        )

        if not isinstance(response.choices[0].message.content, str):
            raise Exception("Unsupported content type in response.")
        return response.id, [Content(type="text", text=response.choices[0].message.content)]

    async def post_user_message(self, conv_id: str, content: list[Content]) -> Optional[tuple[str, str]]:
        if not self.conn:
            raise Exception("Database connection is not established.")
        if len(content) != 1:
            raise Exception("Only single content messages are supported in DummyClient.")
        cursor = self.conn.cursor()

        cursor.execute("SELECT conv_id FROM dummy_conversations WHERE conv_id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            return None

        message_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO dummy_messages (conv_id, message_id, role, content) VALUES (?, ?, ?, ?)",
            (conv_id, message_id, "user", content[0].text)
        )
        self.conn.commit()

        messages = await self._get_messages(conv_id)
        response_id, response = await self._complete(
            messages + [
                Message(
                    message_id=message_id,
                    role="user",
                    content=content
                )
            ]
        )

        cursor.execute(
            "INSERT INTO dummy_messages (conv_id, message_id, role, content) VALUES (?, ?, ?, ?)",
            (conv_id, response_id, "assistant", response[0].text)
        )

        self.conn.commit()
        return message_id, response_id