import difflib
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

class LLMRequestContent(BaseModel):
    type: Literal["text", "thinking"]
    text: str

class LLMRequestMessage(BaseModel):
    part: Literal["request", "response"]
    message_id: str | None
    role: str
    content: list[LLMRequestContent]
    injected: bool
    tool_calls: list[LLMRequestToolCall] | None

    def __str__(self):
        result = ""
        for c in self.content:
            for line in c.text.splitlines():
                result += f"[{self.role}] [{c.type}] {line}\n"
        if self.tool_calls is not None:
            for tc in self.tool_calls:
                result += f"[{self.role}] [tool_call] {tc.type} {tc.function.name} {tc.function.arguments}\n"
        return result

def _parse_llm_content(content: list | str | None) -> list[LLMRequestContent]:
    if content is None:
        return []
    elif isinstance(content, str):
        return [LLMRequestContent(type="text", text=content)]
    else:
        return [LLMRequestContent(type=c["type"], text=c["text"]) for c in content if c["type"] == "text"]

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

def _post_process(msg: LLMRequestMessage, source: Literal["letta"]) -> LLMRequestMessage:
    match source:
        case "letta":
            if msg.role == "assistant" and len(msg.content) == 0 and msg.tool_calls is not None and len(msg.tool_calls) == 1 and msg.tool_calls[0].function.name == "send_message":
                thinking = msg.tool_calls[0].function.arguments.get("thinking")
                message = msg.tool_calls[0].function.arguments.get("message")
                new_content = []
                if thinking is not None:
                    new_content.append(LLMRequestContent(type="thinking", text=thinking))
                if message is not None:
                    new_content.append(LLMRequestContent(type="text", text=message))
                msg.content = new_content
                msg.tool_calls = None
    return msg

def parse_llm_request(llm_request_body: str, llm_response_body: str | None, source: Literal["letta"]) -> tuple[list[LLMRequestMessage], str]:
    data = json.loads(llm_request_body)
    print(json.dumps(data, indent=2))
    result = [LLMRequestMessage(
        part="request",
        message_id=m.get("id"),
        role=m["role"],
        content=_parse_llm_content(m["content"]),
        tool_calls=_parse_tool_calls(m.get("tool_calls")),
        injected=False
    ) for m in data["messages"]]
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
    return [_post_process(msg, source) for msg in result], json.dumps(data.get("tools", []))

def diff_llm_request(llm_request_body: str, llm_response_body: str, visible_parts: list[Message]) -> tuple[list[LLMRequestMessage], str]:
    llm_request, available_tools = parse_llm_request(llm_request_body, llm_response_body, "letta")
    visible_message_texts = {c.text for msg in visible_parts if msg.content for c in msg.content}
    for msg in llm_request:
        if all(c.text not in visible_message_texts for c in msg.content):
            msg.injected = True
    return llm_request, available_tools


class LLMEvent(BaseModel):
    type: Literal["message", "context_change"]
    content: str | None = None
    delta: str | None = None

class LLMContext:
    tools: str
    messages: list[LLMRequestMessage]

    def __init__(self):
        self.tools = ""
        self.messages = []

    def update(self, llm_request: list[LLMRequestMessage], available_tools: str) -> list[LLMEvent]:
        differ = difflib.Differ()
        events = []
        if self.tools != available_tools:
            self.tools = available_tools
            diff = "\n".join(l for l in differ.compare(self.tools.splitlines(), available_tools.splitlines()) if l.startswith("+ ") or l.startswith("- "))
            events.append(LLMEvent(type="context_change", delta=diff))

        old_message_str = "\n".join(str(msg) for msg in self.messages)
        new_message_str = "\n".join(str(msg) for msg in llm_request)
        diff = "\n".join(l for l in differ.compare(old_message_str.splitlines(), new_message_str.splitlines()) if l.startswith("+ ") or l.startswith("- "))
        if old_message_str != new_message_str:
            events.append(LLMEvent(type="context_change", delta=diff))
        self.messages = llm_request
        return events
    
    def push_response(self, llm_response: list[LLMRequestMessage]) -> list[LLMEvent]:
        self.messages.extend(llm_response)
        return [LLMEvent(type="message", content=str(resp)) for resp in llm_response]

def diff_sequence(sequence: list[tuple[str, str]]) -> list[LLMEvent]:
    context = LLMContext()
    events = []
    for request_body, response_body in sequence:
        llm_request_and_response, tools = parse_llm_request(request_body, response_body, "letta")
        tools = json.dumps(json.loads(tools), indent=2)
        llm_request = [msg for msg in llm_request_and_response if msg.part == "request"]
        llm_response = [msg for msg in llm_request_and_response if msg.part == "response"]
        events.extend(context.update(llm_request, tools))
        events.extend(context.push_response(llm_response))
    return events