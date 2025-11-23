import json
import os
from fastapi import Request, Response
from fastapi.datastructures import Headers
import httpx


class ProxyOpenAI:
    async def handle(self, request: Request, path: str) -> Response:
        target_url = self.translate_path(path)

        try:
            async with httpx.AsyncClient() as client:
                req = client.build_request(
                    request.method,
                    target_url,
                    headers=self.forward_headers(request.headers),
                    content=await request.body()
                )
                
                resp = await client.send(req)
                content = self.hack_content(path, resp.content)

                return Response(
                    content=content,
                    status_code=resp.status_code,
                    headers=self.backward_headers(resp.headers)
                )
        except NotImplementedError as e:
            return Response(
                content=json.dumps({
                    "error": {
                        "message": str(e),
                        "type": "not_implemented_error",
                        "param": None,
                        "code": None
                    }
                }),
                status_code=501,
                media_type="application/json"
            )

    def forward_headers(self, headers: Headers) -> dict[str, str]:
        forward_headers = {}
        for key, value in headers.items():
            if key.lower() in ["content-type"]:
                forward_headers[key] = value

        api_key = os.environ["OPENAI_API_KEY"]
        forward_headers["Authorization"] = f"Bearer {api_key}"
        return forward_headers
    
    def backward_headers(self, headers: httpx.Headers) -> dict[str, str]:
        backward_headers = {}
        for key, value in headers.items():
            if key.lower() in ["content-type"]:
                backward_headers[key] = value
        return backward_headers
    
    def hack_content(self, path: str, content: bytes) -> bytes:
        match path:
            case "api/v0/models":
                # Hack to convert OpenAI models response to expected format
                # for compatibility with letta's lmstudio client
                data = json.loads(content)
                for model in data["data"]:
                    model["type"] = "llm"  
                    model["compatibility_type"] = "gguf"
                return json.dumps(data).encode("utf-8")
            case _:
                return content
    
    def translate_path(self, path: str) -> str:
        match path:
            case "api/v0/chat/completions":
                return "https://api.openai.com/v1/chat/completions"
            case "api/v0/models":
                return "https://api.openai.com/v1/models"
            case _:
                raise NotImplementedError(f"Path translation for {path} not implemented")