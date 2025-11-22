from sqlite3 import connect
from typing import Self
from client_interface import ClientInterface, Content, Conversation
import uuid

class DummyClient(ClientInterface):
    def __init__(self):
        self.conn = None

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

    async def get_messages(self, conv_id: str) -> tuple[Conversation, list]:
        if not self.conn:
            raise Exception("Database connection is not established.")
        cursor = self.conn.cursor()
        cursor.execute("SELECT conv_id, created_at, topic FROM dummy_conversations WHERE conv_id = ?", (conv_id,))
        conv_row = cursor.fetchone()
        if not conv_row:
            raise Exception("Conversation not found.")
        conversation = Conversation(id=conv_row[0], created_at=conv_row[1], topic=conv_row[2])
        
        cursor.execute("SELECT message_id, role, content FROM dummy_messages WHERE conv_id = ? ORDER BY created_at", (conv_id,))
        messages = [
            {
                "message_id": row[0],
                "role": row[1],
                "content": [{"type": "text", "text": row[2]}]
            } for row in cursor.fetchall()
        ]
        
        return conversation, messages
    
    async def post_user_message(self, conv_id: str, content: list[Content]) -> None:
        if not self.conn:
            raise Exception("Database connection is not established.")
        if len(content) != 1:
            raise Exception("Only single content messages are supported in DummyClient.")
        cursor = self.conn.cursor()
        message_id = str(uuid.uuid4())
        text_content = content[0].text
        cursor.execute(
            "INSERT INTO dummy_messages (conv_id, message_id, role, content) VALUES (?, ?, ?, ?)",
            (conv_id, message_id, "user", text_content)
        )
        self.conn.commit()