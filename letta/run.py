from letta_client import Letta
import os

# Connect to your self-hosted server

# client = Letta(base_url="http://localhost:8283", http_client=http_client)
client = Letta(base_url="http://localhost:8283")

print("These are the models!!")
# print(client.models.list())

# Create agent with explicit embedding configuration

agent = client.agents.create(
    model="anthropic/claude-haiku-4-5-20251001",
    embedding="openai/text-embedding-3-small", # Required for self-hosted
    memory_blocks=[
        {"label": "persona", "value": "I am a helpful assistant."}
    ],
    tools=["web_search", "run_code"]
)
response = client.agents.messages.create(
    agent_id=agent.id,
    input="What do you know about me?"
)

print(response)