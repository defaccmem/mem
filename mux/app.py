from flask import Flask
from sqlite3 import connect
import uuid

def db_connect():
    conn = connect('conversations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            conv_id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            topic TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            conv_id TEXT PRIMARY KEY,
            message_id TEXT,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    return conn


app = Flask(__name__)

@app.route('/v1/conv', methods=['GET'])
def list_conversations():
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT conv_id, created_at, topic FROM conversations")
        conversations = [{"id": row[0], "created_at": row[1], "topic": row[2]} for row in cursor.fetchall()]
    return {"conversations": conversations}, 200

@app.route('/v1/conv', methods=['POST'])
def create_conversation():
    conv_id = str(uuid.uuid4())
    with db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (conv_id, topic) VALUES (?, ?)", (conv_id, ""))
        conn.commit()
    return {"id": conv_id}, 201

@app.route('/v1/conv/<conv_id>', methods=['DELETE'])
def delete_conversation(conv_id):
    with db_connect() as conn:
        cursor = conn.cursor()
        response = cursor.execute("DELETE FROM conversations WHERE conv_id = ?", (conv_id,))
        conn.commit()
        if response.rowcount == 0:
            return {"error": "Conversation not found"}, 404
    return {"status": f"Conversation deleted: {conv_id}"}, 200

if __name__ == '__main__':
    app.run(debug=True)