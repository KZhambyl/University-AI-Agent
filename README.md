# University Seeker AI Agent
An AI agent that helps Kazakhstani students find universities abroad based on free-form queries — *"warm country"*, *"Europe"*, *"Japan"* — and converts local currencies to KZT in real time.

## Features

- **Natural-language parsing.** Vague queries like *"warm country"* or *"Latin America"* are mapped to a concrete list of countries via LLM-based classification with Pydantic-validated output.
- **University search.** Pulls universities by country (name, country, website) from the Universities API (Hipolabs).
- **Wikipedia summaries.** A 1–2 sentence description for each recommended university.
- **Currency conversion.** Exchange rate from the country's local currency to KZT via the Frankfurter API.
- **Agent orchestration.** LangGraph decides which tool to call and in what order — nothing is hardcoded.

## Tech Stack

| Layer | Tool |
|---|---|
| LLM | OpenAI `gpt-5-mini` |
| Agent | LangGraph (`create_agent`) + custom LangChain tools |
| Backend | FastAPI exposing OpenAI-compatible `/v1/chat/completions` |
| Frontend | OpenWebUI configured as a custom OpenAI provider |
| Observability | Langfuse v2 (self-hosted) + Pipelines filter |
| Deployment | Docker Compose |

## Architecture

```
User
  ↓
OpenWebUI  (:3010)
  ↓  OpenAI-compatible /v1/chat/completions
Pipelines server  (:9099)          ← Langfuse filter (inlet / outlet hooks)
  ↓
tool_server  (:8004)               ← FastAPI + LangGraph create_agent
  │   tools:
  │     • resolve_countries
  │     • search_universities
  │     • get_university_summary
  │     • get_country_currency_rate
  ↓
OpenAI gpt-5-mini
  ↓
Langfuse v2  (:3001) + Postgres    ← traces, tool calls, token usage
```

## Quick Start

```bash
git clone https://github.com/<your-username>/university-seeker.git
cd university-seeker

cp .env.example .env
# fill in OPENAI_API_KEY, WEBUI_SECRET_KEY, and Langfuse keys

docker-compose up -d
```

Then open:

- **OpenWebUI** → http://localhost:3010
- **Langfuse** → http://localhost:3001

In OpenWebUI, pick the `university-agent` model from the dropdown and ask anything in Russian or English.

## Tools

The agent has four tools and chooses which to use based on the query.

| Tool | Purpose | Source |
|---|---|---|
| `resolve_countries` | Map vague descriptions → list of countries | OpenAI + Pydantic |
| `search_universities` | Find universities in a country | Universities API (Hipolabs) |
| `get_university_summary` | Short description for a given university | Wikipedia REST API |
| `get_country_currency_rate` | Local currency → KZT exchange rate | Frankfurter API |

A typical loop: `resolve_countries → search_universities (×N) → get_university_summary (×N) → get_country_currency_rate (×N)` → final composition in Russian.

## Project Structure

```
.
├── docker-compose.yml
├── .env.example
├── README.md
│
├── tool_server/                 # FastAPI + LangGraph agent
│   ├── main.py                  # FastAPI app + OpenAI-compatible endpoints
│   ├── tools.py                 # 4 LangChain tools
│   ├── prompts.py               # system prompt
│   ├── schemas.py               # Pydantic models
│   ├── Dockerfile
│   └── requirements.txt
│
└── pipelines/                   # OpenWebUI Pipelines filters
    └── langfuse_filter.py       # observability filter for all chats
```

## Example Queries

- *"I want to study in a warm country"*
- *"Recommend universities in Germany"*
- *"What universities are there in Japan, and what's the JPY to KZT rate?"*
- *"Tell me about universities in Europe"*
- *"I want to go to Latin America"*

## Prompt Engineering Techniques

- **Role prompting** — system prompt opens with a role tied to the audience (Kazakhstani students), so the model defaults to Russian output and KZT.
- **Be clear and direct** — `# Strict rules` section uses `NEVER` / `ALWAYS` / `ONLY` constraints to prevent hallucination of tuition costs and exchange rates.
- **Output format control** — Pydantic schemas for tool inputs and an explicit `# Final answer format` section in the system prompt.
- **Prompt chaining** — the agent loop is itself a chain of LLM calls, each scoped to a single tool.
- **Context engineering** — every tool returns a precomposed `human_readable` string so the model never reformats numeric data and can't introduce rounding errors.

## Observability

Every chat in OpenWebUI becomes a Langfuse trace with nested generations for every tool call.

The Pipelines filter (`pipelines/langfuse_filter.py`) hooks two events on the OpenWebUI request lifecycle:

- **`inlet`** — opens a `Trace` per `chat_id` and a `Generation` per user message, with the prompt and metadata.
- **`outlet`** — closes the `Generation` with the model's output, duration, and token usage.

Open Langfuse at http://localhost:3001 to inspect token usage, latency, and the full tool-call tree for each request.

## Environment Variables

```bash
# OpenAI
OPENAI_API_KEY= ...
LLM_MODEL=gpt-5-mini

# OpenWebUI
WEBUI_SECRET_KEY=<random-string>

# Langfuse
LANGFUSE_PUBLIC_KEY= ...
LANGFUSE_SECRET_KEY= ...
LANGFUSE_HOST=http://langfuse:3000
```

## Acknowledgements

External APIs used in the agent:

- [Universities API (Hipolabs)](http://universities.hipolabs.com/) — free, no auth required.
- [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) — Wikipedia summaries.
- [Frankfurter](https://www.frankfurter.app/) — free currency exchange rates.
---

Built as the final project for the **AI Engineering** course (Lessons 49–50).
