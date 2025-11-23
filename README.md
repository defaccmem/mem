Create a .env file:

```
OPENAI_API_KEY=
MEM_API_KEY=
LMSTUDIO_API_KEY=
```

MEM_API_KEY and LMSTUDIO_API_KEY are the same, and are the API key that will be used to authenticate incoming requests.

Running: `docker compose up --build`

Rebuilding openapi docs: `cd docs; npx @redocly/cli build-docs openapi.yaml`
