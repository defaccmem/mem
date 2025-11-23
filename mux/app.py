import asyncio
from contextlib import asynccontextmanager
import json
import os
from time import time
from typing import Optional
import uuid
from fastapi import FastAPI, Request
from sqlite3 import connect
from pydantic import BaseModel

from client_letta import LettaClient
from client_interface import ClientInterface, Content, Message
from proxy import ProxyOpenAI
from differ import diff_llm_request, diff_sequence

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
                self.current_conv_id = None
                self.current_request_id = None
    

    def get_current_request_id(self) -> Optional[str]:
        return self.current_request_id

def db_connect():
    conn = connect('storage/conversations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_requests (
            id TEXT PRIMARY KEY,
            conv_id TEXT,
            user_message_id TEXT,
            assistant_message_id TEXT
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_requests (
            id TEXT PRIMARY KEY,
            timestamp DATETIME,
            path TEXT,
            method TEXT,
            request_body TEXT,
            response_status INTEGER,
            response_body TEXT,
            duration_ms INTEGER,
            correlated_request_id TEXT
        );
    ''')
    conn.commit()
    return conn

app = FastAPI()
correlator = ProxyCorrelator()

def get_client() -> ClientInterface:
    return LettaClient()

@app.get('/api/conv')
async def conv_list():
    async with get_client() as client:
        conversations = await client.list_conversations()
    return {"conversations": conversations}

@app.post('/api/conv')
async def conv_create():
    async with get_client() as client:
        conv_id = await client.create_conversation()
    return {"id": conv_id}

@app.delete('/api/conv/{conv_id}')
async def conv_delete(conv_id: str):
    async with get_client() as client:
        if await client.delete_conversation(conv_id):
            return {"status": f"Conversation deleted: {conv_id}"}
        else:
            raise Exception("Conversation not found")

def _get_correlated_llm_requests(message_id_list: list[str]) -> dict[str, list[str]]:
    query = """
        SELECT llm_requests.id FROM llm_requests INNER JOIN user_requests ON llm_requests.correlated_request_id = user_requests.id WHERE user_requests.user_message_id = ? OR user_requests.assistant_message_id = ?
    """
    correlated_requests:dict[str,list[str]] = {}
    with db_connect() as conn:
        cursor = conn.cursor()
        for message_id in message_id_list:
            cursor.execute(query, (message_id, message_id))
            rows = list(cursor.fetchall())
            if len(rows) >= 1:
                correlated_requests[message_id] = [row[0] for row in rows]
    return correlated_requests


@app.get('/api/conv/{conv_id}')
async def conv_retrieve(conv_id: str):
    return await _retrieve(conv_id)

async def _retrieve(conv_id: str):
    async with get_client() as client:
        conversation, messages = await client.get_messages(conv_id)
        correlated = _get_correlated_llm_requests([m.message_id for m in messages])
        for message in messages:
            message.llm_request_ids = correlated.get(message.message_id, [])
    return {
        "id": conversation.id,
        "created_at": conversation.created_at,
        "topic": conversation.topic,
        "messages": messages
    }

async def _retrieve1(conv_id: str, request_id: str):
    query = """
        SELECT id FROM llm_requests WHERE correlated_request_id = ?
    """
    correlated_requests:list[str] = []
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (request_id,))
        rows = list(cursor.fetchall())
        return [row[0] for row in rows]

class ConvPostRequest(BaseModel):
    content: list[Content]

@app.post('/api/conv/{conv_id}')
async def conv_post(conv_id: str, request: ConvPostRequest):
    await _do_post(conv_id, request.content)
    return await _retrieve(conv_id)

@app.post('/api/seq/{conv_id}')
async def seq_post(conv_id: str, request: ConvPostRequest):
    all_prev_request_ids = await _get_all_llm_request_ids(conv_id)
    if len(all_prev_request_ids) == 0:
        initial = None
    else:
        initial = all_prev_request_ids[-1]
    request_id = await _do_post(conv_id, request.content)
    llm_request_ids = await _retrieve1(conv_id, request_id)
    return await _seq_retrieve_llm_request_ids(conv_id, llm_request_ids, initial=initial)

async def _do_post(conv_id: str, content: list[Content]):
    request_id = str(uuid.uuid4())
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_requests (id, conv_id)
            VALUES (?, ?)
        """, (
            request_id,
            conv_id
        ))
        conn.commit()
    async with correlator.correlation_context(request_id):
        async with get_client() as client:
            resp = await client.post_user_message(conv_id, content)
            if resp is None:
                raise Exception("Conversation not found")
            user_message_id, assistant_message_id = resp
            with db_connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE user_requests
                    SET user_message_id = ?,
                    assistant_message_id = ?
                    WHERE id = ?
                """, (
                    user_message_id,
                    assistant_message_id,
                    request_id
                ))
                conn.commit()
    return request_id

@app.get("/api/llm_request")
async def llm_request_list():
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT llm_requests.id, conv_id, user_message_id, assistant_message_id FROM llm_requests LEFT JOIN user_requests ON llm_requests.correlated_request_id = user_requests.id")
        rows = cursor.fetchall()
        return [{
            "id": row[0],
            "correlated_conversation_id": row[1],
            "user_message_id": row[2],
            "assistant_message_id": row[3]
        } for row in rows]

@app.get("/api/llm_request/{llm_request_id}")
async def llm_request_retrieve(llm_request_id: str):
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT llm_requests.request_body, llm_requests.response_body, user_requests.conv_id FROM llm_requests LEFT JOIN user_requests ON llm_requests.correlated_request_id = user_requests.id WHERE llm_requests.id = ?", (llm_request_id,))
        row = cursor.fetchone()
        if row is None:
            raise Exception("LLM Request not found")
        llm_request_body = row[0]
        llm_response_body = row[1]
        conv_id = row[2]
        visible_parts = await _retrieve(conv_id)
        diff, available_tools = diff_llm_request(llm_request_body, llm_response_body, visible_parts["messages"])
        return {
            "id": llm_request_id,
            "conv_id": conv_id,
            "messages": diff,
            "available_tools": available_tools
        }

@app.get('/api/seq/{conv_id}')
async def seq_retrieve(conv_id: str):
    llm_request_ids = await _get_all_llm_request_ids(conv_id)
    return await _seq_retrieve_llm_request_ids(conv_id, llm_request_ids)

async def _get_all_llm_request_ids(conv_id: str) -> list[str]:
    messages = (await _retrieve(conv_id))["messages"]
    llm_request_ids = []
    for msg in messages:
        if msg.llm_request_ids is not None:
            llm_request_ids.extend(msg.llm_request_ids)
    return llm_request_ids

async def _seq_retrieve_llm_request_ids(conv_id: str, llm_request_ids: list[str], initial: str|None=None):
    sequence:list[tuple[str,str]] = []
    initial_body:Optional[tuple[str,str]] = None
    with db_connect() as conn:
        cursor = conn.cursor()
        for llm_request_id in llm_request_ids:
            cursor.execute("SELECT request_body, response_body FROM llm_requests WHERE id = ?", (llm_request_id,))
            row = cursor.fetchone()
            if row is not None:
                sequence.append((row[0], row[1]))
        if initial is not None:
            cursor.execute("SELECT request_body, response_body FROM llm_requests WHERE id = ?", (initial,))
            row = cursor.fetchone()
            if row is not None:
                initial_body = (row[0], row[1])
    return diff_sequence(sequence, initial_body)

@app.api_route("/proxy/{path:path}", methods=["GET", "POST"])
async def proxy(request: Request, path: str):
    body = await request.body()
    llm_request_id = str(uuid.uuid4())

    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO llm_requests (id, timestamp, path, method, request_body, correlated_request_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            llm_request_id,
            time(),
            path.removeprefix("proxy/"),
            "POST",
            body.decode('utf-8'),
            correlator.get_current_request_id()
        ))
        conn.commit()

    # Forward to actual LLM API
    start_time = time()
    response = await ProxyOpenAI().handle(request, path.removeprefix("proxy/"))
    response_body = response.body
    assert isinstance(response_body, bytes)
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE llm_requests
            SET response_status = ?,
            response_body = ?,
            duration_ms = ?
            WHERE id = ?
        """, (
            response.status_code,
            response_body.decode('utf-8'),
            int((time() - start_time) * 1000),
            llm_request_id
        ))
        conn.commit()
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)