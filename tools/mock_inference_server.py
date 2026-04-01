import random
import string
import time
import asyncio
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn
import argparse
import json

app = FastAPI()

# ====== 全局配置 ======
CONFIG = {
    "models": ["mock-gpt-4"],
    "min_delay": 0.1,
    "max_delay": 1.0,
    "min_tokens": 5,
    "max_tokens": 50,
}


# ====== utils ======
def random_text(n: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def random_delay():
    return random.uniform(CONFIG["min_delay"], CONFIG["max_delay"])


def validate_model(model: str):
    if model not in CONFIG["models"]:
        return CONFIG["models"][0]  # fallback
    return model


# ====== /v1/models ======
@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": m,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "mock",
            }
            for m in CONFIG["models"]
        ],
    }


# ====== response ======
def build_chat_response(model: str, content: str):
    return {
        "id": f"chatcmpl-{random_text(12)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": random.randint(5, 20),
            "completion_tokens": len(content),
            "total_tokens": len(content) + random.randint(5, 20),
        },
    }


async def stream_response(model: str, full_text: str):
    chunk_size = 5

    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i : i + chunk_size]

        data = {
            "id": f"chatcmpl-{random_text(12)}",
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [
                {
                    "delta": {"content": chunk},
                    "index": 0,
                    "finish_reason": None,
                }
            ],
        }

        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.05)

    yield "data: [DONE]\n\n"


# ====== /v1/chat/completions ======
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()

    model = validate_model(body.get("model", CONFIG["models"][0]))
    stream = body.get("stream", False)

    # 随机输出
    token_len = random.randint(CONFIG["min_tokens"], CONFIG["max_tokens"])
    content = random_text(token_len)

    # 随机延迟
    await asyncio.sleep(random_delay())

    if stream:
        return StreamingResponse(
            stream_response(model, content),
            media_type="text/event-stream",
        )
    else:
        return JSONResponse(build_chat_response(model, content))


# ====== main ======
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)

    parser.add_argument("--models", type=str, default="mock-gpt-4")
    parser.add_argument("--min-delay", type=float, default=0.1)
    parser.add_argument("--max-delay", type=float, default=1.0)
    parser.add_argument("--min-tokens", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=50)

    args = parser.parse_args()

    CONFIG["models"] = args.models.split(",")
    CONFIG["min_delay"] = args.min_delay
    CONFIG["max_delay"] = args.max_delay
    CONFIG["min_tokens"] = args.min_tokens
    CONFIG["max_tokens"] = args.max_tokens

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()