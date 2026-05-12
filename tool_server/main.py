from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from tools import (
    resolve_countries, 
    search_universities, 
    get_country_currency_rate, 
    get_univeristy_summary
)
from schemas import (
    Message,
    ChatRequest
)
import os
from fastapi import FastAPI
from prompts import system_prompt



llm = init_chat_model(os.getenv("LLM_MODEL", "gpt-5-mini"), temperature = 0.3)

tools = [
    resolve_countries,
    search_universities,
    get_univeristy_summary,
    get_country_currency_rate
]

uni_agent = create_agent(
    model=llm,
    system_prompt=system_prompt,
    tools = tools
)

app = FastAPI()

@app.get("/v1/models")
def list_models():
    """OpenWebUI запрашивает список моделей при подключении к provider."""
    return {
        "object": "list",
        "data": [{
                "id": "university-agent",
                "object": "model",
                "created": 0,
                "owned_by": "custom",
            }],
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """OpenAI compatible chat endpoint"""
    user_message = request.messages[-1].content

    result = uni_agent.invoke({
        "messages": [{"role":"user", "content": user_message}]
    })

    final_answer = result["messages"][-1].content

    return {
        "id": "chatcmpl-uniagent",
        "object": "chat.completion",
        "created": 0,
        "model": "university-agent",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": final_answer},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

@app.get('/v1/health')
def health():
    return {"status": "ok"}