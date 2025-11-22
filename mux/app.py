import asyncio
from contextlib import asynccontextmanager
import json
from time import time
import uuid
from fastapi import FastAPI, Request, Response
from sqlite3 import connect
from pydantic import BaseModel

from client_dummy import DummyClient
from client_interface import ClientInterface, Content

class ProxyCorrelator:
    def __init__(self):
        self.current_request_id = None
        self.lock = asyncio.Lock()
    
    @asynccontextmanager
    async def correlation_context(self, request_id: str):
        """Ensure only one client call happens at a time"""
        async with self.lock:
            self.current_request_id = request_id
            try:
                yield
            finally:
                self.current_request_id = None
    
    def get_current_request_id(self):
        return self.current_request_id

def db_connect():
    conn = connect('conversations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE llm_requests (
            id TEXT PRIMARY KEY,
            timestamp DATETIME,
            path TEXT,
            method TEXT,
            request_body TEXT,
            response_status INTEGER,
            response_body TEXT,
            duration_ms INTEGER
        );
    ''')
    conn.commit()
    return conn

app = FastAPI()

def get_client() -> ClientInterface:
    return DummyClient()

@app.get('/api/conv')
async def conv_list():
    async with get_client() as client:
        conversations = await client.list_conversations()
    return {"conversations": conversations}, 200

@app.post('/api/conv')
async def conv_create():
    async with get_client() as client:
        conv_id = await client.create_conversation()
    return {"id": conv_id}, 201

@app.delete('/api/conv/{conv_id}')
async def conv_delete(conv_id: str):
    async with get_client() as client:
        if await client.delete_conversation(conv_id):
            return {"status": f"Conversation deleted: {conv_id}"}, 200
        else:
            return {"error": "Conversation not found"}, 404

@app.get('/api/conv/{conv_id}')
async def conv_retrieve(conv_id: str):
    async with get_client() as client:
        conversation, messages = await client.get_messages(conv_id)
    return {
        "id": conversation.id,
        "created_at": conversation.created_at,
        "topic": conversation.topic,
        "messages": messages
    }, 200

class ConvPostRequest(BaseModel):
    content: list[Content]

@app.post('/api/conv/{conv_id}')
async def conv_post(conv_id: str, request: ConvPostRequest):
    async with get_client() as client:
        message_id = str(uuid.uuid4())
        async with ProxyCorrelator().correlation_context(message_id):
            if not await client.post_user_message(conv_id, message_id, request.content):
                return {"error": "Conversation not found"}, 404
            conversation, messages = await client.get_messages(conv_id)
    return {
        "id": conversation.id,
        "created_at": conversation.created_at,
        "topic": conversation.topic,
        "messages": messages
    }, 200



@app.api_route("/proxy/{path:path}", methods=["GET", "POST"])
async def proxy(request: Request, path: str):
    body = await request.body()
    request_id = str(uuid.uuid4())

    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO llm_requests (id, timestamp, path, method, request_body)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request_id,
            time(),
            path,
            "POST",
            body.decode('utf-8'),
        ))
        conn.commit()

    # Forward to actual LLM API
    return Response(json.dumps({
        "id": request_id,
        "object": "chat.completion",
        "created": time(),
        "model": "dummy-model",
        "choices": [
            {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I assist you today?",
                "refusal": None,
                "annotations": []
            },
            "logprobs": None,
            "finish_reason": "stop"
            }
        ],
        "usage": {},
        "service_tier": "default"
    }), 200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)