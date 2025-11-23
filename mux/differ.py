from typing import Literal
from pydantic import BaseModel
import json

from client_interface import Content, Message

class LLMRequestToolFunctionCall(BaseModel):
    name: str
    arguments: dict

class LLMRequestToolCall(BaseModel):
    id: str
    type: Literal["function"]
    function: LLMRequestToolFunctionCall

class LLMRequestMessage(BaseModel):
    part: Literal["request", "response"]
    message_id: str | None
    role: str
    content: list[Content]
    injected: bool
    tool_calls: list[LLMRequestToolCall] | None

def _parse_llm_content(content: list | str | None) -> list[Content]:
    if content is None:
        return []
    elif isinstance(content, str):
        return [Content(type="text", text=content)]
    else:
        return [Content(type=c["type"], text=c["text"]) for c in content if c["type"] == "text"]

def _parse_tool_calls(tool_calls_data: list | None) -> list[LLMRequestToolCall] | None:
    if tool_calls_data is None:
        return None
    else:
        tool_calls = []
        for tc in tool_calls_data:
            function_data = tc.get("function", {})
            function_call = LLMRequestToolFunctionCall(
                name=function_data.get("name", ""),
                arguments=json.loads(function_data.get("arguments", "{}"))
            )
            tool_call = LLMRequestToolCall(
                id=tc.get("id", ""),
                type=tc.get("type", ""),
                function=function_call
            )
            tool_calls.append(tool_call)
        return tool_calls

def parse_llm_request(llm_request_body: str, llm_response_body: str | None) -> list[LLMRequestMessage]:
    data = json.loads(llm_request_body)
    result = [LLMRequestMessage(
        part="request",
        message_id=m.get("id"),
        role=m["role"],
        content=_parse_llm_content(m["content"]),
        tool_calls=_parse_tool_calls(m.get("tool_calls")),
        injected=False
    ) for m in data["messages"]]
    print(f"{llm_response_body=}")
    if llm_response_body is not None:
        response_data = json.loads(llm_response_body)
        result.extend([LLMRequestMessage(
            part="response",
            message_id=response_data["id"],
            role=response_data["choices"][0]["message"]["role"],
            content=_parse_llm_content(response_data["choices"][0]["message"]["content"]),
            tool_calls=_parse_tool_calls(response_data["choices"][0]["message"].get("tool_calls")),
            injected=False
        )])
    return result

def diff_llm_request(llm_request_body: str, llm_response_body: str, visible_parts: list[Message]) -> list[LLMRequestMessage]:
    llm_request = parse_llm_request(llm_request_body, llm_response_body)
    visible_message_texts = {c.text for msg in visible_parts if msg.content for c in msg.content}
    for msg in llm_request:
        if all(c.text not in visible_message_texts for c in msg.content):
            msg.injected = True
    return llm_request