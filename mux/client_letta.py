from letta_client import Letta
import os

# create the client with the token set to your password
client = Letta(
  base_url="http://letta:8283",
  api_key="yourpassword"
)

agent_state = client.agents.create(
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",
    memory_blocks=[
        {
            "label": "human",
            "value": "The human's name is Chad. They like vibe coding."
        },
        {
            "label": "persona",
            "value": "My name is Sam, a helpful assistant."
        }
    ],
    tools=["web_search", "run_code"]
)

print(agent_state.id)
# print(client.agents.list())

response = client.agents.messages.create(
    agent_id=agent_state.id,
    messages=[
        {
            "role": "user",
            "content": "Hey, nice to meet you, my name is Brad."
        }
    ]
)

print(response)