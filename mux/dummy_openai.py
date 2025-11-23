import json
from time import time
import uuid

from fastapi import Response


class DummyOpenAI:
    def handle(self, path: str) -> Response:
        match path:
            case "v1/chat/completions":
                return self.create_completion()
            case "v1/models":
                return self.list_models()
            case _:
                return Response(json.dumps({
                    "error": {
                        "message": f"Endpoint {path} not implemented in DummyOpenAI",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": None
                    }
                }), 404)
            
    def list_models(self) -> Response:
        return Response(json.dumps({
            "object": "list",
            "data": [
                {
                    "id": "dummy-model",
                    "object": "model",
                    "created": 1686935002,
                    "owned_by": "organization-owner"
                }
            ]
        }), 200)

    def create_completion(self) -> Response:
        return Response(json.dumps({
            "id": str(uuid.uuid4()),
            "object": "chat.completion",
            "created": time(),
            "model": "dummy-model",
            "choices": [
                {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a dummy response, not from an actual LLM.",
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